# Plan 03 - Restructuration de l'affichage par session

## Contexte

Actuellement, le plugin SwiftBar affiche les informations dans des sections separees:
- Section "Instances" avec les agents
- Section "Tools" (globale)
- Section "Todos" (globale)

Ce design pose probleme car:
1. On ne sait pas quel tool appartient a quel agent
2. On ne sait pas quels todos appartiennent a quelle session
3. Avec une swarm d'agents, c'est impossible de suivre qui fait quoi

## Objectif

Restructurer l'affichage pour que toutes les informations soient rattachees a leur session/agent respectif. Seules les informations globales (usage API) restent en section separee.

## Comportement attendu

### Structure actuelle (problematique)

```
Instances (3)
  Port 4096 (1 busy)
    > Agent 1
  Port 4097 (1 busy)  
    > Agent 2
---
Tools (2)
  Bash
  Read
---
Todos (3)
  2 in progress
  1 pending
---
Session
  10% used
Weekly
  21% used
```

### Structure desiree

```
Instances (3)
  Port 4096 (1 busy)
    > Agent 1: "Ma tache"
      $ Bash: git status
      Todo: 2 in progress, 1 pending
  Port 4097 (1 busy)
    > Agent 2: "Autre tache"
      > Read: config.json
---
Session
  10% used
Weekly  
  21% used
```

### Hierarchie des informations

```
Instance (port)
  └── Agent (session)
       ├── Titre de la tache
       ├── Tools en cours (sous l'agent)
       └── Todos (sous l'agent)
```

### Regles d'affichage

1. **Tools**: Affiches sous leur agent, pas dans une section globale
2. **Todos**: Affiches sous leur agent, pas dans une section globale
3. **Permissions**: Indicateur sur l'agent concerne
4. **Usage API**: Reste global (seule section non liee aux sessions)

### Interactions

- Clic sur un agent → Focus iTerm2 sur la session
- Clic sur un tool → Focus iTerm2 sur la session (meme comportement)
- Les informations de chaque agent sont groupees visuellement

## Checklist de validation

- [ ] Les tools sont affiches sous leur agent respectif
- [ ] Les todos sont affiches sous leur agent respectif
- [ ] La section "Tools" globale est supprimee
- [ ] La section "Todos" globale est supprimee
- [ ] L'usage API reste en section globale separee
- [ ] Chaque agent montre clairement ses informations groupees
- [ ] L'affichage reste lisible avec plusieurs agents actifs
- [ ] Les clics fonctionnent correctement pour focus la bonne session
