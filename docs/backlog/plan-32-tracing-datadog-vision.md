# Plan 32 - Tracing Datadog-style Vision

## Contexte

L'interface de tracing actuelle permet de visualiser les traces d'exécution des agents, mais reste basique comparée aux outils professionnels de tracing distribué comme Datadog APM. L'utilisateur souhaite une expérience de navigation plus riche pour comprendre comment son orchestration d'agents fonctionne.

Points d'inspiration Datadog (sans mention dans le code) :
- Navigation fluide dans les traces avec fil d'Ariane
- Vue waterfall/timeline des exécutions parallèles
- Détails enrichis avec métriques, tags, et contexte
- Filtres et recherche avancés
- Visualisation des dépendances entre agents

## Objectif

Transformer la section Tracing en un outil d'observabilité complet pour les orchestrations d'agents IA :
- Navigation intuitive dans les hiérarchies complexes
- Visualisation temporelle des exécutions
- Détails riches et contextuels pour chaque trace
- Capacités de recherche et filtrage avancées

## Comportement attendu

### 1. Navigation avec Breadcrumb

- Fil d'Ariane en haut du panneau de détail : `ROOT > coordinateur > executeur > tester`
- Chaque élément du breadcrumb est cliquable pour remonter dans la hiérarchie
- Affiche le chemin complet de délégation depuis la session racine

### 2. Vue Timeline/Waterfall

- Nouvelle vue "Timeline" en plus de "Hiérarchie" et "Chronologie"
- Affiche les traces sur un axe temporel horizontal
- Barres proportionnelles à la durée de chaque trace
- Traces parallèles empilées verticalement
- Couleurs par type d'agent ou status
- Zoom in/out sur la timeline
- Survol affiche un tooltip avec durée et tokens

### 3. Panneau de Détails Enrichi

Quand une trace est sélectionnée :

**Section Métriques** :
- Durée (avec comparaison à la moyenne)
- Tokens in/out (avec graphique de répartition)
- Temps de latence (délai avant première réponse)
- Coût estimé (si tarification configurée)

**Section Contexte** :
- Agent type avec icône
- Session parente (lien cliquable)
- Traces enfants (liste avec aperçu)
- Outils utilisés (badges cliquables)

**Section Prompts** (existante, améliorée) :
- Prompt input avec syntax highlighting markdown
- Prompt output avec collapse par défaut si long
- Bouton copier pour chaque section

**Section Tags/Metadata** :
- Tags MITRE si applicable (du module sécurité)
- Répertoire de travail
- Timestamp précis avec fuseau horaire

### 4. Filtres et Recherche

**Barre de recherche** :
- Recherche full-text dans les prompts
- Syntaxe de filtrage : `agent:tester status:error duration:>5s`
- Autocomplétion des noms d'agents et status

**Filtres rapides** :
- Par status : Completed / Running / Error
- Par agent type : dropdown multi-select
- Par durée : slider min/max
- Par période : sélecteur de date (lien avec plan-23)

**Filtres sauvegardés** :
- Possibilité de sauvegarder des filtres fréquents
- Accès rapide aux filtres récents

### 5. Statistiques de Session

En haut de la vue hiérarchie, pour chaque session ROOT :
- Nombre total de traces dans l'arbre
- Durée totale de l'orchestration
- Agents uniques impliqués
- Taux de succès (completed / total)
- Graphique sparkline de l'activité

## Sous-tâches

Ce plan est complexe et peut être découpé :

- 32.1 - Breadcrumb navigation
- 32.2 - Vue Timeline/Waterfall
- 32.3 - Panneau de détails enrichi
- 32.4 - Barre de recherche et filtres
- 32.5 - Statistiques de session

## Priorité des sous-tâches

| Priorité | Sous-tâche | Dépendances | Effort estimé |
|----------|------------|-------------|---------------|
| 1 | 32.3 - Détails enrichis | Plan 30 (bugfixes) | Moyen |
| 2 | 32.1 - Breadcrumb | Aucune | Faible |
| 3 | 32.5 - Stats session | Aucune | Faible |
| 4 | 32.4 - Recherche/filtres | Aucune | Moyen |
| 5 | 32.2 - Timeline | 32.3 | Élevé |

## Checklist de validation

- [ ] Breadcrumb affiché et navigable pour toute trace sélectionnée
- [ ] Vue Timeline fonctionnelle avec barres proportionnelles
- [ ] Panneau de détails affiche toutes les métriques listées
- [ ] Recherche full-text trouve les traces par contenu de prompt
- [ ] Filtres par status/agent/durée fonctionnels
- [ ] Statistiques de session affichées en haut de la hiérarchie
- [ ] Performance acceptable avec 500+ traces
- [ ] Design cohérent avec le reste du dashboard
