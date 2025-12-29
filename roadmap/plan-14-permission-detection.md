# Plan 14 - Permission Detection (Heuristique Polling)

## Contexte

OpenCode ne fournit **pas d'API directe** pour savoir si une permission est en attente. Le systeme actuel utilise une **double approche** :

1. **SSE Events** (temps reel, peu fiable) - evenements `permission.*` rarement emis
2. **Heuristique de polling** (fiable, delai 5s) - detection par duree d'execution des tools

L'heuristique est la methode **principale et fiable** car les SSE events `permission.requested` ne sont quasiment jamais emis par OpenCode.

## Objectif

Migrer le mecanisme de detection des permissions vers le backend Python en conservant la fiabilite de l'heuristique actuelle.

## Comportement attendu

Quand un agent OpenCode attend une permission utilisateur (ex: `bash`, `edit`, `write`) :
1. Le systeme detecte qu'un tool est `running` depuis > 5 secondes
2. L'etat `permission_pending: true` est assigne a la session concernee
3. Le compteur global `permissions_pending` est incremente
4. L'UI affiche l'indicateur avec changement de couleur (orange)
5. Quand la permission est accordee/refusee, le tool passe a `completed` et le compteur reset

---

## Specifications Techniques

### API OpenCode utilisee

| Endpoint | Methode | Usage Permission |
|----------|---------|------------------|
| `/session/{id}/message?limit=1` | GET | **Source principale** - Contient les `parts` avec etat des tools |
| `/event` | SSE | Source secondaire - Events `permission.*` (peu fiable) |

### Structure de donnees Tool

```json
{
  "type": "tool",
  "tool": "bash",
  "state": {
    "status": "running | pending | completed",
    "time": {
      "start": 1767022229583,
      "end": null
    }
  }
}
```

### Etats possibles d'un Tool

| Status | start | end | Signification |
|--------|-------|-----|---------------|
| `pending` | null | null | Tool en queue, pas encore execute |
| `running` | timestamp | null | Tool en cours d'execution |
| `completed` | timestamp | timestamp | Tool termine |

### Algorithme de detection (Heuristique)

```
POUR chaque session BUSY:
  message = GET /session/{id}/message?limit=1
  
  POUR chaque part dans message[0].parts:
    SI part.type == "tool" 
       ET part.state.status == "running"
       ET (now_ms - part.state.time.start) > 5000:
      
      -> PERMISSION PENDING DETECTEE
```

### Code source de reference (bash - eventd lignes 144-155)

```bash
local has_permission="false"
if [[ "$ses_status" == "busy" ]]; then
    local msg=$(curl -s "${url}/session/${ses_id}/message?limit=1")
    if [[ -n "$msg" && "$msg" != "null" ]]; then
        local now_ms=$(($(date +%s) * 1000))
        local stuck=$(echo "$msg" | jq -r --argjson now "$now_ms" \
            '.[0].parts[] | select(
                .type == "tool" 
                and .state.status == "running" 
                and (.state.time.start + 5000) < $now
            ) | .tool' | head -1)
        if [[ -n "$stuck" ]]; then
            has_permission="true"
            stuck_tools=$((stuck_tools + 1))
        fi
    fi
fi
```

### SSE Events (secondaire, peu fiable)

| Event | Action | Fiabilite |
|-------|--------|-----------|
| `permission.requested` | Increment counter | Rarement emis |
| `permission.updated` | Increment counter | Rarement emis |
| `permission.replied` | Reset counter = 0 | Parfois emis |
| `session.idle` | Reset counter = 0 | Fiable |

---

## State Machine - Permission Detection

