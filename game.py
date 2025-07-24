from __future__ import annotations
from enum import Enum, auto
import random
from dataclasses import dataclass, field
import builtins
from pprint import pformat

# Toggle detailed debug logging
DEBUG = False

__builtin_print = builtins.print


def debug(msg: str) -> None:
    if DEBUG:
        __builtin_print(f"DEBUG: {msg}")

def _filtered_print(*args, **kwargs):
    if (
        not DEBUG
        and args
        and isinstance(args[0], str)
        and args[0].startswith("DEBUG")
    ):
        return
    __builtin_print(*args, **kwargs)

print = _filtered_print


class Phase(Enum):
    NIGHT = auto()
    DAY = auto()
    GAME_OVER = auto()


class Alignment(Enum):
    TOWNSFOLK = "Townsfolk"
    OUTSIDER = "Outsider"
    MINION = "Minion"
    DEMON = "Demon"


@dataclass
class PlayerView:
    player_seat: int
    player_name: str
    role_name: str
    phase: Phase
    day: int
    night: int
    role_claim: dict | None
    is_alive: bool
    public_claims: dict
    seat_names: dict
    alive_players: list
    dead_players: list
    memory: dict
    history: list
    votes: dict

    def __repr__(self) -> str:
        return (
            f"PlayerView(seat={self.player_seat}, name={self.player_name}), "
            f"role={self.role_name}, phase={self.phase.name}, day={self.day}, "
            f"alive={self.is_alive})"
        )


def format_player_view(pv: PlayerView) -> str:
    """Return a human friendly string representation of ``PlayerView``."""
    lines = [
        f"--- {pv.player_name}'s view ---",
        f"Phase: {pv.phase.name} (Day {pv.day}, Night {pv.night})",
        f"Role: {pv.role_name} | {'Alive' if pv.is_alive else 'Dead'}",
        "Alive players: " + ", ".join(pv.seat_names[s] for s in pv.alive_players),
    ]
    if pv.dead_players:
        lines.append(
            "Dead players: " + ", ".join(pv.seat_names[s] for s in pv.dead_players)
        )
    if pv.public_claims:
        claims = {pv.seat_names[s]: c for s, c in pv.public_claims.items()}
        lines.append("Public claims: " + pformat(claims))
    if pv.memory:
        lines.append("Your memory: " + pformat(pv.memory))
    if pv.votes:
        lines.append("Votes: " + pformat(pv.votes))
    return "\n".join(lines)

class Role:
    """
    Base class for all roles. Each role has an alignment and may have night/day abilities.
    """

    def __init__(self, name, alignment):
        self.name = name
        self.alignment = alignment

    def night_action(self, player, game):
        pass  # Override in child classes

    def day_action(self, player, game):
        pass  # Override in child classes


def create_role(role_name, storyteller_ai):
    # Roles that use only the AI (require passing storyteller_ai)
    ai_roles = {
        "Washerwoman": Washerwoman,
        "Librarian": Librarian,
        "Investigator": Investigator,
        "Chef": Chef,
        "Empath": Empath,
        "Fortune Teller": FortuneTeller,
        "Undertaker": Undertaker,
        "Monk": Monk,
        "Ravenkeeper": Ravenkeeper,
        "Virgin": Virgin,
        "Slayer": Slayer,
        "Saint": Saint,
        "Poisoner": Poisoner,
        "Spy": Spy,
        "Baron": Baron,
        "Scarlet Woman": ScarletWoman,
        "Imp": Imp,
    }
    # Roles that take no arguments (not storyteller dependent)
    simple_roles = {
        "Soldier": Soldier,
        "Mayor": Mayor,
        "Butler": Butler,
        "Recluse": Recluse,
    }
    # Drunk is a special case—needs a cover_role_name (which must be passed separately)
    if role_name == "Drunk":
        # You'd need to specify a cover_role_name here if creating Drunk directly
        # Example: create_role("Drunk", storyteller_ai, cover_role_name="Chef")
        raise ValueError("Use Drunk(storyteller_ai, cover_role_name) to create Drunk")
    if role_name in ai_roles:
        return ai_roles[role_name](storyteller_ai)
    elif role_name in simple_roles:
        return simple_roles[role_name]()
    else:
        raise ValueError(f"Unknown role: {role_name}")


TROUBLE_BREWING_ROLES = {
    Alignment.TOWNSFOLK: [
        "Washerwoman",
        "Librarian",
        "Investigator",
        "Chef",
        "Empath",
        "Fortune Teller",
        "Undertaker",
        "Monk",
        "Ravenkeeper",
        "Virgin",
        "Slayer",
        "Soldier",
        "Mayor",
    ],
    Alignment.OUTSIDER: ["Butler", "Drunk", "Recluse", "Saint"],
    Alignment.MINION: ["Poisoner", "Scarlet Woman", "Spy", "Baron"],
    Alignment.DEMON: ["Imp"],
}


def player_role_counts(num_players: int) -> tuple[int, int]:
    """Return (minion_count, outsider_count) for a game size."""
    outsider_count = (num_players - 1) % 3
    if num_players <= 9:
        minions = 1
    elif num_players <= 12:
        minions = 2
    else:
        minions = 3
    return minions, outsider_count

def random_trouble_brewing_setup(player_count: int, storyteller_ai: StorytellerAI) -> list[Role]:
    minion_count, outsider_count = player_role_counts(player_count)

    minion_names = random.sample(TROUBLE_BREWING_ROLES[Alignment.MINION], k=minion_count)

    if "Baron" in minion_names:
        outsider_count += 2

    demon_name = random.choice(TROUBLE_BREWING_ROLES[Alignment.DEMON])

    townsfolk_count = player_count - outsider_count - minion_count - 1

    roles: list[Role] = []

    for m in minion_names:
        roles.append(create_role(m, storyteller_ai))

    roles.append(create_role(demon_name, storyteller_ai))

    outsider_pool = TROUBLE_BREWING_ROLES[Alignment.OUTSIDER][:]
    outsider_choices = (
        random.sample(outsider_pool, k=outsider_count)
        if outsider_count > 0
        else []
    )


    townsfolk_pool = TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK][:]
    townsfolk_choices = random.sample(townsfolk_pool, k=townsfolk_count)
    roles.extend(create_role(t, storyteller_ai) for t in townsfolk_choices)

    for o in outsider_choices:
        if o == "Drunk":
            cover = random.choice([role for role in TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK] if role not in townsfolk_choices])
            roles.append(Drunk(storyteller_ai, cover_role_name=cover))
        else:
            roles.append(create_role(o, storyteller_ai))

    return roles

from typing import cast

