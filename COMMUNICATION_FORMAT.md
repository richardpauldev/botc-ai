# Inter-Player Communication Format

This project exchanges information between players using simple Python dictionaries. When one player wants to share something with another, their `PlayerController` constructs a dictionary and passes it to `send_info()`. The receiving `Player` stores the message in `memory['received_info']` as:

```python
{"from": sender_name, "info": message_dict}
```

Two common message types are used:

- **public_claim** – the initial role claim (or bluff). Example:
  ```python
  {"public_claim": {"role": "Investigator", "seen_role": "Poisoner", "seen_players": ["Alice", "Bob"]}}
  ```
- **public** – follow up information publicly shared later. Example:
  ```python
  {"public": {"night_results": [{"night": 2, "player1": "Alice", "player2": "Bob", "ping": False}]}}
  ```

Additional keys may be present for special messages (e.g. the Demon privately sending `{"bluffs": ["Chef", "Mayor", "Empath"]}` to its minions).

Below is a summary of the information each role places in its own `memory` during play. These same structures appear in messages when that information is shared.

## Townsfolk

- **Washerwoman / Librarian / Investigator**
  ```python
  {"seen_role": "RoleName", "seen_players": ["Player1", "Player2"]}
  ```
- **Chef**
  ```python
  {"pairs": number_of_adjacent_evil_pairs}
  ```
- **Empath**
  ```python
  {"night_results": [{"night": N, "player1": "Left", "player2": "Right", "num_evil": count}]}
  ```
- **Fortune Teller**
  ```python
  {"night_results": [{"night": N, "player1": "P1", "player2": "P2", "ping": True_or_False}]}
  ```
- **Undertaker**
  ```python
  {"night_results": [{"night": N, "executed_player": "Name", "seen_role": "Role"}]}
  ```
- **Monk**
  ```python
  {"night": N, "protected": "TargetName"}
  ```
- **Ravenkeeper**
  ```python
  {"night": N, "seen_player": "TargetName", "seen_role": "RoleShown"}
  ```
- **Virgin**
  Records whether the nominator died via `memory["executed_by_virgin"] = True`.
- **Slayer**
  No structured info; ability effects are logged in game history.

## Outsiders

- **Butler**
  ```python
  {"night": N, "master": "TargetName"}
  ```
- **Drunk / Recluse / Saint**
  Do not generate extra info beyond standard claims.

## Minions

- **Poisoner**
  ```python
  "poisoned": "TargetName"
  ```
- **Spy**
  ```python
  {"all_roles": {"Player": "Role", ...}, "demon_bluffs": ["RoleA", "RoleB", "RoleC"]}
  ```
- **Baron / Scarlet Woman**
  Do not produce special info messages.

## Demon

- **Imp**
  ```python
  "kill_target": "TargetName"
  ```
  At game start the Imp also shares a `{"bluffs": [ ... ]}` list with the other evil players.

This file serves as a reference for constructing and interpreting the message dictionaries exchanged between players and controllers within the codebase.
