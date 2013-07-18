#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Parse raw goko game into JSON list of game documents."""

import bz2
import codecs
import collections
import datetime
import itertools
import logging
import logging.handlers
import multiprocessing
import os
import os.path
import pprint
import pymongo
import re
import sys

from dominioncards import get_card, CardEncoder, indexes, index_to_card
from game import Game
from keys import *
from utils import segments
import dominioncards
import game
import name_merger
import simplejson as json
import utils
import parse_common

RECEIVES_COIN_TOKENS_RE = re.compile('receives (\d+) coin token')
USES_COIN_TOKENS_RE = re.compile('uses (\d+) coin token')
KW_OVERPAYS = 'overpays for'

RATING_SYSTEM_RE = re.compile('^Rating system: (.*)$')
GAME_OVER_RE = re.compile('^------------ Game Over ------------$')
EMPTY_LINE_RE = re.compile('^\s*$')
ENDGAME_VP_CHIP_RE = re.compile('^.* - victory point chips: (\d+)$')
ENDGAME_POINTS_RE = re.compile('^.* - total victory points: (-?\d+)$')
START_TURN_RE = re.compile('^---------- (.*): turn (.*?) (\[possessed\] )?----------$')
VP_CHIPS_RE = re.compile('receives (\d+) victory point chips')
HYPHEN_SPLIT_RE = re.compile('^(.*) - (.*)$')
COMMA_SPLIT_RE = re.compile(', ')
NUMBER_CARD_RE = re.compile('\s*(\d+) (.*)')
BANE_RE = re.compile('^Bane card: (.*)$')
PLAYER_AND_START_DECK_RE = re.compile('^(.*) - starting cards: (.*)$')
TAKES_COINS_RE = re.compile('takes (\d+) coin')
RECEIVES_COINS_RE = re.compile('receives (\d+) coin')
TAKES_ACTIONS_RE = re.compile('takes (\d+) action')
RECEIVES_ACTIONS_RE = re.compile('receives (\d+) action')

KW_SCHEME_CHOICE = 'Scheme choice: '
KW_MOVES = 'moves '
KW_MOVES_DECK_TO_DISCARD = 'moves deck to discard'
KW_APPLIED = 'applied ' #applied Watchtower to place X on top of the deck
KW_APPLIES_WHEN_TRASHED = "applies the 'when you trash ability' of "
KW_TO_THE_SUPPLY = ' to the Supply'
KW_PLACE = 'place: '
KW_CARDS = 'cards: '
KW_CARDS_IN_DISCARDS = 'cards in discards'
KW_PLAYS = 'plays '
KW_LOOKS_AT = 'looks at '
KW_GAINS = 'gains '
KW_RECEIVES = 'receives '
KW_RESIGNED = 'resigned'
KW_QUIT = 'quit'
KW_REVEALS_C = 'reveals: ' 
KW_REVEALS_HAND = 'reveals hand: ' 
KW_HAND = 'hand: '
KW_REVEALS = 'reveals ' 
KW_REVEALS_REACTION = 'reveals reaction ' 
KW_REACTION = 'reaction ' 
KW_DISCARDS = 'discards '
KW_DISCARDS_C = 'discards: '
KW_PLACES = 'places '
KW_BUYS = 'buys '
KW_DRAWS = 'draws ' 
KW_TRASHES = 'trashes ' 
KW_PASSES = 'passes ' 
KW_SHUFFLES = 'shuffles deck'
KW_PLACES = 'places ' 
KW_DURATION = 'duration '
KW_SETS_ASIDE = 'sets aside ' 
KW_TAKES_SET_ASIDE = 'takes set aside cards: '
KW_CHOOSES = 'chooses '
KW_CHOOSES_TWO_CARDS_AND_ONE_ACTION = 'chooses two cards and one action'
KW_RECEIVES_ONE_ACTION = 'receives one action'
KW_EMBARGOES = 'embargoes '
KW_NAMES = 'names '
KW_CHOOSES_TWO_COINS = 'chooses two coins'
KW_RETURNS = 'returns ' 
KW_PIRATE_COIN = 'receives a pirate coin, now has '
KW_VP_CHIPS = 'victory point chips'
KW_TAKES = 'takes ' 

ACTION_PHASE = 'ap'
BUY_PHASE = 'bp'
CLEANUP_PHASE = 'cp'

KEYWORDS = [locals()[w] for w in dict(locals()) if w.startswith('KW_')]

