# Plan 00 - Outil de debug et logging des sessions OpenCode

## Contexte

Les demons actuels (`opencode-eventd`, `opencode-usaged`) utilisent l'API HTTP d'OpenCode pour recuperer l'etat des sessions. Cependant:

1. Le comportement de l'API n'est pas documente officiellement
2. Les evenements SSE ne sont pas toujours fiables ou complets
3. Il est difficile de debugger ce qui se passe reellement
4. On a perdu le controle sur la comprehension du flux de donnees

Avant d'ameliorer les fonctionnalites (plans 01-03), il faut reprendre le controle en ayant une visibilite complete sur les donnees disponibles.

## Objectif

Creer un outil de developpement qui:
1. Ecoute toutes les sessions OpenCode actives
2. Log tous les evenements et donnees dans des fichiers analysables
3. Permet de comprendre exactement ce que l'API expose
4. Sert de base pour ameliorer les demons existants

## Sources de donnees a explorer

### 1. API HTTP actuelle (utilisee par les demons)

| Endpoint | Description | Fiabilite |
|----------|-------------|-----------|
| `/session/status` | Statut de toutes les sessions | A verifier |
| `/session/{id}` | Details d'une session | A verifier |
| `/session/{id}/message` | Messages d'une session | A verifier |
| `/session/{id}/todo` | Todos d'une session | A verifier |
| `/event` | Stream SSE d'evenements | Incomplet? |

### 2. MCP Server OpenCode (a explorer)

OpenCode peut exposer un serveur MCP. A investiguer:
- Comment l'activer?
- Quelles donnees sont exposees?
- Est-ce plus fiable que l'API HTTP?

### 3. Fichiers locaux OpenCode

OpenCode stocke probablement des donnees localement:
- `~/.local/share/opencode/` ?
- Logs internes?
- Base de donnees SQLite?

## Comportement attendu de l'outil de debug

### Mode "record"

```bash
make debug-record
# ou
./bin/opencode-debug record
```

L'outil:
1. Decouvre toutes les instances OpenCode actives
2. Se connecte a chaque instance
3. Ecoute le stream SSE
4. Poll periodiquement les endpoints HTTP
5. Ecrit tout dans des fichiers de log structures

### Structure des logs

```
/tmp/opencode-debug/
  2025-12-28_09-30-00/
    events.jsonl          # Tous les evenements SSE (1 JSON par ligne)
    poll-status.jsonl     # Resultats des polls /session/status
    poll-sessions.jsonl   # Resultats des polls /session/{id}
    summary.json          # Resume de la session de debug
```

### Mode "analyze"

```bash
make debug-analyze
```

Affiche un resume:
- Types d'evenements recus
- Frequence des evenements
- Donnees manquantes ou incoherentes
- Suggestions d'amelioration

## Questions a resoudre

1. Quels evenements SSE sont emis et quand?
2. Les donnees des endpoints HTTP sont-elles coherentes avec les evenements?
3. Y a-t-il des evenements manquants (ex: erreurs)?
4. Comment detecter fiablement qu'une tache est terminee?
5. Comment detecter fiablement une erreur?
6. Le MCP server est-il une meilleure option?

## Livrables

1. Script `bin/opencode-debug` avec modes record/analyze
2. Documentation des endpoints API decouverts
3. Recommandations pour ameliorer les demons existants
4. Mise a jour du Makefile avec commandes debug

## Checklist de validation

- [ ] L'outil peut decouvrir toutes les instances OpenCode
- [ ] L'outil log tous les evenements SSE dans un fichier
- [ ] L'outil log les resultats des polls HTTP
- [ ] Les logs sont au format JSONL (analysable)
- [ ] Le mode analyze produit un resume utile
- [ ] On comprend mieux le comportement de l'API
- [ ] Recommandations documentees pour les demons
