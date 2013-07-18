""" Update trueskill ratings for openings."""

import logging
import time

from game import Game
from keys import *
import dominionstats.utils.log
import incremental_scanner
import primitive_util
import trueskill.trueskill as ts
import utils

# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def results_to_ranks(results):
    sorted_results = sorted(results)
    return [sorted_results.index(r) for r in results]

class PrimitiveSkillInfo(primitive_util.PrimitiveConversion):
    def to_primitive_object(self):
        return {'mu': float(self.mu),
                'sigma': float(self.sigma),
                'gamma': float(self.gamma)}

class DbBackedSkillTable(ts.SkillTable):
    def __init__(self, coll):
        ts.SkillTable.__init__(self, self._db_backed_missing_func)
        self.coll = coll
        self.skill_infos = {}

    def _db_backed_missing_func(self, name):
        if name in self.skill_infos:
            return self.skill_infos[name]
        db_data = self.coll.find_one({'_id': name})
        skill_info = PrimitiveSkillInfo()
        if db_data:
            skill_info.mu = db_data['mu']
            skill_info.sigma = db_data['sigma']
            skill_info.gamma = db_data['gamma']
        else:
            skill_info.sigma = 25.0/3
            if name.startswith('open:'):
                skill_info.gamma = 0.0001
                skill_info.mu = 0
            else:
                skill_info.gamma = 25.0/300
                skill_info.mu = 25

        self.skill_infos[name] = skill_info
        return self.skill_infos[name]
        
    def save(self):
        for key, val in self.skill_infos.iteritems():
            utils.write_object_to_db(val, self.coll, key)

def setup_openings_collection(coll):
    coll.ensure_index('_id')

def update_skills_for_game(game_dict, opening_skill_table, 
                           #player_skill_table
                           ):
    teams = []
    results = []
    openings = []
    dups = False

    game = Game(game_dict)

    for deck in game.player_decks:
        opening = game.get_opening(deck)
        open_name = 'open:' + '+'.join(map(str, opening))
        if open_name in openings:
            dups = True
        openings.append(open_name)
        nturns = deck.num_turns()
        if deck.Resigned():
            vp = -1000
        else:
            vp = deck.Points()
        results.append((-vp, nturns))
        player_name = deck.name()

        teams.append([open_name, player_name])
        ranks = results_to_ranks(results)

    if not dups:
        team_results = [
            (team, [0.5, 0.5], rank)
            for team, rank in zip(teams, ranks)
            ]
        ts.update_trueskill_team(team_results, opening_skill_table)
    # player_results = [
    #     ([team[1]], [1.0], rank)
    #     for team, rank in zip(teams, ranks)
    #     ]
    # ts.update_trueskill_team(player_results, player_skill_table)


def run_trueskill_openings(args, db, log, commit_after=25000):
    games = db.games


    collection = db.trueskill_openings
    player_collection = db.trueskill_players
    # player_collection.remove()
    # collection.remove()
    setup_openings_collection(collection)
    # setup_openings_collection(player_collection)

    opening_skill_table = DbBackedSkillTable(collection)
    # player_skill_table = DbBackedSkillTable(player_collection)

    scanner = incremental_scanner.IncrementalScanner('trueskill', db)
    log.info("Starting run: %s", scanner.status_msg())
    if not args.incremental:
        log.warning('resetting scanner and db')
        scanner.reset()
        collection.drop()

    for ind, game in enumerate(
        utils.progress_meter(scanner.scan(db.games, {}))):
        if ( len(game[DECKS]) >= 2 and len(game[DECKS][1][TURNS]) >= 5 and (RATING_SYSTEM not in game or (RATING_SYSTEM in game and 'adventure' not in game[RATING_SYSTEM] and 'unknown' not in game[RATING_SYSTEM]))):
            update_skills_for_game(game, opening_skill_table)
                                   
        if ind == args.max_games:
            break

        if ind % commit_after == 0 and ind > 0:
            start = time.time()
            #player_skill_table.save()
            opening_skill_table.save()
            scanner.save()
            log.info("Committed calculations to the DB in %5.2fs", time.time() - start)

    #player_skill_table.save()
    opening_skill_table.save()
    scanner.save()
    log.info("Ending run: %s", scanner.status_msg())


def main(args):
    db = utils.get_mongo_database()

    run_trueskill_openings(args, db, log)

if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main(args)
