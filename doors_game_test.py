# =============================================
# SAVE THIS AS: doors_game_test.py
# =============================================

import hashlib
import hmac
import time
import random
from typing import List, Tuple
from dataclasses import dataclass

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

class DoorsGameEngine:
    def __init__(self, target_rtp: float = 0.952, jackpot_round: int = 10, jackpot_multiplier: float = 1500):
        self.target_rtp = target_rtp
        self.jackpot_round = jackpot_round
        self.jackpot_multiplier = jackpot_multiplier
        self.total_wagered = 0
        self.total_paid = 0

    def _hmac_hash(self, server_seed: str, client_seed: str, round_num: int) -> str:
        message = f"{client_seed}-{round_num}"
        return hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _float_from_hash(self, hash_hex: str) -> float:
        val = int(hash_hex[:13], 16)
        return (val / 2**52)

    def generate_round(self, client_seed: str, server_seed: str, round_num: int, current_pot: float, initial_bet: float) -> List[Door]:
        hash_input = self._hmac_hash(server_seed, client_seed, round_num)
        random.seed(hash_input)

        # Decide number of doors
        if round_num <= 2:
            door_count = random.choice([2, 3])
        elif round_num >= 8:
            door_count = random.choice([2, 3, 4])
        else:
            door_count = random.choice([3, 4])

        # Decide safe multiplier (the real one)
        current_mult = current_pot / initial_bet
        if round_num <= 3:
            safe_mult = random.triangular(1.7, 3.8, 2.5)
        elif round_num <= 6:
            safe_mult = random.triangular(1.3, 2.6, 1.7)
        elif current_mult > 30:
            safe_mult = random.uniform(1.05, 1.25)   # punish high pots
        else:
            safe_mult = random.uniform(1.10, 1.65)

        safe_mult = round(max(1.01, safe_mult), 2)
        safe_index = random.randint(0, door_count - 1)

        doors = []
        for i in range(door_count):
            if i == safe_index:
                if round_num == self.jackpot_round and random.random() < 0.08:
                    doors.append(Door(self.jackpot_multiplier, True, True))
                else:
                    doors.append(Door(safe_mult, True))
            else:
                # Monster bait logic
                if current_mult > 15 and random.random() < 0.7:
                    bait = round(random.choice([9, 14, 19, 27, 38, 55, 99]) * random.uniform(0.85, 1.2), 2)
                else:
                    bait = round(random.uniform(1.2, 4.5), 2)
                doors.append(Door(bait, False))

        random.shuffle(doors)
        return doors

# =============================================
# DEMO – RUN 10 GAMES AUTOMATICALLY
# =============================================

engine = DoorsGameEngine()

print("DOORS GAME – PSYCHOLOGICAL DEMO")
print("Starting 10 simulated games with 100 TND bets...\n")

total_profit = 0

for game in range(1, 11):
    client_seed = f"player{game}-2025"
    server_seed = hashlib.sha256(f"secret{time.time()+game}".encode()).hexdigest()
    
    bet = 100.0
    state = GameState(bet_amount=bet, current_pot=bet, round=1)
    
    print(f"Game #{game} | Bet: {bet} TND")
    
    survived_rounds = 0
    while True:
        doors = engine.generate_round(client_seed, server_seed, state.round, state.current_pot, bet)
        
        # Simulate player behavior: 70% chance pick the highest multiplier (greedy!)
        highest_idx = 0
        for i in range(len(doors)):
            if doors[i].multiplier > doors[highest_idx].multiplier:
                highest_idx = i
        
        # 30% chance pick random (less greedy)
        picked_idx = random.choices([highest_idx, random.randint(0, len(doors)-1)], weights=[0.70, 0.30], k=1)[0]
        picked = doors[picked_idx]
        
        print(f"  Round {state.round} | Doors: {[f'{d.multiplier}x' for d in doors]} | Chose {picked.multiplier}x → ", end="")

        if picked.is_safe:
            old_pot = state.current_pot
            state.current_pot *= picked.multiplier if not picked.is_jackpot else bet * engine.jackpot_multiplier
            survived_rounds += 1
            print(f"SURVIVED! {old_pot:.0f} → {state.current_pot:.0f} TND")
            
            # Cashout logic: 60% chance to cashout after round 5+
            if state.round >= 5 and random.random() < 0.60:
                print(f"  CASHOUT at {state.current_pot:.2f} TND !")
                profit = state.current_pot - bet
                total_profit += profit
                engine.total_paid += state.current_pot
                break
        else:
            print("MONSTER! Lost everything!")
            profit = -bet
            total_profit += profit
            break
            
        state.round += 1
        if state.round > 15:
            break
    
    engine.total_wagered += bet
    print(f"  → Profit this game: {profit:+.2f} TND\n")

# Final stats
rtp = engine.total_paid / engine.total_wagered if engine.total_wagered > 0 else 0
print(f"TOTAL PROFIT AFTER 10 GAMES: {total_profit:+.2f} TND")
print(f"Actual RTP: {rtp*100:.2f}% (target ~95%)")