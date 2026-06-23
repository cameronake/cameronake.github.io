"""
Tests that call initialize_decks() or initialize_connections_cities_board()
require txt_storage/routes.txt and txt_storage/newconnectionroutes.txt
and are skipped automatically when the files aren't present.

All other tests use a synthetic in-memory board and run without any data files
"""

import copy
import os
import random
import tempfile
import unittest

HAS_DATA_FILES = (
    os.path.exists('txt_storage/routes.txt') and
    os.path.exists('txt_storage/newconnectionroutes.txt')
)
requires_data = unittest.skipUnless(HAS_DATA_FILES, 'requires txt_storage/ data files')

from HeuristicPlayer import HeuristicPlayer
from RandomPlayer import RandomPlayer
from TTR import (
    NUMCOLORS,
    breed,
    breed_cycle,
    initialize_connections_cities_board,
    initialize_decks,
    new_weights,
    output_bots,
    weight_initial_maxes,
    weight_initial_mins,
)

COLORS = list(NUMCOLORS.keys())

# 24 mid-range weights — one per heuristic dimension (a–z, skipping i)
WEIGHTS = (
    2.5, 0.075, 0.075, 1.0, 1.0, 0.5, 2.0, 0.25,
    23.0, 51.0, 0.5, 0.5, -0.5, 0.0, 0.1, 0.1, -0.4,
    1.3, 1.0, 32.0, 1.25, 1.75, 17.0, 0.65,
)

# Minimal 4-city board forming a loop: A-B-C-D-A
BOARD = {
    ('A', 'B'): (2, ['blue']),
    ('B', 'C'): (3, ['red']),
    ('A', 'D'): (4, ['gray']),
    ('C', 'D'): (2, ['green']),
}
CITIES = {'A', 'B', 'C', 'D'}
TICKETS = {('A', 'C'): 5, ('B', 'D'): 8, ('A', 'D'): 4}


def make_heuristic(color='RED'):
    return HeuristicPlayer(
        playercolor=color,
        c_deck=['blue'] * 12 + ['red'] * 12 + ['green'] * 12 + ['WILD'] * 4,
        t_deck=copy.deepcopy(TICKETS),
        colors=COLORS,
        CITIES=CITIES,
        USER_INPUT_CARDS=False,
        PRINT_THINGS=False,
        weights=WEIGHTS,
    )


def make_random(color='BLUE'):
    return RandomPlayer(
        playercolor=color,
        c_deck=['blue'] * 12 + ['red'] * 12 + ['green'] * 12 + ['WILD'] * 4,
        t_deck=copy.deepcopy(TICKETS),
        colors=COLORS,
        CITIES=CITIES,
        USER_INPUT_CARDS=False,
        PRINT_THINGS=False,
    )


# ---------------------------------------------------------------------------
# Game setup
# ---------------------------------------------------------------------------

@requires_data
class TestInitializeDecks(unittest.TestCase):
    def test_total_card_count(self):
        deck, _, face_ups, _ = initialize_decks()
        self.assertEqual(len(deck) + len(face_ups), 110)  # 12*8 + 14

    def test_five_face_ups(self):
        _, _, face_ups, _ = initialize_decks()
        self.assertEqual(len(face_ups), 5)

    def test_discard_starts_empty(self):
        _, _, _, discard = initialize_decks()
        self.assertEqual(discard, [])

    def test_ticket_deck_nonempty(self):
        _, t_deck, _, _ = initialize_decks()
        self.assertGreater(len(t_deck), 0)

    def test_color_counts(self):
        deck, _, face_ups, _ = initialize_decks()
        all_cards = deck + face_ups
        for color, expected in NUMCOLORS.items():
            self.assertEqual(all_cards.count(color), expected, f"wrong count for {color}")


