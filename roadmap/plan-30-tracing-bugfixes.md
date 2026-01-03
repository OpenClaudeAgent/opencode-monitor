# Plan 30 - Tracing Bugfixes

## Contexte

La section Tracing du dashboard PyQt présente plusieurs bugs critiques qui rendent l'interface difficilement utilisable :

1. **User Prompt incorrect** : Quand on clique sur une session ROOT, le panneau de détail affiche "new session" ou un texte générique au lieu du vrai prompt utilisateur. Le prompt devrait montrer la première question/demande de l'utilisateur.

2. **Flickering UI constant** : L'interface alterne sans cesse entre "No traces found" et l'affichage des traces. Ce comportement rend la lecture impossible et suggère un problème de synchronisation ou de comparaison des données.

3. **Traces récentes sans exécution** : Certaines traces récentes apparaissent dans l'arbre mais n'affichent aucune donnée d'exécution (durée, tokens, status) en dessous. Cela indique un problème de jointure ou de récupération des données.

## Objectif

Corriger les 3 bugs critiques pour rendre la section Tracing stable et utilisable :
- Afficher le vrai prompt utilisateur pour les sessions ROOT
- Éliminer le flickering lors des refreshs
- Garantir que toutes les traces affichées ont leurs données d'exécution

## Comportement attendu

### Bug 1 - User Prompt
- Quand l'utilisateur clique sur une session ROOT (icône 🌳), le panneau de détail affiche :
  - Section "💬 User Prompt" avec le premier message de l'utilisateur
  - Si pas de prompt trouvé, afficher "(No prompt recorded)" plutôt qu'un texte trompeur
- Le prompt doit correspondre à ce que l'utilisateur a réellement demandé dans cette session

### Bug 2 - Flickering UI
- L'arbre des traces ne doit se reconstruire QUE si les données ont réellement changé
- Pas de flash "No traces found" entre deux refreshs
- La sélection actuelle doit être préservée après un refresh
- Le scroll position doit être maintenu

### Bug 3 - Traces sans exécution
- Chaque trace affichée dans l'arbre doit avoir ses métriques visibles (durée, tokens, status)
- Si une trace n'a pas de données, elle doit être clairement marquée comme "En cours" ou "Incomplète"
- Les traces orphelines (sans session parente valide) doivent être gérées proprement

## Checklist de validation

- [ ] Cliquer sur une session ROOT affiche le vrai user prompt
- [ ] Le panneau de détail n'affiche plus "new session" de manière incorrecte
- [ ] Aucun flickering visible pendant 30 secondes d'observation
- [ ] La sélection dans l'arbre est préservée après refresh
- [ ] Toutes les traces récentes affichent leurs métriques
- [ ] Les traces "en cours" sont visuellement distinctes
- [ ] Tests unitaires ajoutés pour les queries corrigées
