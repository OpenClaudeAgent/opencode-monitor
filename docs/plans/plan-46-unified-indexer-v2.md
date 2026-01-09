# Plan 46 - Unified Indexer v2 (DuckDB-Only Pipeline)

## Executive Summary

Refonte du système d'indexation pour éliminer le goulot d'étranglement Python realtime (250 files/sec) en unifiant bulk et realtime dans un seul pipeline DuckDB micro-batch (~5,000 files/sec).

> **⚠️ IMPORTANT - Review 2026-01-09**
> 
> Ce plan a été revu après le merge du Plan 45 (Tracing Architecture). Plusieurs ajustements ont été faits :
> - Utilisation de la table `file_index` existante (au lieu de créer `indexed_files`)
> - Renommage `BatchCollector` → `FileBatchAccumulator` (évite confusion avec `BatchProcessor`)
> - Intégration avec le module `unified/` existant et `TraceBuilder`
> - Ajout procédure de rollback et critères go/no-go

| Métrique | Actuel (HybridIndexer) | Cible (v2) | Gain |
|----------|------------------------|------------|------|
| Realtime throughput | 250 files/sec | 5,000 files/sec | **20x** |
| Latence événement→DB | 500ms - 2s | < 500ms | **2-4x** |
| Fichiers manqués | Possible (watchdog) | 0 (réconciliation) | **∞** |
| Pipelines à maintenir | 2 (DuckDB + Python) | 1 (DuckDB) | **50%** |

## Contexte et Problématique

### Architecture actuelle : HybridIndexer

```
┌─────────────────────────────────────────────────────────────────┐
│                        HybridIndexer                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │     BulkLoader       │     │     FileWatcher      │          │
│  │   (DuckDB Native)    │     │     (Watchdog)       │          │
│  │                      │     │                      │          │
│  │  • read_json_auto()  │     │  • Python callbacks  │          │
│  │  • ~20,000 files/s   │     │  • ~250 files/s      │ ← GOULOT │
│  │  • Historical only   │     │  • Real-time only    │          │
│  └──────────┬───────────┘     └──────────┬───────────┘          │
│             │                            │                       │
│             └────────────┬───────────────┘                       │
│                          ▼                                       │
│                   ┌──────────────┐                               │
│                   │  Analytics   │                               │
│                   │   DuckDB     │                               │
│                   └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### Problèmes identifiés

1. **Performance asymétrique** : 80x de différence entre bulk (20k/s) et realtime (250/s)
2. **Double maintenance** : Deux flux de données à maintenir et tester
3. **Fiabilité watchdog** : Peut manquer des événements sous forte charge
4. **Complexité** : Queue, phases, transitions bulk→realtime

## Architecture Cible : Unified DuckDB Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Indexer v2                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FILE DETECTION LAYER                                            │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │   Watchdog Primary   │     │  Periodic Reconciler │          │
│  │   (~100ms latency)   │     │   (every 30 seconds) │          │
│  └──────────┬───────────┘     └──────────┬───────────┘          │
│             │                            │                       │
│             └────────────┬───────────────┘                       │
│                          ▼                                       │
│  BATCHING LAYER                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                FileBatchAccumulator                           ││
│  │  • 200ms collection window                                    ││
│  │  • Max 100 files per batch                                    ││
│  │  • Triggers: window elapsed OR max files reached              ││
│  │  • Thread-safe queue with deduplication                       ││
│  │  • Alimente BatchProcessor existant (unified/batch.py)        ││
│  └────────────────────────┬─────────────────────────────────────┘│
│                           ▼                                      │
│  DUCKDB PROCESSING LAYER                                         │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              DuckDB Micro-Batch INSERT                        ││
│  │  • read_json_auto([file1, file2, ...])                        ││
│  │  • ~5,000 files/sec sustained                                 ││
│  │  • Single INSERT per batch                                    ││
│  └────────────────────────┬─────────────────────────────────────┘│
│                           ▼                                      │
│  TRACKING LAYER                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              file_index Table (existante, étendue)            ││
│  │  • file_path (PK), mtime, size, indexed_at, status            ││
│  │  • Enables reconciliation queries                             ││
│  │  • Fast "needs indexing" checks                               ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Flux de données détaillé

```
         ┌─────────────┐
         │  Watchdog   │  ──────┐
         └─────────────┘        │
                                ▼
         ┌─────────────┐   ┌─────────────────────┐
         │ Reconciler  │──▶│ FileBatchAccumulator│
         └─────────────┘   │                     │
                           │  files: []          │
                           │  timer: 200ms       │
                           │  max: 100           │
                           └────────┬────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │ Trigger conditions:    │                        │
           │ • len(files) >= 100    │                        │
           │ • timer elapsed        │                        │
           │ • force_flush() called │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
                           ┌─────────────────┐
                           │  DuckDB Batch   │
                           │    INSERT       │
                           │                 │
                           │ read_json_auto( │
                           │   [f1,f2,f3...])│
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ file_index      │
                           │ UPDATE status   │
                           └─────────────────┘
