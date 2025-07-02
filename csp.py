import itertools
from constraint import Problem, AllDifferentConstraint

def botc_csp_solver(player_names, TB_ROLES, setup_counts, claims, evil_count):
    """
    constraints: dict {player: [possible_roles]}, e.g. {'Bob': ['Washerwoman']} for hard claims,
    or use for exclusions ['Washerwoman','Empath'] etc.
    """
        # Build role pool per game setup

    all_solutions = []

    for evil_players in itertools.combinations(player_names, evil_count):
        good_players = [p for p in player_names if p not in evil_players]
        problem = Problem()
        
        # Role pool (as before)
        role_pool = []
        for rt, n in setup_counts.items():
            role_pool += TB_ROLES[rt][:] * n
        
        # Add variables for each player
        for p in player_names:
            problem.addVariable(p, role_pool)
        problem.addConstraint(AllDifferentConstraint())
        
        # Setup-count constraint (see earlier answer)
        def count_role_type(*args):
            assignment = args
            demon_count = sum(1 for r in assignment if r in TB_ROLES["Demon"])
            minion_count = sum(1 for r in assignment if r in TB_ROLES["Minion"])
            outsider_count = sum(1 for r in assignment if r in TB_ROLES["Outsider"])
            townsfolk_count = sum(1 for r in assignment if r in TB_ROLES["Townsfolk"])
            return (demon_count == setup_counts.get("Demon", 0) and
                    minion_count == setup_counts.get("Minion", 0) and
                    outsider_count == setup_counts.get("Outsider", 0) and
                    townsfolk_count == setup_counts.get("Townsfolk", 0))
        problem.addConstraint(count_role_type, player_names)

        # Add "good player claims are true" constraints
        for p in good_players:
            if p in claims:
                claimed_role = claims[p]
                # This player's assigned role must match their claim
                def good_claim_constraint(role, claimed=claimed_role):
                    return role == claimed
                problem.addConstraint(good_claim_constraint, [p])

        # (Optional) Add extra info, e.g., "Empath got X", etc.

        # Solve and store solutions
        solutions = problem.getSolutions()
        for sol in solutions:
            sol['_evil'] = evil_players  # Annotate with evil subset for analysis if desired
        all_solutions.extend(solutions)

    return all_solutions

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

players = ["Alice", "Bob", "Carol", "Dave", "Evan", "Frank"]

setups = {
    5:  {'Townsfolk': 3, 'Outsider': 0, 'Minion': 1, 'Demon': 1},
    6:  {'Townsfolk': 3, 'Outsider': 1, 'Minion': 1, 'Demon': 1},
    7:  {'Townsfolk': 5, 'Outsider': 0, 'Minion': 1, 'Demon': 1},
    8:  {'Townsfolk': 5, 'Outsider': 1, 'Minion': 1, 'Demon': 1},
    9:  {'Townsfolk': 5, 'Outsider': 2, 'Minion': 1, 'Demon': 1},
    10: {'Townsfolk': 7, 'Outsider': 0, 'Minion': 2, 'Demon': 1},
    11: {'Townsfolk': 7, 'Outsider': 1, 'Minion': 2, 'Demon': 1},
    12: {'Townsfolk': 7, 'Outsider': 2, 'Minion': 2, 'Demon': 1},
}
setup_counts = setups[len(players)]

constraints = {
    "Alice": "Washerwoman",
    "Bob": "Empath",
    "Dave": "Librarian",
    "Evan": "Mayor",
    "Carol": "Slayer"
    }

evil_count = 2
solutions = botc_csp_solver(players, TB_ROLES, setup_counts, constraints, 2)

n_solutions = len(solutions)
n_alice_imp = sum(1 for sol in solutions if sol["Alice"] == "Imp")
prob_alice_imp = n_alice_imp / n_solutions if n_solutions else 0

print(f"Number of possible worlds: {n_solutions}")
print(f"Probability Alice is Imp: {prob_alice_imp:.2f}")