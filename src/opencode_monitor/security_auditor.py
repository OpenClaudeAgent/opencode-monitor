"""
Security Auditor - Background scanner for OpenCode command history

Scans OpenCode storage files, analyzes commands for security risks,
and stores results in a local SQLite database for audit purposes.
"""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .security import analyze_command, RiskLevel, SecurityAlert
from .logger import info, error, debug

# Paths
OPENCODE_STORAGE = Path.home() / ".local/share/opencode/storage/part"
CONFIG_DIR = Path.home() / ".config/opencode-monitor"
DB_PATH = CONFIG_DIR / "security.db"

# Scan settings
SCAN_INTERVAL = 30  # seconds between incremental scans
BATCH_SIZE = 100  # files to process per batch (for responsiveness)

# Low-value commands - stored in DB but filtered in menu display
LOW_VALUE_WORDS = {
    "cd",
    "ls",
    "cat",
    "echo",
    "pwd",
    "which",
    "head",
    "tail",
    "wc",
    "#",
}

# Store ALL commands for audit (no filtering at storage level)
STORE_ALL_COMMANDS = True

# Sensitive file patterns for read/write operations
SENSITIVE_FILE_PATTERNS = {
    # Critical (80-100)
    "critical": [
        (r"\.ssh/", 95, "SSH directory"),
        (r"id_rsa", 95, "SSH private key"),
        (r"id_ed25519", 95, "SSH private key"),
        (r"\.pem$", 90, "PEM certificate/key"),
        (r"\.key$", 90, "Private key file"),
        (r"\.env$", 85, "Environment file"),
        (r"\.env\.", 85, "Environment file"),
        (r"password", 85, "Password file"),
        (r"secret", 85, "Secret file"),
        (r"/etc/shadow", 100, "System shadow file"),
    ],
    # High (50-79)
    "high": [
        (r"/etc/passwd", 60, "System passwd file"),
        (r"/etc/", 55, "System config"),
        (r"\.aws/", 70, "AWS credentials"),
        (r"\.kube/", 65, "Kubernetes config"),
        (r"credential", 60, "Credentials file"),
        (r"token", 55, "Token file"),
        (r"\.npmrc", 60, "NPM config with tokens"),
        (r"\.pypirc", 60, "PyPI config with tokens"),
    ],
    # Medium (20-49)
    "medium": [
        (r"\.config/", 30, "Config directory"),
        (r"\.git/config", 40, "Git config"),
        (r"auth", 35, "Auth-related file"),
        (r"\.db$", 35, "Database file"),
        (r"\.sqlite", 35, "SQLite database"),
        (r"\.json$", 25, "JSON config"),
    ],
}

# URL patterns for webfetch risk analysis
SENSITIVE_URL_PATTERNS = {
    # Critical (80-100)
    "critical": [
        (r"raw\.githubusercontent\.com.*\.sh$", 90, "Shell script from GitHub"),
        (r"pastebin\.com", 85, "Pastebin content"),
        (r"hastebin", 85, "Hastebin content"),
        (r"\.(sh|bash|zsh)$", 80, "Shell script download"),
        (r"\.exe$", 95, "Executable download"),
    ],
    # High (50-79)
    "high": [
        (r"raw\.githubusercontent\.com", 55, "Raw GitHub content"),
        (r"gist\.github", 50, "GitHub Gist"),
        (r"\.py$", 50, "Python script download"),
        (r"\.js$", 50, "JavaScript download"),
    ],
    # Medium (20-49)
    "medium": [
        (r"api\.", 25, "API endpoint"),
        (r"\.json$", 20, "JSON data"),
        (r"\.xml$", 20, "XML data"),
    ],
}


@dataclass
class AuditedCommand:
    """A command that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    tool: str
    command: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int  # Unix timestamp from OpenCode
    scanned_at: str  # ISO format


@dataclass
class AuditedFileRead:
    """A file read operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedFileWrite:
    """A file write/edit operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    operation: str  # 'write' or 'edit'
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedWebFetch:
    """A webfetch operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    url: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


