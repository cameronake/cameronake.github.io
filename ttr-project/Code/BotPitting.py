from RandomPlayer import RandomPlayer
from HeuristicPlayer import HeuristicPlayer
from TTR import *

if __name__ == '__main__':

    # for quadratic-weighting chain
    # open file of weights and scores and make them into the list
    with open("quadratic-40-bot-chain-05-09/05-09-bot-test-stage_FINAL.txt") as f:
        weights_scores = []
        for line in f:
            full_list = line.split("\t")
            weights_list = full_list[0].split(", ")
            weights_list[0] = weights_list[0][1:]

            # score is first number after the tab
            score = int(full_list[1])
            weights_list[-1] = weights_list[-1][:weights_list[-1].index("]")]
            weights_list = tuple([float(weight) for weight in weights_list])
            weights_scores.append([weights_list, score])
    quad_weights_scores_list = weights_scores

    # for linear-weighting chain
    # open file of weights and scores and make them into the list
    with open("linear-40-bot-chain-05-09/05-09-bot-test-stage_FINAL.txt") as g:
        weights_scores = []
        for line in g:
            full_list = line.split("\t")
            weights_list = full_list[0].split(", ")
            weights_list[0] = weights_list[0][1:]

            # score is first number after the tab
            score = int(full_list[1])
            weights_list[-1] = weights_list[-1][:weights_list[-1].index("]")]
            weights_list = tuple([float(weight) for weight in weights_list])
            weights_scores.append([weights_list, score])
    line_weights_scores_list = weights_scores

    # run a series of games, where pairs of bots from the quadratic weighting are pitted against pairs of bots from the linear weighting
    while len(quad_weights_scores_list) > 0:
        bot1_weights, bot2_weights = quad_weights_scores_list[0][0], quad_weights_scores_list[1][0]
        bot3_weights, bot4_weights = line_weights_scores_list[0][0], line_weights_scores_list[1][0]
        quad_weights_scores_list = quad_weights_scores_list[2:]
        line_weights_scores_list = line_weights_scores_list[2:]

        # set up game values
        card_deck, ticket_deck, face_up_cards, discard_pile = initialize_decks()
        CONNECTIONS, CITIES, board = initialize_connections_cities_board()

        # bots RED and YELLOW correspond to quadratic updating
        RedBot = HeuristicPlayer(playercolor='RED', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                            weights=bot1_weights)
        YellowBot = HeuristicPlayer(playercolor='YELLOW', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                            weights=bot2_weights)
        
        # bots GREEN and BLUE correspond to linear updating
        GreenBot = HeuristicPlayer(playercolor='GREEN', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                            weights=bot3_weights)
        BlueBot = HeuristicPlayer(playercolor='BLUE', c_deck=card_deck, t_deck=ticket_deck, colors=NUMCOLORS.keys(), CITIES=CITIES, USER_INPUT_CARDS=USER_INPUT_CARDS, PRINT_THINGS=PRINT_THINGS,
                            weights=bot4_weights)
        game_bots = [YellowBot, GreenBot, RedBot, BlueBot]

        # output: [[winner's_weights, winner's_score, winner_longest_route, winner_tickets], [second's_weights, second's_score, winner_longest_route, winner_tickets], ...]
        # bots_play_game will output to terminal using form below
        '''
        Beginning game

        Bot [COLOR] got [score] points
                [ticket information: which tickets and how many points were they?]
                [longest route: true or false?]
                        [ticket information: satisfied or no?]
        Bot [COLOR] got [score] points
                [ticket information: which tickets and how many points were they?]
                [longest route: true or false?]
                        [ticket information: satisfied or no?]
        Bot [COLOR] got [score] points
                [ticket information: which tickets and how many points were they?]
                [longest route: true or false?]
                        [ticket information: satisfied or no?]
        Bot [COLOR] got [score] points
                [ticket information: which tickets and how many points were they?]
                [longest route: true or false?]
                        [ticket information: satisfied or no?]
        '''
        weights_scores = bots_play_game(bots=game_bots, 
                                            c_deck=card_deck, 
                                            face_ups=face_up_cards, 
                                            t_deck=ticket_deck, 
                                            board=board, 
                                            discard=discard_pile, 
                                            players=copy.deepcopy(game_bots))

    