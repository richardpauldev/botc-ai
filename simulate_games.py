import argparse
from collections import defaultdict

from game import Game, random_trouble_brewing_setup, DumbStorytellerAI, Alignment
from good_player_controller import GoodPlayerController
from evil_player_controller import EvilPlayerController


def simulate_games(num_games: int, player_count: int = 8) -> None:
    team_results = {"Good": 0, "Evil": 0}
    role_results = defaultdict(lambda: [0, 0])  # role -> [wins, total]

    for _ in range(num_games):
        print(_)
        ai = DumbStorytellerAI()
        player_names = [f"Player {i+1}" for i in range(player_count)]
        roles = random_trouble_brewing_setup(player_count, ai)

        game = Game(player_names, roles)
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
            role_results[p.role.name][1] += 1
            player_team = (
                "Good"
                if p.role.alignment in (Alignment.TOWNSFOLK, Alignment.OUTSIDER)
                else "Evil"
            )
            if player_team == winning_team:
                role_results[p.role.name][0] += 1

    print("Team win rates:")
    for team, wins in team_results.items():
        print(f"{team}: {wins / num_games:.2%} ({wins}/{num_games})")

    print("\nRole win rates:")
    for role, (wins, total) in sorted(role_results.items()):
        print(f"{role}: {wins / total:.2%} ({wins}/{total})")


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