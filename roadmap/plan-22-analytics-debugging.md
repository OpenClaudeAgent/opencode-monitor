# Plan 22 - Analytics Debugging (Date Filtering Fix)

## Contexte

Le panel Analytics du dashboard affiche des donnees qui ne respectent pas le filtrage par date. Par exemple, en selectionnant "24h", des skills supprimes la veille apparaissent encore.

Apres analyse du code `analytics/queries.py`, le probleme est identifie :

**Bug confirme** : Les requetes pour `tools` et `skills` ne filtrent PAS par date :
- `_get_tool_stats()` (ligne 216) : "Note: created_at may be NULL, so we don't filter by date for now"
- `_get_skill_stats()` (ligne 246) : "Note: loaded_at may be NULL, so we don't filter by date for now"

D'autres requetes comme `_get_skills_by_agent()` ne filtrent pas non plus par date.

## Objectif

Corriger le filtrage par date dans toutes les requetes analytics pour que les donnees affichees correspondent a la periode selectionnee.

## Comportement attendu

### Filtrage par date

Quand l'utilisateur selectionne "24h" :
- Seules les sessions creees dans les dernieres 24h sont comptees
- Seuls les messages de ces sessions sont inclus
- Seuls les tools invoques dans cette periode sont listes
- Seuls les skills charges dans cette periode sont listes

### Coherence des donnees

Les totaux affiches dans les cards doivent correspondre aux details des tables :
- Si "Sessions: 5", la table Top Sessions montre max 5 sessions
- Si "Tokens: 100K", c'est la somme des tokens des sessions de la periode

### Refresh des donnees

Apres un refresh, les donnees obsoletes disparaissent si elles sont hors de la periode selectionnee.

## Specifications

### Requetes a corriger

| Methode | Probleme | Correction |
|---------|----------|------------|
| `_get_tool_stats()` | Pas de filtre date | Joindre avec messages pour filtrer |
| `_get_skill_stats()` | Pas de filtre date | Filtrer sur loaded_at ou joindre sessions |
| `_get_skills_by_agent()` | Pas de filtre date | Ajouter WHERE sur dates |

### Verification du modele

1. **Table `parts`** : Verifier que `created_at` est bien peuple lors de l'import
2. **Table `skills`** : Verifier que `loaded_at` est bien peuple
3. **Relations** : Verifier les jointures sessions -> messages -> parts/skills

### Requetes SQL corrigees

```sql
-- Tools avec filtre date (via messages)
SELECT
    p.tool_name,
    COUNT(*) as invocations,
    SUM(CASE WHEN p.tool_status = 'error' THEN 1 ELSE 0 END) as failures
FROM parts p
JOIN messages m ON p.message_id = m.id
WHERE m.created_at >= ? AND m.created_at <= ?
    AND p.tool_name IS NOT NULL
GROUP BY p.tool_name
ORDER BY invocations DESC
LIMIT 15

-- Skills avec filtre date (via messages)
SELECT
    s.skill_name,
    COUNT(*) as load_count
FROM skills s
JOIN messages m ON s.message_id = m.id
WHERE m.created_at >= ? AND m.created_at <= ?
    AND s.skill_name IS NOT NULL
GROUP BY s.skill_name
ORDER BY load_count DESC
```

### Tests de regression

Creer des tests qui verifient :
- Skills charges il y a 2 jours n'apparaissent pas dans "24h"
- Tools utilises il y a 2 jours n'apparaissent pas dans "24h"
- Coherence entre totaux et details

## Checklist de validation

- [ ] Bug reproduit avec test
- [ ] `_get_tool_stats()` corrige avec filtre date
- [ ] `_get_skill_stats()` corrige avec filtre date
- [ ] `_get_skills_by_agent()` corrige avec filtre date
- [ ] Verification que `created_at` est peuple dans parts
- [ ] Verification que `loaded_at` est peuple dans skills
- [ ] Tests de regression ajoutes
- [ ] Dashboard affiche donnees coherentes avec periode
- [ ] Aucune regression sur les autres requetes