class PlayerController:
    def __init__(self):
        self.player: Player = cast(Player, None)

    def set_player(self, player):
        self.player = player

    def send_info(self, player, info):
        player.receive_info(self.player, info)

    def choose_fortune_teller_targets(self, candidates, player_view):
        raise NotImplementedError

    def choose_monk_protect(self, candidates, player_view):
        raise NotImplementedError

    def choose_ravenkeeper_reveal(self, candidates, player_view):
        raise NotImplementedError

    def choose_imp_kill(self, candidates, player_view):
        raise NotImplementedError

    def choose_poisoner_target(self, candidates, player_view):
        raise NotImplementedError

    def choose_master(self, candidates, player_view):
        raise NotImplementedError

    def choose_nominee(self, candidates: list, player_view: PlayerView):
        raise NotImplementedError

    def cast_vote(self, nominee: "Player", player_view: PlayerView) -> bool:
        raise NotImplementedError

    def share_info(self, player_view: PlayerView, context=None):
        raise NotImplementedError


class HumanPlayerController(PlayerController):
    def choose_fortune_teller_targets(self, candidates, player_view):
        print(format_player_view(player_view))
        print(f"\n{self.player.name} (Fortune Teller): Pick TWO different players to test.")
        for i, p in enumerate(candidates):
            print(f"{i}: {p.name} ({p.role.name})")
        idx1 = int(input("Enter the number for the first target: "))
        idx2 = int(input("Enter the number for the second target: "))
        while idx2 == idx1:
            print("Pick two different players.")
            idx2 = int(input("Enter the number for the second target: "))
        return (candidates[idx1], candidates[idx2])

    def choose_monk_protect(self, candidates, player_view):
        print(format_player_view(player_view))
        if not candidates:
            return None
        print(f"\n{self.player.name} (Monk): Pick a player to protect tonight.")
        for i, p in enumerate(candidates):
            print(f"{i}: {p.name} ({p.role.name})")
        idx = int(input("Enter number: "))
        return candidates[idx]

    def choose_ravenkeeper_reveal(self, candidates, player_view):
        print(format_player_view(player_view))
        if not candidates:
            return None
        print(
            f"\n{self.player.name} (Ravenkeeper): Pick a player to check if you die tonight."
        )
        for i, p in enumerate(candidates):
            print(f"{i}: {p.name} ({p.role.name})")
        idx = int(input("Enter number: "))
        return candidates[idx]

    def choose_imp_kill(self, candidates, player_view):
        print(format_player_view(player_view))
        if not candidates:
            return None
        print(f"\n{self.player.name} (Imp): Pick a player to kill tonight.")
        for i, p in enumerate(candidates):
            print(f"{i}: {p.name} ({p.role.name})")
        idx = int(input("Enter number: "))
        return candidates[idx]

    def choose_poisoner_target(self, candidates, player_view):
        print(format_player_view(player_view))
        if not candidates:
            return None
        print(f"\n{self.player.name} (Poisoner): Pick a player to poison tonight.")
        for i, p in enumerate(candidates):
            print(f"{i}: {p.name} ({p.role.name})")
        idx = int(input("Enter number: "))
        return candidates[idx]

    def choose_nominee(self, candidates, player_view):
        print(format_player_view(player_view))
        print(f"\n{self.player.name}: nominate someone (or Enter to skip).")
        for i, p in enumerate(candidates):
            status = "Alive" if p.alive else "Dead"
            print(f"  {i}: {p.name} ({status})")
        resp = input("Number or Enter: ")
        if resp == "":
            return None
        return candidates[int(resp)]

    def cast_vote(self, nominee, player_view):
        resp = input(f"{self.player.name}: execute {nominee.name}? (y/N): ")
        return resp.strip().lower() == "y"

    def share_info(self, player_view: PlayerView, context=None):
        if self.player.role.name in (TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK] + TROUBLE_BREWING_ROLES[Alignment.OUTSIDER]):
            if self.player.claim is None:
                claim = {"role": player_view.role_name}
                if "night_results" in player_view.memory:
                    claim["night_results"] = player_view.memory["night_results"]
                if "info" in player_view.memory:
                    info = player_view.memory["info"]
                    if isinstance(info, dict):
                        claim.update(info)
                    else:
                        claim["info"] = info

                self.player.claim = claim
                self._last_public = claim
                return {"public_claim": self.player.claim}
            info = {
                k: v
                for k, v in self.player.memory.items()
                if k != "received_info"
            }
            if info and info != self._last_public:
                self._last_public = info
                return {"public": info}
            return None


        elif self.player.claim is None:
            claim = input(
                f"{self.player.name}: Enter a role to claim (or press Enter to stay silent): "
            ).strip()
            if claim:
                self.player.claim = {"role": claim}
                return {"public_claim": self.player.claim}
            return None
        return None


@dataclass
class Player:
    """Represents a single player (seat)."""

    seat: int
    name: str
    controller: PlayerController
    # role is assigned after game setup; use a placeholder Role to avoid Optional checks
    role: Role = field(init=False)
    alive: bool = True
    memory: dict = field(default_factory=dict)
    claim: dict | None = None
    votes_today: int = 0
    has_used_dead_vote: bool = False

    def __hash__(self) -> int:
        return hash(self.seat)

    def __post_init__(self) -> None:
        self.controller.set_player(self)
        # Initialize with a placeholder role until roles are assigned
        self.role = Role("Unassigned", Alignment.TOWNSFOLK)

    def assign_role(self, role: Role) -> None:
        self.role = role

    def kill(self) -> None:
        self.alive = False

    def revive(self) -> None:
        self.alive = True

    def receive_info(self, from_player, info) -> None:
        self.memory.setdefault("received_info", []).append(
            {"from": from_player.name, "info": info}
        )

        if isinstance(self.controller, HumanPlayerController):
            print(
                f"\nInfo received by {self.name} from {from_player.name}:"
            )
            print(pformat(info))
            print()

    def __repr__(self):
        role_name = self.role.name
        status = "Alive" if self.alive else "Dead"
        return f"{self.name} ({role_name}) - {status}"

    def choose_fortune_teller_targets(self, game):
        return self.controller.choose_fortune_teller_targets(
            game.players, game.get_player_view(self)
        )

    def choose_monk_protect(self, game):
        candidates = [p for p in game.players if p != self]
        return self.controller.choose_monk_protect(
            candidates, game.get_player_view(self)
        )

    def choose_ravenkeeper_reveal(self, game):
        return self.controller.choose_ravenkeeper_reveal(
            game.players, game.get_player_view(self)
        )

    def choose_imp_kill(self, game):
        return self.controller.choose_imp_kill(
            game.players, game.get_player_view(self)
        )

    def choose_poisoner_target(self, game):
        return self.controller.choose_poisoner_target(
            game.players, game.get_player_view(self)
        )
    
    def choose_master(self, game):
        candidates = [p for p in game.players if p != self]
        return self.controller.choose_master(candidates, game.get_player_view(self))


