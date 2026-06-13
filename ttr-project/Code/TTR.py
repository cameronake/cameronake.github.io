import random
import copy
import queue

from RandomPlayer import RandomPlayer
from HeuristicPlayer import HeuristicPlayer



# Various things necessary to initialize and create for the games to work.

NUMCOLORS = {
    "blue": 12,
    "yellow": 12,
    "orange": 12,
    "black": 12,
    "red": 12,
    "green": 12,
    "pink": 12,
    "white": 12,
    "WILD": 14
}
TICKETS = {tuple(ticket.split("\t")[:2]): int(ticket.split("\t")[2]) for ticket in open("txt_storage/routes.txt")}

USER_INPUT_CARDS = False
PRINT_THINGS = False
SHUFFLE_ORDER = False

def initialize_decks():
    card_deck = []
    for col, num in NUMCOLORS.items():
        card_deck = card_deck + [col]*num
    random.shuffle(card_deck)

    face_up_cards = []
    
    if USER_INPUT_CARDS:
        for _ in range(5):
            col = input("Please input face-up card: ")
            if "none" in col.strip().lower():
                print("No card was added. Moving on")
                break
            if col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO': 
                face_up_cards.append('WILD')
            else:
                # if card is not locomotive
                col = col.strip().lower()
                if col not in NUMCOLORS:
                    raise ValueError(col, "is not a valid color")
                else:
                    face_up_cards.append(col)
    else:
        face_up_cards = card_deck[:5]
        card_deck = card_deck[5:]

    ticket_deck = copy.deepcopy(TICKETS)
    return card_deck, ticket_deck, face_up_cards, []

_CONNECTIONS_CACHE = None
_CITIES_CACHE = None

def initialize_connections_cities_board():
    global _CONNECTIONS_CACHE, _CITIES_CACHE
    if _CONNECTIONS_CACHE is not None:
        return copy.deepcopy(_CONNECTIONS_CACHE), _CITIES_CACHE, copy.deepcopy(_CONNECTIONS_CACHE)

    connections = {}

    for conn in open("txt_storage/newconnectionroutes.txt"):
        conn = conn.strip()
        list_cits = conn.split("\t")[:2]
        cits = tuple(sorted(list_cits))
        if cits not in connections:
            l = conn.split("\t")[2]
            c = conn.split("\t")[3]
            connections[cits] = tuple((int(l), [c]))
        else:
            # add color to already-existing connection
            c = conn.split("\t")[3]

            # whoever made this source txt file just straight-up originally failed to account for gray double routes, because of course they did.
            # all routes are also listed both ways, for some reason
            # i fixed the gray-double-routes thing, i'm 99% sure, but beware of that
            connections[cits][1].append(c)

    for connec, tup in connections.items():
        cols = tup[1]
        cd = {col: cols.count(col) for col in cols}
        for c in cd: # loop over each color, throw error if there's an odd number of any color
            if cd[c] % 2 != 0:
                raise ValueError("Odd number of instances of a color when it should have been looped over; check the file at connection", connec)
            cd[c] = cd[c] // 2
        newcols = []
        for col, num in cd.items(): # make new list of colors with number of each color halved
            newcols = newcols + [col]*num
        connections[connec] = tuple((tup[0], newcols))

    cities = set()
    for tup in connections:
        for cit in tup:
            cities.add(cit)

    _CONNECTIONS_CACHE = connections
    _CITIES_CACHE = cities
    return copy.deepcopy(connections), cities, copy.deepcopy(connections)



# More meta stuff. How the bots will be made!

# mins and maxes that weights will be randomly initialized between
weight_initial_mins  = [0, 0, 0, 0, 0, 0, 0, 0, 10, 44, 0, 0, -2, -.6, -.6, -.6, -1,
                        1,   0,   26,  0.5, 0.5,  4,  0.3]
weight_initial_maxes = [5, .15, .15, 2, 2, 1, 4, .5, 36, 58, 1, 1, 1, .6, .8, .8, .2,
                        1.6, 2,   38,  2,   3,   30, 1  ]
weight_ranges = [ma - mi for ma, mi in zip(weight_initial_maxes, weight_initial_mins)]
weight_averages = [(ma + mi) / 2 for ma, mi in zip(weight_initial_maxes, weight_initial_mins)]

# callable lambda function with new_weights() whenever we want new weights
new_weights = lambda: tuple(((random.random() - .5) * rang) + aver for rang, aver in zip(weight_ranges, weight_averages))

