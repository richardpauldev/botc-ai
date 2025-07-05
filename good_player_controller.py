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
    def choose_nominee(
        self, candidates: List[Player], player_view: PlayerView, game=None
    ):
        """Pick someone to nominate based on evil probability.

        A player will sometimes decline to nominate, but must do so when only
        three players remain. Nomination choices are weighted toward players
        believed to be evil rather than always picking the single top suspect.
        """
        if game is None:
            return None

        alive = self._alive_players(game)
        evil_prob, _ = self._evil_imp_probs(game)

        others = [p for p in alive if p != self.player]
        if not others:
            return None

        final_three = len(alive) == 3

        # Chance to skip nomination unless we're in the final three
        if not final_three and random.random() < 0.3:
            return None

        weights = [max(evil_prob[p.name], 1) for p in others]
        return random.choices(others, weights=weights, k=1)[0]

    def cast_vote(self, nominee: Player, player_view: PlayerView, game=None) -> bool:
        """Decide whether to vote for a nominee.

        Dead players only vote in the final three. Players compare the nominee
        to the current leading candidate and usually vote only if they believe
        the nominee is more likely evil.
        """
        if game is None:
            return False

        alive = self._alive_players(game)
        evil_prob, imp_prob = self._evil_imp_probs(game)
        final_three = len(alive) <= 3

        # Dead players can only vote in the final three
        if not self.player.alive and not final_three:
            return False

        # Determine who is currently leading the vote
        leader = None
        leader_votes = -1
        for n_name, voters in player_view.votes.items():
            if len(voters) > leader_votes:
                leader_votes = len(voters)
                leader = n_name

        leader_score = evil_prob.get(leader, 0)
        nominee_score = evil_prob[nominee.name]

        if final_three:
            # During the final three, players are more decisive. They will vote
            # for the nominee only if they appear more evil than whoever is
            # currently leading the vote count.
            if leader and leader != nominee.name and leader_score >= nominee_score:
                return False
            chance = nominee_score / 100.0
            return random.random() < max(chance, 0.3)

        # Outside final three -------------------------------------------------
        if leader and leader != nominee.name and leader_score >= nominee_score:
            # Current leader is at least as suspicious; don't change the vote
            return False

        # Weight vote probability by how suspicious the nominee is
        chance = nominee_score / 100.0
        # Small baseline so highly suspected players are voted more often
        return random.random() < chance

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

