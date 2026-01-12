# Analyse exhaustive: Suppression du menu HTML Analytics

**Objectif**: Supprimer complètement le mécanisme de génération de rapports HTML via le menu bar, ainsi que tous les artefacts associés.

**Date**: 2026-01-12  
**Branch**: `cleanup/remove-html-menu`  
**Worktree**: `/Users/sofiane/Projects/opencode-monitor/worktrees/cleanup-remove-html-menu`

---

## 📋 Vue d'ensemble

Le système de génération HTML permet d'exporter des rapports analytics au format HTML avec des graphiques Plotly via un menu dans la barre de menu macOS.

### Composants principaux

1. **Module report complet** (`analytics/report/`)
2. **Entrées de menu** (menu bar items)
3. **Handlers de callback** (event handlers)
4. **Imports et exports** (module interfaces)
5. **Dépendances externes** (Plotly)

---

## 🗑️ Fichiers à SUPPRIMER

### 1. Module `analytics/report/` (5 fichiers, 1336 lignes)

**Chemin**: `src/opencode_monitor/analytics/report/`

| Fichier | Lignes | Description |
|---------|--------|-------------|
| `__init__.py` | 21 | Exports du module (AnalyticsReport, generate_html_report, generate_report, format_tokens, get_full_css) |
| `generator.py` | 169 | Orchestration de la génération HTML complète |
| `sections.py` | 389 | 16 générateurs de sections HTML |
| `charts.py` | 289 | 5 générateurs de graphiques Plotly |
| `styles.py` | 468 | CSS design system (dark theme avec blue tint) |
| **TOTAL** | **1336** | |

#### Fonctions principales dans `generator.py`
- `generate_html_report(stats, period_label)` → Génère le document HTML complet
- `AnalyticsReport` dataclass avec méthodes `to_html()` et `to_text()`
- `generate_report(days, db, refresh_data)` → Point d'entrée public

#### Fonctions dans `sections.py` (16 générateurs)
```python
generate_header()
generate_token_details()
generate_session_metrics()
generate_delegation_analytics()
generate_agent_roles()
generate_delegation_flow()
generate_hourly_heatmap()
generate_agent_chains()
generate_top_sessions()
generate_skills()
generate_skills_by_agent()
generate_agent_delegation_stats()
generate_delegation_sessions()
generate_models()
generate_directories()
generate_anomalies()
```

#### Fonctions dans `charts.py` (5 générateurs Plotly)
```python
create_token_pie_chart()      # Donut chart distribution
create_agent_bar_chart()      # Horizontal bar chart
create_hourly_bar_chart()     # Bar chart by hour
create_tools_stacked_chart()  # Stacked bar chart
create_daily_activity_chart() # Time series line
```

---

### 2. Méthodes dans `app/handlers.py`

**Fichier**: `src/opencode_monitor/app/handlers.py`

| Méthode | Lignes | Action |
|---------|--------|--------|
| `_show_analytics(self, days: int)` | 102-142 | Génère et ouvre le rapport HTML dans le navigateur |
| `_refresh_analytics(self, _)` | 144-161 | Rafraîchit les données analytics en arrière-plan |
| `_start_analytics_refresh(self)` | 163-182 | Auto-refresh si données > 24h |

**Détails `_show_analytics`**:
```python
def _show_analytics(self, days: int):
    """Show analytics report for the specified period (runs in background)."""
    def run_in_background():
        db = AnalyticsDB(read_only=False)
        report = generate_report(days, db=db, refresh_data=False)
        report_html = report.to_html()  # ← Génération HTML
        
        report_path = os.path.join(
            tempfile.gettempdir(), 
            f"opencode_analytics_{days}d.html"
        )
        with open(report_path, "w") as f:
            f.write(report_html)
        
        subprocess.run(["open", report_path])  # ← Ouvre dans navigateur
```

---

### 3. Méthodes dans `app/menu.py`

**Fichier**: `src/opencode_monitor/app/menu.py`

| Élément | Lignes | Action |
|---------|--------|--------|
| Type hints pour handlers | 48-49 | Déclarations des méthodes _show_analytics et _refresh_analytics |
| Appel `build_analytics_menu()` | 173-177 | Intégration du menu analytics dans le menu principal |

**Code à supprimer (lignes 173-177)**:
```python
# Analytics menu
analytics_menu = self._menu_builder.build_analytics_menu(
    analytics_callback=self._show_analytics,
    refresh_callback=self._refresh_analytics,
)
self.menu.add(analytics_menu)  # type: ignore[attr-defined]
```

