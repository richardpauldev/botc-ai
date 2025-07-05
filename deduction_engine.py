import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from copy import deepcopy

def construct_info_claim_dict(player: str, claim: dict) -> Optional[dict]:
    """Construct a simplified info-claim dictionary from a raw claim."""
    role = claim.get("role")
    if not role:
        return None

    role_fields = {
        "Washerwoman": ["seen_role", "seen_players"],
        "Librarian": ["seen_role", "seen_players"],
        "Investigator": ["seen_role", "seen_players"],
        "Undertaker": ["night_results"],
        "Ravenkeeper": ["seen_player", "seen_role", "night"],
        "Slayer": ["night", "shot_player", "died"],
        "Virgin": ["night", "first_nominator", "died"],
        "Empath": ["night_results"],
        "Fortune Teller": ["night_results"],
        "Chef": ["pairs"],
    }

    fields = role_fields.get(role)
    if not fields:
        return None

    info = {"type": role.lower(), "claimer": player}

    nr_subfields = {
        "undertaker": ["night", "executed_player", "seen_role"],
        "empath": ["night", "num_evil", "neighbor1", "neighbor2"],
        "fortune teller": ["night", "ping", "player1", "player2"],
    }

    for f in fields:
        value = claim.get(f)
        if f == "night_results":
            if isinstance(value, list):
                subfields = nr_subfields.get(role.lower())
                if subfields:
                    info[f] = [
                        {k: entry.get(k) for k in subfields}
                        for entry in value
                    ]
                else:
                    info[f] = value
            else:
                info[f] = []
        else:
            info[f] = value
    return info

@dataclass
class WorldState:
    """Representation of a possible game world."""

    roles: Dict[str, str]
    poison_nights: List[int] = field(default_factory=list)
    deaths: List[dict] = field(default_factory=list)
    claims: Dict[str, dict] = field(default_factory=dict)
    good_role_options: Dict[str, List[str]] = field(default_factory=dict)
    red_herring: Optional[str] = None

ONGOING_INFO_ROLES = {"Empath", "Fortune Teller", "Undertaker", "Ravenkeeper", "Virgin", "Slayer"}

def generate_all_worlds(
    player_names, all_minion_roles, m_minions, claims, TB_ROLES, outsider_count, deaths=None, pov_player=None
):
    worlds = []
    n = len(player_names)
    players = list(player_names)

    if deaths is None:
        deaths = []

    for minion_role_combo in itertools.combinations(all_minion_roles, m_minions):
        minion_role_combo_set = set(minion_role_combo)
        for minion_players in itertools.combinations(players, m_minions):
            for minion_role_perm in itertools.permutations(minion_role_combo):
                minion_dict = dict(zip(minion_players, minion_role_perm))
                non_minions = [p for p in players if p not in minion_players]
                for imp_player in non_minions:
                    evil = set(minion_players) | {imp_player}
                    if pov_player and pov_player in evil:
                        continue
                    trustworthy = [p for p in players if p not in evil]
                    num_trustworthy_outsiders = sum(
                        1 for p in trustworthy
                        if claims.get(p, {}).get("role") in TB_ROLES["Outsider"]
                    )
                    
                    if num_trustworthy_outsiders > outsider_count:
                        if "Baron" not in minion_role_combo_set:
                            continue  # Skip worlds without Baron
                    else:
                        if "Baron" in minion_role_combo_set:
                            continue # Skip worlds with Baron

                    if num_trustworthy_outsiders == outsider_count or num_trustworthy_outsiders == outsider_count + 2:
                        # No Drunk in evil
                        for drunk_player in [None]:  # No drunk, so no assignment
                            roles = {}
                            for p in players:
                                if p in minion_dict:
                                    roles[p] = minion_dict[p]
                                elif p == imp_player:
                                    roles[p] = "Imp"
                                else:
                                    role = claims.get(p, {}).get("role")
                                    if role:
                                        roles[p] = role
                                    else:
                                        roles[p] = "Good"
                            parsed_claims = {}
                            for pl, c in claims.items():
                                info = construct_info_claim_dict(pl, c)
                                if info:
                                    parsed_claims[pl] = info
                            worlds.append(
                                WorldState(
                                    roles=roles,
                                    claims=parsed_claims,
                                    good_role_options={
                                        pl: c["roles"]
                                        for pl, c in claims.items()
                                        if "roles" in c
                                    },
                                    deaths=list(deaths)
                                )
                            )
                    else:
                        # Outsider count doesn't match: must "remove" a trustworthy to allow Drunk as evil
                        for drunk_player in trustworthy:
                            reduced_trustworthy = [p for p in trustworthy if p != drunk_player]
                            # Only assign Drunk to someone who is not already claiming outsider
                            if claims.get(drunk_player, {}).get("role") in TB_ROLES["Outsider"]:
                                continue
                            roles = {}
                            for p in players:
                                if p in minion_dict:
                                    roles[p] = minion_dict[p]
                                elif p == imp_player:
                                    roles[p] = "Imp"
                                elif p == drunk_player:
                                    roles[p] = "Drunk"
                                else:
                                    role = claims.get(p, {}).get("role")
                                    if role:
                                        roles[p] = role
                                    else:
                                        roles[p] = "Good"
                                
                            if len(roles) == n:
                                parsed_claims = {}
                                for pl, c in claims.items():
                                    info = construct_info_claim_dict(pl, c)
                                    if info:
                                        parsed_claims[pl] = info
                                worlds.append(
                                    WorldState(
                                        roles=roles,
                                        claims=parsed_claims,
                                        good_role_options={
                                            pl: c["roles"]
                                            for pl, c in claims.items()
                                            if "roles" in c
                                        },
                                        deaths=list(deaths)
                                    )
                                )
    return worlds


