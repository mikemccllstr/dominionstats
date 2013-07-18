#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Parse raw iso game into JSON list of game documents."""

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

SECTION_SEP = re.compile('^----------------------$', re.MULTILINE)

NORM_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s turn (?P<turn_no>\d+) ---")
POSS_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s turn \(possessed by (?P<pname>.*)\) ---")
OUTPOST_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s " + re.escape(
        "extra turn (from <span class=card-duration>Outpost</span>)"))

TURN_HEADER_NO_GROUP_RE = re.compile("--- .+'s turn [^-]* ---")
SPLIT_COMMA_AND_RE = re.compile(',| and ')
NUMBER_BEFORE_SPAN = re.compile('(\d+) <span')
NUMBER_COPIES = re.compile('(0|2) copies to')
GETTING_MONEY_RE = re.compile(' \+\$(\d)+')
WHICH_IS_WORTH_RE = re.compile(' which is worth \+\$(\d)+')
FOR_MONEY_RE = re.compile(' for \+\$(\d)+')
VP_TOKEN_RE = re.compile(u'(?P<num>\d+) ▼', re.UNICODE)

KW_ANOTHER_ONE = 'another one'
KW_BUYS = ' buys '
KW_DISCARDS = ' discards '
KW_GAINING = ' gaining '
KW_DRAWS = ' draws '
KW_GAINS_A = ' gains a'
KW_GAMES_A = ' games a'  # short lived bug in iso, spelled gains as games
KW_FOR_MONEY = ' for +$'
KW_GAINS_THE = ' gains the '
KW_GET = 'get +'
KW_GETS = ' gets +'
KW_GETTING = ' getting +'
KW_IS_TRASHED = ' is trashed.'
KW_PLAYING = ' playing '
KW_PLAYS = ' plays '
KW_REPLACING = ' replacing '
KW_RETURNING = ' returning '
KW_REVEALING = ' revealing '
KW_REVEALS = ' reveals '
KW_REVEALS_A = ' reveals a'
KW_TOKEN = ' token.'
KW_TO_THE_SUPPLY = ' to the supply'
KW_TRASHES = ' trashes '
KW_TRASHES_IT = 'trashes it.'
KW_TRASHING = ' trashing '
KW_TURNS_UP_A = ' turns up a'
KW_WHICH_IS_WORTH = ' which is worth +$'
KW_WITH_A = ' with a'
KW_WISHING = ' wishing '
KW_INSTEAD = ' instead.'


KEYWORDS = [locals()[w] for w in dict(locals()) if w.startswith('KW_')]

def capture_cards(line):
    """ Given a line of text from isotropic, extract the cards.

    line: string like 'Rob plays a <span class=card-none>Minion</span>.'
    returns: list of the card objects, eg, [Minion]
    """
    def _as_int_or_1(string_val):
        try:
            return int(string_val)
        except ValueError:
            return 1

    cards = []
    card_sections = SPLIT_COMMA_AND_RE.split(line)
    for sect in card_sections:
        split_at_span = sect.split('<span')
        if not split_at_span:
            continue
        first = split_at_span[0]
        split_first = first.split()
        if not split_first:
            mult = 1
        else:
            mult = _as_int_or_1(split_first[-1])

        for subsect in split_at_span:
            start_of_end_span = subsect.find('</span')
            if start_of_end_span == -1:
                continue
            end_of_begin_span = subsect.rfind('>', 0, start_of_end_span)
            if end_of_begin_span == -1:
                continue
            maybe_plural = subsect[end_of_begin_span + 1:
                                   start_of_end_span]
            if maybe_plural == '&diams;':
                continue
            try:
                card = get_card(maybe_plural)
            except KeyError, exception:
                raise parse_common.ParsingError('Failed to find card in line: %s'
                                                % line)
            cards.extend([card] * mult)
    return cards

def associate_game_with_norm_names(game_dict):
    """ Fill players field in game_dict with list of normed player names."""
    game_dict[PLAYERS] = []
    for player_deck in game_dict[DECKS]:
        normed_name = name_merger.norm_name(player_deck[NAME])
        game_dict[PLAYERS].append(normed_name)

ONLY_NUMBERS_RE = re.compile('^\d+$')

