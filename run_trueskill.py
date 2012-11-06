""" Update trueskill ratings for openings."""

import logging
import logging.handlers
import os
import os.path
import sys

from game import Game
from keys import *
from utils import get_mongo_connection, progress_meter
import incremental_scanner
import primitive_util
import trueskill.trueskill as ts
import utils

# Module-level logging instance
log = logging.getLogger(__name__)


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
    
def run_trueskill_openings(args, db, log):
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
        scanner.reset()
        collection.drop()

    for ind, game in enumerate(
        progress_meter(scanner.scan(db.games, {}), log)):
        if len(game[DECKS]) >= 2 and len(game[DECKS][1][TURNS]) >= 5:
            update_skills_for_game(game, opening_skill_table)
                                   
        if ind == args.max_games:
            break

    #player_skill_table.save()
    opening_skill_table.save()
    scanner.save()
    log.info("Ending run: %s", scanner.status_msg())


def main(args):
    con = get_mongo_connection()
    db = con.test

    run_trueskill_openings(args, db, log)

if __name__ == '__main__':
    args = utils.incremental_max_parser().parse_args()

    script_root = os.path.splitext(sys.argv[0])[0]

    # Configure the logger
    log.setLevel(logging.DEBUG)

    # Log to a file
    fh = logging.handlers.TimedRotatingFileHandler(script_root + '.log',
                                                   when='midnight')
    if args.debug:
        fh.setLevel(logging.DEBUG)
    else:
        fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh.setFormatter(formatter)
    log.addHandler(fh)

    # Put logging output on stdout, too
    ch = logging.StreamHandler(sys.stdout)
    if args.debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    main(args)
