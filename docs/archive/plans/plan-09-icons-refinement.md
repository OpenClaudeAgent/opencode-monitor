# Plan 09 - Refinement des icones

## Contexte

L'application menu bar utilise actuellement un ensemble d'icones emoji pour representer les differents etats et elements :

| Element | Icone actuelle | Probleme |
|---------|----------------|----------|
| Agent principal | 🤖 | - |
| Sub-agent busy | ↳ 🔵 | Tres moche, le combo fleche + emoji bleu ne fonctionne pas visuellement |
| Sub-agent idle | ↳ ⚪ | Meme probleme que busy |
| Instance idle | ⚪ | - |
| Tool en cours | 🔧 | - |
| Todo in_progress | 🔄 | - |
| Todo pending | ⏳ | - |
| Usage API (niveaux) | 🟢🟡🟠🔴 | - |
| Weekly usage | 📅 | - |

Le principal probleme est l'icone des sub-agents (↳ 🔵 / ↳ ⚪) qui manque d'elegance et de lisibilite. Plus generalement, le style visuel global pourrait etre plus harmonieux.

## Objectif

Ameliorer l'ensemble des icones de l'application pour :
1. Remplacer l'icone sub-agent par quelque chose de plus elegant
2. Harmoniser le style visuel global (coherence entre les icones)
3. Ameliorer la lisibilite dans le menu macOS

## Comportement attendu

### 1. Nouvelle icone pour les sub-agents

**Probleme actuel** :
- La combinaison "↳ 🔵" est visuellement incoherente
- La fleche ↳ et l'emoji 🔵 ont des styles differents
- Le rendu est "bricolé" et peu professionnel

**Ce que l'utilisateur devrait voir** :
- Une icone de sub-agent claire et elegante
- Distinction visuelle entre agent principal et sub-agent
- Distinction entre etat busy et idle

**Pistes a explorer** :
- Utiliser une indentation sans fleche (espaces + icone)
- Choisir des emojis plus subtils pour les sub-agents
- Utiliser des variantes plus legeres (cercles vides vs pleins)
- Tester des caracteres Unicode alternatifs

### 2. Harmonisation du style visuel

**Ce que l'utilisateur devrait percevoir** :
- Coherence visuelle entre tous les elements du menu
- Les icones appartiennent a la meme "famille" visuelle
- Pas de rupture de style entre les differents types d'elements

**Principes de design** :
- Minimalisme : preferer des icones simples et lisibles
- Coherence : meme poids visuel pour les elements du meme niveau
- Hierarchie : les elements importants ressortent naturellement
- Elegance : rendu natif macOS, pas "bricolé"

### 3. Grille de coherence

**Hierarchie visuelle souhaitee** :
```
Instances (niveau 1)
  └── Agents (niveau 2)
       └── Sub-agents (niveau 3)
            └── Details (tools, todos)
```

**Ce que l'utilisateur observe** :
- La hierarchie est claire grace aux icones ET a l'indentation
- Chaque niveau a son style propre mais coherent
- Les etats (busy/idle) sont immediatement reconnaissables

### 4. Considerations pour les etats

**Etats a differencier** :
- Idle vs Busy (agents et instances)
- In progress vs Pending (todos)
- Niveaux d'usage (vert → rouge)

**Ce que l'utilisateur devrait voir** :
- Les etats busy/actifs attirent l'attention
- Les etats idle/pending sont plus discrets
- La severite des niveaux d'usage est intuitive (vert = ok, rouge = attention)

### 5. Compatibilite et lisibilite

**Contraintes techniques** :
- Les icones doivent bien rendre dans les menus macOS
- Taille fixe des caracteres dans le menu
- Rendu correct sur ecrans Retina et non-Retina
- Lisibilite en mode clair et sombre

**Ce que l'utilisateur observe** :
- Les icones sont lisibles quelle que soit la configuration
- Pas de caracteres manquants ou mal rendus
- Le menu reste propre et professionnel

### 6. Propositions de style (a evaluer)

**Style minimaliste (cercles)** :
```
● Agent busy      ○ Agent idle
  ◉ Sub-agent busy   ◎ Sub-agent idle
```

**Style avec indicateurs** :
```
▶ Agent busy      ▷ Agent idle
  • Sub-agent busy   ◦ Sub-agent idle
```

**Style emoji coherent** :
```
🔵 Agent busy     ⚪ Agent idle
  💠 Sub-agent busy   ⚬ Sub-agent idle (caractere alternatif)
```

**Note** : Ces propositions sont indicatives. L'executeur testera differentes options et choisira la plus elegante.

### 7. Elements a conserver ou ameliorer

**Elements potentiellement a conserver** :
- 🔧 pour les tools (reconnaissable)
- 🟢🟡🟠🔴 pour les niveaux d'usage (intuitif)

**Elements a reconsiderer** :
- 🤖 pour l'agent principal (peut etre trop "lourd")
- 🔄 et ⏳ pour les todos (coherence avec le reste)
- 📅 pour weekly usage (necessaire ?)

## Checklist de validation

### Sub-agents
- [ ] Nouvelle icone sub-agent busy elegante
- [ ] Nouvelle icone sub-agent idle elegante
- [ ] Distinction claire entre agent principal et sub-agent
- [ ] La fleche ↳ n'est plus utilisee (ou remplacee par une alternative elegante)

### Harmonisation
- [ ] Toutes les icones ont un style coherent
- [ ] La hierarchie visuelle est claire
- [ ] Pas de rupture de style dans le menu
- [ ] Les icones sont de poids visuel similaire

### Etats
- [ ] Distinction claire busy/idle
- [ ] Distinction claire in_progress/pending pour todos
- [ ] Niveaux d'usage intuitifs

### Lisibilite
- [ ] Icones lisibles sur ecran Retina
- [ ] Icones lisibles sur ecran non-Retina
- [ ] Rendu correct en mode clair
- [ ] Rendu correct en mode sombre
- [ ] Pas de caracteres manquants ou mal rendus

### Experience utilisateur
- [ ] Le menu est visuellement agreable
- [ ] Les informations importantes ressortent
- [ ] L'aspect general est professionnel
- [ ] Feedback utilisateur positif sur les nouvelles icones
