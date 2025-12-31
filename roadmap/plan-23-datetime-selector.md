# Plan 23 - DateTime Range Selector

## Contexte

Le panel Analytics permet de filtrer par periodes predefinies (24h, 7d, 30d) via un `SegmentedControl`. Pour des analyses plus fines, il serait utile de pouvoir specifier une plage de dates/heures personnalisee.

## Objectif

Ajouter un selecteur de plage date/heure personnalisee dans le dashboard Analytics.

## Comportement attendu

### Interface

Le `SegmentedControl` actuel (24h | 7d | 30d) est etendu avec une option "Custom" :
- `24h | 7d | 30d | Custom`

Quand "Custom" est selectionne :
- Un panneau s'affiche avec deux selecteurs date/heure
- **From** : date de debut (jour/mois/annee + heure:minute)
- **To** : date de fin (jour/mois/annee + heure:minute)
- Bouton "Apply" pour valider la selection

### Format d'affichage

- Format : `dd/MM/yyyy HH:mm`
- Exemple : `31/12/2025 14:30`

### Valeurs par defaut

- From : maintenant - 24h
- To : maintenant

### Cas d'usage

- Analyser une session specifique qui a eu lieu entre 10h et 12h
- Comparer l'activite de deux jours specifiques
- Investiguer un incident a une heure precise
- Generer un rapport pour une periode precise (ex: sprint de 2 semaines)

### Comportement

- Les presets (24h, 7d, 30d) masquent le picker et utilisent des dates calculees
- "Custom" affiche le picker et utilise les dates selectionnees
- Le changement de date declenche un refresh des donnees
- La plage selectionnee est persistee (optionnel) pour ne pas la perdre en changeant d'onglet

## Specifications

_A completer par l'Executeur_

### Composant PyQt

`DateTimeRangeSelector` :
- Deux `QDateTimeEdit` pour From et To
- Format d'affichage configurable
- Bouton "Apply"
- Signal `range_changed(start: datetime, end: datetime)`

### Integration

- Modifier `SegmentedControl` pour supporter un mode "Custom"
- Ou creer un nouveau widget qui combine `SegmentedControl` + `DateTimeRangeSelector`
- Connecter le signal au refresh des donnees Analytics

## Checklist de validation

- [ ] Composant `DateTimeRangeSelector` cree
- [ ] Integration avec le selecteur de periode existant
- [ ] Selection date de debut (jour/mois/annee heure:minute)
- [ ] Selection date de fin (jour/mois/annee heure:minute)
- [ ] Bouton Apply fonctionnel
- [ ] Donnees filtrees correctement sur plage custom
- [ ] Retour aux presets (24h, 7d, 30d) fonctionne
- [ ] UI responsive et intuitive
- [ ] Tests pour le nouveau composant
