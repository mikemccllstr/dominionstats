#!/usr/bin/python

"""Computes stats about buys/gains and game length for all cards in the game.

When this is called as a stand alone program, it will will incrementally
update statistics for all games in the database.
"""

import logging
import time

from keys import *
from stats import MeanVarStat as MVS
import analysis_util
import dominioncards
import game
import dominionstats.utils.log
import incremental_scanner
import mergeable
import primitive_util
import utils

# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

BUYS_COL_NAME = 'buys'

NO_INFO = MVS().mean_diff(MVS())

PROV_SMOOTH = 21.4
COLONY_SMOOTH = 23.5

class BuyStat(primitive_util.PrimitiveConversion, mergeable.MergeableObject):
    """ A bunch of MeanVar statistics about card buys/game length, etc """

    def __init__(self):
        self.buys = MVS()
        self.gains = MVS()
        self.trashes = MVS()
        self.returns = MVS()
        self.passes = MVS()
        self.receives = MVS()
        self.any_gained = MVS()
        self.available = MVS()

        self.game_length = MVS(1.0, PROV_SMOOTH, PROV_SMOOTH * PROV_SMOOTH) 
        self.game_length_colony = MVS(1.0, COLONY_SMOOTH, 
                                      COLONY_SMOOTH * COLONY_SMOOTH)
    
    @property
    def none_gained(self):
        return self.available - self.any_gained

    def effect_with(self):
        return getattr(self, 'effectiveness_gain', NO_INFO)
    
    def effect_without(self):
        return getattr(self, 'effectiveness_skip', NO_INFO)

class DeckBuyStats(primitive_util.ConvertibleDefaultDict,
                   mergeable.MergeableDict):
    """ Essentially, a defaultdict of BuyStats.

    Since this is convertible, it can be easily turned into a value that
    consists of nothing but primitive types, which is nice for mongo and JSON.
    Likewise, it can be recreated from such a value.

    Since it is mergeable, it can be combined with another DeckBuysInstance to
    tell the combined story.
    """
    def __init__(self):
        primitive_util.ConvertibleDefaultDict.__init__(self, value_type=BuyStat,
                                                       key_type=dominioncards.get_card)

def accum_buy_stats(games_stream, accum_stats, 
                    acceptable_deck_filter=lambda game, name: True,
                    max_games=-1):
    """ Accumulate buy statistics from games_stream into accum_stats.

    games_stream: an iterable of game.Game objects.
    accum_stats: DeckBuyStats object to store results.
    acceptable_deck_filter: predicate that determines if information about
      a particular deck should be included.  By default, include everything.
    """
    for idx, game_val in enumerate(games_stream):
        counted_game_len = False

        for changes in game_val.deck_changes_per_player():
            if not acceptable_deck_filter(game_val, changes.name):
                continue
            any_gained = set()
            win_points = game_val.get_player_deck(changes.name).WinPoints()

            for category in game.PlayerDeckChange.CATEGORIES:
                for card in getattr(changes, category):
                    getattr(accum_stats[card], category).add_outcome(
                        win_points)
                        
                    if category in ['gains', 'buys']:
                        any_gained.add(card)

            for card in any_gained:
                accum_stats[card].any_gained.add_outcome(win_points)

            all_avail = analysis_util.available_cards(game_val, 
                                                      any_gained)
            for card in all_avail:
                accum_stats[card].available.add_outcome(win_points)

            if not counted_game_len:  # don't double count this
                counted_game_len = True
                game_len = game_val.get_turns()[-1].get_turn_no()
                for card in all_avail:
                    stats_obj = accum_stats[card]
                    stats_obj.game_length.add_outcome(game_len)
                    if dominioncards.Colony in game_val.get_supply():
                        stats_obj.game_length_colony.add_outcome(game_len)

        if idx + 1 == max_games:
            break

def add_effectiveness(accum_stats, global_stats):
    """
    Add some statistics about a player's 'effectiveness' when they gain or
    don't gain the card.
    """
    # first, find the incremental effect of the player's skill
    any_eff = accum_stats[dominioncards.Estate].available.mean_diff(
        global_stats[dominioncards.Estate].available)

    for card in accum_stats:
        # now compare games in which the player gains/skips the card to gains
        # in which other players gain/skip the card
        stats_obj = accum_stats[card]
        global_stats_obj = global_stats[card]
        card_gain_eff = stats_obj.any_gained.mean_diff(
            global_stats_obj.any_gained)
        card_skip_eff = stats_obj.none_gained.mean_diff(
            global_stats_obj.none_gained)
        stats_obj.effectiveness_gain = card_gain_eff.mean_diff(any_eff)
        stats_obj.effectiveness_skip = card_skip_eff.mean_diff(any_eff)

def do_scan(scanner, games_col, accum_stats, max_games):
    """ Use scanner to accumulate stats from games_col into accum_stats .

    scanner: incremental_scanner.Scanner to use for traversal.
    games_col:  Mongo collection to scan.
    accum_stats: DeckBuyStats instance to store results.
    """
    accum_buy_stats(analysis_util.games_stream(scanner, games_col),
                    accum_stats, max_games=max_games)

def main(parsed_args):
    """ Scan and update buy data"""
    start = time.time()
    db = utils.get_mongo_database()
    games = db.games
    output_db = db

    overall_stats = DeckBuyStats()

    scanner = incremental_scanner.IncrementalScanner(BUYS_COL_NAME, output_db)
    buy_collection = output_db[BUYS_COL_NAME]

    if not parsed_args.incremental:
        log.warning('resetting scanner and db')
        scanner.reset()
        buy_collection.drop()

    start_size = scanner.get_num_games()
    log.info("Starting run: %s", scanner.status_msg())
    do_scan(scanner, games, overall_stats, parsed_args.max_games)
    log.info("Ending run: %s", scanner.status_msg())
    end_size = scanner.get_num_games()

    if parsed_args.incremental:
        existing_overall_data = DeckBuyStats()
        utils.read_object_from_db(existing_overall_data, buy_collection, '')
        overall_stats.merge(existing_overall_data)
        def deck_freq(data_set):
            return data_set[dominioncards.Estate].available.frequency()
        log.info('existing %s decks', deck_freq(existing_overall_data))
        log.info('after merge %s decks', deck_freq(overall_stats))

    utils.write_object_to_db(overall_stats, buy_collection, '')

    scanner.save()


def profilemain():
    """ Like main(), but print a profile report."""
    import hotshot, hotshot.stats
    prof = hotshot.Profile("buys.prof")
    prof.runcall(main)
    prof.close()
    stats = hotshot.stats.load("buys.prof")
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)

if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main(args)