def _claims_of_type(world: WorldState, claim_type: str) -> List[str]:
    """Return all players who claim the given role type."""
    return [p for p, info in world.claims.items() if info.get("type") == claim_type]


def _trustworthy_claims(world: WorldState, claim_type: str) -> List[dict]:
    """Return claim info for the trustworthy player(s) with the given role."""
    result = []
    # print("asdiljfk", world.claims, world.roles, claim_type)
    for player, role in world.roles.items():
        if role.lower() == claim_type:
            info = world.claims.get(player)
            if info and info.get("type") == claim_type:
                result.append(info)
    return result


def _max_night_from_world(world: WorldState) -> int:
    """Return the maximum referenced night number in a world."""
    max_n = 1
    for c in world.claims.values():
        n = c.get("night")
        if isinstance(n, int) and n > max_n:
            max_n = n
        for entry in c.get("night_results", []):
            e_n = entry.get("night")
            if isinstance(e_n, int) and e_n > max_n:
                max_n = e_n
    for d in world.deaths:
        n = d.get("night")
        if isinstance(n, int) and n > max_n:
            max_n = n
    for n in world.poison_nights:
        if n > max_n:
            max_n = n
    return max_n


def _is_alive(world: WorldState, player: str, night: int) -> bool:
    """Return True if player is alive at the start of the given night."""
    for d in world.deaths:
        if d.get("player") == player:
            d_n = d.get("night", 0)
            if isinstance(d_n, int) and d_n <= night:
                return False
    return True


def _poisoner_alive(world: WorldState, night: int) -> bool:
    for p, r in world.roles.items():
        if r == "Poisoner" and _is_alive(world, p, night):
            return True
    return False


def _branch_poison(world: WorldState, night: int) -> List[WorldState]:
    if not _poisoner_alive(world, night):
        return []
    if night in world.poison_nights:
        return []
    w = deepcopy(world)
    w.poison_nights.append(night)
    return [w]


def _branch_red_herring(world: WorldState, night: int, TB_ROLES) -> List[WorldState]:
    if world.red_herring is not None:
        return []
    candidates = set()
    for info in _trustworthy_claims(world, "fortune teller"):
        for entry in info.get("night_results", []):
            if entry.get("night") != night:
                continue
            players = [entry.get("player1"), entry.get("player2")]
            ping = bool(entry.get("ping"))
            demon_seen = any(world.roles.get(p) in ["Imp", "Recluse"] for p in players)
            if ping and not demon_seen:
                for cand in players:
                    role = world.roles.get(cand)
                    if role in TB_ROLES.get("Townsfolk", []) + TB_ROLES.get("Outsider", []):
                        candidates.add(cand)
    result = []
    for cand in candidates:
        w = deepcopy(world)
        w.red_herring = cand
        result.append(w)
    return result


def _alive_players(world: WorldState, night: int) -> List[str]:
    """Return list of players alive at the start of the given night."""
    return [p for p in world.roles if _is_alive(world, p, night)]

