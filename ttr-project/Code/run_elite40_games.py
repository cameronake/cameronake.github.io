import os
import sys
import ast

from TTR import initialize_decks, initialize_connections_cities_board, bots_play_game, NUMCOLORS
from HeuristicPlayer import HeuristicPlayer

N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 30
FINAL_FILE = "05-12-elite-40/05-12-bot-test-stage_FINAL.txt"
OUT_DIR = "elite40-bot-results"
OUT_FILE = os.path.join(OUT_DIR, f"elite40-bot-results-{N_GAMES}.tsv")
COLORS = ["RED", "YELLOW", "GREEN", "BLUE"]

def load_best_bot(path):
    best_score, best_weights = -1, None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            weights = ast.literal_eval(parts[0])
            score = int(parts[1])
            if score > best_score:
                best_score, best_weights = score, weights
    return best_weights

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    best_weights = load_best_bot(FINAL_FILE)
    print(f"Best bot weights loaded (top score from FINAL).")

    rows = []
    for game_num in range(1, N_GAMES + 1):
        c_deck, t_deck, face_ups, discard = initialize_decks()
        _, CITIES, board = initialize_connections_cities_board()
        bots = [
            HeuristicPlayer(
                playercolor=color,
                c_deck=c_deck,
                t_deck=t_deck,
                colors=NUMCOLORS.keys(),
                CITIES=CITIES,
                USER_INPUT_CARDS=False,
                PRINT_THINGS=False,
                weights=best_weights,
            )
            for color in COLORS
        ]
        result = bots_play_game(bots=bots, c_deck=c_deck, face_ups=face_ups,
                                t_deck=t_deck, board=board, discard=discard)
        scores = sorted([r[1] for r in result], reverse=True)
        rows.append(scores)
        print(f"Game {game_num}/{N_GAMES}: {scores}")

    with open(OUT_FILE, "w") as f:
        for row in rows:
            f.write("\t".join(str(s) for s in row) + "\n")

    print(f"\nWrote {N_GAMES} games to {OUT_FILE}")

if __name__ == "__main__":
    main()