def parse_player_start_decks(log_lines):
    start_decks = []
    start_match = PLAYER_AND_START_DECK_RE.match(log_lines[0])
    while start_match:
        line=log_lines.pop(0)
        name = start_match.group(1)
        start_deck = indexes(capture_cards(start_match.group(2)))
        start_decks.append({NAME:name, START_DECK:start_deck})

        start_match = PLAYER_AND_START_DECK_RE.match(log_lines[0])
    return start_decks

def parse_supply(log_lines):
    line = log_lines.pop(0)
    supply_cards_text = line.split(', ')
    supply_cards_text[0] = supply_cards_text[0].replace('Supply cards: ','')
    supply_cards = []
    for card_name in supply_cards_text:
        try:
            card = get_card(card_name)
        except KeyError, exception:
            raise parse_common.ParsingError('%s is not a card in the supply!'
                                            % card_name)
        supply_cards.append(card.index)

    bane_match = BANE_RE.match(log_lines[0])
    if bane_match:
        try:
            bane_card = get_card(bane_match.groups()[0])
            log_lines.pop(0)
        except KeyError, exception:
            raise parse_common.ParsingError('%s is not a valid bane!'
                                            % card_name)
    return supply_cards

def parse_header(log_lines):
    """Parse the goko header. 
    
    It begins with the 'Game Setup' line and ends with the blank line before
    the first player's first turn.
    """

    # first line - header line
    line = log_lines.pop(0)
    assert('Game Setup' in line)
    
    # next - supply
    supply_cards = parse_supply(log_lines)

    # optionally, may say the game type. Old logs won't have this.
    rating_system_match = RATING_SYSTEM_RE.match(log_lines[0])
    if rating_system_match:
        rating_system = rating_system_match.group(1)
        line = log_lines.pop(0)
    else:
        rating_system = 'unknown'

    # Next N lines will give me the N players and their start decks
    start_decks = parse_player_start_decks(log_lines) 
    names_list = [d[NAME] for d in start_decks]

    # next 2N lines are the players shuffling their decks
    # and drawing their starting hands. Then one blank line. 
    log_lines[0:(len(names_list)*2+1)] = []

    return {START_DECKS:start_decks, PLAYERS:names_list, SUPPLY:supply_cards,
            RATING_SYSTEM:rating_system}

def validate_names(game_dict, dubious_check):
    """ Raise an exception for names that might screw up the parsing.
    This should happen in less than 1% of real games, but it's just easier
    to punt on annoying inputs that to make sure we get them right.
    """
    names = game_dict[PLAYERS]
    used_names = set()
    for name in names:
        if name in used_names:
            # unrecoverable!
            raise parse_common.BogusGameError('Duplicate name %s' % name)
        used_names.add(name)

    if len(names) <= 1 and dubious_check:
        # that's recoverable, so only raise error if checking dubious
        raise parse_common.BogusGameError('only one player')


def capture_cards(line, return_dict=False):
    """ Given a section of text from goko, extract the cards.

    line: string like 'plays 1 Silver, 3 Copper'
    returns: list of the card objects, eg, [Silver, Copper, Copper, Copper]
    """
    for kw in KEYWORDS:
        line=line.replace(kw, '')


    if return_dict:
        cards = {}
    else:
        cards = []

    if EMPTY_LINE_RE.match(line):
        return cards

    card_sections = COMMA_SPLIT_RE.split(line)
    for sect in card_sections:
        multiple = NUMBER_CARD_RE.match(sect)
        if multiple:
            mult = int(multiple.group(1))
            sect = multiple.group(2)
        else:
            mult = 1

        try: 
            card = get_card(sect)
        except KeyError, exception:
            raise parse_common.ParsingError('Failed to find card in line: %s'
                                             % line)
        if return_dict:
            cards[str(card.index)]=mult
        else:
            cards.extend([card] * mult)
    return cards

