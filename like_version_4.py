import itertools
from itertools import product
from collections import Counter, defaultdict
import math
from copy import deepcopy

# TODO figure out how to deal with startpassing (should only affect characters that directly see role: ravenkeeper, undertaker, fortune teller)

# At end, if any possible Imp died during the night, add Imp as a possibility to all untrustworthy with at least 1 minion role
# (Note) If there is a untrustworthy with only Scarlet woman as possbility, add Imp to them

# If all possible Imps have died via execution, Add in a scarlet woman as a required minion

def enforce_required_minions(world, TB_ROLES, setup_counts):
    minion_count = setup_counts.get("Minion", 0)
    demon_set = set(TB_ROLES["Demon"])
    required_minions = world.get("required_minions", set())
    untrustworthy = [p for p, a in world["alignments"].items() if a == "untrustworthy"]
    roles_needed = minion_count + setup_counts.get("Demon", 1)
    has_extra = len(untrustworthy) > roles_needed
    if len(required_minions) == minion_count:
        role_pool = demon_set | required_minions
        if has_extra:
            role_pool.add("Drunk")
        for p in untrustworthy:
            world["possible_roles_per_untrustworthy"][p] &= role_pool
        if any(len(world["possible_roles_per_untrustworthy"][p]) == 0 for p in untrustworthy):
            return False
        
        demon_possible = any(
            bool(world["possible_roles_per_untrustworthy"][p] & demon_set)
            for p in untrustworthy
        )
        minion_possibles = [
            p for p in untrustworthy
            if world["possible_roles_per_untrustworthy"][p] & required_minions
        ]
        if not demon_possible:
            return False
        if len(minion_possibles) < minion_count:
            return False
    return True


def starting_check(world, TB_ROLES, setup_counts):
    trustworthy = [p for p, t in world["alignments"].items() if t == "trustworthy"]
    roles = world["roles"]
    # 1. Duplicate trustworthy claims
    claimed_roles = [roles[p] for p in trustworthy if roles[p]]
    if len(set(claimed_roles)) != len(claimed_roles):
        return []  # Prune this world
    
    alignments = world["alignments"]
    info = world.get("info_to_resolve", [])

    # Virgin check: If any trustworthy Virgin claim includes a "killed" event, Virgin must be trustworthy
    for item in info:
        if item.get("type") == "virgin" and item.get("died"):
            claimer = item.get("claimer")
            if claimer and alignments.get(claimer) == "untrustworthy":
                # Prune this world
                return []
    
    # Slayer check: If any Slayer has fired a shot, that Slayer must not be untrustworthy
    for item in info:
        if item.get("type") == "slayer" and item.get("died"):
            claimer = item.get("claimer")
            if claimer and alignments.get(claimer) == "untrustworthy":
                # Prune this world
                return []

    # TODO: Add check that at least one untrustworthy is alive. If only one alive untrust, remove drunk as a possiblity for that player.

    # 2. Outsider claims logic
    expected_outsiders = setup_counts.get("Outsider", 0)
    trustworthy_outsider_claims = [p for p in trustworthy if roles[p] in TB_ROLES.get("Outsider", [])]
    n_claimed_outsiders = len(trustworthy_outsider_claims)
    result = []

    # 2a. Too many outsiders: must have Baron
    if n_claimed_outsiders > expected_outsiders:
        world.setdefault("required_minions", set()).add("Baron")
        # Immediately restrict possible minions if at capacity
        if not enforce_required_minions(world, TB_ROLES, setup_counts):
            return []

    # 2b/c. Delta of 1: must be Drunk (high liar count only)
    outsider_claim_delta = len(trustworthy_outsider_claims) - expected_outsiders
    n_expected_liars = setup_counts.get("Minion", 0) + setup_counts.get("Demon", 0)
    if abs(outsider_claim_delta) == 1 and n_expected_liars == sum(1 for t in world["alignments"].values() if t == "untrustworthy"):
        return []
    
    if outsider_claim_delta == 0 or outsider_claim_delta == 2:
        for p in world["possible_roles_per_untrustworthy"]:
            world["possible_roles_per_untrustworthy"][p] -= {"Drunk"}
    
    all_claimed = all(roles.get(p) for p in trustworthy)
    if all_claimed and n_claimed_outsiders <= expected_outsiders:
        for p in world["possible_roles_per_untrustworthy"]:
            world["possible_roles_per_untrustworthy"][p] -= {"Baron"}
    return [world]

def branch_for_poisoner(w, TB_ROLES, setup_counts, night=1):
    """
    If Poisoner is possible in current world and not already marked as poisoned,
    create and return a world with Poisoner forced and 1_night_poisoned constraint.
    Returns: poisoned_world or None if not possible.
    """
    if f"{night}_night_poisoned" in w["constraints"]:
        return None
    # Is Poisoner a possible minion for any untrustworthy?
    poisoner_possible = any(
        "Poisoner" in w["possible_roles_per_untrustworthy"][p]
        for p in w["possible_roles_per_untrustworthy"]
    )
    if not poisoner_possible:
        return None
    poisoned_w = deepcopy(w)
    poisoned_w.setdefault("required_minions", set()).add("Poisoner")
    if not enforce_required_minions(poisoned_w, TB_ROLES, setup_counts):
        return None
    
    poisoned_w["constraints"].append(f"{night}_night_poisoned")
    return poisoned_w

def process_washerwoman(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "washerwoman"]
    if not info_items:
        return [world]  # No washerwoman claim

    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        seen_players = info["seen_players"]
        seen_role = info["seen_role"]
        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]
            a, b = seen_players
            a_align, b_align = alignments[a], alignments[b]
            a_role, b_role = roles.get(a), roles.get(b)

            # If any trustworthy among the two claims the seen role, world is valid
            if (a_align == "trustworthy" and a_role == seen_role) or (b_align == "trustworthy" and b_role == seen_role):
                next_worlds.append(w)
                continue

            # If at least one is trustworthy with no claim, ambiguous/valid
            if (a_align == "trustworthy" and not a_role) or (b_align == "trustworthy" and not b_role):
                next_worlds.append(w)
                continue

            # If both trustworthy, only possible if poisoned
            if a_align == "trustworthy" and b_align == "trustworthy":
                poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
                if poisoned_world:
                    next_worlds.append(poisoned_world)
                # else, prune (no next_worlds for this branch)
                continue

            poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
            if poisoned_world:
                next_worlds.append(poisoned_world)

            # Otherwise: for each untrustworthy among the two who could be the seen role, branch
            for pname in [a, b]:
                if alignments[pname] == "untrustworthy" and "Spy" in w["possible_roles_per_untrustworthy"][pname]:
                    # Always branch poisoner first!
                    spy_w = deepcopy(w)
                    spy_w["possible_roles_per_untrustworthy"][pname] &= {"Spy"}
                    spy_w.setdefault("required_minions", set()).add("Spy")
                    # Remove Spy from all other untrustworthy
                    for other in spy_w["possible_roles_per_untrustworthy"]:
                        if other != pname:
                            spy_w["possible_roles_per_untrustworthy"][other] -= {"Spy"}
                    if not enforce_required_minions(spy_w, TB_ROLES, setup_counts):
                        continue
                    if all(len(s) > 0 for s in spy_w["possible_roles_per_untrustworthy"].values()):
                        next_worlds.append(spy_w)
        current_worlds = next_worlds
    return current_worlds