def _world_weight(world: WorldState, TB_ROLES) -> float:
    evil_roles = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))

    good_players = [p for p, r in world.roles.items() if r not in evil_roles]
    num_good = len(good_players)
    if num_good == 0:
        return 1.0
    
    weight = 1.0

    # Drunk probability ---------------------------------------------------
    if any(r == "Drunk" for r in world.roles.values()):
        non_drunk_outsiders = sum(
            1
            for r in world.roles.values()
            if r in TB_ROLES.get("Outsider", []) and r != "Drunk"
        )
        denom = num_good - non_drunk_outsiders
        if denom <= 0:
            denom = num_good
        weight *= 1.0 / denom

    # Poison probability --------------------------------------------------
    for pn in world.poison_nights:
        if pn == 1:
            weight *= 1.0 / num_good
        else:
            alive_ongoing = [
                p
                for p in good_players
                if world.roles[p] in ONGOING_INFO_ROLES and _is_alive(world, p, pn)
            ]
            denom = len(alive_ongoing)
            if denom <= 0:
                denom = num_good
            weight *= 1.0 / denom

    # Fortune Teller red herring ----------------------------------------
    if world.red_herring is not None:
        weight *= 1.0 / num_good

    return weight



def _demon_alive(world: WorldState, night: int) -> bool:
    for p, r in world.roles.items():
        if r == "Imp" and _is_alive(world, p, night):
            return True
    return False


def _handle_imp_day(world: WorldState, night: int, TB_ROLES) -> List[WorldState]:
    alive_before = len(_alive_players(world, night)) + 1
    sw_candidates = [p for p, r in world.roles.items() if r == "Scarlet Woman" and _is_alive(world, p, night)]
    if sw_candidates and alive_before >= 5:
        w = deepcopy(world)
        w.roles[sw_candidates[0]] = "Imp"
        return [w]
    return []


def _handle_imp_night(world: WorldState, night: int, TB_ROLES) -> List[WorldState]:
    minions = [p for p, r in world.roles.items() if r in TB_ROLES.get("Minion", []) and _is_alive(world, p, night)]
    if not minions:
        return []
    if any(world.roles[p] == "Scarlet Woman" for p in minions):
        sw = next(p for p in minions if world.roles[p] == "Scarlet Woman")
        w = deepcopy(world)
        w.roles[sw] = "Imp"
        return [w]
    result = []
    for m in minions:
        w = deepcopy(world)
        w.roles[m] = "Imp"
        result.append(w)
    return result


def _apply_imp_death(world: WorldState, night: int, TB_ROLES) -> List[WorldState]:
    worlds = [world]
    for d in world.deaths:
        if d.get("night") != night:
            continue
        if world.roles.get(d.get("player")) != "Imp":
            continue
        time = d.get("time", "night")
        next_worlds = []
        for w in worlds:
            if time == "day":
                branch = _handle_imp_day(w, night, TB_ROLES)
            else:
                branch = _handle_imp_night(w, night, TB_ROLES)
            for nb in branch:
                if _demon_alive(nb, night):
                    next_worlds.append(nb)
        worlds = next_worlds
    return worlds

def process_soldier(world: WorldState, night: int, TB_ROLES) -> bool:
    """Return True if the Soldier is recorded as dying at night."""
    for d in world.deaths:
        if d.get("night") == night and d.get("time", "night") == "night":
            if world.roles.get(d.get("player")) == "Soldier":
                return True
    return False



def process_washerwoman(world: WorldState, night: int, TB_ROLES) -> bool:
    if night != 1:
        return True
    for info in _trustworthy_claims(world, "washerwoman"):
        players = info.get("seen_players") or []
        role = info.get("seen_role")
        if players and role:
            a, b = players
            if world.roles.get(a) != role and world.roles.get(b) != role:
                if world.roles.get(a) == "Spy" or world.roles.get(b) == "Spy":
                    return True
                return False
    return True


def process_librarian(world: WorldState, night: int, TB_ROLES) -> bool:
    if night != 1:
        return True
    for info in _trustworthy_claims(world, "librarian"):
        players = info.get("seen_players", [])
        role = info.get("seen_role")
        if role is None:
            if any(world.roles.get(p) in TB_ROLES.get("Outsider", []) for p in world.roles):
                return False
        else:
            if not any(world.roles.get(p) == role for p in players):
                if any(world.roles.get(p) == "Spy" for p in players):
                    return True
                return False
    return True


