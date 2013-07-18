#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Parse raw game into JSON list of game documents.
Low-level functionality that isn't implementation-specific.
Called from parse_goko_game and parse_iso_game."""

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

class BogusGameError(Exception):
    """ Exception for a degenerate game that should not be
    parsed. These are common, and by design, so they should not be
    logged except in debug mode.
    """
    def __init__(self, reason):
        Exception.__init__(self)
        self.reason = reason

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return 'BogusGameError %s' % self.reason


class ParsingError(Exception):
    """ Exception for a game that cannot be parsed.
    """
    def __init__(self, reason):
        Exception.__init__(self)
        self.reason = reason

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return 'ParsingError %s' % self.reason

class ParseTurnHeaderError(Exception):
    """ Exception for a game where a turn header cannot be parsed.
    """
    def __init__(self, line):
        self.line = line

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return 'ParseTurnHeaderError %s' % self.line

PLAYER_IND_RE = re.compile('player(?P<num>\d+)')

def _player_label(ind):
    return 'player' + str(ind)

def delete_keys_with_empty_vals(dict_obj):
    """ Remove keys from object associated with values that are False/empty."""
    keys_to_die = []
    for k in dict_obj.keys():
        if isinstance(dict_obj[k], dict):
            delete_keys_with_empty_vals(dict_obj[k])
        if not dict_obj[k]:
            keys_to_die.append(k)
    for k in keys_to_die:
        del dict_obj[k]

def count_money(plays, typeGoko = False):
    """ Return the value of the money from playing cards in plays.

    For iso, This does not include money from cards like Steward or Bank, but
    does count Copper. 
    
    Counts as much as it can from Goko. Does not count cards that depend on the
    game state or on choices (Forager, Harvest, etc.) Does count everything
    with a fixed value or a value that depends only on the sequence of plays
    (Bank, FG, etc.). 

    plays: list of cards.
    """
    coppersmith_ct = 0
    money = 0
    treasures = 0
    fg_active = False
    for card in plays:
        if card.is_treasure():
            treasures += 1

        if card == dominioncards.Coppersmith:
            coppersmith_ct += 1
        elif card == dominioncards.FoolsGold:
            if fg_active:
                money += 4
            else:
                money += 1
            fg_active = True
        elif card == dominioncards.Copper:
            money += 1 + coppersmith_ct
        elif card == dominioncards.Bank and typeGoko:
            money += treasures
        elif card.is_treasure() or typeGoko:
            money += card.money_value()
    return money

def _get_real_name(canon_name, names_list):
    return names_list[int(PLAYER_IND_RE.match(canon_name).group('num'))]


