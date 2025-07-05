"""Heuristic Good player controller."""

from __future__ import annotations

import random
from typing import List, Tuple

from deduction_engine import deduce_game
from game import PlayerController, Player, PlayerView


class GoodPlayerController(PlayerController):
    """A simple AI for good players using deduction heuristics."""

    def _evil_imp_probs(self, game) -> Tuple[dict, dict]:
        """Run deduction from this player's perspective."""
        return deduce_game(game, pov_player=self.player.name)

    # Utility ---------------------------------------------------------------
    def _alive_players(self, game: "Game") -> List[Player]:
        return [p for p in game.players if p.alive]

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

        evil_prob, _ = self._evil_imp_probs(game)
        scored = sorted(
            [p for p in candidates if p != self.player],
            key=lambda p: evil_prob[p.name],
            reverse=True,
        )
        top_two = scored[:2] if len(scored) >= 2 else scored
        while len(top_two) < 2:
            top_two.append(random.choice(candidates))
        return tuple(top_two)

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

        evil_prob, _ = self._evil_imp_probs(game)
        scored = sorted(
            [p for p in candidates if p != self.player],
            key=lambda p: evil_prob[p.name],
            reverse=True,
        )
        pick = scored[0] if scored else None
        return pick

    def share_info(self, game, self_player, context=None):
        info = self_player.memory
        for target in game.players:
            self.send_info(target, {"from": self_player.name, "public": info})

