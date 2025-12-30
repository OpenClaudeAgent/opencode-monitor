# Plan 19 - Heuristiques EDR pour le Security Audit

## Contexte

Le module de securite actuel (plan-11) analyse chaque commande de maniere isolee avec des patterns regex statiques. Cette approche fonctionne pour les menaces evidentes (`rm -rf /`, `curl | bash`) mais manque de sophistication pour detecter des comportements suspects plus subtils.

Les systemes EDR (Endpoint Detection and Response) modernes utilisent des techniques avancees :
- Analyse comportementale sur sequences d'evenements
- Correlation multi-sources
- Detection d'anomalies par rapport a une baseline
- Mapping sur des frameworks comme MITRE ATT&CK

L'objectif est d'explorer ces techniques et d'evaluer lesquelles peuvent ameliorer notre systeme d'audit.

## Objectif

Enrichir le moteur d'analyse de securite avec des heuristiques inspirees des EDR pour :
1. Detecter des patterns d'attaque multi-etapes (kill chains)
2. Correler les evenements entre eux (read + webfetch = exfiltration)
3. Identifier les anomalies comportementales
4. Fournir un contexte plus riche pour l'evaluation des risques

**Approche :** Exploration et implementation incrementale. Chaque axe est evalue independamment avant integration.

## Comportement attendu

### Axe 1 - Analyse de sequences (Kill Chains)

**Concept :**
Certaines attaques se manifestent par une sequence de commandes inoffensives individuellement mais suspectes ensemble.

**Sequences a detecter :**

| Sequence | Interpretation | Score additionnel |
|----------|----------------|-------------------|
| `read(.env)` → `webfetch(externe)` | Exfiltration de secrets | +40 |
| `write(*.sh)` → `chmod(+x)` → `bash(*.sh)` | Creation et execution de script | +30 |
| `git clone` → `npm install` → `bash` | Potentiel supply chain | +25 |
| `read(/etc/passwd)` → `read(/etc/shadow)` | Enumeration systeme | +35 |
| Multiple `rm` en < 30s | Suppression massive | +20 |

**Fenetre temporelle :** Les sequences sont evaluees sur une fenetre glissante (ex: 5 minutes par session).

**Implementation :**
- Buffer circulaire des N derniers evenements par session
- Moteur de pattern matching sur les sequences
- Score supplementaire ajoute au dernier evenement de la sequence

### Axe 2 - Correlation multi-evenements

**Concept :**
Croiser les informations entre differents types d'evenements pour enrichir l'analyse.

**Correlations a implementer :**

| Source | Destination | Signal |
|--------|-------------|--------|
| `read(fichier_sensible)` | `webfetch(url_externe)` | Exfiltration potentielle |
| `webfetch(script)` | `bash(commande_similaire)` | Execution de code distant |
| `write(path)` | `bash(chmod path)` | Preparation d'execution |
| `read(.git/config)` | `webfetch(autre_remote)` | Reconnaissance |

**Donnees a croiser :**
- Chemins de fichiers entre read/write et bash
- URLs entre webfetch et commandes curl/wget
- Timestamps pour proximite temporelle

### Axe 3 - Baseline et detection d'anomalies

**Concept :**
Etablir un profil "normal" et detecter les deviations.

**Metriques de baseline :**
- Commandes les plus frequentes par session/projet
- Volume moyen d'operations par periode
- Patterns d'acces fichiers habituels
- Horaires d'activite typiques

**Anomalies detectables :**

| Anomalie | Description | Indicateur |
|----------|-------------|------------|
| Premiere occurrence | Commande jamais vue dans ce projet | Flag "NEW" |
| Volume inhabituel | 10x plus de rm que d'habitude | Score +15 |
| Heure atypique | Activite a 3h du matin | Score +10 |
| Chemin inhabituel | Acces a /etc/ dans un projet web | Score +20 |

**Stockage :**
- Table de statistiques par projet/session dans la DB
- Historique des commandes uniques vues
- Compteurs par type d'operation

### Axe 4 - Mapping MITRE ATT&CK

