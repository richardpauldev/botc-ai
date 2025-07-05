"""Heuristic Good player controller."""

from __future__ import annotations

import random
import itertools
from typing import List, Tuple

from deduction_engine import (
    deduce_game,
    generate_all_worlds,
    deduction_pipeline,
)
from game import (
    PlayerController,
    Player,
    PlayerView,
    player_role_counts,
    TROUBLE_BREWING_ROLES,
)


class GoodPlayerController(PlayerController):
    """A simple AI for good players using deduction heuristics."""

    def _evil_imp_probs(self, game) -> Tuple[dict, dict]:
        """Run deduction from this player's perspective."""
        return deduce_game(game, pov_player=self.player.name)

    # Utility ---------------------------------------------------------------
    def _alive_players(self, game: "Game") -> List[Player]:
        return [p for p in game.players if p.alive]

    def _possible_worlds(self, game):
        """Return all worlds consistent with this player's knowledge."""
        TB_ROLES = {
            a.value if hasattr(a, "value") else a: roles
            for a, roles in TROUBLE_BREWING_ROLES.items()
        }
        player_names = [p.name for p in game.players]
        m_minions, outsider_count = player_role_counts(len(game.players))

        claims = {}
        for p in game.players:
            c = dict(p.claim) if getattr(p, "claim", None) else {}
            if p is self.player:
                c["role"] = p.role.name
                if "night_results" in p.memory:
                    c["night_results"] = p.memory["night_results"]
                if "info" in p.memory:
                    c.update(p.memory["info"])
            claims[p.name] = c

        worlds = generate_all_worlds(
            player_names,
            TB_ROLES["Minion"],
            m_minions,
            claims,
            TB_ROLES,
            outsider_count,
            deaths=[],
            pov_player=self.player.name,
        )
        return deduction_pipeline(worlds, TB_ROLES)

    def _ft_ping(self, world, pair):
        names = [p.name for p in pair]
        demon_seen = any(
            world.roles.get(n) in ("Imp", "Recluse") for n in names
        )
        if world.red_herring and world.red_herring in names:
            demon_seen = True
        return demon_seen

    # Voting and nominations -----------------------------------------------
    def choose_nominee(self, candidates: List[Player], player_view: PlayerView, game=None):
        if game is None:
            return None

        alive = self._alive_players(game)
        if len(alive) <= 4:
            return None

        evil_prob, _ = self._evil_imp_probs(game)
        best = max((p for p in alive if p != self.player), key=lambda p: evil_prob[p.name])
        # Some randomness so behavior is not deterministic
        if random.random() < 0.2:
            return None
        return best

    def cast_vote(self, nominee: Player, player_view: PlayerView, game=None) -> bool:
        if game is None:
            return False

        alive = self._alive_players(game)
        evil_prob, imp_prob = self._evil_imp_probs(game)

        if len(alive) <= 3:
            target = max(alive, key=lambda p: imp_prob[p.name])
            return nominee == target
        if len(alive) == 4:
            return False

        target = max((p for p in alive if p != self.player), key=lambda p: evil_prob[p.name])
        return nominee == target and random.random() < 0.9

    # Night actions --------------------------------------------------------
    def choose_fortune_teller_targets(self, candidates, player_view, game=None):
        if game is None:
            return random.sample(candidates, 2)

        worlds = self._possible_worlds(game)
        others = [p for p in candidates if p != self.player]
        if len(others) < 2:
            return tuple(random.sample(candidates, 2))

        best_pair = None
        best_score = float("inf")
        for pair in itertools.combinations(others, 2):
            true_count = sum(1 for w in worlds if self._ft_ping(w, pair))
            false_count = len(worlds) - true_count
            score = true_count ** 2 + false_count ** 2
            if score < best_score:
                best_score = score
                best_pair = pair

        return best_pair if best_pair else tuple(random.sample(others, 2))

    def choose_monk_protect(self, candidates, player_view, game=None):
        if game is None:
            return random.choice(candidates) if candidates else None

        evil_prob, _ = self._evil_imp_probs(game)
        info_roles = {
            "Empath",
            "Fortune Teller",
            "Undertaker",
            "Ravenkeeper",
        }
        best = None
        best_score = -1.0
        for p in candidates:
            claim = player_view.public_claims.get(p.seat, {}).get("role")
            if claim == "Soldier":
                continue
            prob_good = 100 - evil_prob[p.name]
            score = prob_good
            if claim in info_roles:
                score *= 1.5
            score *= random.uniform(0.8, 1.2)
            if score > best_score:
                best = p
                best_score = score
        return best

    def choose_ravenkeeper_reveal(self, candidates, player_view, game=None):
        if game is None:
            return random.choice(candidates) if candidates else None

        worlds = self._possible_worlds(game)
        others = [p for p in candidates if p != self.player]
        best_target = None
        best_score = float("inf")
        for t in others:
            counts = {}
            for w in worlds:
                role = w.roles.get(t.name)
                counts[role] = counts.get(role, 0) + 1
            score = sum(c * c for c in counts.values())
            if score < best_score:
                best_score = score
                best_target = t

        return best_target if best_target else (random.choice(others) if others else None)

    def share_info(self, game, self_player, context=None):
        info = self_player.memory
        for target in game.players:
            self.send_info(target, {"from": self_player.name, "public": info})

