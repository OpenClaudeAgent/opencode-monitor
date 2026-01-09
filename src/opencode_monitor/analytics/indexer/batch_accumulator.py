"""
FileBatchAccumulator - US-2: Micro-batch accumulator for file indexing.

Accumulates detected files from watchdog and triggers micro-batches for DuckDB.
Thread-safe implementation with deduplication and configurable triggers.

Configuration validated by POC:
- window_ms: 200ms latency acceptable
- max_files: 200 optimizes burst mode (4,916 files/sec)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Set
import threading


@dataclass
class AccumulatorConfig:
    """Configuration for FileBatchAccumulator.

    Attributes:
        window_ms: Maximum time to wait before flushing (milliseconds).
        max_files: Maximum files to accumulate before flushing.
        flush_on_stop: Whether to flush pending files on stop().
    """

    window_ms: int = 200
    max_files: int = 200
    flush_on_stop: bool = True


@dataclass
class AccumulatorStats:
    """Statistics for FileBatchAccumulator.

    Attributes:
        batches_sent: Total number of batches sent.
        files_accumulated: Total files accumulated.
        files_deduplicated: Files skipped due to deduplication.
        batches_by_timer: Batches triggered by window_ms timer.
        batches_by_max_files: Batches triggered by max_files threshold.
    """

    batches_sent: int = 0
    files_accumulated: int = 0
    files_deduplicated: int = 0
    batches_by_timer: int = 0
    batches_by_max_files: int = 0


class FileBatchAccumulator:
    """Thread-safe file batch accumulator with deduplication.

    Accumulates files and triggers batches either when:
    - max_files threshold is reached, OR
    - window_ms timer expires

    Features:
    - Thread-safe via Lock
    - Automatic deduplication via Set
    - Non-blocking callbacks (executed in separate thread)

    Example:
        >>> def process_batch(files: List[Path]) -> None:
        ...     print(f"Processing {len(files)} files")
        >>>
        >>> config = AccumulatorConfig(window_ms=200, max_files=100)
        >>> acc = FileBatchAccumulator(config, process_batch)
        >>> acc.add(Path("/path/to/file.json"))
        >>> acc.stop()
    """

    def __init__(
        self,
        config: AccumulatorConfig,
        on_batch_ready: Callable[[List[Path]], None],
    ) -> None:
        """Initialize the accumulator.

        Args:
            config: Accumulator configuration.
            on_batch_ready: Callback called with list of files when batch is ready.
        """
        self._config = config
        self._on_batch_ready = on_batch_ready

        # Thread safety
        self._lock = threading.Lock()
        self._stopped = False

        # File accumulation (Set for deduplication)
        self._pending_files: Set[Path] = set()

        # Statistics
        self._stats = AccumulatorStats()

        # Timer for window_ms trigger
        self._timer: Optional[threading.Timer] = None
        self._timer_started = False

    def add(self, file_path: Path) -> None:
        """Add a single file to the accumulator. Thread-safe.

        Args:
            file_path: Path to the file to accumulate.
        """
        with self._lock:
            if self._stopped:
                return

            if file_path in self._pending_files:
                self._stats.files_deduplicated += 1
                return

            self._pending_files.add(file_path)
            self._stats.files_accumulated += 1

            # Check if max_files reached
            if len(self._pending_files) >= self._config.max_files:
                self._flush_internal(trigger="max_files")
            elif not self._timer_started:
                # Start timer on first file
                self._start_timer()

    def add_many(self, files: List[Path]) -> None:
        """Add multiple files to the accumulator. Thread-safe.

        Args:
            files: List of file paths to accumulate.
        """
        with self._lock:
            if self._stopped:
                return

            for file_path in files:
                if file_path in self._pending_files:
                    self._stats.files_deduplicated += 1
                else:
                    self._pending_files.add(file_path)
                    self._stats.files_accumulated += 1

            # Check if max_files reached
            if len(self._pending_files) >= self._config.max_files:
                self._flush_internal(trigger="max_files")
            elif len(self._pending_files) > 0 and not self._timer_started:
                # Start timer if we have files
                self._start_timer()

    def force_flush(self) -> int:
        """Force immediate flush of accumulated files.

        Returns:
            Number of files flushed.
        """
        with self._lock:
            if not self._pending_files:
                return 0
            return self._flush_internal(trigger="force")

    def stop(self) -> None:
        """Stop the accumulator gracefully.

        Flushes pending files if flush_on_stop is True.
        """
        with self._lock:
            if self._stopped:
                return

            self._stopped = True

            # Cancel timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
                self._timer_started = False

            # Flush if configured
            if self._config.flush_on_stop and self._pending_files:
                self._flush_internal(trigger="stop")

    def get_stats(self) -> AccumulatorStats:
        """Get current accumulator statistics.

        Returns:
            AccumulatorStats with current counters.
        """
        with self._lock:
            return AccumulatorStats(
                batches_sent=self._stats.batches_sent,
                files_accumulated=self._stats.files_accumulated,
                files_deduplicated=self._stats.files_deduplicated,
                batches_by_timer=self._stats.batches_by_timer,
                batches_by_max_files=self._stats.batches_by_max_files,
            )

    def _start_timer(self) -> None:
        """Start the window timer. Must be called with lock held."""
        if self._timer is not None:
            self._timer.cancel()

        self._timer = threading.Timer(
            self._config.window_ms / 1000.0,
            self._on_timer_expired,
        )
        self._timer.daemon = True
        self._timer.start()
        self._timer_started = True

    def _on_timer_expired(self) -> None:
        """Handle timer expiration."""
        with self._lock:
            if self._stopped:
                return

            self._timer_started = False

            if self._pending_files:
                self._flush_internal(trigger="timer")

    def _flush_internal(self, trigger: str) -> int:
        """Internal flush - must be called with lock held.

        Args:
            trigger: What triggered the flush ("timer", "max_files", "force", "stop")

        Returns:
            Number of files flushed.
        """
        if not self._pending_files:
            return 0

        # Cancel existing timer
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
            self._timer_started = False

        # Take snapshot of files
        files_to_send = list(self._pending_files)
        self._pending_files.clear()

        # Update stats
        self._stats.batches_sent += 1
        if trigger == "timer":
            self._stats.batches_by_timer += 1
        elif trigger == "max_files":
            self._stats.batches_by_max_files += 1
        # "force" and "stop" don't increment specific counters

        # Execute callback in separate thread (non-blocking)
        callback_thread = threading.Thread(
            target=self._on_batch_ready,
            args=(files_to_send,),
            daemon=True,
        )
        callback_thread.start()

        return len(files_to_send)
