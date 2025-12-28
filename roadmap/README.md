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
| 3 | Restructuration par session | [plan-03](./plan-03-session-structure.md) | `feature/session-structure` | v2.3.0 | Termine |
| 4 | Refonte backend Python | [plan-04](./plan-04-python-backend.md) | `feature/python-backend` | v2.0.0 | Termine |
| 5 | Migration vers rumps | [plan-05](./plan-05-rumps-migration.md) | `feature/rumps-migration` | v2.4.0 | Termine |
| 6 | Tooltips elements tronques | [plan-06](./plan-06-tooltips-truncated.md) | `feature/tooltips` | - | En attente |
| 7 | Detection permissions/stuck | [plan-07](./plan-07-permission-detection.md) | `feature/permissions` | - | En attente |
| 8 | Panel de configuration | [plan-08](./plan-08-settings-panel.md) | `feature/settings` | - | En attente |
| 9 | Refinement des icones | [plan-09](./plan-09-icons-refinement.md) | `feature/icons` | - | En attente |

## Priorite

Les plans 06, 07, 08 sont des ameliorations pour l'application rumps native (v2.4.0+).

Ordre suggere :
1. **Plan 09** (Icones) - Amelioration visuelle rapide, pas de dependances
2. **Plan 08** (Settings) - Permet de configurer les comportements, prerequis pour plan 07
3. **Plan 07** (Permissions) - Detection des agents stuck, depend de plan 08 pour la configuration
4. **Plan 06** (Tooltips) - Amelioration UX independante

## Historique

| Date | Action |
|------|--------|
| 2025-12-28 | Ajout plan-09 (refinement des icones) |
| 2025-12-28 | Ajout plans 06, 07, 08 (tooltips, permissions, settings) |
| 2025-12-28 | Plan-05 termine - Migration vers rumps v2.4.0 |
| 2025-12-28 | Plan-03 termine - Todos affiches sous chaque agent v2.3.0 |
| 2025-12-28 | Plan-02 termine - Notifications sonores v2.2.0 |
| 2025-12-28 | Plan-01 termine - Affichage tools refined v2.1.0 |
| 2025-12-28 | Plan-04 termine - Backend Python async v2.0.0 (~800ms vs 13s) |
| 2025-12-28 | Ajout plan-04 refonte backend Python (nouvelle priorite maximale) |
| 2025-12-28 | Plan-00 termine - Outil debug/logging v1.1.0 |
| 2025-12-28 | Ajout plan-00 debug/logging (prioritaire) |
| 2025-12-28 | Creation roadmap initiale avec 3 plans |