---

### 4. Méthode dans `ui/menu.py`

**Fichier**: `src/opencode_monitor/ui/menu.py`

| Méthode | Lignes | Action |
|---------|--------|--------|
| `build_analytics_menu()` | 601-630 | Construit le sous-menu "📈 OpenCode Analytics" |

**Structure du menu créé**:
```
📈 OpenCode Analytics
  ├─ 📅 Last 24 hours  → _show_analytics(1)
  ├─ 📅 Last 7 days    → _show_analytics(7)
  ├─ 📅 Last 30 days   → _show_analytics(30)
  ├─ ─────────────
  └─ 🔃 Refresh data   → _refresh_analytics()
```

---

## ✏️ Fichiers à MODIFIER

### 1. `src/opencode_monitor/analytics/__init__.py`

**Suppression des imports** (ligne 20):
```python
# AVANT
from .report import AnalyticsReport, generate_report

# APRÈS
# (ligne supprimée)
```

**Suppression des exports** (lignes 38-39):
```python
# AVANT
__all__ = [
    # ...
    "AnalyticsReport",
    "generate_report",
]

# APRÈS
__all__ = [
    # ... (sans AnalyticsReport et generate_report)
]
```

---

### 2. `src/opencode_monitor/app/__init__.py`

**Suppression partielle de l'import** (ligne 30):
```python
# AVANT
from ..analytics import AnalyticsDB, load_opencode_data, generate_report

# APRÈS
from ..analytics import AnalyticsDB, load_opencode_data
```

**Suppression de l'export** (ligne 69):
```python
# AVANT
__all__ = [
    # ...
    "generate_report",
]

# APRÈS
__all__ = [
    # ... (sans generate_report)
]
```

---

### 3. `src/opencode_monitor/app/handlers.py`

**Suppression partielle de l'import** (ligne 12):
```python
# AVANT
from ..analytics import AnalyticsDB, load_opencode_data, generate_report

# APRÈS
from ..analytics import AnalyticsDB, load_opencode_data
```

**Suppression de l'import subprocess** (ligne 3):
```python
# AVANT
import subprocess  # nosec B404 - required for opening reports in OS

# APRÈS
# (vérifier si subprocess est utilisé ailleurs dans le fichier)
# S'il n'est utilisé QUE pour _show_analytics, supprimer complètement
# Sinon, garder l'import et mettre à jour le commentaire
```

**Note**: `subprocess` est également utilisé pour:
- `_show_security_report()` (ligne 74)
- `_export_all_commands()` (ligne 99)

→ **Garder l'import subprocess** (utilisé ailleurs)

---

### 4. `pyproject.toml`

**Vérification de la dépendance Plotly** (ligne 14):
```toml
dependencies = [
    # ...
    "plotly>=5.0.0",  # ← À vérifier
]
```

**Action**: 
1. Rechercher toute utilisation de `plotly` dans le codebase
2. Si UNIQUEMENT utilisé dans `analytics/report/`, SUPPRIMER la dépendance
3. Si utilisé ailleurs, GARDER

**Commande de vérification**:
```bash
grep -r "import plotly\|from plotly" src/ --include="*.py" | grep -v "analytics/report"
```

---

## 🧪 Tests à METTRE À JOUR

### 1. `tests/unit/app/test_app.py`

**Ligne 177** - Mock de `build_analytics_menu`:
```python
# AVANT
mock_builder_instance.build_analytics_menu.return_value = MockMenuItem("Analytics")

# APRÈS
# (ligne à supprimer OU adapter selon le refactoring)
```

**Vérification**: Ce test crée un mock du menu builder. Si on supprime `build_analytics_menu()`, le test doit être adapté.

**Action recommandée**: 
- Vérifier le contexte complet du test
- Si le test vérifie spécifiquement la construction du menu analytics, **supprimer le test**
- Si le test vérifie la construction générale du menu, **adapter** en retirant la partie analytics

---

## ✅ Fichiers à GARDER (NE PAS TOUCHER)

### ⚠️ IMPORTANT: Distinction Security vs Analytics

**À NE PAS CONFONDRE avec les rapports TEXTE de sécurité**:

| Module | Fonction | Format | Action |
|--------|----------|--------|--------|
| `security/auditor/core.py` | `generate_report()` | **TEXTE** | **GARDER** |
| `security/reporter.py` | `generate_full_export()` | **TEXTE** | **GARDER** |
| `analytics/report/` | `generate_html_report()` | **HTML** | **SUPPRIMER** |

**Raison**: Les modules de sécurité génèrent des rapports TEXTE (`.txt`), pas HTML.

### Fichiers security à garder intacts

1. `src/opencode_monitor/security/auditor/core.py`
   - Méthode `generate_report()` (ligne 398) → génère du texte
   
2. `src/opencode_monitor/security/reporter.py`
   - Toutes les méthodes `_export_*()` → génèrent du texte
   
3. `src/opencode_monitor/app/handlers.py`
   - Méthode `_show_security_report()` (lignes 60-75) → ouvre un fichier `.txt`
   - Méthode `_export_all_commands()` (lignes 77-100) → exporte en `.txt`

4. Menu items sécurité dans `ui/menu.py`
   - `build_security_menu()` → **GARDER**
   - Entrées "📋 View Full Report" et "📤 Export All Data" → **GARDER**

---

## 📝 Plan d'action détaillé

### Phase 1: Suppression du module report

```bash
rm -rf src/opencode_monitor/analytics/report/
```

**Impact**: 1336 lignes supprimées

---

### Phase 2: Suppression des handlers

**Fichier**: `src/opencode_monitor/app/handlers.py`

1. Supprimer méthode `_show_analytics()` (lignes 102-142)
2. Supprimer méthode `_refresh_analytics()` (lignes 144-161)
3. Supprimer méthode `_start_analytics_refresh()` (lignes 163-182)
4. Mettre à jour l'import ligne 12:
   ```python
   from ..analytics import AnalyticsDB, load_opencode_data
   ```

**Impact**: ~81 lignes supprimées

---

### Phase 3: Suppression de l'intégration menu

**Fichier**: `src/opencode_monitor/app/menu.py`

1. Supprimer les type hints (lignes 48-49):
   ```python
   def _show_analytics(self, days: int): ...
   def _refresh_analytics(self, _): ...
   ```

2. Supprimer l'appel `build_analytics_menu()` (lignes 172-177):
   ```python
   # Analytics menu
   analytics_menu = self._menu_builder.build_analytics_menu(
       analytics_callback=self._show_analytics,
       refresh_callback=self._refresh_analytics,
   )
   self.menu.add(analytics_menu)  # type: ignore[attr-defined]
   ```

**Impact**: ~7 lignes supprimées

---

**Fichier**: `src/opencode_monitor/ui/menu.py`

Supprimer la méthode `build_analytics_menu()` (lignes 601-630)

**Impact**: ~30 lignes supprimées

---

### Phase 4: Nettoyage des imports/exports

**Fichier**: `src/opencode_monitor/analytics/__init__.py`

```python
# Supprimer ligne 20
from .report import AnalyticsReport, generate_report

# Supprimer lignes 38-39 dans __all__
"AnalyticsReport",
"generate_report",
```

---

**Fichier**: `src/opencode_monitor/app/__init__.py`

```python
# Modifier ligne 30
from ..analytics import AnalyticsDB, load_opencode_data  # (retirer generate_report)

# Supprimer ligne 69 dans __all__
"generate_report",
```

---

### Phase 5: Vérification de Plotly

```bash
cd /Users/sofiane/Projects/opencode-monitor/worktrees/cleanup-remove-html-menu
grep -r "import plotly\|from plotly" src/ --include="*.py" | grep -v "analytics/report"
```

**Si aucun résultat** → Supprimer `plotly>=5.0.0` de `pyproject.toml`  
**Si des résultats** → Garder la dépendance et documenter l'usage

---

### Phase 6: Mise à jour des tests

**Fichier**: `tests/unit/app/test_app.py`

1. Identifier le test qui mock `build_analytics_menu` (ligne 177)
2. Analyser le contexte complet
3. Soit supprimer le test, soit l'adapter

**Commande pour identifier le test**:
```bash
cd worktrees/cleanup-remove-html-menu
grep -B 20 -A 10 "build_analytics_menu" tests/unit/app/test_app.py
```

---

### Phase 7: Vérification et tests