class SecurityAuditor:
    """Background scanner for OpenCode command security analysis"""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._scanned_ids: set = set()  # Cache of already scanned file IDs
        self._stats = {
            "total_scanned": 0,
            "total_commands": 0,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "reads_critical": 0,
            "reads_high": 0,
            "reads_medium": 0,
            "reads_low": 0,
            "writes_critical": 0,
            "writes_high": 0,
            "writes_medium": 0,
            "writes_low": 0,
            "webfetches_critical": 0,
            "webfetches_high": 0,
            "webfetches_medium": 0,
            "webfetches_low": 0,
            "last_scan": None,
        }

        # Initialize database
        self._init_db()
        self._load_scanned_ids()

    def _init_db(self):
        """Initialize SQLite database"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Commands table - stores all analyzed commands
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                tool TEXT NOT NULL,
                command TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                command_timestamp INTEGER,
                scanned_at TEXT NOT NULL
            )
        """)

        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_id ON commands(file_id)
        """)

        # File reads table - stores all file read operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                file_path TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                read_timestamp INTEGER,
                scanned_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reads_file_id ON file_reads(file_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reads_risk_level ON file_reads(risk_level)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_risk_level ON commands(risk_level)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_risk_score ON commands(risk_score DESC)
        """)

        # File writes table - stores write and edit operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                write_timestamp INTEGER,
                scanned_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_writes_file_id ON file_writes(file_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_writes_risk_level ON file_writes(risk_level)
        """)

        # Webfetches table - stores URL fetches
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webfetches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                url TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                fetch_timestamp INTEGER,
                scanned_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webfetches_file_id ON webfetches(file_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webfetches_risk_level ON webfetches(risk_level)
        """)

        # Stats table - for tracking scan progress
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_stats (
                id INTEGER PRIMARY KEY,
                last_full_scan TEXT,
                total_files_scanned INTEGER DEFAULT 0,
                total_commands INTEGER DEFAULT 0
            )
        """)

        # Initialize stats row if not exists
        cursor.execute("INSERT OR IGNORE INTO scan_stats (id) VALUES (1)")

        conn.commit()
        conn.close()

        debug("Security database initialized")

    def _load_scanned_ids(self):
        """Load already scanned file IDs into memory"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Load IDs from all tables
        self._scanned_ids = set()

        cursor.execute("SELECT file_id FROM commands")
        self._scanned_ids.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT file_id FROM file_reads")
        self._scanned_ids.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT file_id FROM file_writes")
        self._scanned_ids.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT file_id FROM webfetches")
        self._scanned_ids.update(row[0] for row in cursor.fetchall())

        # Load stats
        cursor.execute(
            "SELECT total_files_scanned, total_commands FROM scan_stats WHERE id=1"
        )
        row = cursor.fetchone()
        if row:
            self._stats["total_scanned"] = row[0] or 0
            self._stats["total_commands"] = row[1] or 0

        # Count commands by risk level
        cursor.execute("""
            SELECT risk_level, COUNT(*) FROM commands 
            GROUP BY risk_level
        """)
        for level, count in cursor.fetchall():
            if level in self._stats:
                self._stats[level] = count

        # Count reads by risk level
        cursor.execute("""
            SELECT risk_level, COUNT(*) FROM file_reads 
            GROUP BY risk_level
        """)
        for level, count in cursor.fetchall():
            key = f"reads_{level}"
            if key in self._stats:
                self._stats[key] = count

        # Count writes by risk level
        cursor.execute("""
            SELECT risk_level, COUNT(*) FROM file_writes 
            GROUP BY risk_level
        """)
        for level, count in cursor.fetchall():
            key = f"writes_{level}"
            if key in self._stats:
                self._stats[key] = count

        # Count webfetches by risk level
        cursor.execute("""
            SELECT risk_level, COUNT(*) FROM webfetches 
            GROUP BY risk_level
        """)
        for level, count in cursor.fetchall():
            key = f"webfetches_{level}"
            if key in self._stats:
                self._stats[key] = count

        # Count totals
        cursor.execute("SELECT COUNT(*) FROM file_reads")
        self._stats["total_reads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM file_writes")
        self._stats["total_writes"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM webfetches")
        self._stats["total_webfetches"] = cursor.fetchone()[0]

        conn.close()

        info(f"Loaded {len(self._scanned_ids)} scanned file IDs from database")

    def start(self):
        """Start background scanning thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        info("Security auditor started")

    def stop(self):
        """Stop background scanning"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        info("Security auditor stopped")

    def _scan_loop(self):
        """Main scanning loop"""
        # Initial scan
        self._run_scan()

        # Periodic incremental scans
        while self._running:
            time.sleep(SCAN_INTERVAL)
            if self._running:
                self._run_scan()

    def _run_scan(self):
        """Run a scan for new files"""
        start_time = time.time()
        new_files = 0
        new_commands = 0
        new_reads = 0
        new_writes = 0
        new_webfetches = 0

        if not OPENCODE_STORAGE.exists():
            debug("OpenCode storage not found")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # Scan all message directories
            for msg_dir in OPENCODE_STORAGE.iterdir():
                if not msg_dir.is_dir():
                    continue

                # Allow early exit if stopped
                if not self._running and self._thread is not None:
                    break

                for prt_file in msg_dir.glob("prt_*.json"):
                    file_id = prt_file.name

                    # Skip if already scanned
                    if file_id in self._scanned_ids:
                        continue

                    # Process file
                    result = self._process_file(prt_file)
                    if result:
                        result_type = result.get("type")

                        if result_type == "command":
                            # Insert command into database
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO commands 
                                (file_id, content_hash, session_id, tool, command, 
                                 risk_score, risk_level, risk_reason, command_timestamp, scanned_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    result["file_id"],
                                    result["content_hash"],
                                    result["session_id"],
                                    result["tool"],
                                    result["command"],
                                    result["risk_score"],
                                    result["risk_level"],
                                    result["risk_reason"],
                                    result["timestamp"],
                                    result["scanned_at"],
                                ),
                            )
                            new_commands += 1

                            # Update command stats
                            level = result["risk_level"]
                            if level in self._stats:
                                self._stats[level] += 1

                        elif result_type == "read":
                            # Insert file read into database
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO file_reads 
                                (file_id, content_hash, session_id, file_path, 
                                 risk_score, risk_level, risk_reason, read_timestamp, scanned_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    result["file_id"],
                                    result["content_hash"],
                                    result["session_id"],
                                    result["file_path"],
                                    result["risk_score"],
                                    result["risk_level"],
                                    result["risk_reason"],
                                    result["timestamp"],
                                    result["scanned_at"],
                                ),
                            )
                            new_reads += 1

                            # Update read stats
                            level = result["risk_level"]
                            reads_key = f"reads_{level}"
                            if reads_key in self._stats:
                                self._stats[reads_key] += 1

                        elif result_type == "write":
                            # Insert file write/edit into database
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO file_writes 
                                (file_id, content_hash, session_id, file_path, operation,
                                 risk_score, risk_level, risk_reason, write_timestamp, scanned_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    result["file_id"],
                                    result["content_hash"],
                                    result["session_id"],
                                    result["file_path"],
                                    result["operation"],
                                    result["risk_score"],
                                    result["risk_level"],
                                    result["risk_reason"],
                                    result["timestamp"],
                                    result["scanned_at"],
                                ),
                            )
                            new_writes += 1

                            # Update write stats
                            level = result["risk_level"]
                            writes_key = f"writes_{level}"
                            if writes_key in self._stats:
                                self._stats[writes_key] += 1

                        elif result_type == "webfetch":
                            # Insert webfetch into database
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO webfetches 
                                (file_id, content_hash, session_id, url,
                                 risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    result["file_id"],
                                    result["content_hash"],
                                    result["session_id"],
                                    result["url"],
                                    result["risk_score"],
                                    result["risk_level"],
                                    result["risk_reason"],
                                    result["timestamp"],
                                    result["scanned_at"],
                                ),
                            )
                            new_webfetches += 1

                            # Update webfetch stats
                            level = result["risk_level"]
                            webfetches_key = f"webfetches_{level}"
                            if webfetches_key in self._stats:
                                self._stats[webfetches_key] += 1

                    # Mark as scanned
                    self._scanned_ids.add(file_id)
                    new_files += 1

            # Update stats in DB
            self._stats["total_scanned"] += new_files
            self._stats["total_commands"] += new_commands
            self._stats["total_reads"] += new_reads
            self._stats["total_writes"] += new_writes
            self._stats["total_webfetches"] += new_webfetches
            self._stats["last_scan"] = datetime.now().isoformat()

            cursor.execute(
                """
                UPDATE scan_stats SET 
                    total_files_scanned = ?,
                    total_commands = ?,
                    last_full_scan = ?
                WHERE id = 1
            """,
                (
                    self._stats["total_scanned"],
                    self._stats["total_commands"],
                    self._stats["last_scan"],
                ),
            )

            conn.commit()

        except Exception as e:
            error(f"Scan error: {e}")
        finally:
            conn.close()

        elapsed = time.time() - start_time
        if new_files > 0:
            debug(
                f"Scan complete: {new_files} files, {new_commands} cmds, {new_writes} writes, {new_webfetches} fetches in {elapsed:.2f}s"
            )

    def _process_file(self, prt_file: Path) -> Optional[Dict[str, Any]]:
        """Process a single part file, return data for bash commands or file reads"""
        try:
            content = prt_file.read_bytes()
            content_hash = hashlib.md5(content).hexdigest()

            data = json.loads(content)

            # Only process tool calls
            if data.get("type") != "tool":
                return None

            tool = data.get("tool", "")
            state = data.get("state", {})
            cmd_input = state.get("input", {})

            # Process bash commands
            if tool == "bash":
                command = cmd_input.get("command", "")
                if not command:
                    return None

                alert = analyze_command(command, tool)

                return {
                    "type": "command",
                    "file_id": prt_file.name,
                    "content_hash": content_hash,
                    "session_id": data.get("sessionID", ""),
                    "tool": tool,
                    "command": command,
                    "risk_score": alert.score,
                    "risk_level": alert.level.value,
                    "risk_reason": alert.reason,
                    "timestamp": state.get("time", {}).get("start"),
                    "scanned_at": datetime.now().isoformat(),
                }

            # Process file reads
            elif tool == "read":
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None

                score, level, reason = self._analyze_file_path(file_path)

                return {
                    "type": "read",
                    "file_id": prt_file.name,
                    "content_hash": content_hash,
                    "session_id": data.get("sessionID", ""),
                    "file_path": file_path,
                    "risk_score": score,
                    "risk_level": level,
                    "risk_reason": reason,
                    "timestamp": state.get("time", {}).get("start"),
                    "scanned_at": datetime.now().isoformat(),
                }

            # Process file writes (write tool)
            elif tool == "write":
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None

                # Writes are inherently more risky than reads - add base score
                score, level, reason = self._analyze_file_path(
                    file_path, write_mode=True
                )

                return {
                    "type": "write",
                    "file_id": prt_file.name,
                    "content_hash": content_hash,
                    "session_id": data.get("sessionID", ""),
                    "file_path": file_path,
                    "operation": "write",
                    "risk_score": score,
                    "risk_level": level,
                    "risk_reason": reason,
                    "timestamp": state.get("time", {}).get("start"),
                    "scanned_at": datetime.now().isoformat(),
                }

            # Process file edits (edit tool)
            elif tool == "edit":
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None

                # Edits are inherently more risky than reads - add base score
                score, level, reason = self._analyze_file_path(
                    file_path, write_mode=True
                )

                return {
                    "type": "write",  # Store as write type
                    "file_id": prt_file.name,
                    "content_hash": content_hash,
                    "session_id": data.get("sessionID", ""),
                    "file_path": file_path,
                    "operation": "edit",
                    "risk_score": score,
                    "risk_level": level,
                    "risk_reason": reason,
                    "timestamp": state.get("time", {}).get("start"),
                    "scanned_at": datetime.now().isoformat(),
                }

            # Process webfetch operations
            elif tool == "webfetch":
                url = cmd_input.get("url", "")
                if not url:
                    return None

                score, level, reason = self._analyze_url(url)

                return {
                    "type": "webfetch",
                    "file_id": prt_file.name,
                    "content_hash": content_hash,
                    "session_id": data.get("sessionID", ""),
                    "url": url,
                    "risk_score": score,
                    "risk_level": level,
                    "risk_reason": reason,
                    "timestamp": state.get("time", {}).get("start"),
                    "scanned_at": datetime.now().isoformat(),
                }

            return None

        except Exception as e:
            debug(f"Error processing {prt_file}: {e}")
            return None

    def _analyze_file_path(self, file_path: str, write_mode: bool = False) -> tuple:
        """Analyze a file path for security risk

        Args:
            file_path: The file path to analyze
            write_mode: If True, adds base score for write/edit operations (more risky)
        """
        import re

        path_lower = file_path.lower()
        max_score = 0
        reason = "Normal file"

        # Check critical patterns
        for pattern, score, desc in SENSITIVE_FILE_PATTERNS.get("critical", []):
            if re.search(pattern, path_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Check high patterns
        for pattern, score, desc in SENSITIVE_FILE_PATTERNS.get("high", []):
            if re.search(pattern, path_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Check medium patterns
        for pattern, score, desc in SENSITIVE_FILE_PATTERNS.get("medium", []):
            if re.search(pattern, path_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Write/edit operations are inherently more risky
        if write_mode and max_score > 0:
            max_score = min(100, max_score + 10)
            reason = f"WRITE: {reason}"

        # Determine level
        if max_score >= 80:
            level = "critical"
        elif max_score >= 50:
            level = "high"
        elif max_score >= 20:
            level = "medium"
        else:
            level = "low"

        return max_score, level, reason

    def _analyze_url(self, url: str) -> tuple:
        """Analyze a URL for security risk"""
        import re

        url_lower = url.lower()
        max_score = 0
        reason = "Normal URL"

        # Check critical patterns
        for pattern, score, desc in SENSITIVE_URL_PATTERNS.get("critical", []):
            if re.search(pattern, url_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Check high patterns
        for pattern, score, desc in SENSITIVE_URL_PATTERNS.get("high", []):
            if re.search(pattern, url_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Check medium patterns
        for pattern, score, desc in SENSITIVE_URL_PATTERNS.get("medium", []):
            if re.search(pattern, url_lower):
                if score > max_score:
                    max_score = score
                    reason = desc

        # Determine level
        if max_score >= 80:
            level = "critical"
        elif max_score >= 50:
            level = "high"
        elif max_score >= 20:
            level = "medium"
        else:
            level = "low"

        return max_score, level, reason

    def get_stats(self) -> Dict[str, Any]:
        """Get current scan statistics"""
        with self._lock:
            return self._stats.copy()

    def get_critical_commands(self, limit: int = 20) -> List[AuditedCommand]:
        """Get recent critical and high risk commands"""
        return self._get_commands_by_level(["critical", "high"], limit)

    def get_commands_by_level(
        self, level: str, limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk level"""
        return self._get_commands_by_level([level], limit)

    def _get_commands_by_level(
        self, levels: List[str], limit: int
    ) -> List[AuditedCommand]:
        """Internal method to fetch commands by risk levels"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(levels))
        cursor.execute(
            f"""
            SELECT id, file_id, session_id, tool, command, 
                   risk_score, risk_level, risk_reason, command_timestamp, scanned_at
            FROM commands 
            WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, command_timestamp DESC
            LIMIT ?
        """,
            (*levels, limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedCommand(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    tool=row[3],
                    command=row[4],
                    risk_score=row[5],
                    risk_level=row[6],
                    risk_reason=row[7],
                    timestamp=row[8] or 0,
                    scanned_at=row[9],
                )
            )

        conn.close()
        return results

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, tool, command, 
                   risk_score, risk_level, risk_reason, command_timestamp, scanned_at
            FROM commands 
            ORDER BY command_timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedCommand(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    tool=row[3],
                    command=row[4],
                    risk_score=row[5],
                    risk_level=row[6],
                    risk_reason=row[7],
                    timestamp=row[8] or 0,
                    scanned_at=row[9],
                )
            )

        conn.close()
        return results

    def get_sensitive_reads(self, limit: int = 20) -> List[AuditedFileRead]:
        """Get recent sensitive file reads (critical and high risk)"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, 
                   risk_score, risk_level, risk_reason, read_timestamp, scanned_at
            FROM file_reads 
            WHERE risk_level IN ('critical', 'high')
            ORDER BY risk_score DESC, read_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedFileRead(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    file_path=row[3],
                    risk_score=row[4],
                    risk_level=row[5],
                    risk_reason=row[6],
                    timestamp=row[7] or 0,
                    scanned_at=row[8],
                )
            )

        conn.close()
        return results

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, 
                   risk_score, risk_level, risk_reason, read_timestamp, scanned_at
            FROM file_reads 
            ORDER BY read_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedFileRead(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    file_path=row[3],
                    risk_score=row[4],
                    risk_level=row[5],
                    risk_reason=row[6],
                    timestamp=row[7] or 0,
                    scanned_at=row[8],
                )
            )

        conn.close()
        return results

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes/edits"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, operation,
                   risk_score, risk_level, risk_reason, write_timestamp, scanned_at
            FROM file_writes 
            ORDER BY write_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedFileWrite(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    file_path=row[3],
                    operation=row[4],
                    risk_score=row[5],
                    risk_level=row[6],
                    risk_reason=row[7],
                    timestamp=row[8] or 0,
                    scanned_at=row[9],
                )
            )

        conn.close()
        return results

    def get_sensitive_writes(self, limit: int = 20) -> List[AuditedFileWrite]:
        """Get recent sensitive file writes (critical and high risk)"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, operation,
                   risk_score, risk_level, risk_reason, write_timestamp, scanned_at
            FROM file_writes 
            WHERE risk_level IN ('critical', 'high')
            ORDER BY risk_score DESC, write_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedFileWrite(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    file_path=row[3],
                    operation=row[4],
                    risk_score=row[5],
                    risk_level=row[6],
                    risk_reason=row[7],
                    timestamp=row[8] or 0,
                    scanned_at=row[9],
                )
            )

        conn.close()
        return results

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetch operations"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, url,
                   risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at
            FROM webfetches 
            ORDER BY fetch_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedWebFetch(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    url=row[3],
                    risk_score=row[4],
                    risk_level=row[5],
                    risk_reason=row[6],
                    timestamp=row[7] or 0,
                    scanned_at=row[8],
                )
            )

        conn.close()
        return results

    def get_risky_webfetches(self, limit: int = 20) -> List[AuditedWebFetch]:
        """Get recent risky webfetch operations (critical and high risk)"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, file_id, session_id, url,
                   risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at
            FROM webfetches 
            WHERE risk_level IN ('critical', 'high')
            ORDER BY risk_score DESC, fetch_timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                AuditedWebFetch(
                    id=row[0],
                    file_id=row[1],
                    session_id=row[2],
                    url=row[3],
                    risk_score=row[4],
                    risk_level=row[5],
                    risk_reason=row[6],
                    timestamp=row[7] or 0,
                    scanned_at=row[8],
                )
            )

        conn.close()
        return results

    def generate_report(self) -> str:
        """Generate a text report of security findings"""
        stats = self.get_stats()
        critical_cmds = self.get_critical_commands(10)
        sensitive_reads = self.get_sensitive_reads(10)
        sensitive_writes = self.get_sensitive_writes(10)
        risky_fetches = self.get_risky_webfetches(10)

        lines = [
            "=" * 60,
            "OPENCODE SECURITY AUDIT REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "SUMMARY",
            "-" * 40,
            f"Total files scanned: {stats['total_scanned']}",
            f"Total commands: {stats['total_commands']}",
            f"Total file reads: {stats['total_reads']}",
            f"Total file writes: {stats['total_writes']}",
            f"Total webfetches: {stats['total_webfetches']}",
            f"Last scan: {stats['last_scan'] or 'Never'}",
            "",
            "COMMANDS - RISK DISTRIBUTION",
            "-" * 40,
            f"🔴 Critical: {stats['critical']}",
            f"🟠 High:     {stats['high']}",
            f"🟡 Medium:   {stats['medium']}",
            f"🟢 Low:      {stats['low']}",
            "",
            "FILE READS - RISK DISTRIBUTION",
            "-" * 40,
            f"🔴 Critical: {stats['reads_critical']}",
            f"🟠 High:     {stats['reads_high']}",
            f"🟡 Medium:   {stats['reads_medium']}",
            f"🟢 Low:      {stats['reads_low']}",
            "",
            "FILE WRITES - RISK DISTRIBUTION",
            "-" * 40,
            f"🔴 Critical: {stats['writes_critical']}",
            f"🟠 High:     {stats['writes_high']}",
            f"🟡 Medium:   {stats['writes_medium']}",
            f"🟢 Low:      {stats['writes_low']}",
            "",
            "WEBFETCHES - RISK DISTRIBUTION",
            "-" * 40,
            f"🔴 Critical: {stats['webfetches_critical']}",
            f"🟠 High:     {stats['webfetches_high']}",
            f"🟡 Medium:   {stats['webfetches_medium']}",
            f"🟢 Low:      {stats['webfetches_low']}",
            "",
        ]

        if critical_cmds:
            lines.extend(
                [
                    "TOP CRITICAL/HIGH RISK COMMANDS",
                    "-" * 40,
                ]
            )
            for cmd in critical_cmds:
                emoji = "🔴" if cmd.risk_level == "critical" else "🟠"
                lines.extend(
                    [
                        f"{emoji} [{cmd.risk_score}] {cmd.risk_reason}",
                        f"   {cmd.command}",
                        "",
                    ]
                )

        if sensitive_reads:
            lines.extend(
                [
                    "TOP SENSITIVE FILE READS",
                    "-" * 40,
                ]
            )
            for read in sensitive_reads:
                emoji = "🔴" if read.risk_level == "critical" else "🟠"
                lines.extend(
                    [
                        f"{emoji} [{read.risk_score}] {read.risk_reason}",
                        f"   {read.file_path}",
                        "",
                    ]
                )

        if sensitive_writes:
            lines.extend(
                [
                    "TOP SENSITIVE FILE WRITES/EDITS",
                    "-" * 40,
                ]
            )
            for write in sensitive_writes:
                emoji = "🔴" if write.risk_level == "critical" else "🟠"
                lines.extend(
                    [
                        f"{emoji} [{write.risk_score}] {write.risk_reason} ({write.operation})",
                        f"   {write.file_path}",
                        "",
                    ]
                )

        if risky_fetches:
            lines.extend(
                [
                    "TOP RISKY WEBFETCHES",
                    "-" * 40,
                ]
            )
            for fetch in risky_fetches:
                emoji = "🔴" if fetch.risk_level == "critical" else "🟠"
                lines.extend(
                    [
                        f"{emoji} [{fetch.risk_score}] {fetch.risk_reason}",
                        f"   {fetch.url}",
                        "",
                    ]
                )

        lines.append("=" * 60)

        return "\n".join(lines)


# Global instance
_auditor: Optional[SecurityAuditor] = None


def get_auditor() -> SecurityAuditor:
    """Get or create the global auditor instance"""
    global _auditor
    if _auditor is None:
        _auditor = SecurityAuditor()
    return _auditor


def start_auditor():
    """Start the security auditor"""
    get_auditor().start()


def stop_auditor():
    """Stop the security auditor"""
    global _auditor
    if _auditor:
        _auditor.stop()
        _auditor = None