def validate_names(decks):
    """ Raise an exception for names that might screw up the parsing.
    This should happen in less than 1% of real games, but it's just easier
    to punt on annoying inputs that to make sure we get them right.
    
    Different keywords for goko and iso, naturally."""
    used_names = set()
    for deck in decks:
        name = deck[NAME]
        if name in used_names:
            raise parse_common.BogusGameError('Duplicate name %s' % name)
        used_names.add(name)

        if name in ['a', 'and', 'turn']:
            raise parse_common.BogusGameError("annoying name " + name)
        if '---' in name:
            raise parse_common.BogusGameError('--- in name ' + name)

        if ONLY_NUMBERS_RE.match(name):
            raise parse_common.BogusGameError('name contains only numbers ' + name)

        if name[0] == '.':
            raise parse_common.BogusGameError('name %s starts with period' % name)
        for kword in KEYWORDS:
            if kword.lstrip() in name or kword.rstrip() in name:
                raise parse_common.BogusGameError('name %s contains keyword %s' % 
                                                  (name, kword))

    if len(used_names) != len(decks):
        raise parse_common.BogusGameError('not everyone took a turn?')
    if len(decks) <= 1:
        raise parse_common.BogusGameError('only one player')

def canonicalize_names(turns_str, player_names):
    """ Return a new string in which all player names are replaced by
    player0, player1, ..."""
    player_ind_name_pairs = list(enumerate(player_names))
    # Replace longer names first, short names might contain the longer ones.
    player_ind_name_pairs.sort(key = lambda ind_name_pair:
                               -len(ind_name_pair[1]))
    for idx, player in player_ind_name_pairs:
        # This is complicated (matching extra stuff to the left and right
        # of name rather than straight string replace) so that we
        # can allow for annoying names like 'd' that occur as
        # substrings of regular text.
        match_player_name = re.compile(
            '(^|[ \(])' +       # start with newline, space, or open paren
            re.escape(player) + # followed by player name
            "([ '\)])",         # ending with space or ' or close paren
            re.MULTILINE)
        def _replace_name_by_label(match):
            """ keep surrounding delims, replace player name with playerX"""
            return match.group(1) + parse_common._player_label(idx) + match.group(2)
        turns_str = match_player_name.sub(_replace_name_by_label, turns_str)

    return turns_str

def parse_header(header_str):
    """ Parse the isotropic header string.

    Return a dictionary with game_end, supply, and resigned fields,
      like parse_game.
    """
    sections = [s for s in header_str.replace(' \n', '\n').split('\n\n') if s]
    end_str, supply_str = sections
    assert 'gone' in end_str or 'resigned' in end_str, "Not gone or resigned"
    if 'gone' in end_str:
        resigned = False
        gone = capture_cards(end_str.split('\n')[1])
    else:
        resigned = True
        gone = []
    supply = indexes(capture_cards(supply_str))
    return {GAME_END: indexes(gone), SUPPLY: supply, RESIGNED: resigned}

PLACEMENT_RE = re.compile('#\d (.*)')
POINTS_RE = re.compile(': (-*\d+) point(s?)(\s|(' + re.escape('</b>') + '))')

def make_start_decks(names):
    """ 
    Given list of players, make 7xCopper 3xEstate starting decks for each.
    New code for iso logs to match information that is available on goko.
    Shelters were (almost) never present on iso, so 7C3E is the start deck.
    """
    start_decks = []
    for name in names:
        start_decks.append({NAME:name, START_DECK: indexes([dominioncards.Copper]*7+[dominioncards.Estate]*3) })
    return start_decks