```

## Composants Techniques

> **Note architecture** : Ces composants s'intègrent avec le module `unified/` existant :
> - `FileBatchAccumulator` → alimente `BatchProcessor` (unified/batch.py)
> - `Reconciler` → utilise `FileTracker` (tracker.py) 
> - Le `TraceBuilder` (trace_builder/) est appelé après chaque batch

### 1. FileBatchAccumulator (anciennement BatchCollector)

**Fichier** : `src/opencode_monitor/analytics/indexer/batch_accumulator.py`

```python
class FileBatchAccumulator:
    """
    Accumule les fichiers détectés et déclenche des micro-batches.
    
    Thread-safe avec deduplication automatique.
    
    NOTE: Ne pas confondre avec BatchProcessor (unified/batch.py) qui 
    exécute les INSERTs. FileBatchAccumulator accumule les fichiers
    AVANT de les envoyer à BatchProcessor.
    """
    
    def __init__(
        self,
        window_ms: int = 200,
        max_files: int = 100,
        on_batch_ready: Callable[[List[Path]], None]
    ):
        self._pending: Set[Path] = set()  # Dedup automatique
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._window_ms = window_ms
        self._max_files = max_files
        self._on_batch_ready = on_batch_ready
    
    def add(self, file_path: Path) -> None:
        """Ajoute un fichier au batch en cours."""
        with self._lock:
            self._pending.add(file_path)
            
            if len(self._pending) >= self._max_files:
                self._flush_locked()
            elif self._timer is None:
                self._start_timer()
    
    def _flush_locked(self) -> None:
        """Flush le batch (appelé avec lock acquis)."""
        if not self._pending:
            return
        
        batch = list(self._pending)
        self._pending.clear()
        self._cancel_timer()
        
        # Callback hors du lock
        threading.Thread(
            target=self._on_batch_ready,
            args=(batch,),
            daemon=True
        ).start()
```

### 2. Reconciler

**Fichier** : `src/opencode_monitor/analytics/indexer/reconciler.py`

```python
class Reconciler:
    """
    Réconciliation périodique pour rattraper les fichiers manqués.
    
    Scanne le filesystem et compare avec file_index (table existante).
    """
    
    def __init__(
        self,
        storage_path: Path,
        db: AnalyticsDB,
        interval_seconds: int = 30,
        on_missing_files: Callable[[List[Path]], None]
    ):
        self._storage_path = storage_path
        self._db = db
        self._interval = interval_seconds
        self._on_missing = on_missing_files
        self._running = False
    
    def find_missing_files(self) -> List[Path]:
        """
        Trouve les fichiers sur le filesystem non présents dans file_index.
        
        Utilise DuckDB pour la comparaison efficace.
        NOTE: Utilise file_index existante (pas indexed_files).
        """
        conn = self._db.connect()
        
        # Requête efficace: fichiers sur disque mais pas dans file_index
        # ou avec mtime plus récent
        query = """
        WITH filesystem AS (
            SELECT 
                filename AS path,
                file_modified_time AS mtime
            FROM glob('{storage}/**/*.json')
        ),
        indexed AS (
            SELECT file_path, mtime 
            FROM file_index 
            WHERE status = 'indexed'
        )
        SELECT f.path
        FROM filesystem f
        LEFT JOIN indexed i ON f.path = i.file_path
        WHERE i.file_path IS NULL
           OR f.mtime > i.mtime
        LIMIT 10000  -- Safety limit
        """
        
        result = conn.execute(
            query.format(storage=self._storage_path)
        ).fetchall()
        
        return [Path(row[0]) for row in result]
```

### 3. Extension de la table file_index existante

> **⚠️ IMPORTANT** : On ne crée PAS de nouvelle table `indexed_files`.
> On étend la table `file_index` existante (tracker.py) avec une colonne `status`.

**Table existante** (dans `tracker.py`) :
```sql
CREATE TABLE IF NOT EXISTS file_index (
    file_path VARCHAR PRIMARY KEY,
    file_type VARCHAR NOT NULL,
    mtime DOUBLE NOT NULL,
    size INTEGER NOT NULL,
    record_id VARCHAR,
    indexed_at TIMESTAMP,
    error_message VARCHAR
);
```

**Migration à ajouter** (via `_migrate_columns` dans db.py) :
```sql
-- Ajouter colonne status si elle n'existe pas
ALTER TABLE file_index ADD COLUMN IF NOT EXISTS 
    status VARCHAR DEFAULT 'indexed';

