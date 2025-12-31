# Plan 20 - Agent Tracing System

## Contexte

Actuellement, le monitoring affiche les agents actifs et leurs tools en temps reel, mais il n'y a pas de mecanisme pour suivre les traces completes d'execution : quels agents ont ete invoques, par qui, avec quels inputs/outputs, combien de temps ils ont pris, combien de tokens ils ont consomme.

Le systeme actuel (analytics DuckDB) stocke des statistiques agregees mais ne permet pas de reconstruire le flow d'execution d'une session ou de visualiser la chaine de delegation en temps reel.

## Objectif

Implementer un systeme de tracing pour capturer et visualiser les traces d'execution des agents :
- Tracer chaque invocation d'agent avec son contexte (parent, input, output)
- Suivre les delegations entre agents (qui a appele qui)
- Mesurer les durees d'execution et consommation de tokens par agent
- Permettre la reconstruction du flow complet d'une session

## Comportement attendu

### Capture des traces

Quand un agent demarre :
- Une trace est creee avec un ID unique, timestamp, agent parent (si delegation)
- L'input (prompt) est capture (ou un resume/hash si trop long)
- Le statut passe a "running"

Quand un agent termine :
- L'output est capture (ou un resume si trop long)
- Les metriques sont enregistrees (duree, tokens in/out, tools utilises)
- Le statut passe a "completed" ou "error"

### Visualisation

Dans le dashboard ou un outil dedie :
- Vue timeline : chronologie des agents avec durees
- Vue arbre : hierarchie des delegations (parent -> children)
- Vue flow : diagramme de la chaine d'execution
- Metriques : tokens par agent, duree totale, bottlenecks

### Filtrage

L'utilisateur peut :
- Filtrer par session, par date, par agent
- Rechercher des patterns (ex: "toutes les sessions avec tester -> refactoring")
- Identifier les sessions anormalement longues ou couteuses

## Specifications

_A completer par l'Executeur_

### Evaluation des librairies

Evaluer les options suivantes :
1. **OpenTelemetry** : Standard industrie pour le tracing distribue
2. **Langfuse** : Specialise LLM, traces + analytics
3. **LangSmith** : Solution LangChain
4. **Solution custom** : Extension du systeme DuckDB existant

Criteres d'evaluation :
- Integration avec le code Python existant
- Overhead de performance
- Stockage local vs cloud
- Visualisation incluse ou a developper
- Compatibilite avec le monitoring temps reel

### Architecture proposee

_A definir selon la librairie choisie_

## Checklist de validation

- [ ] Evaluation des librairies documentee
- [ ] Choix de la solution justifie
- [ ] POC fonctionnel avec une session simple
- [ ] Capture des traces sur delegations (task tool)
- [ ] Metriques de duree et tokens par trace
- [ ] Vue de reconstruction du flow
- [ ] Performance acceptable (< 5% overhead)
- [ ] Tests unitaires pour le module de tracing
- [ ] Documentation utilisateur