def parse_deck(deck_str):
    """ Given an isotropic deck string, return a dictionary containing the
    player names

    deck_str: starts with placement and name, ends with last card in deck.
    returns dictionary containing the following fields
      name:
      vp_tokens: number of vp tokens.
      deck: Dictionary keyed card name who value is the card frequency.
      resigned: True iff this player resigned
      """
    try:
        name_vp_list, _opening, deck_contents = deck_str.split('\n')
    except ValueError, e:
        raise parse_common,ParsingError('Failed to split the deck')
    vp_tokens = 0
    #print 'vp', name_vp_list

    matched_points = POINTS_RE.search(name_vp_list)

    if matched_points:
        point_loc = matched_points.end()
        resigned, points  = False, int(matched_points.group(1))
        name_points, vp_list = (name_vp_list[:point_loc],
                                name_vp_list[point_loc + 1:])
    else:
        resign_loc = name_vp_list.find('resigned')
        assert resign_loc != -1, 'could not find resign in %s' % name_vp_list
        resigned, points = True, -100
        name_points, vp_list = (name_vp_list[:resign_loc],
                                name_vp_list[resign_loc + 1:])

    last_colon_in_name_points = name_points.rfind(':')
    name, _points_or_resign = (name_points[:last_colon_in_name_points],
                               name_points[last_colon_in_name_points + 1:])

    def cleanup_name(name):
        """ Given a name and placement, get rid of the bold tags and  """
        htmlless_name = name.replace('<b>', '').replace('</b>', '')
        placement_match = PLACEMENT_RE.match(htmlless_name)
        if placement_match:
            return placement_match.group(1)
        return htmlless_name

    name = cleanup_name(name)

    for chunk in vp_list.split(','):
        diamond_loc = chunk.find(u'▼')
        if diamond_loc != -1:
            start_point_loc = max(chunk.rfind('(', 0, diamond_loc - 1),
                                  chunk.rfind(' ', 0, diamond_loc - 1))
            vp_tokens = int(chunk[start_point_loc + 1:diamond_loc - 1])

        card_list_chunks = deck_contents[
            deck_contents.find(']') + 1:].replace(',', ' ')
        card_blobs = [x for x in card_list_chunks.split('</span>') if
                      '<span' in x]
        deck_comp = {}
        for card_blob in card_blobs:
            right_bracket_index = card_blob.find('>')
            card_name = card_blob[right_bracket_index + 1:]
            try:
                card = get_card(card_name)
            except KeyError, exception:
                raise parse_common.ParsingError("Failed to get card. chunk: '%s', card_name: '%s', card_blob: '%s'" % \
                                       (chunk, card_name, card_blob[right_bracket_index - 10:]))
            card_quant = int(card_blob.split()[0])
            deck_comp[str(card.index)] = card_quant
    #FIXME: deck_comp is undefined if there's no vp_list
    return {NAME: name, POINTS: points, RESIGNED: resigned,
            DECK: deck_comp, VP_TOKENS: vp_tokens}

def parse_decks(decks_blob):
    """ Parse and return a list of decks"""
    deck_blobs = [s for s in decks_blob.split('\n\n') if s]
    return [parse_deck(deck_blob) for deck_blob in deck_blobs]

VETO_RE = re.compile('(.*) vetoes (.*)\.')
def parse_vetoes(game_dict, veto_str):
    matches = VETO_RE.findall(veto_str)
    v_dict = {}
    if matches:
        for (player, card) in matches:
            # Use the player index number (as a string) as the
            # dictionary key, instead of the player's name, because
            # some names contain periods, which are invalid keys for
            # structures stored in MongoDB.
            player = name_merger.norm_name(player)
            try:
                v_dict[str(game_dict[PLAYERS].index(player))] = int(capture_cards(card)[0].index)
            except ValueError, ve:
                raise parse_common.ParsingError("Failed to handle veto: %s" % ve)

    return v_dict

def associate_turns_with_owner(game_dict, turns):
    """ Move each turn in turns to be a member of the corresponding player
    in game_dict.

    Remove the names from the turn, since it is redundant with the name
    on the player level dict."""
    name_to_owner = {}
    for idx, deck in enumerate(game_dict[DECKS]):
        deck[NAME] = name_merger.norm_name(deck[NAME])
        name_to_owner[deck[NAME]] = deck
        deck[TURNS] = []

    order_ct = 0

    for idx, turn in enumerate(turns):
        owner = name_to_owner[name_merger.norm_name(turn[NAME])]
        owner[TURNS].append(turn)
        if not ORDER in owner:
            owner[ORDER] = idx + 1
            order_ct += 1
        del turn[NAME]

    if order_ct != len(game_dict[DECKS]):
        raise parse_common.BogusGameError('Did not find turns for all players')

def name_and_rest(line, term):
    """ Split line about term, return (before, after including term). """
    start_of_term = line.find(term)
    assert start_of_term != -1, "start_of_term is -1"

    def _strip_leading(val, dead_chars):
        for idx, char in enumerate(val):
            if char not in dead_chars:
                return val[idx:]
        return ''

    name = _strip_leading(line[:start_of_term], ' .').strip()
    return name, line[start_of_term + len(term):]


