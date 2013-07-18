#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time

from game import Game
from primitive_util import PrimitiveConversion, ConvertibleDefaultDict
from stats import MeanVarStat
import dominioncards
import dominionstats.utils.log
import incremental_scanner
import utils

# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class DBCardRatioTracker(PrimitiveConversion):
    """ This keeps track of every final and progressive card ratio for one
    pair of cards.
    """
    def __init__(self):
        self.final = ConvertibleDefaultDict(MeanVarStat)
        self.progressive = ConvertibleDefaultDict(MeanVarStat)

    def add_outcome(self, tracker_type, ratio, win_points):
        if tracker_type == 'final':
            tracker = self.final
        elif tracker_type == 'progressive':
            tracker = self.progressive
        else:
            raise

        if ratio not in tracker:
            tracker[ratio] = MeanVarStat()

        tracker[ratio].add_outcome(win_points)

class DBCardRatioTrackerManager:
    """ This keeps track of every final and progressive card ratio for all
    pairs of cards. This manages DBCardRatioTracker instances.
    """
    def __init__(self, collection, incremental=True):
        self.collection = collection
        self.incremental = incremental
        self.trackers = {}
        if self.incremental:
            for entry in collection.find():
                tracker = DBCardRatioTracker()
                tracker.from_primitive_object(entry)
                self.trackers[entry['_id']] = tracker

    def integrate_results(self, tracker_type, ratio_dict, win_points):
        for key in ratio_dict:
            if key not in self.trackers:
                self.trackers[key] = DBCardRatioTracker()
            tracker = self.trackers[key]
            for ratio in ratio_dict[key]:
                ratio = str(ratio[0]) + ':' + str(ratio[1])
                tracker.add_outcome(tracker_type, ratio, win_points)

    def save(self):
        if not self.incremental:
            self.collection.drop()
        for key, tracker in self.trackers.iteritems():
            utils.write_object_to_db(tracker, self.collection, key)

class CardRatioTracker:
    """ Base class for the final and progressive card ratio trackers.
    """
    def __init__(self, supply):
        self.card_counts = {}

        for card in [dominioncards.Estate, dominioncards.Duchy,
                     dominioncards.Province, dominioncards.Curse,
                     dominioncards.Copper, dominioncards.Silver,
                     dominioncards.Gold] + supply:
            self.card_counts[card] = 0

    def get_card_ratios(self):
        ratios = {}
        for card1 in self.card_counts.iterkeys():
            for card2 in self.card_counts.iterkeys():
                if str(card1) < str(card2):
                    key = str(card1) + ':' + str(card2)
                    ratios[key] = set([(self.card_counts[card1], self.card_counts[card2])])
        return ratios

class FinalCardRatioTracker(CardRatioTracker):
    """ This is used to get the ratios between all of the cards in the supply
    that a player has at the end of the game.
    """
    def __init__(self, supply):
        CardRatioTracker.__init__(self, supply)

    def adjust_card_count(self, card, adjustment):
        if card not in self.card_counts:
            return

        self.card_counts[card] += adjustment

    def get_ratio_dict(self):
        return CardRatioTracker.get_card_ratios(self)

class ProgressiveCardRatioTracker(CardRatioTracker):
    """ This tracks all of the ratios between all of the cards in the supply
    that a player has at any point throughout the whole game.
    """
    def __init__(self, supply):
        CardRatioTracker.__init__(self, supply)
        self.card_counts[dominioncards.Estate] = 3
        self.card_counts[dominioncards.Copper] = 7
        self.ratios = self.get_card_ratios()

    def adjust_card_count(self, card, adjustment):
        if card not in self.card_counts:
            return

        self.card_counts[card] += adjustment

        for card2 in self.card_counts.iterkeys():
            if card != card2:
                if str(card) < str(card2):
                    c1, c2 = card, card2
                else:
                    c1, c2 = card2, card

                key = str(c1) + ':' + str(c2)
                self.ratios[key].add((self.card_counts[c1], self.card_counts[c2]))

    def get_ratio_dict(self):
        return self.ratios

def process_game(game):
    names = game.all_player_names()
    supply = game.get_supply()
    name_to_final_tracker = dict((name, FinalCardRatioTracker(supply)) for name in names)
    name_to_progressive_tracker = dict((name, ProgressiveCardRatioTracker(supply)) for name in names)
    name_to_win_points = dict((player_deck.name(), player_deck.WinPoints()) for player_deck in game.get_player_decks())

    for player_deck in game.get_player_decks():
        tracker = name_to_final_tracker[player_deck.name()]
        for card, count in player_deck.Deck().iteritems():
            tracker.adjust_card_count(card, count)

    for turn in game.get_turns():
        for deck_change in turn.deck_changes():
            tracker = name_to_progressive_tracker[deck_change.name]
            for card in deck_change.buys:
                tracker.adjust_card_count(card, 1)
            for card in getattr(deck_change, 'receives',[]):
                tracker.adjust_card_count(card, 1)
            for card in getattr(deck_change, 'passes',[]):
                tracker.adjust_card_count(card, -1)
            for card in deck_change.gains:
                tracker.adjust_card_count(card, 1)
            for card in deck_change.returns:
                tracker.adjust_card_count(card, -1)
            for card in deck_change.trashes:
                tracker.adjust_card_count(card, -1)

    retval = []
    for name in names:
        retval.append([name_to_final_tracker[name].get_ratio_dict(),
                       name_to_progressive_tracker[name].get_ratio_dict(),
                       name_to_win_points[name]])
    return retval

def main(args):
    commit_after = 25000
    database = utils.get_mongo_database()
    games = database.games
    collection = database.optimal_card_ratios
    db_tracker = None

    scanner = incremental_scanner.IncrementalScanner('optimal_card_ratios', database)

    if not args.incremental:
        log.warning('resetting scanner and db')
        scanner.reset()

    log.info("Starting run: %s", scanner.status_msg())

    for ind, game in enumerate(
        utils.progress_meter(scanner.scan(games, {}))):
        if not db_tracker:
            log.debug("Initializing db tracker manager")
            db_tracker = DBCardRatioTrackerManager(collection, args.incremental)
            log.debug("DB tracker manager initialized")

        result = process_game(Game(game))
        for final_ratio_dict, progressive_ratio_dict, win_points in result:
            db_tracker.integrate_results('final', final_ratio_dict, win_points)
            db_tracker.integrate_results('progressive', progressive_ratio_dict, win_points)

        if args.max_games >= 0 and ind >= args.max_games:
            log.info("Reached max_games of %d", args.max_games)
            break

        if ind % commit_after == 0 and ind > 0:
            start = time.time()
            db_tracker.save()
            scanner.save()
            log.info("Committed calculations to the DB in %5.2fs", time.time() - start)

    log.info("Ending run: %s", scanner.status_msg())

    if db_tracker:
        db_tracker.save()
    scanner.save()

if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    outer_args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(outer_args.debug)
    main(outer_args)
