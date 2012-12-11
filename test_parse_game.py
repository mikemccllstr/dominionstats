#!/usr/bin/python
# -*- coding: utf-8 -*-
try:
    import unittest2 as unittest
except ImportError, e:
    import unittest
import parse_game
import pprint
from keys import *
import dominioncards
import codecs

DEF_NAME_LIST = ['p' + str(x) for x in range(15)]

def assert_equal_card_lists(indexes, names, msg=None):
    list1 = [dominioncards.index_to_card(i) for i in indexes]
    assert_equal_indexed_lists(list1, names, msg)

def assert_equal_indexed_lists(list1, names, msg=None):
    list2 = [dominioncards.get_card(n) for n in names]
    if list1==list2:
        return
    elif msg is None:
        raise AssertionError(repr(list1)+' != '+repr(list2))
    else:
        raise AssertionError(msg)

def assert_equal_card_dicts(indexes, names, msg=None):
    dict1 = {}
    dict2 = {}
    for i,c in indexes.iteritems():
        dict1[dominioncards.index_to_card(int(i))] = c
    for n,c in names.iteritems():
        dict2[dominioncards.get_card(n)] = c
    if dict1==dict2:
        return
    elif msg is None:
        raise AssertionError(repr(dict1)+' != '+repr(dict2))
    else:
        raise AssertionError(msg)

class CaptureCardsTest(unittest.TestCase):
    def test_capture_cards(self):
        captured = parse_game.capture_cards(
            'player0 plays 3 <span class=card-treasure>Coppers</span>.')
        assert_equal_indexed_lists(captured, ['Copper'] * 3)

        captured = parse_game.capture_cards(
            '... ... and plays the <span class=card-none>Throne Room</span> '
            'again.')
        assert_equal_indexed_lists(captured, ['Throne Room'])

        captured = parse_game.capture_cards(
            '... player0 gains the '
            '<span class=card-reaction>Watchtower</span>.')
        assert_equal_indexed_lists(captured, ['Watchtower'])

        captured = parse_game.capture_cards(
            '... player1 gains a <span class=card-treasure>Copper</span> '
            'and a <span class=card-curse>Curse</span>')
        assert_equal_indexed_lists(captured, ['Copper', 'Curse'])

        captured = parse_game.capture_cards(
            'player1 plays a <span class=card-treasure>Platinum</span>, '
            '3 <span class=card-treasure>Golds</span>, and a '
            '<span class=card-treasure>Copper</span>.')
        assert_equal_indexed_lists(captured, ['Platinum', 'Gold', 'Gold', 'Gold',
                                     'Copper'])

        captured = parse_game.capture_cards(
            'cards in supply: <span cardname="Black Market" '
            'class=card-none>Black Market</span>, '
            '<span cardname="Caravan" class=card-duration>Caravan</span>')
        assert_equal_indexed_lists(captured, ['Black Market', 'Caravan'])

        captured = parse_game.capture_cards(
            'player0 plays a <span class=card-none>Coppersmith</span>.')
        assert_equal_indexed_lists(captured, ['Coppersmith'])

        captured = parse_game.capture_cards(
            'player4 buys an <span class=card-none>Expand</span>')
        assert_equal_indexed_lists(captured, ['Expand'])

    def test_bane(self):
        captured = parse_game.capture_cards(
            '<span cardname="Chapel" class=card-none>Chapel</span>, <span cardname="Moat" class=card-reaction>Moat</span><span class=bane-star>&diams;</span>,')
        assert_equal_indexed_lists(captured, ['Chapel', 'Moat'])

class DeleteKeysTest(unittest.TestCase):
    def test_delete_keys_with_empty_vals(self):
        d1 = {'p6': {}}
        parse_game.delete_keys_with_empty_vals(d1)
        self.assertEquals(d1, {})

    def test_ultimately_empty_nested_dict(self):
        d2 = {1: {OPP: {}}}
        parse_game.delete_keys_with_empty_vals(d2)
        self.assertEquals(d2, {})

class PlayerTrackerTest(unittest.TestCase):
    def setUp(self):
        self.tracker = parse_game.PlayerTracker()

    def test_simple_tracking(self):
        self.assertEquals(0, self.tracker.get_active_player(
                'player0 plays 3 <span class=card-treasure>Coppers</span>.'))

        self.assertEquals(self.tracker.current_player(), 0)

        self.assertEquals(0, self.tracker.get_active_player(
                'player0 buys a <span class=card-treasure>Silver</span>.'))

    def test_complicated_tracking(self):
        line_output_list = [
            ('player1 plays a <span class=card-none>Throne Room</span>.', 1),
            ('... and plays a <span class=card-none>Bureaucrat</span>.,', 1),
            ('... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.', 1),
            ('... ... player2 puts an <span class=card-victory>Estate</span> back on the deck.', 2),
            ('... and plays the <span class=card-none>Bureaucrat</span> again.', 1),
            ('... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.', 1),
            ('... ... player2 reveals 4 <span class=card-treasure>Golds</span>.', 2)]
        for line, expected_output in line_output_list:
            self.assertEquals(self.tracker.get_active_player(line),
                              expected_output, line)
        self.assertEquals(self.tracker.current_player(), 1)

class ParseTurnHeaderTest(unittest.TestCase):
    def test_normal_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "--- player0's turn 3 ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['turn_no'], 3)

    def test_possesion_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "--- player0's turn (possessed by player1) ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['pname'], 'p1')

    def test_outpost_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            """--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---""", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['outpost'], True)

    def test_header_with_leading_space(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "   --- player0's turn 3 ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['turn_no'], 3)

class ParseTurnTest(unittest.TestCase):
    def test_parse_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player0's turn 3 ---
   player0 plays 3 <span class=card-treasure>Coppers</span>.
   player0 buys a <span class=card-treasure>Silver</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p0')
        assert_equal_card_lists(turn_info[PLAYS], ['Copper', 'Copper', 'Copper'])
        assert_equal_card_lists(turn_info[BUYS], ['Silver'])
        self.assertEquals(turn_info[MONEY], 3)

    def test_chapel_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player5's turn 4 ---
player5 plays a <span class=card-none>Chapel</span>.
... trashing 2 <span class=card-treasure>Coppers</span>.
(player5 reshuffles.)""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[PLAYS], ['Chapel'])
        assert_equal_card_lists(turn_info[TRASHES], ['Copper', 'Copper'])
        self.assertTrue(OPP not in turn_info)

    def test_bishop_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player2's turn 7 ---
player2 plays a <span class=card-none>Bishop</span>.
... getting +$1 and +1 ▼.
... player2 trashes a <span class=card-treasure>Copper</span>.
... player3 trashes a <span class=card-treasure>Copper</span>.
player2 plays 3 <span class=card-treasure>Coppers</span>.
player2 buys a <span class=card-treasure>Silver</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[PLAYS], ['Bishop', 'Copper',
                                               'Copper', 'Copper'])
        assert_equal_card_lists(turn_info[TRASHES], ['Copper'])
        self.assertEquals(turn_info[VP_TOKENS], 1)
        self.assertEquals(turn_info[MONEY], 4)

    def test_bishop_turn2(self):
        turn_info = parse_game.parse_turn(
u"""--- player3's turn 3 ---
 player3 plays a <span class=card-none>Bishop</span>.
 ... getting +$1 and +1 ▼.
 ... player3 trashes an <span class=card-victory>Estate</span> and gets +1 ▼.
 ... player6 trashes nothing.
 player3 plays 3 <span class=card-treasure>Coppers</span>.
 player3 buys a <span class=card-none>Throne Room</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[TRASHES], ['Estate'])
        self.assertTrue(OPP not in turn_info)
        self.assertEquals(turn_info[VP_TOKENS], 2)
        self.assertEquals(turn_info[MONEY], 4)

    def test_bishop_turn3(self):
        turn_info = parse_game.parse_turn(
u"""   --- player6's turn 4 ---
    player6 plays a <span class=card-none>Bishop</span>.
    ... getting +$1 and +1 ▼.
    ... player6 trashes an <span class=card-victory>Estate</span> and gets +1 ▼.
    ... player3 trashes a <span class=card-treasure>Copper</span>.""",
DEF_NAME_LIST)
        self.assertEquals(turn_info[VP_TOKENS], 2)
        assert_equal_card_lists(turn_info[TRASHES], ['Estate'])
        assert_equal_card_lists(turn_info[OPP]['3'][TRASHES], ['Copper'])
        self.assertEquals(turn_info[MONEY], 1)

    def test_trader_gain_silver_instead_of_buy(self):
        turn_info = parse_game.parse_turn(
u"""--- player1's turn 8 ---
   player1 plays a <span class=card-duration>Lighthouse</span>.
   ... getting +1 action and +$1.
   player1 plays 3 <span class=card-treasure>Coppers</span>.
   player1 buys a <span class=card-victory>Gardens</span>.
   ... player1 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
   ... player1 gains a <span class=card-treasure>Silver</span>.,.
""",
DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Silver'])
        self.assertFalse(BUYS in turn_info, 'should not be here: ' + 
                         str(turn_info.get(BUYS, [])))

    def test_trader_gain_silver_instead_of_gain(self):
        turn_info = parse_game.parse_turn(
u"""--- player1's turn 11 ---</a> 
   player1 plays a <span class=card-none>Torturer</span>.
   ... drawing 3 cards.
   ... player2 gains a <span class=card-curse>Curse</span> in hand.
   ... ... player2 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
   ... ... player2 gains a <span class=card-treasure>Silver</span>.
   player1 plays 2 <span class=card-treasure>Silvers</span> and a <span class=card-treasure>Copper</span>.
   player1 buys an <span class=card-none>Upgrade</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][GAINS], ['Silver'])

    def test_mine_upgrade_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player3's turn 12 ---