def process_librarian(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "librarian"]
    if not info_items:
        return [world]
    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        seen_players = info.get("seen_players", [])
        seen_role = info.get("seen_role")
        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]
            expected_outsiders = setup_counts.get("Outsider", 0)

            # Case: told None (no Outsider in play)
            if not seen_players or seen_role is None:
                outsider_claims = [p for p, r in roles.items()
                                   if alignments[p] == "trustworthy" and r in TB_ROLES.get("Outsider",[])]
                if outsider_claims:
                    # Add poisoned world before pruning!
                    poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
                    if poisoned_world:
                        next_worlds.append(poisoned_world)
                    continue
                next_worlds.append(w)
                continue

            # If we see an outsider but setup expects none, must have a Baron!
            if expected_outsiders == 0:
                # Add poisoned world before enforcing Baron
                poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
                if poisoned_world:
                    next_worlds.append(poisoned_world)
                w_bar = deepcopy(w)
                w_bar.setdefault("required_minions", set()).add("Baron")
                if not enforce_required_minions(w_bar, TB_ROLES, setup_counts):
                    continue
                next_worlds.append(w_bar)
                continue

            a, b = seen_players
            a_align, b_align = alignments[a], alignments[b]
            a_role, b_role = roles.get(a), roles.get(b)

            # If any trustworthy among seen_players claims the seen_role, world is valid
            if (a_align == "trustworthy" and a_role == seen_role) or (b_align == "trustworthy" and b_role == seen_role):
                next_worlds.append(w)
                continue

            # If at least one is trustworthy with no claim, ambiguous/valid
            if not seen_role == "Drunk" and (a_align == "trustworthy" and not a_role) or (b_align == "trustworthy" and not b_role):
                next_worlds.append(w)
                continue

            poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
            if poisoned_world:
                next_worlds.append(poisoned_world)

            # Drunk logic: Drunk can be untrustworthy, others can't.
            if seen_role == "Drunk":
                for pname in [a, b]:
                    if alignments[pname] == "untrustworthy" and "Drunk" in w["possible_roles_per_untrustworthy"][pname]:
                        # Add poisoned world before creating Drunk branch
                        branch = deepcopy(w)
                        branch["possible_roles_per_untrustworthy"][pname] = {"Drunk"}
                        for other in [a, b]:
                            if other != pname and alignments[other] == "untrustworthy":
                                branch["possible_roles_per_untrustworthy"][other] -= {"Drunk"}
                        if all(len(s) > 0 for s in branch["possible_roles_per_untrustworthy"].values()):
                            next_worlds.append(branch)
        current_worlds = next_worlds
    return current_worlds

def process_investigator(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "investigator"]
    if not info_items:
        return [world]
    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        if not "seen_players" in info or info["seen_players"] == None:
            continue
        seen_players = info.get("seen_players", [])
        seen_role = info.get("seen_role")
        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]

            a, b = seen_players
            a_align, b_align = alignments[a], alignments[b]
            a_role, b_role = roles.get(a), roles.get(b)


            if (a_align == "trustworthy" and a_role == "Recluse") or (b_align == "trustworthy" and b_role == "Recluse"):
                next_worlds.append(w)
                continue

            poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts)
            if poisoned_world:
                next_worlds.append(poisoned_world)
            # If one or both untrustworthy:
            for pname in [a, b]:
                if alignments[pname] == "untrustworthy" and seen_role in w["possible_roles_per_untrustworthy"][pname]:
                    # Poisoner branch before gaining knowledge
                    branch = deepcopy(w)
                    branch["possible_roles_per_untrustworthy"][pname] = {seen_role}
                    for other in [a, b]:
                        if other != pname and alignments[other] == "untrustworthy":
                            branch["possible_roles_per_untrustworthy"][other] -= {seen_role}
                    branch.setdefault("required_minions", set()).add(seen_role)
                    
                    if not enforce_required_minions(branch, TB_ROLES, setup_counts):
                        continue
                    if all(len(s) > 0 for s in branch["possible_roles_per_untrustworthy"].values()):
                        next_worlds.append(branch)
            current_worlds = next_worlds
        return current_worlds

def process_undertaker(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "undertaker"]
    if not info_items:
        return [world]  # No undertaker claims

    current_worlds = [world]
    for info in info_items:
        if not "night_results" in info or info["night_results"] == None:
            continue
        night_results = info.get("night_results", [])
        claimer = info["claimer"]


        for night_info in night_results:
            next_worlds = []
            night = night_info["night"]
            executed_player = night_info["executed_player"]
            seen_role = night_info["seen_role"]

            for w in current_worlds:
                roles = w["roles"]
                alignments = w["alignments"]
                executed_align = alignments.get(executed_player)
                executed_actual_role = roles.get(executed_player)
                minion_roles = set(TB_ROLES.get("Minion", []))
                demon_roles = set(TB_ROLES.get("Demon", []))
                evil_roles = minion_roles | demon_roles
                townsfolk_roles = set(TB_ROLES.get("Townsfolk", []))
                outsider_roles = set(TB_ROLES.get("Outsider", []))

                # CASE 1: TRUSTWORTHY executed player
                if executed_align == "trustworthy":
                    # Normal correct info
                    if executed_actual_role == seen_role:
                        next_worlds.append(w)
                        continue
                    # Recluse exception: undertaker can see any minion/demon if executed player is Recluse
                    if executed_actual_role == "Recluse" and seen_role in evil_roles:
                        next_worlds.append(w)
                        continue
                    # Not matching—split a poisoned world if possible
                    poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                    if poisoned_world:
                        next_worlds.append(poisoned_world)
                    # else, prune (no next_worlds for this branch)
                    continue

                # CASE 2: UNTRUSTWORTHY executed player
                if executed_align == "untrustworthy":
                    # First, always branch a poisoned world if possible
                    poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                    if poisoned_world:
                        next_worlds.append(poisoned_world)

                    # If seen_role is a Townsfolk or Outsider, evil player can bluff as Spy or Drunk
                    if seen_role in townsfolk_roles or seen_role in outsider_roles:
                        # Branch: evil player is the Spy
                        if "Spy" in w["possible_roles_per_untrustworthy"][executed_player]:
                            spy_world = deepcopy(w)
                            spy_world["possible_roles_per_untrustworthy"][executed_player] &= {"Spy"}
                            for other in w["possible_roles_per_untrustworthy"]:
                                if other != executed_player:
                                    spy_world["possible_roles_per_untrustworthy"][other] -= {"Spy"}
                            spy_world.setdefault("required_minions", set()).add("Spy")
                            if enforce_required_minions(spy_world, TB_ROLES, setup_counts):
                                next_worlds.append(spy_world)

                        # Branch: evil player is the Drunk (only if Drunk is allowed for untrustworthy)
                        if seen_role == "Drunk" and "Drunk" in w["possible_roles_per_untrustworthy"][executed_player]:
                            drunk_world = deepcopy(w)
                            drunk_world["possible_roles_per_untrustworthy"][executed_player] = {"Drunk"}
                            for other in w["possible_roles_per_untrustworthy"]:
                                if other != executed_player:
                                    drunk_world["possible_roles_per_untrustworthy"][other] -= {"Drunk"}
                            if enforce_required_minions(drunk_world, TB_ROLES, setup_counts):
                                next_worlds.append(drunk_world)

                    # If seen_role is a minion or demon, assign that role to executed_player
                    if seen_role in evil_roles:
                        if seen_role in w["possible_roles_per_untrustworthy"][executed_player]:
                            assign_evil_world = deepcopy(w)
                            assign_evil_world["possible_roles_per_untrustworthy"][executed_player] = {seen_role}
                            for other in w["possible_roles_per_untrustworthy"]:
                                if other != executed_player:
                                    assign_evil_world["possible_roles_per_untrustworthy"][other] -= {seen_role}
                            if seen_role in minion_roles:
                                assign_evil_world.setdefault("required_minions", set()).add(seen_role)
                                if enforce_required_minions(assign_evil_world, TB_ROLES, setup_counts):
                                    next_worlds.append(assign_evil_world)
                            else:
                                next_worlds.append(assign_evil_world)
            current_worlds = next_worlds
    return current_worlds

