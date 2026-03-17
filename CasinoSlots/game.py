#!/usr/bin/env python3
"""Groovey Casino Slots - PortMaster-ready local slot machine game.

Designed for handheld Linux devices (including R36S) that can run Python + pygame.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
THEME_DIR = ROOT / "assets" / "themes"

WIDTH, HEIGHT = 960, 540
FPS = 60


@dataclass
class GameMode:
    name: str
    description: str
    starting_credits: int
    min_bet: int
    max_bet: int
    jackpot_multiplier: int


class SlotMachine:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Groovey Casino Slots")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans", 24)
        self.big_font = pygame.font.SysFont("dejavusans", 44, bold=True)

        self.config = self._load_json(DATA_DIR / "config.json")
        self.games = self.config["slot_games"]
        self.modes = [GameMode(**m) for m in self.config["game_modes"]]

        self.game_idx = 0
        self.mode_idx = 0
        self.theme = self._load_theme(self.games[self.game_idx]["theme"])

        self.credits = self.modes[self.mode_idx].starting_credits
        self.bet = self.modes[self.mode_idx].min_bet
        self.last_win = 0
        self.message = "Press SPACE to spin"

        self.reels = [
            random.choice(self.games[self.game_idx]["symbols"]),
            random.choice(self.games[self.game_idx]["symbols"]),
            random.choice(self.games[self.game_idx]["symbols"]),
        ]

    @staticmethod
    def _load_json(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_theme(self, theme_name: str) -> dict:
        return self._load_json(THEME_DIR / f"{theme_name}.json")

    def _reset_for_mode(self) -> None:
        mode = self.modes[self.mode_idx]
        self.credits = mode.starting_credits
        self.bet = mode.min_bet
        self.message = f"Mode switched to {mode.name}"

    def _switch_game(self, delta: int) -> None:
        self.game_idx = (self.game_idx + delta) % len(self.games)
        game = self.games[self.game_idx]
        self.theme = self._load_theme(game["theme"])
        self.reels = [random.choice(game["symbols"]) for _ in range(3)]
        self.message = f"Selected {game['name']}"

    def _switch_mode(self, delta: int) -> None:
        self.mode_idx = (self.mode_idx + delta) % len(self.modes)
        self._reset_for_mode()

    def _adjust_bet(self, delta: int) -> None:
        mode = self.modes[self.mode_idx]
        self.bet = max(mode.min_bet, min(mode.max_bet, self.bet + delta))

    def _spin(self) -> None:
        mode = self.modes[self.mode_idx]
        game = self.games[self.game_idx]

        if self.credits < self.bet:
            self.message = "Not enough credits. Press R to reset mode credits."
            return

        self.credits -= self.bet
        self.reels = [random.choice(game["symbols"]) for _ in range(3)]
        counts = {s: self.reels.count(s) for s in set(self.reels)}

        payout_multiplier = 0
        if 3 in counts.values():
            symbol = next(sym for sym, c in counts.items() if c == 3)
            payout_multiplier = game["payouts"].get(symbol, mode.jackpot_multiplier)
            self.message = f"JACKPOT! 3x {symbol}"
        elif 2 in counts.values():
            symbol = next(sym for sym, c in counts.items() if c == 2)
            payout_multiplier = max(1, game["payouts"].get(symbol, 2) // 2)
            self.message = f"Nice! Pair of {symbol}"
        else:
            self.message = "No win. Spin again!"

        self.last_win = self.bet * payout_multiplier
        self.credits += self.last_win

    def _draw_panel(self) -> None:
        t = self.theme
        self.screen.fill(tuple(t["background"]))

        title = self.big_font.render(self.games[self.game_idx]["name"], True, tuple(t["title_color"]))
        self.screen.blit(title, (30, 20))

        mode_text = self.font.render(f"Mode: {self.modes[self.mode_idx].name}", True, tuple(t["text_color"]))
        credit_text = self.font.render(f"Credits: {self.credits}", True, tuple(t["text_color"]))
        bet_text = self.font.render(f"Bet: {self.bet}", True, tuple(t["text_color"]))
        win_text = self.font.render(f"Last Win: {self.last_win}", True, tuple(t["text_color"]))
        self.screen.blit(mode_text, (30, 80))
        self.screen.blit(credit_text, (30, 110))
        self.screen.blit(bet_text, (30, 140))
        self.screen.blit(win_text, (30, 170))

        reel_rect = pygame.Rect(260, 130, 440, 220)
        pygame.draw.rect(self.screen, tuple(t["reel_bg"]), reel_rect, border_radius=14)
        pygame.draw.rect(self.screen, tuple(t["accent"]), reel_rect, 4, border_radius=14)

        for i, symbol in enumerate(self.reels):
            cell = pygame.Rect(280 + i * 140, 160, 120, 160)
            pygame.draw.rect(self.screen, tuple(t["cell_bg"]), cell, border_radius=10)
            pygame.draw.rect(self.screen, tuple(t["accent"]), cell, 2, border_radius=10)
            s_text = self.big_font.render(symbol, True, tuple(t["text_color"]))
            s_pos = s_text.get_rect(center=cell.center)
            self.screen.blit(s_text, s_pos)

        message = self.font.render(self.message, True, tuple(t["message_color"]))
        self.screen.blit(message, (30, HEIGHT - 95))

        controls = [
            "SPACE: Spin",
            "A/D: Change game",
            "W/S: Change mode",
            "LEFT/RIGHT: Bet -/+",
            "R: Reset mode credits",
            "ESC: Quit",
        ]
        for i, text in enumerate(controls):
            c_text = self.font.render(text, True, tuple(t["text_color"]))
            self.screen.blit(c_text, (30, HEIGHT - 65 + i * 22))

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_SPACE:
                        self._spin()
                    elif event.key == pygame.K_a:
                        self._switch_game(-1)
                    elif event.key == pygame.K_d:
                        self._switch_game(1)
                    elif event.key == pygame.K_w:
                        self._switch_mode(-1)
                    elif event.key == pygame.K_s:
                        self._switch_mode(1)
                    elif event.key == pygame.K_LEFT:
                        self._adjust_bet(-1)
                    elif event.key == pygame.K_RIGHT:
                        self._adjust_bet(1)
                    elif event.key == pygame.K_r:
                        self._reset_for_mode()

            self._draw_panel()
            pygame.display.flip()
            self.clock.tick(FPS)


def main() -> int:
    try:
        SlotMachine().run()
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
