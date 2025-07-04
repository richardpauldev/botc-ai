import like_version_4 as v4
import like_version_5 as v5

player_names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Fiona", "Gina", "Holly"]
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
    ],
    "Outsider": ["Drunk", "Recluse", "Saint", "Butler"],
    "Minion": ["Poisoner", "Scarlet Woman", "Baron", "Spy"],
    "Demon": ["Imp"],
}
setup_counts = {"Minion": 1, "Demon": 1, "Outsider": 1, "Townsfolk": 5}
claims = {
    "Alice": {
        "role": "Fortune Teller",
        "night_results": [
            {"night": 1, "ping": True, "player1": "Alice", "player2": "Eve"},
            {"night": 2, "ping": True, "player1": "Bob", "player2": "Fiona"},
            {"night": 3, "ping": True, "player1": "Alice", "player2": "Carol"},
        ],
    },
    "Bob": {"role": "Recluse"},
    "Carol": {"role": "Slayer"},
    "Dave": {"role": "Ravenkeeper", "seen_player": "Carol", "seen_role": "Slayer", "night": 3},
    "Eve": {"role": "Washerwoman", "seen_role": "Virgin", "seen_players": ["Dave", "Fiona"]},
    "Fiona": {"role": "Virgin"},
    "Gina": {"role": "Butler"},
    "Holly": {"role": "Mayor"},
}

# Canonical representation as sorted tuple of player-role pairs

def canon_roles(mapping):
    return tuple(sorted(mapping.items()))


# replicate like_version_4's world_key used during expansion
def world_key(world):
    def normalize_constraint(c):
        if isinstance(c, dict):
            return ("dict", tuple(sorted(c.items())))
        else:
            return ("str", str(c))
    roles_key = tuple(sorted(world["roles"].items()))
    constraints_key = tuple(sorted((normalize_constraint(c) for c in world.get("constraints", [])), key=str))
    return (roles_key, constraints_key)


# assign into like_version_4 module for use by expand_all_to_concrete
v4.world_key = world_key


def run_v4():
    worlds = v4.all_initial_worlds(player_names, TB_ROLES, setup_counts, claims)
    steps = [
        v4.starting_check,
        v4.process_washerwoman,
        v4.process_librarian,
        v4.process_investigator,
        v4.process_undertaker,
        v4.process_ravenkeeper,
        v4.process_slayer,
        v4.process_empath,
        v4.process_virgin,
        v4.process_fortune_teller,
    ]
    deduced = v4.deduction_pipeline(worlds, TB_ROLES, setup_counts, steps)
    concrete = v4.expand_all_to_concrete(deduced, TB_ROLES, setup_counts, player_names)
    return {canon_roles(w["roles"]): w for w in concrete}


def run_v5():
    all_minion_roles = ["Poisoner", "Scarlet Woman", "Baron", "Spy"]
    m_minions = 1
    worlds = v5.generate_all_worlds(player_names, all_minion_roles, m_minions, claims, TB_ROLES, setup_counts["Outsider"])
    deduced = v5.deduction_pipeline(worlds, TB_ROLES)
    return {canon_roles(w.roles): w for w in deduced}


def main():
    v4_worlds = run_v4()
    v5_worlds = run_v5()
    only_v4 = set(v4_worlds) - set(v5_worlds)
    only_v5 = set(v5_worlds) - set(v4_worlds)
    print(f"Version 4 produced {len(v4_worlds)} unique role assignments")
    print(f"Version 5 produced {len(v5_worlds)} unique role assignments")
    print(f"In V4 only: {len(only_v4)}")
    for r in sorted(only_v4)[:20]:
        print("  ", r)
    print(f"In V5 only: {len(only_v5)}")
    for r in sorted(only_v5)[:20]:
        print("  ", r)


if __name__ == "__main__":
    main()