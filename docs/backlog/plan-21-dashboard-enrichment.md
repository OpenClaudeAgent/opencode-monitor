# Plan 21 - Dashboard Enrichment (HTML Report Migration)

## Contexte

Le rapport HTML genere par le module analytics contient de nombreuses informations riches qui ne sont pas encore presentes dans le dashboard PyQt :
- Delegation Analytics (metriques globales)
- Agent Architecture (roles: orchestrator, hub, worker)
- Delegation Flow (patterns parent -> child)
- Top Delegation Chains
- Skills by Agent
- Sessions with Multiple Delegations
- Hourly Heatmap
- Anomalies Detected

Le dashboard actuel se limite aux metriques de base (sessions, messages, tokens, cache hit) et aux listes d'agents/tools/skills.

## Objectif

Enrichir le dashboard PyQt avec les donnees avancees du rapport HTML, en privilegiant les visualisations les plus utiles pour le monitoring quotidien.

## Comportement attendu

### Section Analytics enrichie

L'utilisateur voit dans la section Analytics :

**Metriques de delegation** (cards supplementaires ou sous-section)
- Total Delegations
- Sessions with Delegations
- Unique Patterns
- Recursive %
- Max Depth

**Agent Roles** (nouvelle table)
- Colonne Agent
- Colonne Role (orchestrator/hub/worker) avec badge colore
- Colonne Sent (delegations envoyees)
- Colonne Received (delegations recues)
- Colonne Tokens/Task

**Delegation Flow** (nouvelle table)
- From -> To -> Count -> Tokens
- Top 10 patterns les plus frequents

**Agent Chains** (nouvelle table ou liste)
- Chain (ex: "executeur -> tester -> refactoring")
- Depth
- Occurrences

### Section Security enrichie

**Anomalies** (nouvelle sous-section)
- Liste des anomalies detectees
- Sessions avec trop de task calls
- Tools avec taux d'echec eleve

### Navigation

Possibilite d'ajouter des onglets ou accordeons dans les sections existantes pour ne pas surcharger l'interface.

## Specifications

_A completer par l'Executeur lors de l'implementation_

### Elements a migrer (par priorite)

| Priorite | Element | Section cible | Complexite |
|----------|---------|---------------|------------|
| 1 | Delegation Metrics | Analytics | Faible |
| 2 | Agent Roles | Analytics | Moyenne |
| 3 | Delegation Flow | Analytics | Moyenne |
| 4 | Agent Chains | Analytics | Faible |
| 5 | Anomalies | Security | Faible |
| 6 | Skills by Agent | Analytics | Faible |
| 7 | Hourly Heatmap | Analytics | Elevee |

### Donnees deja disponibles

Les queries existent dans `analytics/queries.py` :
- `_get_delegation_metrics()` -> DelegationMetrics
- `_get_agent_roles()` -> list[AgentRole]
- `_get_delegation_patterns()` -> list[DelegationPattern]
- `_get_agent_chains()` -> list[AgentChain]
- `_get_anomalies()` -> list[str]
- `_get_skills_by_agent()` -> list[SkillByAgent]
- `_get_hourly_delegations()` -> list[HourlyDelegations]

## Checklist de validation

- [ ] Delegation Metrics affiches dans Analytics
- [ ] Table Agent Roles avec badges de role
- [ ] Table Delegation Flow (top patterns)
- [ ] Table/Liste Agent Chains
- [ ] Section Anomalies dans Security
- [ ] Skills by Agent table
- [ ] UI responsive et non surchargee
- [ ] Donnees mises a jour avec le refresh
- [ ] Tests pour les nouveaux widgets