# number of bots that it will use each repetition
N_bots = 40
N_rounds = 3

# number of repetitions (and index at which to start, getting bots from files)
N_repetitions = 200
start = 0

# list of all the weights combinations that will be used in this session of games
starting_weights = []
for _ in range(N_bots):
    starting_weights.append(new_weights())


def is_last_turn(bots):
    for bot in bots:
        if bot.num_trains <= 2:
            return True
    return False

# bots is a list of bots
def bots_play_game(bots, c_deck, face_ups, t_deck, board, discard):
    print("Beginning game\n")
    order = copy.deepcopy(bots) #DON'T reference bots - bots is only the bots as they ORIGINALLY were
    if SHUFFLE_ORDER: random.shuffle(order)
    s_initial_order = [str(o) for o in order]
    if PRINT_THINGS: print("Turn order:", [str(o) for o in order])
    for bot in order: # first go-around (give starting cards and tickets)
        c_deck = bot.give_starting_cards(c_deck=c_deck)
        t_deck = bot.give_starting_tickets(t_deck=t_deck, board=board)
    MAX_TURNS = 500
    turn_count = 0
    while not is_last_turn(order):
        if turn_count >= MAX_TURNS:
            print(f"WARNING: game exceeded {MAX_TURNS} turns without ending; forcing last turn")
            break
        if PRINT_THINGS: print("It's ", order[0], "'s turn!", sep="")
        c_deck, face_ups, t_deck, board, discard = order[0].take_turn(c_deck=c_deck,
                                                            face_ups=face_ups,
                                                            t_deck=t_deck,
                                                            board=board,
                                                            discard=discard,
                                                            players=order)
        if PRINT_THINGS: print(order[0], "now has hand", order[0].cards)
        order.append(order.pop(0))
        turn_count += 1
        '''
        inp = input("\nPress Enter to continue with the next bot's turn/D for Deck/F for Faceup/N for Numtrains: ") #wait for person to input to continue
        if "D" in inp.strip():
            print(c_deck)
        if "F" in inp.strip():
            print(face_ups)
        if "N" in inp.strip():
            print([bot.num_trains for bot in order])
            '''
    if PRINT_THINGS: print("\n--------------------------------------\nBot",
          order[-1], "has 2 cars or less. It is now the last turn."
          "\n--------------------------------------\n")
    for bot in order: # last turn: dummy loop for friendliness
        if PRINT_THINGS: print("It's ", bot, "'s turn!", sep="")
        c_deck, face_ups, t_deck, board, discard = bot.take_turn(c_deck=c_deck,
                           face_ups=face_ups,
                           t_deck=t_deck,
                           board=board,
                           discard=discard,
                           players=order)
        bot.ticket_points = bot.calc_ticket_points(board=board) # refresh ticket points at end of turn too
    if PRINT_THINGS: print("\n--------------------------------------\nThe game has ended!\n--------------------------------------\n")
    
    # compute each bot's longest route once and reuse across all scoring loops
    bot_lr_cache = {str(bot): bot.find_longest_route(board) for bot in order}
    longest_route_val = max(lr for _, lr in bot_lr_cache.values())

    # get each bot's tickets
    bot_tickets_cache = {str(bot): bot.tickets for bot in order}

    for bot in order: # announce points
        lrl, lr = bot_lr_cache[str(bot)]
        if PRINT_THINGS: print("\n--------------------------------------",
              "\nBot", bot, "got", bot.open_points, "points plus", bot.ticket_points,
              "ticket points\nwith tickets:", bot.tickets)
        for ticket in bot.tickets:
            if PRINT_THINGS: print("\tticket", ticket, ["NOT connected.", "connected!"][bot.has_connection(ticket, board, set())])
        if PRINT_THINGS: print("with longest route", lrl, "\nof length", lr, "\ngetting",
              bot.open_points + bot.ticket_points + [0, 10][lr == longest_route_val], "TOTAL POINTS",
              "\n--------------------------------------\n")

    q = queue.PriorityQueue() # I didn't have to use a priorityQueue but I decided to for practice !!
    for bot in order:
        lrl, lr = bot_lr_cache[str(bot)]
        q.put((-1 * bot.open_points - bot.ticket_points - [0, 10][lr == longest_route_val], -1 * bot.tickets_completed,
               [0, -1][lr == longest_route_val], -1 * s_initial_order.index(str(bot)),
               bot)) # negated so most points are first, second val is alphabetical ordering in case two bots have same score
    
    # [[winner's_weights, winner's_score], [second's_weights, second's_score], ...]
    weights_order = []
    while not q.empty():
        next_bot = q.get()
        bot = next_bot[4]
        has_longest = (next_bot[2] == -1)  # [0,-1][lr==longest_route_val] stored at index 2
        ticket_sat = {ticket: bool(bot.has_connection(ticket, board, set())) for ticket in bot.tickets}
        if len(weights_order) == 0 and PRINT_THINGS:
            print("\n--------------------------------------\nWINNER:",
                str(bot),'\n--------------------------------------\n')
        weights_order.append([bot.weights, max(0, -1 * next_bot[0]), has_longest, ticket_sat])
        print("Bot", bot, "got", -1 * next_bot[0], "points")
        print("\t with tickets", bot_tickets_cache[str(bot)])
        print("\t longest route:", has_longest)
        for ticket, sat in ticket_sat.items():
            print("\t\t", ticket, "satisfied" if sat else "NOT satisfied")
    print()
    return weights_order
    # yay game done!

