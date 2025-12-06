import hashlib
import hmac
import time
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class GameMode(Enum):
    FEED = "feed"          # RTP too low → give wins
    BALANCED = "balanced"  # normal play
    PUNISH = "punish"      # RTP too high → kill greed

@dataclass
class Door:
    multiplier: float
    is_safe: bool
    is_jackpot: bool = False

@dataclass
class GameState:
    bet_amount: float
    current_pot: float
    round: int
    seed_client: str
    seed_server: str
    history: List[Door]  # chosen doors so far

class DoorsGameEngine:
    def __init__(self, target_rtp: float = 0.95, jackpot_at_round: int = 10, jackpot_multiplier: float = 1000.0):
        self.target_rtp = target_rtp
        self.jackpot_at_round = jackpot_at_round
        self.jackpot_multiplier = jackpot_multiplier

        # Global stats (in real app: use Redis or DB)
        self.global_stats = {
            "total_wagered": 0.0,
            "total_paid": 0.0,
            "games_played": 0,
            "big_wins": 0  # >100x
        }

    def _get_current_mode(self) -> GameMode:
        """Determine if we need to feed or punish players"""
        if self.global_stats["games_played"] == 0:
            return GameMode.BALANCED

        rtp_1h = self.global_stats["total_paid"] / (self.global_stats["total_wagered"] or 1)
        
        if rtp_1h > self.target_rtp + 0.03:
            return GameMode.PUNISH
        elif rtp_1h < self.target_rtp - 0.04:
            return GameMode.FEED
        else:
            return GameMode.BALANCED

    def _generate_server_seed(self) -> str:
        return hashlib.sha256(str(time.time()).encode() + random.bytes(32)).hexdigest()

    def _hmac_hash(self, server_seed: str, client_seed: str, round: int) -> str:
        message = f"{client_seed}-{round}"
        return hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _float_from_hash(self, hash_hex: str, max_value: float = 1.0) -> float:
        """Convert first 8 chars of hash to float 0.00–1.00"""
        val = int(hash_hex[:13], 16)
        return (val / 2**52) * max_value

    def generate_round(self, client_seed: str, server_seed: str, current_round: int, current_pot: float, initial_bet: float) -> Tuple[List[Door], str]:
        """
        Returns: (list of doors for this round, server_seed_hashed for provably fair)
        """
        mode = self._get_current_mode()
        hash_input = self._hmac_hash(server_seed, client_seed, current_round)
        rnd = self._float_from_hash(hash_input + "doors")  # deterministic randomness

        random.seed(hash_input)  # make all random calls deterministic

        # Dynamic door count based on round & mode
        if current_round <= 2 or mode == GameMode.FEED:
            door_count = random.choices([2, 3], weights=[0.7, 0.3], k=1)[0]
        elif current_round >= 8:
            door_count = random.choices([2, 3, 4], weights=[0.4, 0.4, 0.2], k=1)[0]
        else:
            door_count = random.choices([3, 4], weights=[0.6, 0.4], k=1)[0]

        doors: List[Door] = []
        safe_multiplier = self._calculate_safe_multiplier(current_round, current_pot, initial_bet, mode, rnd)
        safe_index = random.randint(0, door_count - 1)

        is_jackpot_round = (current_round == self.jackpot_at_round)

        for i in range(door_count):
            if i == safe_index:
                mult = self.jackpot_multiplier if is_jackpot_round and random.random() < 0.1 else safe_multiplier
                doors.append(Door(multiplier=round(mult, 2), is_safe=True, is_jackpot=is_jackpot_round))
            else:
                # Monster door bait
                bait = self._generate_bait_multiplier(current_round, current_pot, initial_bet, mode, rnd)
                doors.append(Door(multiplier=bait, is_safe=False))

        random.shuffle(doors)  # client can't predict position
        return doors, hashlib.sha256(server_seed.encode()).hexdigest()[:16] + "..."  # masked for frontend

    def _calculate_safe_multiplier(self, round_num: int, current_pot: float, initial_bet: float, mode: GameMode, rnd: float) -> float:
        current_mult = current_pot / initial_bet if initial_bet > 0 else 1.0

        base = 1.0
        if mode == GameMode.FEED:
            base = random.uniform(1.8, 4.2) if round_num <= 3 else random.uniform(1.4, 2.8)
        elif mode == GameMode.PUNISH:
            if current_mult > 20:
                base = random.uniform(1.05, 1.20)
            elif current_mult > 50:
                base = random.uniform(1.02, 1.12)
            else:
                base = random.uniform(1.10, 1.60)
        else:  # BALANCED
            if round_num <= 3:
                base = random.triangular(1.6, 3.5, 2.4)
            elif round_num <= 6:
                base = random.triangular(1.3, 2.8, 1.7)
            elif round_num <= 8:
                base = random.uniform(1.12, 1.70)
            else:
                base = random.uniform(1.08, 1.45)

        # Final correction to keep long-term RTP
        if current_mult > 100 and rnd < 0.3:
            base = max(1.03, base * 0.9)

        return max(1.01, base)  # never <1.01x safe

    def _generate_bait_multiplier(self, round_num: int, current_pot: float, initial_bet: float, mode: GameMode, rnd: float) -> float:
        current_mult = current_pot / initial_bet if initial_bet > 0 else 1.0

        if mode == GameMode.PUNISH and current_mult > 15 and rnd < 0.75:
            # GREED KILL: show insane bait
            return round(random.choice([8, 12, 18, 25, 35, 50, 99]) * random.uniform(0.9, 1.3), 2)
        elif mode == GameMode.FEED:
            return round(random.uniform(1.1, 2.2), 2)
        else:
            if round_num >= 5 and current_mult > 10 and random.random() < 0.6:
                return round(random.uniform(5.0, 25.0), 2)
            else:
                return round(random.uniform(1.15, 3.8), 2)

    def resolve_pick(self, doors: List[Door], picked_index: int, game_state: GameState):
        picked = doors[picked_index]
        if picked.is_safe:
            game_state.current_pot *= picked.multiplier
            game_state.round += 1
            if picked.is_jackpot:
                game_state.current_pot = game_state.bet_amount * self.jackpot_multiplier
            return True, game_state.current_pot
        else:
            # Player loses everything
            self.global_stats["total_wagered"] += game_state.current_pot / (game_state.current_pot / game_state.bet_amount)  # count risked amount
            return False, 0.0

    def cashout(self, game_state: GameState):
        won = game_state.current_pot
        self.global_stats["total_wagered"] += game_state.bet_amount
        self.global_stats["total_paid"] += won
        self.global_stats["games_played"] += 1
        if won >= game_state.bet_amount * 100:
            self.global_stats["big_wins"] += 1
        return won