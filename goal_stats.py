#!/usr/bin/python

# Module-level logging instance
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import AIs
import collections
import operator

import dominionstats.utils.log
import goals
import incremental_scanner
import utils


def main(parsed_args):
    db = utils.get_mongo_database()
    goal_db = db.goals
    gstats_db = db.goal_stats
    all_goals = goals.goal_check_funcs.keys()
    total_pcount = collections.defaultdict(int)
    goal_scanner = incremental_scanner.IncrementalScanner('goals', db)
    stat_scanner = incremental_scanner.IncrementalScanner('goal_stats', db)

    if not parsed_args.incremental:
        log.warning('resetting scanner and db')
        stat_scanner.reset()
        gstats_db.remove()

    log.info("Starting run: %s", stat_scanner.status_msg())

    # TODO: The following logic doesn't work now that goal calculation doesn't happen with a scanner.
    # if goal_scanner.get_max_game_id() == stat_scanner.get_max_game_id():
    #     log.info("Stats already set! Skip")
    #     exit(0)

    log.info('all_goals %s', all_goals)
    for goal_name in all_goals:
        log.info("Working on %s", goal_name)
        found_goals_cursor = goal_db.find({'goals.goal_name': goal_name},
                                          {'goals.player': 1, '_id': 0})
        total = found_goals_cursor.count()
        log.info("Found %d instances of %s", total, goal_name)

        pcount = collections.defaultdict(int)
        for goal in found_goals_cursor:
            player = goal['goals'][0]['player']
            pcount[player] += 1
            total_pcount[player] += 1

        psorted = sorted(pcount.iteritems(), key=operator.itemgetter(1), 
                         reverse=True)
        top = []
        leaders = 0
        i = 0
        while leaders < 3 and i < len(psorted):
            (player, count) = psorted[i]
            players = []
            if player not in AIs.names:
                players = [player]
            i += 1
            while i < len(psorted) and psorted[i][1] == count:
                if psorted[i][0] not in AIs.names:
                    players.append(psorted[i][0])
                i += 1
            leaders += len(players)
            if len(players) > 0:
                top.append((players, count))
			
        mongo_val = {'_id': goal_name, 'count': total, 'top': top}
        gstats_db.save(mongo_val)

    stat_scanner.set_max_game_id(goal_scanner.get_max_game_id())
    stat_scanner.save()
    log.info("Ending run: %s", stat_scanner.status_msg())


if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main(args)