@dataclass
class GameState:
    """Public game state shared with all players."""

    player_count: int
    day: int = 1
    night: int = 0
    phase: Phase = Phase.NIGHT
    nominees: list = field(default_factory=list)
    votes: dict = field(default_factory=dict)
    dead_players: set = field(default_factory=set)
    grimoire: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    executed_today: Player | None = None
    pending_deaths: set = field(default_factory=set)
    monk_protected: Player | None = None
    demon_bluffs: list[str] | None = None

    def queue_death(self, player):
        self.pending_deaths.add(player.seat)

    def advance_phase(self):
        if self.phase == Phase.NIGHT:
            self.phase = Phase.DAY
        elif self.phase == Phase.DAY:
            self.day += 1
            self.phase = Phase.NIGHT
        print(f"Phase: {self.phase}")

    def record_death(self, player):
        self.dead_players.add(player.seat)


class Game:
    """
    Main controller
    """

    def __init__(self, player_names, role_list):
        self.players = [
            Player(i, name, PlayerController())
            for i, name in enumerate(player_names)
        ]
        self.state = GameState(len(self.players))
        self.roles = role_list
        self.assign_roles()
        self.assign_evil_info_and_bluffs()
        for p in self.players:
            self.state.grimoire[p.seat] = p

    def display_state(self):
        """Print a concise summary of the current game state."""
        print("\nCurrent Game State:")
        for p in self.players:
            status = "Alive" if p.alive else "Dead"
            print(f"  {p.name} [{p.role.name}] - {status}")

    def assign_roles(self):
        roles = self.roles.copy()
        random.shuffle(roles)
        for player, role in zip(self.players, roles):
            player.assign_role(role)
            player.claim = None

    def assign_evil_info_and_bluffs(self):
        evil_team = [
            p
            for p in self.players
            if p.role.alignment in [Alignment.MINION, Alignment.DEMON]
        ]
        demon = next(
            (p for p in evil_team if p.role.alignment == Alignment.DEMON), None
        )

        # --- 1. Assign Bluffs to Demon ---
        all_good_roles = (
            TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK]
            + TROUBLE_BREWING_ROLES[Alignment.OUTSIDER]
        )
        # Remove roles actually in play (except Drunk's cover role)
        in_play = [
            p.role.cover_role_name if isinstance(p.role, Drunk) else p.role.name
            for p in self.players
        ]
        in_play.extend([
            p.role.name for p in self.players if isinstance(p.role, Drunk)
        ])
        bluff_pool = [r for r in all_good_roles if r not in in_play and r != "Drunk"]
        # Choose 3 bluffs randomly
        bluffs = random.sample(bluff_pool, k=3) if len(bluff_pool) >= 3 else bluff_pool
        if demon:
            demon.memory["bluffs"] = bluffs
            self.state.demon_bluffs = bluffs
            for p in evil_team:
                if p is demon:
                    continue
                p.memory["bluffs"] = bluffs
                demon.controller.send_info(p, {"bluffs": bluffs})

            # Assign a specific bluff to each evil player so they can coordinate
            assignments = {}
            available = bluffs[:] if bluffs else []
            random.shuffle(available)
            for idx, p in enumerate(evil_team):
                chosen = available[idx % len(available)] if available else None
                assignments[p.name] = chosen
                p.memory["assigned_bluff"] = chosen
            for p in evil_team:
                p.memory["bluff_plan"] = assignments
                if p is not demon:
                    demon.controller.send_info(p, {"bluff_plan": assignments, "assigned_bluff": assignments[p.name]})

        # --- 2. Share Evil Team Info with All Evil Players ---
        evil_team_info = [
            {"name": p.name, "alignment": p.role.alignment, "seat": p.seat}
            for p in evil_team
        ]
        for p in evil_team:
            p.memory["evil_team"] = evil_team_info

    def info_swapping_opportunity(self, context=None):
        for player in self.players:
            # if player.claim is not None:
            #     claim_msg = {"from": player.name, "public_claim": player.claim}
            #     for target in self.players:
            #         if target is player:
            #             continue
            #         player.controller.send_info(target, claim_msg)

            # Additonal Information
            pv = self.get_player_view(player)
            info = player.controller.share_info(pv, context)
            if info:
                for target in self.players:
                    if target is player:
                        continue
                    player.controller.send_info(target, info)

    def is_player_alive(self, player: Player) -> bool:
        return player.alive and player.seat not in self.state.pending_deaths

    def get_alive_players(self):
        return [p for p in self.players if self.is_player_alive(p)]

    def night_phase(self):
        """
        night phase for alive roles w/ abilities
        """

        self.state.night += 1
        print(f"\n==== NIGHT {self.state.night} ====")  # start of night_phase
        self.display_state()

        
        self.state.monk_protected = None
        for player in self.get_alive_players():
            if not self.is_player_alive(player):
                continue
            player.role.night_action(player, self)
            print(
                f"Night summary for {player.name} ({player.role.name}): {pformat(player.memory)}"
            )
        self.state.advance_phase()

    def day_phase(self):
        """
        nominations, voting, executions
        """
        for seat in self.state.pending_deaths:
            player = self.state.grimoire[seat]
            player.alive = False
            self.state.dead_players.add(player.seat)
            self.state.history.append(f"{player.name} died last night.")
        self.state.pending_deaths.clear()

        print(f"\n==== DAY {self.state.day} ====")  # start of day_phase

        self.info_swapping_opportunity(context="wakeup")

        print("Players Info:")
        self.display_state()
        alive_players = self.get_alive_players()

        self.state.nominees = []
        self.state.votes = {}
        nominations = 0
        executed_today = None

        votes_per_nominee = []
        nominated = set()
        already_nominated = set()
        idx = 0
        passes = 0
        executed_today = None
        while alive_players and passes < len(alive_players):
            nominator = alive_players[idx]
            if nominator.seat in nominated:
                passes += 1
            else:
                pv = self.get_player_view(nominator)
                nominee = nominator.controller.choose_nominee(self.players, pv)
                if nominee is None or nominee.seat in already_nominated:
                    nominated.add(nominator.seat)
                    passes += 1
                else:
                    passes = 0
                    nominated.add(nominator.seat)
                    already_nominated.add(nominee.seat)
                    self.state.nominees.append((nominator, nominee))
                    nominations += 1
                    print(f"{nominator.name} nominates {nominee.name}")

                    if hasattr(nominee.role, "on_nominated") and nominee.alive:
                        nominee.role.on_nominated(nominee, nominator, self)
                        if not nominator.alive:
                            print(f"{nominator.name} executed by Virgin's ability!")
                            alive_players = self.get_alive_players()
                            if not alive_players:
                                break
                            idx %= len(alive_players)
                            executed_today = nominator
                            break

                    votes = []
                    vote_names = []
                    voters = [p for p in self.players if p.alive or not p.has_used_dead_vote]
                    start = (nominee.seat + 1) % len(self.players)
                    order = [self.players[(start + i) % len(self.players)] for i in range(len(self.players))]
                    for voter in order:
                        if voter not in voters:
                            continue
                        if voter.controller.cast_vote(nominee, pv):
                            votes.append(voter)
                            vote_names.append(voter.name)
                            if not voter.alive:
                                voter.has_used_dead_vote = True
                    print(f"Votes for {nominee.name}: {len(votes)}")
                    votes_per_nominee.append((nominee, votes))
                    self.state.votes[nominee.name] = vote_names

            idx = (idx + 1) % len(alive_players)
            alive_players = self.get_alive_players()
        
        if executed_today:
            self.state.executed_today = executed_today
            print("Virgin triggered, ending day")
        elif self.state.nominees:
            print("\nVoting summary:")
            for nominee, names in self.state.votes.items():
                print(f"  {nominee}: {len(names)} votes - [{', '.join(names)}]")

            alive_players = self.get_alive_players()
            required_votes = (len(alive_players) + 1) // 2
            print(f"\nVotes required to execute: {required_votes}\n")

            max_votes = max((len(v) for v in self.state.votes.values()), default=0)
            top_nominees = [
                nominee
                for nominee, votes in votes_per_nominee
                if len(votes) == max_votes and max_votes >= required_votes
            ]

            if len(top_nominees) == 1:
                executed_today = top_nominees[0]
                print(f"\n{executed_today.name} has been chosen for execution!")
                self.execute_player(executed_today)
                self.state.executed_today = executed_today
                # Saint check (with drunk/poisoned check)
                if executed_today is not None and executed_today.role.name == "Saint":
                    ai = getattr(executed_today.role, "storyteller_ai", None)
                    is_drunk_poisoned = (
                        ai.is_drunk_or_poisoned(executed_today, self) if ai else False
                    )
                    if not is_drunk_poisoned:
                        print("Saint was executed! Evil wins immediately!")
                        self.state.phase = Phase.GAME_OVER
                        self.state.history.append(
                            "Saint was executed. Evil wins immediately."
                        )
                    else:
                        print(
                            "Saint was executed while drunk/poisoned—ability does NOT trigger."
                        )
                        self.state.history.append(
                            "Saint was executed while drunk/poisoned (no effect)."
                        )
            elif len(top_nominees) > 1:
                print("\nTie for most votes; no one is executed.")
                self.state.executed_today = None
            else:
                print("\nNo one was executed today.")
                self.state.executed_today = None

        else:
            print("\nNo nominations today.")
            self.state.executed_today = None

        self.state.advance_phase()

    def execute_player(self, player):
        player.kill()
        self.state.record_death(player)
        self.state.history.append(
            f"{player.name} was executed on day {self.state.day}."
        )

        self.resolve_scarlet_woman(player)

    def check_win_conditions(self):
        alive = self.get_alive_players()
        demon_alive = any(p.role.alignment == Alignment.DEMON for p in alive)
        if (
            len(alive) == 3
            and any(p.role.name == "Mayor" for p in alive)
            and self.state.phase == Phase.NIGHT
            and self.state.executed_today == None
        ):
            return "Good Wins!"
        if not demon_alive:
            self.state.phase = Phase.GAME_OVER
            return "Good wins!"

        if len(alive) <= 2:
            self.state.phase = Phase.GAME_OVER
            return "Evil wins!"
        return None

    def run(self, verbose: bool = True) -> str | None:
        """
        Main game loop. If ``verbose`` is False, suppress output and skip the
        deduction step. Returns the winning team string (e.g. "Good wins!") or
        ``None`` if the game ended without a clear winner.
        """
        result = None
        if not verbose: #Stop all printing
            saved_print = globals().get("__builtin_print")
            globals()["__builtin_print"] = lambda *a, **k: None
        else:
            saved_print = None
        try:
            while self.state.phase != Phase.GAME_OVER:
                if self.state.phase == Phase.NIGHT:
                    self.night_phase()
                elif self.state.phase == Phase.DAY:
                    self.day_phase()
                result = self.check_win_conditions()
                if result or self.state.phase == Phase.GAME_OVER or self.state.night > 10:
                    if verbose:
                        print(result)
                    break
        finally:
            if not verbose:
                globals()["__builtin_print"] = saved_print  # type: ignore

        if verbose:
            print("\nGame over! Final state:")
            for p in self.players:
                print(p)
            # After the game ends, run deduction analysis on the final game state
            self.run_deduction()

        return result

    def resolve_scarlet_woman(self, killed_player):
        if killed_player.role.name != "Imp":
            return
        alive_before = len(self.get_alive_players()) + 1
        if alive_before < 5:
            return
        for p in self.get_alive_players():
            if isinstance(p.role, ScarletWoman):
                ai = p.role.storyteller_ai
                is_drunk_poisoned = ai.is_drunk_or_poisoned(p, self)
                if not is_drunk_poisoned:
                    p.role = Imp(ai)
                    self.state.history.append(
                        f"Scarlet Woman ({p.name}) becomes the new Imp after {killed_player.name} was killed."
                    )
                    print(
                        f"Scarlet Woman ({p.name}) becomes the new Imp after {killed_player.name} was killed."
                    )
                    return

    def get_player_view(self, player):
        if self.state.night == 1 and self.state.phase == Phase.NIGHT:
            claims = {}
        else:
            claims = {p.seat: p.claim for p in self.players if p.claim is not None}
        return PlayerView(
            player_seat=player.seat,
            player_name=player.name,
            role_name=(
                player.role.name
                if player.role.name != "Drunk"
                else player.role.cover_role_name
            ),
            phase=self.state.phase,
            day=self.state.day,
            night=self.state.night,
            is_alive=player.alive,
            role_claim=player.claim,
            public_claims=claims,
            seat_names={p.seat: p.name for p in self.players},
            alive_players=[p.seat for p in self.players if p.alive],
            dead_players=[p.seat for p in self.players if not p.alive],
            memory=player.memory.copy(),
            history=self.state.history.copy(),
            votes=self.state.votes.copy(),
        )

    def run_deduction(self):
        """Run the deduction engine on the current game state and print results."""
        from deduction_engine import (
            generate_all_worlds,
            deduction_pipeline,
            compute_role_probs,
        )

        player_names = [p.name for p in self.players]
        TB_ROLES = {a.value if hasattr(a, "value") else a: roles for a, roles in TROUBLE_BREWING_ROLES.items()}

        all_minion_roles = TB_ROLES["Minion"]
        m_minions, outsider_count = player_role_counts(len(self.players))

        claims = {p.name: p.claim for p in self.players if p.claim}

        try:
            worlds = generate_all_worlds(
                player_names,
                all_minion_roles,
                m_minions,
                claims,
                TB_ROLES,
                outsider_count,
                deaths=[],
            )
            deduced = deduction_pipeline(worlds, TB_ROLES)
            evil_prob, imp_prob = compute_role_probs(
                deduced, player_names, TB_ROLES
            )
            print("\nDeduction results:")
            for name in player_names:
                print(
                    f"{name}: {evil_prob[name]:.1f}% evil, {imp_prob[name]:.1f}% Imp"
                )
        except Exception as e:  # pragma: no cover - fallback for early bugs
            print(f"Deduction failed: {e}")


