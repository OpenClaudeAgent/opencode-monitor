# Plan 01 - Affichage des tools refined

## Contexte

Actuellement, quand des tools (Bash, Read, Write, etc.) sont executes par les agents, l'affichage dans SwiftBar montre trop de lignes separees. Par exemple, on voit une ligne pour "Bash", une autre pour la commande, etc. Cela rend l'interface confuse et difficile a lire.

Ce plugin est un outil de management pour une "swarm of agents". Il est crucial d'avoir une vue claire de ce que chaque agent execute.

## Objectif

Refiner l'affichage des tools en cours d'execution pour avoir une vue compacte et actionnable par agent/session.

## Comportement attendu

### Affichage actuel (problematique)
```
Tools (5)
  Bash
  Bash  
  Read
  ls -la
  cat file.txt
```

### Affichage desire
```
Instance Port 4096
  Agent: "Ma tache"
    Running: Bash (ls -la)
    Running: Read (file.txt)
```

### Interactions

- Chaque ligne de tool doit etre cliquable
- Un clic sur un tool doit focus la fenetre iTerm2 correspondante (via le TTY de l'instance)
- Le nom du tool + un resume de l'argument principal doivent etre visibles sur une seule ligne
- Si plusieurs tools tournent pour le meme agent, ils sont groupes sous cet agent

### Format compact

Pour chaque tool en cours:
- Afficher: `{icon} {tool_name}: {argument_resume}`
- Limiter l'argument a ~30 caracteres avec troncature "..."
- Exemples:
  - `$ Bash: git status`
  - `$ Bash: npm install --save-dev...`
  - `> Read: src/components/App.tsx`
  - `< Write: config.json`

## Checklist de validation

- [ ] Les tools sont affiches sous leur agent/session respectif (pas dans une section separee)
- [ ] Chaque tool affiche son nom + argument resume sur une seule ligne
- [ ] Les arguments longs sont tronques proprement
- [ ] Un clic sur un tool focus la bonne fenetre iTerm2
- [ ] L'affichage reste lisible avec 5+ tools en parallele
- [ ] Pas de lignes dupliquees ou confuses
