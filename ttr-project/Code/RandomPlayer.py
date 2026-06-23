import random
import copy
import heapq
from collections import deque, defaultdict

class RandomPlayer():

    # card_deck and ticket_deck are set/dictionary respectively
    # color is set of colors possible
    # doesn't actually take cards/tickets, only sets up variables
    def __init__(self, playercolor, c_deck, t_deck, colors, CITIES, USER_INPUT_CARDS, PRINT_THINGS):

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

        self.weights = (0, 0) #dummy "weights" thing so compiling is fine

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
    def give_starting_tickets(self, t_deck):

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
            # random bot currently only chooses two tickets
            chosen_tickets = possible_tickets[:2]

            for ticket in chosen_tickets:
                self.tickets[ticket] = t_deck[ticket]
                t_deck.pop(ticket)

        if self.PRINT_THINGS: print(self.tickets)

        return t_deck

    # replaces face-ups if there are 3+ locomotives face-up
    def clean_face_ups(self, c_deck, face_ups, discard):

        if face_ups.count('WILD') >= 3:

                discard += face_ups

                if self.USER_INPUT_CARDS:

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

                    if len(c_deck) >= 5:
                        face_ups = c_deck[:5]
                        c_deck = c_deck[5:]
                    elif len(c_deck) > 0:
                        face_ups = c_deck
                        c_deck = []
                    else: #card deck is empty
                        return c_deck, face_ups, discard

        return c_deck, face_ups, discard

    # draws a single card from face-down deck
    def draw_card(self, c_deck):

        if len(c_deck) < 1:
            raise ValueError("No cards to draw")

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
            if len(possibs) > 0: possib_routes[route] = (num_needed, possibs)
        return possib_routes

    # takes new tickets
    def new_tickets(self, t_deck):

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
            # random bot currently only chooses one ticket
            chosen_tickets = possible_tickets[:1]

            for ticket in chosen_tickets:
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
            if len(cols) == 1 and "gray" not in cols and self.player_color not in cols:
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

    # expected CAFTC value if we draw a deck card
    def average_CAFTC(self, tup, route_taken, dist_left, board, current_caft=None):
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
        tup = board[route]
        num_needed = tup[0]
        return [1, 2, 4, 7, 10, 15][num_needed - 1]

    def tickets_all_done(self, board):
        for tick, val in self.tickets.items():
            if not self.has_connection(tick, board, set()):
                return False

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

    # return 10 if this move gets us the longest route, else 0
    def longest_route_change(self, board, route, players):
        other_players = list(players)
        other_players.remove(self)
        my_lrl, my_lrnum = self.find_longest_route(board)
        longest_lrnum = my_lrnum
        for bot in other_players:
            lrl, lrnum = bot.find_longest_route(board)
            if lrnum > longest_lrnum: longest_lrnum = lrnum

        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)
        board[route] = (board[route][0], temp_col_list)

        my_new_lrl, my_new_lrnum = self.find_longest_route(board)
        longest_new_lrnum = my_new_lrnum
        for bot in other_players:
            nlrl, nlrnum = bot.find_longest_route(board)
            if nlrnum > longest_new_lrnum: longest_new_lrnum = nlrnum

        # fix board
        board[route] = (board[route][0], col_list)

        if my_new_lrnum == longest_new_lrnum and my_new_lrnum > my_lrnum: return 10
        else: return 0

    def longest_route_diff(self, board, route):
        my_lrl, my_lrnum = self.find_longest_route(board)

        col_list = board[route][1]
        temp_col_list = list(col_list)
        temp_col_list.append(self.player_color)
        board[route] = (board[route][0], temp_col_list)

        my_new_lrl, my_new_lrnum = self.find_longest_route(board)

        # fix board
        board[route] = (board[route][0], col_list)

        return my_new_lrnum - my_lrnum

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

        col_to_take = max(possibs, key=possibs.get)
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
        board[route] = (num_needed, new_cols)

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

            possib_routes = self.possible_routes(board)

            # set probabilities for (first part of) turn - divide these by the sum
            P_DRAW = [45, 0][len(c_deck) == 0 and len(discard) == 0]
            P_FACE = [25, 0][len([f for f in face_ups if f in self.non_wild_colors]) == 0]
            P_FACEL = [3, 0]['WILD' not in face_ups or turn_going_to_end] #locomotive
            P_TICK = [3, 0][len(t_deck) == 0 or turn_going_to_end] #add in turn_going_to_end parts in case of repeating
            P_PLAY = [75 - self.num_trains, 0][len(possib_routes) == 0 or turn_going_to_end]

            choices = ['draw'] * P_DRAW + ['faceup'] * P_FACE + ['faceupl'] * P_FACEL + ['tick'] * P_TICK + ['play'] * P_PLAY
            choice = random.choice(choices)
            if self.PRINT_THINGS: print("\nchoice:", choice, "\n")

            # turn-ending choices first
            if choice == 'play':
                kl = list(possib_routes.keys())
                r = random.choice(kl)

                if self.PRINT_THINGS: print("RandomBot", self.player_color, "playing trains on route", r)
                board, discard = self.play_trains(r, board, discard)

                if self.PRINT_THINGS: print("discard: ", discard)

                return c_deck, face_ups, t_deck, board, discard

            if choice == 'tick':
                if self.PRINT_THINGS: print("RandomBot", self.player_color, "taking new tickets.")

                t_deck = self.new_tickets(t_deck)

                if self.PRINT_THINGS: print("Now have", self.tickets)

                return c_deck, face_ups, t_deck, board, discard

            if choice == 'faceupl':

                if len(c_deck) == 0: # refresh card deck from discard
                    c_deck = discard
                    random.shuffle(c_deck)
                    discard = []

                if self.PRINT_THINGS: print("RandomBot drawing loco face-up")

                c_deck, face_ups = self.draw_face_up(c_deck, face_ups, col='WILD', discard=discard)

                return c_deck, face_ups, t_deck, board, discard

            if choice == 'draw':

                if len(c_deck) == 0: # refresh card deck from discard
                    c_deck = discard
                    random.shuffle(c_deck)
                    discard = []

                if self.PRINT_THINGS: print("RandomBot drawing deck card")

                c_deck = self.draw_card(c_deck)

                if turn_going_to_end: #end turn
                    return c_deck, face_ups, t_deck, board, discard
                turn_going_to_end = True

            if choice == 'faceup':

                if len(c_deck) == 0: # refresh card deck from discard
                    c_deck = discard
                    random.shuffle(c_deck)
                    discard = []

                kl = [f for f in face_ups if f != 'WILD']
                col = random.choice(kl) #random non-wild color

                if self.PRINT_THINGS: print("RandomBot drawing face-up", col)

                c_deck, face_ups = self.draw_face_up(c_deck, face_ups, col, discard)

                if turn_going_to_end:
                    return c_deck, face_ups, t_deck, board, discard
                turn_going_to_end = True