player3 plays a <span class=card-none>Mine</span>.
... trashing a <span class=card-treasure>Talisman</span> and gaining a <span class=card-treasure>Gold</span>.
player3 plays a <span class=card-treasure>Gold</span>, a <span class=card-treasure>Royal Seal</span>, and a <span class=card-treasure>Copper</span>.
player3 buys a <span class=card-treasure>Gold</span>.
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Gold'])
        assert_equal_card_lists(turn_info[BUYS], ['Gold'])
        assert_equal_card_lists(turn_info[TRASHES], ['Talisman'])
        self.assertEquals(turn_info[MONEY], 6)

    def test_ambassador_turn(self):
        turn_info = parse_game.parse_turn(
u"""        --- player8's turn 3 ---
player8 plays an <span class=card-none>Ambassador</span>.
... player8 reveals an <span class=card-victory>Estate</span>.
... returning 2 copies to the supply.
... player9 gains an <span class=card-victory>Estate</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p8')
        assert_equal_card_lists(turn_info[PLAYS], ['Ambassador'])
        assert_equal_card_lists(turn_info[RETURNS], ['Estate', 'Estate'])
        assert_equal_card_lists(turn_info[OPP]['9'][GAINS],
                          ['Estate'])

    def test_ambassador_secret_chamber_response_turn(self):
        input_str = u"""   --- player0's turn 16 ---
   player0 plays an <span class=card-none>Ambassador</span>.
   ... player1 reveals a <span class=card-reaction>Secret Chamber</span>.
   ... ... drawing 2 cards.
   ... ... returning 2 cards to the deck.
   ... player0 reveals a <span class=card-treasure>Copper</span>.
   ... returning 2 copies to the supply.
   ... player1 gains a <span class=card-treasure>Copper</span>."""
        turn_info = parse_game.parse_turn(input_str, DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p0')
        assert_equal_card_lists(turn_info[PLAYS], ['Ambassador'])
        assert_equal_card_lists(turn_info[RETURNS], ['Copper', 'Copper'])
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Copper'])

    def test_ambassador3(self):
        turn_info = parse_game.parse_turn(
"""   --- player0's turn 6 ---
   player0 plays an <span class=card-none>Ambassador</span>.
   ... player0 reveals a <span class=card-treasure>Copper</span>.
   ... returning it to the supply.
   ... player1 gains a <span class=card-treasure>Copper</span>.""", 
['f', 't'])
        assert_equal_card_lists(turn_info[RETURNS], ['Copper'])
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Copper'])

    def test_ambassador4(self):
        turn_info = parse_game.parse_turn(
"""--- player0's turn 4 ---
player0 plays an <span class=card-none>Ambassador</span>.
... revealing 2 <span class=card-treasure>Coppers</span> and returning them to the supply.
... player1 gains a <span class=card-treasure>Copper</span>.
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[RETURNS], ['Copper', 'Copper'])

    def test_ambassador5(self):
        turn_info = parse_game.parse_turn("""--- player3's turn 8 ---
player3 plays a <span class=card-none>Worker's Village</span>.
... drawing 1 card and getting +2 actions and +1 buy.
player3 plays an <span class=card-none>Ambassador</span>.
... revealing a <span class=card-treasure>Copper</span> and returning it to the supply.
... player0 gains a <span class=card-treasure>Copper</span>.
player3 plays an <span class=card-none>Ambassador</span>.
... revealing nothing and returning them to the supply.
... player0 gains a <span class=card-treasure>Copper</span>.
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[RETURNS], ['Copper'])
        assert_equal_card_lists(turn_info[OPP]['0'][GAINS], 
                          ['Copper', 'Copper'])

    def test_ambassador6(self):
        turn_info = parse_game.parse_turn("""--- player0's turn 8 ---
 player0 plays a <span class=card-none>Scout</span>.
 ... player0 reveals a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-none>Spy</span>.
 ... putting nothing into the hand.
 ... putting 4 cards back on the deck.
 player0 plays an <span class=card-none>Ambassador</span>.
 ... revealing an <span class=card-victory>Estate</span> and returning it to the supply.
 ... player1 gains an <span class=card-victory>Estate</span>.
 """, ['foo', 'bar'])
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Estate'])

    def test_ambassador_moat(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
player0 plays an <span class=card-none>Ambassador</span>.
... player1 reveals a <span class=card-reaction>Moat</span>.
... revealing 2 <span class=card-victory>Estates</span> and returning them to the supply.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[RETURNS], ['Estate', 'Estate'])


    def test_swindler_watchtower(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 8 ---</a> 
   player0 plays a <span class=card-none>Swindler</span>.
   ... player1 turns up a <span class=card-none>Steward</span> and trashes it.
   ... replacing player1's <span class=card-none>Steward</span> with a <span class=card-reaction>Watchtower</span>.
   ... ... revealing a <span class=card-reaction>Watchtower</span>.
   ... ... trashing the <span class=card-reaction>Watchtower</span>.""",
                                          DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Watchtower'])
        assert_equal_card_lists(turn_info[OPP]['1'][TRASHES], 
                          ['Steward', 'Watchtower'])

    def test_trading_post_turn(self):
        turn_info = parse_game.parse_turn(
"""--- player1's turn 11 ---
player1 plays a <span class=card-none>Trading Post</span>.
      ... player1 trashes a <span class=card-treasure>Copper</span> and an <span class=card-victory>Estate</span>, gaining a <span class=card-treasure>Silver</span> in hand.
      player1 plays a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Silver</span>.
      player1 buys a <span class=card-treasure>Silver</span>.
      (player1 reshuffles.)
      <span class=logonly>(player1 draws: 2 <span class=card-curse>Curses</span>, a <span class=card-treasure>Copper</span>, a <span class=card-none>Trading Post</span>, and a <span class=card-none>Laboratory</span>.)</span>""", 
DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[TRASHES], ['Copper', 'Estate'])
        assert_equal_card_lists(turn_info[GAINS], ['Silver'])
        self.assertEquals(turn_info[MONEY], 3)

    def test_sea_hag_turn(self):
        turn_info = parse_game.parse_turn(
"""--- player0's turn 14 ---
    player0 plays a <span class=card-none>Sea Hag</span>.
    ... player1 discards a <span class=card-none>Courtyard</span> and gains a <span class=card-curse>Curse</span> on top of the deck.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Curse'])

    def test_sea_hag_turn2(self):
        turn_info = parse_game.parse_turn("""
  --- player0's turn 6 ---
    player0 plays a <span class=card-none>Sea Hag</span>.
    ... player1 discards nothing and gains a <span class=card-curse>Curse</span> on top of the deck.
    player0 plays a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Quarry</span>.
    player0 buys a <span class=card-none>Cutpurse</span>.
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Curse'])
        self.assertEquals(turn_info[MONEY], 2)

    def test_pirate_ship_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player8's turn 7 ---
player8 plays a <span class=card-none>Pirate Ship</span>.
... attacking the other players.
... (player11 reshuffles.)
... player11 reveals a <span class=card-duration>Wharf</span> and a <span class=card
-treasure>Copper</span>.
... player8 trashes player11's <span class=card-treasure>Copper</span>.
... player8 gains a <span class=card-none>Pirate Ship</span> token.
player8 plays 2 <span class=card-treasure>Coppers</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p8')
        self.assertTrue(GAINS not in turn_info)
        self.assertEquals(turn_info[MONEY], 2)
        self.assertTrue(OPP in turn_info, turn_info)
        assert_equal_card_lists(turn_info[OPP]['11'][TRASHES], ['Copper'])
        self.assertTrue(TRASHES not in turn_info)
        self.assertEquals(turn_info[PIRATE_TOKENS], 1)

    def test_noble_brigand_trash(self):
        turn_info = parse_game.parse_turn(
"""--- player1's turn 10 ---
   player1 plays a <span class=card-none>Noble Brigand</span>.
   ... getting +$1.
   ... player2 draws and reveals a <span class=card-none>Ghost Ship</span> and a <span class=card-treasure>Silver</span>, trashing a <span class=card-treasure>Silver</span>.
   ... player2 discards a <span class=card-none>Ghost Ship</span>.
   ... player1 gains the <span class=card-treasure>Silver</span>.""", 
DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][TRASHES], ['Silver'])

    def test_noble_brigand_3_p_trash(self):
        turn_info = parse_game.parse_turn(
"""--- player1's turn 9 ---
      player1 plays a <span class=card-none>Noble Brigand</span>.
      ... getting +$1.
      ... player2 reveals and discards a <span class=card-treasure>Copper</span> and a <span class=card-none>Warehouse</span>.
      ... player3 draws and reveals a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Gold</span>, trashing a <span class=card-treasure>Gold</span>.
      ... player3 discards a <span class=card-treasure>Copper</span>.
      ... player1 gains the <span class=card-treasure>Gold</span>.""",
DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['3'][TRASHES], ['Gold'])

    def test_noble_brigand_talisman(self):
        turn_info = parse_game.parse_turn(
"""--- player1's turn 15 ---
player1 plays an <span class=card-none>Alchemist</span>.
... drawing 2 cards and getting +1 action.
player1 plays a <span class=card-none>Workshop</span>.
... gaining a <span class=card-treasure>Talisman</span>.
player1 plays 3 <span class=card-treasure>Coppers</span> and a <span class=card-treasure>Talisman</span>.
player1 buys a <span class=card-none>Noble Brigand</span>.
... player2 reveals and discards a <span class=card-treasure>Copper</span> and a <span class=card-none>Hunting Party</span>.
... gaining another <span class=card-none>Noble Brigand</span>.
<span class=logonly>(player1 draws: an <span class=card-victory>Estate</span>, a <span class=card-none>Scrying Pool</span>, a <span class=card-treasure>Potion</
span>, an <span class=card-none>Alchemist</span>, and a <span class=card-treasure>Silver</span>.)</span>
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Talisman', 'Noble Brigand'])
        


    def test_bank_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player2's turn 10 ---
player2 plays a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-treasure>Gold</span>.
player2 plays a <span class=card-treasure>Bank</span>.
... which is worth +$5.
player2 buys a <span class=card-victory>Province</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[MONEY], 12)

    def test_philospher_stone_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player4's turn 15 ---
player4 plays a <span class=card-none>Laboratory</span>.
... drawing 2 cards and getting +1 action.
player4 plays a <span class=card-none>Laboratory</span>.
... drawing 2 cards and getting +1 action.
player4 plays a <span class=card-none>University</span>.
... getting +2 actions.
... gaining a <span class=card-none>Laboratory</span>.
player4 plays an <span class=card-none>Herbalist</span>.
... getting +1 buy and +$1.
player4 plays a <span class=card-treasure>Silver</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Philosopher's Stone</span>.
... which is worth +$4 (6 cards in deck, 17 cards in discard).
player4 buys a <span class=card-none>Laboratory</span>.
player4 buys a <span class=card-none>Minion</span>.
player4 returns a <span class=card-treasure>Philosopher's Stone</span> to the top of the deck.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[MONEY], 10)

    def test_gain_via_workshop_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn 4 ---
player0 plays a <span class=card-none>Workshop</span>.
... gaining a <span class=card-none>Bridge</span>.
player0 plays 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-none>Pawn</span>.
(player0 reshuffles.)
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[PLAYS], ['Workshop', 'Copper', 'Copper'])
        assert_equal_card_lists(turn_info[GAINS], ['Bridge'])
        assert_equal_card_lists(turn_info[BUYS], ['Pawn'])
        self.assertEquals(turn_info[MONEY], 2)

    def test_golem_chapel_moat_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 9 ---
   player0 plays a <span class=card-none>Golem</span>.
   ... revealing a <span class=card-none>Witch</span>, and a <span class=card-none>Chapel</span>.
   ... playing the <span class=card-none>Witch</span> first.
   ... ... drawing 2 cards.
   ... ... player1 reveals a <span class=card-reaction>Moat</span>.
   ... playing the <span class=card-none>Chapel</span> second.
   ... ... trashing an <span class=card-victory>Estate</span>.""", 
                                          DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[PLAYS], ['Golem', 'Witch', 'Chapel'])
        assert_equal_card_lists(turn_info[TRASHES], ['Estate'])

    def test_throneroom_throneroom_pirateship_chapel_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 20 ---
   player0 plays a <span class=card-none>Throne Room</span>.
   ... and plays a <span class=card-none>Throne Room</span>.
   ... ... and plays a <span class=card-none>Pirate Ship</span>.
   ... ... ... attacking the other players.
   ... ... ... player1 reveals a <span class=card-victory>Province</span> and an <span class=card-victory>Estate</span>.
   ... ... and plays the <span class=card-none>Pirate Ship</span> again.
   ... ... ... attacking the other players.
   ... ... ... player1 reveals a <span class=card-none>Pirate Ship</span> and a <span class=card-none>Chapel</span>.
   ... and plays the <span class=card-none>Throne Room</span> again.
   ... ... and plays a <span class=card-none>Chapel</span>.
   ... ... ... trashing a <span class=card-victory>Gardens</span>.
   ... ... and plays the <span class=card-none>Chapel</span> again.
   ... ... ... trashing nothing.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[TRASHES], ['Gardens'])

    def test_throne_room_beaurcrat_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 13 ---
