import itertools
from collections import Counter
import math

def get_neighbors(players, idx):
    """Return the names of the left and right neighbor (seated in a circle)."""
    n = len(players)
    left = players[(idx - 1) % n]
    right = players[(idx + 1) % n]
    return (left, right)

def validate_world(world, claims, TB_ROLES, player_names, imp_player, minion_player, red_herring=None):
    for pname in player_names:
        claim = claims.get(pname)
        role = world.get(pname)
        if role == "Washerwoman" and isinstance(claim, dict) and claim.get("role") == "Washerwoman":
            seen_role = claim.get("seen_role")
            seen_players = claim.get("seen_players", [])
            # Must see two players, and one must have the seen_role (must be Townsfolk)
            if (
                seen_role not in TB_ROLES["Townsfolk"]
                or len(seen_players) != 2
                or not any(world.get(p) == seen_role for p in seen_players)
            ):
                return False
        # Librarian
        elif role == "Librarian" and isinstance(claim, dict) and claim.get("role") == "Librarian":
            seen_role = claim.get("seen_role")
            seen_players = claim.get("seen_players", [])
            if seen_role is None:
                # Claiming no Outsider seen: there must be NO Outsider assigned
                if any(world.get(p) in TB_ROLES["Outsider"] for p in player_names):
                    return False
            else:
                # Must see two players, and one must have the seen_role (must be Outsider)
                if (
                    seen_role not in TB_ROLES["Outsider"]
                    or len(seen_players) != 2
                    or not any(world.get(p) == seen_role for p in seen_players)
                ):
                    return False
        # Investigator
        elif role == "Investigator" and isinstance(claim, dict) and claim.get("role") == "Investigator":
            seen_role = claim.get("seen_role")
            seen_players = claim.get("seen_players", [])
            # Must see two players, and one must have the seen_role (must be Minion)
            if (
                seen_role not in TB_ROLES["Minion"]
                or len(seen_players) != 2
                or not any(world.get(p) == seen_role for p in seen_players)
            ):
                return False
        #Empath Check
        elif role == "Empath" and isinstance(claim, dict) and 'empath_evil_neighbors' in claim:
            idx = player_names.index(pname)
            left, right = get_neighbors(player_names, idx)
            evil_neighbors = sum(
                n in {imp_player, minion_player} for n in (left, right)
            )
            if evil_neighbors != claim['empath_evil_neighbors']:
                return False
        elif role == "Undertaker" and isinstance(claim, dict) and claim.get("role") == "Undertaker":
            infos = claim.get("info", [])
            if not infos or not isinstance(infos, list):
                return False
            for undertaker_info in infos:
                executed = undertaker_info.get("executed")
                seen_role = undertaker_info.get("seen_role")
                # Both executed and seen_role must be present
                if not executed or seen_role is None:
                    return False
                # The executed player's actual role in this world must match the seen_role
                if world.get(executed) != seen_role:
                    return False
        elif role == "Fortune Teller" and isinstance(claim, dict) and claim.get("role") == "Fortune Teller":
                infos = claim.get("info", [])
                if not infos or not isinstance(infos, list):
                    return False
                demon = None
                # There may be multiple demons in custom scripts, but in Trouble Brewing, there's one
                for pname2, rname in world.items():
                    if rname in TB_ROLES["Demon"]:
                        demon = pname2
                        break
                if demon is None:
                    return False
                for ft_info in infos:
                    pair = ft_info.get("pair")
                    starred = ft_info.get("starred")
                    if not pair or len(pair) != 2 or starred is None:
                        return False
                    # "starred" means at least one is the demon
                    is_star = demon in pair or (red_herring and red_herring in pair)
                    if is_star != starred:
                        return False
    return True

