# -*- coding: utf-8 -*-

"""Object and classes representing the various cards of Dominion.
"""

import csv
import os

# Module-level logging instance
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

# TODO: Look at moving this to utils.py
def int_or_default(string, default):
    """Returns the integer value of string if the value is
    unambiguous, otherwise the default"""
    try:
        return int(string)
    except ValueError:
        return default

class Card(object):
    """Card object. Instances of this class, initialized by this
    module, know about card characteristics and rules.
    """
    def __init__(self, cardlist_row):
        for key, value in cardlist_row.iteritems():
            prop = str.lower(key)
            setattr(self, prop, value)

        # Optimize performance by cleaning up loaded values now,
        # instead of in the getter during each call.
        self.vp = int_or_default(self.vp, 0)
        self.coins = int_or_default(self.coins, 0)
        self.trash = int_or_default(self.trash, 1)
        self.actions = int_or_default(self.actions, 1)
        self.index = int(self.index)

    def pluralize(self, freq):
        return self.singular if freq == 1 else self.plural

    def sane_title(self):
        return self.singular.replace("'S", "'s").replace(' Of ', ' of ').strip()

    def is_treasure(self):
        return self.treasure == '1'

    def is_reaction(self):
        return self.reaction == '1'

    def is_victory(self):
        return self.victory == '1'

    def is_action(self):
        return self.action == '1'

    def is_attack(self):
        return self.attack == '1'

    def vp_per_card(self):
        return self.vp

    def money_value(self):
        return self.coins

    def trashes(self):
        return self.trash

    def num_plus_actions(self):
        return self.actions

    def get_expansion(self):
        return self.expansion

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.singular)

    def __eq__(self, other):
        if type(self)==type(other):
            return self.index==other.index
        else:
            return False

    def __hash__(self):
        return self.index

    def num_copies_per_game(self, num_players):
        if self.is_victory():
            if num_players >= 3:
                return 12
            return 8
        card_name = self.singular
        if card_name == 'Curse':
            return 10 * (num_players - 1)
        return {'Potion': 16,
                'Platinum': 12,
                'Gold': 30,
                'Silver': 40,
                'Copper': 60
                }.get(card_name, 10)


_CARDS = {}
"""dict containing all card objects, indexed by various string
representations (singular, plural, and __repr__()"""

def get_card(name):
    """Look up a card by its name."""
    try:
        return _CARDS[name]
    except KeyError:
        raise CardNameError(name)

def is_valid_card_name(name):
    """Determines if the given string is a valid dominion card name"""
    return name in _CARDS

class CardNameError(Exception):
    """Indicates a user-inputted card name is invalid."""
    def __init__(self, name):
        self.args = "Invalid card name: %s"%name,
        self.reason = self.args[0]

    def __str__(self):
        return '<Card name error %s>' % self.reason

_INDEXED = {}
"""dict containing all card objects, indexed by the `Index` column
value in the card_list.csv file."""

def index_to_card(index):
    """ Look up a card by its index """
    return _INDEXED[index]

def indexes(cards):
    """ Return a list of index for the passed list of cards """
    return [card.index for card in cards]



def pythonify_card_name(name):
    """Helper function to convert a card name into a valid Python
    object name"""
    return ''.join([n for n in name if n not in [' ', "'", '-']])


_namespace = vars()
def _init():
    """Initialize the library of cards"""

    # TODO: Look at using pkg_resources to find this file, so it will
    # work if stored in an egg
    _cardlist_reader = csv.DictReader(open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'card_info/card_list.csv')))

    global _namespace
    for cardlist_row in _cardlist_reader:
        singular = cardlist_row['Singular']
        c = Card(cardlist_row)
        _CARDS[singular] = c
        _CARDS[cardlist_row['Plural']] = c
        _CARDS[c.__repr__()] = c      # Enable lookup by __repr__()
        _INDEXED[c.index] = c

        pname = pythonify_card_name(singular)
        _namespace[pname] = c

# Initialize the module
_init()


# Methods to return sets of card objects

def all_cards():
    return _INDEXED.values()

TOURNAMENT_WINNINGS = [Princess, Diadem, Followers, TrustySteed, BagofGold]

EVERY_SET_CARDS = [Estate, Duchy, Province, Copper, Silver, Gold, Curse]


def opening_cards():
    """Returns the set of cards that can be bought on an opening turn.

    This includes only cards costing between 0 and 5 coin."""
    return sorted([card for card in all_cards()
            if card.cost in ('0', '2', '3', '4', '5')])


import collections
def get_expansion_weight(supply):
    weights = collections.defaultdict(float)
    total = 0

    for c in supply:
        expansion = c.get_expansion()
        if expansion == 'Common':
            continue
        weights[expansion] += 1.0
        total += 1

    for expansion in weights:
        weights[expansion] /= float(total)

    return weights

import simplejson as json
class CardEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Card):
            return int(obj.index)
        return obj

    def encode(self, obj):
        if isinstance(obj, Card):
            return json.JSONEncoder.encode(self, str(obj.index))
        return json.JSONEncoder.encode(self, obj)