def process_ravenkeeper(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "ravenkeeper"]
    if not info_items:
        return [world] 

    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        if not "night" in info or info["night"] == None:
            continue
        night = info["night"]
        claimer = info["claimer"]
        seen_player = info["seen_player"]
        seen_role = info["seen_role"]

        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]
            executed_align = alignments.get(seen_player)
            executed_actual_role = roles.get(seen_player)
            minion_roles = set(TB_ROLES.get("Minion", []))
            demon_roles = set(TB_ROLES.get("Demon", []))
            evil_roles = minion_roles | demon_roles
            townsfolk_roles = set(TB_ROLES.get("Townsfolk", []))
            outsider_roles = set(TB_ROLES.get("Outsider", []))

            # CASE 1: TRUSTWORTHY executed player
            if executed_align == "trustworthy":
                # Normal correct info
                if executed_actual_role == seen_role:
                    next_worlds.append(w)
                    continue
                # Recluse exception: undertaker can see any minion/demon if executed player is Recluse
                if executed_actual_role == "Recluse" and seen_role in evil_roles:
                    next_worlds.append(w)
                    continue
                # Not matching—split a poisoned world if possible
                poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                if poisoned_world:
                    next_worlds.append(poisoned_world)
                # else, prune (no next_worlds for this branch)
                continue

            # CASE 2: UNTRUSTWORTHY executed player
            if executed_align == "untrustworthy":
                # First, always branch a poisoned world if possible
                poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                if poisoned_world:
                    next_worlds.append(poisoned_world)

                # If seen_role is a Townsfolk or Outsider, evil player can bluff as Spy or Drunk
                if seen_role in townsfolk_roles or seen_role in outsider_roles:
                    # Branch: evil player is the Spy
                    if "Spy" in w["possible_roles_per_untrustworthy"][seen_player]:
                        spy_world = deepcopy(w)
                        spy_world["possible_roles_per_untrustworthy"][seen_player] &= {"Spy"}
                        for other in w["possible_roles_per_untrustworthy"]:
                            if other != seen_player:
                                spy_world["possible_roles_per_untrustworthy"][other] -= {"Spy"}
                        spy_world.setdefault("required_minions", set()).add("Spy")
                        if enforce_required_minions(spy_world, TB_ROLES, setup_counts):
                            next_worlds.append(spy_world)

                    # Branch: evil player is the Drunk (only if Drunk is allowed for untrustworthy)
                    if seen_role == "Drunk" and "Drunk" in w["possible_roles_per_untrustworthy"][executed_player]:
                        drunk_world = deepcopy(w)
                        drunk_world["possible_roles_per_untrustworthy"][seen_player] = {"Drunk"}
                        for other in w["possible_roles_per_untrustworthy"]:
                            if other != seen_player:
                                drunk_world["possible_roles_per_untrustworthy"][other] -= {"Drunk"}
                        if enforce_required_minions(drunk_world, TB_ROLES, setup_counts):
                            next_worlds.append(drunk_world)

                # If seen_role is a minion or demon, assign that role to seen_player
                if seen_role in evil_roles:
                    if seen_role in w["possible_roles_per_untrustworthy"][seen_player]:
                        assign_evil_world = deepcopy(w)
                        assign_evil_world["possible_roles_per_untrustworthy"][seen_player] = {seen_role}
                        for other in w["possible_roles_per_untrustworthy"]:
                            if other != seen_player:
                                assign_evil_world["possible_roles_per_untrustworthy"][other] -= {seen_role}
                        if seen_role in minion_roles:
                            assign_evil_world.setdefault("required_minions", set()).add(seen_role)
                            if enforce_required_minions(assign_evil_world, TB_ROLES, setup_counts):
                                next_worlds.append(assign_evil_world)
                        else:
                            next_worlds.append(assign_evil_world)
        current_worlds = next_worlds
    return current_worlds

def process_slayer(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "slayer"]
    if not info_items:
        return [world] 

    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        if not "night" in info or not isinstance(info["night"], int):
            continue
        night = info["night"]
        shot_player = info["shot_player"]
        player_died = info["died"]

        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]
            alignment = alignments.get(shot_player)
            role = roles.get(shot_player)
            

            if player_died:
                if alignment == "trustworthy" and role == "Recluse":
                    next_worlds.append(w)
                    continue
                if alignment == "untrustworthy":
                    if "Imp" in w["possible_roles_per_untrustworthy"][shot_player]:
                        imp_world = deepcopy(w)
                        imp_world["possible_roles_per_untrustworthy"][shot_player] = {"Imp"}
                        # Remove Imp from other untrustworthy
                        for other in imp_world["possible_roles_per_untrustworthy"]:
                            if other != shot_player:
                                imp_world["possible_roles_per_untrustworthy"][other] -= {"Imp"}
                        next_worlds.append(imp_world)
                    continue
                # Otherwise, trustworthy non-Recluse can't die to Slayer; prune
                continue
            else:
                if alignment == "trustworthy":
                    next_worlds.append(w)
                    continue
                # Branch 1: Poisoner world, with constraint for this night
                poisoned_world = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                if poisoned_world:
                    # In poisoned world, shot_player must be Imp (as Slayer shot would have worked if not poisoned)
                    if "Imp" in poisoned_world["possible_roles_per_untrustworthy"][shot_player]:
                        poisoned_world["possible_roles_per_untrustworthy"][shot_player] = {"Imp"}
                        for other in poisoned_world["possible_roles_per_untrustworthy"]:
                            if other != shot_player:
                                poisoned_world["possible_roles_per_untrustworthy"][other] -= {"Imp"}
                        next_worlds.append(poisoned_world)
                # Branch 2: Remove Imp from shot_player's possible roles
                if "Imp" in w["possible_roles_per_untrustworthy"][shot_player]:
                    not_imp_world = deepcopy(w)
                    not_imp_world["possible_roles_per_untrustworthy"][shot_player] -= {"Imp"}
                    next_worlds.append(not_imp_world)
                # branch for poison world, INCLUDING that the shot player must be the IMP
                # branch where that player has imp removed.
        current_worlds = next_worlds
    return current_worlds