def process_investigator(world: WorldState, night: int, TB_ROLES) -> bool:
    if night != 1:
        return True
    for info in _trustworthy_claims(world, "investigator"):
        players = info.get("seen_players", [])
        role = info.get("seen_role")
        if not any(world.roles.get(p) == role or world.roles.get(p) == "Recluse" for p in players):
            return False
    return True


def process_undertaker(world: WorldState, night: int, TB_ROLES) -> bool:
    for info in _trustworthy_claims(world, "undertaker"):
        for entry in info.get("night_results", []):
            if entry.get("night") == night:
                executed = entry.get("executed_player")
                seen_role = entry.get("seen_role")
                if world.roles.get(executed) != seen_role and not world.roles.get(executed) == "Spy":
                    return False
    return True


def process_ravenkeeper(world: WorldState, night: int, TB_ROLES) -> bool:
    # print("raven", _trustworthy_claims(world, "ravenkeeper"))
    for info in _trustworthy_claims(world, "ravenkeeper"):
        # print(info)
        if info.get("night") == night:
            if world.roles.get(info.get("seen_player")) != info.get("seen_role") and not world.roles.get(info.get("seen_player")) == "Spy":
                return False
    return True


def process_slayer(world: WorldState, night: int, TB_ROLES) -> bool:
    for info in _trustworthy_claims(world, "slayer"):
        if info.get("night") == night:
            shot = info.get("shot_player")
            died = info.get("died")
            claimer = info.get("claimer")
            is_imp = world.roles.get(shot) in ["Imp", "Recluse"]
            if died and not is_imp:
                return False
            if not died and is_imp:
                return False
            if died and claimer:
                r = world.roles.get(claimer)
                evil = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))
                if r in evil or r == "Drunk":
                    return False
    return True


def process_virgin(world: WorldState, night: int, TB_ROLES) -> bool:
    townsfolk = set(TB_ROLES.get("Townsfolk", []))
    for info in _trustworthy_claims(world, "virgin"):
        if info.get("night") == night:
            nom = info.get("first_nominator")
            died = info.get("died")
            claimer = info.get("claimer")
            if nom:
                nom_role = world.roles.get(nom)
                if died and nom_role not in townsfolk and nom_role != "Spy":
                    return False
                if not died and nom_role in townsfolk:
                    return False
    return True 


def process_empath(world: WorldState, night: int, TB_ROLES) -> bool:
    evil = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))
    for info in _trustworthy_claims(world, "empath"):
        for entry in info.get("night_results", []):
            if entry.get("night") == night:
                neighbors = [entry.get("neighbor1"), entry.get("neighbor2")]
                count = sum(1 for p in neighbors if world.roles.get(p) in evil)
                spy_nieghbor = any(True for p in neighbors if world.roles.get(p) == "Spy")
                if spy_nieghbor:
                    if count != entry.get("num_evil") - 1 or count != entry.get("num_evil"):
                        return False
                elif count != entry.get("num_evil"):
                    return False
    return True


def process_fortune_teller(world: WorldState, night: int, TB_ROLES) -> bool:
    for info in _trustworthy_claims(world, "fortune teller"):
        for entry in info.get("night_results", []):
            if entry.get("night") == night:
                players = [entry.get("player1"), entry.get("player2")]
                demon_seen = any(world.roles.get(p) == "Imp" or world.roles.get(p) == "Recluse" for p in players)
                if world.red_herring and world.red_herring in players:
                    demon_seen = True
                if bool(entry.get("ping")) != demon_seen:
                    print("rejected", world.red_herring)
                    return False
    return True


def process_chef(world: WorldState, night: int, TB_ROLES) -> bool:
    if night != 1:
        return True
    for info in _trustworthy_claims(world, "chef"):
        pairs = info.get("pairs")
        if pairs is None:
            continue
        players = sorted(world.roles)  # Or whatever order you want
        
        roles = [world.roles[p] for p in players]
        evil_roles = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))
        ambiguous_indexes = [i for i, r in enumerate(roles) if r in {"Spy", "Recluse"}]
        # Prepare base evil list, with ambiguous as None
        base_evil = []
        for r in roles:
            if r in evil_roles:
                base_evil.append(True)
            elif r in {"Spy", "Recluse"}:
                base_evil.append(None)
            else:
                base_evil.append(False)
        
        # For each combination of ambiguous roles as evil/good
        bounds = []
        for assignment in itertools.product([False, True], repeat=len(ambiguous_indexes)):
            evil_list = base_evil[:]
            for idx, as_evil in zip(ambiguous_indexes, assignment):
                evil_list[idx] = as_evil
            count = 0
            prev = evil_list[-1]
            for cur in evil_list:
                if prev and cur:
                    count += 1
                prev = cur
            bounds.append(count)
        
        min_pairs = min(bounds)
        max_pairs = max(bounds)
        if not (min_pairs <= pairs <= max_pairs):
            return False
    return True