# outputs weights and points for all bots: runs a round of games based on the weights of the bots that it will be using. does NOT breed
def collection_of_games(weights_list):

    # set up overall variables
    N_games = len(weights_list) // 4
    output_weightspoints = []

    for _ in range(N_games):
    
        # set up game values
        card_deck, ticket_deck, face_up_cards, discard_pile = initialize_decks()
        CONNECTIONS, CITIES, board = initialize_connections_cities_board()

        # set up bots
        RedBot = HeuristicPlayer(playercolor='RED', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                         weights=weights_list.pop(0))
        YellowBot = HeuristicPlayer(playercolor='YELLOW', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                         weights=weights_list.pop(0))
        GreenBot = HeuristicPlayer(playercolor='GREEN', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                         weights=weights_list.pop(0))
        BlueBot = HeuristicPlayer(playercolor='BLUE', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                         weights=weights_list.pop(0))
        game_bots = [YellowBot, GreenBot, RedBot, BlueBot]

        # [[winner's_weights, winner's_score, winner_longest_route, winner_tickets], [second's_weights, second's_score, winner_longest_route, winner_tickets], ...]
        weights_scores = bots_play_game(bots=game_bots,
                                        c_deck=card_deck,
                                        face_ups=face_up_cards,
                                        t_deck=ticket_deck,
                                        board=board,
                                        discard=discard_pile)
        
        output_weightspoints = output_weightspoints + weights_scores

    return output_weightspoints

def collection_of_games_averaged(weights_list, n_rounds=3):
    """
    Evaluates each bot in weights_list over n_rounds rounds with reshuffled groupings each round.
    Scores are averaged across rounds.
    Returns [[weights, avg_score, last_has_longest, last_tickets], ...] preserving original order.
    """
    n = len(weights_list)
    score_sums = [0] * n
    game_counts = [0] * n
    last_has_longest = [False] * n
    last_tickets = [{} for _ in range(n)]

    for _ in range(n_rounds):
        indices = list(range(n))
        random.shuffle(indices)
        i = 0
        while i < n:
            primary_idx = indices[i:i+4]
            group_idx = list(primary_idx)
            while len(group_idx) < 4:
                group_idx.append(random.choice(indices))
            i += 4

            group_weights = [weights_list[j] for j in group_idx]

            card_deck, ticket_deck, face_up_cards, discard_pile = initialize_decks()
            CONNECTIONS, CITIES, board = initialize_connections_cities_board()
            PLAYER_COLORS = ['RED', 'YELLOW', 'GREEN', 'BLUE']
            game_bots = [
                HeuristicPlayer(
                    playercolor=PLAYER_COLORS[k],
                    c_deck=card_deck, t_deck=ticket_deck,
                    colors=NUMCOLORS.keys(), CITIES=CITIES,
                    USER_INPUT_CARDS=USER_INPUT_CARDS,
                    PRINT_THINGS=PRINT_THINGS,
                    weights=group_weights[k]
                )
                for k in range(4)
            ]

            results = bots_play_game(
                bots=game_bots,
                c_deck=card_deck,
                face_ups=face_up_cards,
                t_deck=ticket_deck,
                board=board,
                discard=discard_pile
            )

            updated_primaries = set()
            for r in results:
                for k, pi in enumerate(primary_idx):
                    if pi not in updated_primaries and tuple(r[0]) == tuple(weights_list[pi]):
                        updated_primaries.add(pi)
                        score_sums[pi] += r[1]
                        game_counts[pi] += 1
                        last_has_longest[pi] = r[2]
                        last_tickets[pi] = r[3]
                        break

    return [
        [list(weights_list[i]), round(score_sums[i] / max(game_counts[i], 1)),
         last_has_longest[i], last_tickets[i]]
        for i in range(n)
    ]