def process_virgin(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "virgin"]
    if not info_items:
        return [world] 

    current_worlds = [world]
    for info in info_items:
        next_worlds = []
        night = info["night"]
        nom_player = info["first_nominator"]
        player_died = info["died"]
        for w in current_worlds:
            roles = w["roles"]
            alignments = w["alignments"]
            alignment = alignments.get(nom_player)
            role = roles.get(nom_player)
            

            if player_died:
                if alignment == "trustworthy" and role in TB_ROLES["Townsfolk"]:
                    next_worlds.append(w)
                    continue
                if alignment == "untrustworthy":
                    w["possible_roles_per_untrustworthy"][nom_player] &= {"Spy"}
                    w.setdefault("required_minions", set()).add("Spy")
                    for other in w["possible_roles_per_untrustworthy"]:
                        if other != nom_player:
                            w["possible_roles_per_untrustworthy"][other] -= {"Spy"}
                    if not enforce_required_minions(w, TB_ROLES, setup_counts):
                        continue
                    next_worlds.append(w)
                    continue
                continue
            else:
                if alignment == "trustworthy" and role in TB_ROLES["Townsfolk"]:
                    pw = branch_for_poisoner(world, TB_ROLES, setup_counts, night=night)
                    if pw:
                        next_worlds.append(pw)
                    continue
                next_worlds.append(w)
        current_worlds = next_worlds
    return current_worlds

def process_empath(world, TB_ROLES, setup_counts):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "empath"]
    if not info_items:
        return [world]  # No undertaker claims

    current_worlds = [world]
    for info in info_items:
        night_results = info.get("night_results", [])
        claimer = info["claimer"]

        for night_info in night_results:
            next_worlds = []
            night = night_info["night"]
            num_evil = night_info["num_evil"]
            a_player = night_info["neighbor1"]
            b_player = night_info["neighbor2"]

            for w in current_worlds:
                # print(current_worlds)
                roles = w["roles"]
                alignments = w["alignments"]
                a_role = roles.get(a_player)
                b_role = roles.get(b_player)
                a_alignment = alignments.get(a_player)
                b_alignment = alignments.get(b_player)

                # Helper for poison branch
                def poison_branch(w):
                    # print_world(-1, w)
                    poisoned = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                    if poisoned:
                        next_worlds.append(poisoned)

                if a_alignment == "trustworthy" and b_alignment == "trustworthy":
                    if (a_role == "Recluse" or b_role == "Recluse") and num_evil == 1:
                        next_worlds.append(w)
                        continue
                    if num_evil > 0: 
                        poison_branch(w)
                        continue
                    
                    next_worlds.append(w)
                    continue
                
                                # Case: one untrustworthy, one trustworthy
                if (a_alignment == "untrustworthy" and b_alignment == "trustworthy") or \
                   (a_alignment == "trustworthy" and b_alignment == "untrustworthy"):
                    untrustworthy_player = a_player if a_alignment == "untrustworthy" else b_player
                    trustworthy_player = b_player if a_alignment == "untrustworthy" else a_player
                    trustworthy_role = roles.get(trustworthy_player)

                    possible_roles = w["possible_roles_per_untrustworthy"][untrustworthy_player]

                    if num_evil == 0:
                        # If untrustworthy but result 0, only possible if untrustworthy is Spy or Drunk
                        narrowed = possible_roles & {"Spy", "Drunk"}
                        if narrowed:
                            branch = deepcopy(w)
                            branch["possible_roles_per_untrustworthy"][untrustworthy_player] &= {"Spy", "Drunk"}
                            next_worlds.append(branch)
                            poison_branch(w)
                        continue
                    if num_evil == 1:
                        # Remove Drunk from possibilities (unless trustworthy is Recluse)
                        if trustworthy_role != "Recluse" and "Drunk" in possible_roles:
                            branch = deepcopy(w)
                            branch["possible_roles_per_untrustworthy"][untrustworthy_player] -= {"Drunk"}
                            next_worlds.append(branch)
                            poison_branch(w)
                        else:
                            next_worlds.append(w)
                        continue
                    if num_evil == 2:
                        # If trustworthy is Recluse, remove Drunk; else, prune
                        if trustworthy_role == "Recluse" and "Drunk" in possible_roles:
                            branch = deepcopy(w)
                            branch["possible_roles_per_untrustworthy"][untrustworthy_player] -= {"Drunk"}
                            next_worlds.append(branch)
                        else:
                            poison_branch(w)
                        continue

                # Case: both untrustworthy
                if a_alignment == "untrustworthy" and b_alignment == "untrustworthy":
                    a_poss = w["possible_roles_per_untrustworthy"][a_player]
                    b_poss = w["possible_roles_per_untrustworthy"][b_player]

                    if num_evil == 0:
                        # Two worlds: a is Drunk/Spy, b is Drunk/Spy (must pick opposite in each)
                        for a_role_choice, b_role_choice in [("Drunk", "Spy"), ("Spy", "Drunk")]:
                            if a_role_choice in a_poss and b_role_choice in b_poss:
                                branch = deepcopy(w)
                                branch["possible_roles_per_untrustworthy"][a_player] = {a_role_choice}
                                branch["possible_roles_per_untrustworthy"][b_player] = {b_role_choice}
                                next_worlds.append(branch)
                        poison_branch(w)
                        continue
                    if num_evil == 1:
                        # Two branches: each player limited to Spy or Drunk
                        for player, other in [(a_player, b_player), (b_player, a_player)]:
                            poss = w["possible_roles_per_untrustworthy"][player]
                            narrowed = poss & {"Spy", "Drunk"}
                            if narrowed:
                                branch = deepcopy(w)
                                branch["possible_roles_per_untrustworthy"][player] &= {"Spy", "Drunk"}
                                next_worlds.append(branch)
                        poison_branch(w)
                        continue
                    if num_evil == 2:
                        # Remove Drunk from both
                        poison_branch(w)
                        for player in (a_player, b_player):
                            poss = w["possible_roles_per_untrustworthy"][player]
                            if "Drunk" in poss:
                                w["possible_roles_per_untrustworthy"][player] -= {"Drunk"}
                        next_worlds.append(w)
                        continue
            current_worlds = next_worlds
    return current_worlds

