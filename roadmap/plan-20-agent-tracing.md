# Plan 20 - Agent Tracing System

## Contexte

Actuellement, le monitoring affiche les agents actifs et leurs tools en temps reel, mais il n'y a pas de mecanisme pour suivre les traces completes d'execution : quels agents ont ete invoques, par qui, avec quels inputs/outputs, combien de temps ils ont pris, combien de tokens ils ont consomme.

Le systeme actuel (analytics DuckDB) stocke des statistiques agregees mais ne permet pas de reconstruire le flow d'execution d'une session ou de visualiser la chaine de delegation en temps reel.

## Objectif

Implementer un systeme de tracing pour capturer et visualiser les traces d'execution des agents :
- Tracer chaque invocation d'agent avec son contexte (parent, input, output)
- Suivre les delegations entre agents (qui a appele qui)
- Mesurer les durees d'execution et consommation de tokens par agent
- Permettre la reconstruction du flow complet d'une session

## Comportement attendu

### Capture des traces

Quand un agent demarre :
- Une trace est creee avec un ID unique, timestamp, agent parent (si delegation)
- L'input (prompt) est capture (ou un resume/hash si trop long)
- Le statut passe a "running"

Quand un agent termine :
- L'output est capture (ou un resume si trop long)
- Les metriques sont enregistrees (duree, tokens in/out, tools utilises)
- Le statut passe a "completed" ou "error"

### Visualisation

Dans le dashboard ou un outil dedie :
- Vue timeline : chronologie des agents avec durees
- Vue arbre : hierarchie des delegations (parent -> children)
- Vue flow : diagramme de la chaine d'execution
- Metriques : tokens par agent, duree totale, bottlenecks

### Filtrage

L'utilisateur peut :
- Filtrer par session, par date, par agent
- Rechercher des patterns (ex: "toutes les sessions avec tester -> refactoring")
- Identifier les sessions anormalement longues ou couteuses

## Sous-taches

Ce plan est divise en 3 phases independantes :

| Phase | Sous-tache | Description |
|-------|------------|-------------|
| 20.1 | Extraction des traces | Parser les fichiers session, extraire les tool "task" |
| 20.2 | Schema et stockage BDD | Table DuckDB, index, module queries |
| 20.3 | Affichage Dashboard | Section PyQt, QTreeWidget, panel detail |

### Priorite des sous-taches

| Priorite | Sous-tache | Dependances |
|----------|------------|-------------|
| 1 | 20.1 - Extraction | Aucune |
| 2 | 20.2 - BDD | 20.1 (besoin du modele de donnees) |
| 3 | 20.3 - Dashboard | 20.1 + 20.2 (besoin des donnees) |

---

## Decisions architecturales

### Collecte des traces

**Solution retenue** : Systeme OpenCode existant (pas de librairie de telemetrie)

- Le loader existant lit deja les fichiers de session OpenCode
- La DB DuckDB est en place pour les analytics
- Pas de dependance externe pour la collecte
- Coherence avec l'architecture existante

**Exclus** : OpenTelemetry, Langfuse, LangSmith

### Visualisation des traces

**Solution retenue** : 100% PyQt natif dans le dashboard existant

- Coherence avec le dashboard existant (widgets natifs)
- Plotly est dans une partie depreciee du projet
- Pas de dependance QWebEngineView
- Performance optimale

### Conservation des prompts

Les prompts sont conserves **en integralite** (pas de troncature) pour :
- Suivre la transmission des informations entre agents
- Debugger les problemes de communication
- Analyser la qualite des delegations

---

## 20.1 - Extraction des traces

### Objectif
Parser les fichiers de session OpenCode pour extraire les invocations du tool `task` (delegations).

### Fichiers concernes
- `analytics/loader.py` : Etendre pour extraire les traces

### Logique d'extraction

