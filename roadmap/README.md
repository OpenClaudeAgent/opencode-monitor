# Roadmap - OpenCode Monitor

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
| 6 | Tooltips elements tronques | [plan-06](./plan-06-tooltips-truncated.md) | `feature/tooltips` | v2.7.0 | Termine |
| 7 | Detection permissions/stuck | [plan-07](./plan-07-permission-detection.md) | `feature/permissions` | - | Non realisable |
| 8 | Panel de configuration | [plan-08](./plan-08-settings-panel.md) | `feature/settings` | v2.6.0 | Termine |
| 9 | Refinement des icones | [plan-09](./plan-09-icons-refinement.md) | `feature/icons` | v2.5.0 | Termine |
| 10 | Notifications systeme macOS | [plan-10](./plan-10-system-notifications.md) | `feature/notifications` | - | Abandonne |
| 11 | Module securite / Analyse commandes | [plan-11](./plan-11-security-analysis.md) | `feature/security` | v2.8.0 | Termine |
| 12 | Debug systeme preferences | [plan-12](./plan-12-preferences-debug.md) | `feature/preferences-debug` | v2.6.1 | Termine |
| 13 | Refactoring code source | [plan-13](./plan-13-refactoring.md) | `feature/refactoring` | v2.9.0 | Termine |
| 14 | Permission Detection (Heuristique) | [plan-14](./plan-14-permission-detection.md) | `feature/permission-heuristic` | v2.10.0 | Termine |
| 15 | Detection MCP Notify ask_user | [plan-15](./plan-15-ask-user-detection.md) | `feature/ask-user-detection` | - | En attente |
| 16 | Analytics et statistiques | [plan-16](./plan-16-analytics.md) | `feature/analytics` | - | En attente |
| 17 | Dashboard PyQt | [plan-17](./plan-17-pyqt-dashboard.md) | `feature/pyqt-dashboard` | - | En attente |

## Priorite

Les plans 06, 08, 10, 11, 12 sont des ameliorations pour l'application rumps native (v2.4.0+).

Ordre suggere :
1. ~~**Plan 09** (Icones)~~ - Termine v2.5.0
2. ~~**Plan 08** (Settings)~~ - Termine v2.6.0
3. ~~**Plan 07** (Permissions)~~ - **Non realisable** - Les API OpenCode ne permettent pas de detecter l'etat "waiting for permission" de maniere fiable
4. ~~**Plan 12** (Debug preferences)~~ - Termine v2.6.1
5. ~~**Plan 10** (Notifications systeme)~~ - **Abandonne** - Detection des permissions non fiable via API OpenCode
6. ~~**Plan 06** (Tooltips)~~ - Termine v2.7.0
7. **Plan 11** (Securite) - A revoir sans dependance aux notifications

**Note Plan-07** : L'endpoint `/permission` d'OpenCode retourne toujours un tableau vide et les SSE events `permission.updated` ne sont pas emis. La seule detection possible (scan des tools avec `status: "pending"`) est trop peu fiable pour une UX correcte.

**Note Plan-10** : Abandonne apres investigation approfondie. L'API OpenCode ne fournit pas d'evenements SSE pour les demandes de permission. Le status "pending" des tools ne correspond pas aux demandes de permission mais a l'etat de preparation des outils. Focus sur le monitoring pur.

## Historique

| Date | Action |
|------|--------|
| 2025-12-29 | Ajout plan-17 (dashboard PyQt) - Interface graphique pour afficher monitoring, security, analytics |
| 2025-12-29 | Ajout plan-16 (analytics et statistiques) - DuckDB, menu avec periodes, detection anomalies |
| 2025-12-29 | Ajout plan-15 (detection MCP Notify ask_user) - Heuristique session idle + tool completed |
| 2025-12-29 | Plan-14 termine - Detection permissions heuristique (icone cadenas, seuil configurable) v2.10.0 |
| 2025-12-29 | Ajout plan-14 (permission detection via heuristique polling) - Nouvelle approche viable |
| 2025-12-29 | Projet renomme opencode-monitor, branche main, tests 99% coverage (547 tests) |
| 2025-12-28 | Plan-13 termine - Refactoring modules security (database, risk_analyzer, reporter, terminal) v2.9.0 |
| 2025-12-28 | Plan-11 termine - Module securite avec analyse commands, reads, writes, webfetches v2.8.0 |
| 2025-12-28 | Plan-06 termine - Tooltips sur elements tronques v2.7.0 |
| 2025-12-28 | Plan-10 abandonne - API OpenCode ne supporte pas la detection de permissions via SSE |
| 2025-12-28 | Plan-12 termine - Fix preferences et menu v2.6.1 |
| 2025-12-28 | Ajout plan-12 (debug systeme preferences) |
| 2025-12-28 | Plan-07 marque non realisable - API OpenCode ne supporte pas la detection des permissions |
| 2025-12-28 | Mise a jour plan-10 - Integration notifications permissions simplifiee |
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