def process_fortune_teller(world, TB_ROLES, setup_counts):
    def get_red_herring_constraint(constraints):
        for c in constraints:
            if "red herring" in c:
                return c["red herring"]
        return None
    
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "fortune teller"]
    if not info_items:
        return [world]  # No fortune teller claims

    current_worlds = [world]
    for info in info_items:
        night_results = info.get("night_results", [])
        claimer = info["claimer"]
        # print(info)

        for night_info in night_results:
            next_worlds = []
            night = night_info["night"]
            ping = night_info["ping"]
            a_player = night_info["player1"]
            b_player = night_info["player2"]
            if not isinstance(ping, bool):
                continue
            if len(a_player) <= 0 or len(b_player) <= 0:
                continue


            for w in current_worlds:
                roles = w["roles"]
                alignments = w["alignments"]
                possible_roles_per_untrustworthy = w["possible_roles_per_untrustworthy"]
                red_herring = get_red_herring_constraint(w.get("constraints", []))


                a_role = roles.get(a_player)
                b_role = roles.get(b_player)
                a_alignment = alignments.get(a_player)
                b_alignment = alignments.get(b_player)

                def poison_branch(w):
                    poisoned = branch_for_poisoner(w, TB_ROLES, setup_counts, night=night)
                    if poisoned:
                        next_worlds.append(poisoned)

                '''
                if Red Herring constraint exists:
                    if ping True:
                        if either is a recluse or red herring: continue
                        if both trustworthy:
                            prune world
                        if one trustworthy:
                            spin off 1 world where untrustworthy is Imp 2. poisoned world
                        if both untrustworthy:
                            spin off 3 worlds total: 2 worlds for either is imp, poison world
                    if ping False:
                        if either is a red herring:
                            poisoned world
                        if both trustworthy, continue
                        if one of each (trustworthy and untrustworthy): two worlds, untrustworthy is not demon OR poisioned world
                        if both untrustworthy: Two worlds, both untrustworthy's are not the demon, OR poisioned world

                no red herring currently:
                    if ping True:
                        if either is a recluse: continue
                        if both trustworthy:
                            spin off a world where both either are the red herring
                        if one trustworthy:
                            spin off 4 worlds 1. world where trustworthy is red herring 2. world where untrustworthy is drunk and red herring 3. world where untrustworthy is Imp 4. poisoned world
                        if both untrustworthy:
                            spin off 5 worlds total: spin 2 worlds for either being drunk red herring, 2 worlds for either is imp, poison world
                    if ping False:
                        if both trustworthy, continue
                        if one of each (trustworthy and untrustworthy): two worlds, untrustworthy is not demon OR poisioned world
                        if both untrustworthy: Two worlds, both untrustworthy's are not the demon, OR poisioned world
                
                '''
                is_recluse = a_role == "Recluse" or b_role == "Recluse"
                # Red Herring constraint exists
                if red_herring is not None:
                    is_red_herring = a_player == red_herring or b_player == red_herring

                    if ping:
                        if is_recluse or is_red_herring:
                            next_worlds.append(w)
                            continue
                        if a_alignment == "trustworthy" and b_alignment == "trustworthy":
                            continue
                        if (a_alignment == "trustworthy" and b_alignment == "untrustworthy") or \
                           (a_alignment == "untrustworthy" and b_alignment == "trustworthy"):
                            evil = a_player if a_alignment == "untrustworthy" else b_player
                            branch = deepcopy(w)
                            branch["possible_roles_per_untrustworthy"][evil] &= {"Imp"}
                            next_worlds.append(branch)
                            poison_branch(w)
                            continue
                        if a_alignment == "untrustworthy" and b_alignment == "untrustworthy":
                            for evil in (a_player, b_player):
                                poss = w["possible_roles_per_untrustworthy"][evil]
                                if "Imp" in poss:
                                    branch = deepcopy(w)
                                    branch["possible_roles_per_untrustworthy"][evil] &= {"Imp"}
                                    next_worlds.append(branch)
                            poison_branch(w)
                            continue

                    else:
                        if is_red_herring:
                            poison_branch(w)
                            continue
                        if a_alignment == "trustworthy" and b_alignment == "trustworthy":
                            next_worlds.append(w)
                            continue
                        if (a_alignment == "trustworthy" and b_alignment == "untrustworthy") or \
                           (a_alignment == "untrustworthy" and b_alignment == "trustworthy"):
                            evil = a_player if a_alignment == "untrustworthy" else b_player
                            if "Imp" in possible_roles_per_untrustworthy[evil]:
                                branch = deepcopy(w)
                                branch["possible_roles_per_untrustworthy"][evil] -= {"Imp"}
                                next_worlds.append(branch)
                            poison_branch(w)
                            continue
                        if a_alignment == "untrustworthy" and b_alignment == "untrustworthy":
                            for p in (a_player, b_player):
                                if "Imp" in possible_roles_per_untrustworthy[p]:
                                    branch = deepcopy(w)
                                    branch["possible_roles_per_untrustworthy"][p] -= {"Imp"}
                                    next_worlds.append(branch)
                            poison_branch(w)
                            continue

                # No red herring currently:
                else:
                    if ping:
                        if is_recluse:
                            next_worlds.append(w)
                            continue
                        if a_alignment == "trustworthy" and b_alignment == "trustworthy":
                            for h in (a_player, b_player):
                                branch = deepcopy(w)
                                branch.setdefault("constraints", []).append({"red herring": h})
                                next_worlds.append(branch)
                            continue
                        if (a_alignment == "trustworthy" and b_alignment == "untrustworthy") or \
                           (a_alignment == "untrustworthy" and b_alignment == "trustworthy"):
                            good = a_player if a_alignment == "trustworthy" else b_player
                            evil = a_player if a_alignment == "untrustworthy" else b_player
                            # 1. Trustworthy is herring
                            branch = deepcopy(w)
                            branch.setdefault("constraints", []).append({"red herring": good})
                            next_worlds.append(branch)
                            # 2. Evil is drunk and herring
                            if "Drunk" in possible_roles_per_untrustworthy[evil]:
                                branch = deepcopy(w)
                                branch.setdefault("constraints", []).append({"red herring": evil})
                                branch["possible_roles_per_untrustworthy"][evil] &= {"Drunk"}
                                next_worlds.append(branch)
                            # 3. Evil is Imp
                            if "Imp" in possible_roles_per_untrustworthy[evil]:
                                branch = deepcopy(w)
                                branch["possible_roles_per_untrustworthy"][evil] &= {"Imp"}
                                next_worlds.append(branch)
                            # 4. Poisoned
                            poison_branch(w)
                            continue
                        if a_alignment == "untrustworthy" and b_alignment == "untrustworthy":
                            for drunk in (a_player, b_player):
                                if "Drunk" in possible_roles_per_untrustworthy[drunk]:
                                    branch = deepcopy(w)
                                    branch.setdefault("constraints", []).append({"red herring": drunk})
                                    branch["possible_roles_per_untrustworthy"][drunk] &= {"Drunk"}
                                    next_worlds.append(branch)
                            for imp in (a_player, b_player):
                                if "Imp" in possible_roles_per_untrustworthy[imp]:
                                    branch = deepcopy(w)
                                    branch["possible_roles_per_untrustworthy"][imp] &= {"Imp"}
                                    next_worlds.append(branch)
                            poison_branch(w)
                            continue

                    else: # false ping
                        if a_alignment == "trustworthy" and b_alignment == "trustworthy":
                            next_worlds.append(w)
                            continue
                        if (a_alignment == "trustworthy" and b_alignment == "untrustworthy") or \
                           (a_alignment == "untrustworthy" and b_alignment == "trustworthy"):
                            evil = a_player if a_alignment == "untrustworthy" else b_player
                            if "Imp" in possible_roles_per_untrustworthy[evil]:
                                branch = deepcopy(w)
                                branch["possible_roles_per_untrustworthy"][evil] -= {"Imp"}
                                next_worlds.append(branch)
                            poison_branch(w)
                            continue
                        if a_alignment == "untrustworthy" and b_alignment == "untrustworthy":
                            for p in (a_player, b_player):
                                if "Imp" in possible_roles_per_untrustworthy[p]:
                                    branch = deepcopy(w)
                                    branch["possible_roles_per_untrustworthy"][p] -= {"Imp"}
                                    next_worlds.append(branch)
                            poison_branch(w)
                            continue
            current_worlds = [world for world in next_worlds if is_valid_world(world, TB_ROLES, setup_counts)]
    return current_worlds      

