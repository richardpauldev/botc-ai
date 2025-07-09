from __future__ import annotations

import random
from typing import List, Tuple

from deduction_engine import generate_all_worlds, deduction_pipeline, compute_role_probs
from game import (
    PlayerController,
    Player,
    PlayerView,
    Alignment,
    TROUBLE_BREWING_ROLES,
    player_role_counts,
)


class EvilPlayerController(PlayerController):
    """AI controller for evil team players."""

    def __init__(self):
        super().__init__()
        self.chosen_bluff: str | None = None
        self.has_claimed = False

    # Utility ---------------------------------------------------------------
    def _evil_imp_probs(self, player_view: PlayerView) -> Tuple[dict, dict]:
        """Run deduction without filtering by POV using ``PlayerView``."""
        TB_ROLES = {
            a.value if hasattr(a, "value") else a: roles
            for a, roles in TROUBLE_BREWING_ROLES.items()
        }
        player_names = [name for name in player_view.seat_names.values()]
        m_minions, outsider_count = player_role_counts(len(player_names))

        claims = {}
        for seat, name in player_view.seat_names.items():
            c = dict(player_view.public_claims.get(seat, {}) or {})
            claims[name] = c

        try:
            worlds = generate_all_worlds(
                player_names,
                TB_ROLES["Minion"],
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
        except Exception as e:  # pragma: no cover - fallback for early bugs
            print(f"Deduction error: {e}")
            evil_prob = {name: 0.0 for name in player_names}
            imp_prob = {name: 0.0 for name in player_names}
        return evil_prob, imp_prob

    def _alive_players(self, candidates: List[Player], player_view: PlayerView) -> List[Player]:
        alive_seats = set(player_view.alive_players)
        return [p for p in candidates if p.seat in alive_seats]

    # Voting and nominations -----------------------------------------------
    def choose_nominee(
        self, candidates: List[Player], player_view: PlayerView
    ):
        """Evil players avoid nominating."""
        return None

    def cast_vote(self, nominee: Player, player_view: PlayerView) -> bool:
        """Evil players abstain from voting."""
        return False

    # Night actions --------------------------------------------------------
    def choose_poisoner_target(self, candidates, player_view):
        goods = [p for p in candidates if p != self.player]

        evil_names = {info["name"] for info in self.player.memory.get("evil_team", [])}
        goods = [p for p in goods if p.name not in evil_names]
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
        if player_view.night == 1:
            return random.choice(goods) if goods else None
        info_claimers = [
            p
            for p in goods
            if player_view.public_claims.get(p.seat, {}).get("role") in info_roles
        ]
        if info_claimers:
            return random.choice(info_claimers)
        return random.choice(goods) if goods else None

    def choose_imp_kill(self, candidates, player_view):
        targets = [p for p in candidates if p.alive and p != self.player]

        evil_prob, imp_prob = self._evil_imp_probs(player_view)
        minion_names = [
            info["name"]
            for info in self.player.memory.get("evil_team", [])
            if info["alignment"] == Alignment.MINION
        ]
        minions = [p for p in candidates if p.name in minion_names]
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
        targets = [p for p in candidates if p.alive and p != self.player and not p in minions]
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

    def choose_master(self, candidates, player_view):
        others = [p for p in candidates if p != self.player]
        return random.choice(others) if others else None

    # Bluffing -------------------------------------------------------------
    def _select_bluff(self, player_view):
        bluffs = self.player.memory.get("bluffs")
        if not bluffs:
            return None
        claimed = {c.get("role") for c in player_view.public_claims.values() if c}
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

    def _fake_info(self, bluff_role, player_view):
        demon_name = None
        for info in self.player.memory.get("evil_team", []):
            if info["alignment"] == Alignment.DEMON:
                demon_name = info["name"]
                break
        others = [name for seat, name in player_view.seat_names.items() if name != demon_name]
        if bluff_role == "Investigator":
            seen_role = random.choice(TROUBLE_BREWING_ROLES[Alignment.MINION])
            players = random.sample(others, 2)
            return {"seen_role": seen_role, "seen_players": players}
        if bluff_role == "Librarian":
            seen_role = "Drunk"
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

    def share_info(self, player_view: PlayerView, context=None):
        if self.has_claimed:
            return None
        bluff = self._select_bluff(player_view)
        if not bluff:
            return None
        self.chosen_bluff = bluff
        self.player.claim = {"role": bluff}
        info = self._fake_info(bluff, player_view)
        if info:
            self.player.claim.update(info)
        self.has_claimed = True
        return {"public_claim": self.player.claim}
