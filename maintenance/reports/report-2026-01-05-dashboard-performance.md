# Rapport Maintainer - Santé Projet opencode-monitor

**Date**: 2026-01-05  
**Branche**: feature/dashboard-performance  
**Version**: v2.23.0  
**Dernier tag**: v2.23.0  

---

## Score Global: C (Attention Requise)

Le projet présente des métriques de taille préoccupantes avec plusieurs fichiers critiques dépassant 500 lignes. La couverture de tests par module est insuffisante (36%), bien que le ratio LOC tests/source soit bon (81%).

---

## Métriques Principales

| Métrique | Valeur | Seuil | Status |
|----------|--------|-------|--------|
| Fichiers Python | 211 | - | ℹ️ |
| LOC Total | 50,202 | <50k | ⚠️ |
| LOC Source | 27,053 | <20k | ⚠️ |
| LOC Tests | 22,005 | - | ✅ |
| Ratio Tests/Source | 81% | >50% | ✅ |
| Fichiers >500L | **28** | 0 | ❌ |
| Fichiers >300L | 51 | <5 | ❌ |
| TODO/FIXME | 0* | <10 | ✅ |
| Fonctions >5 params | 8 | 0 | ⚠️ |
| Nesting depth >4 | 10 | 0 | ⚠️ |
| Tests unitaires | 530 | - | ✅ |
| Fichiers tests | 40 | - | ✅ |
| Couverture modules | 36% | >70% | ❌ |

\* Les "TODO" trouvés sont des constantes (TODO_CURRENT_MAX_LENGTH), pas des vrais TODOs.

---

## 🚨 Fichiers Critiques (>500 lignes)

### Source Code

| Fichier | Lignes | Criticité | Action |
|---------|--------|-----------|--------|
| `api/routes/tracing.py` | 1,103 | 🔴 CRITIQUE | Splitter en sous-modules |
| `analytics/indexer/unified.py` | 1,082 | 🔴 CRITIQUE | Splitter (déjà en cours?) |
| `dashboard/sections/tracing/section.py` | 895 | 🟠 HAUTE | Refactoriser |
| `analytics/collector.py` | 865 | 🟠 HAUTE | Refactoriser |
| `dashboard/window.py` | 725 | 🟠 HAUTE | Extraire composants |
| `analytics/indexer/trace_builder.py` | 697 | 🟠 HAUTE | Refactoriser |
| `dashboard/sections/.../panel.py` | 663 | 🟡 MOYENNE | Surveiller |
| `security/auditor.py` | 620 | 🟡 MOYENNE | Surveiller |
| `ui/menu.py` | 609 | 🟡 MOYENNE | Surveiller |
| `security/db/repository.py` | 588 | 🟡 MOYENNE | Surveiller |
| `analytics/loaders/traces.py` | 582 | 🟡 MOYENNE | Surveiller |
| `analytics/db.py` | 567 | 🟡 MOYENNE | Surveiller |
| `analytics/tracing/helpers.py` | 548 | 🟡 MOYENNE | Surveiller |
| `analytics/queries/trace_queries.py` | 541 | 🟡 MOYENNE | Surveiller |
| `analytics/tracing/session_queries.py` | 509 | 🟡 MOYENNE | Surveiller |

### Tests (informatif - moins critique)

| Fichier | Lignes | Note |
|---------|--------|------|
| `test_monitor.py` | 1,452 | Tests exhaustifs, acceptable |
| `test_loader.py` | 1,363 | Tests exhaustifs, acceptable |
| `test_analytics_queries.py` | 1,254 | Tests exhaustifs, acceptable |
| `test_app.py` | 1,129 | Tests exhaustifs, acceptable |
| `test_menu.py` | 1,105 | Tests exhaustifs, acceptable |

---

## 🔍 Focus: Nouveau Code (Hybrid Indexer)

### Structure du module `analytics/indexer/`

| Fichier | Lignes | Tests dédiés | Status |
|---------|--------|--------------|--------|
| `unified.py` | 1,082 | ✅ test_indexer.py | ⚠️ Trop gros |
| `trace_builder.py` | 697 | ✅ Partiel | ⚠️ Trop gros |
| `parsers.py` | 462 | ✅ | ⚠️ |
| `bulk_loader.py` | 437 | ❌ **MANQUANT** | 🔴 |
| `hybrid.py` | 410 | ❌ **MANQUANT** | 🔴 |
| `tracker.py` | 376 | ✅ | ⚠️ |
| `watcher.py` | 315 | ❌ **MANQUANT** | 🔴 |
| `sync_state.py` | ~200 | ❌ **MANQUANT** | ⚠️ |

### ⚠️ Tests Manquants pour le Nouveau Code

Le **HybridIndexer** et le **BulkLoader** n'ont **PAS de tests dédiés** !

C'est le composant central de l'amélioration de performance (250 → 2000 files/s), mais il n'est pas testé unitairement.

**Risques**:
- Régressions non détectées lors du merge
- Comportement edge-cases non vérifié
- Concurrence (threading) non testée

---

## 🔍 Focus: API Routes

| Fichier | Lignes | Status |
|---------|--------|--------|
| `tracing.py` | 1,103 | 🔴 CRITIQUE - À splitter |
| `sessions.py` | 164 | ✅ OK |
| `health.py` | 104 | ✅ OK |
| `delegations.py` | 61 | ✅ OK |
| `stats.py` | 43 | ✅ OK |
| `_context.py` | 69 | ✅ OK |

