# Plan 38 - Outils d'analyse Python CLI

## Contexte

Les agents IA qui travaillent sur ce projet ont besoin d'outils d'analyse de code Python performants et standalone. Le serveur MCP lsmcp-python avec pyright souffre de problemes de timeout (5s hardcode, non configurable) rendant son utilisation impraticable sur des projets de taille moyenne.

Une solution CLI native en Python, integree au projet, permettrait aux agents d'avoir acces a des fonctionnalites LSP-like sans dependre d'un serveur externe.

## Objectif

Creer un outil CLI Python integre au projet (`tools/pycode`) qui expose les fonctionnalites d'analyse de code suivantes :
- Navigation (goto definition, find references)
- Inspection (hover/documentation, symbols listing)
- Diagnostics (linting, type checking, metriques)
- Qualite (code mort, complexite, securite)

## Comportement attendu

### Installation des dependances

L'outil utilise des packages Python standalone ajoutes aux dependances de developpement :
- `jedi` : Navigation et refactoring
- `ruff` : Linting ultra-rapide (deja disponible)
- `radon` : Metriques de complexite
- `vulture` : Detection de code mort

### Interface CLI

```bash
# Navigation (via jedi)
uv run python -m tools.pycode goto <file>:<line>:<col>
uv run python -m tools.pycode refs <file>:<line>:<col>
uv run python -m tools.pycode hover <file>:<line>:<col>
uv run python -m tools.pycode symbols <file>

# Diagnostics (via ruff)
uv run python -m tools.pycode lint <file|directory>
uv run python -m tools.pycode check <file|directory>

# Metriques (via radon)
uv run python -m tools.pycode complexity <file|directory>
uv run python -m tools.pycode maintainability <file|directory>

# Code mort (via vulture)
uv run python -m tools.pycode dead-code <file|directory>

# Rapport combine
uv run python -m tools.pycode report <file|directory>
```

### Format de sortie

Toutes les commandes supportent :
- `--json` : Sortie JSON pour parsing par les agents
- `--verbose` : Details supplementaires
- Par defaut : Sortie texte lisible

## Checklist de validation

### Dependances
- [x] Package `jedi` ajoute aux dependances dev
- [x] Package `radon` ajoute aux dependances dev
- [x] Package `vulture` ajoute aux dependances dev

### Module tools/pycode
- [x] Module `tools/pycode/__init__.py` cree
- [x] Module `tools/pycode/__main__.py` avec CLI argparse
- [x] Commande `goto` implementee et testee
- [x] Commande `refs` implementee et testee
- [x] Commande `hover` implementee et testee
- [x] Commande `symbols` implementee et testee
- [x] Commande `lint` (wrapper ruff) implementee
- [x] Commande `complexity` implementee
- [x] Commande `dead-code` implementee
- [x] Commande `report` combinant les metriques
- [x] Sortie JSON fonctionnelle pour toutes les commandes

### Tests et documentation
- [x] Tests unitaires pour chaque commande (24 tests)
- [x] Documentation usage dans DEVELOPMENT.md
- [x] Fichier `.opencode/AGENTS.md` cree avec instructions

## Implementation

### Fichiers crees

| Fichier | Description |
|---------|-------------|
| `tools/pycode/__init__.py` | Exports du module |
| `tools/pycode/__main__.py` | CLI entry point (argparse) |
| `tools/pycode/navigation.py` | Navigation jedi (goto, refs, hover, symbols) |
| `tools/pycode/diagnostics.py` | Diagnostics ruff (lint, check) |
| `tools/pycode/metrics.py` | Metriques radon (complexity, maintainability) |
| `tools/pycode/deadcode.py` | Detection vulture (dead-code) |
| `tools/pycode/report.py` | Rapport combine |
| `tests/test_pycode.py` | 24 tests unitaires |
| `.opencode/AGENTS.md` | Instructions pour agents OpenCode |

### Statut

**Termine** - v2.23.0
