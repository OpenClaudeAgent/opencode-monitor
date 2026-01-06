# Plan 11 - Module de securite / Analyse des commandes

## Contexte

L'application monitore les instances OpenCode qui executent des commandes via leurs tools (Bash, Read, Write, Edit, etc.). Certaines de ces commandes peuvent etre potentiellement dangereuses : suppression de fichiers, modification de permissions, execution de code distant, operations SQL destructives, etc.

Actuellement, l'utilisateur voit les commandes s'executer sans indication de leur niveau de risque. Il n'a pas de moyen rapide d'identifier une commande critique qui meriterait son attention.

## Objectif

Fournir un systeme de surveillance passive qui analyse les commandes executees par les agents, les classe par niveau de criticite, et alerte l'utilisateur lorsqu'une commande potentiellement dangereuse est detectee.

**Principes directeurs :**
- Monitoring passif uniquement (ne jamais bloquer l'execution)
- Alertes informatives sans etre intrusives
- Tolerance aux faux positifs (commandes legitimes flaggees)
- Performance minimale (analyse en temps reel sans impact)

## Comportement attendu

### Niveaux de criticite

Le systeme classe chaque commande selon 4 niveaux :

| Niveau | Score | Description | Exemples typiques |
|--------|-------|-------------|-------------------|
| **Critique** | 80-100 | Risque majeur de perte de donnees ou compromission systeme | `rm -rf /`, `curl ... \| bash`, `dd if=... of=/dev/...` |
| **Eleve** | 50-79 | Operations sensibles necessitant attention | `sudo ...`, `chmod 777`, `DROP TABLE`, `DELETE FROM` |
| **Moyen** | 20-49 | Operations avec impact potentiel | `git push --force`, `kill -9`, modifications `/etc/` |
| **Bas** | 0-19 | Operations normales sans risque | `ls`, `cat`, `git status`, `npm install` |

### Detection des commandes

Le systeme analyse les commandes des tools suivants :
- **Bash** : Commandes shell (source principale)
- **Write/Edit** : Ecriture de fichiers (si chemins sensibles)

**Categories de patterns detectes :**
1. Commandes de suppression massives (`rm -rf`, `rmdir`, patterns avec wildcards)
2. Elevation de privileges (`sudo`, `su`, `doas`)
3. Modifications de permissions dangereuses (`chmod 777`, `chmod -R`)
4. Execution de code distant (`curl | bash`, `wget | sh`, `eval $(curl ...)`)
5. Operations Git destructives (`push --force`, `reset --hard`, `clean -fd`)
6. Operations SQL destructives (`DROP`, `DELETE`, `TRUNCATE`, patterns sans WHERE)
7. Modifications systeme (fichiers dans `/etc/`, `/usr/`, `/var/`, `/boot/`)
8. Gestion de processus aggressive (`kill -9`, `pkill`, `killall`)
9. Operations reseau suspectes (redirection de ports, tunnels)
10. Commandes de chiffrement/dechiffrement non sollicitees

### Indicateur visuel dans le menu

**Comportement normal (aucune alerte recente) :**
- Le menu s'affiche comme d'habitude, sans indication particuliere

**Quand une commande critique/elevee est detectee :**
- Un indicateur d'alerte apparait dans la barre de menu (ex: point orange/rouge, ou badge)
- L'indicateur reste visible pendant un certain temps ou jusqu'a consultation

**Dans le sous-menu d'un agent :**
- Les commandes critiques/elevees sont marquees visuellement (emoji, couleur, prefixe)
- L'utilisateur peut distinguer immediatement les commandes a risque

### Notifications

**Commande critique detectee (score 80+) :**
- Notification systeme macOS avec le resume de la commande
- Son d'alerte optionnel (si les sons sont actives)
- La notification indique quel agent a execute la commande

**Commande elevee detectee (score 50-79) :**
- Notification optionnelle (configurable par l'utilisateur)
- Pas de son par defaut

**Commandes moyennes/basses :**
- Pas de notification
- Visibles uniquement dans l'historique

### Historique des commandes critiques

L'utilisateur peut acceder a un historique des commandes flaggees :
- Liste des X dernieres commandes critiques/elevees
- Pour chaque commande : timestamp, agent, commande (tronquee), niveau de criticite
- Action possible : copier la commande complete, voir le contexte

**Acces a l'historique :**
- Menu item "Security History" ou equivalent
- Sous-menu listant les alertes recentes

### Configuration

L'utilisateur peut configurer (via le panel Settings existant) :
- Activer/desactiver l'analyse de securite
- Niveau minimum pour les notifications (critique uniquement, eleve+, tout)
- Activer/desactiver le son d'alerte pour les commandes critiques
- Duree de retention de l'historique
- Eventuellement : patterns personnalises a ignorer (whitelist)

### Tolerances et faux positifs

Le systeme doit etre intelligent concernant le contexte :
- `rm -rf node_modules/` dans un projet → Moyen (pas Critique)
- `sudo brew install ...` → Eleve mais legitime sur macOS
- `git push --force origin feature-branch` → Moyen
- `git push --force origin main` → Critique

**Mecanisme de mitigation :**
- Les patterns tiennent compte des arguments complets
- Certaines commandes legitimes courantes sont reconnues
- L'utilisateur peut "dismiss" une alerte sans consequence

## Sous-taches

- 11.1 - Moteur d'analyse et scoring des commandes
- 11.2 - Integration avec le monitoring existant
- 11.3 - Indicateurs visuels dans le menu
- 11.4 - Notifications pour commandes critiques
- 11.5 - Historique des alertes de securite
- 11.6 - Configuration dans le panel Settings

## Priorite des sous-taches

| Priorite | Sous-tache | Dependances |
|----------|------------|-------------|
| 1 | 11.1 - Moteur d'analyse | Aucune |
| 2 | 11.2 - Integration monitoring | 11.1 |
| 3 | 11.3 - Indicateurs visuels | 11.2 |
| 4 | 11.4 - Notifications | 11.2, plan-10 (optionnel) |
| 5 | 11.5 - Historique | 11.2 |
| 6 | 11.6 - Configuration | 11.1, plan-08 |

## Checklist de validation

### Moteur d'analyse
- [ ] Les commandes Bash des agents sont analysees en temps reel
- [ ] Chaque commande recoit un score de criticite (0-100)
- [ ] Le niveau (bas/moyen/eleve/critique) est determine correctement
- [ ] Les patterns de base sont detectes : `rm -rf`, `sudo`, `chmod 777`, `curl|bash`, etc.
- [ ] L'analyse ne bloque pas l'affichage du menu
- [ ] Les faux positifs courants sont minimises (ex: `rm -rf node_modules`)

### Indicateurs visuels
- [ ] Un indicateur apparait dans la barre de menu quand une commande critique est detectee
- [ ] Les commandes critiques/elevees sont marquees dans le sous-menu de l'agent
- [ ] L'indicateur disparait apres un delai ou apres consultation

### Notifications
- [ ] Une notification macOS est envoyee pour les commandes critiques
- [ ] La notification indique l'agent et un resume de la commande
- [ ] Le son d'alerte fonctionne (si active)
- [ ] Les notifications respectent la configuration utilisateur

### Historique
- [ ] L'utilisateur peut voir les X dernieres commandes flaggees
- [ ] L'historique affiche : timestamp, agent, commande, niveau
- [ ] L'historique est accessible depuis le menu principal

### Configuration
- [ ] L'utilisateur peut activer/desactiver l'analyse de securite
- [ ] L'utilisateur peut choisir le niveau minimum pour les notifications
- [ ] Les preferences sont persistees dans la configuration existante

### Integration
- [ ] Le module s'integre sans modifier le comportement existant
- [ ] La performance de l'application n'est pas impactee significativement
- [ ] Le module peut etre desactive completement si souhaite
