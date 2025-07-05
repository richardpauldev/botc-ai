from __future__ import annotations

import random
from typing import List, Tuple

from deduction_engine import deduce_game
from game import (
    PlayerController,
    Player,
    PlayerView,
    Alignment,
    TROUBLE_BREWING_ROLES,
)


class EvilPlayerController(PlayerController):
    """AI controller for evil team players."""

    def __init__(self):
        super().__init__()
        self.chosen_bluff: str | None = None
        self.has_claimed = False

    # Utility ---------------------------------------------------------------
    def _evil_imp_probs(self, game) -> Tuple[dict, dict]:
        """Run deduction without filtering by POV."""
        return deduce_game(game)

    def _alive_players(self, game: "Game") -> List[Player]:
        return [p for p in game.players if p.alive]

    # Voting and nominations -----------------------------------------------
    def choose_nominee(
        self, candidates: List[Player], player_view: PlayerView, game=None
    ):
        """Evil players avoid nominating."""
        return None

    def cast_vote(self, nominee: Player, player_view: PlayerView, game=None) -> bool:
        """Evil players abstain from voting."""
        return False

    # Night actions --------------------------------------------------------
    def choose_poisoner_target(self, candidates, player_view, game=None):
        if game is None:
            goods = [p for p in candidates if p != self.player]
            return random.choice(goods) if goods else None

        evil_names = {info["name"] for info in self.player.memory.get("evil_team", [])}
        goods = [p for p in candidates if p.name not in evil_names and p != self.player]
        if not goods:
            goods = [p for p in candidates if p != self.player]

        info_roles = {
            "Washerwoman",
            "Librarian",
            "Investigator",
            "Chef",
            "Empath",
            "Fortune Teller",
            "Undertaker",
            "Ravenkeeper",
        }
        if game.state.night == 1:
            return random.choice(goods) if goods else None
        info_claimers = [
            p
            for p in goods
            if player_view.public_claims.get(p.seat, {}).get("role") in info_roles
        ]
        if info_claimers:
            return random.choice(info_claimers)
        return random.choice(goods) if goods else None

    def choose_imp_kill(self, candidates, player_view, game=None):
        if game is None:
            targets = [p for p in candidates if p.alive and p != self.player]
            return random.choice(targets) if targets else None

        evil_prob, imp_prob = self._evil_imp_probs(game)
        minions = [p for p in game.players if p.role.alignment == Alignment.MINION]
        minion_imp_probs = [imp_prob.get(m.name, 0) for m in minions]
        self_imp_prob = imp_prob.get(self.player.name, 0)
        if minion_imp_probs:
            lowest_minion_imp = min(minion_imp_probs)
        else:
            lowest_minion_imp = 0

        if self_imp_prob > 50 and lowest_minion_imp < 20:
            return self.player

        info_roles = {
            "Washerwoman",
            "Librarian",
            "Investigator",
            "Chef",
            "Empath",
            "Fortune Teller",
            "Undertaker",
            "Ravenkeeper",
        }
        targets = [p for p in candidates if p.alive and p != self.player]
        best = None
        best_score = float("inf")
        for t in targets:
            score = imp_prob.get(t.name, 0)
            claim = player_view.public_claims.get(t.seat, {}).get("role")
            if claim in info_roles:
                score *= 0.5
            if score < best_score:
                best = t
                best_score = score
        return best if best else (random.choice(targets) if targets else None)

    # Bluffing -------------------------------------------------------------
    def _select_bluff(self, game):
        bluffs = self.player.memory.get("bluffs")
        if not bluffs:
            demon_name = None
            for info in self.player.memory.get("evil_team", []):
                if info["alignment"] == Alignment.DEMON:
                    demon_name = info["name"]
                    break
            if demon_name:
                demon = next((p for p in game.players if p.name == demon_name), None)
                if demon:
                    bluffs = demon.memory.get("bluffs", [])
        if not bluffs:
            return None
        claimed = {p.claim.get("role") for p in game.players if p.claim}
        available = [b for b in bluffs if b not in claimed]
        if not available:
            available = bluffs
        info_roles = {
            "Washerwoman",
            "Librarian",
            "Investigator",
            "Chef",
            "Empath",
            "Fortune Teller",
            "Undertaker",
            "Ravenkeeper",
        }
        if self.player.role.alignment == Alignment.MINION:
            info_avail = [b for b in available if b in info_roles]
            if info_avail:
                available = info_avail
        return random.choice(available)

    def _fake_info(self, bluff_role, game):
        demon_name = None
        for info in self.player.memory.get("evil_team", []):
            if info["alignment"] == Alignment.DEMON:
                demon_name = info["name"]
                break
        others = [p.name for p in game.players if p.name != demon_name]
        if bluff_role == "Investigator":
            seen_role = random.choice(TROUBLE_BREWING_ROLES[Alignment.MINION])
            players = random.sample(others, 2)
            return {"seen_role": seen_role, "seen_players": players}
        if bluff_role == "Librarian":
            seen_role = random.choice(TROUBLE_BREWING_ROLES[Alignment.OUTSIDER])
            players = random.sample(others, 2)
            return {"seen_role": seen_role, "seen_players": players}
        if bluff_role == "Washerwoman":
            role = random.choice(TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK])
            players = random.sample(others, 2)
            return {"seen_role": role, "seen_players": players}
        if bluff_role == "Chef":
            return {"pairs": 0}
        if bluff_role == "Empath":
            return {"night_results": [{"night": 1, "player1": others[0], "player2": others[1], "num_evil": 0}]}
        if bluff_role == "Fortune Teller":
            return {"night_results": [{"night": 1, "player1": others[0], "player2": others[1], "ping": False}]}
        if bluff_role == "Undertaker":
            return {"night_results": []}
        if bluff_role == "Ravenkeeper":
            return {}
        return {}

    def share_info(self, game, self_player, context=None):
        if self.has_claimed:
            return
        bluff = self._select_bluff(game)
        if not bluff:
            return
        self.chosen_bluff = bluff
        self_player.claim = {"role": bluff}
        info = self._fake_info(bluff, game)
        if info:
            self_player.claim.update(info)
        self.has_claimed = True
        for target in game.players:
            self.send_info(target, {"from": self_player.name, "public_claim": self_player.claim})
