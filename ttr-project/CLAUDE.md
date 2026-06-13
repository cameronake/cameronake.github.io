# TTR Project — Implementation Notes

See the root `CLAUDE.md` for portfolio-wide context.

---

## Project Overview

Live in-browser demo of a Ticket to Ride genetic algorithm. Bots evolve over several generations; visitors watch the improvement. Five tabs: live demo runner, full run results, bot vs. Vanderbot Jr. comparison, how-to-play primer, limitations & future work.

Demo page: `ttr-demo.html` (portfolio root)

---

## Bot Representation

- In Python: `HeuristicPlayer` class instances (also a `RandomPlayer` class, not used in GA)
- In `.txt` files: one bot per line — **24 weights**, plus **score**, **longest_route** (bool), and **tickets_achieved** (bool)
- Most recent 4-bot population: `Code/05-11-greedy-4/` (200 stages + FINAL)
- File line format: `[w1, w2, ..., w24]\tscore\tlongest_route\ttickets`
  - `longest_route`: `True` / `False` — always `True` for at least one bot per game
  - `tickets`: `('City A', 'City B'):True/False;('City C', 'City D'):True/False` — variable length
- `Code/05-11-greedy-4/05-11-bot-test-stage_FINAL.txt` is the most evolved 4-bot population
- Child bots produced by breeding have no performance data until evaluated (`longestRoute: null, tickets: null`)
- `bot.avgEval`: set to `true` by `evalPopulation` when `nEvalRounds > 1`; reset to `false` at start of each eval phase. When true, UI suppresses per-game breakdown and shows a note instead.

---

## Technical Approach: Pyodide

**Pyodide** runs Python in the browser via WebAssembly — no backend needed, enabling static GitHub Pages hosting.

The demo uses a **scaled-down "mini-run"** (6–10 bots, 1–3 games/bot, 5–10 generations) to stay within browser timing limits.

### Pyodide Integration Pattern

```html
<script src="https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js"></script>
<script>
  async function main() {
    const pyodide = await loadPyodide();
    const code = await fetch("ttr-project/Code/your_file.py").then(r => r.text());
    await pyodide.runPythonAsync(code);
    const result = pyodide.globals.get("your_function")(arg1, arg2);
  }
  main();
</script>
```

Key constraints:
- TTR code uses only stdlib (`random`, `copy`, `queue`, `heapq`, `collections.deque`, `collections.defaultdict`) — no `micropip` needed.
- File I/O (`open(...)`) doesn't work directly — must fetch files in JS and write to Pyodide VFS.
- Long-running Python blocks the UI thread — use `runPythonAsync` and run Pyodide in a Web Worker.

### Python API (TTR.py)

- `cycle_bots(weights_scores_list, output_file_base_name, start=0, N_repetitions=11, selection_mode="linear", elite_pct=0.0, n_rounds=1, lr=None, lr_decay=1.0)` — full GA loop
- `collection_of_games_averaged(weights_list, n_rounds=3)` — multi-round eval; returns `[[weights, avg_score, last_longest, last_tickets], ...]`
- `breed_cycle(weights_scores_list, selection_mode="linear", elite_pct=0.0, lr=None)` — one breeding step; returns `[(weights, is_child), ...]`
  - `selection_mode`: `"linear"` or `"quadratic"` (weight by score²)
  - `elite_pct`: fraction 0.0–1.0 of top bots guaranteed to survive
- `breed(bot1, bot2, lr=None)` — crossover + mutate two weight vectors
- `initialize_decks()` — must be called before constructing bots; returns `c_deck, t_deck, face_ups, discard`
- `HeuristicPlayer` — bot class

`HeuristicPlayer.__init__(self, playercolor, c_deck, t_deck, colors, CITIES, USER_INPUT_CARDS, PRINT_THINGS, weights)`:
- `USER_INPUT_CARDS`, `PRINT_THINGS`: always `False` for automated play
- `weights`: 24-element list

Full game setup sequence:
```python
c_deck, t_deck, face_ups, discard = initialize_decks()
board = initialize_connections_cities_board()  # index 2 = board, index 1 = CITIES
colors = NUMCOLORS.keys()
```

`bots_play_game(bots, c_deck, face_ups, t_deck, board, discard)`:
- Returns `[[weights, score, has_longest, tickets_satisfied], ...]` ordered by finish position (winner first)
- `tickets_satisfied`: dict with tuple keys `{('City A', 'City B'): True/False, ...}`

**Pyodide VFS note:** TTR.py reads `"txt_storage/newconnectionroutes.txt"` at import time. Fetch and write to `/txt_storage/newconnectionroutes.txt` before importing, with cwd set to `/`.

### Web Worker Architecture

Must run Pyodide in a Web Worker to avoid blocking the UI. Worker file: `ttr-worker.js`.

Worker message types:
- `run_game` → `game_result` / `game_error` (non-fatal)
- `run_breed_cycle` → `breed_result` / `breed_error` (non-fatal); payload `{weightsScores, selectionMode, elitePct, learningRate}`; returns `[{weights, isChild}, ...]`
- Init errors → `type: 'error'` (fatal — marks engine unavailable)

### Pyodide Worker — Implementation Notes

