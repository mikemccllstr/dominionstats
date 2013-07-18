#!/usr/bin/python
# -*- coding: utf-8 -*-

import bz2
import logging
import os
import re

import dominionstats.utils.log
import name_merger
import utils


# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def main():
    filename_pattern = re.compile(r'^(?P<date>\d\d\d\d-\d\d-\d\d)\.html\.bz2$')
    iso_leaderboard_pattern = re.compile(r'<td>(?P<skill_mean>-?\d+\.\d+) &plusmn; ' + \
                                     r'(?P<skill_error>-?\d+\.\d+)</td><td class=c2>' + \
                                     r'(?P<rank>\d+)</td><td class=c>' + \
                                     r'(?P<eligible_games_played>\d+)</td><td>' + \
                                     r'(?P<nickname>[^<]*) <')
    goko_leaderboard_pattern = re.compile(r'\s+<td class="leaders-table-item table-item-rank">(?P<rank>\d+)</td>\s*\n' + r'\s*<td class="leaders-table-item table-item-name"><img [^>]*>(?P<nickname>.*)</td>\s*\n' + r'\s*<td class="leaders-table-item table-item-points">(?P<skill_mean>\d+)</td>')

    database = utils.get_mongo_database()
    history_collection = database.leaderboard_history
    scanner_collection = database.scanner

    db_val = scanner_collection.find_one({'_id': 'leaderboard_history'})
    last_date = db_val['last_date'] if db_val else '0000-00-00'

    directory = 'static/leaderboard/'

    filenames = os.listdir(directory)
    filenames.sort()

    bad_leaderboard_dates = utils.get_bad_leaderboard_dates()

    for filename in filenames:
        match = filename_pattern.search(filename)
        if not match:
            continue

        date = match.group('date')

        if date in bad_leaderboard_dates:
            # don't load data from when the leaderboard was messed up
            log.warning("Skipping %s because the leaderboard was messed up", date)
            continue

        if date <= last_date:
            log.warning("Date %s is less than last date %s", date, last_date)
            continue

        log.info('Processing %s', date)

        file_obj = bz2.BZ2File(directory + filename)
        content = file_obj.read().decode('utf-8')
        file_obj.close()

        nickname_to_entry = {}
        num_matches = 0
        last_rank = -1

        pos = 0
        while True:
            match = iso_leaderboard_pattern.search(content, pos)
            if not match:
                break

            num_matches += 1
            skill_mean = float(match.group('skill_mean'))
            skill_error = float(match.group('skill_error'))
            rank = int(match.group('rank'))
            eligible_games_played = int(match.group('eligible_games_played'))
            nickname = match.group('nickname')

            normed_nickname = name_merger.norm_name(nickname)

            if normed_nickname not in nickname_to_entry:
                nickname_to_entry[normed_nickname] = [date, skill_mean, skill_error, rank, eligible_games_played]
            else:
                log.info('normed nickname %s already exists for %s', normed_nickname, date)

            last_rank = rank
            pos = match.end()

        pos = 0
        while True:
            match = goko_leaderboard_pattern.search(content, pos)
            if not match:
                break

            num_matches += 1
            skill_mean = float(match.group('skill_mean'))
            skill_error = 0
            rank = int(match.group('rank'))
            eligible_games_played = 0
            nickname = match.group('nickname')

            normed_nickname = nickname

            if normed_nickname not in nickname_to_entry:
                nickname_to_entry[normed_nickname] = [date, skill_mean, skill_error, rank, eligible_games_played]
            else:
                log.info('normed nickname %s already exists for %s', normed_nickname, date)

            last_rank = rank
            pos = match.end()
        log.info('%d entries matched', num_matches)

        if num_matches == 0:
            log.error('No entries found, so the regex is probably not doing its job anymore.')
            break

        if num_matches != last_rank:
            log.error('ERROR: # entries does not match last rank, so the regex is probably not doing its job anymore.')
            break

        for nickname, data in nickname_to_entry.iteritems():
            history_collection.update({'_id': nickname}, {'$push': {'history': data}}, upsert=True)

        log.info('%d player histories updated', len(nickname_to_entry))

        last_date = date

    scanner_collection.update({'_id': 'leaderboard_history'}, {'$set': {'last_date': last_date}}, upsert=True)


if __name__ == '__main__':
    parser = utils.incremental_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main()
