#!/usr/bin/python

import unittest
import codecs

from keys import *
import dominioncards
import game
import parse_game


def get_test_game(game_id):
    """Return the parsed Game for the passed game id"""
    return game.Game(parse_game.parse_game( \
            codecs.open('testing/testdata/'+game_id, encoding='utf-8').read()))


class ScoreDeckTest(unittest.TestCase):
    def test_gardens(self):
        self.assertEquals(game.score_deck({dominioncards.Gardens: 1, dominioncards.Copper: 9}), 1)
        self.assertEquals(game.score_deck({dominioncards.Gardens: 2, dominioncards.Copper: 8}), 2)
        self.assertEquals(game.score_deck({dominioncards.Gardens: 2, dominioncards.Copper: 7}), 0)

    def test_feodum(self):
        self.assertEquals(game.score_deck({dominioncards.Feodum: 1, dominioncards.Silver: 9}), 3)
        self.assertEquals(game.score_deck({dominioncards.Feodum: 2, dominioncards.Silver: 8}), 4)
        self.assertEquals(game.score_deck({dominioncards.Feodum: 2, dominioncards.Silver: 2}), 0)

    def test_fairgrounds(self):
        self.assertEquals(game.score_deck({dominioncards.Fairgrounds: 1,
                                           dominioncards.Copper: 1,
                                           dominioncards.Silver: 1,
                                           dominioncards.Gold: 1,
                                           dominioncards.Bank: 1}), 2)

    def test_duke(self):
        self.assertEquals(game.score_deck({dominioncards.Duke: 2, dominioncards.Duchy: 2}), 10)


    def test_simple(self):
        self.assertEquals(game.score_deck({
                    dominioncards.Curse: 1, dominioncards.Estate: 1, dominioncards.Duchy: 1,
                    dominioncards.Province: 1, dominioncards.Colony: 1}), 19)

    def test_vineyards(self):
        self.assertEquals(game.score_deck({dominioncards.Vineyard: 2, dominioncards.Jester: 3,
                                           dominioncards.FishingVillage: 3}), 4)

def make_deck(name, points, win_points, order):
    return {NAME: name, POINTS: points, WIN_POINTS: win_points,
            DECK: {}, ORDER: order, TURNS: [],}

class WinLossTieTest(unittest.TestCase):
    def test_win_loss_tie_3p(self):
        g = game.Game(
            {DECKS: [make_deck('p1', 1, 1.5, 1),
                     make_deck('p2', 1, 1.5, 2),
                     make_deck('p3', 0, 0, 3),],
             SUPPLY: [], '_id': ''})
        self.assertEquals(game.TIE, g.win_loss_tie('p1', 'p2'))
        self.assertEquals(game.TIE, g.win_loss_tie('p2', 'p1'))
        self.assertEquals(game.WIN, g.win_loss_tie('p1', 'p3'))
        self.assertEquals(game.LOSS, g.win_loss_tie('p3', 'p1'))

class GameStateTest(unittest.TestCase):
    outpost_game = get_test_game('game-20101015-094051-95e0a59e.html')

    def _get_turn_labels(self, game_state_it):
        return [game_state_it.turn_label() for t in game_state_it]

    def test_turn_labels(self):
        # 'game-20101015-094051-95e0a59e.html' contains Outpost card
        turn_labels = self._get_turn_labels(self.outpost_game.game_state_iterator())
        for game_state in self.outpost_game.game_state_iterator():
            pass

    def test_score(self):
        self.assertEquals(game.score_deck(self.outpost_game.get_player_deck('moop').deck),
                          42)
        self.assertEquals(game.score_deck(self.outpost_game.get_player_deck('qzhdad').deck),
                          30)


class GokoGameTest(unittest.TestCase):

    def test_masq_game(self):
        g = get_test_game('log.50bbfdf8e4b07d338bca0e67.1364827084306.txt')
        self.assertEquals(['Kerry Monroe', 'Warlord Bot', 'Conqueror Bot', 'Villager Bot'], g.all_player_names())

        accum_results = g.cards_gained_per_player()
        player_bought = accum_results[game.BOUGHT][u'Kerry Monroe']
        self.assertEquals(player_bought[dominioncards.Library], 1)
        self.assertEquals(player_bought[dominioncards.Gold], 8)
        self.assertEquals(player_bought[dominioncards.Masquerade], 1)
        self.assertEquals(player_bought[dominioncards.TradeRoute], 1)
        self.assertEquals(player_bought[dominioncards.HuntingParty], 2)
        self.assertEquals(player_bought[dominioncards.Province], 5)
        self.assertEquals(player_bought[dominioncards.Duchy], 3)
        self.assertEquals(player_bought[dominioncards.Estate], 1)

        player_received = accum_results[game.GAINED][u'Kerry Monroe']
        self.assertEquals(player_received[dominioncards.Copper], 10)
        self.assertEquals(player_received[dominioncards.Fortress], 3)
        self.assertEquals(player_received[dominioncards.Masquerade], 2)
        self.assertEquals(player_received[dominioncards.Silver], 1)

        last_state = None
        game_state_iterator = g.game_state_iterator()
        for game_state in game_state_iterator:
            last_state = game_state
        for player_deck in g.get_player_decks():

            parsed_deck_comp = player_deck.Deck()
            computed_deck_comp = last_state.get_deck_composition(
                player_deck.name())

            for card in set(parsed_deck_comp.keys() +
                            computed_deck_comp.keys()):
                self.longMessage = True
                self.assertEqual(parsed_deck_comp.get(card, 0), computed_deck_comp.get(card, 0), card)


    def test_ruins_game(self):
        g = get_test_game('log.50612a9b51c36e573294bfd0.1368579645597.txt')
        last_state = None
        game_state_iterator = g.game_state_iterator()
        for game_state in game_state_iterator:
            last_state = game_state
        for player_deck in g.get_player_decks():

            parsed_deck_comp = player_deck.Deck()
            computed_deck_comp = last_state.get_deck_composition(
                player_deck.name())

            for card in set(parsed_deck_comp.keys() +
                            computed_deck_comp.keys()):
                self.longMessage = True
                self.assertEqual(parsed_deck_comp.get(card, 0), computed_deck_comp.get(card, 0), card)

    def test_goko_unknown_error(self):
        g = get_test_game('log.50bbfdf8e4b07d338bca0e67.1366508665569.txt')
        last_state = None
        game_state_iterator = g.game_state_iterator()
        for game_state in game_state_iterator:
            last_state = game_state
        for player_deck in g.get_player_decks():

            parsed_deck_comp = player_deck.Deck()
            computed_deck_comp = last_state.get_deck_composition(
                player_deck.name())

            for card in set(parsed_deck_comp.keys() +
                            computed_deck_comp.keys()):
                self.longMessage = True
                self.assertEqual(parsed_deck_comp.get(card, 0), computed_deck_comp.get(card, 0), card)