**Concept :**
Classifier les detections selon le framework MITRE ATT&CK pour un contexte standardise.

**Techniques pertinentes :**

| ID | Technique | Patterns detectables |
|----|-----------|---------------------|
| T1059 | Command and Scripting Interpreter | Shells obfusques, eval, source |
| T1048 | Exfiltration Over Alternative Protocol | curl/wget vers IP externe |
| T1222 | File and Directory Permissions Modification | chmod sur scripts, 777 |
| T1070 | Indicator Removal | rm logs, history -c, shred |
| T1105 | Ingress Tool Transfer | wget/curl executables |
| T1053 | Scheduled Task/Job | crontab modifications |
| T1087 | Account Discovery | cat /etc/passwd, id, whoami |
| T1082 | System Information Discovery | uname, cat /proc |

**Implementation :**
- Chaque pattern existant est enrichi d'un tag MITRE
- Le rapport de securite peut grouper par technique
- Aide a la comprehension du risque

### Axe 5 - Scoring contextuel dynamique

**Concept :**
Ajuster le score en fonction du contexte plutot qu'une evaluation statique.

**Facteurs de contexte :**

| Facteur | Effet sur le score |
|---------|-------------------|
| Projet sensible (credentials, infra) | Multiplicateur x1.5 |
| Agent avec historique d'alertes | +10 par alerte precedente |
| Commande dans une sequence suspecte | +score sequence |
| Premiere occurrence de la commande | +5 (flag "NEW") |
| Heure hors plage normale | +10 |
| Cible = fichier deja alerte | +15 |

**Scoring final :**
```
score_final = (score_pattern + score_sequence + score_anomalie) * multiplicateur_contexte
```

### Integration dans le systeme existant

**Modifications du SecurityAuditor :**
- Nouveau composant `SequenceAnalyzer` pour l'analyse de sequences
- Nouveau composant `BaselineManager` pour les anomalies
- Extension de `SecurityAlert` avec champs MITRE et contexte
- Buffer d'evenements recents par session

**Rapport enrichi :**
- Section "Kill Chains detectees"
- Section "Anomalies comportementales"
- Groupement par technique MITRE
- Timeline visuelle des sequences

**Performance :**
- Analyse en O(1) pour les patterns simples (existant)
- Analyse en O(n) pour les sequences (n = taille du buffer, limite)
- Baseline mise a jour incrementalement

## Checklist de validation

### Axe 1 - Sequences
- [ ] Buffer d'evenements par session implemente
- [ ] Patterns de sequences definis et configurables
- [ ] Detection de sequence read→webfetch fonctionnelle
- [ ] Detection de sequence write→chmod→bash fonctionnelle
- [ ] Score additionnel correctement calcule
- [ ] Tests unitaires pour chaque pattern de sequence

### Axe 2 - Correlation
- [ ] Correlation entre read et webfetch
- [ ] Correlation entre write et bash
- [ ] Fenetre temporelle configurable
- [ ] Tests de correlation

### Axe 3 - Baseline
- [ ] Stockage des statistiques par projet
- [ ] Detection "premiere occurrence"
- [ ] Detection volume inhabituel
- [ ] Flag visuel pour anomalies
- [ ] Tests baseline et anomalies

### Axe 4 - MITRE ATT&CK
- [ ] Mapping des patterns existants vers MITRE
- [ ] Tags MITRE dans les alertes
- [ ] Documentation des techniques couvertes
- [ ] Section MITRE dans le rapport

### Axe 5 - Scoring contextuel
- [ ] Facteurs de contexte implementes
- [ ] Multiplicateur projet sensible
- [ ] Historique agent pris en compte
- [ ] Score final combine correctement

### Integration
- [ ] SequenceAnalyzer integre au SecurityAuditor
- [ ] BaselineManager integre
- [ ] Rapport enrichi avec nouvelles sections
- [ ] Performance acceptable (< 100ms par analyse)
- [ ] Tests d'integration complets
- [ ] Documentation des nouvelles heuristiques