# TODO Insert Role implementations
class StorytellerAI:
    pass


class DumbStorytellerAI(StorytellerAI):

    def is_drunk_or_poisoned(self, player, game):
        result = (
            (hasattr(player, "role") and player.role.name == "Drunk")
            or (
                hasattr(game.state, "drunk")
                and player in getattr(game.state, "drunk", set())
            )
            or (
                hasattr(game.state, "poisoned")
                and player in getattr(game.state, "poisoned", set())
            )
        )
        if result:
            print(f"DEBUG: {player.name} is drunk or poisoned.")
        return result

    def choose_two_townsfolk(self, washerwoman, game):
        candidates = [
            (p, p.role.name)
            for p in game.players
            if p.role.alignment == Alignment.TOWNSFOLK and p.role.name != "Washerwoman"
        ]
        for p in game.players:
            if p.role.name == "Spy":
                fake_role = random.choice(
                    [
                        role
                        for role in TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK]
                        if role != "Washerwoman"
                    ]
                )
                candidates.append((p, fake_role))
        print(
            f"DEBUG: Washerwoman info candidates: {[(p.name, r) for p,r in candidates]}"
        )
        if not candidates:
            print("DEBUG: No valid Washerwoman candidates.")
            return None, None, None
        if self.is_drunk_or_poisoned(washerwoman, game):
            fake_players = [p for p in game.players if p != washerwoman]
            fake_roles = [r for _, r in candidates]
            fake_real = random.choice(fake_players)
            fake_role = random.choice(fake_roles)
            others = [p for p in game.players if p != washerwoman and p != fake_real]
            other = random.choice(others)
            pair = [fake_real, other]
            random.shuffle(pair)
            print(
                f"DEBUG: Washerwoman (drunk/poisoned) shows role {fake_role} and players {pair[0].name}, {pair[1].name}"
            )
            return fake_role, pair[0], pair[1]
        real, role_to_show = random.choice(candidates)
        others = [p for p in game.players if p != washerwoman and p != real]
        other = random.choice(others)
        pair = [real, other]
        random.shuffle(pair)
        print(
            f"DEBUG: Washerwoman shows role {role_to_show} and players {pair[0].name}, {pair[1].name}"
        )
        return role_to_show, pair[0], pair[1]

    def choose_two_outsiders(self, librarian, game):
        candidates = [
            (p, p.role.name)
            for p in game.players
            if p.role.alignment == Alignment.OUTSIDER
        ]
        for p in game.players:
            if p.role.name == "Spy":
                fake_role = random.choice(TROUBLE_BREWING_ROLES[Alignment.OUTSIDER])
                candidates.append((p, fake_role))
        print(
            f"DEBUG: Librarian info candidates: {[(p.name, r) for p,r in candidates]}"
        )
        if not candidates:
            print("DEBUG: No valid Librarian candidates.")
            return None, None, None
        if self.is_drunk_or_poisoned(librarian, game):
            fake_players = [p for p in game.players if p != librarian]
            fake_roles = [r for _, r in candidates]
            fake_real = random.choice(fake_players)
            fake_role = random.choice(["Saint", "Butler", "Drunk", "Recluse"])
            others = [p for p in game.players if p != librarian and p != fake_real]
            other = random.choice(others)
            pair = [fake_real, other]
            random.shuffle(pair)
            print(
                f"DEBUG: Librarian (drunk/poisoned) shows role {fake_role} and players {pair[0].name}, {pair[1].name}"
            )
            return fake_role, pair[0], pair[1]
        real, role_to_show = random.choice(candidates)
        others = [p for p in game.players if p != librarian and p != real]
        other = random.choice(others)
        pair = [real, other]
        random.shuffle(pair)
        print(
            f"DEBUG: Librarian shows role {role_to_show} and players {pair[0].name}, {pair[1].name}"
        )
        return role_to_show, pair[0], pair[1]

    def choose_two_minions(self, investigator, game):
        minion_candidates = [
            (p, p.role.name)
            for p in game.players
            if p.role.alignment == Alignment.MINION
        ]
        recluse_candidates = [p for p in game.players if p.role.name == "Recluse"]
        minion_role_options = ["Poisoner", "Spy", "Scarlet Woman", "Baron"]
        candidates = minion_candidates.copy()
        for p in recluse_candidates:
            fake_role = random.choice(minion_role_options)
            candidates.append((p, fake_role))
        print(
            f"DEBUG: Investigator info candidates: {[(p.name, r) for p,r in candidates]}"
        )
        if not candidates:
            print("DEBUG: No valid Investigator candidates.")
            return None, None, None
        if self.is_drunk_or_poisoned(investigator, game):
            fake_players = [p for p in game.players if p != investigator]
            fake_real = random.choice(fake_players)
            fake_role = random.choice(minion_role_options)
            others = [p for p in game.players if p != investigator and p != fake_real]
            other = random.choice(others)
            pair = [fake_real, other]
            random.shuffle(pair)
            print(
                f"DEBUG: Investigator (drunk/poisoned) shows role {fake_role} and players {pair[0].name}, {pair[1].name}"
            )
            return fake_role, pair[0], pair[1]
        real, role_to_show = random.choice(candidates)
        others = [p for p in game.players if p != investigator and p != real]
        other = random.choice(others)
        pair = [real, other]
        random.shuffle(pair)
        print(
            f"DEBUG: Investigator shows role {role_to_show} and players {pair[0].name}, {pair[1].name}"
        )
        return role_to_show, pair[0], pair[1]

    def evil_for_empath(self, player):
        if player.role.name == "Recluse":
            result = random.choice([True, False])
            print(
                f"DEBUG: Empath checks {player.name} (Recluse), random evil? {result}"
            )
            return result
        if player.role.name == "Spy":
            print(f"DEBUG: Empath checks {player.name} (Spy), always not evil.")
            return False
        result = player.role.alignment in [Alignment.MINION, Alignment.DEMON]
        print(f"DEBUG: Empath checks {player.name}, evil? {result}")
        return result

    def chef_evilness_map(self, alive_players):
        """Return a mapping of player seat -> whether they register as evil."""
        mapping = {}
        for p in alive_players:
            if p.role.name == "Recluse":
                val = random.choice([True, False])
                mapping[p.seat] = val
                print(f"DEBUG: Chef checks {p.name} (Recluse), random evil? {val}")
            elif p.role.name == "Spy":
                val = random.choice([True, False])
                mapping[p.seat] = val
                print(f"DEBUG: Chef checks {p.name} (Spy), random evil? {val}")
            else:
                val = p.role.alignment in [Alignment.MINION, Alignment.DEMON]
                mapping[p.seat] = val
                print(f"DEBUG: Chef checks {p.name}, evil? {val}")
        return mapping

    def give_empath_info(self, empath, game, true_evil_neighbors):
        if self.is_drunk_or_poisoned(empath, game):
            val = 0 if true_evil_neighbors >= 1 else 1
            print(
                f"DEBUG: Empath ({empath.name}) is drunk/poisoned: giving {val} instead of {true_evil_neighbors}"
            )
            return val
        print(f"DEBUG: Empath ({empath.name}) is sober: giving {true_evil_neighbors}")
        return true_evil_neighbors

    def give_chef_info(self, chef, game, true_evil_pairs):
        if self.is_drunk_or_poisoned(chef, game):
            rand_val = random.randint(0, 3)
            print(
                f"DEBUG: Chef ({chef.name}) is drunk/poisoned: giving random {rand_val}"
            )
            return rand_val
        print(f"DEBUG: Chef ({chef.name}) is sober: giving {true_evil_pairs}")
        return true_evil_pairs

    def pick_red_herring(self, game):
        candidates = [
            p
            for p in game.players
            if p.role.alignment != Alignment.DEMON
            and p.role.alignment != Alignment.MINION
            and p.role.name != "Recluse"
        ]
        pick = random.choice(candidates)
        print(f"DEBUG: Fortune Teller red herring is {pick.name}")
        return pick

    def fortune_teller_result(self, fortune_teller, pair, game):
        print(
            f"DEBUG: Fortune Teller is checking {pair[0].name if pair[0] else None} and {pair[1].name if pair[1] else None}"
        )
        if self.is_drunk_or_poisoned(fortune_teller, game):
            result = random.choice([True, False, False])
            print(
                f"DEBUG: Fortune Teller ({fortune_teller.name}) is drunk/poisoned: random ping {result}"
            )
            return result
        if not hasattr(game.state, "red_herring") or game.state.red_herring is None:
            game.state.red_herring = self.pick_red_herring(game)
        red_herring = game.state.red_herring
        for p in pair:
            if p is None:
                continue
            if self.registers_as_demon(p):
                print(f"DEBUG: Fortune Teller pinged true on {p.name} (Demon)")
                return True
            if p == red_herring:
                print(f"DEBUG: Fortune Teller pinged true on {p.name} (Red Herring)")
                return True
        print("DEBUG: Fortune Teller did not ping (both safe)")
        return False

    def registers_as_demon(self, player):
        if player.role.name == "Recluse":
            val = random.choice([True, False])
            print(f"DEBUG: {player.name} (Recluse) registers as demon? {val}")
            return val
        result = player.role.alignment == Alignment.DEMON
        print(f"DEBUG: {player.name} registers as demon? {result}")
        return result

    def undertaker_info(self, undertaker, executed_player, game):
        if self.is_drunk_or_poisoned(undertaker, game):
            if random.random() < 0.7:
                print(
                    f"DEBUG: Undertaker ({undertaker.name}) is drunk/poisoned: giving actual role {executed_player.role.name}"
                )
                return executed_player.role.name
            else:
                true_alignment = executed_player.role.alignment
                all_alignments = [
                    Alignment.TOWNSFOLK,
                    Alignment.OUTSIDER,
                    Alignment.MINION,
                    Alignment.DEMON,
                ]
                opposite_alignments = [
                    a for a in TROUBLE_BREWING_ROLES if a != true_alignment
                ]
                role_pool = []
                for p in game.players:
                    if p.role.alignment in opposite_alignments:
                        role_pool.append(p.role.name)
                pick = random.choice(role_pool)
                print(
                    f"DEBUG: Undertaker ({undertaker.name}) is drunk/poisoned: giving false role {pick}"
                )
                return pick
        if executed_player.role.name == "Recluse":
            if random.choice([True, False]):
                pick = random.choice(["Poisoner", "Scarlet Woman", "Spy", "Baron"])
                print(f"DEBUG: Undertaker sees Recluse as {pick}")
                return pick
            else:
                print("DEBUG: Undertaker sees Recluse as Imp")
                return "Imp"
        if executed_player.role.name == "Spy":
            if random.choice([True, False]):
                pick = random.choice(TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK])
                print(f"DEBUG: Undertaker sees Spy as {pick}")
                return pick
            else:
                pick = random.choice(TROUBLE_BREWING_ROLES[Alignment.OUTSIDER])
                print(f"DEBUG: Undertaker sees Spy as {pick}")
                return pick
        print(f"DEBUG: Undertaker sees true role {executed_player.role.name}")
        return executed_player.role.name

    # The remaining methods (monk_protect, ravenkeeper_info, etc.) can be similarly instrumented with prints, if needed.
    def monk_protect(self, monk, target, game):
        if self.is_drunk_or_poisoned(monk, game):
            print(f"DEBUG: Monk ({monk.name}) is drunk/poisoned: no one protected.")
            game.state.monk_protected = None
            return
        game.state.monk_protected = target
        print(
            f"DEBUG: Monk ({monk.name}) protects {target.name if target else 'nobody'}."
        )

    def ravenkeeper_info(self, ravenkeeper, target, game):
        if self.is_drunk_or_poisoned(ravenkeeper, game):
            true_alignment = target.role.alignment
            opposite_alignments = [
                a for a in TROUBLE_BREWING_ROLES if a != true_alignment
            ]
            role_pool = []
            for align in opposite_alignments:
                role_pool.extend(TROUBLE_BREWING_ROLES[align])
            pick = random.choice(role_pool)
            print(
                f"DEBUG: Ravenkeeper ({ravenkeeper.name}) is drunk/poisoned: shown {pick} for {target.name}."
            )
            return pick
        if target.role.name == "Recluse":
            if random.choice([True, False]):
                role_pool = (
                    TROUBLE_BREWING_ROLES[Alignment.MINION]
                    + TROUBLE_BREWING_ROLES[Alignment.DEMON]
                )
                pick = random.choice(role_pool)
                print(f"DEBUG: Ravenkeeper sees Recluse as {pick}.")
                return pick
            else:
                print(f"DEBUG: Ravenkeeper sees Recluse as Recluse.")
                return "Recluse"
        if target.role.name == "Spy":
            if random.choice([True, False]):
                pick = random.choice(TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK])
                print(f"DEBUG: Ravenkeeper sees Spy as {pick}.")
                return pick
            else:
                pick = random.choice(TROUBLE_BREWING_ROLES[Alignment.OUTSIDER])
                print(f"DEBUG: Ravenkeeper sees Spy as {pick}.")
                return pick
        print(
            f"DEBUG: Ravenkeeper sees true role {target.role.name} for {target.name}."
        )
        return target.role.name

    def virgin_nominator_registers_as_townsfolk(self, nominator, game):
        if nominator.role.alignment == Alignment.TOWNSFOLK:
            print(f"DEBUG: Virgin nomination: {nominator.name} is a real Townsfolk.")
            return True
        if nominator.role.name == "Spy":
            val = random.choice([True, False])
            print(
                f"DEBUG: Virgin nomination: {nominator.name} is Spy, registers as Townsfolk? {val}"
            )
            return val
        print(f"DEBUG: Virgin nomination: {nominator.name} is not a Townsfolk or Spy.")
        return False

    def virgin_nomination_check(self, virgin, nominator, game):
        if self.is_drunk_or_poisoned(virgin, game):
            print(
                f"DEBUG: Virgin ({virgin.name}) is drunk/poisoned: ability does not trigger."
            )
            return
        if self.virgin_nominator_registers_as_townsfolk(nominator, game):
            print(f"DEBUG: Virgin's ability triggers, executing {nominator.name}.")
            nominator.kill()
            game.state.history.append(
                f"{nominator.name} was executed on day {game.state.day}."
            )
            nominator.memory["executed_by_virgin"] = True
        else:
            print(f"DEBUG: Virgin's ability does NOT trigger for {nominator.name}.")

    def slayer_shot(self, slayer, target, game):
        if self.is_drunk_or_poisoned(slayer, game):
            print(
                f"DEBUG: Slayer ({slayer.name}) is drunk/poisoned: shot does nothing."
            )
            return
        if target.role.alignment == Alignment.DEMON:
            print(f"DEBUG: Slayer shot and killed {target.name} (Demon)!")
            target.kill()
            game.state.history.append(
                f"The Slayer ({slayer.name}) shot {target.name} and killed them!"
            )
            game.resolve_scarlet_woman(target)
            return
        if target.role.name == "Recluse":
            val = random.choice([True, False])
            print(
                f"DEBUG: Slayer shot Recluse ({target.name}). Registers as demon? {val}"
            )
            if val:
                target.kill()
                game.state.history.append(
                    f"The Slayer ({slayer.name}) shot {target.name} and killed them!"
                )
                return
        print(f"DEBUG: Slayer shot {target.name}, but nothing happened.")

    def resolve_demon_kill(self, demon, target, game):
        print(f"DEBUG: Demon ({demon.name}) is trying to kill {target.name}.")
        if self.is_drunk_or_poisoned(demon, game):
            return

        if not game.is_player_alive(target):
            return

        mayor_bounce = [
            p for p in game.players if p.alive and p.role.alignment != Alignment.DEMON
        ]
        if target.role.name == "Mayor" and not self.is_drunk_or_poisoned(target, game):
            redirect_target = random.choice(mayor_bounce)
            if redirect_target != target:
                print(
                    f"DEBUG: Mayor bounce! Redirecting kill from {target.name} to {redirect_target.name}."
                )
            else:
                print(f"DEBUG: Mayor self-bounce! Kill remains on {target.name}.")
            target = redirect_target

        if (
            hasattr(game.state, "monk_protected")
            and game.state.monk_protected == target
        ):
            print(f"DEBUG: Target {target.name} is protected by the Monk.")
            return

        if target.role.name == "Soldier" and not self.is_drunk_or_poisoned(
            target, game
        ):
            print(f"DEBUG: Target {target.name} is the Soldier and cannot be killed.")
            return

        if target.role.name == "Ravenkeeper":
            print(
                f"DEBUG: Ravenkeeper ({target.name}) is dying at night! Triggering their ability."
            )
            game.state.pending_deaths.add(target.seat)
            game.state.history.append(f"{target.name} was killed in the night.")

            checked = target.choose_ravenkeeper_reveal(game)
            shown_role = self.ravenkeeper_info(target, checked, game)
            target.memory["info"] = {
                "night": game.state.night,
                "seen_player": checked.name if checked else None,
                "seen_role": shown_role,
            }
            print(
                f"RAVENKEEPER INFO: {target.name} (dead) checked {checked.name}: role is {shown_role}"
            )
            return

        if demon == target:
            print(f"DEBUG: Imp is trying to star-pass (suicide).")
            sw_candidates = [
                p for p in game.players if p.role.name == "Scarlet Woman" and p.alive
            ]
            if sw_candidates:
                sw = sw_candidates[0]
                print(f"DEBUG: Scarlet Woman ({sw.name}) becomes new Imp.")
                sw.role = Imp(self)
                game.state.pending_deaths.add(demon.seat)
                game.state.history.append(f"{target.name} was killed in the night.")
                return
            minion_candidates = [
                p
                for p in game.players
                if p.role.alignment == Alignment.MINION and p.alive and p != demon
            ]
            if minion_candidates:
                new_imp = random.choice(minion_candidates)
                print(
                    f"DEBUG: No Scarlet Woman; {new_imp.name} (Minion) becomes the new Imp."
                )
                new_imp.role = Imp(self)
                game.state.pending_deaths.add(demon.seat)
                game.state.history.append(f"{target.name} was killed in the night.")
                return
            else:
                print(f"DEBUG: Imp suicides, no one to inherit Demonhood.")
                game.state.pending_deaths.add(demon.seat)
                game.state.history.append(f"{target.name} was killed in the night.")
                return

        print(f"DEBUG: Demon kill successful, {target.name} dies.")
        game.state.pending_deaths.add(target.seat)
        game.state.history.append(f"{target.name} was killed in the night.")

    def poison_player(self, poisoner, target, game):
        if not hasattr(game.state, "poisoned"):
            game.state.poisoned = set()
        game.state.poisoned.add(target)
        print(f"DEBUG: Poisoner ({poisoner.name}) poisons {target.name} this night.")

    def spy_night_info(self, spy, game):
        role_map = {p.name: p.role.name for p in game.players}
        demon_bluffs = getattr(game.state, "demon_bluffs", [])
        print(f"DEBUG: Spy ({spy.name}) sees all roles: {role_map}")
        return {"all_roles": role_map, "demon_bluffs": demon_bluffs}


