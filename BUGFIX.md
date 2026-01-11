# Bugfix: Timeline vide dans le dashboard

## Problème

Après implémentation de la pagination, la timeline ne s'affichait plus dans le dashboard quand on sélectionnait une trace.

## Cause

Les endpoints de pagination avaient des limites **par défaut** obligatoires :
- `/api/session/<id>/timeline/full` : limit=100 par défaut
- `/api/session/<id>/messages` : limit=100 par défaut  
- `/api/session/<id>/exchanges` : limit=50 par défaut

Le dashboard appelait ces endpoints **sans passer le paramètre `limit`**, donc recevait seulement les 50-100 premiers items, tronquant les données.

## Solution

Rendu le paramètre `limit` **optionnel** pour tous les endpoints :

- **Si `limit` n'est pas fourni** → Comportement original (pas de limite, tous les résultats)
- **Si `limit` est fourni** → Pagination appliquée avec la limite spécifiée

### Changements

**Endpoints modifiés** :

1. `GET /api/session/<id>/timeline/full`
   - Avant : `limit=100` par défaut (IMPOSÉ)
   - Après : `limit=None` par défaut (OPTIONNEL)
   - Max si fourni : 5000

2. `GET /api/session/<id>/messages`
   - Avant : `limit=100` par défaut (IMPOSÉ)
   - Après : `limit=None` par défaut (OPTIONNEL)
   - Max si fourni : 5000

3. `GET /api/session/<id>/exchanges`
   - Avant : `limit=50` par défaut (IMPOSÉ)
   - Après : `limit=None` par défaut (OPTIONNEL)
   - Max si fourni : 1000

**Logique SQL** :

```python
if limit is None:
    # Pas de LIMIT dans la query
    query = "SELECT ... ORDER BY ..."
    results = conn.execute(query, [session_id]).fetchall()
else:
    # LIMIT + OFFSET appliqués
    query = "SELECT ... ORDER BY ... LIMIT ? OFFSET ?"
    results = conn.execute(query, [session_id, limit, offset]).fetchall()
```

## Rétrocompatibilité

✅ **Complète** - Tous les appels existants continuent de fonctionner :
- Dashboard (ne passe pas `limit`) → Reçoit tout
- Appels futurs avec pagination explicite → Limite appliquée

## Exemple d'usage

```python
# Sans pagination (comportement par défaut)
GET /api/session/abc123/timeline/full
# → Renvoie TOUS les événements

# Avec pagination explicite
GET /api/session/abc123/timeline/full?limit=100
# → Renvoie 100 premiers événements

GET /api/session/abc123/timeline/full?limit=200&offset=100
# → Renvoie événements 101-300
```

## Test de validation

1. ✅ Dashboard timeline s'affiche correctement
2. ✅ Pas de troncature des données
3. ✅ Pagination fonctionne quand explicitement demandée
4. ✅ Aucune erreur LSP

## Fichiers modifiés

- `src/opencode_monitor/api/routes/sessions.py` - 3 endpoints
- `src/opencode_monitor/analytics/tracing/session_queries.py` - 3 méthodes