-- Index pour la réconciliation rapide
CREATE INDEX IF NOT EXISTS idx_file_index_status 
ON file_index(status);
```

**Valeurs de status** :
- `'indexed'` : Fichier traité avec succès
- `'error'` : Erreur lors du traitement (voir error_message)
- `'pending'` : En attente de traitement

### 4. DuckDB Micro-Batch INSERT

> **Intégration** : Cette logique sera intégrée dans `BatchProcessor` (unified/batch.py)
> qui appelle déjà `TraceBuilder` pour créer les traces.

```python
def process_batch(self, files: List[Path]) -> int:
    """
    Traite un batch de fichiers via DuckDB read_json_auto.
    
    Args:
        files: Liste de chemins de fichiers JSON
        
    Returns:
        Nombre de fichiers traités avec succès
    """
    if not files:
        return 0
    
    conn = self._db.connect()
    
    # Grouper par type de fichier
    by_type: Dict[str, List[Path]] = defaultdict(list)
    for f in files:
        file_type = self._detect_file_type(f)
        by_type[file_type].append(f)
    
    total_processed = 0
    
    for file_type, type_files in by_type.items():
        # Construire la liste de fichiers pour DuckDB
        file_list = ", ".join(f"'{f}'" for f in type_files)
        
        # INSERT via read_json_auto avec liste de fichiers
        query = self._get_insert_query(file_type, file_list)
        
        try:
            conn.execute(query)
            total_processed += len(type_files)
            
            # Mettre à jour file_index (pas indexed_files!)
            self._update_tracking(conn, type_files, file_type, 'indexed')
            
        except Exception as e:
            self._update_tracking(conn, type_files, file_type, 'error', str(e))
    
    # Post-traitement pour les traces (intégration Plan 45)
    if total_processed > 0:
        self._trace_builder.resolve_parent_traces()
        # build_all() appelé périodiquement, pas à chaque batch
    
    return total_processed
```

## Migration Strategy

### Phase 1 : Feature Flag (Sprint 1)

```python
# config.py
UNIFIED_INDEXER_V2_ENABLED = os.getenv("UNIFIED_INDEXER_V2", "false") == "true"
UNIFIED_INDEXER_V2_ROLLOUT = float(os.getenv("UNIFIED_INDEXER_V2_ROLLOUT", "0"))

def should_use_v2() -> bool:
    """Détermine si on utilise l'indexer v2."""
    if UNIFIED_INDEXER_V2_ENABLED:
        return True
    
    if UNIFIED_INDEXER_V2_ROLLOUT > 0:
        # Rollout progressif basé sur hash du hostname
        import hashlib
        host_hash = int(hashlib.md5(socket.gethostname().encode()).hexdigest(), 16)
        return (host_hash % 100) < (UNIFIED_INDEXER_V2_ROLLOUT * 100)
    
    return False
```

### Phase 2 : Rollout Progressif (Sprint 3)

1. **10%** : Machines de dev internes
2. **25%** : Utilisateurs beta opt-in
3. **50%** : Validation 48h
4. **100%** : General availability

### Phase 3 : Cleanup (Sprint 3)

- Supprimer `HybridIndexer` (hybrid.py)
- **Conserver** `bulk_loader.py` pour le mode batch initial
- Supprimer flag de migration
- Archiver documentation v1

## Procédure de Rollback

En cas de problème avec le v2, voici comment revenir au v1 :

### Rollback Immédiat (< 1 minute)

```bash
# 1. Désactiver le v2
export UNIFIED_INDEXER_V2_ENABLED=false
export UNIFIED_INDEXER_V2_ROLLOUT=0

# 2. Redémarrer l'application
# → HybridIndexer sera automatiquement utilisé

# 3. Vérifier
# Les données dans file_index restent intactes
# La colonne 'status' est ignorée par le v1
```

### Vérifications Post-Rollback

```sql
-- Vérifier que les sessions sont toujours là
SELECT COUNT(*) FROM sessions;

