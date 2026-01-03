# Sprints - OpenCode Monitor

## Configuration

- **Cycle actif** : A (Qualite-First)
- **Duree sprint** : 2 semaines
- **Date debut** : 2026-01-06

## Cycle A : Qualite-First

```
Phase 1: Bugfix     -> Phase 2: E2E Tests -> Phase 3: Refactoring -> Phase 4: Features
```

---

## Sprint 01 - Data Enrichment (2026-01-06 → 2026-01-17)

### Objectif
Exploiter 100% des donnees disponibles dans OpenCode storage et consolider le schema.

### Phase 1 : Chargement donnees (Semaine 1)

| Jour | Plan | Taches | Statut |
|------|------|--------|--------|
| Lun | 35 | load_todos(), load_projects(), tests | En attente |
| Mar | 34 | Schema parts enrichi, load reasoning | En attente |
| Mer | 34 | load step-finish, load patch | En attente |
| Jeu | 34 | Queries + TracingDataService | En attente |
| Ven | 34 | API endpoints + tests | En attente |

### Phase 2 : Consolidation (Semaine 2)

| Jour | Plan | Taches | Statut |
|------|------|--------|--------|
| Lun | 36 | Remplir colonnes mortes (parts) | En attente |
| Mar | 36 | Migration script, is_root, project_name | En attente |
| Mer | 37 | Migrer 3 endpoints vers TracingDataService | En attente |
| Jeu | 37 | Nouveaux endpoints (search, cost, daily) | En attente |
| Ven | 37 | Documentation API.md, tests finaux | En attente |

### Plans inclus

| # | Plan | Type | Priorite | Dependances |
|---|------|------|----------|-------------|
| 35 | Todos & Projects Loading | Feature | P0 | - |
| 34 | Parts Enrichment | Feature | P0 | - |
| 36 | Schema Cleanup | Refactoring | P1 | 34 |
| 37 | API Consolidation | Refactoring | P1 | 36 |

### Metriques de succes

| Metrique | Avant | Cible | Actuel |
|----------|-------|-------|--------|
| Types parts charges | 2/7 (29%) | 7/7 (100%) | - |
| Fichiers todo charges | 0/88 | 88/88 | - |
| Fichiers project charges | 0/5 | 5/5 | - |
| Colonnes mortes | 9 | 0 | - |
| Endpoints via Service | 70% | 100% | - |
| Couverture tests | ~85% | >90% | - |

### Risques

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Migration DB casse donnees | Faible | Haut | Backup avant, script rollback |
| Performance degradee avec nouvelles tables | Moyen | Moyen | Indexes, batch inserts |
| Breaking changes API | Faible | Moyen | Versionner si necessaire |

---

## Backlog Sprints Futurs

### Sprint 02 (Prevu)
- Plan 33 : Integration Tests infrastructure
- Plan 32 : Tracing Datadog Vision (Phase 1)
- Plan 21 : Dashboard Enrichment

### Sprint 03 (Prevu)
- Plan 23 : DateTime Range Selector
- Plan 18 : OpenCode Hooks (si API disponible)

---

## Historique

| Sprint | Dates | Plans | Statut |
|--------|-------|-------|--------|
| Sprint 01 | 2026-01-06 → 2026-01-17 | 34, 35, 36, 37 | En attente |

---

## Notes

### Regles de sprint
1. Un plan ne peut etre deplace en cours de sprint qu'avec validation utilisateur
2. Les dependances sont respectees (Plan 36 attend Plan 34)
3. Les tests sont obligatoires avant merge
4. Review de fin de sprint avec metriques

### Definition of Done
- [ ] Code implemente et teste
- [ ] Tests unitaires passent (>80% coverage)
- [ ] Documentation mise a jour
- [ ] Pas de regression
- [ ] Review par agent Quality
