# Plan 25 - Open Session in Terminal

## Contexte

La fonctionnalite de focus iTerm2 existe deja dans le menubar (`ui/terminal.py` avec AppleScript). Quand l'utilisateur clique sur un agent dans le menu, ca ouvre/focus la fenetre iTerm correspondante.

Cette feature n'est pas disponible dans le Dashboard PyQt. L'utilisateur doit pouvoir cliquer sur un agent dans le dashboard pour ouvrir/focus le terminal correspondant.

## Objectif

Permettre d'ouvrir/focus la session iTerm2 correspondante depuis le Dashboard PyQt :
- Dans la section Monitoring > Active Agents
- Dans la section Monitoring > Waiting for Response
- (Optionnel) Via un raccourci clavier

## Comportement attendu

1. **Double-clic sur une ligne** dans la table "Active Agents" → Focus iTerm2 sur le TTY de cet agent
2. **Double-clic sur une ligne** dans la table "Waiting for Response" → Focus iTerm2 sur le TTY de cet agent
3. **Bouton "Open in Terminal"** (optionnel) dans un context menu (clic droit)
4. **Feedback visuel** : Curseur change au survol pour indiquer que c'est cliquable

## Specifications techniques

### Donnees necessaires

Chaque agent doit avoir son `tty` disponible. Actuellement dans `window.py/_fetch_monitoring_data()`, on recupere les agents mais pas leur TTY de maniere explicite.

Modifications :
1. Ajouter `tty` dans `agents_data` et `waiting_data`
2. Stocker le mapping `agent_id -> tty` pour pouvoir focus

### Implementation UI (PyQt6)

Dans `sections.py` :
```python
# Activer le double-clic sur DataTable
self._agents_table.cellDoubleClicked.connect(self._on_agent_double_click)

def _on_agent_double_click(self, row: int, col: int):
    agent_id = self._agents_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    # Emettre signal avec agent_id
    self.open_terminal_requested.emit(agent_id)
```

Dans `window.py` :
```python
# Connecter le signal au handler
self._monitoring.open_terminal_requested.connect(self._on_open_terminal)

def _on_open_terminal(self, agent_id: str):
    tty = self._agent_tty_map.get(agent_id)
    if tty:
        from ..ui.terminal import focus_iterm2
        focus_iterm2(tty)
```

### Curseur cliquable

```python
self._agents_table.setCursor(Qt.CursorShape.PointingHandCursor)
```

## Fichiers a modifier

| Fichier | Modification |
|---------|--------------|
| `dashboard/sections.py` | Ajouter signal `open_terminal_requested`, handler double-clic, curseur |
| `dashboard/window.py` | Connecter signal, stocker mapping agent_id->tty, appeler `focus_iterm2()` |
| `core/models.py` | (Si besoin) S'assurer que `Agent.tty` est disponible |

## Validation

- [x] Double-clic sur agent BUSY ouvre iTerm sur le bon terminal
- [x] Double-clic sur agent WAITING ouvre iTerm sur le bon terminal
- [x] Curseur change au survol des lignes
- [x] Pas d'erreur si TTY non disponible (ex: agent zombie)
- [x] Tests unitaires pour le mapping et le signal

## Statut

**TERMINE** - v2.18.0 - 2025-12-31

## Notes

- La fonction `focus_iterm2()` existe deja et fonctionne
- Pas besoin de supporter d'autres terminaux pour l'instant (Terminal.app, etc.)
- Le TTY est deja recupere via `get_tty_for_port()` dans `monitor.py`