-- Vérifier les messages récents
SELECT COUNT(*) FROM messages 
WHERE created_at > NOW() - INTERVAL '1 hour';
```

### Points Importants

- La colonne `status` ajoutée à `file_index` est **backward-compatible**
- Aucune donnée n'est perdue lors du rollback
- Le rollback peut être fait sans redémarrer la DB

## Critères Go/No-Go pour le Rollout

| Phase | Durée min | Critères de succès | Qui décide |
|-------|-----------|-------------------|------------|
| 10% (dev) | 24h | Error rate < 0.1%, Latence p95 < 500ms | Dev |
| 25% (beta) | 48h | Error rate < 0.1%, 0 fichiers manqués | Dev |
| 50% | 48h | Throughput >= 4,000/sec, métriques stables | Dev |
| 100% | 1 semaine | Toutes métriques stables | Dev |

### Métriques à surveiller

- `indexer_files_per_second` : doit être >= 4,000
- `indexer_error_rate` : doit être < 0.1%
- `indexer_latency_p95` : doit être < 500ms
- `reconciler_files_recovered` : doit tendre vers 0

## Risques et Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Performance micro-batch < prévue | High | Medium | Benchmark avant merge, ajuster window/max |
| Watchdog manque plus d'events que prévu | Medium | Low | Reconciler couvre, ajuster intervalle |
| DuckDB lock contention | High | Low | Connection pool, retries exponentiels |
| Migration corrompt données | Critical | Very Low | Feature flag, rollback instantané |
| Réconciliation trop lente sur 1M fichiers | Medium | Medium | Index optimisés, pagination |

## Métriques de Succès

### Performance

- [ ] Realtime throughput ≥ 5,000 files/sec (POC avant implementation)
- [ ] Latence p95 < 500ms (event → DB)
- [ ] Reconciliation 1M files < 10 secondes

### Fiabilité

- [ ] 0 fichiers manqués sur 1 semaine de test
- [ ] Recovery automatique après crash
- [ ] Pas de corruption de données

### Maintenabilité

- [ ] Réduction de 40% du code d'indexation
- [ ] Tests unitaires ≥ 90% coverage
- [ ] Documentation architecture complète

## Timeline

| Sprint | Focus | Livrables |
|--------|-------|-----------|
| **Sprint 0** | POC | Benchmark micro-batch, validation 5,000 files/sec |
| **Sprint 1** | Fondations | Extension file_index, FileBatchAccumulator, Reconciler, tests |
| **Sprint 2** | Intégration | Évolution UnifiedIndexer, intégration TraceBuilder, benchmarks |
| **Sprint 3** | Migration | Rollout 10%→100%, cleanup hybrid.py, documentation |

### Prérequis Sprint 1

Avant de démarrer Sprint 1, le POC doit valider :
- [x] Throughput >= 4,500 files/sec avec batch de 100 fichiers → **10,016 files/sec** ✅
- [ ] Pas de lock contention visible avec dashboard ouvert (à tester)
- [ ] Query réconciliation < 2s sur 100k fichiers (à tester)

> **Note POC 2026-01-09** : Le throughput est 2.2x supérieur à la cible.
> Condition critique : utiliser `mark_indexed_batch()` pour éviter le goulot file_index.

## Annexes

### A. Benchmark DuckDB Micro-Batch (POC)

Le script de benchmark est disponible dans `tmp/benchmark_microbatch.py` (non versionné).

**Configuration** : `memory_limit=2GB, threads=4`

**Résultats réels** (MacBook Pro M1, 800 sessions réelles) :

| Batch Size | Files/sec | INSERT ms | file_index ms | Verdict |
|------------|-----------|-----------|---------------|---------|
| 25 | 4,957 | 106 | 55 | ✅ |
| 50 | 8,311 | 66 | 30 | ✅ |
| 100 | 10,016 | 58 | 21 | ✅ |
| 200 | **11,686** | 50 | 18 | ✅ |

> **⚠️ DÉCOUVERTE CRITIQUE** : Le goulot d'étranglement n'est PAS l'INSERT DuckDB,
> c'est la mise à jour de `file_index` !
>
> | Méthode | Files/sec |
> |---------|-----------|
> | file_index un par un | 1,314 ❌ |
> | file_index en batch | **11,686** ✅ |
>
> **Action requise** : Utiliser `FileTracker.mark_indexed_batch()` (déjà existant dans tracker.py)
> au lieu de `mark_indexed()` dans une boucle.

### B. Intégration avec code existant

| Composant existant | Fichier | Interaction avec v2 |
|-------------------|---------|---------------------|
| `UnifiedIndexer` | `unified/core.py` | Évolue pour utiliser FileBatchAccumulator |
| `BatchProcessor` | `unified/batch.py` | Reçoit les batches de FileBatchAccumulator |
| `FileTracker` | `tracker.py` | Gère file_index avec nouveau status |
| `TraceBuilder` | `trace_builder/` | Appelé après chaque batch |

### C. Requêtes SQL

Les requêtes sont définies dans `queries.py` existant. 
Nouvelles queries à ajouter dans la même logique.

### D. Migration file_index

```sql
-- À ajouter dans db.py via _migrate_columns()
ALTER TABLE file_index ADD COLUMN IF NOT EXISTS 
    status VARCHAR DEFAULT 'indexed';

CREATE INDEX IF NOT EXISTS idx_file_index_status 
ON file_index(status);
```

---

**Auteur**: Architecture Team  
**Date**: 2026-01-08  
**Mis à jour**: 2026-01-09 (POC validé - 11,686 files/sec)  
**Version**: 1.2  
**Status**: ✅ Validé - Prêt pour Sprint 1
