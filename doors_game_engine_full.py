# ================================================
# DOORS GAME – FULL PSYCHOLOGICAL ENGINE (2025)
# Run this file directly → you will play LIVE!
# ================================================

import hashlib
import hmac
import random
import time
from dataclasses import dataclass
from typing import List

@dataclass
class Door:
    multiplier: float
    is_safe: bool
    is_jackpot: bool = False

    def __str__(self):
        emoji = "JACKPOT" if self.is_jackpot else "SAFE" if self.is_safe else "MONSTER"
        return f"{self.multiplier:.2f}x [{'SAFE' if self.is_safe else 'MONSTER'}]"

class DoorsGameEngine:
    def __init__(self, target_rtp=0.952, jackpot_round=10, jackpot_mult=1500):
        self.target_rtp = target_rtp
        self.jackpot_round = jackpot_round
        self.jackpot_mult = jackpot_mult

        # Global stats (in production use Redis/DB)
        self.stats = {
            "wagered": 0.0,
            "paid": 0.0,
            "games": 0
        }

    def _get_mode(self):
        if self.stats["games"] == 0:
            return "balanced"
        rtp = self.stats["paid"] / self.stats["wagered"] if self.stats["wagered"] > 0 else 1.0
        if rtp > self.target_rtp + 0.03:
            return "punish"
        elif rtp < self.target_rtp - 0.04:
            return "feed"
        return "balanced"

    def generate_round(self, client_seed: str, server_seed: str, round_num: int, current_pot: float, initial_bet: float) -> List[Door]:
        mode = self._get_mode()
        h = hmac.new(server_seed.encode(), f"{client_seed}-{round_num}".encode(), hashlib.sha256).hexdigest()
        random.seed(h)

        # Door count logic
        if round_num <= 2 or mode == "feed":
            doors_count = random.choices([2, 3], weights=[80, 20])[0]
        elif round_num >= 8:
            doors_count = random.choices([2, 3, 4], weights=[30, 50, 20])[0]
        else:
            doors_count = random.choices([3, 4], weights=[65, 35])[0]

        current_mult = current_pot / initial_bet

        # Safe multiplier (real path)
        if mode == "feed":
            safe = random.uniform(1.9, 4.4) if round_num <= 3 else random.uniform(1.5, 3.0)
        elif mode == "punish" and current_mult > 25:
            safe = random.uniform(1.04, 1.18)
        elif round_num <= 3:
            safe = random.triangular(1.7, 4.0, 2.6)
        elif round_num <= 6:
            safe = random.triangular(1.25, 2.9, 1.7)
        else:
            safe = random.uniform(1.08, 1.55)

        safe = round(max(1.01, safe), 2)
        safe_idx = random.randint(0, doors_count - 1)

        doors = []
        for i in range(doors_count):
            if i == safe_idx:
                if round_num == self.jackpot_round and random.random() < 0.07:
                    doors.append(Door(self.jackpot_mult, True, True))
                else:
                    doors.append(Door(safe, True))
            else:
                # Bait monsters
                if current_mult > 15 and random.random() < 0.78 and mode != "feed":
                    bait = round(random.choice([8, 12, 19, 28, 44, 77, 99, 150]) * random.uniform(0.9, 1.25), 2)
                else:
                    bait = round(random.uniform(1.15, 5.5), 2)
                doors.append(Door(bait, False))

        random.shuffle(doors)
        return doors

# ================================================
# LIVE INTERACTIVE GAME – PLAY NOW!
# ================================================

print("DOORS OF GREED – LIVE TEST")
print("Warning: This game is designed to make you lose slowly and beautifully\n")

bet = float(input("Enter your bet amount (e.g. 100): "))
if bet <= 0:
    bet = 100

engine = DoorsGameEngine()
client_seed = input("Enter any text as client seed (or press Enter for random): ").strip()
if not client_seed:
    client_seed = "player_" + str(int(time.time()))
server_seed = hashlib.sha256(f"secret_server_{time.time()}".encode()).hexdigest()

print(f"\nClient seed: {client_seed}")
print(f"Server seed: HIDDEN (will reveal at end for provably fair)\n")

current_pot = bet
round_num = 1

while True:
    doors = engine.generate_round(client_seed, server_seed, round_num, current_pot, bet)

    print(f"\nROUND {round_num} | Current pot: {current_pot:.2f} TND")
    print("Doors:")
    for i, door in enumerate(doors):
        star = "JACKPOT" if door.is_jackpot else ""
        print(f"  [{i+1}] → {door.multiplier:.2f}x {star}")

    print(f"\n[1–{len(doors)}] Choose door | [0] Cashout → {current_pot:.2f} TND")

    choice = input("\nYour choice (0 to cashout): ").strip()

    if choice == "0":
        print(f"\nCASHED OUT! You walk away with {current_pot:.2f} TND")
        engine.stats["wagered"] += bet
        engine.stats["paid"] += current_pot
        engine.stats["games"] += 1
        break

    if not choice.isdigit() or int(choice) not in range(1, len(doors)+1):
        print("Invalid choice!")
        continue

    picked_idx = int(choice) - 1
    picked = doors[picked_idx]

    if picked.is_safe:
        old = current_pot
        if picked.is_jackpot:
            current_pot = bet * engine.jackpot_mult
            print(f"\nJACKPOT!!! YOU WON {current_pot:.2f} TND!!!")
        else:
            current_pot *= picked.multiplier
            print(f"\nSAFE! {old:.0f} × {picked.multiplier:.2f} → {current_pot:.2f} TND")
        round_num += 1
    else:
        print(f"\nMONSTER!!! You lose everything!")
        current_pot = 0
        engine.stats["wagered"] += bet
        engine.stats["games"] += 1
        break

    if round_num > 20:
        print("You survived too long… forcing cashout!")
        break

# Reveal server seed at the end
print(f"\nProvably Fair – Server seed was: {server_seed}")
rtp = engine.stats["paid"] / engine.stats["wagered"] if engine.stats["wagered"] > 0 else 0
print(f"Session RTP so far: {rtp:.1%}")