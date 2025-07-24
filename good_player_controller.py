"""Heuristic Good player controller."""

from __future__ import annotations

import random
import itertools
from typing import List, Tuple

from deduction_engine import (
    generate_all_worlds,
    deduction_pipeline,
    compute_role_probs,
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

    def __init__(self):
        super().__init__()
        self._last_public = None

    def _evil_imp_probs(self, player_view: PlayerView) -> Tuple[dict, dict]:
        """Run deduction using only the provided ``PlayerView``."""
        TB_ROLES = {
            a.value if hasattr(a, "value") else a: roles
            for a, roles in TROUBLE_BREWING_ROLES.items()
        }
        player_names = [name for name in player_view.seat_names.values()]
        m_minions, outsider_count = player_role_counts(len(player_names))

        claims = {}
        for seat, name in player_view.seat_names.items():
            c = dict(player_view.public_claims.get(seat, {}) or {})
            if seat == player_view.player_seat:
                c["role"] = player_view.role_name
                if "night_results" in player_view.memory:
                    c["night_results"] = player_view.memory["night_results"]
                if "info" in player_view.memory:
                    c.update(player_view.memory["info"])
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
                pov_player=self.player.name,
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

    # Utility ---------------------------------------------------------------
    def _alive_players(self, candidates: List[Player], player_view: PlayerView) -> List[Player]:
        alive_seats = set(player_view.alive_players)
        return [p for p in candidates if p.seat in alive_seats]

    def _possible_worlds(self, player_view: PlayerView):
        """Return all worlds consistent with this player's knowledge."""
        TB_ROLES = {
            a.value if hasattr(a, "value") else a: roles
            for a, roles in TROUBLE_BREWING_ROLES.items()
        }
        player_names = [name for name in player_view.seat_names.values()]
        m_minions, outsider_count = player_role_counts(len(player_names))

        claims = {}
        for seat, name in player_view.seat_names.items():
            c = dict(player_view.public_claims.get(seat, {}) or {})
            if seat == player_view.player_seat:
                c["role"] = player_view.role_name
                if "night_results" in player_view.memory:
                    c["night_results"] = player_view.memory["night_results"]
                if "info" in player_view.memory:
                    c.update(player_view.memory["info"])
            claims[name] = c

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
    def choose_nominee(
        self, candidates: List[Player], player_view: PlayerView
    ):
        """Pick someone to nominate based on evil probability.

        This implementation selects the most suspicious living player and
        attempts to nominate them. If that player has already been nominated,
        the controller declines to nominate anyone else, leading to fewer
        overall nominations.
        """
        alive = self._alive_players(candidates, player_view)
        evil_prob, _ = self._evil_imp_probs(player_view)

        others = [p for p in alive if p != self.player]
        if not others:
            return None

        final_three = len(alive) == 3

        ranked = sorted(others, key=lambda p: evil_prob[p.name], reverse=True)
        target = ranked[0]

        return target

    def cast_vote(self, nominee: Player, player_view: PlayerView) -> bool:
        """Decide whether to vote for a nominee.

        Dead players only vote in the final three. Players compare the nominee
        to the current leading candidate and usually vote only if they believe
        the nominee is more likely evil.
        """
        evil_prob, imp_prob = self._evil_imp_probs(player_view)
        num_alive = len(player_view.alive_players)
        final_three = num_alive <= 3

        if num_alive == 4: # Don't vote on final 4
            return False

        # Dead players will only vote in the final three
        if not self.player.alive and not final_three:
            return False

        # Determine who is currently leading the vote
        leader = None
        leader_votes = -1
        for n_name, voters in player_view.votes.items():
            if len(voters) > leader_votes and len(voters) >= num_alive / 2:
                leader_votes = len(voters)
                leader = n_name

        leader_score = evil_prob.get(leader, 0)
        nominee_score = evil_prob[nominee.name]

        if final_three:
            alive_names = [player_view.seat_names[s] for s in player_view.alive_players]
            best_demon = max(alive_names, key=lambda n: imp_prob.get(n, 0)) if alive_names else None
            if nominee.name != best_demon:
                return False
            return True
            

        # Outside final three -------------------------------------------------
        if leader and leader != nominee.name and leader_score >= nominee_score:
            # Current leader is at least as suspicious; don't change the vote
            return False

        # Weight vote probability by how suspicious the nominee is
        if leader_score == 0:
            chance = 1
        else:
            chance = (nominee_score / leader_score) / 50.0
        if num_alive % 2 == 0:
            chance *= 2
        else:
            chance /= 2
        # Small baseline so highly suspected players are voted more often
        return random.random() < max(chance, .3)

    # Night actions --------------------------------------------------------
    def choose_fortune_teller_targets(self, candidates, player_view):

        worlds = self._possible_worlds(player_view)
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

    def choose_monk_protect(self, candidates, player_view):

        evil_prob, _ = self._evil_imp_probs(player_view)
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
    
    def choose_master(self, candidates, player_view):
        evil_prob, _ = self._evil_imp_probs(player_view)
        others = [p for p in candidates if p != self.player]
        if not others:
            return None
        best = max(others, key=lambda p: 100 - evil_prob[p.name])
        return best

    def choose_ravenkeeper_reveal(self, candidates, player_view):

        worlds = self._possible_worlds(player_view)
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

    def share_info(self, player_view: PlayerView, context=None):
        # info = self.player.memory
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

