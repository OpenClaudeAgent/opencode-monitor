# Plan 33 - Infrastructure Tests d'Integration PyQt

## Contexte

Le projet dispose actuellement de tests unitaires solides (547+ tests, 99% coverage) qui testent les composants individuellement. Cependant, il n'existe pas d'infrastructure pour tester le dashboard PyQt de maniere integree : lancer l'application, interagir avec les menus/boutons, verifier que les elements s'affichent correctement avec les bonnes donnees.

L'application dashboard (`DashboardWindow`) :
- Utilise PyQt6 avec navigation par sidebar
- Contient 4 sections : Monitoring, Security, Analytics, Tracing
- Communique avec un serveur API Flask pour recuperer les donnees
- Effectue des refresh periodiques via `SyncChecker`

## Objectif

Mettre en place une infrastructure de tests d'integration robuste avec pytest-qt permettant de :
1. Tester le dashboard PyQt de bout en bout
2. Simuler les interactions utilisateur (clics, navigation)
3. Verifier le contenu affiche dans les widgets
4. Moquer le serveur API pour des tests reproductibles
5. Executer les tests en isolation et en parallele
6. Supporter l'execution en mode visible (debug) et headless (CI)

## Comportement attendu

### Installation et configuration

L'utilisateur peut lancer les tests d'integration avec :
```bash
# Mode headless (CI/CD)
make test-integration

# Mode visible (debug)
make test-integration-visible

# Un test specifique
pytest tests/integration/ -k "test_navigation" -v
```

### Execution des tests

Quand un test d'integration s'execute :
1. Une instance isolee du dashboard demarre avec l'API mockee
2. Le test simule des interactions (clics, navigation)
3. Le test verifie l'etat des widgets (texte, visibilite, donnees)
4. Le dashboard se ferme proprement apres le test
5. Aucun effet de bord entre tests (isolation complete)

### Mock de l'API

Le serveur API Flask est remplace par un mock qui :
- Retourne des donnees de test predefinies
- Permet de configurer des scenarios (erreurs, latence, etc.)
- Ne necessite pas de base de donnees reelle
- Est instantane (pas d'attente reseau)

### Parallelisation

Les tests peuvent s'executer en parallele :
- Chaque test a sa propre instance de QApplication
- Pas de ressources partagees entre tests
- Utilisation de pytest-xdist pour la parallelisation

### Mode visible vs headless

- **Mode visible** : La fenetre s'affiche, utile pour debugger
- **Mode headless** : Pas d'affichage, pour CI/CD (xvfb sur Linux, natif sur macOS)

## Specifications

*(Section destinee a l'Executeur)*

### Dependances a ajouter

```toml
[project.optional-dependencies]
dev = [
    # ... existant ...
    "pytest-qt>=4.4.0",
    "pytest-xdist>=3.5.0",  # Parallelisation
]
```

### Structure des fichiers

```
tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py           # Fixtures pytest-qt + mock API
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── api_responses.py  # Donnees de test pour mock API
│   ├── test_dashboard_launch.py
│   ├── test_navigation.py
│   └── test_sections.py
├── conftest.py               # Existant (tests unitaires)
└── ...
```

### Fixtures principales

#### `conftest.py` (integration)

```python
@pytest.fixture(scope="function")
def mock_api_client(monkeypatch):
    """Mock le client API avec des donnees de test."""
    # Remplace get_api_client() par un mock
    ...

@pytest.fixture
def dashboard(qtbot, mock_api_client):
    """Cree une instance du dashboard pour les tests."""
    window = DashboardWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    yield window
    window.close()
```

#### `api_responses.py`

```python
MOCK_STATS = {
    "sessions": 5,
    "agents": 3,
    "busy": 1,
    ...
}

MOCK_MONITORING_DATA = { ... }
MOCK_SECURITY_DATA = { ... }
MOCK_ANALYTICS_DATA = { ... }
MOCK_TRACING_DATA = { ... }
```

### Makefile

```makefile
# Tests d'integration (headless)
test-integration:
	pytest tests/integration/ -v --tb=short

# Tests d'integration (visible pour debug)
test-integration-visible:
	pytest tests/integration/ -v --tb=short -s

# Tests d'integration en parallele
test-integration-parallel:
	pytest tests/integration/ -v -n auto
```

### Tests initiaux a implementer

1. **test_dashboard_launch.py**
   - `test_dashboard_creates_window` : La fenetre se cree et s'affiche
   - `test_dashboard_has_sidebar` : La sidebar est presente
   - `test_dashboard_has_sections` : Les 4 sections existent

2. **test_navigation.py**
   - `test_click_monitoring_tab` : Navigation vers Monitoring
   - `test_click_security_tab` : Navigation vers Security
   - `test_click_analytics_tab` : Navigation vers Analytics
   - `test_click_tracing_tab` : Navigation vers Tracing

3. **test_sections.py**
   - `test_monitoring_shows_agents` : Les agents s'affichent
   - `test_security_shows_commands` : Les commandes s'affichent
   - `test_analytics_shows_metrics` : Les metriques s'affichent

## Checklist de validation

### Infrastructure
- [ ] pytest-qt ajoute aux dependances dev
- [ ] pytest-xdist ajoute aux dependances dev
- [ ] Dossier `tests/integration/` cree
- [ ] `conftest.py` avec fixtures de base
- [ ] Mock API client fonctionnel
- [ ] Donnees de test dans `fixtures/api_responses.py`

### Configuration
- [ ] Makefile avec commandes test-integration
- [ ] Tests fonctionnent en mode headless
- [ ] Tests fonctionnent en mode visible
- [ ] Parallelisation fonctionne avec -n auto

### Tests initiaux
- [ ] test_dashboard_launch.py passe
- [ ] test_navigation.py passe
- [ ] test_sections.py passe
- [ ] Aucune interference entre tests

### Qualite
- [ ] Documentation dans le code
- [ ] Pas de flaky tests (stabilite)
- [ ] Temps d'execution raisonnable (< 30s pour la suite)
- [ ] CI compatible (si applicable)

## Documentation

Ce plan pose les fondations pour les tests d'integration du dashboard. Une fois l'infrastructure en place, d'autres tests pourront etre ajoutes incrementalement pour couvrir :
- Interactions complexes (drag & drop, double-click)
- Scenarios d'erreur (API indisponible, timeout)
- Etats edge-case (listes vides, grandes quantites de donnees)
- Performance (temps de rendu, responsivite)

Le README du projet pourra etre mis a jour pour documenter comment lancer les tests d'integration.