def breed(bot1, bot2, lr=0.25):
    new1 = list(bot1)
    new2 = list(bot2)

    # create babies
    for i in range(len(new1)):
        w1, w2 = new1[i], new2[i]
        if random.random() >= 0.5: new1[i], new2[i] = w2, w1

        # mutate
        for l in [new1, new2]:
            l[i] += (random.random() - .5) * weight_ranges[i] * lr
            l[i] = max(weight_initial_mins[i], min(weight_initial_maxes[i], l[i]))

    return tuple(new1), tuple(new2)

def breed_cycle(weights_scores_list, selection_mode="linear", elite_pct=0.0, lr=0.25):
    """
    selection_mode: "linear"    — selection probability proportional to score
                    "quadratic" — selection probability proportional to score^2
    elite_pct:      fraction 0.0–0.5 of bots guaranteed to survive each cycle
                        by simply preserving highest scorers automatically 
    lr:             learning rate for mutation; defaults to global LEARNING_RATE

    Returns a list of (weights, is_child) tuples. is_child=False for survivors,
    is_child=True for newly bred offspring.
    """
    n = len(weights_scores_list)
    half = n // 2
    n_pairs = n // 4

    def sel_weight(score):
        s = max(score, 1)
        return s * s if selection_mode == "quadratic" else s

    def weighted_pick(pool):
        total = sum(sel_weight(l[1]) for l in pool)
        r = random.random() * total
        cumsum = 0
        for i, l in enumerate(pool):
            cumsum += sel_weight(l[1])
            if cumsum > r:
                return i
        return len(pool) - 1

    results = []

    # Elite survivors: top elite_pct by score, automatically carry forward
    # truncates number of bots
    n_elite = int(n * elite_pct)
    sorted_indices = sorted(range(n), key=lambda i: weights_scores_list[i][1], reverse=True)
    elite_indices = set(sorted_indices[:n_elite])
    for i in sorted_indices[:n_elite]:
        results.append((weights_scores_list[i][0], False))

    # Probabilistic survivors: fill remaining half slots from non-elite pool
    surv_pool = [l for i, l in enumerate(weights_scores_list) if i not in elite_indices]
    for _ in range(half - n_elite):
        if not surv_pool:
            break
        idx = weighted_pick(surv_pool)
        results.append((surv_pool[idx][0], False))
        surv_pool = surv_pool[:idx] + surv_pool[idx+1:]

    # Breeding: produce children from the full population
    breed_pool = list(copy.deepcopy(weights_scores_list))
    for _ in range(n_pairs):
        if len(breed_pool) < 2:
            breed_pool = list(copy.deepcopy(weights_scores_list))

        idx1 = weighted_pick(breed_pool)
        bot1 = breed_pool[idx1][0]
        breed_pool = breed_pool[:idx1] + breed_pool[idx1+1:]

        if not breed_pool:
            breed_pool = list(copy.deepcopy(weights_scores_list))

        idx2 = weighted_pick(breed_pool)
        bot2 = breed_pool[idx2][0]
        breed_pool = breed_pool[:idx2] + breed_pool[idx2+1:]

        child1, child2 = breed(bot1, bot2, lr)
        results.append((child1, True))
        results.append((child2, True))

    return results

def output_bots(weights_scores_list, output_file):
    f = open(output_file, "w")
    for l in weights_scores_list:
        bot = l[0]
        score = l[1]
        line = str([round(n, 3) for n in list(bot)]) + "\t" + str(score)
        if len(l) > 2:
            line += "\t" + str(l[2])  # has_longest
        if len(l) > 3:
            ticket_str = ";".join(str(ticket) + ":" + str(sat) for ticket, sat in l[3].items())
            line += "\t" + ticket_str
        f.write(line + "\n")
    f.close()

