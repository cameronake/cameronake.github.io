# TICKETPLAN — New Heuristic Weights

## Goal

Add **7 new heuristic weights** and one endgame behavioral override to `HeuristicPlayer`,
addressing two existing limitations:

1. **Ticket selection**: Bots currently keep tickets randomly (2 at start, 1 mid-game) with
   no heuristic input. The bot will evaluate all legal subsets of the 3 offered tickets using
   purpose-built formulas and keep the highest-scoring one.
2. **Endgame awareness**: Bots have no signal that the game is ending. On the final turn,
   `best_move()` will override normal heuristic evaluation and force the bot to only play
   trains, scoring each play by its direct point benefit.

---

## Files to Change

| File | Change |
|---|---|
| `HeuristicPlayer.py` | 2 new helper functions; update `give_starting_tickets`, `new_tickets`, `best_move`; update weight docstring |
| `TTR.py` | Extend `weight_initial_mins/maxes/ranges/averages`; update `new_weights` (17 → 24 entries); `breed` and `breed_cycle` require no logic changes |
| `ttr-demo.html` | Update JS `breed()` mins/maxes arrays (24 entries); weight bar UI; bot detail panel; `STAGE_FINAL_*` data (see Q5/Q6 below) |
| `ttr-worker.js` | No logic changes expected; new weights pass through automatically |
| `CLAUDE.md` | Update bot-representation weight count (17 → 24) |

---

## New Weight Layout (indices 17–23)

Total weight count: **17 → 24**.

The 7 new weights fall into two groups: ticket-selection (start formula), ticket-selection
(midgame formula). No weights are added to `move_quality` — endgame awareness is achieved
via the `best_move` override instead.

| Index | User label | Descriptive name | Used in | Range |
|---|---|---|---|---|
| 17 | W1 | `start_length_risk` | Start formula | [1, 1.6] |
| 18 | W2 | `start_overrun_penalty` | Start formula | [0, 2] |
| 19 | —  | `start_overrun_threshold` | Start formula | [26, 38] |
| 20 | W3 | `mid_length_risk` | Midgame formula | [0.5, 2] |
| 21 | W4 | `mid_card_base` | Midgame formula | [0.5, 3] |
| 22 | W5 | `mid_card_urgency` | Midgame formula | [4, 30] |
| 23 | W6 | `mid_card_refuse` | Midgame override | [0.3, 1] |

---

## Part 1 — Ticket Selection

### New helper: `total_trains_needed_for_tickets(self, tickets, board)`

Returns `(cost, route_list)` — the minimum total train-car cost and the corresponding
route list for a network that satisfies all tickets simultaneously, counting already-claimed
routes as free (cost 0).

**Algorithm: Dreyfus–Wagner Steiner tree DP**

1. Collect terminal cities: deduplicate the union of both endpoints of every ticket in
   `tickets` (at most 6 terminals for 3 tickets).
2. Build a modified adjacency structure where `self.player_color in board[route][1]` → weight 0,
   otherwise → `board[route][0]` (route length).
3. Precompute all-pairs shortest paths from each city to every other city using one
   Dijkstra run per source city on the modified graph. Store `dist[u][v]` and `prev[u][v]`
   (predecessor for path reconstruction).
4. Run Dreyfus–Wagner DP over subsets of terminals:
   - `dp[S][v]` = min cost to build a Steiner tree spanning all terminals in subset `S`
     with `v` as a node in the tree.
   - Base: `dp[{t}][v] = dist[v][t]` for each terminal `t` and every city `v`.
   - Subset merge (over all proper non-empty sub-partitions of S containing v):
     `dp[S][v] = min over S1 ⊂ S, v ∈ S1: dp[S1][v] + dp[S \ S1][v]`
   - Edge relaxation: for each fixed subset S, run Dijkstra over the values
     `dp[S][·]` to propagate lower costs through non-terminal nodes.
   - Backpointers are stored alongside DP values so the actual route list can be
     reconstructed.
5. Answer: `min over all cities v: dp[all_terminals][v]`, plus the reconstructed route list.
6. With k ≤ 6 terminals and n ≈ 36 cities: 3^6 × 36 ≈ 26k operations — trivially fast.
7. **Signature change**: `give_starting_tickets` and `new_tickets` will receive `board` as
   a new parameter (propagated from their callers in TTR.py / ttr-worker.js).

---

### New helper: `total_cards_away_from_tickets(self, route_list, board)`

Returns the minimum number of additional train cards needed beyond `self.cards` to legally
claim every route in `route_list` (the Steiner tree route list from the helper above).
Follows the same structure as `cards_away_from_ticket`:

- Iterate through `route_list`, branching hypothetical hands for gray/multi-color routes.
- Return `total_cars_in_route_list − (original_hand_size − best_remaining_hand_size)`.

Takes `route_list` (already computed) rather than re-running the Steiner tree.

---

### Start-of-game formula (`give_starting_tickets`)

The bot evaluates all **4 legal subsets** of the 3 offered tickets (must keep ≥ 2: the
three pairs + the full triple). No override rules apply at game start. No `total_cards_away`
call — cards are essentially irrelevant at game start.

```
quality(subset) = total_point_value(subset)
               - W1 * total_trains_needed(subset)
               - W2 * max(0, total_trains_needed(subset) − W3_threshold)
```

