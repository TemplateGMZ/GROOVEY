# Groovey Casino Slots (PortMaster / R36S)

A **local, offline casino-style slot machine game** designed for handheld Linux devices such as the **R36S** through PortMaster-style launching.

## Features

- Multiple selectable slot games:
  - Royal Gold Slots
  - Neon Vegas Slots
  - Emerald Fortune
- Multiple game modes:
  - Casual
  - High Roller
  - Survival
- Credit system with variable betting and payouts.
- JSON-driven themes and balance values.
- HD editable vector assets (`.svg`) for casino and slot icons.

## Controls

- `SPACE` spin reels
- `A / D` previous/next slot game
- `W / S` previous/next game mode
- `LEFT / RIGHT` lower/raise bet
- `R` reset current mode credits
- `ESC` quit

## PortMaster-style launch

1. Copy the `CasinoSlots/` folder to your device's ports directory.
2. Ensure Python 3 and pygame are available.
3. Launch `CasinoSlots.sh` from your launcher or shell.

## Editability

- Slot/game definitions: `CasinoSlots/data/config.json`
- Theme colors: `CasinoSlots/assets/themes/*.json`
- HD icons and slot symbols: `CasinoSlots/assets/icons/*.svg`, `CasinoSlots/assets/slots/*.svg`

## Notes

- This is a simulated slot game for entertainment.
- No real-money wagering or online gambling integration is included.
