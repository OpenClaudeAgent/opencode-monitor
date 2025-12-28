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
| 1 | Affichage tools refined | [plan-01](./plan-01-tools-display.md) | `feature/tools-display` | - | En attente |
| 2 | Notifications sonores | [plan-02](./plan-02-sound-notifications.md) | `feature/sounds` | - | En attente |
| 3 | Restructuration par session | [plan-03](./plan-03-session-structure.md) | `feature/session-structure` | - | En attente |

## Priorite

Le plan 00 (debug/logging) doit etre realise EN PREMIER car il permet de:
- Comprendre exactement ce que l'API OpenCode expose
- Identifier les problemes actuels des demons
- Guider l'implementation des plans suivants

## Historique

| Date | Action |
|------|--------|
| 2025-12-28 | Plan-00 termine - Outil debug/logging v1.1.0 |
| 2025-12-28 | Ajout plan-00 debug/logging (prioritaire) |
| 2025-12-28 | Creation roadmap initiale avec 3 plans |
