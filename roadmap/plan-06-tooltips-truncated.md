# Plan 06 - Tooltips sur elements tronques

## Contexte

Dans l'application menu bar, certains elements de texte sont tronques pour respecter les contraintes d'affichage des menus macOS :
- Noms d'outils (tool name) parfois longs
- Labels de todos pouvant etre verbeux
- Titres d'agents ou de sessions descriptifs
- Arguments de commandes (ex: chemins de fichiers longs)

Actuellement, quand un element est tronque (avec "..."), l'utilisateur n'a aucun moyen de voir le contenu complet sans aller chercher l'information ailleurs.

## Objectif

Afficher un tooltip natif macOS au survol des elements tronques, permettant a l'utilisateur de lire le contenu complet. Les elements non tronques ne doivent pas avoir de tooltip superflu.

## Comportement attendu

### 1. Detection du troncage

**Ce que l'application fait en interne** :
- Avant d'afficher un element de menu, l'application determine si le texte sera tronque
- Un texte est considere tronque s'il depasse une limite de longueur definie
- La limite peut varier selon le type d'element (tool name vs todo label vs agent title)

**Ce que l'utilisateur ne voit pas** :
- La logique de detection est transparente pour l'utilisateur
- Pas d'indication visuelle supplementaire que l'element est tronque (le "..." suffit)

### 2. Affichage du tooltip

**Ce que l'utilisateur voit** :
- Au survol d'un element tronque, un tooltip natif macOS apparait apres un court delai
- Le tooltip affiche le contenu complet, non tronque
- Le tooltip disparait quand le curseur quitte l'element

**Ce que l'utilisateur ne voit pas** :
- Pour les elements non tronques, aucun tooltip n'apparait
- Pas de tooltip vide ou repetant le texte deja visible

### 3. Types d'elements concernes

**Elements pouvant etre tronques** :
- Nom de l'outil en cours (ex: "Read: /un/tres/long/chemin/vers/fichier.py")
- Label de todo (ex: "Implementer la fonctionnalite de synchronisation...")
- Titre de l'agent/session (ex: "mon-super-projet-avec-nom-long")
- Arguments de commande (ex: chemins de fichiers, requetes)

**Comportement par type** :
- Tool name : tooltip avec le nom complet + argument complet
- Todo label : tooltip avec le texte complet de la todo
- Agent title : tooltip avec le chemin complet du projet ou le titre complet

### 4. Experience utilisateur

**Ce que l'utilisateur fait** :
- Survole un element tronque avec la souris
- Attend un instant (delai standard macOS)
- Lit le contenu complet dans le tooltip
- Continue sa navigation

**Ce que l'utilisateur observe** :
- Le tooltip apparait de maniere fluide et native
- Le contenu est lisible et formate proprement
- Le tooltip ne bloque pas l'interaction avec le menu

### 5. Cas limites

**Texte tres long** :
- Si le texte complet est extremement long, le tooltip peut etre limite a une longueur raisonnable
- Alternative : afficher sur plusieurs lignes si supporte

**Elements dynamiques** :
- Les tooltips se mettent a jour si le contenu change pendant que le menu est ouvert
- Pas de tooltip "stale" avec des informations obsoletes

## Checklist de validation

### Detection du troncage
- [ ] Les elements tronques sont correctement identifies
- [ ] Les elements non tronques n'ont pas de tooltip
- [ ] La limite de troncage est coherente pour chaque type d'element

### Affichage tooltip
- [ ] Le tooltip apparait au survol d'un element tronque
- [ ] Le tooltip affiche le contenu complet
- [ ] Le tooltip utilise le style natif macOS
- [ ] Le tooltip disparait quand le curseur quitte l'element

### Types d'elements
- [ ] Tooltip fonctionne sur les noms d'outils tronques
- [ ] Tooltip fonctionne sur les labels de todos tronques
- [ ] Tooltip fonctionne sur les titres d'agents tronques
- [ ] Tooltip fonctionne sur les arguments de commandes tronques

### Experience utilisateur
- [ ] Le delai d'apparition est naturel (standard macOS)
- [ ] Le tooltip ne gene pas la navigation dans le menu
- [ ] Le contenu du tooltip est lisible et bien formate
- [ ] Pas de tooltip superflu sur les elements non tronques

### Cas limites
- [ ] Les textes tres longs sont geres proprement
- [ ] Les elements dynamiques ont des tooltips a jour
