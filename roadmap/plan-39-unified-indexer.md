# Plan 39 - Unified Real-Time Indexer

## Objectif

Remplacer le systeme collector.py + loader.py par un indexer unifie temps reel avec:
- Detection instantanee des nouvelles sessions (< 1s)
- Change detection intelligent (mtime + size)
- Backfill progressif non-bloquant
- Meilleure gestion memoire

## Contexte

L'ancien systeme avait deux composants separes:
- `collector.py` : Collecte periodique des fichiers
- `loader.py` : Chargement et parsing en batch

Problemes:
- Latence de detection (polling lent)
- Pas de detection temps reel
- Re-parsing de fichiers non modifies
- Backfill bloquant au demarrage

## Solution

Nouveau module `analytics/indexer/` avec architecture unifiee:

```
indexer/
  __init__.py      # Exports publics
  unified.py       # UnifiedIndexer - orchestrateur principal
  watcher.py       # FileWatcher - surveillance temps reel
  tracker.py       # ChangeTracker - detection changements
  parsers.py       # Parsers JSON (sessions, messages, parts)
  trace_builder.py # Construction des traces
```

## Implementation

### Phase 1 : Architecture de base
- [x] Creer module `indexer/`
- [x] Implementer `UnifiedIndexer` avec interface publique
- [x] Implementer `FileWatcher` avec watchdog
- [x] Implementer `ChangeTracker` avec mtime + size

### Phase 2 : Parsers et persistence
- [x] Migrer parsers depuis loader.py
- [x] Implementer upsert intelligent (evite doublons)
- [x] Gerer les fichiers incomplets/corrompus

### Phase 3 : Integration
- [x] Modifier `app/core.py` pour utiliser le nouvel indexer
- [x] Deprecier `collector.py` et `loader.py`
- [x] Tests unitaires complets (25 tests)

### Phase 4 : Optimisations
- [x] Backfill progressif (100 fichiers/cycle)
- [x] Debouncing des evenements filesystem
- [x] Stats et monitoring integres

## Metriques cibles

| Metrique | Ancien | Nouveau | Gain |
|----------|--------|---------|------|
| Latence detection | 5-10s | < 1s | 10x |
| RAM au demarrage | Variable | < 300MB | Stable |
| Backfill 1000 fichiers | Bloquant | Progressif | UX |
| Re-parsing inutile | Oui | Non | CPU |

## Tests

- 25 tests unitaires dans `tests/test_indexer.py`
- Tests de performance manuels (RAM, latence)

## Risques

- Migration: Les anciens fichiers collector/loader restent pour compatibilite
- Watchdog: Dependance externe pour la surveillance filesystem

## Statut

**En cours** - Implementation terminee, tests OK, en attente de validation performance et merge.