def all_possible_evil_teams(
    player_names, TB_ROLES, setup_counts, claims, dead_players=None
):
    """
    Enumerate all possible valid worlds:
      - For every evil pair (one Imp, one Minion role)
      - All other players are good: if claimed, must get claimed role; if not, get any valid good role
    Returns: list of dicts (assignment per world), with keys _evil, _imp, _minion, _good
    """
    if dead_players is None:
        dead_players = []
    minion_roles = TB_ROLES['Minion']
    demon_role = TB_ROLES['Demon'][0]
    n_evil = setup_counts['Minion'] + setup_counts['Demon']
    results = []

    # Build list of all good roles for assignment (for this setup)
    all_good_roles = TB_ROLES["Townsfolk"] + TB_ROLES["Outsider"]

    for evil_team in itertools.combinations(player_names, n_evil):
        worlds = []
        imp_candidates = [p for p in evil_team if p not in dead_players]
        if not imp_candidates:
            continue   
        for imp_player in imp_candidates:
        # Remaining evil is minion (may be dead)
            minion_candidates = [p for p in evil_team if p != imp_player]
            for minion_player in minion_candidates:
                good_players = [p for p in player_names if p not in evil_team]
                # For each possible minion role:
                for minion_role in minion_roles:
                    assignment = {}
                    # Assign evil
                    assignment[imp_player] = demon_role
                    assignment[minion_player] = minion_role
                    used_roles = {demon_role, minion_role}
                    # Assign claimed roles to good players who have claims
                    unclaimed_good = []
                    for p in good_players:
                        if p in claims and isinstance(claims[p], dict):
                            claimed = claims[p]['role']
                        else:
                            claimed = claims.get(p, None)
                        if claimed:
                            if claimed in used_roles or claimed not in all_good_roles:
                                break  # Duplicate or illegal claim
                            assignment[p] = claimed
                            used_roles.add(claimed)
                        else:
                            unclaimed_good.append(p)
                    else:
                        roles_left = [r for r in all_good_roles if r not in used_roles]
                        if len(roles_left) < len(unclaimed_good):
                            continue  # Not enough roles to assign
                        for perm in set(itertools.permutations(roles_left, len(unclaimed_good))):
                            world = assignment.copy()
                            for p, r in zip(unclaimed_good, perm):
                                world[p] = r
                            # Final role count check
                            counts = {rt: 0 for rt in TB_ROLES}
                            for role in world.values():
                                for rt in TB_ROLES:
                                    if role in TB_ROLES[rt]:
                                        counts[rt] += 1
                            if any(counts[rt] != setup_counts[rt] for rt in setup_counts):
                                continue

                            
                            # === BRANCH FOR RED HERRING IF FT EXISTS ===
                            has_ft = any(
                                world.get(p) == "Fortune Teller" and
                                isinstance(claims.get(p), dict) and
                                claims[p].get("role") == "Fortune Teller"
                                for p in player_names
                            )
                            if has_ft:
                                eligible_rh = [
                                    p for p in player_names
                                    if world.get(p) not in TB_ROLES["Demon"] + TB_ROLES["Minion"]
                                ]
                                for rh in eligible_rh:
                                    valid = validate_world(
                                        world, claims, TB_ROLES, player_names,
                                        imp_player, minion_player, red_herring=rh
                                    )
                                    if not valid:
                                        continue
                                    w = world.copy()
                                    w['_evil'] = {imp_player, minion_player}
                                    w['_imp'] = imp_player
                                    w['_minion'] = minion_player
                                    w['_minion_role'] = minion_role
                                    w['_good'] = set(good_players)
                                    w['_red_herring'] = rh
                                    w['_weight'] = 1
                                    worlds.append(w)
                            else:
                                valid = validate_world(
                                    world, claims, TB_ROLES, player_names,
                                    imp_player, minion_player, red_herring=None
                                )
                                if not valid:
                                    continue
                                world['_evil'] = {imp_player, minion_player}
                                world['_imp'] = imp_player
                                world['_minion'] = minion_player
                                world['_minion_role'] = minion_role
                                world['_good'] = set(good_players)
                                world['_red_herring'] = None
                                worlds.append(world)
        for world in worlds:
            world['_weight'] = 1/len(worlds)
            results.append(world)
            
    return results

def imp_probabilities(players, worlds):
    imp_weight = Counter()
    total_weight = 0
    for w in worlds:
        wt = w['_weight']
        imp_weight[w['_imp']] += wt
        total_weight += wt
    # Probability = count / total
    probs = {p: imp_weight[p]/total_weight for p in players}
    return probs

# Example usage
if __name__ == "__main__":
    TB_ROLES = {
        "Townsfolk": [
            "Washerwoman", "Librarian", "Investigator", "Chef", "Empath",
            "Fortune Teller", "Undertaker", "Monk", "Ravenkeeper", "Virgin",
            "Slayer", "Soldier", "Mayor"
        ],
        "Outsider": [
            "Butler", "Drunk", "Recluse", "Saint"
        ],
        "Minion": [
            "Poisoner", "Scarlet Woman", "Spy", "Baron"
        ],
        "Demon": [
            "Imp"
        ]
    }

    players = ["Alice", "Bob", "Carol", "Dave", "Evan", "Frank", "Grace"]
    setups = {
        5:  {'Townsfolk': 3, 'Outsider': 0, 'Minion': 1, 'Demon': 1},
        6:  {'Townsfolk': 3, 'Outsider': 1, 'Minion': 1, 'Demon': 1},
        7:  {'Townsfolk': 5, 'Outsider': 0, 'Minion': 1, 'Demon': 1}
    }
    setup_counts = setups[len(players)]
    claims = {
        "Alice": {
            "role": "Chef"
        },
        "Bob": {
            "role": "Empath",
            "empath_evil_neighbors": 1  # Will only be true if one neighbor is evil in the world
        },
        "Carol": {
            "role": "Librarian",
            "seen_role": None,  # No Outsider seen
            "seen_players": []
        },
        "Dave": {
            "role": "Undertaker",
            "info": [
                {"executed": "Frank", "seen_role": "Scarlet Woman"},
                {"executed": "Grace", "seen_role": "Chef"}
            ]
        },
        "Evan": {
            "role": "Investigator",
            "seen_role": "Poisoner",
            "seen_players": ["Carol", "Frank"]
        },
        "Frank": {
            "role": "Slayer"
        },
        "Grace": {
            "role": "Fortune Teller",
            "info": [
                # If red herring is Bob, this pair will return True, else only if the demon is present
                {"pair": ["Alice", "Bob"], "starred": True},
                {"pair": ["Evan", "Frank"], "starred": False},
                # If red herring is Carol or demon is present, will be True
                {"pair": ["Carol", "Dave"], "starred": True}
            ]
        }
    }
    dead_players = []#["Dave", "Carol"]
    # claims = {
    #     "Alice": {"role": "Ravenkeeper"},
    #     "Bob": {"role": "Undertaker"},
    #     "Carol": {"role": "Monk"},
    #     "Dave": {"role": "Virgin"},
    #     "Evan": {"role": "Librarian", "seen_role": None}, # None = no outsider seen
    # }


    worlds = all_possible_evil_teams(players, TB_ROLES, setup_counts, claims, dead_players=dead_players)
    # print(f"Generated {len(worlds)} valid worlds.")
    # for w in worlds:
    #     print({p: w[p] for p in players}, "| Evil:", w['_evil'])
    imp_probs = imp_probabilities(players, worlds)
    print("\nProbability of being the Imp/Demon:")
    for p, prob in imp_probs.items():
        print(f"{p}: {prob:.3f}")