@requires_data
class TestInitializeBoard(unittest.TestCase):
    def test_returns_nonempty_structures(self):
        connections, cities, board = initialize_connections_cities_board()
        self.assertGreater(len(connections), 0)
        self.assertGreater(len(cities), 0)

    def test_caching_returns_equivalent_data(self):
        c1, cities1, _ = initialize_connections_cities_board()
        c2, cities2, _ = initialize_connections_cities_board()
        self.assertEqual(set(c1.keys()), set(c2.keys()))
        self.assertEqual(cities1, cities2)

    def test_returned_board_is_independent_copy(self):
        # Mutating the returned board should not affect the internal cache
        _, _, board = initialize_connections_cities_board()
        first_key = next(iter(board))
        original_length = board[first_key][0]
        board[first_key] = (9999, ['test'])
        _, _, fresh = initialize_connections_cities_board()
        self.assertEqual(fresh[first_key][0], original_length)


# ---------------------------------------------------------------------------
# Genetic algorithm
# ---------------------------------------------------------------------------

class TestBreed(unittest.TestCase):
    def test_produces_two_children_of_correct_length(self):
        c1, c2 = breed(new_weights(), new_weights())
        self.assertEqual(len(c1), 24)
        self.assertEqual(len(c2), 24)

    def test_children_stay_within_bounds(self):
        for _ in range(30):
            c1, c2 = breed(new_weights(), new_weights())
            for i, (lo, hi) in enumerate(zip(weight_initial_mins, weight_initial_maxes)):
                self.assertGreaterEqual(c1[i], lo, f"weight {i} below min")
                self.assertLessEqual(c1[i], hi, f"weight {i} above max")
                self.assertGreaterEqual(c2[i], lo)
                self.assertLessEqual(c2[i], hi)

    def test_mutation_produces_variety(self):
        bot = new_weights()
        children = set()
        for _ in range(20):
            c1, c2 = breed(bot, bot, lr=0.5)
            children.update([c1, c2])
        self.assertGreater(len(children), 1)


class TestBreedCycle(unittest.TestCase):
    def _pop(self, n=8):
        return [[new_weights(), random.randint(10, 100)] for _ in range(n)]

    def test_output_count_matches_input(self):
        result = breed_cycle(self._pop(8))
        self.assertEqual(len(result), 8)

    def test_zero_elite_gives_equal_split(self):
        result = breed_cycle(self._pop(8), elite_pct=0.0)
        survivors = [r for r in result if not r[1]]
        children  = [r for r in result if r[1]]
        self.assertEqual(len(survivors), 4)
        self.assertEqual(len(children), 4)

    def test_elite_count(self):
        result = breed_cycle(self._pop(8), elite_pct=0.25)
        # 25% of 8 = 2 elite; the first 2 appended to results are the elite
        elite = [r for r in result if not r[1]]
        self.assertGreaterEqual(len(elite), 2)

    def test_elite_are_top_scorers(self):
        pop = [[new_weights(), i * 10] for i in range(8)]
        result = breed_cycle(pop, elite_pct=0.25)
        # Top 2 bots (indices 6, 7) must appear unchanged in results
        top_weights = {tuple(pop[6][0]), tuple(pop[7][0])}
        result_weights = {tuple(r[0]) for r in result}
        for w in top_weights:
            self.assertIn(w, result_weights)

    def test_quadratic_selection_mode_runs(self):
        result = breed_cycle(self._pop(8), selection_mode="quadratic")
        self.assertEqual(len(result), 8)


class TestOutputBots(unittest.TestCase):
    def test_roundtrip(self):
        weights = [new_weights() for _ in range(4)]
        scores  = [random.randint(20, 80) for _ in range(4)]
        data = [[list(w), s] for w, s in zip(weights, scores)]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            path = f.name
        try:
            output_bots(data, path)
            with open(path) as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(len(lines), 4)
            for line, expected_score in zip(lines, scores):
                parts = line.split('\t')
                self.assertEqual(int(parts[1]), expected_score)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Player setup
# ---------------------------------------------------------------------------

class TestGiveStartingCards(unittest.TestCase):
    def test_removes_four_from_deck(self):
        p = make_heuristic()
        deck = ['red', 'blue', 'green', 'yellow', 'red', 'blue']
        remaining = p.give_starting_cards(deck[:])
        self.assertEqual(len(remaining), 2)

    def test_adds_cards_to_hand(self):
        p = make_heuristic()
        p.give_starting_cards(['red', 'red', 'blue', 'blue', 'green'])
        self.assertEqual(p.cards['red'], 2)
        self.assertEqual(p.cards['blue'], 2)

    def test_raises_on_short_deck(self):
        p = make_heuristic()
        with self.assertRaises(ValueError):
            p.give_starting_cards(['red', 'blue', 'green'])