- TTR.py must be written to `/TTR.py` in the VFS and imported as a module (`from TTR import *`) — direct `runPythonAsync` execution triggers the top-level `cycle_bots()` call.
- `/` must be added to `sys.path`: `import os, sys; os.chdir("/"); sys.path.insert(0, "/")`.
- HeuristicPlayer.py and RandomPlayer.py must also be written to `/`.
- Before each generation's eval, survivor bots' `longestRoute` and `tickets` are reset to `null` to prevent stale data from leaking.
- Survivor weights returned by `run_breed_cycle` are exact float matches to input; `weightsMatch` finds them in the previous population to copy ID/score/performance data.
- **Stable eval mode**: `eval-mode` select (value `"1"` or `"3"`) controls `nEvalRounds`. In stable mode, `makeGameGroups(pop)` reshuffles groupings each round; scores accumulated in `scoreAccum[id]` and averaged at end. `updatedIds` Set prevents double-attribution from padding bots.

---

## Page Structure (Five Tabs)

### 1. Live Demo (`tab-demo`)

Controls: bot count (4–40), breeding cycles (1–10), LR slider (0.05–1.0), LR decay (0.70–1.0, default 1.0), selection mode (linear/quadratic), elite % (0–50%), eval mode (1 game / 3 games averaged).

Results: score distribution chart (avg + IQR band + 5-stage rolling trend), generation nav, per-generation stats, bot grid + detail panel.

Bot cards: score, longest-route badge, per-ticket pills, weight bars; click to expand detail. Stable mode shows "3-game avg score" label.

Bot IDs: persistent integers (gen0 gets 1–N, children N+1 onward); color + label derived from `bot.id`.

### 2. Full Run Results (`tab-fullrun`)

Dataset selector at top; switching calls `switchDataset(key)` to update summary stats, charts, and final population in-place.

Five datasets:
- `'greedy4'` — 4 bots, quadratic², 1 game/cycle, LR 0.5 decay 0.98, 200 stages (default; no `avgScores`)
- `'greedy40'` — 40 bots, quadratic², 3-game avg, LR 0.5 decay 0.98, 200 stages (`avgScores: true`)
- `'linear40'` — 40 bots, linear, 1 game/cycle, LR 0.25 no decay, 50 stages
- `'quad40'` — 40 bots, quadratic², 1 game/cycle, LR 0.25 no decay, 50 stages
- `'elite40'` — 40 bots, quadratic², 3-game avg, LR 0.5 decay 0.99, 5% elite, 200 stages (`avgScores: true`)

Summary stats (hardcoded in JS):
- greedy4: 61.0 → 49.0, peak 165 (stage 15), tickets 55.6% → 27.3%
- greedy40: 51.9 → 93.5, peak 128 (stage 2), tickets 45.8% → 71.1%
- linear40: 54.1 → 69.8, peak 136 (stage 48), tickets 40.7% → 41.3%
- quad40: 46.1 → 76.9, peak 150 (stage 18), tickets 38.7% → 56.5%
- elite40: 54.3 → 83.4, peak 127 (stage 90), tickets 38.8% → 77.4%

Data loaded via `<script src="data/<key>.js">` tags; globals like `DATA_GREEDY4` contain `{evolution, final, stage0}`. Format per evolution entry: `{stage, avg, best, worst, ticketPct, q1, median, q3}`.

Chart: score distribution (avg line + IQR Q1–Q3 band + 5-stage rolling trend). Lazy-initialized on first tab open. Dependency: Chart.js v4.

Head-to-head comparison sub-section: pits stage-0 bots vs. final bots in live Pyodide-backed games. Each game uses 2 stage-0 + 2 final bots. Controls: games-to-run slider (1–10, default 5). Results: avg score cards + per-game results. `switchDataset` clears stale comparison results.

### 3. Bot Comparison (`tab-compare`)

Compares elite40 bot vs. Vanderbot Jr. (Days of Wonder's AI). Stats hardcoded in HTML. Chart from `data/compare.js` (`DATA_COMPARE.bins/elite40/dow`). Lazy-initialized grouped bar histogram.

### 4. How to Play (`tab-howtoplay`)

Static educational content: game overview, turn structure, scoring table (1–6 cars → 1/2/4/7/10/15 pts), strategy tips, bot architecture explanation.

### 5. Limitations & Future Work (`tab-limitations`)

Static. Contact: cameron.m.ake@gmail.com. Limitations include: high variance per game, no minimax, no Bayesian opponent modeling, WebAssembly overhead in demo. Future work: bot playback, more stable fitness evaluation.

---

## Data Files (`data/`)

| File | Global | Contents |
|------|--------|----------|
| `greedy4.js` | `DATA_GREEDY4` | `{evolution, final, stage0}` |
| `greedy40.js` | `DATA_GREEDY40` | `{evolution, final, stage0}` |
| `linear40.js` | `DATA_LINEAR40` | `{evolution, final, stage0}` |
| `quad40.js` | `DATA_QUAD40` | `{evolution, final, stage0}` |
| `elite40.js` | `DATA_ELITE40` | `{evolution, final, stage0}` |
| `compare.js` | `DATA_COMPARE` | `{bins, elite40, dow}` |

---

## Fixed Bugs (for reference)

- **`possible_moves()` empty-list bug** — `"tickets"` gated on `len(t_deck) >= 3`; early-return guards added for both draw branches when `possible_moves` is empty.
- **Weight clamping mismatch** — both JS and Python `breed()` now clamp each weight to `[weight_initial_mins[i], weight_initial_maxes[i]]`.
- **Infinite/very long games** — card duplication in `clean_face_ups` fixed; `MAX_TURNS = 500` added; draw-phase guards added.
- **Stale opponent awareness** — `bots_play_game` now passes `players=order` (live list) instead of a frozen snapshot.
- **`MemoryError` in `total_cards_away_from_tickets`** — both passes made greedy (constant-size hypothetical_hands list instead of exponential branching).