class PlayerTracker(object):
    ''' The player tracker is used to keep track of the active player being
    modified by the gain and trashes actions in a sequence of isotropic
    game lines. '''

    def __init__(self):
        self.player_stack = [None]
        self.orig_player = None

    def get_active_player(self, line):
        ''' Feed the next line to the tracker, it returns the active player.'''
        mentioned_players = self._get_player_inds(line)

        indent_level = line.count('...')
        if indent_level >= len(self.player_stack):
            self.player_stack.append(self.player_stack[-1])
        while len(self.player_stack) > indent_level + 1:
            self.player_stack.pop()

        if len(mentioned_players) > 0:
            self.player_stack[-1] = mentioned_players[-1]
            if self.orig_player is None:
                self.orig_player = mentioned_players[-1]

        return self.player_stack[-1]

    def current_player(self):
        ''' Return the player whose turn it is.
        This requires at least one call to get_active_player() first. '''
        return self.orig_player

    def _get_player_inds(self, line):
        '''return list of player indicies in given line.
        eg, line "player1 trashes player2's ..." -> [1, 2]
        '''
        return map(int, parse_common.PLAYER_IND_RE.findall(line))


def parse_turn_header(turn_header_line, names_list = None):
    """ Given a turn header line return a dictionary containing
    information about the turn.  All turns have a player name in the key
    'name'.

    Normal turns have a 'turn_no'.
    Possession turns have a 'pname' for the name of the possessor.
    Outpost turns have the 'outpost' value set to true."""

    # This could be done with a single really complicated regexp, but I kept
    # screwing up the regexp when I tried to join them, and so here we
    # have some code to match against the three different cases.

    def _get_name(match, name_key = 'name'):
        if names_list is None:
            return match.group(name_key)
        return parse_common._get_real_name(match.group(name_key), names_list)

    parsed_header = {}
    norm_match = NORM_TURN_HEADER_RE.search(turn_header_line)
    if norm_match:
        parsed_header['turn_no'] = int(norm_match.group('turn_no'))
        parsed_header['name'] = _get_name(norm_match)
        return parsed_header

    poss_match = POSS_TURN_HEADER_RE.search(turn_header_line)
    if poss_match:
        parsed_header['name'] = _get_name(poss_match)
        parsed_header['pname'] = _get_name(poss_match, 'pname')
        return parsed_header

    out_match = OUTPOST_TURN_HEADER_RE.search(turn_header_line)
    if out_match:
        parsed_header['name'] = _get_name(out_match)
        parsed_header['outpost'] = True
        return parsed_header

    raise parse_common.ParseTurnHeaderError(turn_header_line)