def parse_turn(log_lines, names_list, trash_pile, trade_route_set, removed_from_supply, masq_targets, previous_name):
    """ Parse the information from a given turn.

    Maintain the trash pile. This is necessary for Forager money counting.
    Maintains the trade route tokens AND the list of all cards gained, which 
    we need to accurately know when Cities are activated.

    Return a dict containing the following fields.  If any of the fields have
    a value that evaluates to False, do not keep it.

    name: player name.
    number: 1 indexed turn number.
    plays: List of cards played.
    buys: List of cards bought.
    gains: List of cards gained.
    trashes: List of cards trashed.
    returns: List of cards returned.
    passes: List of cards passed with Masquerade.
    receives: List of cards received from Masquerade.
    ps_tokens: Number of pirate ship tokens gained.
    vp_tokens: Number of victory point tokens gained.
    money: Amount of money available during entire buy phase.
    opp: Dict keyed by opponent index in names_list, containing dicts with trashes/gains/passes/receives.
    """
    n_players = len(names_list)

    def pile_size(card, n_players):
        if card == dominioncards.Ruins or card == dominioncards.Curse:
            return max((n_players - 1)*10, 10)
        if card == dominioncards.Province:
            if n_players <= 2:
                return 8
            if n_players == 3:
                return 12
            return 12+(n_players - 4)*3
        if card.is_victory():
            if n_players <= 2:
                return 8
            return 12
        if card in [dominioncards.Spoils, dominioncards.Mercenary, 
                dominioncards.Madman] or card.is_ruins() or card.is_shelter():
            return 999 
        if card == dominioncards.Copper:
            if n_players < 5:
                return 60
            return 120
        if card == dominioncards.Silver:
            if n_players < 5:
                return 40
            return 80
        if card == dominioncards.Gold:
            if n_players < 5:
                return 30
            return 60
        if card == dominioncards.Platinum:
            return 12
        if card == dominioncards.Potion:
            return 16
        return 10

    def empty_piles(removed_from_supply, n_players):
        # For cities...
        empty_piles = []

        # First, piles of different cards
        if (sum([removed_from_supply[c] for c in removed_from_supply.keys() if c.is_knight()]) == pile_size(dominioncards.Knights, n_players)):
            empty_piles.append(dominioncards.Knights)
        if (sum([removed_from_supply[c] for c in removed_from_supply.keys() if c.is_ruins()]) == pile_size(dominioncards.Knights, n_players)):
            empty_piles.append(dominioncards.Knights)

        for pile,num in removed_from_supply.items():
            if pile_size(pile, n_players) == num:
                empty_piles.append(pile)
        return empty_piles

    def _delete_if_exists(d, n):
        if n in d:
            del d[n]

    def fix_buys_and_gains(buys, gains):
        """Goko reports each buy and gain separately. This is correct, but
        having everything compatible with iso stats would be nice! So, here
        I 'fix' buys and gains so things which are bought and gained are 
        only reported once, in 'buys', and things which are bought but not
        gained (such as due to trader or possession) are not listed.
        """
        new_buys = []
        for buy in buys:
            if buy in gains:
                gains.remove(buy)
                new_buys.append(buy)
        return (new_buys, gains)

    ret = {PLAYS: [], RETURNS: [], GAINS: [], TRASHES: [], BUYS: [], PASSES: [],
           RECEIVES: []}
    durations = []
    turn_money = 0
    turn_coin_tokens = 0
    vp_tokens = 0
    ps_tokens = 0

    # Keep track of last play, and whether it is still 'active' 
    # for stuff like trashing copper to Moneylender, gaining cards from the
    # trash, etc. Card effects which last more than one line. 
    last_play = None
    harvest_reveal = []
    trashed_to_mercenary = 0
    current_phase = None
    dup_plays_remaining = -1
    done_self_trashing = False
    bom_plays = 0 # For throne room/procession/KC - don't get to rechoose BoM
    bom_choice = None
    bom_processioned = False # to trash it properly
    storeroom_discards = [] 
    done_resolving = True
    coin_tokens = 0

    action_counter = 0 # All this... just for diadem. :/ 

    opp_turn_info = collections.defaultdict(lambda: {GAINS: [], BUYS: [],
                                                     TRASHES: [], PASSES: [],
                                                     RECEIVES:[]})
    while True:
        line = log_lines.pop(0)
        turn_start = START_TURN_RE.match(line)

        if turn_start:
            action_counter = 1
            ret[NAME] = turn_start.group(1)
            ret[NUMBER] = int(turn_start.group(2))
            current_phase = ACTION_PHASE
            if turn_start.group(3):
                ret[POSSESSION] = True
            if previous_name and previous_name not in masq_targets:
                masq_targets[previous_name] = ret[NAME]
            continue

        # empty line ends the turn, clean up and return
        if EMPTY_LINE_RE.match(line):
            # Current goko log bug - does not report 1 VP from Bishop
            vp_tokens += ret[PLAYS].count(dominioncards.Bishop)

            if last_play == dominioncards.Forager and not done_resolving:
                turn_money += sum([d.is_treasure() for d in set(trash_pile)])
            if last_play == dominioncards.Harvest and not done_resolving:
                turn_money += len(set(harvest_reveal))

            money = parse_common.count_money(ret[PLAYS], True) + \
                    turn_money + parse_common.count_money(durations, True) - \
                    durations.count(dominioncards.HorseTraders)*3 

            (buys, gains) = fix_buys_and_gains(ret[BUYS], ret[GAINS])

            ret[BUYS] = indexes(buys)
            ret[PLAYS] = indexes(ret[PLAYS])
            ret[RETURNS] = indexes(ret[RETURNS])
            ret[GAINS] = indexes(gains)
            ret[TRASHES] = indexes(ret[TRASHES])
            ret[PASSES] = indexes(ret[PASSES])
            ret[RECEIVES] = indexes(ret[RECEIVES])
            durations = indexes(durations)
            for opp in opp_turn_info.keys():
                _delete_if_exists(opp_turn_info[opp], 'buy_or_gain')
                parse_common.delete_keys_with_empty_vals(opp_turn_info[opp])

                d = opp_turn_info[opp]
                for k, v in d.iteritems():
                    if k==VP_TOKENS:
                        d[k] = v
                    else:
                        d[k] = indexes(v)

            ret.update({MONEY:money, VP_TOKENS: vp_tokens, 
                PIRATE_TOKENS: ps_tokens, COIN_TOKENS: coin_tokens, OPP: dict(opp_turn_info)})
            return ret



        player_and_rest = HYPHEN_SPLIT_RE.match(line)
        active_player = player_and_rest.group(1)
        action_taken = player_and_rest.group(2)

        # Card-specific processing:
        # Will need to add Stash options whenever stash is implemented.
        # These cards all have unstated effects that last longer than one goko
        # line. For example, Forager will need to count coins after the next
        # 'trash' line - if there is one. Mining Village gives +$2 if trashed - 
        # on the next line after it is played and it draws a card. 
        if (last_play == dominioncards.Forager and not done_resolving and
                KW_TRASHES not in action_taken):
            turn_money += sum([d.is_treasure() for d in set(trash_pile)])
            done_resolving = True
        elif (last_play == dominioncards.MiningVillage and 
                KW_SHUFFLES not in action_taken and
                KW_DRAWS not in action_taken and
                KW_TRASHES not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Tournament and
                KW_REVEALS not in action_taken and
                KW_REVEALS_C not in action_taken and
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Counterfeit and 
                (KW_PLAYS not in action_taken or
                    dominioncards.Spoils not in capture_cards(action_taken))):
            done_resolving = True
        elif (last_play == dominioncards.Thief and 
                KW_TRASHES not in action_taken and
                KW_SHUFFLES not in action_taken and 
                KW_REVEALS not in action_taken and 
                KW_REVEALS_C not in action_taken and 
                KW_DISCARDS not in action_taken and 
                KW_DISCARDS_C not in action_taken and 
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.NobleBrigand and 
                KW_GAINS in action_taken and 
                dominioncards.NobleBrigand in capture_cards(action_taken)):
            done_resolving = True
        elif (last_play == dominioncards.NobleBrigand and 
                KW_TRASHES not in action_taken and
                KW_SHUFFLES not in action_taken and 
                KW_REVEALS not in action_taken and 
                KW_REVEALS_C not in action_taken and 
                KW_DISCARDS not in action_taken and 
                KW_DISCARDS_C not in action_taken and 
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Rogue and 
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Graverobber and 
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Mercenary and 
                KW_TRASHES not in action_taken and
                KW_REVEALS not in action_taken and 
                KW_DRAWS not in action_taken and 
                KW_PLACES not in action_taken and 
                KW_GAINS not in action_taken and 
                KW_SHUFFLES not in action_taken):
            done_resolving = True
            trashed_to_mercenary = 0
        elif (last_play == dominioncards.Moneylender and 
                (KW_TRASHES not in action_taken or
                    dominioncards.Copper not in capture_cards(action_taken))):
            done_resolving = True
        elif (last_play == dominioncards.Salvager and 
                KW_TRASHES not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Baron and 
                (KW_DISCARDS not in action_taken or 
                    dominioncards.Estate not in capture_cards(action_taken))):
            done_resolving = True
        elif (last_play == dominioncards.Harvest and 
                KW_REVEALS not in action_taken and 
                KW_REVEALS_C not in action_taken and 
                KW_SHUFFLES not in action_taken):
            turn_money += len(set(harvest_reveal))
            harvest_reveal = []
            done_resolving = True
        elif (last_play == dominioncards.BandofMisfits and 
                KW_CHOOSES not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Ironmonger and 
                KW_DRAWS not in action_taken and 
                KW_SHUFFLES not in action_taken and 
                KW_REVEALS_C not in action_taken and 
                KW_REVEALS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Ironworks and 
                KW_GAINS not in action_taken):
            done_resolving = True
        elif (last_play == dominioncards.Storeroom and 
                KW_DISCARDS not in action_taken and 
                KW_DRAWS not in action_taken and 
                KW_SHUFFLES not in action_taken):
            turn_money += len(storeroom_discards)
            storeroom_discards = []
            done_resolving = True

        if KW_PLAYS in action_taken:
            played = capture_cards(action_taken)
            ret[PLAYS].extend(played)

            # special cases 
            for play in played: 
                if play.is_action():
                    if not(play == dominioncards.Cultist and play == last_play) and play != dominioncards.BandofMisfits:
                        action_counter -= 1
                action_counter += play.num_plus_actions()
                if bom_choice is not None:
                    if bom_plays == 0:
                        bom_choice = None
                    else:
                        bom_plays -= 1

                if dup_plays_remaining >= 0 and play != dominioncards.BandofMisfits:
                    dup_plays_remaining -= 1
                if dup_plays_remaining < 0:
                    done_self_trashing = False

                if play.is_treasure():
                    phase = BUY_PHASE
                elif (last_play == dominioncards.ThroneRoom or 
                        last_play == dominioncards.Procession or 
                        last_play == dominioncards.Golem):
                    action_counter += 2 
                elif last_play == dominioncards.KingsCourt:
                    action_counter += 3 

                if play == dominioncards.PoorHouse:
                    turn_money += 4 # Subtraction will happen later
                elif play == dominioncards.ThroneRoom or play == dominioncards.Procession:
                    dup_plays_remaining = 2
                elif play == dominioncards.KingsCourt:
                    dup_plays_remaining = 3
                elif play == dominioncards.Madman and dup_plays_remaining <= 0:
                    ret[RETURNS].append(play)
                elif play == dominioncards.Spoils:
                    # Spoils always get returned on play...
                    # ...unless it's Counterfeited. 
                    # Technically, this clause will be incorrect if someone
                    # plays a counterfeit, selects no treasure to counterfeit, 
                    # and then just plays a spoils. 
                    if (last_play != dominioncards.Counterfeit or 
                        done_resolving):
                        ret[RETURNS].append(play)
                elif play == dominioncards.TradeRoute:
                    turn_money += len(trade_route_set)
                elif play == dominioncards.Tournament:
                    turn_money += 1 # Might be canceled out later
                elif play == dominioncards.Diadem:
                    turn_money += action_counter
                elif play == dominioncards.BandofMisfits:
                    bom_processioned = False
                    if last_play == dominioncards.ThroneRoom:
                        bom_plays = 2
                    elif last_play == dominioncards.Procession:
                        bom_plays = 2
                        bom_processioned = True
                    elif last_play == dominioncards.KingsCourt:
                        bom_plays = 3
                    else:
                        bom_plays = 1
                elif play == dominioncards.Conspirator and len(ret[PLAYS]) > 2:
                    action_counter += 1
                elif (play == dominioncards.Crossroads and 
                        ret[PLAYS].count(dominioncards.Crossroads) == 1):
                    action_counter += 3
                elif play == dominioncards.City:
                    if len(empty_piles(removed_from_supply, n_players)) >= 2:
                        turn_money += 1
                    
                last_play = play
                done_resolving = False
            continue

        if KW_BUYS in action_taken:
            buys = capture_cards(action_taken)
            ret[BUYS].extend(buys)

            # easier to deal with the on-buy attack by making it a fake play
            if dominioncards.NobleBrigand in buys:
                last_play == dominioncards.NobleBrigand  
                done_resolving = False
            continue

        if KW_RETURNS in action_taken:
            returned = capture_cards(action_taken)
            ret[RETURNS].extend(returned)
            for r in returned:
                removed_from_supply[r] -= 1
            continue

        if KW_GAINS in action_taken:
            gained = capture_cards(action_taken)
            trade_route_set.update([g for g in gained if g.is_victory()])

            if active_player == ret[NAME]:
                ret[GAINS].extend(gained)
                if(not done_resolving and (last_play == dominioncards.Thief or 
                    last_play == dominioncards.NobleBrigand) and 
                    dominioncards.Mercenary not in gained):
                    for c in gained:
                        if not c.is_treasure():
                            done_resolving = True
                        else:
                            if c in trash_pile:
                                # Early goko logs have bugs with who reported
                                # trashing cards. 
                                trash_pile.remove(c)
                if(not done_resolving and (last_play == dominioncards.Rogue or 
                    last_play == dominioncards.Graverobber) and 
                    dominioncards.Mercenary not in gained):
                    for c in gained:
                        if c in trash_pile:
                            # BoM as death cart is ambiguous
                            trash_pile.remove(c)
                        done_resolving = True
                else:
                    for g in gained:
                        removed_from_supply[g] += 1

                if (last_play == dominioncards.Ironworks and 
                      not done_resolving):
                    if gained[0].is_treasure():
                        turn_money += 1
                    if gained[0].is_action():
                        action_counter += 1
                    done_resolving = True
            else:
                opp_turn_info[str(names_list.index(active_player))][GAINS].extend(gained)
                for g in gained:
                    removed_from_supply[g] += 1
            continue

        # Some old Goko logs mis-attribute trashing from attacks. I'm not 
        # going to special-case all the various goko bugs that have since been
        # fixed, though. So there will be bugs with some old logs.
        if KW_TRASHES in action_taken:
            trashed = capture_cards(action_taken)

            if active_player == ret[NAME]:

                # Making TR-feast not doublecount Feast trashing
                if(last_play not in trashed or not last_play.can_trash_self()):
                    done_self_trashing = False
                if (dup_plays_remaining >= 0 and last_play in trashed and done_self_trashing and last_play.can_trash_self()):
                    trashed.remove(last_play) #TR+feast
                if (last_play in trashed and dup_plays_remaining > 0 and last_play.can_trash_self()):
                    done_self_trashing = True


                if (last_play == dominioncards.MiningVillage and
                    not done_resolving and 
                    dominioncards.MiningVillage in trashed):
                    turn_money += 2
                elif (last_play == dominioncards.Moneylender and 
                      not done_resolving and 
                      dominioncards.Copper in trashed):
                    turn_money += 3
                elif last_play == dominioncards.Salvager and not done_resolving:
                    turn_money += trashed[0].coin_cost
                elif last_play == dominioncards.Mercenary and not done_resolving:
                    trashed_to_mercenary += len(trashed)
                    if trashed_to_mercenary == 2:
                        turn_money += 2
                        done_resolving = True
                        trashed_to_mercenary = 0

                while dominioncards.Fortress in trashed:
                    trashed.remove(dominioncards.Fortress)
                if trashed == bom_choice and (bom_choice[0].can_trash_self() or bom_processioned): 
                    trashed = [dominioncards.BandofMisfits]
                if (bom_choice is not None and
                        dominioncards.TreasureMap in bom_choice and
                        dominioncards.TreasureMap in trashed):
                    trashed.remove(dominioncards.TreasureMap)
                    trashed.extend([dominioncards.BandofMisfits])


                if POSSESSION not in ret:
                    ret[TRASHES].extend(trashed)
                    trash_pile.extend(trashed)

                if last_play == dominioncards.Forager and not done_resolving:
                    turn_money +=sum([d.is_treasure() for d in set(trash_pile)])
                    done_resolving = True

            else:
                while dominioncards.Fortress in trashed:
                    trashed.remove(dominioncards.Fortress)
                opp_turn_info[str(names_list.index(active_player))][TRASHES].extend(trashed)
                trash_pile.extend(trashed)

            if last_play in [dominioncards.MiningVillage, dominioncards.Forager, dominioncards.Salvager]:
                done_resolving = True
            continue

        match = USES_COIN_TOKENS_RE.match(action_taken)
        if match:
            turn_money += int(match.group(1))
            turn_coin_tokens -= int(match.group(1))
            continue

        match = RECEIVES_COIN_TOKENS_RE.match(action_taken)
        if match:
            turn_coin_tokens += int(match.group(1))
            continue

        if KW_PASSES in action_taken:
            passed_cards = capture_cards(action_taken)
            receiver = masq_targets[active_player]

            if active_player == ret[NAME]:
                ret[PASSES].extend(passed_cards)
            else:
                opp_turn_info[str(names_list.index(active_player))][PASSES].extend(passed_cards)
            if receiver == ret[NAME]:
                ret[RECEIVES].extend(passed_cards)
            else:
                opp_turn_info[str(names_list.index(receiver))][RECEIVES].extend(passed_cards)

            continue

        if KW_DURATION in action_taken:
            duration = capture_cards(action_taken)
            durations.extend(duration)
            for d in duration:
                if d in [dominioncards.FishingVillage, dominioncards.Tactician]:
                    action_counter += 1
            continue

        if (KW_CHOOSES_TWO_CARDS_AND_ONE_ACTION in action_taken or 
                KW_RECEIVES_ONE_ACTION in action_taken):
            action_counter += 1
            continue 

        if KW_CHOOSES_TWO_COINS in action_taken:
            turn_money += 2
            continue

        if KW_CHOOSES in action_taken:
            if last_play == dominioncards.BandofMisfits and not done_resolving:
                bom_choice = capture_cards(action_taken)
            if bom_choice[0] == dominioncards.Knights:
                bom_choice[0] == dominioncards.SirMartin
            continue

        if KW_PIRATE_COIN in action_taken:
            ps_tokens += 1
            continue

        if KW_VP_CHIPS in action_taken:
            vp_chips_match = VP_CHIPS_RE.match(action_taken)
            vp_tokens += int(vp_chips_match.group(1))
            continue

        match = TAKES_COINS_RE.match(action_taken)
        if match:
            turn_money += int(match.group(1))
            continue

        match = RECEIVES_COINS_RE.match(action_taken)
        if match:
            turn_money += int(match.group(1))
            continue

        match = TAKES_ACTIONS_RE.match(action_taken)
        if match:
            action_counter += int(match.group(1))
            continue

        match = RECEIVES_ACTIONS_RE.match(action_taken)
        if match:
            action_counter += int(match.group(1))
            continue
        if KW_DISCARDS in action_taken or KW_DISCARDS_C in action_taken:
            if (dominioncards.Estate in capture_cards(action_taken) and 
                    last_play == dominioncards.Baron and 
                    not done_resolving):
                turn_money += 4
                done_resolving = True
            elif (last_play == dominioncards.SecretChamber):
                turn_money += len(capture_cards(action_taken))
            elif (last_play == dominioncards.Vault and 
                    active_player == ret[NAME]):
                turn_money += len(capture_cards(action_taken))
            elif (last_play == dominioncards.Storeroom and not done_resolving):
                storeroom_discards.extend(capture_cards(action_taken))
            continue

        if (KW_REVEALS_HAND in action_taken):
            if last_play == dominioncards.PoorHouse and not done_resolving:
                turn_money -= len([tr for tr in capture_cards(action_taken) if tr.is_treasure()])
                if turn_money < 0:
                    turn_money = 0
            continue


        if (KW_REVEALS in action_taken or KW_REVEALS_C in action_taken):
            if last_play == dominioncards.Harvest:
                harvest_reveal.extend(capture_cards(action_taken))
            elif last_play == dominioncards.Herald:
                c = capture_cards(action_taken)
                if len(c) > 0:
                    if c[0].is_action():
                        action_counter += 1 
                        if bom_plays > 0:
                            bom_plays += 1
                        if dup_plays_remaining > 0:
                            dup_plays_remaining += 1
            elif last_play == dominioncards.Golem:
                action_counter += len([c for c in capture_cards(action_taken)if (c.is_action() and not c == dominioncards.Golem)])
            elif (last_play == dominioncards.Tournament and 
                not done_resolving and active_player != ret[NAME] and 
                dominioncards.Province in capture_cards(action_taken)):
                turn_money -= 1
                done_resolving = True
            elif (last_play == dominioncards.Ironmonger and not done_resolving):
                if capture_cards(action_taken)[0].is_treasure():
                    turn_money += 1
                if capture_cards(action_taken)[0].is_action():
                    action_counter += 1
                done_resolving = True
            continue

        if KW_DRAWS in action_taken: 
            if last_play == dominioncards.Storeroom:
                storeroom_discards = []
            continue
        # All remaining actions should be captured; the next few statements
        # are those which are not logged in any way (though they could be!)

        if (KW_LOOKS_AT in action_taken or 
            KW_RECEIVES in action_taken or 
            KW_PLACES in action_taken or 
            KW_SETS_ASIDE in action_taken or 
            KW_TAKES in action_taken or
            KW_EMBARGOES in action_taken or 
            KW_OVERPAYS in action_taken or 
            KW_NAMES in action_taken or 
            KW_CARDS_IN_DISCARDS in action_taken or
            KW_APPLIED in action_taken or 
            KW_APPLIES_WHEN_TRASHED in action_taken or 
            KW_MOVES in action_taken or 
            KW_MOVES_DECK_TO_DISCARD in action_taken or 
            KW_SCHEME_CHOICE in action_taken or 
            KW_SHUFFLES in action_taken or 
            KW_TAKES_SET_ASIDE in action_taken):
            continue

        raise parse_common.BogusGameError('Line did not match any keywords!')


