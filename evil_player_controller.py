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
        alive_seats = set(player_view.alive_players)

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

        if self_imp_prob > 50 and self_imp_prob - lowest_minion_imp > 25:
            return self.player
        
        targets = [p for p in candidates if p.seat in alive_seats and p != self.player and p not in minions]

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
        assigned = self.player.memory.get("assigned_bluff")
        if assigned:
            return assigned
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
        team = [info["name"] for info in self.player.memory.get("evil_team", [])]
        for info in self.player.memory.get("evil_team", []):
            if info["alignment"] == Alignment.DEMON:
                demon_name = info["name"]
                break
        others = [name for seat, name in player_view.seat_names.items() if name != self.player.name]
        assignments = self.player.memory.get("bluff_plan", {})
        if bluff_role == "Investigator":
            seen_role = random.choice(TROUBLE_BREWING_ROLES[Alignment.MINION])
            players = random.sample(others, 2)
            return {"seen_role": seen_role, "seen_players": players}
        if bluff_role == "Librarian":
            buddy_opts = [n for n in team if n != self.player.name]
            if buddy_opts:
                buddy = random.choice(buddy_opts)
                other = random.choice([n for n in others if n != buddy])
                role = assignments.get(buddy, "Drunk")
                if role not in TROUBLE_BREWING_ROLES[Alignment.OUTSIDER]:
                    role = "Drunk"
                players = [buddy, other]
            else:
                role = "Drunk"
                players = random.sample(others, 2)
            return {"seen_role": role, "seen_players": players}
        if bluff_role == "Washerwoman":
            buddy_opts = [n for n in team if n != self.player.name]
            if buddy_opts:
                buddy = random.choice(buddy_opts)
                other = random.choice([n for n in others if n != buddy])
                role = assignments.get(buddy, random.choice(TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK]))
                players = [buddy, other]
            else:
                role = random.choice(TROUBLE_BREWING_ROLES[Alignment.TOWNSFOLK])
                players = random.sample(others, 2)
            return {"seen_role": role, "seen_players": players}
        if bluff_role == "Chef":
            return {"pairs": 0}
        if bluff_role == "Empath":
            alive = player_view.alive_players
            if len(alive) >= 3 and player_view.player_seat in alive:
                idx = alive.index(player_view.player_seat)
                left_seat = alive[(idx - 1) % len(alive)]
                right_seat = alive[(idx + 1) % len(alive)]
                left = player_view.seat_names[left_seat]
                right = player_view.seat_names[right_seat]
            else:
                left = None
                right = None
            return {
                "night_results": [
                    {
                        "night": 1,
                        "player1": left,
                        "player2": right,
                        "num_evil": 0,
                    }
                ]
            }        
        if bluff_role == "Fortune Teller":
            buddy_opts = [n for n in team if n != self.player.name]
            if buddy_opts:
                buddy = random.choice(buddy_opts)
                other = random.choice([n for n in others if n != buddy])
                players = [buddy, other]
            else:
                players = others[:2]
            return {"night_results": [{"night": 1, "player1": players[0], "player2": players[1], "ping": False}]}
        if bluff_role == "Undertaker":
            return {"night_results": []}
        if bluff_role == "Ravenkeeper":
            return {}
        return {}

    def share_info(self, player_view: PlayerView, context=None):
        msg = {}
        if not self.has_claimed:
            bluff = self._select_bluff(player_view)
            if bluff:
                self.chosen_bluff = bluff
                self.player.claim = {"role": bluff}
                info = self._fake_info(bluff, player_view)
                if info:
                    self.player.claim.update(info)
                self.has_claimed = True
                msg["public_claim"] = self.player.claim

        plan = self.player.memory.get("bluff_plan", {})
        confirmed = self.player.memory.setdefault("confirmed_teammates", [])
        confirmations = []
        for seat, name in player_view.seat_names.items():
            if name == self.player.name:
                continue
            claim = player_view.public_claims.get(seat)
            expected = plan.get(name)
            if claim and expected and claim.get("role") == expected and name not in confirmed:
                confirmations.append({"player": name, "role": expected})
                confirmed.append(name)
        if confirmations:
            msg["confirm"] = confirmations

        return msg if msg else None