ROLE_STEPS = [
    process_washerwoman,
    process_librarian,
    process_investigator,
    process_undertaker,
    process_ravenkeeper,
    process_slayer,
    process_virgin,
    process_empath,
    process_fortune_teller,
    process_chef,
    process_soldier
]


def deduction_pipeline(worlds, TB_ROLES):
    """Apply deduction role by role, night by night."""
    if not worlds:
        return []
    max_night = max(_max_night_from_world(w) for w in worlds)
    current = worlds
    for night in range(1, max_night + 1):
        for step in ROLE_STEPS:
            next_worlds = []
            for w in current:
                if step(w, night, TB_ROLES):
                    next_worlds.append(w)
                else:
                    if step is process_fortune_teller:
                        next_worlds.extend(_branch_red_herring(w, night, TB_ROLES))
                    next_worlds.extend(_branch_poison(w, night))
            current = next_worlds
            if not current:
                break
        if current:
            updated = []
            for w in current:
                updated.extend(_apply_imp_death(w, night, TB_ROLES))
            current = updated
        if not current:
            break
    return current

def get_untrustworthy_correlation(worlds, all_players, TB_ROLES):
    """Return correlation matrix of players appearing together as evil."""
    evil_roles = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))
    unique_sets = set()
    for w in worlds:
        uw_set = frozenset(p for p, r in w.roles.items() if r in evil_roles)
        unique_sets.add(uw_set)

    player_to_sets = {p: set() for p in all_players}
    for uw_set in unique_sets:
        for p in uw_set:
            player_to_sets[p].add(uw_set)

    correlation = {p1: {} for p1 in all_players}
    for p1 in all_players:
        sets_with_p1 = player_to_sets[p1]
        total = len(sets_with_p1)
        for p2 in all_players:
            if total == 0:
                correlation[p1][p2] = 0.0
            else:
                both_count = sum(1 for s in sets_with_p1 if p2 in s)
                correlation[p1][p2] = both_count / total
    return correlation


def compute_role_probs(worlds, all_players, TB_ROLES):
    """Return probability each player is evil or specifically the Imp."""
    evil_roles = set(TB_ROLES.get("Minion", []) + TB_ROLES.get("Demon", []))
    evil_probs = {p: 0.0 for p in all_players}
    imp_probs = {p: 0.0 for p in all_players}

    weights = []
    for w in worlds:
        weights.append(_world_weight(w, TB_ROLES))
    
    total = sum(weights)

    if total == 0:
        return evil_probs, imp_probs

    for w, weight in zip(worlds, weights):
        for p in all_players:
            role = w.roles.get(p)
            if role in evil_roles:
                evil_probs[p] += weight
            if role == "Imp":
                imp_probs[p] += weight

    for p in all_players:
        evil_probs[p] = evil_probs[p] / total * 100
        imp_probs[p] = imp_probs[p] / total * 100

    return evil_probs, imp_probs


def deduce_game(game, pov_player=None):
    """Run deduction on a ``Game`` instance from ``game.py``.

    ``pov_player`` specifies the name of the player making the deduction. Any
    worlds where that player is evil are discarded.
    """
    TB_ROLES = {a.value if hasattr(a, "value") else a: roles for a, roles in game.TROUBLE_BREWING_ROLES.items()}
    player_names = [p.name for p in game.players]
    all_minion_roles = TB_ROLES["Minion"]
    num_players = len(game.players)
    outsider_count = (num_players - 1) % 3
    if num_players <= 9:
        m_minions = 1
    elif num_players <= 12:
        m_minions = 2
    else:
        m_minions = 3
    claims = {p.name: p.claim for p in game.players if getattr(p, "claim", None)}
    worlds = generate_all_worlds(
        player_names,
        all_minion_roles,
        m_minions,
        claims,
        TB_ROLES,
        outsider_count,
        deaths=[],
        pov_player=pov_player,
    )
    deduced = deduction_pipeline(worlds, TB_ROLES)
    evil_prob, imp_prob = compute_role_probs(deduced, player_names, TB_ROLES)
    return evil_prob, imp_prob