player1 plays a <span class=card-none>Throne Room</span>.
... and plays a <span class=card-none>Bureaucrat</span>.
... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.
... ... player2 puts an <span class=card-victory>Estate</span> back on the deck.
... and plays the <span class=card-none>Bureaucrat</span> again.
... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.
... ... player2 reveals 4 <span class=card-treasure>Golds</span>.""", 
                                          DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Silver', 'Silver'])
        self.assertTrue(not OPP in turn_info, turn_info)
        
    def test_witch_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn 5 ---
player0 plays a <span class=card-none>Witch</span>.
... drawing 2 cards.
... player1 gains a <span class=card-curse>Curse</span>.
player0 plays 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-duration>Lighthouse</span>.
""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[PLAYS], ['Witch', 'Copper', 'Copper'])
        self.assertTrue(GAINS not in turn_info)
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS], ['Curse'])
        self.assertEquals(turn_info[MONEY], 2)

    def test_swindler_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 9 ---
   player1 plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... player2 turns up a <span class=card-treasure>Silver</span> and trashes it.
   ... replacing player2's <span class=card-treasure>Silver</span> with a <span class=card-none>Shanty Town</span>.
   ... player3 turns up a <span class=card-none>Shanty Town</span> and trashes it.
   ... replacing player3's <span class=card-none>Shanty Town</span> with a <span class=card-none>Shanty Town</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][GAINS], ['Shanty Town'])
        assert_equal_card_lists(turn_info[OPP]['2'][TRASHES], ['Silver'])
        assert_equal_card_lists(turn_info[OPP]['3'][GAINS], ['Shanty Town'])
        assert_equal_card_lists(turn_info[OPP]['3'][TRASHES], ['Shanty Town'])

    def test_swindler_turn2(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
 player0 plays a <span class=card-none>Worker's Village</span>.
 ... drawing 1 card and getting +2 actions and +1 buy.
 player0 plays a <span class=card-none>Swindler</span>.
 ... getting +$2.
 ... player1 turns up a <span class=card-treasure>Copper</span> and trashes it.
 ... replacing player1's <span class=card-treasure>Copper</span> with a <span class=card-curse>Curse</span>.
 player0 plays a <span class=card-none>Swindler</span>.
 ... getting +$2.
 ... player1 turns up an <span class=card-victory>Estate</span> and trashes it.
 ... replacing player1's <span class=card-victory>Estate</span> with an <span class=card-victory>Estate</span>.
 player0 plays 2 <span class=card-treasure>Coppers</span>.
 player0 buys a <span class=card-treasure>Gold</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][TRASHES], 
                          ['Copper', 'Estate'])
        assert_equal_card_lists(turn_info[OPP]['1'][GAINS],
                          ['Curse', 'Estate'])

    def test_watchtower_mountebank_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 18 ---
    player0 plays a <span class=card-none>Throne Room</span>.
    ... and plays a <span class=card-none>Mountebank</span>.
    ... ... getting +$2.
    ... ... player1 gains a <span class=card-curse>Curse</span> and a <span class=card-treasure>Copper</span>.
    ... ... ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-curse>Curse</span>.
    ... ... ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-treasure>Copper</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][TRASHES], ['Curse', 'Copper'], turn_info)

    def test_mountebank_traders_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player1's turn 6 ---
player1 plays a <span class=card-none>Mountebank</span>.
... getting +$2.
... player2 gains a <span class=card-curse>Curse</span> and a <span class=card-treasure>Copper</span>.
... ... player2 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
... ... player2 gains a <span class=card-treasure>Silver</span>.
... ... player2 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
... ... player2 gains a <span class=card-treasure>Silver</span>.
player1 plays 2 <span class=card-treasure>Silvers</span> and 2 <span class=card-treasure>Coppers</span>.
player1 buys a <span class=card-treasure>Bank</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][GAINS], 
                          ['Silver', 'Silver'], turn_info)

    def test_mountebank_traders_turn2(self):
        # this test is broken because it's an unfixed bug.
        turn_info = parse_game.parse_turn(
u"""--- player1's turn 12 ---</a> 
   player1 plays a <span class=card-none>Mountebank</span>.
   ... getting +$2.
   ... player2 gains a <span class=card-curse>Curse</span> and a <span class=card-treasure>Copper</span>.
   ... ... player2 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
   ... ... player2 gains a <span class=card-treasure>Silver</span>.
   ... ... ... player2 reveals a <span class=card-reaction>Trader</span> to gain a <span class=card-treasure>Silver</span> instead.
   ... ... ... player2 gains a <span class=card-treasure>Silver</span>.""",
DEF_NAME_LIST)
        # p2 only turned the curse gain into a silver, but then just
        # repeatedly spammed that silver -> silver, never cancelled the
        # copper though.
        # TODO: fix it if you want an adventure?
        #self.assertEquals(turn_info[OPP]['2'][GAINS],
        #                  ['Copper', 'Silver'], turn_info[OPP]['2'])
        # similiar bug in 
        # http://councilroom.com/game?game_id=game-20111017-112224-14cd96f7.html&debug=1#Mick_Swagger-show-turn-8
        # with develop/trader interaction.

        # similiar bug in
        # councilroom.com/game?game_id=game-20111017-111832-61528d54.html&debug=1#ChickenSedan-show-turn-13
        # with trader/multiple hoard interaction.

    def test_watchtower_buy_curse_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 11 ---
   player0 buys a <span class=card-curse>Curse</span>.
   ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-curse>Curse</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[BUYS], ['Curse'])
        assert_equal_card_lists(turn_info[TRASHES], ['Curse'])

    def test_thief_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
 player0 plays a <span class=card-none>Thief</span>.
 ... player1 reveals a <span class=card-treasure>Silver</span> and an <span class=card-victory>Estate</span>.
 ... player0 trashes one of player1's <span class=card-treasure>Silvers</span>.
 ... player0 gains the trashed <span class=card-treasure>Silver</span>.""",
                                          DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['1'][TRASHES], ['Silver'])
        assert_equal_card_lists(turn_info[GAINS], ['Silver'])

    def test_mint_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 16 ---
    player0 plays a <span class=card-none>Mint</span>.
    ... revealing a <span class=card-treasure>Platinum</span> and gaining another one.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Platinum'])

    def test_explorer_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 19 ---
      player1 plays an <span class=card-none>Explorer</span>.
      ... revealing a <span class=card-victory>Province</span> and gaining a <span class=card-treasure>Gold</span> in hand.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Gold'])

    def test_mining_village_money(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 9 ---
   player1 plays a <span class=card-none>Mining Village</span>.
   ... (player1 reshuffles.)
   ... drawing 1 card and getting +2 actions.
   ... trashing the <span class=card-none>Mining Village</span> for +$2.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[MONEY], 2)

    def test_fools_gold_reveal_turn(self):
        turn_info = parse_game.parse_turn(
u""" --- player1's turn 10 ---
player1 buys a <span class=card-victory>Province</span>.
   ... player2 reveals a <span class=card-treasure-reaction>Fool's Gold</span>.
   ... ... trashing it.
   ... ... gaining a <span class=card-treasure>Gold</span> on the deck.""",
DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][TRASHES], ["Fool's Gold"])
        assert_equal_card_lists(turn_info[OPP]['2'][GAINS], ["Gold"])

    def test_saboteur_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player2's turn 7 ---
