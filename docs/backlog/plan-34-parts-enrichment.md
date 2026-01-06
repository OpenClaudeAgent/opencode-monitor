# Plan 34 - Parts Enrichment (Reasoning, Step-Finish, Patch)

## Contexte

L'analyse du code source OpenCode et des fichiers JSON reels a revele que le loader actuel (`loader.py` lignes 217-234) ne traite que 2 types de parts sur 7 disponibles :

| Type | Charge | Contenu |
|------|--------|---------|
| `text` | Oui | Contenu textuel des messages |
| `tool` | Oui | Appels d'outils avec arguments/resultats |
| `reasoning` | **Non** | Pensees internes de l'agent + signature Anthropic |
| `step-finish` | **Non** | Tokens par step, snapshot git, cout precis |
| `step-start` | **Non** | Debut de step avec snapshot initial |
| `patch` | **Non** | Hash git + liste fichiers modifies |
| `compaction` | **Non** | Flag compaction auto/manuelle |
| `file` | **Non** | Attachements (images en base64) |

Ces donnees sont precieuses pour :
- **Debugging** : Comprendre le raisonnement de l'agent
- **Couts precis** : Tokens par step plutot que par message
- **Tracabilite** : Snapshots git pour historique modifications
- **Analytics** : Metriques sur le processus de reflexion

## Objectif

Charger les 5 types de parts actuellement ignores et exposer ces donnees via l'API.

## Comportement attendu

### Chargement des parts enrichis

1. **Reasoning parts** :
   - Extraire `text` (pensees de l'agent)
   - Extraire `metadata.anthropic.signature` (signature crypto)
   - Extraire `time.start` et `time.end`
   - Stocker dans table `parts` avec `part_type = 'reasoning'`

2. **Step-finish parts** :
   - Extraire `reason` (tool-calls, end_turn, etc.)
   - Extraire `snapshot` (hash git)
   - Extraire `cost` et `tokens` (input, output, reasoning, cache)
   - Stocker dans nouvelle table `step_events`

3. **Patch parts** :
   - Extraire `hash` (hash git du commit)
   - Extraire `files` (liste fichiers modifies)
   - Stocker dans nouvelle table `patches`

4. **Compaction parts** :
   - Extraire `auto` (boolean)
   - Stocker dans table `parts` avec metadata

5. **File parts** (basse priorite) :
   - Extraire `mime`, `filename`, `url`
   - Stocker reference (pas le contenu base64 complet)

### Acces via API

- `GET /api/session/<id>/reasoning` : Liste des pensees de l'agent
- `GET /api/session/<id>/steps` : Timeline des steps avec tokens/cout
- `GET /api/session/<id>/git-history` : Historique des patches git
- `GET /api/session/<id>/precise-cost` : Cout calcule depuis step-finish

### Dashboard

- Nouvel onglet "Reasoning" dans le detail session (optionnel, phase 2)
- Affichage du cout precis (depuis steps vs depuis messages)

## Specifications

### Schema DB - Nouvelles tables

```sql
-- Step events (step-start, step-finish)
CREATE TABLE IF NOT EXISTS step_events (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    message_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,  -- 'start' ou 'finish'
    reason VARCHAR,               -- Pour finish: tool-calls, end_turn, etc.
    snapshot_hash VARCHAR,        -- Git hash
    cost DECIMAL(10,6) DEFAULT 0,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_reasoning INTEGER DEFAULT 0,
    tokens_cache_read INTEGER DEFAULT 0,
    tokens_cache_write INTEGER DEFAULT 0,
    created_at TIMESTAMP
);

-- Patches (modifications git)
CREATE TABLE IF NOT EXISTS patches (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    message_id VARCHAR NOT NULL,
    git_hash VARCHAR NOT NULL,
    files TEXT[],  -- Liste des fichiers modifies
    created_at TIMESTAMP
);
```

### Schema DB - Enrichissement parts

```sql
-- Colonnes additionnelles pour parts
ALTER TABLE parts ADD COLUMN IF NOT EXISTS reasoning_text TEXT;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS anthropic_signature TEXT;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS compaction_auto BOOLEAN;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS file_mime VARCHAR;
ALTER TABLE parts ADD COLUMN IF NOT EXISTS file_name VARCHAR;
```

### Modification loader.py

Dans `load_parts_fast()`, ajouter apres ligne 234 :

```python
elif part_type == "reasoning":
    text = data.get("text", "")
    metadata = data.get("metadata", {})
    signature = metadata.get("anthropic", {}).get("signature")
    # Stocker dans parts avec colonnes enrichies

elif part_type == "step-finish":
    # Stocker dans step_events
    reason = data.get("reason")
    snapshot = data.get("snapshot")
    cost = data.get("cost", 0)
    tokens = data.get("tokens", {})

elif part_type == "patch":
    # Stocker dans patches
    git_hash = data.get("hash")
    files = data.get("files", [])
```

## Checklist de validation

- [ ] Table `step_events` creee avec schema correct
- [ ] Table `patches` creee avec schema correct
- [ ] Colonnes enrichies ajoutees a `parts`
- [ ] `load_parts_fast()` traite les 5 nouveaux types
- [ ] Tests unitaires pour chaque type de part
- [ ] Endpoint `/api/session/<id>/reasoning` fonctionnel
- [ ] Endpoint `/api/session/<id>/steps` fonctionnel
- [ ] Endpoint `/api/session/<id>/git-history` fonctionnel
- [ ] TracingDataService enrichi avec nouvelles methodes
- [ ] Documentation mise a jour

## Estimation

- **Effort** : Medium (2-3 jours)
- **Risque** : Faible (ajout de fonctionnalites, pas de breaking changes)
- **Dependances** : Aucune
