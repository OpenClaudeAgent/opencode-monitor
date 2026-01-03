# Plan 37 - API Consolidation

## Contexte

L'analyse de l'API (`server.py`) a revele des inconsistances :

### Endpoints utilisant SQL direct vs TracingDataService

| Endpoint | Methode | Probleme |
|----------|---------|----------|
| `/api/sessions` | SQL direct (L220) | Devrait utiliser service |
| `/api/traces` | SQL direct (L267) | Devrait utiliser service |
| `/api/delegations` | SQL direct (L329) | Devrait utiliser service |
| Autres | `self._get_service()` | OK |

### Problemes identifies

1. **Duplication de logique** : Le meme SQL est potentiellement ecrit a plusieurs endroits
2. **Maintenance difficile** : Modifier une requete necessite de chercher partout
3. **Inconsistance** : Format de reponse peut varier
4. **Pas de pagination** : Endpoints lourds retournent tout

### Endpoints manquants

- Recherche full-text sur sessions
- Details d'un trace specifique
- Stats journalieres agregees
- Health check detaille

## Objectif

Centraliser toutes les requetes SQL dans TracingDataService et ajouter les endpoints manquants.

## Comportement attendu

### 1. Migration des endpoints existants

**Avant** (`server.py`) :
```python
@self._app.route("/api/sessions", methods=["GET"])
def get_sessions():
    rows = conn.execute("SELECT ... FROM sessions ...").fetchall()
    # Processing manuel
```

**Apres** :
```python
@self._app.route("/api/sessions", methods=["GET"])
def get_sessions():
    service = self._get_service()
    return jsonify(service.get_sessions_list(days=days, limit=limit))
```

### 2. Nouveaux endpoints

| Endpoint | Description | Parametres |
|----------|-------------|------------|
| `GET /api/sessions/search` | Recherche full-text | `q`, `limit` |
| `GET /api/trace/<id>` | Details d'un trace | - |
| `GET /api/stats/daily` | Stats par jour | `days` |
| `GET /api/health/detailed` | Metriques internes | - |
| `GET /api/session/<id>/cost` | Cout detaille | - |

### 3. Pagination

Tous les endpoints de liste supportent :
- `page` : Numero de page (defaut 1)
- `per_page` : Elements par page (defaut 50, max 200)
- Header `X-Total-Count` dans la reponse

### 4. Format de reponse standardise

```json
{
  "success": true,
  "data": [...],
  "meta": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

## Specifications

### Nouvelles methodes TracingDataService

```python
def get_sessions_list(
    self, 
    days: int = 30, 
    limit: int = 100,
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None
) -> dict:
    """Get paginated list of sessions.
    
    Args:
        days: Filter sessions from last N days
        limit: Maximum total results
        page: Page number (1-based)
        per_page: Results per page
        search: Optional search query for title/directory
        
    Returns:
        Dict with data, meta (pagination info)
    """
    ...

def get_traces_list(
    self,
    days: int = 30,
    limit: int = 500,
    page: int = 1,
    per_page: int = 50
) -> dict:
    """Get paginated list of traces."""
    ...

def get_delegations_list(
    self,
    days: int = 30,
    limit: int = 1000,
    page: int = 1,
    per_page: int = 50
) -> dict:
    """Get paginated list of delegations."""
    ...

def get_trace_details(self, trace_id: str) -> dict:
    """Get full details of a specific trace."""
    ...

def get_daily_stats(self, days: int = 7) -> list[dict]:
    """Get aggregated stats per day."""
    ...

def search_sessions(self, query: str, limit: int = 20) -> list[dict]:
    """Search sessions by title or directory."""
    ...

def get_session_cost_breakdown(self, session_id: str) -> dict:
    """Get detailed cost breakdown for a session."""
    ...
```

### Nouveaux endpoints server.py

```python
@self._app.route("/api/sessions/search", methods=["GET"])
def search_sessions():
    """Search sessions by title/directory."""
    try:
        q = request.args.get("q", "")
        limit = request.args.get("limit", 20, type=int)
        
        with self._db_lock:
            service = self._get_service()
            results = service.search_sessions(q, limit)
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@self._app.route("/api/trace/<trace_id>", methods=["GET"])
def get_trace_details(trace_id: str):
    """Get details of a specific trace."""
    try:
        with self._db_lock:
            service = self._get_service()
            data = service.get_trace_details(trace_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@self._app.route("/api/stats/daily", methods=["GET"])
def get_daily_stats():
    """Get daily aggregated statistics."""
    try:
        days = request.args.get("days", 7, type=int)
        
        with self._db_lock:
            service = self._get_service()
            data = service.get_daily_stats(days)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@self._app.route("/api/health/detailed", methods=["GET"])
def health_detailed():
    """Detailed health check with metrics."""
    try:
        with self._db_lock:
            db = get_analytics_db()
            stats = db.get_stats()
            db_path = db._db_path
            db_size = db_path.stat().st_size if db_path.exists() else 0
            
        return jsonify({
            "success": True,
            "data": {
                "status": "ok",
                "service": "analytics-api",
                "database": {
                    "path": str(db_path),
                    "size_bytes": db_size,
                    "size_mb": round(db_size / 1024 / 1024, 2),
                    "tables": stats
                }
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@self._app.route("/api/session/<session_id>/cost", methods=["GET"])
def get_session_cost(session_id: str):
    """Get detailed cost breakdown for a session."""
    try:
        with self._db_lock:
            service = self._get_service()
            data = service.get_session_cost_breakdown(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

### Documentation API.md

Creer `API.md` avec :
- Liste complete des endpoints
- Parametres et types
- Exemples de reponses
- Codes d'erreur
- Exemples curl

## Checklist de validation

- [ ] `/api/sessions` migre vers TracingDataService
- [ ] `/api/traces` migre vers TracingDataService
- [ ] `/api/delegations` migre vers TracingDataService
- [ ] Endpoint `/api/sessions/search` fonctionnel
- [ ] Endpoint `/api/trace/<id>` fonctionnel
- [ ] Endpoint `/api/stats/daily` fonctionnel
- [ ] Endpoint `/api/health/detailed` fonctionnel
- [ ] Endpoint `/api/session/<id>/cost` fonctionnel
- [ ] Pagination implementee sur endpoints de liste
- [ ] Header X-Total-Count present
- [ ] Tests API pour tous les nouveaux endpoints
- [ ] API.md documente tous les endpoints
- [ ] Aucun SQL direct dans server.py (sauf health)

## Estimation

- **Effort** : Medium (2-3 jours)
- **Risque** : Faible (pas de breaking changes, ajouts)
- **Dependances** : Plan 36 (schema stable pour requetes)