player2 plays an <span class=card-none>Ironworks</span>.
... gaining an <span class=card-victory-action>Island</span>.
... (player2 reshuffles.)
... drawing 1 card and getting +1 action.
player2 plays a <span class=card-none>Saboteur</span>.
... player3 reveals an <span class=card-victory>Estate</span> and a <span class=card-treasure>Copper</span> and then a <span class=card-none>Baron</span>.
... The <span class=card-none>Baron</span> is trashed.
... player3 gains nothing to replace it.
... player9 reveals a <span class=card-none>Baron</span> and trashes it.
... player9 gains nothing to replace it.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['3'][TRASHES], ['Baron'])
        assert_equal_card_lists(turn_info[OPP]['9'][TRASHES], ['Baron'])

    def test_saboteur_turn2(self):
        turn_info = parse_game.parse_turn("""--- player9's turn 14 ---
      player9 plays a <span class=card-none>Saboteur</span>.
      ... player2 reveals a <span class=card-none>Saboteur</span> and trashes it.
      ... player2 gains a <span class=card-treasure>Silver</span> to replace it.
      ... player3 reveals 3 <span class=card-treasure>Coppers</span> and then an <span class=card-victory-action>Island</span>.
      ... The <span class=card-victory-action>Island</span> is trashed.
      ... player3 gains nothing to replace it.
      player9 plays a <span class=card-treasure>Silver</span> and 3 <span class=card-treasure>Coppers</span>.
      player9 buys a <span class=card-none>Saboteur</span>.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[OPP]['2'][TRASHES], ['Saboteur'])
        assert_equal_card_lists(turn_info[OPP]['2'][GAINS], ['Silver'])
        assert_equal_card_lists(turn_info[OPP]['3'][TRASHES], ['Island'])

    def test_lookout_turn(self):
        turn_info = parse_game.parse_turn("""--- player2's turn 9 ---
           player2 plays a <span class=card-none>Lookout</span>.
   ... getting +1 action.
   ... (player2 reshuffles.)
   ... drawing 3 cards.
   ... trashing a <span class=card-treasure>Copper</span>.
   ... discarding a <span class=card-treasure>Copper</span>.
   ... putting a card back on the deck.""", DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[TRASHES], ['Copper'])

    def test_coppersmith(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 3 ---
player0 plays a <span class=card-none>Coppersmith</span>.
... making each <span class=card-treasure>Copper</span> worth $2.
player0 plays a <span class=card-treasure>Silver</span> and 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-victory-action>Nobles</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p0')
        assert_equal_card_lists(turn_info[PLAYS],
                          ['Coppersmith', 'Silver', 'Copper', 'Copper'])
        self.assertEquals(turn_info[MONEY], 6)

    def test_UTF8_name(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 1 ---
player1 plays 3 <span class=card-treasure>Coppers</span>.
player1 buys a <span class=card-none>Workshop</span>.
""", ['', u'Görling'])
        self.assertEquals(turn_info[NAME], u'Görling')
        self.assertEquals(turn_info[MONEY], 3)

    def test_possessed_turn(self):
        turn_info = parse_game.parse_turn(
            u"""--- player0's turn (possessed by player1) ---
player0 plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Mint</span>.
... ... player1 gains the <span class=card-none>Mint</span>.
player0 plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Bazaar</span>.
... ... player1 gains the <span class=card-none>Bazaar</span>.""", 
            DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p1')
        assert_equal_card_lists(turn_info[GAINS], ['Mint', 'Bazaar'])
        self.assertTrue(turn_info[POSSESSION])
        self.assertFalse(OPP in turn_info)

    def test_possessed_turn2(self):
        turn_info = parse_game.parse_turn(
            u"""--- player0's turn (possessed by player1) ---
 player0 plays a <span class=card-none>Remodel</span>.
 ... trashing a <span class=card-none>Mountebank</span>.
 ... gaining a <span class=card-treasure>Gold</span>.
 ... ... player1 gains the <span class=card-treasure>Gold</span>.
 player0 plays 2 <span class=card-treasure>Silvers</span>.
 player0 buys a <span class=card-none>Remodel</span>.
 ... player1 gains the <span class=card-none>Remodel</span>.
 (player0 reshuffles.)
 player0 discards the "trashed" card (a <span class=card-none>Mountebank</span>).""", DEF_NAME_LIST)
        self.assertEquals(turn_info[NAME], 'p1')
        assert_equal_card_lists(turn_info[GAINS], ['Gold', 'Remodel'])
        self.assertFalse(BUYS in turn_info)

    def test_possession_ambassador(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn (possessed by player1) ---</a> 
    player0 plays an <span class=card-none>Ambassador</span>.
    ... revealing 2 <span class=card-victory>Duchies</span> and returning them to the supply.
    ... player1 gains a <span class=card-victory>Duchy</span>.
    player0 plays a <span class=card-treasure>Silver</span>.
    player0 buys an <span class=card-victory>Estate</span>.
    ... player1 gains the <span class=card-victory>Estate</span>.""",
                                          DEF_NAME_LIST)
        assert_equal_card_lists(turn_info[GAINS], ['Duchy', 'Estate'])
        assert_equal_card_lists(turn_info[OPP]['0'][RETURNS], [
                'Duchy', 'Duchy'])

    def test_possession_bishop(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn (possessed by player1) ---</b>
   player0 plays a <span class=card-none>Bishop</span>.
   ... getting +$1 and +1 ▼.
   ... player0 trashes a <span class=card-none>Possession</span> and gets +3 ▼.
   ... player1 trashes nothing.
   player0 plays a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Silver</span>.
   player0 buys a <span class=card-treasure>Silver</span>.
   ... player1 gains the <span class=card-treasure>Silver</span>.
   <span class=logonly>(player0 draws: a <span class=card-treasure>Copper</span>, a <span class=card-treasure>Silver</span>, a <span class=card-none>Native Village</span>, a <span class=card-none>Laboratory</span>, and a <span class=card-none>Wishing Well</span>.)</span>
   player0 discards the "trashed" card (a <span class=card-none>Possession</span>).
   <br>""", DEF_NAME_LIST)
        self.assertEquals(turn_info[OPP]['0'][VP_TOKENS], 4)


class CanonicalizeNamesTest(unittest.TestCase):
    def test_canonicalize_names(self):
        replaced = parse_game.canonicalize_names(
"""--- Zor Prime's turn 1 ---
Zor Prime plays 3 <span class=card-treasure>Coppers</span>.""",
['Zor Prime'])
        self.assertEquals(replaced,
"""--- player0's turn 1 ---
player0 plays 3 <span class=card-treasure>Coppers</span>.""")

    def test_name_as_substring(self):
        replaced = parse_game.canonicalize_names(
"""--- contain ed's turn 9 ---
   contain ed plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... contain turns up a <span class=card-treasure>Silver</span> and trashes it.""", ['contain', 'contain ed'])
        self.assertEquals(replaced,
"""--- player1's turn 9 ---
   player1 plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... player0 turns up a <span class=card-treasure>Silver</span> and trashes it.""")

    def test_evil_short_name(self):
        replaced = parse_game.canonicalize_names(
"""   --- d's turn 2 ---
    d plays 3 <span class=card-treasure>Coppers</span>.
    d buys a <span class=card-none>Masquerade</span>.
    (d reshuffles.)""", ['d'])
        self.assertEquals(replaced,
"""   --- player0's turn 2 ---
    player0 plays 3 <span class=card-treasure>Coppers</span>.
    player0 buys a <span class=card-none>Masquerade</span>.
    (player0 reshuffles.)""")
                          
class SplitTurnsTest(unittest.TestCase):
    def test_split_simple(self):
        split_turns = parse_game.split_turns(
"""--- player1's turn 1 ---
Foo
--- player2's turn 2 ---
Bar""")
        self.assertEquals(len(split_turns), 2)
        self.assertEquals(split_turns[0], "--- player1's turn 1 ---\nFoo\n")
        self.assertEquals(split_turns[1], "--- player2's turn 2 ---\nBar\n")

    def test_possesion_split(self):
        split_turns = parse_game.split_turns(
"""--- player0's turn (possessed by player1) ---
player0 plays an <span class=card-duration>Outpost</span>.
--- player2's turn 2 ---
Bar
--- player3's turn 1 ---
Ick""")
        self.assertEquals(len(split_turns), 3)
        self.assertEquals(split_turns[0], 
 "--- player0's turn (possessed by player1) ---\n"
 "player0 plays an <span class=card-duration>Outpost</span>.\n")
        
    def test_outpost_split(self):
        split_turns = parse_game.split_turns(
"""--- player0's turn 1 ---
... foo
--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---
bar""")
        self.assertEquals(len(split_turns), 2)

    def test_curious_split(self):
        split_turns = parse_game.split_turns(
u"""--- player3's turn 1 ---
player3 plays 3 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(player3 draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- player2's turn 1 ---
   player2 plays 5 <span class=card-treasure>Coppers</span>.
   player2 buys a <span class=card-none>Festival</span>.
    <span class=logonly>(player2 draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

--- player3's turn 2 ---
player3 plays 4 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
(player3 reshuffles.)""")
        self.assertEquals(len(split_turns), 3)

class ParseTurnsTest(unittest.TestCase):
    def test_simple_input(self):
        turns_info = parse_game.parse_turns(u"""--- player3's turn 1 ---
player3 plays 3 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(player3 draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- player2's turn 1 ---
   player2 plays 5 <span class=card-treasure>Coppers</span>.
   player2 buys a <span class=card-none>Festival</span>.
    <span class=logonly>(player2 draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

--- player3's turn 2 ---
player3 plays 4 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
(player3 reshuffles.)
""", DEF_NAME_LIST)
        turn1Z = turns_info[0]
        self.assertEquals(turn1Z[NAME], 'p3')
        assert_equal_card_lists(turn1Z[PLAYS], ['Copper'] * 3)
        assert_equal_card_lists(turn1Z[BUYS], ['Silver'])

        turn1A = turns_info[1]
        self.assertEquals(turn1A[NAME], 'p2')
        assert_equal_card_lists(turn1A[PLAYS], ['Copper'] * 5)
        assert_equal_card_lists(turn1A[BUYS], ['Festival'])

        turn2Z = turns_info[2]
        self.assertEquals(turn2Z[NAME], 'p3')
        assert_equal_card_lists(turn2Z[PLAYS], ['Copper'] * 4)
        assert_equal_card_lists(turn2Z[BUYS], ['Silver'])

    def test_possesion_output_turns(self):
        turns = parse_game.parse_turns(u"""--- player0's turn (possessed by player1) ---
player0 plays an <span class=card-duration>Outpost</span>.
player0 plays 3 <span class=card-treasure>Golds</span>.
player0 buys a <span class=card-treasure>Gold</span>.
... player1 gains the <span class=card-treasure>Gold</span>.
<span class=logonly>(player0 draws: a <span class=card-treasure>Gold</span>, a <span class=card-none>Village</span>, and an <span class=card-duration>Outpost</span>.)</span> 
 
--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---
player0 plays a <span class=card-none>Village</span>.
... (player0 reshuffles.)
... drawing 1 card and getting +2 actions.
player0 plays an <span class=card-duration>Outpost</span>.
player0 plays 2 <span class=card-treasure>Golds</span>.
player0 buys a <span class=card-treasure>Gold</span>.
<span class=logonly>(player0 draws: 2 <span class=card-treasure>Golds</span> and a <span class=card-none>Chapel</span>.)</span> """, DEF_NAME_LIST)
        self.assertEquals(len(turns), 2)

        self.assertTrue(OUTPOST in turns[1])
        assert_equal_card_lists(turns[1][BUYS], ['Gold'])

class ParseDeckTest(unittest.TestCase):
    def test_deck(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Snead: 75 points</b> (7 <span class=card-victory>Colonies</span>, 2 <span class=card-victory-action>Islands</span>, and an <span class=card-victory>Estate</span>); 22 turns
       opening: <span class=card-victory-action>Island</span> / <span class=card-treasure>Silver</span>
       [15 cards] 2 <span class=card-victory-action>Islands</span>, 1 <span class=card-none>Chapel</span>, 1 <span class=card-duration>Tactician</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Platinums</span>, 1 <span class=card-victory>Estate</span>, 7 <span class=card-victory>Colonies</span>""")
        self.assertEquals(parsed_deck[NAME], 'Snead')
        self.assertEquals(parsed_deck[POINTS], 75)
        self.assertEquals(parsed_deck[VP_TOKENS], 0)
        assert_equal_card_dicts(parsed_deck[DECK],
                          {'Island': 2,
                           'Chapel': 1,
                           'Tactician': 1,
                           'Silver': 1,
                           'Platinum': 2,
                           'Estate': 1,
                           'Colony': 7})

    def test_deck_with_resign(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 kiwi</b>: resigned (1st); 13 turns
      opening: <span class=card-none>Shanty Town</span> / <span class=card-none>Baron</span> 
      [23 cards] 8 <span class=card-none>Shanty Towns</span>, 5 <span class=card-none>Rabbles</span>, 2 <span class=card-none>Expands</span>, 1 <span class=card-none>Market</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Estate</span> """)
        self.assertEquals(parsed_deck[RESIGNED], True)

    def test_20101213_style_deck(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 zorkkorz</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck[NAME], 'zorkkorz')

    def test20101213_style_deck_with_paren_name(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 Foo (Bar)</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck[NAME], 'Foo (Bar)')

    def test_20101226_evil_fing_name(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 20 points</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck[NAME], '20 points')
        self.assertEquals(parsed_deck[POINTS], 43)


    def test_deck_with_VP(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Jon: 19 points</b> (16 ▼ and a <span class=card-victory>Duchy</span>); 20 turns
     opening: <span class=card-none>Salvager</span> / <span class=card-none>Black Market</span>
     [7 cards] 2 <span class=card-none>Bishops</span>, 1 <span class=card-duration>Tactician</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Golds</span>, 1 <span class=card-victory>Duchy</span>""")
        self.assertEquals(parsed_deck[VP_TOKENS], 16)

    def test_deck_with_VP2(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Chrome: 12 points</b> (a <span class=card-victory>Province</span> and 6 ▼); 13 turns
        opening: <span class=card-none>Ironworks</span> / <span class=card-none>Black Market</span>
        [25 cards] 5 <span class=card-duration>Merchant Ships</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Apprentices</span>, 2 <span class=card-none>Warehouses</span>, 1 <span class=card-none>Bishop</span>, 1 <span class=card-none>Black Market</span>, 1 <span class=card-none>Explorer</span>, 1 <span class=card-none>Worker's Village</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Province</span>""")
        self.assertEquals(parsed_deck[VP_TOKENS], 6)

    def test_parse_old_deck_with_paren(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Jeremy (player1): 66 points</b> (8 <span class=card-victory>Provinces</span>, 4 <span class=card-victory>Duchies</span>, and 6 <span class=card-victory>Estates</span>); 28 turns
                     opening: <span class=card-none>Smithy</span> / <span class=card-treasure>Silver</span> 
                     [38 cards] 2 <span class=card-none>Smithies</span>, 7 <span class=card-treasure>Coppers</span>, 5 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 6 <span class=card-victory>Estates</span>, 4 <span class=card-victory>Duchies</span>, 8 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck[NAME], 'Jeremy (player1)')

    def test_deck_with_VP3(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Chrome: 12 points</b> (a <span class=card-victory>Province</span> and 26 ▼); 13 turns
        opening: <span class=card-none>Ironworks</span> / <span class=card-none>Black Market</span>
        [25 cards] 5 <span class=card-duration>Merchant Ships</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Apprentices</span>, 2 <span class=card-none>Warehouses</span>, 1 <span class=card-none>Bishop</span>, 1 <span class=card-none>Black Market</span>, 1 <span class=card-none>Explorer</span>, 1 <span class=card-none>Worker's Village</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Province</span>""")
        self.assertEquals(parsed_deck[VP_TOKENS], 26)

    def test_parse_empty_deck(self):
        # it's random BS like this that makes writing a dominion log parser
        # a pain.
        parsed_deck = parse_game.parse_deck(u"""<b>torchrat: 0 points</b> (nothing); 24 turns
          opening: <span class=card-none>Moneylender</span> / <span class=card-treasure>Silver</span>
          [0 cards] """)
        self.assertEquals(parsed_deck[VP_TOKENS], 0)
        self.assertEquals(parsed_deck[DECK], {})

class AssignWinPointsTest(unittest.TestCase):
    def test_assign_win_points_simple(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}]},
                {POINTS: 1, TURNS: [{}, {}]}
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g[DECKS][0][WIN_POINTS], 2.0)
        self.assertEquals(g[DECKS][1][WIN_POINTS], 0.0)

    def test_assign_win_points_break_ties_by_turns(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}]},
                {POINTS: 2, TURNS: [{}]}
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g[DECKS][0][WIN_POINTS], 0.0)
        self.assertEquals(g[DECKS][1][WIN_POINTS], 2.0)        
        
    def test_tie(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}]},
                {POINTS: 2, TURNS: [{}, {}]}
                ]}
        parse_game.assign_win_points(g)        
        self.assertEquals(g[DECKS][0][WIN_POINTS], 1.0)
        self.assertEquals(g[DECKS][1][WIN_POINTS], 1.0)

    def test_partial_tie(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}]},
                {POINTS: 2, TURNS: [{}, {}]},
                {POINTS: 1, TURNS: [{}, {}]}
                ]}
        parse_game.assign_win_points(g)        
        self.assertEquals(g[DECKS][0][WIN_POINTS], 1.5)
        self.assertEquals(g[DECKS][1][WIN_POINTS], 1.5)

    def test_outpost_turn(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}, {OUTPOST: True}]},
                {POINTS: 2, TURNS: [{}, {}]},
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g[DECKS][0][WIN_POINTS], 1.0)

    def test_possession_turn(self):
        g = {DECKS: [
                {POINTS: 2, TURNS: [{}, {}, {POSSESSION: True}]},
                {POINTS: 2, TURNS: [{}, {}]},
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g[DECKS][0][WIN_POINTS], 1.0)        

class ParseGameHeaderTest(unittest.TestCase):
    def test_parse_header(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #2051</title></head><body><pre>AndMyAxe! wins!
All <span class=card-victory>Provinces</span> are gone.

cards in supply: <span cardname="Black Market" class=card-none>Black Market</span>, <span cardname="Caravan" class=card-duration>Caravan</span>, <span cardname="Chancellor" class=card-none>Chancellor</span>, <span cardname="City" class=card-none>City</span>, <span cardname="Council Room" class=card-none>Council Room</span>, <span cardname="Counting House" class=card-none>Counting House</span>, <span cardname="Explorer" class=card-none>Explorer</span>, <span cardname="Market" class=card-none>Market</span>, <span cardname="Mine" class=card-none>Mine</span>, and <span cardname="Pawn" class=card-none>Pawn</span>""")
        assert_equal_card_lists(parsed_header[GAME_END], ['Province'])
        assert_equal_card_lists(parsed_header[SUPPLY], ['Black Market',
                                                    "Caravan",
                                                    "Chancellor",
                                                    "City",
                                                    "Council Room",
                                                    "Counting House",
                                                    "Explorer",
                                                    "Market",
                                                    "Mine",
                                                    "Pawn"])

    def test_header_with_resign(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/client.css"><title>Dominion Game #262</title></head><body><pre>uberme wins!
All but one player has resigned.
 
cards in supply: <span cardname="Bank" class=card-treasure>Bank</span>, <span cardname="Black Market" class=card-none>Black Market</span>, <span cardname="Colony" class=card-victory>Colony</span>, <span cardname="Hoard" class=card-treasure>Hoard</span>, <span cardname="Ironworks" class=card-none>Ironworks</span>, <span cardname="Militia" class=card-none>Militia</span>, <span cardname="Moneylender" class=card-none>Moneylender</span>, <span cardname="Platinum" class=card-treasure>Platinum</span>, <span cardname="Rabble" class=card-none>Rabble</span>, <span cardname="Scout" class=card-none>Scout</span>, <span cardname="Sea Hag" class=card-none>Sea Hag</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>
""")
        self.assertEquals(parsed_header[GAME_END], [])
        self.assertEquals(parsed_header[RESIGNED], True)
        

    def test_parse_header_with_multi_end(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #3865</title></head><body><pre>stormybriggs wins!
<span class=card-victory>Duchies</span>, <span class=card-victory>Estates</span>, and <span class=card-none>Peddlers</span> are all gone.

cards in supply: <span cardname="Colony" class=card-victory>Colony</span>, <span cardname="Grand Market" class=card-none>Grand Market</span>, <span cardname="Loan" class=card-treasure>Loan</span>, <span cardname="Mine" class=card-none>Mine</span>, <span cardname="Monument" class=card-none>Monument</span>, <span cardname="Outpost" class=card-duration>Outpost</span>, <span cardname="Peddler" class=card-none>Peddler</span>, <span cardname="Platinum" class=card-treasure>Platinum</span>, <span cardname="Stash" class=card-treasure>Stash</span>, <span cardname="Warehouse" class=card-none>Warehouse</span>, <span cardname="Witch" class=card-none>Witch</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>
""")
        assert_equal_card_lists(parsed_header[GAME_END], ['Duchy', 'Estate', 
                                                      'Peddler'])
        self.assertEquals(parsed_header[RESIGNED], False)

class ValidateNamesTest(unittest.TestCase):
    def test_keyword_in_name(self):
        decks = [{NAME: 'gains a curse'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

    def test_starts_with_period(self):
        decks = [{NAME: '.evil'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

    def test_name_is_a(self):
        decks = [{NAME: 'a'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

class ParseGameTest(unittest.TestCase):
    def test_parse_game(self):
        parsed_game = parse_game.parse_game(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #2083</title></head><body><pre>Alenia wins!
All <span class=card-victory>Provinces</span> are gone.

cards in supply: <span cardname="Coppersmith" class=card-none>Coppersmith</span>, <span cardname="Expand" class=card-none>Expand</span>, <span cardname="Gardens" class=card-victory>Gardens</span>, <span cardname="Mining Village" class=card-none>Mining Village</span>, <span cardname="Nobles" class=card-victory-action>Nobles</span>, <span cardname="Outpost" class=card-duration>Outpost</span>, <span cardname="Pearl Diver" class=card-none>Pearl Diver</span>, <span cardname="Thief" class=card-none>Thief</span>, <span cardname="Throne Room" class=card-none>Throne Room</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>

----------------------

<b>Alenia: 58 points</b> (8 <span class=card-victory>Provinces</span> and 5 <span class=card-victory-action>Nobles</span>); 24 turns
        opening: <span class=card-treasure>Silver</span> / <span class=card-none>Coppersmith</span>
        [37 cards] 5 <span class=card-victory-action>Nobles</span>, 3 <span class=card-none>Expands</span>, 3 <span class=card-none>Pearl Divers</span>, 3 <span class=card-none>Worker's Villages</span>, 1 <span class=card-duration>Outpost</span>, 1 <span class=card-none>Throne Room</span>, 5 <span class=card-treasure>Coppers</span>, 8 <span class=card-treasure>Silvers</span>, 8 <span class=card-victory>Provinces</span>

<b>AndMyAxe!: 30 points</b> (5 <span class=card-victory>Gardens</span> [46 cards], 7 <span class=card-victory>Estates</span>, and a <span class=card-victory>Duchy</span>); 23 turns
           opening: <span class=card-treasure>Silver</span> / <span class=card-none>Worker's Village</span>
           [46 cards] 6 <span class=card-none>Worker's Villages</span>, 5 <span class=card-victory>Gardens</span>, 1 <span class=card-none>Coppersmith</span>, 1 <span class=card-duration>Outpost</span>, 1 <span class=card-none>Throne Room</span>, 21 <span class=card-treasure>Coppers</span>, 3 <span class=card-treasure>Silvers</span>, 7 <span class=card-victory>Estates</span>, 1 <span class=card-victory>Duchy</span>

----------------------

trash: a <span class=card-treasure>Silver</span>, 3 <span class=card-victory>Gardens</span>, a <span class=card-victory>Duchy</span>, 3 <span class=card-victory>Estates</span>, 2 <span class=card-treasure>Coppers</span>, a <span class=card-none>Coppersmith</span>, and 3 <span class=card-none>Expands</span>
league game: no

<hr/><b>Game log</b>

Turn order is Alenia and then AndMyAxe!.

<span class=logonly>(Alenia's first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>
<span class=logonly>(AndMyAxe!'s first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 1 ---
Alenia plays 3 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(Alenia draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- AndMyAxe!'s turn 1 ---
   AndMyAxe! plays 3 <span class=card-treasure>Coppers</span>.
   AndMyAxe! buys a <span class=card-treasure>Silver</span>.
   <span class=logonly>(AndMyAxe! draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 2 ---
Alenia plays 4 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-none>Coppersmith</span>.
(Alenia reshuffles.)
<span class=logonly>(Alenia draws: an <span class=card-victory>Estate</span>, a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-none>Coppersmith</span>.)</span>

   --- AndMyAxe!'s turn 2 ---
   AndMyAxe! plays 4 <span class=card-treasure>Coppers</span>.
   AndMyAxe! buys a <span class=card-none>Worker's Village</span>.
   (AndMyAxe! reshuffles.)
   <span class=logonly>(AndMyAxe! draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 3 ---
Alenia plays a <span class=card-none>Coppersmith</span>.
... making each <span class=card-treasure>Copper</span> worth $2.
Alenia plays a <span class=card-treasure>Silver</span> and 2 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-victory-action>Nobles</span>.
<span class=logonly>(Alenia draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

All <span class=card-victory>Provinces</span> are gone.
Alenia wins!
</pre></body></html>""")
        self.assertEquals(parsed_game[PLAYERS], ['Alenia', 'AndMyAxe!'])
        self.assertEquals(parsed_game[DECKS][0][NAME], 'Alenia')
        self.assertEquals(parsed_game[DECKS][0][POINTS], 58)
        self.assertEquals(parsed_game[DECKS][0][ORDER], 1)
        self.assertEquals(parsed_game[DECKS][1][NAME], 'AndMyAxe!')
        self.assertEquals(parsed_game[DECKS][1][ORDER], 2)
        self.assertEquals(len(parsed_game[DECKS][0][TURNS]), 3)
        self.assertEquals(len(parsed_game[DECKS][1][TURNS]), 2)
        
        self.assertEquals(parsed_game[DECKS][0][WIN_POINTS], 2.0)
        self.assertEquals(parsed_game[DECKS][1][WIN_POINTS], 0.0)

        assert_equal_card_lists(parsed_game[DECKS][0][TURNS][2][PLAYS], 
                          ['Coppersmith', 'Silver', 'Copper', 'Copper'])
        assert_equal_card_lists(parsed_game[SUPPLY],
                          ["Coppersmith", 
                           "Expand",
                           "Gardens",
                           "Mining Village",
                           "Nobles",
                           "Outpost",
                           "Pearl Diver",
                           "Thief", 
                           "Throne Room",
                           "Worker's Village"])

        self.assertEquals(parsed_game[VETO], {})

    EVIL_GAME_CONTENTS = u"""<html><head><link rel="stylesheet" href="/client.css"><title>Dominion Game #40068</title></head><body><pre>dcg wins!
All but one player has resigned.

cards in supply: <span cardname="Apprentice" class=card-none>Apprentice</span>, <span cardname="Familiar" class=card-none>Familiar</span>, <span cardname="Island" class=card-victory-action>Island</span>, <span cardname="Minion" class=card-none>Minion</span>, <span cardname="Possession" class=card-none>Possession</span>, <span cardname="Potion" class=card-treasure>Potion</span>, <span cardname="Royal Seal" class=card-treasure>Royal Seal</span>, <span cardname="Shanty Town" class=card-none>Shanty Town</span>, <span cardname="Throne Room" class=card-none>Throne Room</span>, <span cardname="Trade Route" class=card-none>Trade Route</span>, and <span cardname="Upgrade" class=card-none>Upgrade</span>

----------------------

<b>#1 dcg</b>: 3 points (3 <span class=card-victory>Estates</span>); 1 turns
     opening: <span class=card-treasure>Potion</span> / nothing
     [11 cards] 7 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Potion</span>, 3 <span class=card-victory>Estates</span>

<b>#2 8----------------------D</b>: resigned (1st); 2 turns
                          opening: <span class=card-none>Minion</span> / nothing
                          [11 cards] 1 <span class=card-none>Minion</span>, 7 <span class=card-treasure>Coppers</span>, 3 <span class=card-victory>Estates</span>

----------------------

trash: nothing
league game: no

<hr/><b>Game log</b>

Turn order is 8----------------------D and then dcg.

<span class=logonly>(8----------------------D's first hand: 5 <span class=card-treasure>Coppers</span>.)</span>
<span class=logonly>(dcg's first hand: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

--- 8----------------------D's turn 1 ---
8----------------------D plays 5 <span class=card-treasure>Coppers</span>.
8----------------------D buys a <span class=card-none>Minion</span>.
<span class=logonly>(8----------------------D draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

   --- dcg's turn 1 ---
   dcg plays 4 <span class=card-treasure>Coppers</span>.
   dcg buys a <span class=card-treasure>Potion</span>.
   <span class=logonly>(dcg draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- 8----------------------D's turn 2 ---
8----------------------D resigns from the game (client disconnected).

All but one player has resigned.
dcg wins!
</pre></body></html>"""
    def test_parse_game_with_bogus_check(self):
        self.assertRaises(parse_game.BogusGameError, parse_game.parse_game,
                          ParseGameTest.EVIL_GAME_CONTENTS, True)

    def test_possesion_minigame(self):
        game_contents = u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #888</title></head><body><pre>Leeko wins!
<span class=card-none>Bazaars</span>, <span class=card-none>Laboratories</span>, and <span class=card-curse>Curses</span> are all gone.
 
cards in supply: <span class=card-none>Bazaar</span>, <span class=card-none>Cutpurse</span>, <span class=card-none>Familiar</span>, <span class=card-victory>Gardens</span>, <span class=card-none>Laboratory</span>, <span class=card-none>Library</span>, <span class=card-none>Mint</span>, <span class=card-none>Possession</span>, <span class=card-treasure>Potion</span>, <span class=card-none>University</span>, and <span class=card-reaction>Watchtower</span> 

----------------------

<b>Leeko: 4 points</b> (a <span class=card-victory>Province</span>, 3 <span class=card-victory>Estates</span>, and 5 <span class=card-curse>Curses</span>); 17 turns
       opening: <span class=card-treasure>Silver</span> / <span class=card-treasure>Potion</span> 
       [40 cards] 9 <span class=card-none>Laboratories</span>, 7 <span class=card-none>Bazaars</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Familiars</span>, 1 <span class=card-none>Cutpurse</span>, 1 <span class=card-none>Mint</span>, 1 <span class=card-reaction>Watchtower</span>, 2 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Potions</span>, 3 <span class=card-victory>Estates</span>, 1 <span class=card-victory>Province</span>, 5 <span class=card-curse>Curses</span> 

<b>michiel: 0 points</b> (3 <span class=card-victory>Estates</span> and 3 <span class=card-curse>Curses</span>); 16 turns
         opening: <span class=card-treasure>Potion</span> / <span class=card-reaction>Watchtower</span> 
         [28 cards] 3 <span class=card-none>Bazaars</span>, 3 <span class=card-none>Familiars</span>, 3 <span class=card-reaction>Watchtowers</span>, 2 <span class=card-none>Mints</span>, 1 <span class=card-none>Cutpurse</span>, 1 <span class=card-none>Laboratory</span>, 1 <span class=card-none>Possession</span>, 4 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Potions</span>, 1 <span class=card-treasure>Gold</span>, 3 <span class=card-victory>Estates</span>, 3 <span class=card-curse>Curses</span> 

----------------------
trash: 8 <span class=card-treasure>Coppers</span>, a <span class=card-treasure>Silver</span>, and 2 <span class=card-curse>Curses</span> 
league game: no
 
<hr/><b>Game log</b> 
 
Turn order is Leeko and then michiel.
<span class=logonly>(Leeko's first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span> 
<span class=logonly>(michiel's first hand: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span> 
 
--- Leeko's turn 1 ---
Leeko plays 3 <span class=card-treasure>Coppers</span>.
Leeko buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(Leeko draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span> 
 
   --- michiel's turn 1 ---
   michiel plays 4 <span class=card-treasure>Coppers</span>.
   michiel buys a <span class=card-treasure>Potion</span>.
   <span class=logonly>(michiel draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span> 

   --- michiel's turn 15 ---
   michiel plays a <span class=card-none>Laboratory</span>.
   ... drawing 2 cards and getting +1 action.
   michiel plays a <span class=card-none>Possession</span>.
   <span class=logonly>(michiel draws: a <span class=card-reaction>Watchtower</span>, a <span class=card-treasure>Potion</span>, a <span class=card-none>Familiar</span>, a <span class=card-treasure>Gold</span>, and a <span class=card-curse>Curse</span>.)</span> 

--- Leeko's turn (possessed by michiel) ---
Leeko plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Mint</span>.
... ... michiel gains the <span class=card-none>Mint</span>.
Leeko plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Bazaar</span>.
... ... michiel gains the <span class=card-none>Bazaar</span>.
Leeko plays 2 <span class=card-treasure>Coppers</span>.
(Leeko reshuffles.)
<span class=logonly>(Leeko draws: a <span class=card-none>University</span>, a <span class=card-none>Mint</span>, a <span class=card-none>Bazaar</span>, and 2 <span class=card-curse>Curses</span>.)</span>  

<span class=card-none>Bazaars</span>, <span class=card-none>Laboratories</span>, and <span class=card-curse>Curses</span> are all gone.
Leeko wins!
</pre></body></html> """
        parsed_game = parse_game.parse_game(game_contents)
        leeko_deck = parsed_game[DECKS][0]
        self.assertEquals(leeko_deck[NAME], 'Leeko')
        michiel_deck = parsed_game[DECKS][1]
        self.assertEquals(michiel_deck[NAME], 'michiel')
        self.assertEquals(len(leeko_deck[TURNS]), 1)
        self.assertEquals(len(michiel_deck[TURNS]), 3)
        self.assertTrue(michiel_deck[TURNS][2][POSSESSION])
        # pprint.pprint(parsed_game)

    def test_parse_game_with_vetos(self):
        game_contents = u"""<html><head><link rel="stylesheet" href="/client.css"><title>Dominion Game #412275</title></head><body><pre>Arsenic03 wins!
<span class=card-victory-treasure>Harems</span>, <span class=card-none>Wishing Wells</span>, and <span class=card-victory>Duchies</span> are all gone.

cards in supply: <span cardname="Counting House" class=card-none>Counting House</span>, <span cardname="Duchess" class=card-none>Duchess</span>, <span cardname="Harem" class=card-victory-treasure>Harem</span>, <span cardname="Haven" class=card-duration>Haven</span>, <span cardname="Horn of Plenty" class=card-treasure>Horn of Plenty</span>, <span cardname="Merchant Ship" class=card-duration>Merchant Ship</span>, <span cardname="Noble Brigand" class=card-none>Noble Brigand</span>, <span cardname="Scout" class=card-none>Scout</span>, <span cardname="Trade Route" class=card-none>Trade Route</span>, and <span cardname="Wishing Well" class=card-none>Wishing Well</span>

----------------------

<b>#1 Arsenic03</b>: 40 points (3 <span class=card-victory>Provinces</span>, 4 <span class=card-victory>Duchies</span>, and 5 <span class=card-victory-treasure>Harems</span>); 18 turns
           opening: <span class=card-none>Trade Route</span> / <span class=card-none>Wishing Well</span>
           [34 cards] 8 <span class=card-none>Wishing Wells</span>, 5 <span class=card-victory-treasure>Harems</span>, 4 <span class=card-duration>Havens</span>, 4 <span class=card-none>Scouts</span>, 1 <span class=card-duration>Merchant Ship</span>, 1 <span class=card-none>Trade Route</span>, 3 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Gold</span>, 4 <span class=card-victory>Duchies</span>, 3 <span class=card-victory>Provinces</span>

<b>#2 Trikillall</b>: 30 points (2 <span class=card-victory>Provinces</span>, 4 <span class=card-victory>Duchies</span>, and 3 <span class=card-victory-treasure>Harems</span>); 18 turns
            opening: <span class=card-none>Trade Route</span> / <span class=card-treasure>Silver</span>
            [27 cards] 3 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Wishing Wells</span>, 1 <span class=card-duration>Haven</span>, 1 <span class=card-treasure>Horn of Plenty</span>, 1 <span class=card-none>Noble Brigand</span>, 1 <span class=card-none>Scout</span>, 1 <span class=card-none>Trade Route</span>, 4 <span class=card-treasure>Coppers</span>, 3 <span class=card-treasure>Silvers</span>, 4 <span class=card-treasure>Golds</span>, 4 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Provinces</span>

----------------------

trash: 7 <span class=card-treasure>Coppers</span>, 7 <span class=card-treasure>Horns of Plenty</span>, and 6 <span class=card-victory>Estates</span>

<hr/><b>Game log</b>

Turn order is Arsenic03 and then Trikillall.

The 12 chosen cards are <span cardname="Counting House" class=card-none>Counting House</span>, <span cardname="Duchess" class=card-none>Duchess</span>, <span cardname="Fool's Gold" class=card-treasure-reaction>Fool's Gold</span>, <span cardname="Harem" class=card-victory-treasure>Harem</span>, <span cardname="Haven" class=card-duration>Haven</span>, <span cardname="Horn of Plenty" class=card-treasure>Horn of Plenty</span>, <span cardname="Merchant Ship" class=card-duration>Merchant Ship</span>, <span cardname="Noble Brigand" class=card-none>Noble Brigand</span>, <span cardname="Scout" class=card-none>Scout</span>, <span cardname="Tactician" class=card-duration>Tactician</span>, <span cardname="Trade Route" class=card-none>Trade Route</span>, and <span cardname="Wishing Well" class=card-none>Wishing Well</span>.
Arsenic03 vetoes <span class=card-treasure-reaction>Fool's Gold</span>.
Trikillall vetoes <span class=card-duration>Tactician</span>.


<span class=logonly>(Arsenic03's first hand: 4 <span class=card-treasure>Coppers</span> and an <span class=card-victory>Estate</span>.)</span>
<span class=logonly>(Trikillall's first hand: 3 <span class=card-treasure>Coppers</span> and 2 <span class=card-victory>Estates</span>.)</span>
<br>
&mdash; Arsenic03's turn 1 &mdash;
Arsenic03 plays 4 <span class=card-treasure>Coppers</span>.
Arsenic03 buys a <span class=card-none>Trade Route</span>.
<span class=logonly>(Arsenic03 draws: 3 <span class=card-treasure>Coppers</span> and 2 <span class=card-victory>Estates</span>.)</span>
   <br>
   &mdash; Trikillall's turn 1 &mdash;
   Trikillall plays 3 <span class=card-treasure>Coppers</span>.
   Trikillall buys a <span class=card-none>Trade Route</span>.
   <span class=logonly>(Trikillall draws: 4 <span class=card-treasure>Coppers</span> and an <span class=card-victory>Estate</span>.)</span>
<br>
&mdash; Arsenic03's turn 2 &mdash;
Arsenic03 plays 3 <span class=card-treasure>Coppers</span>.
Arsenic03 buys a <span class=card-none>Wishing Well</span>.
(Arsenic03 reshuffles.)
<span class=logonly>(Arsenic03 draws: 4 <span class=card-treasure>Coppers</span> and a <span class=card-none>Wishing Well</span>.)</span>
   <br>
   &mdash; Trikillall's turn 2 &mdash;
   Trikillall plays 4 <span class=card-treasure>Coppers</span>.
   Trikillall buys a <span class=card-treasure>Silver</span>.
   (Trikillall reshuffles.)
   <span class=logonly>(Trikillall draws: 4 <span class=card-treasure>Coppers</span> and a <span class=card-treasure>Silver</span>.)</span>

<span class=card-victory-treasure>Harems</span>, <span class=card-none>Wishing Wells</span>, and <span class=card-victory>Duchies</span> are all gone.
Arsenic03 wins!
</pre></body></html>"""
        parsed_game = parse_game.parse_game(game_contents)
        veto_dict = parsed_game[VETO]
        assert_equal_card_lists([veto_dict['1']], ["Tactician"])
        assert_equal_card_lists([veto_dict['0']], ["Fool's Gold"])

        game_contents = codecs.open('testing/testdata/game-20120120-122852-2861266d.html', encoding='utf-8').read()
        parsed_game = parse_game.parse_game(game_contents)
        # Name 'Slow connection - sorry' is normed down to 'Slow connectionsorry'
        self.assertEquals(parsed_game[PLAYERS], [u'Slow connectionsorry', u'richard', u'Kazantzakis'])
        veto_dict = parsed_game[VETO]
        assert_equal_card_lists([veto_dict['0']], ["Upgrade"])
        assert_equal_card_lists([veto_dict['1']], ["Ill-Gotten Gains"])
        assert_equal_card_lists([veto_dict['2']], ["Alchemist"])

        # The following game had the string "away" in a user's name, which was getting normalized away
        game_contents = codecs.open('testing/testdata/game-20120122-190607-28dac253.html', encoding='utf-8').read()
        parsed_game = parse_game.parse_game(game_contents)
        self.assertEquals(parsed_game[PLAYERS], [u'carraway', u'Dad Frog', u'Lanaro'])
        veto_dict = parsed_game[VETO]
        assert_equal_card_lists([veto_dict['0']], ["Chancellor"])
        assert_equal_card_lists([veto_dict['1']], ["Familiar"])
        assert_equal_card_lists([veto_dict['2']], ["Ambassador"])


    def test_name_folding(self):
        """Player names get folded to remove certain strings/substrings. Check these rules."""

        # Names should be consistent between the PLAYERS list and the
        # player name stored with each deck. The player's real name in
        # this game is "BGGDL-Celicath", but it should get normalized
        # down to "Celicath".

        game_contents = codecs.open('testing/testdata/game-20101015-024842-a866e78a.html', encoding='utf-8').read()
        parsed_game = parse_game.parse_game(game_contents)
        self.assertEquals(parsed_game[PLAYERS], [u'Celicath', u'tafkal'])
        self.assertEquals(parsed_game[DECKS][0][NAME], u'Celicath')
        self.assertEquals(parsed_game[DECKS][1][NAME], u'tafkal')


if __name__ == '__main__':
    unittest.main()
