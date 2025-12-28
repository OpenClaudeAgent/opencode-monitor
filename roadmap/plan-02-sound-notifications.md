# Plan 02 - Notifications sonores

## Contexte

Quand on manage une swarm d'agents, on n'a pas toujours les yeux sur la barre de menu. Des notifications sonores permettraient d'etre alerte des evenements importants sans avoir a surveiller constamment.

## Objectif

Ajouter des sons de notification pour les evenements critiques:
- Permission demandee (warning)
- Erreur rencontree (alerte)
- Tache completee (succes)

## Comportement attendu

### Evenements et sons

| Evenement | Type de son | Declencheur |
|-----------|-------------|-------------|
| Permission demandee | Warning/attention | Un agent attend une permission utilisateur (tool bloque > 5s) |
| Erreur | Alerte/erreur | Un agent rencontre une erreur (a definir) |
| Tache completee | Succes/completion | Tous les todos d'une session passent a "completed" |

### Regles

- Les sons doivent etre discrets mais audibles
- Utiliser les sons systeme macOS pour la coherence
- Eviter la repetition: un son par evenement, pas de spam
- Option future: pouvoir desactiver les sons (pas dans ce plan)

### Sons macOS suggeres

- Permission: "Ping" ou "Pop" (attention douce)
- Erreur: "Basso" ou "Funk" (alerte)
- Completion: "Glass" ou "Hero" (succes)

### Integration

Le daemon `opencode-eventd` doit:
1. Detecter les changements d'etat pertinents
2. Jouer le son approprie via `afplay` ou equivalent
3. Eviter les doublons (ne pas rejouer si deja joue pour cet evenement)

## Checklist de validation

- [ ] Son de warning quand une permission est demandee
- [ ] Son d'erreur quand une erreur est detectee
- [ ] Son de completion quand tous les todos d'une session sont termines
- [ ] Les sons ne sont pas spammes (1 son par evenement)
- [ ] Les sons sont audibles mais pas intrusifs
- [ ] Les sons fonctionnent meme si le plugin SwiftBar n'est pas au premier plan