```bash
cd /Users/sofiane/Projects/opencode-monitor/worktrees/cleanup-remove-html-menu

# 1. Vérifier qu'il n'y a plus de références
grep -r "generate_html_report\|AnalyticsReport\|generate_report" src/ --include="*.py"
grep -r "build_analytics_menu\|_show_analytics\|_refresh_analytics" src/ --include="*.py"
grep -r "from.*\.report import" src/ --include="*.py"

# 2. Lancer les tests
make test

# 3. Vérifier le linting
make lint

# 4. Vérifier le type checking
make typecheck
```

---

## 📊 Statistiques

### Fichiers supprimés

| Type | Nombre | Lignes totales |
|------|--------|----------------|
| Modules Python (report/) | 5 | 1336 |
| **TOTAL SUPPRESSIONS** | **5** | **~1336** |

### Fichiers modifiés

| Fichier | Lignes supprimées | Lignes modifiées |
|---------|-------------------|------------------|
| `app/handlers.py` | ~81 | ~1 |
| `app/menu.py` | ~7 | 0 |
| `ui/menu.py` | ~30 | 0 |
| `analytics/__init__.py` | ~3 | 0 |
| `app/__init__.py` | ~2 | 0 |
| `pyproject.toml` | 0-1 | 0 |
| **TOTAL MODIFICATIONS** | **~124** | **~1** |

### Impact global

- **~1460 lignes de code supprimées**
- **6 fichiers modifiés**
- **5 fichiers supprimés**
- **1 dépendance potentiellement supprimée** (plotly)

---

## ✅ Vérification finale

### Checklist de validation

- [ ] Module `analytics/report/` supprimé
- [ ] Méthodes `_show_analytics`, `_refresh_analytics`, `_start_analytics_refresh` supprimées
- [ ] Type hints des méthodes supprimées dans `menu.py`
- [ ] Appel `build_analytics_menu()` supprimé dans `app/menu.py`
- [ ] Méthode `build_analytics_menu()` supprimée dans `ui/menu.py`
- [ ] Imports nettoyés dans `analytics/__init__.py`
- [ ] Imports nettoyés dans `app/__init__.py`
- [ ] Imports nettoyés dans `app/handlers.py`
- [ ] Dépendance plotly vérifiée et supprimée si inutilisée
- [ ] Tests mis à jour ou supprimés
- [ ] Aucune référence résiduelle à `generate_html_report`, `AnalyticsReport`, `generate_report`
- [ ] Aucune référence résiduelle à `build_analytics_menu`, `_show_analytics`, `_refresh_analytics`
- [ ] Tests passent: `make test`
- [ ] Linting passe: `make lint`
- [ ] Type checking passe: `make typecheck`
- [ ] Application démarre sans erreur: `make run`
- [ ] Menu bar s'affiche correctement (sans entrée Analytics)

---

## 🎯 Résultat attendu

Après cette opération, l'application:

1. **N'aura plus** de menu "📈 OpenCode Analytics" dans la barre de menu
2. **N'aura plus** la capacité de générer des rapports HTML
3. **Conservera** toutes les fonctionnalités de sécurité audit (rapports texte)
4. **Conservera** le dashboard PyQt6 (fonctionnalité séparée)
5. **Conservera** toute la collecte de données analytics (database, indexer, queries)
6. **Fonctionnera** normalement sans aucun artefact lié au menu HTML

---

## 🚀 Prochaines étapes

1. Exécuter le plan d'action phase par phase
2. Tester après chaque phase
3. Commit avec message descriptif
4. Créer une PR pour review
5. Merger après validation

---

## 📌 Notes importantes

### Dashboard PyQt6 vs Menu HTML

**IMPORTANT**: Le dashboard PyQt6 (`src/opencode_monitor/dashboard/`) est une fonctionnalité SÉPARÉE qui:
- Affiche les analytics dans une fenêtre native PyQt6
- N'utilise PAS le module `analytics/report/`
- N'utilise PAS Plotly
- Doit être **CONSERVÉ INTACT**

**Distinction**:
- **Menu HTML** → Génère fichiers HTML avec Plotly → **À SUPPRIMER**
- **Dashboard PyQt6** → Fenêtre native avec widgets Qt → **À GARDER**

### Collecte de données analytics

La suppression du menu HTML **ne supprime PAS**:
- La base de données DuckDB (`analytics.duckdb`)
- L'indexer temps réel (`analytics/indexer/`)
- Les queries SQL (`analytics/queries/`)
- Les loaders (`analytics/loader.py`)
- Les models (`analytics/models.py`)

**Raison**: Ces composants sont utilisés par le dashboard PyQt6.

---

**Fin de l'analyse**