1. Parcourir les messages de chaque session
2. Identifier les tool calls avec `name: "task"`
3. Extraire les parametres : `subagent_type`, `prompt`, `description`
4. Trouver le message de reponse correspondant (prompt_output)
5. Calculer la duree (timestamp fin - timestamp debut)
6. Determiner le parent (agent qui a fait l'appel)

### Modele de donnees extrait

```python
@dataclass
class AgentTrace:
    trace_id: str           # UUID genere
    session_id: str
    parent_trace_id: str | None
    parent_agent: str | None
    subagent_type: str
    prompt_input: str       # Prompt complet
    prompt_output: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    tokens_in: int | None
    tokens_out: int | None
    status: str             # running, completed, error
    tools_used: list[str]
```

### Checklist 20.1
- [ ] Fonction `extract_traces(session_path) -> list[AgentTrace]`
- [ ] Detection des tool calls "task"
- [ ] Extraction prompt_input (parametre `prompt`)
- [ ] Extraction prompt_output (message de reponse)
- [ ] Calcul duree entre appel et reponse
- [ ] Detection du parent_agent
- [ ] Gestion des traces imbriquees (recursif)
- [ ] Tests unitaires extraction

---

## 20.2 - Schema et stockage BDD

### Objectif
Stocker les traces dans DuckDB avec un schema optimise pour les requetes.

### Fichiers concernes
- `analytics/db.py` : Ajouter table `agent_traces`
- `analytics/queries/trace_queries.py` : Nouveau module

### Schema SQL

```sql
CREATE TABLE agent_traces (
    trace_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    parent_trace_id VARCHAR,
    parent_agent VARCHAR,
    subagent_type VARCHAR NOT NULL,
    prompt_input TEXT NOT NULL,
    prompt_output TEXT,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_ms INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    status VARCHAR DEFAULT 'running',
    tools_used TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_traces_session ON agent_traces(session_id);
CREATE INDEX idx_traces_parent ON agent_traces(parent_trace_id);
CREATE INDEX idx_traces_subagent ON agent_traces(subagent_type);
CREATE INDEX idx_traces_date ON agent_traces(started_at);
```

### Queries a implementer

| Query | Description |
|-------|-------------|
| `get_traces_by_session(session_id)` | Toutes les traces d'une session |
| `get_trace_tree(session_id)` | Arbre hierarchique des delegations |
| `get_traces_by_date_range(start, end)` | Traces dans une periode |
| `get_traces_by_agent(subagent_type)` | Traces par type d'agent |
| `get_trace_details(trace_id)` | Detail complet avec prompts |
| `get_sessions_with_traces()` | Liste sessions ayant des traces |

### Checklist 20.2
- [ ] Table `agent_traces` dans `db.py`
- [ ] Index pour performance
- [ ] Fonction `save_traces(traces: list[AgentTrace])`
- [ ] Module `queries/trace_queries.py`
- [ ] Query `get_traces_by_session`
- [ ] Query `get_trace_tree` (reconstruction hierarchie)
- [ ] Query `get_traces_by_date_range`
- [ ] Query `get_sessions_with_traces`
- [ ] Tests unitaires queries

---

## 20.3 - Affichage Dashboard

### Objectif
Nouvelle section dans le dashboard PyQt pour visualiser les traces.

### Fichiers concernes
- `dashboard/sections/tracing.py` : Nouveau module
- `dashboard/sections/__init__.py` : Export
- `dashboard/window.py` : Ajouter onglet

### Composants UI

| Composant | Widget PyQt | Role |
|-----------|-------------|------|
| Arbre + timeline | **QTreeWidget** | Hierarchie des delegations avec colonnes |
| Barre de duree | **QProgressBar** custom | Visualisation relative des durees |
| Panel detail | **QTextEdit** (read-only) | Affichage prompts input/output |
| Layout | **QSplitter** | Arbre a gauche, detail a droite |
| Filtres | **QComboBox** | Selection session, periode |

### Maquette vue principale

```
┌─────────────────────────────────────────────────────────────────────┐
│ Session: [abc123 ▼]  Date: [2026-01-01 ▼]                          │
├─────────────────────────────────────────────────────────────────────┤
│ Agent              │ Duree   │ Tokens │ Status    │ Timeline       │
├─────────────────────────────────────────────────────────────────────┤
│ ▼ coordinateur     │ 45s     │ 12K    │ completed │ ██████████████ │
│   ▼ executeur      │ 20s     │ 5K     │ completed │ ████████░░░░░░ │
│     └ tester       │ 8s      │ 2K     │ completed │ ███░░░░░░░░░░░ │
│   └ executeur      │ 15s     │ 4K     │ completed │ ██████░░░░░░░░ │
└─────────────────────────────────────────────────────────────────────┘
```

### Maquette panel detail

```
┌─ Trace Details ─────────────────────────────────────────┐
│ Agent: tester                                           │
│ Duration: 8s | Tokens: 2K in / 1K out                   │
├─────────────────────────────────────────────────────────┤
│ ▼ Prompt Input                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Ecris les tests unitaires pour le module...        │ │
│ └─────────────────────────────────────────────────────┘ │
│ ▼ Prompt Output                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ J'ai cree 15 tests couvrant les cas suivants...    │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Interactions

- **Expand/collapse** : Click sur fleche pour deployer/replier
- **Selection** : Click sur ligne = affiche details dans panel droit
- **Double-click** : Ouvre la session dans iTerm (comme plan-25)
- **Filtrage** : Combobox session + selecteur date

### Checklist 20.3
- [ ] Nouvelle section `dashboard/sections/tracing.py`
- [ ] Export dans `sections/__init__.py`
- [ ] Onglet "Traces" dans la navigation (`window.py`)
- [ ] QTreeWidget avec colonnes (Agent, Duree, Tokens, Status)
- [ ] Widget custom pour barre de duree (Timeline)
- [ ] QSplitter horizontal (arbre | detail)
- [ ] Panel detail avec QTextEdit read-only
- [ ] Sections collapsibles pour prompts (input/output)
- [ ] Click = affiche details
- [ ] Double-click = ouvre iTerm
- [ ] Combobox selection session
- [ ] Filtrage par date
- [ ] Refresh automatique des donnees