if __name__ == "__main__":
    player_names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Gina", "Holly"]
    all_minion_roles = ["Poisoner", "Scarlet Woman", "Baron", "Spy"]
    m_minions = 1
    claims = {
        "Alice": {
            "role": "Empath",
            "night_results": [
                {"night": 1, "num_evil": 0, "player1": "Bob", "player2": "Holly"},
            ],
            # "dead": True
        },
        "Bob": {
            "role": "Washerwoman",
            "seen_role": "Librarian",
            "seen_players": ["Carol", "Holly"]
            # "night_results": [
            #     {"night": 1, "ping": True, "player1": "Bob", "player2": "Fiona"},
            #     {"night": 2, "ping": False, "player1": "Bob", "player2": "Eve"}
            # ],
            # "dead": True
        },
        "Carol": {
            "role": "Librarian",
            "seen_role": "Recluse",
            "seen_players": ["Dave", "Holly"]
            # "dead": True
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
            "role": "Investigator",
            "seen_role": "Scarlet Woman",
            "seen_players": ["Carol", "Frank"]
            # "dead": True
            # "night_results": [
            #     {"night": 1, "num_evil": 1, "neighbor1": "Carol", "neighbor2": "Eve"}
            # ],
            # "dead": True
        },
        "Eve": {
            "role": "Soldier",
            # "seen_role": "Virgin",
            # "seen_players": ["Dave", "Fiona"],
            # "dead": True
            # "night": 2,
            # "seen_role": "Empath",
            # "seen_player": "Gina"
        },
        "Frank": {
            "role": "Chef",
            "evil_pairs": 1,
            "night": 1
            # "night_results": [
            #     {"night": 2, "seen_role": "Imp", "executed_player": "Dave"},
            #     {"night": 3, "seen_role": "Fortune Teller", "executed_player": "Alice"}
            # ],
            # "dead": True
        },
        "Gina": {
            "role": "Mayor",
            # "night_results": [
            #     {"night": 1, "num_evil": 1, "neighbor1": "Holly", "neighbor2": "Fiona"}
            # ],
            # "dead": True
        },
        "Holly": {
            "role": "Recluse",
            # "seen_role": "Undertaker",
            # "seen_players": ["Bob", "Gina"]
            # "dead": True,
            # "first_nominator": "Fiona",
            # "died": False
        }
    }
    TB_ROLES = {
        "Townsfolk": [
            "Chef",
            "Washerwoman",
            "Slayer",
            "Fortune Teller",
            "Undertaker",
            "Ravenkeeper",
            "Librarian",
            "Investigator",
            "Monk",
            "Virgin",
            "Empath",
            "Soldier",
            "Mayor",
        ],
        "Outsider": ["Drunk", "Recluse", "Saint", "Butler"],
        "Minion": ["Poisoner", "Scarlet Woman", "Baron", "Spy"],
        "Demon": ["Imp"],
    }
    outsider_count = 1

    # Add deaths here 
    # {"player": "X", "night": -1, "time": "day" OR "night"}
    deaths = [{"player": "Holly", "night": 1, "time": "day"},
              {"player": "Alice", "night": 2, "time": "night"},
              {"player": "Frank", "night": 3, "time": "night"}]

    worlds = generate_all_worlds(
        player_names, all_minion_roles, m_minions, claims, TB_ROLES, outsider_count, deaths=deaths
    )
    print(f"Generated {len(worlds)} worlds before deduction.")
    deduced = deduction_pipeline(worlds, TB_ROLES)
    print(f"After deduction: {len(deduced)} worlds remain.")
    for w in deduced[:3]:
        print(w)
    
    corr = get_untrustworthy_correlation(deduced, player_names, TB_ROLES)
    print("\nUntrustworthy correlation:")
    header = " " * 10 + " ".join(f"{p:>10}" for p in player_names)
    print(header)
    for p1 in player_names:
        row = f"{p1:>10} " + " ".join(
            f"{corr[p1][p2]*100:>9.1f}%" for p2 in player_names
        )
        print(row)

    evil_prob, imp_prob = compute_role_probs(deduced, player_names, TB_ROLES)
    print("\nRole probabilities:")
    for p in player_names:
        print(f"{p}: {evil_prob[p]:.1f}% evil, {imp_prob[p]:.1f}% Imp")