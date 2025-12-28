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
| 8 | Panel de configuration | [plan-08](./plan-08-settings-panel.md) | `feature/settings` | v2.6.0 | Termine |
| 9 | Refinement des icones | [plan-09](./plan-09-icons-refinement.md) | `feature/icons` | v2.5.0 | Termine |
| 10 | Notifications systeme macOS | [plan-10](./plan-10-system-notifications.md) | `feature/notifications` | - | En attente |
| 11 | Module securite / Analyse commandes | [plan-11](./plan-11-security-analysis.md) | `feature/security` | - | En attente |

## Priorite

Les plans 06, 07, 08, 10, 11 sont des ameliorations pour l'application rumps native (v2.4.0+).

Ordre suggere :
1. ~~**Plan 09** (Icones)~~ - Termine v2.5.0
2. ~~**Plan 08** (Settings)~~ - Termine v2.6.0
3. **Plan 07** (Permissions) - Detection des agents stuck, depend de plan 08 pour la configuration
4. **Plan 10** (Notifications systeme) - Notifications macOS natives, depend de plans 07 et 08
5. **Plan 06** (Tooltips) - Amelioration UX independante
6. **Plan 11** (Securite) - Analyse des commandes, alertes. Beneficie de plan-10 pour les notifications

**Note** : Le plan 10 peut etre implemente partiellement (notifications de completion) avant les plans 07/08, puis complete une fois ceux-ci termines.

**Note plan-11** : Le module de securite peut etre implemente independamment (sous-taches 11.1-11.3), mais les notifications (11.4) beneficieront du plan-10 s'il est termine avant.

## Historique

| Date | Action |
|------|--------|
| 2025-12-28 | Ajout plan-11 (module securite / analyse commandes) |
| 2025-12-28 | Plan-08 termine - Panel de configuration v2.6.0 |
| 2025-12-28 | Ajout plan-10 (notifications systeme macOS) |
| 2025-12-28 | Plan-09 termine - Icones sub-agents minimalistes v2.5.0 |
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