```
                          Session Status
                               |
                               v
                    +---------------------+
                    |   session.status    |
                    |      == "idle"      |
                    +----------+----------+
                               |
              +----------------+----------------+
              | YES                             | NO
              v                                 v
     +-----------------+              +-----------------+
     |      IDLE       |              |      BUSY       |
     |                 |              |                 |
     | permission = 0  |              | Check tools...  |
     +-----------------+              +--------+--------+
                                               |
                                               v
                                    +---------------------+
                                    |  GET /session/{id}/ |
                                    |  message?limit=1    |
                                    +----------+----------+
                                               |
                                               v
                                    +---------------------+
                                    |  For each tool part |
                                    |  in message.parts   |
                                    +----------+----------+
                                               |
                          +--------------------+--------------------+
                          |                                         |
                          v                                         v
               +---------------------+                   +---------------------+
               | tool.status ==      |                   | tool.status !=      |
               | "running"           |                   | "running"           |
               +----------+----------+                   +----------+----------+
                          |                                         |
                          v                                         |
               +---------------------+                              |
               | elapsed =           |                              |
               | now - tool.start    |                              |
               +----------+----------+                              |
                          |                                         |
              +-----------+-----------+                             |
              |                       |                             |
              v                       v                             |
    +------------------+   +------------------+                     |
    | elapsed > 5000ms |   | elapsed <= 5000ms|                     |
    +--------+---------+   +--------+---------+                     |
             |                      |                               |
             v                      |                               |
    +------------------+            |                               |
    |   PERMISSION     |            |                               |
    |    PENDING       |            |                               |
    |                  |            |                               |
    | permission = 1   |            |                               |
    | indicator shown  |            |                               |
    | color = orange   |            |                               |
    +--------+---------+            |                               |
             |                      |                               |
             +----------------------+-------------------------------+
                                    |
                                    v
                         +---------------------+
                         |  Continue polling   |
                         |  (next cycle)       |
                         +---------------------+
```

### Permission Reset Triggers

```
    +------------------+
    |   PERMISSION     |
    |    PENDING       |
    +--------+---------+
             |
             |  Reset when ANY of:
             |
             +------------------------------------------------------+
             |                                                      |
             v                                                      v
    +------------------+                              +------------------+
    | tool.status      |                              | SSE Event:       |
    | changes to       |                              | session.idle     |
    | "completed"      |                              | OR               |
    |                  |                              | permission.replied|
    | (detected via    |                              |                  |
    |  next poll)      |                              | (if received)    |
    +--------+---------+                              +--------+---------+
             |                                                  |
             +----------------------+---------------------------+
                                    |
                                    v
                         +---------------------+
                         |   PERMISSION = 0    |
                         |   indicator removed |
                         |   color = normal    |
                         +---------------------+
```

---

## Sous-taches d'implementation

| # | Sous-tache | Description | Dependances |
|---|------------|-------------|-------------|
| 1.1 | API Client | Classe pour appeler `/session/{id}/message` | Aucune |
| 1.2 | Tool Parser | Parser les `parts` et extraire tools avec status | 1.1 |
| 1.3 | Heuristique | Logique `elapsed > 5000ms` = permission pending | 1.2 |
| 1.4 | SSE Listener | Ecouter `permission.*` events (backup) | Aucune |
| 1.5 | State Aggregator | Combiner heuristique + SSE, compteur global | 1.3, 1.4 |
| 1.6 | Reset Logic | Detecter `completed` ou `session.idle` -> reset | 1.5 |

## Priorite des sous-taches

```
    1.1 API Client ------+
                         +---> 1.2 Tool Parser ---> 1.3 Heuristique ---+
    1.4 SSE Listener ----+                                             +---> 1.5 State Aggregator ---> 1.6 Reset Logic
```

---

## Checklist de validation

### Detection
- [x] Un tool `bash` running > 5s declenche `may_need_permission = true`
- [x] Un tool `edit` running > 5s declenche `may_need_permission = true`
- [x] Un tool running < 5s ne declenche PAS de permission
- [x] Tool `task` exclu de la detection (sub-agents longs)
- [N/A] Le compteur global `permissions_pending` - Non implemente (decision: eviter confusion avec todos)

### Reset
- [x] Quand le tool passe a `completed`, il n'apparait plus (detection automatique au prochain poll)
- [x] Quand la session passe a `idle`, plus de tools running
- [N/A] SSE event `permission.replied` - Non implemente (polling seul)

