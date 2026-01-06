# Plan 36 - Schema Cleanup & Consolidation

## Contexte

L'analyse du schema DB et du loader a revele plusieurs inconsistances :

### Colonnes migrees mais jamais remplies

| Table | Colonne | Ajoutee (db.py) | Remplie (loader.py) |
|-------|---------|-----------------|---------------------|
| `parts` | `call_id` | L450 | **Non** |
| `parts` | `ended_at` | L451 | **Non** |
| `parts` | `duration_ms` | L452 | **Non** |
| `parts` | `result_summary` | L454 | **Non** |
| `parts` | `error_message` | L455 | **Non** |
| `sessions` | `ended_at` | L458 | **Non** |
| `sessions` | `duration_ms` | L459 | **Non** |
| `sessions` | `is_root` | L460 | Toujours TRUE |
| `sessions` | `project_name` | L461 | **Non** |

### Duplication delegations / agent_traces

Les deux tables sont alimentees depuis la meme source (`tool == 'task'`) :
- `load_delegations()` : DuckDB bulk read, focus parent/child agents
- `extract_traces()` : Iteration Python, focus prompt/output/tools

### Tables fantomes

- `file_operations.trace_id` : Colonne definie mais toujours NULL
- `file_operations.risk_reason` : Toujours NULL ou "normal"

## Objectif

Nettoyer le schema : remplir les colonnes utiles, supprimer les inutiles, documenter les choix.

## Comportement attendu

### 1. Remplir les colonnes parts existantes

Dans `load_parts_fast()`, extraire :
- `call_id` : depuis `data["callID"]` (ID appel Claude)
- `ended_at` : depuis `state.time.end`
- `duration_ms` : calculer `end - start`
- `error_message` : depuis `state.error` si present

### 2. Remplir les colonnes sessions existantes

Apres INSERT sessions :
- `is_root` : `FALSE` si `parent_id IS NOT NULL`
- `project_name` : basename du `directory`
- `ended_at` : depuis `time.updated` (approximation)
- `duration_ms` : `updated - created`

### 3. Supprimer les colonnes inutilisees

- `parts.result_summary` : Pas de cas d'usage clair, supprimer
- OU documenter son usage prevu dans STRUCTURE.md

### 4. Clarifier delegations vs agent_traces

**Decision** : Garder les deux tables (usages differents)
- `delegations` : Vue legere pour stats parent/child
- `agent_traces` : Vue complete avec prompts et tools

Documenter cette decision dans STRUCTURE.md.

### 5. Migration script

Creer un script pour les DB existantes :
```sql
-- Marquer les sessions enfants
UPDATE sessions SET is_root = FALSE WHERE parent_id IS NOT NULL;

-- Calculer project_name depuis directory
UPDATE sessions SET project_name = regexp_extract(directory, '[^/]+$');

-- Calculer duration_ms
UPDATE sessions SET duration_ms = 
    EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000
WHERE duration_ms IS NULL AND updated_at IS NOT NULL;
```

## Specifications

### Modification load_parts_fast() - Extraction enrichie

```python
# Dans la boucle de traitement des parts tool
if part_type == "tool":
    state = data.get("state", {})
    time_data = state.get("time", {})
    
    # Existant
    tool_name = data.get("tool")
    tool_status = state.get("status")
    
    # Nouveau - call_id
    call_id = data.get("callID")
    
    # Nouveau - timing
    start_ts = time_data.get("start")
    end_ts = time_data.get("end")
    ended_at = ms_to_datetime(end_ts) if end_ts else None
    duration_ms = (end_ts - start_ts) if (start_ts and end_ts) else None
    
    # Nouveau - error
    error_message = state.get("error")
```

### Modification INSERT parts

```sql
INSERT OR REPLACE INTO parts 
(id, session_id, message_id, part_type, content, tool_name, tool_status, 
 created_at, arguments, call_id, ended_at, duration_ms, error_message)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

### Post-processing sessions

```python
def enrich_sessions_metadata(db: AnalyticsDB) -> None:
    """Enrich sessions with computed fields."""
    conn = db.connect()
    
    # Mark child sessions
    conn.execute("""
        UPDATE sessions 
        SET is_root = FALSE 
        WHERE parent_id IS NOT NULL AND is_root = TRUE
    """)
    
    # Extract project_name from directory
    conn.execute("""
        UPDATE sessions 
        SET project_name = regexp_extract(directory, '[^/]+$')
        WHERE project_name IS NULL AND directory IS NOT NULL
    """)
    
    # Calculate duration
    conn.execute("""
        UPDATE sessions 
        SET duration_ms = EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000
        WHERE duration_ms IS NULL 
          AND updated_at IS NOT NULL 
          AND created_at IS NOT NULL
    """)
    
    # Calculate ended_at (approximation)
    conn.execute("""
        UPDATE sessions 
        SET ended_at = updated_at
        WHERE ended_at IS NULL AND updated_at IS NOT NULL
    """)
```

### Documentation STRUCTURE.md

Ajouter section :
```markdown
## Schema Decisions

### delegations vs agent_traces
- `delegations` : Vue legere pour hierarchie parent/child
- `agent_traces` : Vue complete avec prompts/output/tools
- Les deux sont alimentees depuis tool='task' mais avec focus different
- Garder les deux pour flexibilite des requetes

### Colonnes parts enrichies
- `call_id` : ID appel Claude (toolu_xxx), utile pour debugging
- `ended_at` / `duration_ms` : Timing precis des tools
- `error_message` : Erreurs d'execution des tools
- `result_summary` : Reserve pour usage futur (resume automatique)
```

## Checklist de validation

- [ ] Colonnes parts remplies : call_id, ended_at, duration_ms, error_message
- [ ] Colonnes sessions remplies : is_root, project_name, ended_at, duration_ms
- [ ] Script de migration fonctionne sur DB existante
- [ ] `enrich_sessions_metadata()` integre dans `load_opencode_data()`
- [ ] Tests verifient que les colonnes sont remplies
- [ ] STRUCTURE.md documente les decisions
- [ ] Pas de regression sur les requetes existantes

## Estimation

- **Effort** : Medium (2 jours)
- **Risque** : Moyen (modification de colonnes existantes, migration)
- **Dependances** : Plan 34 (si on enrichit les parts en meme temps)
