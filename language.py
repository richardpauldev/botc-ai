from collections import defaultdict
import random
from enum import Enum, auto

class Alignment(Enum):
    TOWNSFOLK = "Townsfolk"
    OUTSIDER = "Outsider"
    MINION = "Minion"
    DEMON = "Demon"

class BotcInferenceAI:
    def __init__(self, player_names):
        self.player_names = player_names
        self.prob_role = self.get_trouble_brewing_initial_role_probs(player_names)
        self.prob_evil = self.get_evil_prob(self.prob_role)
        self.log = []
        
        
    @staticmethod
    def get_trouble_brewing_initial_role_probs(player_names, player_count=None):
        # Trouble Brewing role lists
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

        # Role counts by player count
        setup = {
            5:  {'Townsfolk': 3, 'Outsider': 0, 'Minion': 1, 'Demon': 1},
            6:  {'Townsfolk': 3, 'Outsider': 1, 'Minion': 1, 'Demon': 1},
            7:  {'Townsfolk': 5, 'Outsider': 0, 'Minion': 1, 'Demon': 1},
            8:  {'Townsfolk': 5, 'Outsider': 1, 'Minion': 1, 'Demon': 1},
            9:  {'Townsfolk': 5, 'Outsider': 2, 'Minion': 1, 'Demon': 1},
            10: {'Townsfolk': 7, 'Outsider': 0, 'Minion': 2, 'Demon': 1},
            11: {'Townsfolk': 7, 'Outsider': 1, 'Minion': 2, 'Demon': 1},
            12: {'Townsfolk': 7, 'Outsider': 2, 'Minion': 2, 'Demon': 1},
        }
        if player_count is None:
            player_count = len(player_names)
        s = setup[player_count]
        minion_count = s['Minion']

        p_baron = minion_count / 4
        p_not_baron = 1 - p_baron

        s_baron = s.copy()
        s_baron['Outsider'] += 2
        s_baron['Townsfolk'] -= 2

        priors = {}
        for p in player_names:
            priors[p] = {}
            # Townsfolk roles
            for role in TB_ROLES['Townsfolk']:
                # P(role | not Baron)
                prob_regular = s['Townsfolk'] / (len(TB_ROLES['Townsfolk']) * player_count)
                # P(role | Baron)
                prob_baron = s_baron['Townsfolk'] / (len(TB_ROLES['Townsfolk']) * player_count)
                priors[p][role] = p_not_baron * prob_regular + p_baron * prob_baron

            # Outsider roles
            for role in TB_ROLES['Outsider']:
                # P(role | not Baron)
                prob_regular = s['Outsider'] / (len(TB_ROLES['Outsider']) * player_count) if s['Outsider'] else 0.0
                # P(role | Baron)
                prob_baron = s_baron['Outsider'] / (len(TB_ROLES['Outsider']) * player_count)
                priors[p][role] = p_not_baron * prob_regular + p_baron * prob_baron

            # Minion
            min_prob = s['Minion'] / (len(TB_ROLES['Minion']) * player_count)
            for role in TB_ROLES['Minion']:
                priors[p][role] = min_prob
            # Demon
            dem_prob = s['Demon'] / (len(TB_ROLES['Demon']) * player_count)
            for role in TB_ROLES['Demon']:
                priors[p][role] = dem_prob
        print(priors)
        return priors
    
    def get_evil_prob(self, role_probs):
        minion_roles = ["Poisoner", "Scarlet Woman", "Spy", "Baron"]
        demon_roles = ["Imp"]

        evil_probs = {}
        for player, probs in role_probs.items():
            evil_prob = sum(probs.get(role, 0) for role in minion_roles + demon_roles)
            evil_probs[player] = evil_prob
        return evil_probs
    
    def process_claim(self, player, claimed_role):
        """
        Updates the probabilities: If good, player must be the claimed role; if evil, can be any evil role.
        Claiming a good role redistributes only the good-role probability.
        """
        minion_roles = ["Poisoner", "Scarlet Woman", "Spy", "Baron"]
        demon_roles = ["Imp"]
        evil_roles = set(minion_roles + demon_roles)

        # Compute sums before claim
        old_probs = self.prob_role[player]
        evil_sum = sum(old_probs[r] for r in evil_roles)
        good_roles = [r for r in old_probs if r not in evil_roles]
        good_sum = sum(old_probs[r] for r in good_roles)

        if claimed_role in evil_roles:
            # Ignore claims of evil roles
            return

        updated_probs = {}
        for role in old_probs:
            if role in evil_roles:
                updated_probs[role] = old_probs[role]
            elif role == claimed_role:
                updated_probs[role] = good_sum
            else:
                updated_probs[role] = 0.0

        # Normalize so total probability is 1
        total = evil_sum + good_sum
        if total > 0:
            for r in updated_probs:
                updated_probs[r] /= total
        else:
            # Edge case: only evil roles
            n_evil = sum(1 for r in updated_probs if r in evil_roles)
            for r in updated_probs:
                updated_probs[r] = 1.0 / n_evil if r in evil_roles else 0.0

        self.prob_role[player] = updated_probs
        self.prob_evil = self.get_evil_prob(self.prob_role)
        self.log.append(f"{player} claims {claimed_role}")


    def normalize_roles(self):
        for p, roles in self.prob_role.items():
            total = sum(roles.values())
            for r in roles:
                roles[r] /= total

    def print_summary(self):
        self.normalize_roles()
        print("\n==== AI DEDUCTION ====")
        print("Probabilities each player is evil:")
        for p in self.player_names:
            print(f"  {p}: {self.prob_evil[p]:.2f}")
        print("\nRole probability (by player):")
        for p in self.player_names:
            best_role = max(self.prob_role[p], key=self.prob_role[p].get)
            print(f"  {p}: Most likely {best_role} ({self.prob_role[p][best_role]:.2f})")
        print("\nLOG:")
        for entry in self.log:
            print(" ", entry)

if __name__ == "__main__":
    # Sample game setup
    players = ["Alice", "Bob", "Carol", "Dave", "Evan", "Frank"]

    ai = BotcInferenceAI(players)

    ai.print_summary()

    ai.process_claim("Bob", "Washerwoman")

    ai.print_summary()