import random
import heapq
from collections import deque, defaultdict

class HeuristicPlayer():

    # card_deck and ticket_deck are set/dictionary respectively
    # color is set of colors possible
    # doesn't actually take cards/tickets, only sets up variables
    # weights is a tuple of like eleven weights
    def __init__(self, playercolor, c_deck, t_deck, colors, CITIES, USER_INPUT_CARDS, PRINT_THINGS, weights):

        self.player_color = playercolor

        self.non_wild_colors = [c for c in colors if c != 'WILD']

        # dictionary - keys: colors - values: quantity of each color in hand
        self.cards = {col: 0 for col in colors}

        # dictionary - keys: (city1, city2) - values: length
        self.tickets = {}

        self.num_trains = 45
        self.open_points = 0
        self.ticket_points = 0
        self.tickets_completed = 0

        self.CITIES = CITIES
        self.USER_INPUT_CARDS = USER_INPUT_CARDS
        self.PRINT_THINGS = PRINT_THINGS

        self.weights = weights

        # adjacency list: city -> [(other_city, pair_key)]; built once on first use
        self._adj = None

    def __str__(self):
        return self.player_color

    # build and cache adjacency list from board (graph structure never changes)
    def _get_adj(self, board):
        if self._adj is None:
            adj = defaultdict(list)
            for pair in board:
                c1, c2 = pair
                adj[c1].append((c2, pair))
                adj[c2].append((c1, pair))
            self._adj = dict(adj)
        return self._adj

    # takes starting cards
    def give_starting_cards(self, c_deck):

        if len(c_deck) < 4:
            raise ValueError("Cannot give starting cards with a deck of <4 cards")

        if self.USER_INPUT_CARDS:
            for _ in range(4):
                col = input("Please input card drawn by player " + str(self) + ": ")
                if "none" in col.strip().lower():
                    print("No card was added. Moving on")
                    break
                if col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO':
                    self.cards['WILD'] += 1
                else:
                    # if card is not locomotive
                    col = col.strip().lower()
                    if col not in self.cards:
                        raise ValueError(col, "is not a valid color")
                    else:
                        self.cards[col] += 1
        else:
            for col in c_deck[:4]:
                self.cards[col] += 1

        # update deck
        c_deck = c_deck[4:]
        if self.PRINT_THINGS: print(self.cards)
        return c_deck

    # takes starting tickets
    def give_starting_tickets(self, t_deck, board):

        if len(t_deck) < 3:
            raise ValueError("Cannot give starting tickets with a deck of <3 tickets")

        possible_tickets = random.sample(population=sorted(t_deck), k=3)

        if self.USER_INPUT_CARDS:

            possible_tickets_d = {}
            for i in range(1, 4):
                print("\nFor ticket possibility ", i, " for player ", str(self), ":", sep="")
                city1 = input("Please input ticket's first city: ")
                city2 = input("Please input ticket's second city: ")
                length = input("Please input ticket's length: ")
                if "none" in city1.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                elif "none" in city2.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                elif "none" in length.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                ticket_l = []
                for city in (city1, city2):
                    c = city.strip()
                    c = c[:1].upper() + c[1:]
                    for i in range(len(c) - 2):
                        if c[i:i+1] == " ":
                            c = c[:i+1] + c[i+1].upper() + c[i+2:].lower()
                    ticket_l.append(c)
                ticket_l = sorted(ticket_l)
                ticket = (ticket_l[0], ticket_l[1])
                possible_tickets_d[ticket] = int(length)

            if len(possible_tickets_d) == 0:
                raise ValueError("No tickets to draw.")

            chosen_tickets = []
            for ticket in possible_tickets_d:
                chosen_tickets.append((ticket, possible_tickets_d[ticket]))
            random.shuffle(chosen_tickets)
            chosen_tickets = chosen_tickets[:2]

            for ticket in chosen_tickets:
                self.tickets[ticket[0]] = ticket[1]

        else:
            t0, t1, t2 = possible_tickets
            subset_candidates = [
                [t0, t1], [t0, t2], [t1, t2],
                [t0, t1, t2]
            ]
            w1 = self.weights[17]
            w2 = self.weights[18]
            wthresh = self.weights[19]

            best_quality = float('-inf')
            best_subset = subset_candidates[0]
            for subset in subset_candidates:
                cost, _ = self.total_trains_needed_for_tickets(subset, board)
                total_value = sum(t_deck[t] for t in subset)
                quality = total_value - w1 * cost - w2 * max(0, cost - wthresh)
                if quality > best_quality:
                    best_quality = quality
                    best_subset = subset

            for ticket in best_subset:
                self.tickets[ticket] = t_deck[ticket]
                t_deck.pop(ticket)

        if self.PRINT_THINGS: print(self.tickets)

        return t_deck

    # replaces face-ups if there are 3+ locomotives face-up
    def clean_face_ups(self, c_deck, face_ups, discard):

        if face_ups.count('WILD') >= 3:

                if self.USER_INPUT_CARDS:

                    discard += face_ups
                    face_ups = []

                    for _ in range(min(5, len(c_deck))):
                        col = input("Please input face-up card: ")
                        if "none" in col.strip().lower():
                            print("No card was added. Moving on")
                            break
                        if col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO':
                            face_ups.append('WILD')
                        else:
                            # if card is not locomotive
                            col = col.strip().lower()
                            if col not in self.cards:
                                raise ValueError(col, "is not a valid color")
                            else:
                                face_ups.append(col)

                else:

                    # If c_deck is empty, try to refresh from discard before replacing face-ups.
                    # Must do this BEFORE adding face_ups to discard to avoid duplicating cards.
                    if len(c_deck) == 0 and len(discard) > 0:
                        c_deck = list(discard)
                        random.shuffle(c_deck)
                        discard = []

                    if len(c_deck) == 0:
                        # No replacement cards anywhere; leave face_ups unchanged to avoid duplication
                        return c_deck, face_ups, discard

                    discard += face_ups
                    if len(c_deck) >= 5:
                        face_ups = c_deck[:5]
                        c_deck = c_deck[5:]
                    else:
                        face_ups = list(c_deck)
                        c_deck = []

        return c_deck, face_ups, discard

    # draws a single card from face-down deck
    def draw_card(self, c_deck):

        if len(c_deck) < 1:
            raise ValueError("Cannot draw cards from deck", c_deck)

        if self.USER_INPUT_CARDS:

            col = input("Please input card drawn by player " + str(self) + ": ")
            if "none" in col.strip().lower():
                print("No card was added. Moving on")
            elif col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO':
                self.cards['WILD'] += 1
            else:
                # if card is not locomotive
                col = col.strip().lower()
                if col not in self.cards:
                    raise ValueError(col, "is not a valid color")
                else:
                    self.cards[col] += 1

        else:
            self.cards[c_deck[0]] += 1

        # update deck
        return c_deck[1:]

    # draws the face-up card with color 'col'
    def draw_face_up(self, c_deck, face_ups, col, discard):

        if col not in face_ups:
            raise ValueError("Color not one of the face up cards")

        index = face_ups.index(col)
        self.cards[col] += 1

        if len(c_deck) >= 1:
            # update deck(s)
            if self.USER_INPUT_CARDS:
                col = input("Please input face-up card: ")
                if "none" in col.strip().lower():
                    print("No card was added. Moving on")
                elif col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO':
                    face_ups[index] = 'WILD'
                else:
                    # if card is not locomotive
                    col = col.strip().lower()
                    if col not in self.cards:
                        raise ValueError(col, "is not a valid color")
                    else:
                        face_ups[index] = col

            else:
                face_ups[index] = c_deck[0]
                c_deck = c_deck[1:]

        else: #simply remove from face-ups
            face_ups = face_ups[:index] + face_ups[index+1:]

        c_deck, face_ups, discard = self.clean_face_ups(c_deck=c_deck, face_ups=face_ups, discard=discard)

        return c_deck, face_ups

    # return the board dictionary but only routes that can be taken
    def possible_routes(self, board):
        possib_routes = {}
        for route, tup in board.items():
            num_needed = tup[0]
            cols = tup[1]
            if self.player_color in cols: continue #can't take this route if you've taken the route parallel to it
            possibs = []
            for col in cols:
                if col.lower() != col: continue
                if col == 'gray':
                    for c in self.non_wild_colors:
                        if self.cards[c] + self.cards['WILD'] >= num_needed and c not in possibs:
                            possibs.append(c)
                elif self.cards[col] + self.cards['WILD'] >= num_needed and col not in possibs:
                    possibs.append(col)
            if len(possibs) > 0: possib_routes[route] = tuple((num_needed, possibs))
        return possib_routes

    # takes new tickets
    def new_tickets(self, t_deck, board):

        if len(t_deck) < 3:
            raise ValueError("Cannot give tickets with a deck of <3 tickets")

        possible_tickets = random.sample(population=sorted(t_deck), k=3)

        if self.USER_INPUT_CARDS:

            possible_tickets_d = {}
            for i in range(1, 4):
                print("\nFor ticket possibility ", i, " for player ", str(self), ":", sep="")
                city1 = input("Please input ticket's first city: ")
                city2 = input("Please input ticket's second city: ")
                length = input("Please input ticket's length: ")
                if "none" in city1.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                elif "none" in city2.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                elif "none" in length.strip().lower():
                    print("No ticket was added. Moving on")
                    break
                ticket_l = []
                for city in (city1, city2):
                    c = city.strip()
                    c = c[:1].upper() + c[1:]
                    for i in range(len(c) - 2):
                        if c[i:i+1] == " ":
                            c = c[:i+1] + c[i+1].upper() + c[i+2:].lower()
                    ticket_l.append(c)
                ticket_l = sorted(ticket_l)
                ticket = (ticket_l[0], ticket_l[1])
                possible_tickets_d[ticket] = int(length)

            if len(possible_tickets_d) == 0:
                raise ValueError("No tickets to draw.")

            chosen_tickets = []
            for ticket in possible_tickets_d:
                chosen_tickets.append((ticket, possible_tickets_d[ticket]))
            random.shuffle(chosen_tickets)
            chosen_tickets = chosen_tickets[:1]

            for ticket in chosen_tickets:
                self.tickets[ticket[0]] = ticket[1]

        else:
            t0, t1, t2 = possible_tickets
            all_subsets = [
                [t0], [t1], [t2],
                [t0, t1], [t0, t2], [t1, t2],
                [t0, t1, t2]
            ]
            w3 = self.weights[20]
            w4 = self.weights[21]
            w5 = self.weights[22]
            w6 = self.weights[23]

            cars_played = {}
            for route, (length, cols) in board.items():
                for col in cols:
                    if col == col.upper() and col != 'WILD':
                        cars_played[col] = cars_played.get(col, 0) + length
            max_cars_played = max(cars_played.values(), default=0)
            turns_left = 43 - max_cars_played

            best_quality = float('-inf')
            best_subset = None

            for subset in all_subsets:
                cost, route_list = self.total_trains_needed_for_tickets(subset, board)
                if cost > self.num_trains:
                    continue
                cards_away = self.total_cards_away_from_tickets(route_list, board)
                if cards_away > w6 * turns_left:
                    continue
                total_value = sum(t_deck[t] for t in subset)
                quality = total_value - w3 * cost - cards_away * (w4 + w5 / max(1, turns_left))
                if quality > best_quality:
                    best_quality = quality
                    best_subset = subset

            # Fallback: all subsets disqualified — take the single lowest-value ticket
            if best_subset is None:
                best_subset = [min(possible_tickets, key=lambda t: t_deck[t])]

            for ticket in best_subset:
                self.tickets[ticket] = t_deck[ticket]
                t_deck.pop(ticket)

        if self.PRINT_THINGS: print(self.tickets)

        return t_deck

    # returns True if the player has connected the cities in the tuple. DFS using adjacency list.
    # traversed is a set of cities it's traversed (should pass in an empty set)
    def has_connection(self, tup, board, traversed):
        if tup[0] == tup[1]:
            return True
        adj = self._get_adj(board)
        for other, pair in adj.get(tup[0], []):
            if self.player_color in board[pair][1] and other not in traversed:
                traversed.add(other)
                if self.has_connection((other, tup[1]), board, traversed):
                    return True
        return False

    # calculates and returns number of ticket points; also updates self.tickets_completed
    def calc_ticket_points(self, board):

        # reset for algorithm
        self.tickets_completed = 0
        self.ticket_points = 0
        for tick, val in self.tickets.items():
            if self.has_connection(tick, board, set()):
                self.tickets_completed += 1
                self.ticket_points += val
            else:
                self.ticket_points -= val
        return self.ticket_points

    # helper method to use BFS to find player's longest consecutive train route starting at a particular city
    def find_longest_route_starting_at_city(self, board, city):
        adj = self._get_adj(board)
        longest_route = 0
        longest_route_l = []
        q = deque()

        # seed BFS with every player-owned edge touching city
        for other, pair in adj.get(city, []):
            if self.player_color in board[pair][1]:
                q.append(([city, other], frozenset({pair})))

        # BFS: extend each partial route; when no extension is possible, score it
        while q:
            route, traversed = q.popleft()
            next_city = route[-1]
            extended = False
            for other, pair in adj.get(next_city, []):
                if self.player_color in board[pair][1] and pair not in traversed:
                    q.append((route + [other], traversed | {pair}))
                    extended = True
            if not extended:
                route_len = 0
                for cit, nxt in zip(route, route[1:]):
                    key = (cit, nxt) if (cit, nxt) in board else (nxt, cit)
                    route_len += board[key][0]
                if route_len > longest_route:
                    longest_route = route_len
                    longest_route_l = route

        return longest_route_l, longest_route

    # find player's longest consecutive train route
    def find_longest_route(self, board):

        # only start BFS from cities where this player has placed trains
        active_cities = set()
        for pair in board:
            if self.player_color in board[pair][1]:
                active_cities.update(pair)
        if not active_cities:
            return [], 0

        longest_route = 0
        longest_route_list = []
        for city in active_cities:
            li, length = self.find_longest_route_starting_at_city(board, city)
            if length > longest_route:
                longest_route = length
                longest_route_list = li
        return longest_route_list, longest_route

    # uses Dijkstra to find the minimum distance between the cities in tuple tup
    def min_dist_between_cities(self, tup, board):
        adj = self._get_adj(board)
        counter = 0
        pq = [(0, counter, tup[0])]
        cities_found = {tup[0]: 0}
        while pq:
            dist, _, city = heapq.heappop(pq)
            if dist > cities_found.get(city, float('inf')):
                continue
            if city == tup[1]:
                return dist
            for other, pair in adj.get(city, []):
                new_dist = dist + board[pair][0]
                if other not in cities_found or cities_found[other] > new_dist:
                    cities_found[other] = new_dist
                    counter += 1
                    heapq.heappush(pq, (new_dist, counter, other))

    # same as min_dist_between_cities but counts routes this player has taken as adding 0 distance
    def dist_left_to_span(self, tup, board):
        adj = self._get_adj(board)
        counter = 0
        pq = [(0, counter, tup[0], [])]
        cities_found = {tup[0]: 0}
        while pq:
            dist, _, city, route_taken = heapq.heappop(pq)
            if dist > cities_found.get(city, float('inf')):
                continue
            if city == tup[1]:
                return dist, route_taken
            for other, pair in adj.get(city, []):
                d = 0 if self.player_color in board[pair][1] else board[pair][0]
                new_dist = dist + d
                if other not in cities_found or cities_found[other] > new_dist:
                    cities_found[other] = new_dist
                    counter += 1
                    heapq.heappush(pq, (new_dist, counter, other, route_taken + [pair]))
        return float('inf'), []

    # original_dist is the dist_left_to_span prior to playing the route
    def distance_reduction(self, original_dist, route, ticket_tup, board):
        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)

        board[route] = (board[route][0], temp_col_list)
        d, rl = self.dist_left_to_span(ticket_tup, board)
        dr = max(0, original_dist - d) # find distance reduction

        # fix board
        board[route] = (board[route][0], col_list)

        return dr

    # return whether better_hand actually has more than (or the same as) worse_hand of every card
    def hand_objectively_better(self, better_hand, worse_hand):
        for col in self.cards:
            if worse_hand[col] > better_hand[col]: return False
        return True

    # how many cards away are we from having enough cards to take the entire route given?  (route_taken is a list of tuples here)
    def cards_away_from_ticket(self, tup, route_taken, dist_left, board):
        original_hand_size = sum(self.cards.values())
        hypothetical_hands = [self.cards.copy()]

        for route in route_taken:
            # loop through all single-route-not-gray first
            cols = board[route][1]
            if len(cols) == 1 and "gray" not in cols and sum(col == col.upper() for col in cols) == 0: #none of the cols are uppercase
                # only one hypothetical hand right now
                n_cards = hypothetical_hands[0][cols[0]]
                if n_cards >= board[route][0]:
                    hypothetical_hands[0][cols[0]] -= board[route][0]
                else:
                    hypothetical_hands[0][cols[0]] -= n_cards
                    n_wilds = hypothetical_hands[0]['WILD']
                    if n_wilds >= (board[route][0] - n_cards):
                        hypothetical_hands[0]['WILD'] -= (board[route][0] - n_cards)
                    else:
                        hypothetical_hands[0]['WILD'] -= n_wilds

        for route in route_taken:
            cols = board[route][1]
            # now loop through double routes
            if len(cols) == 2 and "gray" not in cols and self.player_color not in cols:
                new_hypothetical_hands = []
                for hand in hypothetical_hands:
                    for col in cols:
                        if col.upper() == col: continue #can't play on a player color
                        handcopy = hand.copy()
                        n_cards = handcopy[col]
                        if n_cards >= board[route][0]:
                            handcopy[col] -= board[route][0]
                        else:
                            handcopy[col] -= n_cards
                            n_wilds = handcopy['WILD']
                            if n_wilds >= (board[route][0] - n_cards):
                                handcopy['WILD'] -= (board[route][0] - n_cards)
                            else:
                                handcopy['WILD'] -= n_wilds
                        new_hypothetical_hands.append(handcopy)
                hypothetical_hands = new_hypothetical_hands

        for route in route_taken:
            cols = board[route][1]
            # now loop through gray routes
            if "gray" in cols and self.player_color not in cols:
                new_hypothetical_hands = []
                for hand in hypothetical_hands:
                    for col in self.non_wild_colors: # non-wild, non-player-color cards
                        handcopy = hand.copy()
                        n_cards = handcopy[col]
                        if n_cards >= board[route][0]:
                            handcopy[col] -= board[route][0]
                        else:
                            handcopy[col] -= n_cards
                            n_wilds = handcopy['WILD']
                            if n_wilds >= (board[route][0] - n_cards):
                                handcopy['WILD'] -= (board[route][0] - n_cards)
                            else:
                                handcopy['WILD'] -= n_wilds
                        new_hypothetical_hands.append(handcopy)
                hypothetical_hands = new_hypothetical_hands

        # now that all the routes have been removed
        best_hand = 0
        if len(hypothetical_hands) > 0:
            best_hand = min(sum(hand.values()) for hand in hypothetical_hands)

        return dist_left - (original_hand_size - best_hand)

    # would we get less cards away from this ticket (1) or would it stay the same (0) if we drew a given card?
    def cards_away_from_ticket_change(self, card_taken, tup, route_taken, dist_left, board, current_caft=None):
        if current_caft is None:
            current_caft = self.cards_away_from_ticket(tup, route_taken, dist_left, board)
        self.cards[card_taken] += 1
        new_cards_away = self.cards_away_from_ticket(tup, route_taken, dist_left, board)
        self.cards[card_taken] -= 1
        return current_caft - new_cards_away #will always be positive or 0

    # would we get more cards away from this ticket (-n) or would it stay the same (0) if we played a given route?
    def CAFT_change_from_playing(self, route_playing, ticket, route_taken, dist_left, board, current_caft=None):
        current_cards_away = self.cards_away_from_ticket(ticket, route_taken, dist_left, board) if current_caft is None else current_caft
        possib_hand = self.cards.copy()

        # simulate playing trains via changing card numbers
        tup = board[route_playing]
        num_needed = tup[0]
        cols = tup[1]
        old_cols = list(cols)
        possibs = {} # dictionary of possible colors to take and how much the bot has of that color plus wilds
        for col in cols:
            if col.lower() != col: continue
            if col == 'gray':
                for c in self.non_wild_colors:
                    if self.cards[c] + self.cards['WILD'] >= num_needed and c not in possibs:
                        possibs[c] = self.cards[c] + self.cards['WILD']
            elif self.cards[col] + self.cards['WILD'] >= num_needed and col not in possibs:
                possibs[col] = self.cards[col] + self.cards['WILD']
        if len(possibs) == 0:
            raise ValueError("Not enough trains to take route", route_playing)
        # decide which color to take (most cards of that color)
        col_to_take = max(possibs, key=possibs.get)
        # play trains (update hypothetical data structure)
        new_cols = list(cols)
        num_left = num_needed
        for i in range(len(new_cols)):
            if new_cols[i] == col_to_take or new_cols[i] == 'gray':
                new_cols[i] = self.player_color
                if possib_hand[col_to_take] >= num_left:
                    possib_hand[col_to_take] -= num_left
                else: #take all the cards from this color plus any wilds needed
                    num_left -= possib_hand[col_to_take]
                    possib_hand[col_to_take] = 0
                    possib_hand['WILD'] -= num_left
                break #don't want to replace all in case it's a gray route

        board[route_playing] = (num_needed, new_cols)
        dist_left -= num_needed #update dist_left

        # after "playing trains"
        old_cards = self.cards.copy()
        self.cards = possib_hand
        new_cards_away = self.cards_away_from_ticket(tup, route_taken, dist_left, board)

        # return to current
        self.cards = old_cards
        board[route_playing] = (num_needed, old_cols)
        return current_cards_away - new_cards_away #will always be negative, or 0 if these cards are being used perfectly ideally

    # expected CAFTC value if we draw a deck card
    def average_CAFTC(self, tup, route_taken, dist_left, board, current_caft=None):
        # uses full-deck counts as an approximation; does not account for cards already in play or discarded
        num_each_color_card = 12
        num_wild = 14
        num_cols = 8
        total_cards = num_each_color_card * num_cols + num_wild
        if current_caft is None:
            current_caft = self.cards_away_from_ticket(tup, route_taken, dist_left, board)

        avg_val = 0
        for col in self.cards:
            val = self.cards_away_from_ticket_change(col, tup, route_taken, dist_left, board, current_caft)
            if col == "WILD": avg_val += val * (num_wild / total_cards)
            else: avg_val += val * (num_each_color_card / total_cards)

        return avg_val

    # how many points do we get directly from playing a given route?
    def points_gained_from_playing(self, route, board):
        return [1, 2, 4, 7, 10, 15][board[route][0] - 1]

    def tickets_all_done(self, board):
        for tick, val in self.tickets.items():
            if not self.has_connection(tick, board, set()):
                return False
        return True

    # bonus in heuristic for taking new tickets, based on how many train cars lowest person has left. tickets don't need to be all done
    # (that's accounted for in actual heuristic calculation)
    def ticket_taking_boost(self, board):

        players_trains_played = {} # dict of playercolor, total_trains_played
        for route in board:
            cols = board[route][1]
            l = board[route][0]
            for col in cols:
                if col.upper() == col:
                    # then the player with this color has played on this route
                    if col in players_trains_played: players_trains_played[col] += l
                    else: players_trains_played[col] = l

        if players_trains_played == {}: most_played = 0
        else: most_played = max(players_trains_played.values())

        return 45 - most_played

    def num_trains_played(self, tup, board):
        return board[tup][0]

    # return increase in ticket points that would result from playing this route
    def ticket_point_change(self, route, board):
        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)

        board[route] = (board[route][0], temp_col_list)

        new_tp = 0
        for tick, val in self.tickets.items():
            if self.has_connection(tick, board, set()):
                new_tp += val
            else:
                new_tp -= val

        # fix board
        board[route] = (board[route][0], col_list)

        return new_tp - self.ticket_points

    # compute both longest-route bonus (10 if this play would give us the longest route) and
    # longest-route diff (increase in our longest route) in a single find_longest_route call post-play
    def _lr_change_and_diff(self, board, route, other_max_lr, my_lr):
        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)
        board[route] = (board[route][0], temp_col_list)

        my_new_lrnum = self.find_longest_route(board)[1]
        longest_new_lrnum = max(my_new_lrnum, other_max_lr)

        # fix board
        board[route] = (board[route][0], col_list)

        lr_change = 10 if (my_new_lrnum == longest_new_lrnum and my_new_lrnum > my_lr and longest_new_lrnum > 10) else 0
        lr_diff = my_new_lrnum - my_lr
        return lr_change, lr_diff

    # return 10 if this move gets us the longest route, else 0
    def longest_route_change(self, board, route, players, other_max_lr=None):
        if other_max_lr is None:
            other_max_lr = max((p.find_longest_route(board)[1] for p in players if str(p) != str(self)), default=0)
        my_lrl, my_lrnum = self.find_longest_route(board)

        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)
        board[route] = (board[route][0], temp_col_list)

        my_new_lrnum = self.find_longest_route(board)[1]
        longest_new_lrnum = max(my_new_lrnum, other_max_lr)

        # fix board
        board[route] = (board[route][0], col_list)

        if my_new_lrnum == longest_new_lrnum and my_new_lrnum > my_lrnum and longest_new_lrnum > 10: return 10
        else: return 0

    def longest_route_diff(self, board, route):
        my_lrl, my_lrnum = self.find_longest_route(board)

        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)
        board[route] = (board[route][0], temp_col_list)

        my_new_lrnum = self.find_longest_route(board)[1]

        # fix board
        board[route] = (board[route][0], col_list)

        return my_new_lrnum - my_lrnum

    def total_trains_needed_for_tickets(self, tickets, board):
        """
        Returns (cost, route_list) — minimum train cars and the corresponding unclaimed
        routes to build a network satisfying all tickets simultaneously. Already-claimed
        routes cost 0. Uses Dreyfus-Wagner Steiner tree DP.
        """
        ticket_list = list(tickets)
        terminals = list({city for ticket in ticket_list for city in ticket})
        k = len(terminals)
        if k <= 1:
            return 0, []

        adj = self._get_adj(board)
        all_cities = list({c for pair in board for c in pair})
        INF = float('inf')

        def _dijkstra(src):
            dist = {c: INF for c in all_cities}
            prev = {c: None for c in all_cities}
            dist[src] = 0
            counter = 0
            pq = [(0, counter, src)]
            while pq:
                d, _, city = heapq.heappop(pq)
                if d > dist[city]:
                    continue
                for other, pair in adj.get(city, []):
                    w = 0 if self.player_color in board[pair][1] else board[pair][0]
                    nd = d + w
                    if nd < dist[other]:
                        dist[other] = nd
                        prev[other] = (city, pair)
                        counter += 1
                        heapq.heappush(pq, (nd, counter, other))
            return dist, prev

        sp_dist = []
        sp_prev = []
        for t in terminals:
            d, p = _dijkstra(t)
            sp_dist.append(d)
            sp_prev.append(p)

        full_mask = (1 << k) - 1
        dp = {}
        back = {}

        for i in range(k):
            s = 1 << i
            for city in all_cities:
                dp[(s, city)] = sp_dist[i][city]
                back[(s, city)] = ('base', i)

        for size in range(2, k + 1):
            for s in range(1, full_mask + 1):
                if bin(s).count('1') != size:
                    continue
                lsb = s & (-s)
                rest = s ^ lsb
                for city in all_cities:
                    dp[(s, city)] = INF
                    back[(s, city)] = None
                # enumerate all proper subsets of s containing lsb
                sub = rest
                while True:
                    s1 = sub | lsb
                    s2 = rest ^ sub
                    if s2 > 0:
                        for city in all_cities:
                            cost = dp.get((s1, city), INF) + dp.get((s2, city), INF)
                            if cost < dp[(s, city)]:
                                dp[(s, city)] = cost
                                back[(s, city)] = ('split', s1, s2)
                    if sub == 0:
                        break
                    sub = (sub - 1) & rest
                # Dijkstra relaxation: allow tree to route through non-terminal nodes
                counter = 0
                pq = []
                for city in all_cities:
                    if dp[(s, city)] < INF:
                        counter += 1
                        heapq.heappush(pq, (dp[(s, city)], counter, city))
                while pq:
                    d, _, city = heapq.heappop(pq)
                    if d > dp[(s, city)]:
                        continue
                    for other, pair in adj.get(city, []):
                        w = 0 if self.player_color in board[pair][1] else board[pair][0]
                        nd = d + w
                        if nd < dp[(s, other)]:
                            dp[(s, other)] = nd
                            back[(s, other)] = ('edge', city, pair)
                            counter += 1
                            heapq.heappush(pq, (nd, counter, other))

        best_cost = INF
        best_root = None
        for city in all_cities:
            c = dp.get((full_mask, city), INF)
            if c < best_cost:
                best_cost = c
                best_root = city

        if best_root is None or best_cost == INF:
            return INF, []

        routes_used = set()

        def _reconstruct(mask, city):
            entry = back.get((mask, city))
            if entry is None:
                return
            kind = entry[0]
            if kind == 'base':
                term_idx = entry[1]
                cur = city
                while sp_prev[term_idx][cur] is not None:
                    prev_city, route = sp_prev[term_idx][cur]
                    if self.player_color not in board[route][1]:
                        routes_used.add(route)
                    cur = prev_city
            elif kind == 'split':
                _reconstruct(entry[1], city)
                _reconstruct(entry[2], city)
            elif kind == 'edge':
                prev_city, route = entry[1], entry[2]
                if self.player_color not in board[route][1]:
                    routes_used.add(route)
                _reconstruct(mask, prev_city)

        _reconstruct(full_mask, best_root)
        return best_cost, list(routes_used)

    def total_cards_away_from_tickets(self, route_list, board):
        """
        Returns the minimum additional train cards needed beyond self.cards to claim
        all routes in route_list. Mirrors cards_away_from_ticket over a full route set.
        """
        dist_left = sum(board[r][0] for r in route_list if self.player_color not in board[r][1])
        original_hand_size = sum(self.cards.values())
        hypothetical_hands = [self.cards.copy()]

        # Pass 1: single-color non-gray routes
        for route in route_list:
            cols = board[route][1]
            if self.player_color in cols:
                continue
            if len(cols) == 1 and 'gray' not in cols and not any(c == c.upper() for c in cols):
                n = board[route][0]
                col = cols[0]
                new_hands = []
                for hand in hypothetical_hands:
                    h = hand.copy()
                    have = h[col]
                    if have >= n:
                        h[col] -= n
                    else:
                        h[col] = 0
                        h['WILD'] -= min(h['WILD'], n - have)
                    new_hands.append(h)
                hypothetical_hands = new_hands

        # Pass 2: double (two-color) non-gray routes — greedy: pick the color that covers the most
        for route in route_list:
            cols = board[route][1]
            if self.player_color in cols:
                continue
            if len(cols) == 2 and 'gray' not in cols:
                n = board[route][0]
                non_upper = [c for c in cols if c.upper() != c]
                if not non_upper:
                    continue
                new_hands = []
                for hand in hypothetical_hands:
                    best_col = max(non_upper, key=lambda c: min(hand[c], n))
                    h = hand.copy()
                    have = h[best_col]
                    if have >= n:
                        h[best_col] -= n
                    else:
                        h[best_col] = 0
                        h['WILD'] -= min(h['WILD'], n - have)
                    new_hands.append(h)
                hypothetical_hands = new_hands

        # Pass 3: gray routes — greedy: pick the color that covers the most (avoids 9^N blowup)
        for route in route_list:
            cols = board[route][1]
            if self.player_color in cols:
                continue
            if 'gray' in cols:
                n = board[route][0]
                new_hands = []
                for hand in hypothetical_hands:
                    best_col = max(self.non_wild_colors, key=lambda c: min(hand[c], n))
                    h = hand.copy()
                    have = h[best_col]
                    if have >= n:
                        h[best_col] -= n
                    else:
                        h[best_col] = 0
                        h['WILD'] -= min(h['WILD'], n - have)
                    new_hands.append(h)
                hypothetical_hands = new_hands

        if not hypothetical_hands:
            return dist_left
        best_hand = min(sum(h.values()) for h in hypothetical_hands)
        return dist_left - (original_hand_size - best_hand)

    '''
    a: Ticket Contribution Factor
        high a incentivizes player to reduce the distance left to get the ticket
        weighted based on ticket length, since longer tickets are more critical
    b: Longest-Route Aggression
        high b incentivizes player to take a route that will give them the longest continuous route
    c: Longest-Route Priority
        high c incentivizes player to take a route that will increase their longest continuous route
            note: b examines whether a given move would outright give them the longest route;
            c just examines the increase in their longest route
    d: Direct Scoring Weight
        high d incentivizes player to take a route that will give them more points (e.g. 6 trains = 15 points)
    e: Direct Ticket Weight
        high e incentivizes player to take a route that will increase how many points they get from tickets
    f: Optimal Card Weight
        high f incentivizes player to draw cards that will make it easier for them to take a ticket
        weighted based on ticket length, since longer tickets are more critical
    g: Train Use Specificity
        high g penalizes player for playing trains, forcing them to only take routes that really matter
    h: Ticket Draw Aggression
        high h (mostly) boosts value of taking tickets if other players have not played many trains
    j: Ticket Draw Opportunism
        high j (mostly) boosts value of taking tickets if this player has completed tickets
    k: Ticket Draw Risk Factor
        high k decreases value of taking tickets in case other players have played lots of trains
    l: Wild Draw Penalty
        high l penalizes player for drawing face-up locomotive as opposed to other face-up cards
    m: Ticket Inefficiency Penalty
        high m penalizes player for taking a route that forces the player to use cards inefficiently to connect a ticket
        weighted based on ticket length, since longer tickets are more critical
    n: Expected Score Parameter
        baseline score. included for the model of move_quality ~= # points expected from move but shouldn't affect moves made
    p: Face-Down Draw Priority
        high p incentivizes player to draw face-down cards
    q: Ticket Draw Priority
        high q incentivizes player to take new tickets
    r: Face-Up Draw Priority
        high r incentivizes player to draw faceup cards
    s: Train Play Priority
        high s incentivizes player to play trains
    t: Start Ticket Length Aversion
        high t penalizes ticket collections requiring many train cars to complete (start of game)
    u: Start Ticket Overrun Penalty
        high u adds an extra penalty when total_trains_needed exceeds the overrun threshold v
        captures heightened risk of collections that eat nearly the whole game
    v: Start Ticket Overrun Threshold
        high v means penalty from u only kicks in for longer tickets
        train-car count above which the u penalty kicks in when choosing starting tickets
    w: Midgame Ticket Length Aversion
        high w penalizes midgame ticket collections requiring many train cars
        separate from t so the bot can evolve different risk tolerances for start vs midgame
    x: Midgame Ticket Difficulty Penalty
        high x penalizes midgame ticket collections requiring many additional cards
    y: Late Game Ticket Urgency
        high y amplifies the card penalty more as the game nears its end
        divides by remaining turns-worth of trains (43 - max cars played by any player)
    z: Late Game Ticket Refusal Threshold
        high z keeps bot from taking tickets that require many cards if the game is near its end
        controls how conservatively the bot refuses ticket subsets when too many
        cards are still needed relative to the game's remaining length
    '''
    # high = good move
    # my_lr: pre-computed value of self.find_longest_route(board)[1] to avoid redundant calls across play moves
    def move_quality(self, move_type, the_rest, board, players, dist_cache=None, caft_cache=None, other_max_lr=None, my_lr=None):
        # a: dist_reduction  b: lr_bonus(10pt)  c: lr_diff  d: route_pts  e: ticket_pt_change
        # f: caftc_draw  g: trains_used_penalty  h: ticket_timing  j: all_done_bonus
        # k: ticket_timing_offset  l: faceup_card_bonus  m: caftc_play  n: baseline
        # p: draw_offset  q: tickets_offset  r: faceup_offset  s: play_offset
        a, b, c, d, e, f, g, h, j, k, l, m, n, p, q, r, s, t, u, v, w, x, y, z = self.weights
        val = n

        # do it for "draw" moves
        if move_type == "draw":
            for ticket in self.tickets:
                dist, route = dist_cache[ticket] if dist_cache is not None else self.dist_left_to_span(ticket, board)
                current_caft = caft_cache[ticket] if caft_cache is not None else None
                avg_caftc = self.average_CAFTC(ticket, route, dist, board, current_caft)

                # Weighted by distance of ticket / 5, so bot aims for longer tickets.
                # /5 so that initialized ranges of values are still ballpark appropriate
                # (Didn't want to change initializing ranges that I carefully thought out)
                val += dist * (f * avg_caftc) / (len(self.tickets) * 5) + p
            return val

        # do it for new-ticket-taking
        if move_type == "tickets":
            boost = self.ticket_taking_boost(board)
            done = [0, j][self.tickets_all_done(board)]
            val += h * (boost + done - k) + q
            return val

        if move_type == "faceup":
            col = the_rest
            for ticket in self.tickets:
                dist, route = dist_cache[ticket] if dist_cache is not None else self.dist_left_to_span(ticket, board)
                current_caft = caft_cache[ticket] if caft_cache is not None else None
                avg_caftc = self.cards_away_from_ticket_change(col, ticket, route, dist, board, current_caft)

                # Weighted by distance of ticket / 5, so bot aims for longer tickets
                val += dist * (f * avg_caftc) / (len(self.tickets) * 5) + r
            val += [l * 2, l][col == 'WILD'] # add l * number of cards drawn
            return val

        if move_type == "play":
            idx = the_rest.index("-")
            route_playing = (the_rest[:idx], the_rest[idx+1:])
            for ticket in self.tickets:
                dist, route = dist_cache[ticket] if dist_cache is not None else self.dist_left_to_span(ticket, board)
                current_caft = caft_cache[ticket] if caft_cache is not None else None
                reduction = self.distance_reduction(dist, route_playing, ticket, board)
                caftc = self.CAFT_change_from_playing(route_playing, ticket, route, dist, board, current_caft)

                # Weighted by distance of ticket / 5, so bot aims for longer tickets
                val += dist * (a * reduction) / (len(self.tickets) * 5)
                val += dist * (m * caftc) / (len(self.tickets) * 5)

            if my_lr is None:
                my_lr = self.find_longest_route(board)[1]
            lr_change, lr_diff = self._lr_change_and_diff(board, route_playing, other_max_lr, my_lr)
            points_gained = self.points_gained_from_playing(route_playing, board)
            tp_change = self.ticket_point_change(route_playing, board)
            trains_played = self.num_trains_played(route_playing, board)
            val += b * lr_change + c * lr_diff + d * points_gained + e * tp_change - g * trains_played + s
            return val

        raise ValueError("Move type \'", move_type, "\' and the_rest \'", the_rest, "\' invalid", sep="")

    def best_move(self, possible_moves, board, players):
        # precompute per-ticket costs once so move_quality doesn't repeat expensive Dijkstra/CAFT per candidate
        dist_cache = {ticket: self.dist_left_to_span(ticket, board) for ticket in self.tickets}
        caft_cache = {ticket: self.cards_away_from_ticket(ticket, dist_cache[ticket][1], dist_cache[ticket][0], board)
                      for ticket in self.tickets}
        other_max_lr = max((p.find_longest_route(board)[1] for p in players if str(p) != str(self)), default=0)
        my_lr = self.find_longest_route(board)[1]

        # Endgame override: on the last turn, restrict to train-playing only and score
        # by direct point benefit (no heuristic weights — maximize immediate points).
        if any(p.num_trains <= 2 for p in players):
            play_moves = [m for m in possible_moves if m.startswith('play-')]
            if play_moves:
                best_val = float('-inf')
                best_entry = None
                for move in play_moves:
                    the_rest = move[5:]  # strip leading 'play-'
                    idx = the_rest.index('-')
                    route = (the_rest[:idx], the_rest[idx+1:])
                    lr_change, _ = self._lr_change_and_diff(board, route, other_max_lr, my_lr)
                    score = (self.points_gained_from_playing(route, board)
                             + self.ticket_point_change(route, board)
                             + lr_change)
                    if score > best_val:
                        best_val = score
                        best_entry = (-score, 'play', the_rest)
                return best_entry
            # No playable routes on last turn: fall through to normal heuristic

        best_val = float('-inf')
        best_entry = None
        for move in possible_moves:
            if "-" in move:
                idx = move.index("-")
                move_type = move[:idx]
                the_rest = move[idx+1:]
            else:
                move_type = move
                the_rest = ""
            val = self.move_quality(move_type, the_rest, board, players, dist_cache, caft_cache, other_max_lr, my_lr)
            if val > best_val:
                best_val = val
                best_entry = (-val, move_type, the_rest)
        return best_entry

    # route is a tuple, ordered, of cities
    def play_trains(self, route, board, discard):

        tup = board[route]
        num_needed = tup[0]
        cols = tup[1]
        possibs = {} # dictionary of possible colors to take and how much the bot has of that color plus wilds
        for col in cols:
            if col.lower() != col: continue
            if col == 'gray':
                for c in self.non_wild_colors:
                    if self.cards[c] + self.cards['WILD'] >= num_needed and c not in possibs:
                        possibs[c] = self.cards[c] + self.cards['WILD']
            elif self.cards[col] + self.cards['WILD'] >= num_needed and col not in possibs:
                possibs[col] = self.cards[col] + self.cards['WILD']

        if len(possibs) == 0:
            raise ValueError("Not enough trains to take route", route)

        # decide which route to take
        col_to_take = ""
        n_had = 0
        for c, n in possibs.items(): #random.choice(possibs.keys())
            if n > n_had:
                col_to_take = c
                n_had = n
        # play trains (update data structures)
        new_cols = cols
        num_left = num_needed
        for i in range(len(cols)):
            if cols[i] == col_to_take or cols[i] == 'gray':
                new_cols[i] = self.player_color
                if self.cards[col_to_take] >= num_left:
                    discard += [col_to_take] * num_needed # since it's all those needed
                    self.cards[col_to_take] -= num_left
                else: #take all the cards from this color plus any wilds needed
                    discard += [col_to_take] * self.cards[col_to_take]
                    num_left -= self.cards[col_to_take]
                    self.cards[col_to_take] = 0
                    discard += ['WILD'] * num_left # number of wilds used
                    self.cards['WILD'] -= num_left
                break #don't want to replace all in case it's a gray route
        board[route] = tuple((num_needed, new_cols))

        # update number of trains and points
        self.num_trains -= num_needed
        self.open_points += [1, 2, 4, 7, 10, 15][num_needed - 1]

        return board, discard

    def take_turn(self, c_deck, face_ups, t_deck, board, discard, players):

        turn_going_to_end = False

        self.ticket_points = self.calc_ticket_points(board)

        while True: # turn_going_to_end mechanism is coded in later, so it always takes the right # of actions

            # replenish face-ups if possible
            if self.USER_INPUT_CARDS:
                while len(face_ups) < 5:
                    col = input("Please input replenished face-up card: ")
                    if "none" in col.strip().lower():
                        print("No card was added. Moving on")
                        break
                    if col.strip().upper() == 'WILD' or col.strip().upper() == 'LOCO':
                        face_ups.append('WILD')
                    else:
                        # if card is not locomotive
                        col = col.strip().lower()
                        if col not in self.cards:
                            raise ValueError(col, "is not a valid color")
                        else:
                            face_ups.append(col)
            else:
                while len(face_ups) < 5 and len(c_deck) > 0:
                    face_ups.append(c_deck.pop(0))

            c_deck, face_ups, discard = self.clean_face_ups(c_deck=c_deck, face_ups=face_ups, discard=discard)

            # find and make best move, depending on whether or not we've already drawn
            if turn_going_to_end == False: # any move is available

                possib_routes = self.possible_routes(board)

                # come up with a list of all the possible moves to make
                possible_moves = []

                # can draw face-down card as long as deck is nonempty
                # deck can still be empty if discard is also empty (players hogging cards)
                # so we need to check if there are cards to draw
                if len(c_deck) > 0 or len(discard) > 0:
                    possible_moves += ["draw"] # draw face-down card

                # draw each face-up card, including face-up locomotives
                possible_moves += ["faceup" + "-" + col for col in face_ups]

                # take new tickets (only if deck has enough)
                # if deck has less than three tickets, we don't allow drawing tickets
                if len(t_deck) >= 3:
                    possible_moves += ["tickets"]

                # play on a route
                possible_moves += ["play" + "-" + route[0] + "-" + route[1] for route in possib_routes]

                if self.PRINT_THINGS: print(possible_moves)

                # no moves available (all cards held by players, no claimable routes, no tickets)
                if not possible_moves:
                    return c_deck, face_ups, t_deck, board, discard

                best_move = self.best_move(possible_moves, board, players)
                best_move_val = best_move[0]
                move_type = best_move[1]
                move_info = best_move[2]

                if self.PRINT_THINGS: print(best_move_val, move_type, move_info)

                choice = move_type
            else: #has already taken a card, needs to take another 
                # (only options available: draw face-down or face-up non-wild)

                # come up with a list of all the possible moves to make
                possible_moves = []

                # can draw face-down card as long as deck is nonempty
                # deck can still be empty if discard is also empty (players hogging cards)
                # so we need to check if there are cards to draw
                if len(c_deck) > 0 or len(discard) > 0:
                    possible_moves += ["draw"] # draw face-down card

                # play on a route
                possible_moves += ["faceup" + "-" + col for col in face_ups if col != 'WILD'] #draw each face-up card, excluding face-up locomotives

                if self.PRINT_THINGS: print(possible_moves)

                # case where draw and discard both empty and there are only face-up wilds left
                # in this case, just end the player's turn
                if not possible_moves:
                    return c_deck, face_ups, t_deck, board, discard

                best_move = self.best_move(possible_moves, board, players)
                best_move_val = best_move[0]
                move_type = best_move[1]
                move_info = best_move[2]

                if self.PRINT_THINGS: print(best_move_val, move_type, move_info)

                choice = move_type

            # turn-ending choices first
            if choice == 'play':
                r = (move_info[:move_info.index("-")], move_info[move_info.index("-")+1:])

                if self.PRINT_THINGS: print("HeuristicBot", self.player_color, "playing trains on route", r)
                board, discard = self.play_trains(r, board, discard)

                if self.PRINT_THINGS: print("discard: ", discard)

                return c_deck, face_ups, t_deck, board, discard

            if choice == 'tickets':
                if self.PRINT_THINGS: print("HeuristicBot", self.player_color, "taking new tickets.")

                t_deck = self.new_tickets(t_deck, board)

                if self.PRINT_THINGS: print("Now have", self.tickets)

                return c_deck, face_ups, t_deck, board, discard

            if choice == 'draw':

                if len(c_deck) == 0: # refresh card deck from discard
                    c_deck = discard
                    random.shuffle(c_deck)
                    discard = []

                if self.PRINT_THINGS: print("HeuristicBot drawing deck card")

                c_deck = self.draw_card(c_deck)

                if turn_going_to_end: #end turn
                    return c_deck, face_ups, t_deck, board, discard
                turn_going_to_end = True

            if choice == 'faceup':

                col = move_info
                if col == 'WILD':
                    turn_going_to_end = True

                if self.PRINT_THINGS: print("HeuristicBot drawing face-up", col)

                c_deck, face_ups = self.draw_face_up(c_deck, face_ups, col, discard)

                if turn_going_to_end:
                    return c_deck, face_ups, t_deck, board, discard
                turn_going_to_end = True