# input: bots that just played. output: bots that just played. spits out each cycle of weights and scores into its own file
def cycle_bots(weights_scores_list, output_file_base_name, start=0, N_repetitions=11, selection_mode="linear", elite_pct=0.0, n_rounds=1, lr=0.25, lr_decay=1.0):
    # resumes from stage start; caller is expected to load {output_file_base_name}{start}.txt as the starting checkpoint
    # n_rounds > 1 uses averaged multi-game evaluation (collection_of_games_averaged) instead of single-game
    # lr_decay < 1.0 multiplies the learning rate by lr_decay each cycle (exponential decay)
    for i in range(start, N_repetitions):
        # output each cycle into a new file so I can retrieve it later if I hit a stopping point now
        output_bots(weights_scores_list, output_file_base_name[:output_file_base_name.index(".")] + str(i) + output_file_base_name[output_file_base_name.index("."):])
        current_lr = lr * (lr_decay ** i)
        new_bots = [b[0] for b in breed_cycle(weights_scores_list, selection_mode=selection_mode, elite_pct=elite_pct, lr=current_lr)]
        new_bots = [tuple([round(n, 3) for n in list(b)]) for b in new_bots]
        for b in new_bots:
            print(b)
        if n_rounds > 1:
            weights_scores_list = collection_of_games_averaged(new_bots, n_rounds=n_rounds)
        else:
            weights_scores_list = collection_of_games(new_bots)
    output_bots(weights_scores_list, output_file_base_name[:output_file_base_name.index(".")] + "FINAL" + output_file_base_name[output_file_base_name.index("."):])
    return weights_scores_list

'''
card_deck, ticket_deck, face_up_cards, discard_pile = initialize_decks()
connections, cities, board = initialize_connections_cities_board()
RedBot = RandomPlayer(playercolor='RED', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=cities, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS)
BlueBot = RandomPlayer(playercolor='BLUE', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=cities, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS)
GreenBot = HeuristicPlayer(playercolor='GREEN', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=cities, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                           weights=weight_averages)
YellowBot = HeuristicPlayer(playercolor='YELLOW', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=cities, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                            weights=[2.043, 0.122, 0.107, 1.17, 0.37, 0.577, 2.495, 0.512, 25.836, 45.824, 0.176, 0.917, -0.029, -0.256, -0.092, 0.549, -0.867])

bots = [YellowBot, GreenBot, RedBot, BlueBot]

weightspoints = bots_play_game(bots, card_deck, face_up_cards, ticket_deck, board, discard_pile, bots)

print(weightspoints)

'''

if __name__ == '__main__':
    
    '''
    # open file of weights and scores and make them into the list
    with open("05-12-elite-40/05-12-bot-test-stage_286.txt") as f:
        weights_scores = []
        for line in f:
            full_list = line.split("\t")

            # extract weight info
            weights_list = full_list[0].split(", ")
            weights_list[0] = weights_list[0][1:]
            weights_list[-1] = weights_list[-1][:weights_list[-1].index("]")]
            weights_list = tuple([float(weight) for weight in weights_list])

            # score is first number after the tab
            score = int(full_list[1])

            # longest_route is the boolean after the second tab
            lr_true = full_list[2] == "True"

            # the rest is the ticket dictionary of form
            # ('city1', 'city2'):bool;('city3', 'city4'):bool
            tickets_string = full_list[3]
            tickets_list = tickets_string.split(";")
            tickets_dict = {}
            for t in tickets_list:
                ticket_list = t.split(":")
                
                # tup_string is a string of form 'city1', 'city2'
                tup_string = ticket_list[0][1:-1]
                # strip off whitespace so that newline characters aren't parsed
                achieved = ticket_list[1].strip() == "True"
                cities_l = tup_string.split(", ")

                # strip off quotes
                cities_l = [s[1:-1] for s in cities_l]

                tickets_dict[(cities_l[0], cities_l[1])] = achieved

            weights_scores.append([weights_list, score, lr_true, tickets_dict])
    weights_scores_list = weights_scores
    '''

    if N_rounds == 1:
        # start from scratch - 1 round
        weights_scores_list = collection_of_games(starting_weights)
    elif N_rounds > 1:
        # start from scratch - multiple rounds
        weights_scores_list = collection_of_games_averaged(starting_weights, n_rounds=N_rounds)
        
    weights_scores_list_final = cycle_bots(weights_scores_list, 
                                           output_file_base_name="05-13-elite-40-v2/05-13-bot-test-stage_.txt", 
                                           start=start, 
                                           N_repetitions=N_repetitions, 
                                           selection_mode="quadratic",
                                           elite_pct=0.05,
                                           n_rounds=N_rounds,
                                           lr=0.5,
                                           lr_decay=0.99)
