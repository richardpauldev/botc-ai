import argparse
from collections import defaultdict
from math import sqrt

from game import Game, random_trouble_brewing_setup, DumbStorytellerAI, Alignment
from good_player_controller import GoodPlayerController
from evil_player_controller import EvilPlayerController

def proportion_confidence_interval(wins, total, z=1.645):
    """Returns (center, lower_bound, upper_bound) for a proportion ±0.90 CI.
    z=1.645 is the critical value for 90% confidence."""
    if total == 0:
        return 0, 0, 0
    p = wins / total
    se = sqrt(p * (1 - p) / total)
    lower = max(0, p - z * se)
    upper = min(1, p + z * se)
    return p, lower, upper

def simulate_games(num_games: int, player_count: int = 8) -> None:
    team_results = {"Good": 0, "Evil": 0}
    role_results = defaultdict(lambda: [0, 0])  # role -> [wins, total]

    for _ in range(num_games):
        print(_)
        ai = DumbStorytellerAI()
        player_names = [f"Player {i+1}" for i in range(player_count)]
        roles = random_trouble_brewing_setup(player_count, ai)

        game = Game(player_names, roles)
        # Keep track of each player's starting role so win rates are based on
        # initial roles even if they change (e.g. Imp star-pass).
        starting_roles = {
            p.seat: (p.role.name, p.role.alignment) for p in game.players
        }
        for p in game.players:
            if p.role.alignment in (Alignment.MINION, Alignment.DEMON):
                p.controller = EvilPlayerController()
            else:
                p.controller = GoodPlayerController()
            p.controller.set_player(p)

        result = game.run(verbose=False)
        winning_team = "Good" if result and result.lower().startswith("good") else "Evil"
        team_results[winning_team] += 1

        for p in game.players:
            start_name, start_align = starting_roles[p.seat]
            role_results[start_name][1] += 1
            player_team = (
                "Good"
                if start_align in (Alignment.TOWNSFOLK, Alignment.OUTSIDER)
                else "Evil"
            )
            if player_team == winning_team:
                role_results[start_name][0] += 1

    print("Team win rates:")
    for team, wins in team_results.items():
        print(f"{team}: {wins / num_games:.2%} ({wins}/{num_games})")

    print("\nRole win rates (sorted):")
    # Prepare list with winrate and CI for sorting/printing
    stats = []
    for role, (wins, total) in role_results.items():
        winrate, lower, upper = proportion_confidence_interval(wins, total)
        stats.append((winrate, role, wins, total, lower, upper))

    # Sort by winrate descending
    stats.sort(reverse=True)

    print(f"{'Role':<20}{'Winrate':>12}{'90% CI':>20} {'Record':>12}")
    for winrate, role, wins, total, lower, upper in stats:
        print(f"{role:<20}{winrate:>10.2%}   [{lower:.2%}, {upper:.2%}]   {wins}/{total}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate multiple BOTC games")
    parser.add_argument("num_games", type=int, help="Number of games to simulate")
    parser.add_argument(
        "--players", type=int, default=8, help="Number of players in each game"
    )
    args = parser.parse_args()
    simulate_games(args.num_games, args.players)

if __name__ == "__main__":
    main()