def parse_turns(log_lines, names_list, removed_from_supply):
    """
    Sequentially go through the log and parse the game, splitting it into turns.

    Also handle outpost and possession turns here.
    They require cross-turn information from the end of the *previous* turn.

    In the case of Outpost played during Possession turn, this will mark the 
    WRONG turn as being an outpost turn, but will still mark one of them. 

    Needs number of players so parse_turn can accurately track when vp card 
    piles have run out, to accurately report number of coins Cities give.

    Starting decks are removed from supply (count supply for city empty piles)
    """
    turns = [];
    trash_pile = [];
    trade_route_set = set([])

    masq_targets = {}
    
    previous_name = None # for Possession and Masq
    while not GAME_OVER_RE.match(log_lines[0]):
        turn = parse_turn(log_lines, names_list, trash_pile, trade_route_set, 
                          removed_from_supply, masq_targets, previous_name)
        if POSSESSION in turn:
            turn['pname'] = previous_name
        elif(len(turns) > 0 and turn[NAME] == turns[-1][NAME] and 
           POSSESSION not in turn and  POSSESSION not in turns[-1]):
            turn[OUTPOST] = True
            previous_name = turn[NAME]
        else:
            turn['turn_no'] = True
            previous_name = turn[NAME]
        turns.append(turn)

    log_lines.pop(0)
    return turns



