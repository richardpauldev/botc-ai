import itertools

def generate_all_worlds(
    player_names, all_minion_roles, m_minions, claims, TB_ROLES, outsider_count
):
    worlds = []
    n = len(player_names)
    players = list(player_names)

    for minion_role_combo in itertools.combinations(all_minion_roles, m_minions):
        # Only allow Barons for over-outsider worlds:
        minion_role_combo_set = set(minion_role_combo)
        for minion_players in itertools.combinations(players, m_minions):
            for minion_role_perm in itertools.permutations(minion_role_combo):
                minion_dict = dict(zip(minion_players, minion_role_perm))
                non_minions = [p for p in players if p not in minion_players]

                for imp_player in non_minions:
                    evil = set(minion_players) | {imp_player}
                    trustworthy = [p for p in players if p not in evil]
                    num_trustworthy_outsiders = sum(
                        1 for p in trustworthy
                        if claims.get(p, {}).get("role") in TB_ROLES["Outsider"]
                    )
                    # --- NEW LOGIC: If outsider claims > expected, must have Baron ---
                    if num_trustworthy_outsiders > outsider_count:
                        if "Baron" not in minion_role_combo_set:
                            continue  # Skip worlds without Baron
                    else:
                        if "Baron" in minion_role_combo_set:
                            continue # Skip worlds with Baron

                    if num_trustworthy_outsiders == outsider_count or num_trustworthy_outsiders == outsider_count + 2:
                        # No Drunk in evil
                        for drunk_player in [None]:  # No drunk, so no assignment
                            world = {}
                            for p in players:
                                if p in minion_dict:
                                    world[p] = minion_dict[p]
                                elif p == imp_player:
                                    world[p] = "Imp"
                                else:
                                    role = claims.get(p, {}).get("role")
                                    if role:
                                        world[p] = role  # Explicit outsider claim
                                    else:
                                        world[p] = "Good"
                            worlds.append(world.copy())
                    else:
                        # Outsider count doesn't match: must "remove" a trustworthy to allow Drunk as evil
                        for drunk_player in trustworthy:
                            reduced_trustworthy = [p for p in trustworthy if p != drunk_player]
                            # Now choose Drunk from the evil team (not a minion/imp who claims outsider)
                            # Only assign Drunk to someone who is not already claiming outsider
                            if claims.get(drunk_player, {}).get("role") in TB_ROLES["Outsider"]:
                                continue
                            world = {}
                            for p in players:
                                if p in minion_dict:
                                    world[p] = minion_dict[p]
                                elif p == imp_player:
                                    world[p] = "Imp"
                                elif p == drunk_player:
                                    world[p] = "Drunk"
                                else:
                                    role = claims.get(p, {}).get("role")
                                    if role:
                                        world[p] = role
                                    else:
                                        world[p] = "Good"
                            if len(world) == n:
                                worlds.append(world.copy())
    return worlds

# Usage as before...


# Usage:
player_names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Gina", "Holly"]
all_minion_roles = ["Poisoner", "Scarlet Woman", "Baron", "Spy"]
m_minions = 1
claims = {
    # Example: "Bob": {"role": "Recluse"}, ...
}
TB_ROLES = {
    "Townsfolk": ["Chef", "Washerwoman", "Slayer", "Fortune Teller", "Undertaker", "Ravenkeeper", "Librarian", "Investigator", "Monk", "Virgin", "Empath", "Soldier", "Mayor"],
    "Outsider": ["Drunk", "Recluse", "Saint", "Butler"],
    "Minion": ["Poisoner", "Scarlet Woman", "Baron", "Spy"],
    "Demon": ["Imp"]
}
outsider_count = 1  # Set as needed

worlds = generate_all_worlds(player_names, all_minion_roles, m_minions, claims, TB_ROLES, outsider_count)
print(f"Generated {len(worlds)} worlds.")
for w in worlds[:3]: print(w)