# Plan 31 - Tracing UX Refinement

## Contexte

L'interface de tracing présente des problèmes d'ergonomie qui nuisent à l'expérience utilisateur :

1. **Menu confus** : Les contrôles en haut à droite ("All Sessions" dropdown et "View: Sessions/Traces" toggle) ne sont pas clairs :
   - "All Sessions" ne semble pas fonctionner (pas de filtrage visible)
   - "View: Sessions" vs "View: Traces" - la différence n'est pas évidente
   - L'utilisateur ne comprend pas à quoi servent ces contrôles

2. **Chevrons non visibles** : L'arbre utilise des indicateurs bleus peu visibles pour expand/collapse. Le CSS actuel supprime les flèches natives (`image: none`) sans fournir d'alternative claire. L'utilisateur ne sait pas qu'il peut déplier les éléments.

## Objectif

Améliorer l'ergonomie de la section Tracing :
- Clarifier ou supprimer les contrôles inutiles
- Rendre l'arbre clairement navigable avec des chevrons visibles

## Comportement attendu

### Clarification du menu

**Option A - Simplification** :
- Supprimer le dropdown "All Sessions" s'il n'apporte pas de valeur
- Renommer "View: Sessions" → "📁 Hiérarchie" (vue par session/projet)
- Renommer "View: Traces" → "📊 Chronologie" (vue flat des traces)
- Ajouter un tooltip explicatif sur le toggle

**Option B - Fonctionnalité complète** :
- Faire fonctionner "All Sessions" comme filtre réel
- Quand une session est sélectionnée, n'afficher que ses traces
- Ajouter un indicateur visuel du filtre actif

### Chevrons de l'arbre

- Ajouter des chevrons visibles (▶ fermé, ▼ ouvert) avant chaque élément parent
- Les chevrons doivent être cliquables pour expand/collapse
- Couleur contrastée avec le texte (ex: couleur accent ou text_secondary)
- Animation fluide lors de l'ouverture/fermeture
- Le chevron doit être visible même sans hover

### Améliorations visuelles complémentaires

- Indentation claire entre niveaux (20px minimum, déjà en place)
- Ligne de connexion optionnelle entre parent et enfants
- Hover state distinct sur les lignes cliquables

## Checklist de validation

- [ ] Les chevrons ▶/▼ sont visibles sur tous les éléments avec enfants
- [ ] Cliquer sur un chevron expand/collapse l'élément
- [ ] Le toggle de vue a des labels clairs et compréhensibles
- [ ] Un tooltip explique la différence entre les deux vues
- [ ] Le dropdown "All Sessions" fonctionne OU est supprimé
- [ ] L'arbre reste lisible avec 3+ niveaux de profondeur
- [ ] Les animations sont fluides (pas de saccades)