def is_valid_world(w, TB_ROLES, setup_counts):
    DEMONS = set(TB_ROLES["Demon"])
    MINIONS = set(TB_ROLES["Minion"])
    """
    Validates and prunes a world in place according to the following logic:
    1. Singleton possible_roles_per_untrustworthy are removed from all other untrustworthy possible lists (recurse until stable).
    2. Purges if any untrustworthy possible_roles is empty.
    3. Purges if no demon remains among all roles and possibilities.
    4. Purges if number of unique minion roles across all untrustworthy possibilities is less than minion setup count.
    5. Purges if world expects a drunk but there is no Drunk in possible roles.
    Returns pruned world (deepcopy) if valid, else None.
    """
    poss_roles = w.get("possible_roles_per_untrustworthy", {})
    changed = True

    # 1. Propagate singleton role removals (constraint satisfaction)
    while changed:
        changed = False
        # Find all singleton roles
        singletons = {list(roles)[0] for roles in poss_roles.values() if len(roles) == 1}
        for player, roles in poss_roles.items():
            if len(roles) > 1:
                before = set(roles)
                roles.difference_update(singletons)
                if before != roles:
                    changed = True
    # 2. Purge world if any possible_roles is empty
    if any(not roles for roles in poss_roles.values()):
        return None

    # 3. World must have at least one Demon, either fixed or as possibility
    demon_found = False
    for role in w["roles"].values():
        if role in DEMONS:
            demon_found = True
            break
    if not demon_found:
        for poss in poss_roles.values():
            if DEMONS & poss:
                demon_found = True
                break
    if not demon_found:
        return None

    # 4. Unique minion roles must >= setup_counts["minions"]
    minion_count_required = setup_counts.get("minions", 0)
    minion_poss = set()
    for poss in poss_roles.values():
        minion_poss |= (poss & MINIONS)
    if len(minion_poss) < minion_count_required:
        return None

    # 5. If world expects a Drunk but no Drunk possible anywhere
    if w.get("drunk_player"):
        has_drunk = any("Drunk" in poss for poss in poss_roles.values())
        if not has_drunk:
            return None

    return w
      

def deduction_pipeline(worlds, TB_ROLES, setup_counts, deduction_steps):
    """
    worlds: list of world dicts
    deduction_steps: list of deduction step functions
    Each step is applied to all current worlds in sequence.
    """
    current_worlds = worlds
    for step in deduction_steps:
        next_worlds = []
        for w in current_worlds:
            result = step(w, TB_ROLES, setup_counts)
            for world in result:
                valid_world = is_valid_world(world, TB_ROLES, setup_counts)
                if valid_world:
                    # print_world(-9, valid_world)
                    next_worlds.append(valid_world)
        current_worlds = next_worlds
        print(f"After {step.__name__}, {len(current_worlds)} worlds remain.")
        if not current_worlds:
            print("No worlds remain after deduction step:", step.__name__)
            break
    return current_worlds





def create_initial_world(player_names, trustworthy, claims, TB_ROLES, setup_counts):
    untrustworthy = [p for p in player_names if p not in trustworthy]
    n_untrustworthy = len(untrustworthy)
    n_minion = setup_counts.get("Minion", 0)
    n_demon = setup_counts.get("Demon", 1)
    roles_needed = n_minion + n_demon
    has_extra = n_untrustworthy > roles_needed

    all_evil_roles = set(TB_ROLES["Minion"] + TB_ROLES["Demon"])
    if has_extra:
        all_evil_roles.add("Drunk")
    possible_roles_per_untrustworthy ={}
    for p in untrustworthy:
        if claims[p].get("dead", False):
            roles = set(TB_ROLES["Minion"])
        else:
            roles = set(TB_ROLES["Minion"] + TB_ROLES["Demon"])
        if has_extra and not (claims.get(p, {}).get("role") in TB_ROLES.get("Outsider", [])):
            roles.add("Drunk")
        possible_roles_per_untrustworthy[p] = roles
    assigned_roles = [claims.get(p, {}).get("role") for p in trustworthy if claims.get(p, {}).get("role")]
    remaining_roles = {
        "Townsfolk": [r for r in TB_ROLES["Townsfolk"] if r not in assigned_roles],
        "Outsider": [r for r in TB_ROLES.get("Outsider", []) if r != "Drunk"],
        "Minion": TB_ROLES["Minion"][:],
        "Demon": TB_ROLES["Demon"][:]
    }
    info_to_resolve = []
    for p in trustworthy:
        c = claims.get(p, {})
        if c.get("role") in TB_ROLES["Townsfolk"]:
            info = construct_info_claim_dict(p, c)
            # print(info)
            if info:
                info_to_resolve.append(info)

    world = {
        "alignments": {p: ("trustworthy" if p in trustworthy else "untrustworthy") for p in player_names},
        "roles": {p: claims[p].get("role") if p in trustworthy and "role" in claims.get(p, {}) else None for p in player_names},
        "possible_roles_per_untrustworthy": possible_roles_per_untrustworthy,
        "required_minions": set(),
        "remaining_roles": remaining_roles,
        "constraints": [],
        "info_to_resolve": info_to_resolve,
        "drunk_player": has_extra,
        "meta": {
            "source": "initial",
            "history": []
        }
    }
    return world

def all_initial_worlds(player_names, TB_ROLES, setup_counts, claims, dead_players=None):
    n_players = len(player_names)
    ''' Sample Claims Structure
        "Fiona": {
            "role": "Chef",
            "pairs": 1
        },
        "Gina": {
            "role": "Fortune Teller",
    '''
    outsider_count = setup_counts["Outsider"]
    evil_count = setup_counts["Minion"] + setup_counts["Demon"]
    results = []

    for evil in itertools.combinations(player_names, evil_count):
        trustworthy = [p for p in player_names if p not in evil]
        num_trustworthy_outsiders = sum(
            1 for p in trustworthy
            if claims.get(p, {}).get("role") in TB_ROLES["Outsider"]
        )
        if num_trustworthy_outsiders == outsider_count or num_trustworthy_outsiders == outsider_count + 2:
            world = create_initial_world(player_names, trustworthy, claims, TB_ROLES, setup_counts)
            results.append(world)
        else:
            for to_remove in trustworthy:
                reduced_trustworthy = [p for p in trustworthy if p not in to_remove]
                world = create_initial_world(player_names, reduced_trustworthy, claims, TB_ROLES, setup_counts)
                results.append(world)
    return results

def print_world(idx, w):
    if idx == -1:
        return
    print(f"\n--- Final world #{idx+1} ---")
    print("Possible roles per untrustworthy:")
    for p, rset in w["possible_roles_per_untrustworthy"].items():
        print(f"  {p}: {rset}")
    print("Required minions:", w["required_minions"])
    print("Constraints:", w["constraints"])

