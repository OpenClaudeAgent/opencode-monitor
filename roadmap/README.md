# Roadmap - OpenCode SwiftBar Monitor

Ce dossier contient les plans d'implementation pour les futures fonctionnalites.

## Methodologie

- Chaque plan est un fichier `plan-XX-nom.md` immutable
- Le suivi se fait dans ce README
- L'implementation est faite par l'agent Executeur

## Suivi des taches

| # | Tache | Plan | Branche | Version | Statut |
|---|-------|------|---------|---------|--------|
| 0 | Debug et logging | [plan-00](./plan-00-debug-logging.md) | `feature/debug-logging` | v1.1.0 | Termine |
| 1 | Affichage tools refined | [plan-01](./plan-01-tools-display.md) | `feature/tools-display` | v2.1.0 | Termine |
| 2 | Notifications sonores | [plan-02](./plan-02-sound-notifications.md) | `feature/sounds` | v2.2.0 | Termine |
| 3 | Restructuration par session | [plan-03](./plan-03-session-structure.md) | `feature/session-structure` | - | En attente |
| 4 | Refonte backend Python | [plan-04](./plan-04-python-backend.md) | `feature/python-backend` | v2.0.0 | Termine |

## Priorite

Les plans 01, 02, 03 peuvent maintenant etre realises sur la base du backend Python (plan 04).

## Historique

| Date | Action |
|------|--------|
| 2025-12-28 | Plan-02 termine - Notifications sonores v2.2.0 |
| 2025-12-28 | Plan-01 termine - Affichage tools refined v2.1.0 |
| 2025-12-28 | Plan-04 termine - Backend Python async v2.0.0 (~800ms vs 13s) |
| 2025-12-28 | Ajout plan-04 refonte backend Python (nouvelle priorite maximale) |
| 2025-12-28 | Plan-00 termine - Outil debug/logging v1.1.0 |
| 2025-12-28 | Ajout plan-00 debug/logging (prioritaire) |
| 2025-12-28 | Creation roadmap initiale avec 3 plans |
