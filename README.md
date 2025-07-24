# Blood on the Clocktower AI

A Python-based AI and game engine for the social deduction game [Blood on the Clocktower](https://www.bloodontheclocktower.com/), designed to play, simulate, and analyze complex deduction scenarios.

> **Status:** 🚧 Work in progress / testing phase.  
> The codebase is rapidly evolving; some file names and structures are temporary. The main AI logic currently lives in `deduction_engine.py`. Refactoring and clean-up planned for future releases.

## What is this?

This project is an experimental AI designed to:
- Simulate *Blood on the Clocktower* games, including roles, night actions, and voting.
- Model deduction, bluffing, and constraint satisfaction (Bayesian/probabilistic reasoning).
- Serve as a testbed for experimenting with social deduction AI.

## Features (so far)
- Role logic for key BOTC characters (Fortune Teller, Undertaker, Poisoner, etc).
- Probabilistic reasoning and deduction engine.
- Basic game simulation and storyteller AI logic.
- Player nomination/voting and star-passing mechanics.
- Coordinated bluffing system for evil players with public confirmations.

## Limitations & To-Do
- File structure is under heavy development; expect refactoring soon.
- Many scripts are duplicated or experimental; use `deduction_engine.py` for latest logic.
- Minimal user interface—currently used for research, testing, and development only.
- Improved documentation, tests, and a public API are planned.

## How to use

1. Clone the repo:
```
git clone https://github.com/richardpauldev/botc-ai.git
cd botc-ai
```
2. Try out the deduction engine example:
```bash
python deduction_engine.py
```
3. Launch a quick game simulation:
```bash
python game.py
```
*(See in-code comments for configuration options.)*

## Technologies Used

- Python 3
- No external dependencies
- Standard library modules like `dataclasses`, `enum`, `itertools` and `random`

## Why did I build this?

I love social deduction games and wanted to explore the challenges of building an AI capable of simulating and reasoning about player interactions in BOTC. This is both a technical passion project and a playground for AI/game logic experiments.

## License

[MIT License](/LICENSE)

---

**Questions, feedback, or collaboration ideas?** Open an issue or contact me!