class PlayerDeckTest(unittest.TestCase):

    outpost_game = get_test_game('game-20101015-094051-95e0a59e.html')
    deck_changes_game = get_test_game('game-20101015-024842-a866e78a.html')
    accum_game = get_test_game('game-20130111-164348-84fd128e.html')
    accum2_game = get_test_game('game-20121201-103128-e6e30146.html')

    def test_deck_composition(self):
        last_state = None
        game_state_iterator = self.outpost_game.game_state_iterator()
        for game_state in game_state_iterator:
            last_state = game_state
        for player_deck in self.outpost_game.get_player_decks():

            parsed_deck_comp = player_deck.Deck()
            computed_deck_comp = last_state.get_deck_composition(
                player_deck.name())

            for card in set(parsed_deck_comp.keys() +
                            computed_deck_comp.keys()):
                self.longMessage = True
                self.assertEqual(parsed_deck_comp.get(card, 0), computed_deck_comp.get(card, 0), card)

    def test_deck_changes_per_player(self):
        self.assertEquals(['Celicath', 'tafkal'], self.deck_changes_game.all_player_names())

        pd = self.deck_changes_game.get_player_decks()[0]
        self.assertEquals('Celicath', pd.name())
        pd = self.deck_changes_game.get_player_decks()[1]
        self.assertEquals('tafkal', pd.name())

        for changes in self.deck_changes_game.deck_changes_per_player():
            win_points = self.deck_changes_game.get_player_deck(changes.name).WinPoints()

    def test_card_accum_by_self(self):
        accum_results = self.accum_game.cards_gained_per_player()
        player_bought = accum_results[game.BOUGHT][u'Wolphmaniac']
        player_gained = accum_results[game.GAINED][u'Wolphmaniac']
        self.assertEquals(player_bought[dominioncards.Spy], 10)
        self.assertEquals(player_gained[dominioncards.Spy], 10)
        self.assertEquals(player_bought[dominioncards.Curse], 10)
        self.assertEquals(player_bought[dominioncards.Goons], 7)
        self.assertEquals(player_bought[dominioncards.City], 7)
        self.assertEquals(player_bought[dominioncards.Quarry], 3)

    def test_card_accum_by_any(self):
        """Confirms the difference between buying and being given cards"""
        accum_results = self.accum2_game.cards_gained_per_player()
        player_bought = accum_results[game.BOUGHT][u'Varsinor']
        player_gained = accum_results[game.GAINED][u'Varsinor']
        self.assertEquals(player_bought[dominioncards.Curse], 0)
        self.assertEquals(player_gained[dominioncards.Curse], 10)


class ParsedGameStructureTest(unittest.TestCase):
    """ Test cases for game structures.
    """

    def test_game_with_dots_in_player_name(self):
        """ Test vetoes with names containing dots.
        """

        test_game = get_test_game('game-20120415-072057-6d356cf1.html')
        last_state = None
        game_state_iterator = test_game.game_state_iterator()
        for game_state in game_state_iterator:
            last_state = game_state
        self.assertEquals(test_game.vetoes[str(test_game.all_player_names().index(u'nrggirl'))],
                          int(dominioncards.PirateShip.index))
        self.assertEquals(test_game.vetoes[str(test_game.all_player_names().index(u'Mr.Penskee'))],
                          int(dominioncards.Masquerade.index))


class GameStateTest(unittest.TestCase):
    def test_encode_game_state(self):
        game_val = get_test_game('game-20120415-072057-6d356cf1.html')

        states = []
        for idx, game_state in enumerate(game_val.game_state_iterator()):
            encoded = game_state.encode_game_state()
            states.append(encoded)

        self.assertEquals(states[0]['money'], 4)
        self.assertEquals(states[1]['money'], 4)
        self.assertEquals(states[4]['money'], 4)
        self.assertEquals(states[5]['money'], 5)
        self.assertEquals(states[17]['money'], 3)
        self.assertEquals(states[18]['money'], 7)


if __name__ == '__main__':
    unittest.main()