### Multi-instance
- [x] Plusieurs instances OpenCode avec permissions simultanees sont correctement detectees
- [x] Chaque tool a son propre flag `may_need_permission`

### Edge cases
- [x] Tool avec `start: null` (pending) ne trigger pas de faux positif (elapsed_ms = 0)
- [x] Seuil configurable dans Settings (defaut 5s)
- [x] Affichage lisible pour durees > 60s (format "1m 30s")

---

## Notes d'implementation Python

### Pseudo-code heuristique

```python
import time

PERMISSION_THRESHOLD_MS = 5000

def detect_permission(session_id: str, api_client) -> bool:
    """Detecte si une session attend une permission."""
    message = api_client.get_last_message(session_id)
    if not message or not message.get('parts'):
        return False
    
    now_ms = int(time.time() * 1000)
    
    for part in message['parts']:
        if part.get('type') != 'tool':
            continue
        
        state = part.get('state', {})
        if state.get('status') != 'running':
            continue
        
        start_time = state.get('time', {}).get('start')
        if start_time is None:
            continue
        
        elapsed = now_ms - start_time
        if elapsed > PERMISSION_THRESHOLD_MS:
            return True
    
    return False
```

### Classe PermissionDetector suggeree

```python
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class PermissionState:
    session_id: str
    permission_pending: bool
    tool_name: Optional[str] = None
    elapsed_ms: int = 0

class PermissionDetector:
    THRESHOLD_MS = 5000
    
    def __init__(self, api_client):
        self.api_client = api_client
        self._previous_count = 0
    
    def check_session(self, session_id: str, session_status: str) -> PermissionState:
        """Verifie si une session a une permission en attente."""
        if session_status != "busy":
            return PermissionState(session_id=session_id, permission_pending=False)
        
        message = self.api_client.get_last_message(session_id)
        if not message:
            return PermissionState(session_id=session_id, permission_pending=False)
        
        now_ms = int(time.time() * 1000)
        
        for part in message.get('parts', []):
            if part.get('type') != 'tool':
                continue
            
            state = part.get('state', {})
            if state.get('status') != 'running':
                continue
            
            start_time = state.get('time', {}).get('start')
            if start_time is None:
                continue
            
            elapsed = now_ms - start_time
            if elapsed > self.THRESHOLD_MS:
                return PermissionState(
                    session_id=session_id,
                    permission_pending=True,
                    tool_name=part.get('tool'),
                    elapsed_ms=elapsed
                )
        
        return PermissionState(session_id=session_id, permission_pending=False)
    
    def check_all_sessions(self, sessions: dict) -> tuple[int, list[PermissionState]]:
        """Verifie toutes les sessions et retourne le compteur global."""
        states = []
        for session_id, session_info in sessions.items():
            state = self.check_session(session_id, session_info.get('type', 'idle'))
            states.append(state)
        
        pending_count = sum(1 for s in states if s.permission_pending)
        return pending_count, states
```

### Points d'attention

| Point | Detail |
|-------|--------|
| Timestamp | OpenCode utilise des timestamps **millisecondes**, pas secondes |
| Polling interval | Recommande 2-3s pour balance reactivite/charge |
| SSE backup | Ne pas dependre uniquement des events `permission.*` |
| Debounce | Eviter refresh UI trop frequent (min 2s entre refreshs) |
| Thread safety | Si multi-thread, proteger l'acces au compteur global |

---

## Fichiers source de reference

| Fichier | Chemin | Lignes cles |
|---------|--------|-------------|
| Event Daemon | `~/.local/bin/opencode-eventd` | 144-155 (heuristique), 244-253 (SSE events) |
| SwiftBar Plugin | `~/Library/Application Support/SwiftBar/Plugins/opencode.2s.sh` | 86, 147-151, 208-228 |
| State File | `/tmp/opencode-state.json` | Structure JSON avec `permissions_pending` |