class TestGiveStartingTickets(unittest.TestCase):
    def test_tickets_land_in_hand(self):
        p = make_heuristic()
        t_deck = copy.deepcopy(TICKETS)
        p.give_starting_tickets(t_deck, copy.deepcopy(BOARD))
        self.assertGreater(len(p.tickets), 0)

    def test_chosen_tickets_removed_from_deck(self):
        p = make_heuristic()
        t_deck = copy.deepcopy(TICKETS)
        t_deck = p.give_starting_tickets(t_deck, copy.deepcopy(BOARD))
        for ticket in p.tickets:
            self.assertNotIn(ticket, t_deck)

    def test_raises_on_short_deck(self):
        p = make_heuristic()
        with self.assertRaises(ValueError):
            p.give_starting_tickets({('A', 'B'): 3, ('B', 'C'): 2}, copy.deepcopy(BOARD))


# ---------------------------------------------------------------------------
# Graph / connectivity
# ---------------------------------------------------------------------------

class TestHasConnection(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_same_city_is_trivially_connected(self):
        self.assertTrue(self.p.has_connection(('A', 'A'), self.board, set()))

    def test_no_trains_placed(self):
        self.assertFalse(self.p.has_connection(('A', 'B'), self.board, set()))

    def test_direct_single_hop(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.assertTrue(self.p.has_connection(('A', 'B'), self.board, set()))

    def test_multi_hop(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.board[('B', 'C')] = (3, ['red', 'RED'])
        self.assertTrue(self.p.has_connection(('A', 'C'), self.board, set()))

    def test_partial_chain_not_enough(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.assertFalse(self.p.has_connection(('A', 'C'), self.board, set()))

    def test_other_players_routes_dont_count(self):
        self.board[('A', 'B')] = (2, ['blue', 'BLUE'])
        self.assertFalse(self.p.has_connection(('A', 'B'), self.board, set()))


class TestCalcTicketPoints(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_no_tickets(self):
        self.p.tickets = {}
        self.assertEqual(self.p.calc_ticket_points(self.board), 0)

    def test_satisfied_ticket_adds_points(self):
        self.p.tickets = {('A', 'B'): 3}
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.assertEqual(self.p.calc_ticket_points(self.board), 3)
        self.assertEqual(self.p.tickets_completed, 1)

    def test_unsatisfied_ticket_subtracts_points(self):
        self.p.tickets = {('A', 'C'): 5}
        self.assertEqual(self.p.calc_ticket_points(self.board), -5)
        self.assertEqual(self.p.tickets_completed, 0)

    def test_mixed_tickets(self):
        self.p.tickets = {('A', 'B'): 3, ('A', 'C'): 5}
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.assertEqual(self.p.calc_ticket_points(self.board), 3 - 5)


class TestFindLongestRoute(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_no_trains_placed(self):
        _, length = self.p.find_longest_route(self.board)
        self.assertEqual(length, 0)

    def test_single_segment(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        _, length = self.p.find_longest_route(self.board)
        self.assertEqual(length, 2)

    def test_chain_lengths_add(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.board[('B', 'C')] = (3, ['red', 'RED'])
        _, length = self.p.find_longest_route(self.board)
        self.assertEqual(length, 5)

    def test_full_loop_traverses_all_edges(self):
        # A(2)B(3)C(2)D(4)A — claiming all four lets BFS traverse every edge once
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.board[('B', 'C')] = (3, ['red', 'RED'])
        self.board[('C', 'D')] = (2, ['green', 'RED'])
        self.board[('A', 'D')] = (4, ['gray', 'RED'])
        _, length = self.p.find_longest_route(self.board)
        self.assertEqual(length, 11)  # 2+3+2+4


class TestMinDist(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_adjacent(self):
        self.assertEqual(self.p.min_dist_between_cities(('A', 'B'), self.board), 2)

    def test_two_hops(self):
        # A→B→C = 2+3 = 5; A→D→C = 4+2 = 6; shortest is 5
        self.assertEqual(self.p.min_dist_between_cities(('A', 'C'), self.board), 5)

    def test_picks_shorter_of_two_paths(self):
        # A→D directly = 4; A→B→C→D = 2+3+2 = 7
        self.assertEqual(self.p.min_dist_between_cities(('A', 'D'), self.board), 4)


class TestDistLeftToSpan(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_unclaimed_route_costs_full_length(self):
        dist, _ = self.p.dist_left_to_span(('A', 'B'), self.board)
        self.assertEqual(dist, 2)

    def test_owned_route_costs_zero(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        dist, _ = self.p.dist_left_to_span(('A', 'B'), self.board)
        self.assertEqual(dist, 0)

    def test_partial_ownership_reduces_cost(self):
        # A→C costs 5 normally; if RED owns A→B, only B→C (3) remains
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        dist, _ = self.p.dist_left_to_span(('A', 'C'), self.board)
        self.assertEqual(dist, 3)


# ---------------------------------------------------------------------------
# Route decisions
# ---------------------------------------------------------------------------

class TestPossibleRoutes(unittest.TestCase):
    def setUp(self):
        self.board = copy.deepcopy(BOARD)

    def test_route_available_with_enough_cards(self):
        p = make_heuristic()
        p.cards['blue'] = 3
        self.assertIn(('A', 'B'), p.possible_routes(self.board))

    def test_route_blocked_without_enough_cards(self):
        p = make_heuristic()
        p.cards = {col: 0 for col in p.cards}
        self.assertNotIn(('A', 'B'), p.possible_routes(self.board))

    def test_wilds_count_toward_requirement(self):
        p = make_heuristic()
        p.cards = {col: 0 for col in p.cards}
        p.cards['blue'] = 1
        p.cards['WILD'] = 1
        self.assertIn(('A', 'B'), p.possible_routes(self.board))

    def test_already_claimed_route_excluded(self):
        p = make_heuristic()
        p.cards['blue'] = 5
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        self.assertNotIn(('A', 'B'), p.possible_routes(self.board))

    def test_gray_route_accepts_any_color(self):
        p = make_heuristic()
        p.cards = {col: 0 for col in p.cards}
        p.cards['green'] = 5
        board = {('A', 'B'): (3, ['gray'])}
        self.assertIn(('A', 'B'), p.possible_routes(board))


class TestPlayTrains(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.p.cards['blue'] = 5
        self.board = copy.deepcopy(BOARD)
        self.discard = []

    def test_player_color_written_to_board(self):
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertIn('RED', self.board[('A', 'B')][1])

    def test_cards_deducted_from_hand(self):
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertEqual(self.p.cards['blue'], 3)  # 5 - 2

    def test_trains_deducted(self):
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertEqual(self.p.num_trains, 43)  # 45 - 2

    def test_open_points_awarded(self):
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertEqual(self.p.open_points, 2)  # length-2 route = 2 pts

    def test_used_cards_go_to_discard(self):
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertEqual(self.discard.count('blue'), 2)

    def test_wilds_used_when_short_on_color(self):
        self.p.cards['blue'] = 1
        self.p.cards['WILD'] = 3
        self.p.play_trains(('A', 'B'), self.board, self.discard)
        self.assertEqual(self.p.cards['blue'], 0)
        self.assertEqual(self.p.cards['WILD'], 2)

    def test_point_scale_for_all_route_lengths(self):
        expected = {1: 1, 2: 2, 3: 4, 4: 7, 5: 10, 6: 15}
        for length, pts in expected.items():
            board = {('X', 'Y'): (length, ['blue'])}
            p = make_heuristic()
            p.cards['blue'] = length
            p.play_trains(('X', 'Y'), board, [])
            self.assertEqual(p.open_points, pts, f"wrong points for length {length}")


# ---------------------------------------------------------------------------
# Steiner tree / card estimation
# ---------------------------------------------------------------------------

class TestTotalTrainsNeeded(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)

    def test_direct_route(self):
        cost, routes = self.p.total_trains_needed_for_tickets([('A', 'B')], self.board)
        self.assertEqual(cost, 2)
        self.assertIn(('A', 'B'), routes)

    def test_indirect_route_uses_shortest_path(self):
        # A→C: A-B-C=5 beats A-D-C=6
        cost, _ = self.p.total_trains_needed_for_tickets([('A', 'C')], self.board)
        self.assertEqual(cost, 5)

    def test_already_owned_segment_costs_zero(self):
        self.board[('A', 'B')] = (2, ['blue', 'RED'])
        cost, routes = self.p.total_trains_needed_for_tickets([('A', 'B')], self.board)
        self.assertEqual(cost, 0)
        self.assertEqual(routes, [])

    def test_shared_segment_counted_once(self):
        # Tickets A-C and A-B both need A-B; together should cost 5, not 7
        cost, _ = self.p.total_trains_needed_for_tickets(
            [('A', 'C'), ('A', 'B')], self.board
        )
        self.assertEqual(cost, 5)


# ---------------------------------------------------------------------------
# Heuristic move scoring
# ---------------------------------------------------------------------------

class TestMoveQuality(unittest.TestCase):
    def setUp(self):
        self.p = make_heuristic()
        self.board = copy.deepcopy(BOARD)
        self.p.tickets = {('A', 'C'): 5}
        self.p.ticket_points = self.p.calc_ticket_points(self.board)

    def test_draw_returns_number(self):
        val = self.p.move_quality("draw", "", self.board, [self.p])
        self.assertIsInstance(val, (int, float))

    def test_tickets_returns_number(self):
        val = self.p.move_quality("tickets", "", self.board, [self.p])
        self.assertIsInstance(val, (int, float))

    def test_faceup_returns_number(self):
        val = self.p.move_quality("faceup", "blue", self.board, [self.p])
        self.assertIsInstance(val, (int, float))

    def test_play_returns_number(self):
        self.p.cards['blue'] = 3
        val = self.p.move_quality("play", "A-B", self.board, [self.p])
        self.assertIsInstance(val, (int, float))

    def test_invalid_move_type_raises(self):
        with self.assertRaises(Exception):
            self.p.move_quality("invalid", "", self.board, [self.p])

    def test_play_toward_ticket_increases_value(self):
        # Playing A-B (first leg toward A-C) should score higher than playing
        # a route in the opposite direction (C-D, which doesn't help A-C)
        self.p.cards['blue'] = 3
        self.p.cards['green'] = 3
        val_toward = self.p.move_quality("play", "A-B", self.board, [self.p])
        val_away   = self.p.move_quality("play", "C-D", self.board, [self.p])
        self.assertGreater(val_toward, val_away)


# ---------------------------------------------------------------------------
# RandomPlayer smoke tests
# ---------------------------------------------------------------------------

class TestRandomPlayer(unittest.TestCase):
    def setUp(self):
        self.p = make_random()
        self.board = copy.deepcopy(BOARD)

    def test_give_starting_cards(self):
        deck = ['red', 'blue', 'green', 'yellow', 'red']
        remaining = self.p.give_starting_cards(deck[:])
        self.assertEqual(len(remaining), 1)
        self.assertEqual(self.p.cards['red'], 1)
        self.assertEqual(self.p.cards['blue'], 1)

    def test_play_trains_updates_board_and_counts(self):
        self.p.cards['blue'] = 5
        self.p.play_trains(('A', 'B'), self.board, [])
        self.assertIn('BLUE', self.board[('A', 'B')][1])
        self.assertEqual(self.p.num_trains, 43)
        self.assertEqual(self.p.open_points, 2)

    def test_has_connection(self):
        self.assertFalse(self.p.has_connection(('A', 'C'), self.board, set()))
        self.board[('A', 'B')] = (2, ['blue', 'BLUE'])
        self.board[('B', 'C')] = (3, ['red', 'BLUE'])
        self.assertTrue(self.p.has_connection(('A', 'C'), self.board, set()))

    def test_calc_ticket_points(self):
        self.p.tickets = {('A', 'B'): 4}
        self.board[('A', 'B')] = (2, ['blue', 'BLUE'])
        self.assertEqual(self.p.calc_ticket_points(self.board), 4)


if __name__ == '__main__':
    unittest.main()