`tracing.py` concentre trop de logique. Recommandation: extraire en sous-modules.

---

## 📊 Complexité du Code

### Fonctions avec trop de paramètres (>5)

| Fichier | Fonction | Params |
|---------|----------|--------|
| `security/auditor.py:289` | `_apply_edr_and_build_result()` | **11** 🔴 |
| `dashboard/sections/monitoring.py:167` | `update_data()` | 9 |
| `dashboard/.../panel.py:585` | `show_session()` | 8 |
| `dashboard/.../panel.py:556` | `show_trace()` | 8 |
| `dashboard/sections/analytics.py:135` | `update_data()` | 7 |
| `dashboard/.../panel.py:402` | `show_exchange()` | 7 |
| `api/routes/tracing.py:655` | `_build_user_exchange()` | 6 |
| `analytics/indexer/trace_builder.py:350` | `create_root_trace()` | 6 |

### Fichiers avec Nesting Profond (>4 niveaux)

| Fichier | Profondeur |
|---------|------------|
| `dashboard/sections/tracing/section.py` | **10** 🔴 |
| `security/auditor.py` | 8 |
| `analytics/loaders/parts.py` | 7 |
| `analytics/indexer/hybrid.py` | 7 |
| `dashboard/.../handlers/data_loader.py` | 7 |
| `dashboard/window.py` | 6 |
| `analytics/collector.py` | 6 |
| `analytics/queries/trace_queries.py` | 6 |
| `analytics/indexer/unified.py` | 6 |
| `api/routes/tracing.py` | 6 |

---

## 📦 Dépendances

### Dependencies Principales (pyproject.toml)

```
rumps>=0.4.0        # Menu bar
aiohttp>=3.9.0      # HTTP async
duckdb>=1.0.0       # Database
plotly>=5.0.0       # Charts
PyQt6>=6.6.0        # Dashboard
watchdog>=4.0.0     # File watching
flask>=3.1.2        # API server
```

### Status Dépendances

| Check | Status |
|-------|--------|
| Outdated packages | ⚠️ Non vérifié (pip-audit non installé) |
| Vulnerabilités | ⚠️ Non vérifié (pip-audit non installé) |

**Recommandation**: Installer `pip-audit` et exécuter un scan.

---

## 📁 Structure du Projet

```
src/opencode_monitor/
├── analytics/         # Indexation, queries, reporting
│   ├── indexer/       # 🆕 Hybrid Indexer (focus)
│   ├── loaders/       # Data loaders
│   ├── queries/       # SQL queries
│   └── tracing/       # Trace analytics
├── api/               # REST API
│   └── routes/        # ⚠️ tracing.py trop gros
├── dashboard/         # PyQt6 dashboard
│   └── sections/      # UI sections
├── security/          # Audit & security
├── core/              # Core models
├── ui/                # Menu bar UI
└── utils/             # Utilities
```

- **115 fichiers Python** dans src/
- **44 répertoires**
- Profondeur max: 8 niveaux (acceptable)

---

## ✅ Recommandations

### 🔴 CRITIQUE (Blocker pour merge)

1. **Ajouter des tests pour HybridIndexer et BulkLoader**
   - Le nouveau code de performance n'est pas testé
   - Risque élevé de régression après merge
   - Fichiers: `hybrid.py`, `bulk_loader.py`, `watcher.py`, `sync_state.py`

### 🟠 HAUTE (À planifier rapidement)

2. **Splitter `api/routes/tracing.py`** (1,103 lignes)
   - Extraire en sous-modules: `tracing/sessions.py`, `tracing/messages.py`, etc.

3. **Splitter `analytics/indexer/unified.py`** (1,082 lignes)
   - Note: Il semble qu'un refactoring est en cours (dossier `unified/` existe)
   - Finaliser la migration

4. **Refactoriser `_apply_edr_and_build_result()`** (11 paramètres)
   - Utiliser un dataclass/TypedDict pour regrouper les params

### 🟡 MOYENNE (Backlog)

5. **Réduire le nesting dans `section.py`** (depth=10)
   - Extraire des méthodes helper

6. **Améliorer la couverture de tests** (36% → 70%)
   - Prioriser: analytics, security, api

---

## 📈 Historique (Activité Récente)

| Métrique | Valeur |
|----------|--------|
| Commits totaux | 245 |
| Commits (7 derniers jours) | 191 |
| Fichiers modifiés depuis main | 242 |
| Lignes ajoutées | +49,171 |
| Lignes supprimées | -7,500 |

L'activité est **très intense** sur cette branche.

---

## 🎯 Conclusion

| Critère | Évaluation |
|---------|------------|
| **Santé globale** | ⚠️ **ATTENTION** |
| **Prêt à merger** | ❌ **NON** |

### Conditions pour le merge:

1. ✅ ~~Performance améliorée~~ (250 → 2000 files/s)
2. ❌ **Tests HybridIndexer/BulkLoader manquants**
3. ⚠️ Fichiers critiques > 1000 lignes (acceptable temporairement)
4. ⚠️ Couverture tests faible (36%)

### Verdict Final

> **Ne pas merger avant d'avoir ajouté des tests pour le nouveau code HybridIndexer/BulkLoader.**
> 
> Le gain de performance est significatif, mais le risque de régression sans tests est trop élevé pour une fonctionnalité aussi critique (indexation de fichiers).

---

*Rapport généré automatiquement par Agent Maintainer*
*Projet: opencode-monitor | Branche: feature/dashboard-performance*