def get_all_possible_imps(worlds):
    seen_untrustworthy_combinations = set()
    imps = set()
    for w in worlds:
        # Get the set of untrustworthy players (as a frozenset for hashability)
        untrustworthy = frozenset(
            p for p, alignment in w["alignments"].items() if alignment == "untrustworthy"
        )
        # Deduplicate worlds by their untrustworthy combo
        if untrustworthy in seen_untrustworthy_combinations:
            continue
        seen_untrustworthy_combinations.add(untrustworthy)
        # Find the Imp in this world (assuming roles is player: role)
        for p, roles in w["possible_roles_per_untrustworthy"].items():
            if "Imp" in roles:
                imps.add(p)
    return imps

def get_untrustworthy_correlation(worlds, all_players):
    # Build set of all unique untrustworthy combinations (keyed by player set)
    unique_uw_sets = set()
    for w in worlds:
        uw_set = frozenset(w["possible_roles_per_untrustworthy"].keys())
        unique_uw_sets.add(uw_set)
    
    # For each player, track which sets they appear in
    player_to_uw_sets = defaultdict(set)
    for uw_set in unique_uw_sets:
        for p in uw_set:
            player_to_uw_sets[p].add(uw_set)

    # Now, for each p1, compute the correlation with each p2
    correlation = {p1: {} for p1 in all_players}
    for p1 in all_players:
        uw_sets_with_p1 = player_to_uw_sets[p1]
        total = len(uw_sets_with_p1)
        for p2 in all_players:
            if total == 0:
                correlation[p1][p2] = 0.0
            else:
                # Count sets where both p1 and p2 appear
                both_count = sum(1 for s in uw_sets_with_p1 if p2 in s)
                correlation[p1][p2] = both_count / total
    return correlation

def construct_info_claim_dict(player, claim):
    """Given a player's name and claim dict, construct a deduction-ready info claim dict."""
    role = claim.get("role")
    # print(player)
    if role == "Washerwoman":
        return {
            "type": "washerwoman",
            "claimer": player,
            "seen_role": claim.get("seen_role"),
            "seen_players": claim.get("seen_players"),
        }
    elif role == "Librarian":
        # seen_role can be None (for "saw no outsiders") or the outsider role (for "one of X and Y is [Outsider]")
        # seen_players should be [] or length 2
        return {
            "type": "librarian",
            "claimer": player,
            "seen_role": claim.get("seen_role"),
            "seen_players": claim.get("seen_players", []),
        }
    elif role == "Investigator":
        # seen_role is always the minion role, seen_players is always 2 names
        return {
            "type": "investigator",
            "claimer": player,
            "seen_role": claim.get("seen_role"),
            "seen_players": claim.get("seen_players", []),
        }
    elif role == "Undertaker":
        return {
            "type": "undertaker",
            "claimer": player,
            "night_results": [
                {
                    "night": entry.get("night"),
                    "executed_player": entry.get("executed_player"),
                    "seen_role": entry.get("seen_role"),
                }
                for entry in claim.get("night_results", [])
            ]
        }
    elif role == "Ravenkeeper":
        return {
                "type": "ravenkeeper",
                "claimer": player,
                "seen_player": claim.get("seen_player"),
                "seen_role": claim.get("seen_role"),
                "night": claim.get("night"),
            }
    elif role == "Slayer": #TODO needs night for poison
        return {
            "type": "slayer",
            "night": claim.get("night"),
            "claimer": player,
            "shot_player": claim.get("shot_player"),
            "died": claim.get("died")
        }
    elif role == "Virgin":
        return {
            "type": "virgin",
            "claimer": player,
            "night": claim.get("night"),
            "first_nominator": claim.get("first_nominator"),
            "died": claim.get("died")
        }
    elif role == "Empath":
        return {
            "type": "empath",
            "claimer": player,
            "night_results": [
                {
                    "night": entry.get("night"),
                    "num_evil": entry.get("num_evil"),
                    "neighbor1": entry.get("neighbor1"),
                    "neighbor2": entry.get("neighbor2")
                }
                for entry in claim.get("night_results", [])
            ]
        }
    elif role == "Fortune Teller":
        return {
            "type": "fortune teller",
            "claimer": player,
            "night_results": [
                {
                    "night": entry.get("night"),
                    "ping": entry.get("ping"),
                    "player1": entry.get("player1"),
                    "player2": entry.get("player2")
                }
                for entry in claim.get("night_results", [])
            ]
        }
    elif role == "Chef":
        return {
            "type": "chef",
            "claimer": player,
            "pairs": claim.get("pairs")
        }
    # Add additional info roles here if desired
    return None

def chef_check(world, TB_ROLES, setup_counts, player_names):
    info_items = [info for info in world["info_to_resolve"] if info["type"] == "chef"]
    if not info_items:
        return True

    info = info_items[0]
    seen_pairs = info["pairs"]

    poss_evil_pair = 0
    must_evil_pair = 0

    prev_role_can_be_evil = world["roles"][player_names[-1]] in ["Imp", "Recluse", "Spy", "Baron", "Scarlet Woman", "Poisoner"]
    prev_role_must_be_evil = world["roles"][player_names[-1]] in ["Imp", "Baron", "Scarlet Woman", "Poisoner"]
    for player in player_names:
        cur_role_can_be_evil = world["roles"][player] in ["Imp", "Recluse", "Spy", "Baron", "Scarlet Woman", "Poisoner"]
        cur_role_must_be_evil = world["roles"][player] in ["Imp", "Baron", "Scarlet Woman", "Poisoner"]
        if cur_role_must_be_evil and prev_role_must_be_evil:
            must_evil_pair += 1
        if cur_role_can_be_evil and prev_role_can_be_evil:
            poss_evil_pair += 1
        prev_role_can_be_evil = cur_role_can_be_evil
        prev_role_must_be_evil = prev_role_must_be_evil

    # print(poss_evil_pair, must_evil_pair, seen_pairs)
    if seen_pairs <= poss_evil_pair and seen_pairs >= must_evil_pair:
        return True

    if "Poisoner" in world["roles"] and not "1_night_poisoned" in world["constraints"]:
        world["constraints"].append("1_night_poisoned")
        return True
    return False

def expand_all_to_concrete(final_worlds, TB_ROLES, setup_counts, player_names):
        """
        Given a list of worlds (final_worlds), expand each into all concrete worlds,
        and remove duplicates. Returns a list of unique, valid, concrete worlds.
        """
        unique_worlds = {}
        for world in final_worlds:
            untrustworthy = list(world["possible_roles_per_untrustworthy"].keys())
            possible_roles_lists = [list(world["possible_roles_per_untrustworthy"][p]) for p in untrustworthy]
            for assignment in product(*possible_roles_lists):
                # Enforce unique roles among untrustworthy (remove this if not needed)
                if len(set(assignment)) < len(assignment):
                    continue
                w = deepcopy(world)
                for p, role in zip(untrustworthy, assignment):
                    w["roles"][p] = role
                    w["possible_roles_per_untrustworthy"][p] = {role}
                # Only add if valid and not already seen
                if is_valid_world(w, TB_ROLES, setup_counts) and chef_check(w, TB_ROLES, setup_counts, player_names):
                    num_untrustworthy = len(w["possible_roles_per_untrustworthy"])
                    good_players = len(player_names) - num_untrustworthy
                    drunk_factor = 1
                    if setup_counts["Minion"] + setup_counts["Demon"] < num_untrustworthy:
                        drunk_factor = 1/ (good_players + 1) 
                    w["weight"] = drunk_factor / good_players ** len(w["constraints"])
                    key = world_key(w)
                    if key not in unique_worlds:
                        unique_worlds[key] = w
        return list(unique_worlds.values())

