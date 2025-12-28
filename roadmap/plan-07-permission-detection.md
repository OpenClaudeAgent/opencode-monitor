# Plan 07 - Detection des permissions (agents stuck)

## Contexte

OpenCode (Claude Code CLI) demande regulierement des permissions a l'utilisateur avant d'executer certaines actions sensibles (ecriture de fichiers, execution de commandes, etc.). Quand une permission est demandee, l'agent est bloque en attente de la reponse de l'utilisateur.

**Probleme actuel** :
- Aucune detection fiable de l'etat "waiting for permission"
- Impossible de distinguer un agent "busy" sur une tache longue d'un agent "stuck" sur une permission
- L'utilisateur peut oublier qu'un agent attend une reponse dans un autre terminal
- Pas de moyen de savoir quelle permission est demandee sans aller regarder le terminal

**Historique** :
- Une detection des permissions existait mais a ete retiree car peu fiable
- Le mecanisme doit etre repense pour etre plus robuste

## Objectif

Implementer une detection fiable des permissions en attente, permettant :
1. D'identifier quelle session demande une permission
2. De savoir quelle permission est demandee
3. De detecter les agents "stuck" (permission non traitee depuis un moment)
4. De rediriger l'utilisateur vers l'agent concerne

## Comportement attendu

### 1. Detection d'une permission en attente

**Ce que l'application observe** :
- Un agent passe en etat "waiting for permission"
- L'etat persiste tant que l'utilisateur n'a pas repondu (yes/no)
- L'etat se resout quand la permission est accordee ou refusee

**Ce que l'application doit identifier** :
- Le type de permission demandee (si disponible dans les donnees)
- La session/agent concerne
- Le timestamp du debut de l'attente

### 2. Affichage dans le menu

**Ce que l'utilisateur voit** :
- Un indicateur visuel clair sur l'agent en attente de permission
- L'indicateur se distingue de l'etat "busy" normal
- Le type de permission est affiche si disponible

**Exemples d'affichage** :
- "Agent X - Waiting for permission"
- "Agent X - Permission: Write file"
- Icone ou couleur differente de l'etat "busy" normal

### 3. Detection des agents "stuck"

**Definition de "stuck"** :
- Un agent est "stuck" quand il attend une permission depuis plus d'un certain delai
- Le delai suggere : 30 secondes ou plus (a ajuster selon l'usage)
- Un agent "stuck" merite une notification plus urgente

**Ce que l'utilisateur voit** :
- Apres le delai, l'indicateur visuel change (couleur plus vive, icone d'alerte)
- L'icone de la menu bar peut changer pour signaler un agent stuck

**Ce que l'application fait** :
- Suit le temps depuis le debut de l'attente de permission
- Change l'affichage quand le seuil "stuck" est atteint
- Peut declencher une notification ou un son d'alerte

### 4. Notification et redirection

**Notification** :
- Une notification peut etre envoyee quand une permission est detectee
- Une notification plus urgente quand un agent devient "stuck"
- Configurable par l'utilisateur (voir plan-08 settings)

**Redirection vers l'agent** :
- L'utilisateur peut cliquer sur l'agent en attente
- Le clic ouvre/focus le terminal sur la session concernee
- L'utilisateur peut alors repondre a la permission

**Ce que l'utilisateur fait** :
- Voit l'indicateur de permission dans le menu
- Clique sur l'agent ou l'item "Focus terminal"
- Le terminal s'active sur la bonne session
- L'utilisateur repond a la permission (yes/no)

### 5. Indicateurs visuels globaux

**Icone menu bar** :
- Couleur orange quand au moins un agent attend une permission
- Couleur rouge quand un agent est "stuck" depuis longtemps
- Retour a la couleur normale (vert/jaune) quand resolue

**Compteur optionnel** :
- Peut afficher le nombre d'agents en attente de permission
- Ex: "2 pending" dans le tooltip de l'icone

### 6. Source des donnees

**Ce que l'application doit analyser** :
- L'etat retourne par l'API OpenCode pour chaque session
- Les indicateurs de permission dans les donnees de l'agent
- Le timestamp de changement d'etat pour calculer la duree

**Robustesse** :
- La detection doit fonctionner meme si les donnees sont incompletes
- Pas de faux positifs (agent busy != permission pending)
- Pas de faux negatifs (permission reellement en attente doit etre detectee)

### 7. Cas limites

**Permission resolue rapidement** :
- Si la permission est traitee avant le prochain refresh, l'indicateur peut ne jamais apparaitre
- C'est un comportement acceptable

**Plusieurs permissions simultanees** :
- Plusieurs agents peuvent attendre des permissions en meme temps
- Chaque agent affiche son propre indicateur
- L'icone menu bar reflete l'etat global (le pire cas)

**Reconnexion apres deconnexion** :
- Apres une perte de connexion, les etats de permission doivent etre redetectes
- Le timestamp "stuck" redemarrer depuis la reconnexion

## Checklist de validation

### Detection de base
- [ ] L'etat "waiting for permission" est correctement detecte
- [ ] La session/agent concerne est identifie
- [ ] Le type de permission est affiche si disponible

### Affichage dans le menu
- [ ] L'agent en attente a un indicateur visuel distinct
- [ ] L'indicateur se distingue clairement de l'etat "busy"
- [ ] Le texte ou l'icone indique qu'une permission est attendue

### Detection "stuck"
- [ ] Le temps d'attente est suivi
- [ ] L'affichage change apres le seuil "stuck"
- [ ] L'icone menu bar reflete l'etat "stuck"

### Notifications
- [ ] Une notification peut etre envoyee pour une permission
- [ ] Une notification plus urgente pour un agent "stuck"
- [ ] Les notifications sont configurables

### Redirection
- [ ] Le clic sur l'agent focus le bon terminal
- [ ] L'utilisateur peut facilement repondre a la permission
- [ ] Le comportement est coherent avec le reste de l'application

### Indicateurs globaux
- [ ] L'icone menu bar change de couleur pour les permissions
- [ ] Orange pour permission en attente
- [ ] Rouge pour agent stuck

### Robustesse
- [ ] Pas de faux positifs (busy != permission)
- [ ] Pas de faux negatifs (permissions non detectees)
- [ ] Gestion correcte des permissions multiples simultanees
- [ ] Reprise correcte apres deconnexion/reconnexion