def associate_turns_with_owner(game_dict, turns, dubious_check):
    """ Move each turn in turns to be a member of the corresponding player
    in game_dict.

    Remove the names from the turn, since it is redundant with the name
    on the player level dict."""
    name_to_owner = {}
    for idx, deck in enumerate(game_dict[DECKS]):
        name_to_owner[deck[NAME]] = deck
        deck[TURNS] = []

    order_ct = 0

    for idx, turn in enumerate(turns):
        owner = name_to_owner[turn[NAME]]
        owner[TURNS].append(turn)
        if not ORDER in owner:
            owner[ORDER] = idx + 1
            order_ct += 1
        del turn[NAME]

    if order_ct != len(game_dict[DECKS]) and dubious_check:
        # This may be okay! Only raise if dubious_check
        raise parse_common.BogusGameError('Did not find turns for all players')

def parse_endgame(log_lines):
    """
    Parses the endgame section of a goko log.
    Everything after the Game Over line. Puts results directly in the game dict.

    Cannot calculate game_end; the trash is not restated in the endgame section,
    so there isn't necessarily a way to know why the game ended without going 
    through the whole game. 
    """

    decks = []
    while not KW_PLACE in log_lines[0]:
        resigned = False
        line = log_lines.pop(0)
        hyphen_split_match = HYPHEN_SPLIT_RE.match(line)
        name = hyphen_split_match.group(1)

        if KW_RESIGNED in hyphen_split_match.group(2) or KW_QUIT in hyphen_split_match.group(2):
            resigned = True
            line = log_lines.pop(0)
            hyphen_split_match = HYPHEN_SPLIT_RE.match(line)
            name = hyphen_split_match.group(1)

        deck_comp = capture_cards(hyphen_split_match.group(2), True)

        line = log_lines.pop(0)
        vp_chip_match = ENDGAME_VP_CHIP_RE.match(line)
        if vp_chip_match:
            vp_tokens = int(vp_chip_match.group(1))
            line=log_lines.pop(0)
        else:
            vp_tokens = 0

        points_match = ENDGAME_POINTS_RE.match(line)
        total_vp = int(points_match.group(1))
        
        # line which says how many turns there were
        log_lines.pop(0)
        # blank line
        log_lines.pop(0)

        # Handle resignations here; give fake -1 point
        if resigned:
            total_vp = -1

        decks.append({NAME: name, POINTS: total_vp, RESIGNED: resigned,
                      DECK: deck_comp, VP_TOKENS: vp_tokens})
    return decks