def parse_turn(turn_blob, names_list):
    """ Parse the information from a given turn.

    Return a dict containing the following fields.  If any of the fields have
    a value that evaluates to False, do not keep it.

    name: player name.
    number: 1 indexed turn number.
    plays: List of cards played.
    buys: List of cards bought.
    gains: List of cards gained.
    trashes: List of cards trashed.
    returns: List of cards returned.
    ps_tokens: Number of pirate ship tokens gained.
    vp_tokens: Number of victory point tokens gained.
    money: Amount of money available during entire buy phase.
    opp: Dict keyed by opponent index in names_list, containing dicts with trashes/gains.
    """
    lines = turn_blob.strip().split('\n')
    header = lines[0]
    parsed_header = parse_turn_header(header, names_list)

    poss, outpost = False, False

    if 'pname' in parsed_header:
        possessee_name = parsed_header['name']
        possessee_index = names_list.index(possessee_name)
        poss = True
    if 'outpost' in parsed_header:
        outpost = True

    ret = {GAINS: [], TRASHES: [], BUYS: []}
    plays = []
    returns = []
    turn_money = 0
    vp_tokens = 0
    ps_tokens = 0
    opp_turn_info = collections.defaultdict(lambda: {GAINS: [],
                                                     TRASHES: [],
                                                     BUYS: []})
    tracker = PlayerTracker()

    for line_idx, line in enumerate(lines):
        active_player = tracker.get_active_player(line)
        if active_player == tracker.current_player():
            targ_obj = ret
        else:
            # Stop using the player's name here, as it is used as a
            # key name in a dict, which can't be stored in MongoDB if
            # it contains a dot ('.') or starts with a dollar
            # sign. Instead, use the player index number so we can
            # extract the name later.
            #
            # targ_obj = opp_turn_info[names_list[active_player]]
            targ_obj = opp_turn_info[str(active_player)]

        has_trashing = KW_TRASHING in line
        has_trashes = KW_TRASHES in line
        has_gaining = KW_GAINING in line
        orig_buys_len = len(targ_obj.get(BUYS, []))
        orig_gains_len = len(targ_obj.get(GAINS, []))

        did_trading_post_gain = False

        if has_trashes:
            if has_gaining:
                # Trading post turn, first trashes, then gaining
                gain_start = line.find(KW_GAINING)
                targ_obj[TRASHES].extend(capture_cards(line[:gain_start]))
                targ_obj[GAINS].extend(capture_cards(line[gain_start:]))
                did_trading_post_gain = True
            else:
                targ_obj[TRASHES].extend(capture_cards(line))
        if KW_WITH_A in line:
            if KW_REPLACING in line:
                new_gained_portion = line[line.find(KW_WITH_A):]
                targ_obj[GAINS].extend(capture_cards(new_gained_portion))
        if KW_PLAYS in line or KW_PLAYING in line:
            plays.extend(capture_cards(line))
        if has_gaining and not did_trading_post_gain:
            if KW_ANOTHER_ONE in line: # mints a gold gaining another one
                targ_obj[GAINS].extend(capture_cards(line))
            else:
                # gaining always associated with current player?
                targ_obj[GAINS].extend(
                    capture_cards(line[line.find(KW_GAINING):]))
        if KW_BUYS in line:
            targ_obj[BUYS].extend(capture_cards(line))
        if KW_GAINS_THE in line:
            targ_obj[GAINS].extend(capture_cards(line))
        if has_trashing:
            if KW_REVEALS in lines[line_idx - 1] and not KW_DRAWS in line:
                targ_obj[TRASHES].extend(capture_cards(lines[line_idx - 1]))
            if KW_REVEALING in line or KW_REVEALS in line:
                # reveals watchtower trashing ...
                # noble brigand reveals xx, yy and trashes yy
                trashed = capture_cards(line[line.find(KW_TRASHING):])
                targ_obj[TRASHES].extend(trashed)
            else:
                rest = line
                if KW_GAINING in line:
                    rest = line[:line.find(KW_GAINING)]
                targ_obj[TRASHES].extend(capture_cards(rest))
        if KW_GAINS_A in line or KW_GAMES_A in line:
            if KW_TOKEN in line:
                assert get_card('Pirate Ship') in capture_cards(line), 'Pirate ship not in line'
                ps_tokens += 1
            else:
                rest = line[max(line.find(KW_GAINS_A), line.find(KW_GAMES_A)):]
                targ_obj[GAINS].extend(capture_cards(rest))
        if KW_IS_TRASHED in line:
            # Saboteur after revealing cards, name not mentioned on this line.
            cards = capture_cards(line)
            targ_obj[TRASHES].extend(cards)
        if KW_REVEALS in line:
            card_revealed = capture_cards(line)

            # arg, ambassador requires looking at the next line to figure
            # out how many copies were returned
            if (card_revealed and line_idx + 1 < len(lines) and
                KW_RETURNING in lines[line_idx + 1] and not
                KW_REVEALING in lines[line_idx + 1]):
                next_line = lines[line_idx + 1]
                num_copies = 1
                num_copies_match = NUMBER_COPIES.search(next_line)
                if num_copies_match:
                    num_copies = int(num_copies_match.group(1))
                returns.extend(card_revealed * num_copies)
        if KW_REVEALING in line and KW_TO_THE_SUPPLY in line:
            # old style ambassador line
            returns.extend(capture_cards(line))
        if KW_GETTING in line or KW_GETS in line or KW_GET in line:
            money_match = GETTING_MONEY_RE.search(line)
            if money_match:
                turn_money += int(money_match.group(1))
        if KW_WHICH_IS_WORTH in line:
            worth_match = WHICH_IS_WORTH_RE.search(line)
            assert bool(worth_match), line
            turn_money += int(worth_match.group(1))
        if KW_FOR_MONEY in line:
            worth_match = FOR_MONEY_RE.search(line)
            assert bool(worth_match), line
            turn_money += int(worth_match.group(1))
        if u'▼' in line:
            vp_tokens += int(VP_TOKEN_RE.search(line).group('num'))
        if KW_INSTEAD in line and not KW_WISHING in line and 'Trader' in line:
            if 'buy_or_gain' in targ_obj:
                targ_list = targ_obj[targ_obj['buy_or_gain']]
                non_silver_ind = len(targ_list) - 1
                while (non_silver_ind >= 0 and
                       targ_list[non_silver_ind] == get_card('Silver')):
                    non_silver_ind -= 1
                # This shouldn't work when there is no non-silver, but then
                # non_silver_ind == -1 if there is no non-silver,
                # which magically pops the last item.  <3 guido.
                targ_list.pop(non_silver_ind)
            else:
                assert 'Ill-Gotten Gains' in plays, (
                    "line %s: line\n, targ_obj: %s\n context: %s" % (
                        line, str(targ_obj),
                        '\n'.join(lines[line_idx - 2: line_idx + 2])))

        now_buys_len = len(targ_obj.get(BUYS, []))
        now_gains_len = len(targ_obj.get(GAINS, []))
        if now_buys_len > orig_buys_len:
            targ_obj['buy_or_gain'] = BUYS
        if now_gains_len > orig_gains_len:
            targ_obj['buy_or_gain'] = GAINS

        assert not (now_buys_len > orig_buys_len and
                    now_gains_len > orig_gains_len), 'buys or gains mismatch'

    def _delete_if_exists(d, n):
        if n in d:
            del d[n]

    _delete_if_exists(ret, 'buy_or_gain')

    if poss:
        possessee_info = opp_turn_info[str(possessee_index)]
        for k in [GAINS, TRASHES]:
            _delete_if_exists(possessee_info, k)

        possessee_info[VP_TOKENS], vp_tokens = vp_tokens, 0
        possessee_info[RETURNS], returns = returns, []
        ret[BUYS] = []  # buys handled by possesion gain line.

    for opp in opp_turn_info.keys():
        _delete_if_exists(opp_turn_info[opp], 'buy_or_gain')
        parse_common.delete_keys_with_empty_vals(opp_turn_info[opp])

        d = opp_turn_info[opp]
        for k, v in d.iteritems():
            if k==VP_TOKENS:
                d[k] = v
            else:
                d[k] = indexes(v)

    ret[BUYS] = indexes(ret[BUYS])
    ret[GAINS] = indexes(ret[GAINS])
    ret[TRASHES] = indexes(ret[TRASHES])

    ret.update({NAME: names_list[tracker.current_player()],
                PLAYS: indexes(plays) , RETURNS: indexes(returns),
                MONEY: parse_common.count_money(plays) + turn_money,
                VP_TOKENS: vp_tokens, PIRATE_TOKENS: ps_tokens,
                POSSESSION: poss, OUTPOST: outpost,
                OPP: dict(opp_turn_info)})

    parse_common.delete_keys_with_empty_vals(ret)
    return ret