def compute_role_probs(worlds, all_players):
    """
    Returns:
        evil_probs: {player: float} % chance player is evil
        imp_probs: {player: float} % chance player is Imp
    """
    evil_probs = {p: 0.0 for p in all_players}
    imp_probs = {p: 0.0 for p in all_players}
    total_weight = 0.0

    for w in worlds:
        weight = w.get("weight", 1.0)  # Use your world's weight, or 1 if not present

        # You must have "alignments" and "roles" finalized for each world!
        for p in all_players:
            # Evil: player is untrustworthy and not Drunk
            if w["alignments"][p] == "untrustworthy":
                # Only role should be set, but just in case:
                role = w["roles"].get(p)
                if role and role != "Drunk":
                    evil_probs[p] += weight
                if role == "Imp":
                    imp_probs[p] += weight

        total_weight += weight

    # Normalize to get probabilities (percentages)
    if total_weight > 0:
        for p in all_players:
            evil_probs[p] = evil_probs[p] / total_weight * 100
            imp_probs[p] = imp_probs[p] / total_weight * 100

    return evil_probs, imp_probs

# TODO fix chef wraparound

# Example usage
if __name__ == "__main__":
    player_names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Fiona", "Gina", "Holly"]

    TB_ROLES = {
        "Townsfolk": ["Chef", "Washerwoman", "Slayer", "Fortune Teller", "Undertaker", "Ravenkeeper", "Librarian", "Investigator", "Monk", "Virgin", "Empath"],
        "Outsider": ["Drunk", "Recluse", "Saint", "Butler"],
        "Minion": ["Poisoner", "Scarlet Woman", "Baron", "Spy"],
        "Demon": ["Imp"]
    }

    setup_counts = {
        "Minion": 1,
        "Demon": 1,
        "Outsider": 1,
        "Townsfolk": 5
    }

    claims = {
        "Alice": {
            "role": "Fortune Teller",
            "night_results": [
                {"night": 1, "ping": True, "player1": "Alice", "player2": "Eve"},
                {"night": 2, "ping": True, "player1": "Bob", "player2": "Fiona"},
                {"night": 3, "ping": True, "player1": "Alice", "player2": "Carol"},

            ],
            # "dead": True
        },
        "Bob": {
            "role": "Recluse",
            # "night_results": [
            #     {"night": 1, "ping": True, "player1": "Bob", "player2": "Fiona"},
            #     {"night": 2, "ping": False, "player1": "Bob", "player2": "Eve"}
            # ],
            "dead": True
        },
        "Carol": {
            "role": "Slayer",
            "dead": True
            # "shot_player": "Fiona",
            # "died": False,
            # "night": 2
            # "night_results": [
            #     {"night": 2, "executed_player": "Fiona", "seen_role": "Chef"},
            #     # {"night": 3, "executed_player": "Dave", "seen_role": "Investigator"},
            #     # {"night": 4, "executed_player": "Gina", "seen_role": "Chef"}
            # ],
            # "dead": True
        },
        "Dave": {
            "role": "Ravenkeeper",
            "seen_player": "Carol",
            "seen_role": "Slayer",
            "night": 3,
            "dead": True
            # "night_results": [
            #     {"night": 1, "num_evil": 1, "neighbor1": "Carol", "neighbor2": "Eve"}
            # ],
            # "dead": True
        },
        "Eve": {
            "role": "Washerwoman",
            "seen_role": "Virgin",
            "seen_players": ["Dave", "Fiona"],
            "dead": True
            # "night": 2,
            # "seen_role": "Empath",
            # "seen_player": "Gina"
        },
        "Fiona": {
            "role": "Virgin",
            # "night_results": [
            #     {"night": 2, "seen_role": "Imp", "executed_player": "Dave"},
            #     {"night": 3, "seen_role": "Fortune Teller", "executed_player": "Alice"}
            # ],
            "dead": True
        },
        "Gina": {
            "role": "Butler",
            # "night_results": [
            #     {"night": 1, "num_evil": 1, "neighbor1": "Holly", "neighbor2": "Fiona"}
            # ],
            # "dead": True
        },
        "Holly": {
            "role": "Mayor",
            # "seen_role": "Undertaker",
            # "seen_players": ["Bob", "Gina"]
            # "dead": True,
            # "first_nominator": "Fiona",
            # "died": False
        }
    }

    # trustworthy = ["Alice", "Bob", "Carol", "Fiona", "Gina", "Holly"]  
    # worlds = [create_initial_world(player_names, trustworthy, claims, TB_ROLES, setup_counts)]
    # List of deduction steps to run in order

    worlds = all_initial_worlds(player_names, TB_ROLES, setup_counts, claims)
    deduction_steps = [
        starting_check,
        process_washerwoman,
        process_librarian,
        process_investigator,
        process_undertaker,
        process_ravenkeeper,
        process_slayer,
        process_empath,
        process_virgin,
        process_fortune_teller,
        # ...add more deduction steps here as you implement them...
    ]



    print("=== Running deduction pipeline ===")
    final_worlds = deduction_pipeline(worlds, TB_ROLES, setup_counts, deduction_steps)

    print(f"\nWorlds left after all deduction: {len(final_worlds)}")
    # for idx, w in enumerate(final_worlds):

        # print_world(idx, w)
    # final_worlds = remove_subset_worlds(final_worlds)
    # print(f"\nWorlds left after reduction: {len(final_worlds)}")
    # for idx, w in enumerate(final_worlds):
    #     print_world(idx, w)

    def world_key(world):
        """
        Create a canonical (hashable) key for a concrete world.
        Here, just the roles and constraints (sorted) are included for uniqueness.
        """
        # Use tuple of sorted (player, role) and sorted (constraint as tuple of items)
        def normalize_constraint(c):
            if isinstance(c, dict):
                # Sorted tuple of items, for deterministic order
                return ("dict", tuple(sorted(c.items())))
            else:
                # Just use the string directly
                return ("str", str(c))
        roles_key = tuple(sorted(world["roles"].items()))
        constraints_key = tuple(sorted((normalize_constraint(c) for c in world.get("constraints", [])), key=str)) 
        return (roles_key, constraints_key)


    # for i, w in enumerate(expanded_worlds, 1):
    #     print(f"--- Concrete world #{i} ---")
    #     print("Roles:", w["roles"])
    #     print("Constraints:", w.get("constraints", []))
    # ... and so on ...

    final_worlds = expand_all_to_concrete(final_worlds, TB_ROLES, setup_counts, player_names)
    # corr = get_untrustworthy_correlation(final_worlds, player_names)
    for i in range(len(final_worlds)):
        print_world(i, final_worlds[i])
    # for p1 in player_names:
    #     print(f"{p1}: ", end='')
    #     print(", ".join(f"{p2}: {corr[p1][p2]:.2f}" for p2 in player_names))

    evil_prob, imp_prob = compute_role_probs(final_worlds, player_names)

    for p in player_names:
        print(f"{p}: {evil_prob[p]:.1f}% evil, {imp_prob[p]:.1f}% Imp")