- **`total_point_value`**: sum of the point rewards of all tickets in the subset.
- **W1** (`start_length_risk`): penalizes collections requiring many train cars (risk tolerance).
- **W2** (`start_overrun_penalty`): extra penalty per car above the threshold — captures
  heightened risk of collections that eat nearly the whole game.
- **W3_threshold** (`start_overrun_threshold`, index 19): the evolved threshold (~26–38)
  above which the W2 penalty kicks in.

The bot takes the subset with the highest `quality`, pops only those tickets from `t_deck`,
and leaves the rest in the deck.

---

### Midgame formula (`new_tickets`)

The bot evaluates all **7 non-empty subsets** of the 3 offered tickets. Two override rules
can disqualify a subset before scoring. If ALL subsets are disqualified, a fallback fires.

**Max cars played** is computed from `board` by summing claimed route lengths per player
color — no `players` parameter needed.

```python
cars_played = {}
for route, (length, cols) in board.items():
    for col in cols:
        if col == col.upper() and col != 'WILD':  # player color
            cars_played[col] = cars_played.get(col, 0) + length
max_cars_played = max(cars_played.values(), default=0)
```

**Override 1 — route feasibility**: disqualify a subset if
`total_trains_needed(subset) > self.num_trains`
(the bot literally doesn't have enough trains left to complete the network).

**Override 2 — card feasibility**: disqualify a subset if
`total_cards_away(subset) > W6 * (43 − max_cars_played)`
(too many cards still needed given how close the game is to ending; 43 is hardcoded as the
last-turn trigger).

**Scoring** (applied only to non-disqualified subsets):
```
quality(subset) = total_point_value(subset)
               - W3 * total_trains_needed(subset)
               - total_cards_away(subset) * (W4 + W5 / max(1, 43 − max_cars_played))
```

- **W3** (`mid_length_risk`): penalty per train car required, separate from W1 so the bot
  can evolve different risk tolerances for start vs midgame.
- **W4** (`mid_card_base`): baseline penalty per additional card needed.
- **W5** (`mid_card_urgency`): scales up the card penalty as the game nears its end
  (divides by remaining turns-worth of trains, amplifying urgency).
- **W6** (`mid_card_refuse`): controls how conservatively the bot refuses subsets via
  override 2.

**Fallback**: if every subset is disqualified by the override rules, the bot takes the
single ticket with the **lowest point value** (minimising penalty points if it cannot
complete any ticket).

The bot pops only the kept tickets from `t_deck`; the rest remain in the deck.

---

## Part 2 — Endgame `best_move` Override

### Detection

Inside `best_move(self, possible_moves, board, players)`, before any heuristic computation:

```python
is_endgame = any(p.num_trains <= 2 for p in players)
```

This fires True only during the final for-loop in `bots_play_game` (since the while loop
exits as soon as any bot hits ≤ 2 trains, so no bot can have ≤ 2 trains while the while
loop is still running).

### Override behaviour

If `is_endgame` is True:
1. Filter `possible_moves` to only `"play-*"` entries.
2. If no play moves remain, fall back to normal heuristic scoring across all original
   `possible_moves` (edge case: bot truly can't play any route on its last turn).
3. For each remaining play move, compute score as:
   ```
   score = points_gained_from_playing(route, board)
         + ticket_point_change(route, board)
         + longest_route_change(board, route, players, other_max_lr)
   ```
   (No weights involved — direct point benefit only.)
4. Return the play move with the highest score.

`other_max_lr` and `my_lr` are still precomputed at the top of `best_move` and reused
here, so `_lr_change_and_diff` can be used instead of the more expensive
`longest_route_change` call for efficiency.

---

## Implementation Order (suggested)

1. Add helper stubs (`total_trains_needed_for_tickets`, `total_cards_away_from_tickets`)
   and verify Steiner tree correctness on simple examples.
2. Update `give_starting_tickets` with start formula.
3. Update `new_tickets` with midgame formula + overrides + fallback.
4. Update `best_move` with endgame override.
5. Extend weight arrays in `TTR.py` (+ update weight docstring in `HeuristicPlayer.py`).
6. Update JS in `ttr-demo.html`.

---

## Decisions Made

- **Weight ranges**: All resolved — see table above.
- **Backward compatibility**: Old `.txt` files (17 weights) become archive-only. The new
  code will not attempt to load them. All new GA runs use 24-weight bots.
- **Demo page `STAGE_FINAL_*` data**: Will be regenerated via a new GA run after
  implementation is complete. In the interim, the existing 17-weight hardcoded arrays
  remain in `ttr-demo.html` but will be replaced. No UI note needed since the regeneration
  will happen before the page is published.

---

## Complete `weight_initial_mins` / `weight_initial_maxes` (24 entries)

Existing 17 entries are unchanged. New entries appended at indices 17–23:

```python
weight_initial_mins  = [0, 0, 0, 0, 0, 0, 0, 0, 10, 44, 0, 0, -2, -.6, -.6, -.6, -1,
                         1,   0,   26,  0.5, 0.5,  4,  0.3]
weight_initial_maxes = [5, .15, .15, 2, 2, 1, 4, .5, 36, 58, 1, 1, 1, .6, .8, .8, .2,
                         1.6, 2,   38,  2,   3,   30, 1  ]
```