class Washerwoman(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Washerwoman", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night == 1:
            role_to_show, p1, p2 = self.storyteller_ai.choose_two_townsfolk(
                player, game
            )
            player.memory["info"] = {
                "seen_role": role_to_show,
                "seen_players": [p1.name if p1 else None, p2.name if p2 else None],
            }


class Librarian(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Librarian", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night == 1:
            role_to_show, p1, p2 = self.storyteller_ai.choose_two_outsiders(
                player, game
            )
            player.memory["info"] = {
                "seen_role": role_to_show,
                "seen_players": [p1.name if p1 else None, p2.name if p2 else None],
            }


class Investigator(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Investigator", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night == 1:
            role_to_show, p1, p2 = self.storyteller_ai.choose_two_minions(player, game)
            player.memory["info"] = {
                "seen_role": role_to_show,
                "seen_players": [p1.name if p1 else None, p2.name if p2 else None],
            }


class Chef(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Chef", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night == 1:
            alive_players = [p for p in game.players if p.alive]
            # Ask the storyteller how each alive player should be treated
            evilness_map = self.storyteller_ai.chef_evilness_map(alive_players)
            N = len(alive_players)
            evil_pairs = 0
            for i in range(N):
                p1 = alive_players[i]
                p2 = alive_players[(i + 1) % N]  # wrap around
                if evilness_map[p1.seat] and evilness_map[p2.seat]:
                    evil_pairs += 1
            chef_info = self.storyteller_ai.give_chef_info(player, game, evil_pairs)
            player.memory["info"] = {"pairs": chef_info}


class Empath(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Empath", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        alive_players = [p for p in game.players if game.is_player_alive(player)]
        left: Player | None = None
        right: Player | None = None
        if len(alive_players) < 3:
            evil_count = 0
        else:
            idx = alive_players.index(player)
            left = alive_players[(idx - 1) % len(alive_players)]
            right = alive_players[(idx + 1) % len(alive_players)]
            evil_count = 0
            for neighbor in [left, right]:
                if self.storyteller_ai.evil_for_empath(neighbor):
                    evil_count += 1
        empath_info = self.storyteller_ai.give_empath_info(player, game, evil_count)
        player.memory.setdefault("night_results", []).append(
            {
                "night": game.state.night,
                "player1": left.name if left else None,
                "player2": right.name if right else None,
                "num_evil": empath_info,
            }
        )


class FortuneTeller(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Fortune Teller", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        pair = player.choose_fortune_teller_targets(game)
        is_ping = self.storyteller_ai.fortune_teller_result(player, pair, game)
        player.memory.setdefault("night_results", []).append(
            {
                "night": game.state.night,
                "player1": pair[0].name if pair[0] else None,
                "player2": pair[1].name if pair[1] else None,
                "ping": is_ping,
            }
        )


class Undertaker(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Undertaker", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        # Should be called the night after an execution
        executed_player = (
            game.state.executed_today if hasattr(game.state, "executed_today") else None
        )
        if executed_player is None:
            return
        # Info may be fuzzed by StorytellerAI (e.g. for Recluse, poison, etc.)
        shown_role = self.storyteller_ai.undertaker_info(player, executed_player, game)
        player.memory.setdefault("night_results", []).append(
            {
                "night": game.state.night,
                "executed_player": executed_player.name,
                "seen_role": shown_role,
            }
        )


class Monk(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Monk", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night > 1:
            target = player.choose_monk_protect(game)
            self.storyteller_ai.monk_protect(player, target, game)
            player.memory.setdefault("info", []).append(
                {
                    "night": game.state.night,
                    "protected": target.name if target else None,
                }
            )


class Ravenkeeper(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Ravenkeeper", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai


class Virgin(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Virgin", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai
        self.has_been_nominated = False  # Track only the first nomination

    def on_nominated(self, player, nominator, game):
        if self.has_been_nominated:
            return
        self.has_been_nominated = True
        if not player.alive:
            return
        self.storyteller_ai.virgin_nomination_check(player, nominator, game)


class Slayer(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Slayer", Alignment.TOWNSFOLK)
        self.storyteller_ai = storyteller_ai
        self.has_shot = False

    def use_ability(self, player, target, game):
        """
        Use Slayer ability on a target.
        - player: the Slayer (self)
        - target: Player object to be shot
        - game: game state object
        """
        if self.has_shot:
            return  # Only once per game
        self.has_shot = True
        self.storyteller_ai.slayer_shot(player, target, game)


class Soldier(Role):
    def __init__(self):
        super().__init__("Soldier", Alignment.TOWNSFOLK)


class Mayor(Role):
    def __init__(self):
        super().__init__("Mayor", Alignment.TOWNSFOLK)


class Butler(Role):
    def __init__(self):
        super().__init__("Butler", Alignment.OUTSIDER)

    def night_action(self, player, game):
        target = player.choose_master(game)
        self.master = target
        player.memory.setdefault("info", []).append(
            {
                "night": game.state.night,
                "master": target.name if target else None,
            }
        )


class Recluse(Role):
    def __init__(self):
        super().__init__("Recluse", Alignment.OUTSIDER)


class Drunk(Role):
    def __init__(self, storyteller_ai, cover_role_name):
        super().__init__("Drunk", Alignment.OUTSIDER)
        self.storyteller_ai = storyteller_ai
        self.cover_role_name = cover_role_name
        self.cover_role = None

    def assign_cover_role(self, game):
        self.cover_role = create_role(self.cover_role_name, self.storyteller_ai)

    def night_action(self, player, game):
        # Behave exactly as cover role for decision-making
        if self.cover_role is None:
            self.assign_cover_role(game)
        # Call cover role's night_action, but StorytellerAI should always treat them as drunk
        assert self.cover_role is not None
        self.cover_role.night_action(player, game)

    def day_action(self, player, game):
        if self.cover_role is None:
            self.assign_cover_role(game)
        assert self.cover_role is not None
        self.cover_role.day_action(player, game)


class Saint(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Saint", Alignment.OUTSIDER)
        self.storyteller_ai = storyteller_ai


class Poisoner(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Poisoner", Alignment.MINION)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        # Player/AI chooses a poison target (not self, per rules, but you can allow it for testing)
        target = player.choose_poisoner_target(game)
        self.storyteller_ai.poison_player(player, target, game)
        player.memory["poisoned"] = target.name if target else None


class Spy(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Spy", Alignment.MINION)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        # See all roles (and which bluffs Demon is using)
        info = self.storyteller_ai.spy_night_info(player, game)
        player.memory["info"] = info


class Baron(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Baron", Alignment.MINION)
        self.storyteller_ai = storyteller_ai


class ScarletWoman(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Scarlet Woman", Alignment.MINION)
        self.storyteller_ai = storyteller_ai


class Imp(Role):
    def __init__(self, storyteller_ai):
        super().__init__("Imp", Alignment.DEMON)
        self.storyteller_ai = storyteller_ai

    def night_action(self, player, game):
        if game.state.night > 1:
            target = player.choose_imp_kill(game)
            self.storyteller_ai.resolve_demon_kill(player, target, game)
            player.memory["kill_target"] = target.name if target else None


if __name__ == "__main__":
    import sys

    # Alias this module as 'game' so the controller modules can import it
    sys.modules.setdefault("game", sys.modules[__name__])

    from good_player_controller import GoodPlayerController
    from evil_player_controller import EvilPlayerController

    ai = DumbStorytellerAI()

    player_count = 8
    player_names = [f"Player {i+1}" for i in range(player_count)]
    roles = random_trouble_brewing_setup(player_count, ai)

    game = Game(player_names, roles)

    human_idx = random.randrange(len(game.players))
    for idx, p in enumerate(game.players):
        if idx == human_idx:
            p.controller = HumanPlayerController()
        elif p.role.alignment in (Alignment.MINION, Alignment.DEMON):
            p.controller = EvilPlayerController()
        else:
            p.controller = GoodPlayerController()
        p.controller.set_player(p)

    print(f"Human player is {game.players[human_idx].name} as {game.players[human_idx].role.name}\n")
    print("Starting game...\n")    
    game.run()


    # TODO: Better bluffs/ Confirmation increase 'trust'
    # TODO: Improve storyteller handling of drunk/ poisoned