def split_turns(turns_blob):
    """ Given a string of game play data, return a list of turn strings
    separated by turn headers."""
    turn_texts = ['']
    for line in turns_blob.split('\n'):
        try:
            parse_turn_header(line)
            turn_texts.append(line + '\n')
        except parse_common.ParseTurnHeaderError, e:
            turn_texts[-1] += line + '\n'
    return [t for t in turn_texts if t]

def parse_turns(turns_blob, names_list):
    """ Return a list of turn objects, as documented by parse_turn(). """
    return [parse_turn(text, names_list) for text in split_turns(turns_blob)]


def parse_game(game_str, dubious_check = False):
    """ Parse game_str into game dictionary

    game_str: Entire contents of a log file.
    dubious_check: If true, raise a BogusGame exception if the game is
      suspicious.

    returns a dict with the following fields:
      decks: A list of player decks, as documented in parse_deck().
      supply: A list of cards in the supply.
      players: A list of normalized player names.
      game_end: List of cards exhausted that caused the game to end.
      resigned: True iff some player in the game resigned..
      start_decks: 7coppers and 3estates for all iso logs.
      rating_system: 'isotropic' for all iso logs.
    """
    game_str = game_str.replace('&mdash;', '---')

    try:
        split_sects = SECTION_SEP.split(game_str)
        header_str, decks_blob, trash_and_turns = split_sects
    except ValueError, exception:
        raise parse_common.ParsingError('Failed to split sections')
    game_dict = parse_header(header_str)
    game_dict[RATING_SYSTEM] = 'isotropic'
    decks = parse_decks(decks_blob)
    game_dict[DECKS] = decks
    validate_names(decks)

    names_list = [d[NAME] for d in game_dict[DECKS]]
    game_dict[START_DECKS] = make_start_decks(names_list)

    turns_str = trash_and_turns.split('Game log')[1]
    first_index = turns_str.find('---')
    veto_str = turns_str[:first_index]
    turns_str = turns_str[first_index:]
    turns_str = canonicalize_names(turns_str, names_list)

    turns = parse_turns(turns_str, names_list)

    associate_game_with_norm_names(game_dict)
    associate_turns_with_owner(game_dict, turns)
    game_dict[VETO] = parse_vetoes(game_dict, veto_str)

    return game_dict