def parse_game(game_str, dubious_check = False):
    """ Parse game_str into game dictionary.

    game_str: Entire contents of a log file from goko.
    dubious_check: If true, raise a BogusGame exception if the game is
      suspicious.

    returns a dict with the following fields:
      decks: A list of player decks, as documented in parse_endgame.
      start_decks: A list of player starting decks. Usually 7c3e. 
      supply: A list of cards in the supply.
      players: A list of normalized player names.
      game_end: List of cards exhausted that caused the game to end.
      resigned: True iff some player in the game resigned..
    """

    # Goko logs are not split into sections by an obvious separator
    # So analyze sequentially, by lines
    log_lines = game_str.split('\n')

    game_dict = parse_header(log_lines)
    # start_decks, players, and supply are now set

    validate_names(game_dict, dubious_check)
    game_dict[VETO] = {}

    # So much work just to know when two piles are empty for cities! 
    # Here, need to account for number of coppers/zapped silvers in all start
    # decks. Can't get estates to work with zapped start decks and shelters... 
    removed_from_supply = collections.defaultdict(lambda: 0)
    for d in game_dict[START_DECKS]:
        for c in d[START_DECK]:
            card = index_to_card(c)
            if card != dominioncards.Estate and not card.is_shelter():
                removed_from_supply[card] += 1

    turns = parse_turns(log_lines, game_dict[PLAYERS], removed_from_supply)
    decks = parse_endgame(log_lines)
    game_dict[DECKS] = decks
    associate_turns_with_owner(game_dict, turns, dubious_check)
    return game_dict
