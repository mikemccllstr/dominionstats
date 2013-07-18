# -*- coding: utf-8 -*-

""" Background tasks for Dominion stats
"""

from __future__ import absolute_import

from celery.utils.log import get_task_logger
import datetime

from background.celery import celery
from goals import calculate_goals
from parse_game import parse_and_insert
import game_stats
import isotropic
import goko
import utils


log = get_task_logger(__name__)

# TODO: These should be pulled from a config file
PARSE_GAMES_CHUNK_SIZE = 100
CALC_GOALS_CHUNK_SIZE = 100
SUMMARIZE_GAMES_CHUNK_SIZE = 2000


@celery.task 
def parse_games(games, day):
    """Takes list of game ids and a game date and parses them out."""
    log.info("Parsing %d games for %s", len(games), day)

    connection = utils.get_mongo_connection()
    db = connection.test
    raw_games_col = db.raw_games
    parsed_games_col = db.games
    parse_error_col = db.parse_error

    raw_games = []
    for game_id in games:
        game = raw_games_col.find_one({'_id': game_id})
        if game:
            raw_games.append(game)
        else:
            log.warning('Found nothing for game id %s', game_id)

    return parse_and_insert(log, raw_games, parsed_games_col, parse_error_col, day)


@celery.task 
def parse_days(days):
    """Parses rawgames into games records and stores them in the DB.

    Takes a list of one or more days in the format "YYYYMMDD" or
    datetime.date, and generates tasks to parse the games that
    occurred on those days.

    Skips days where there are no rawgames available.

    Skips days where the parsed game collection has more than 95% of
    the quantity of rawgames, as this suggests the date has already
    been parsed.

    Returns the number of individual games referred for parsing.
    """
    game_count = 0
    db = utils.get_mongo_database()
    raw_games_col = db.raw_games
    games_col = db.games
    raw_games_col.ensure_index('game_date')

    for day in days:
        if type(day) is datetime.date:
            day = day.strftime('%Y%m%d')
        games_to_parse = raw_games_col.find({'game_date': day}, {'_id': 1})

        raw_games_qty = games_to_parse.count()
        if raw_games_qty < 1:
            log.info('no games to parse in %s', day)
            continue

        parsed_games_qty = games_col.find({'game_date': day}).count()
        if float(parsed_games_qty) / float(raw_games_qty) > 0.85:
            log.info('Looks like raw games for %s have already been parsed. Found %5.2f%% in games collection.',
                     day, 100.0 * parsed_games_qty / raw_games_qty)
            continue

        game_count += games_to_parse.count()
        log.info('%s games to parse in %s', games_to_parse.count(), day)
        for chunk in utils.segments([x['_id'] for x in games_to_parse], PARSE_GAMES_CHUNK_SIZE):
            parse_games.delay(chunk, day) 

    return game_count


@celery.task 
def calc_goals(game_ids, day):
    """ Calculate the goals achieved in the passed list of games """
    log.info("Calculating goals for %d game IDs from %s", len(game_ids), day)

    connection = utils.get_mongo_connection()
    db = connection.test
    games_col = db.games
    goals_col = db.goals
    goals_error_col = db.goals_error

    games = []
    for game_id in game_ids:
        game = games_col.find_one({'_id': game_id})
        if game:
            games.append(game)
        else:
            log.warning('Found nothing for game id %s', game_id)

    return calculate_goals(games, goals_col, goals_error_col, day)


@celery.task 
def calc_goals_for_days(days):
    """Examines games and determines if any goals were achieved, storing them in the DB.


    Takes a list of one or more days in the format "YYYYMMDD" or
    datetime.date, and generates tasks to calculate the goals achieved
    in each of the individual games that occurred on those days.

    Skips days where there are no games available.

    Skips games that are already present in the goal collection.

    Returns the number of individual games referred for searching.
    """
    game_count = 0
    db = utils.get_mongo_database()
    games_col = db.games
    goals_col = db.goals
    games_col.ensure_index('game_date')

    for day in days:
        if type(day) is datetime.date:
            day = day.strftime('%Y%m%d')
        games_to_process = games_col.find({'game_date': day}, {'_id': 1})

        if games_to_process.count() < 1:
            log.info('no games to search for goals on %s', day)
            continue

        log.info('%s games to search for goals on %s', games_to_process.count(), day)

        chunk = []
        for game in games_to_process:
            if len(chunk) >= CALC_GOALS_CHUNK_SIZE:
                calc_goals.delay(chunk, day) 
                chunk = []

            if goals_col.find({'_id': game['_id']}).count() == 0:
                chunk.append(game['_id'])
                game_count += 1

        if len(chunk) > 0:
            calc_goals.delay(chunk, day) 

    return game_count


@celery.task(rate_limit='2/m')
def scrape_raw_games(date):
    """Download the specified raw game archive, store it in S3, and load it into MongoDB.

    date is a datetime.date object
    """
    db = utils.get_mongo_database()

    scraper = goko.GokoScraper(db)

    try:
        inserted = scraper.scrape_and_store_rawgames(date)
        #if inserted > 0: #TODO:FIX
            # Also need to parse the raw games for the days where we
            # inserted new records.
            #parse_days.delay([date]) 
        parse_days.delay([date]) 
        return inserted

    except goko.ScrapeError:
        log.info("Data for %s is not available", date)
        return None


@celery.task 
def check_for_work():
    """Examine the state of the database and generate tasks for necessary work.

    This task is intended to be called on a regular basis, e.g., from
    a frequently run cron job. It is intended to scan through the
    database, identify what needs to be done to bring it to a current
    state, and then create the needed tasks.
    """

    connection = utils.get_mongo_connection()
    db = connection.test

    # Scrape goko for raw games
    for date in goko.dates_needing_scraping(db):
        scrape_raw_games.delay(date)


@celery.task
def summarize_game_stats_for_days(days):
    """Examines games and determines if need to be summarized.

    Takes a list of one or more days in the format "YYYYMMDD" or
    datetime.date, and generates tasks to summarize each of the
    individual games that occurred on those days.

    Skips days where there are no games available.

    Skips games that are already present in the games_stats
    collection.

    Returns the number of individual games referred for summarizing.
    """
    game_count = 0
    db = utils.get_mongo_database()
    games_col = db.games
    game_stats_col = db.game_stats
    games_col.ensure_index('game_date')

    for day in days:
        if type(day) is datetime.date:
            day = day.strftime('%Y%m%d')
        games_to_process = games_col.find({'game_date': day}, {'_id': 1})

        if games_to_process.count() < 1:
            log.info('No games available to summarize on %s', day)
            continue

        log.info('%s games to summarize on %s', games_to_process.count(), day)

        chunk = []
        for game in games_to_process:
            if len(chunk) >= SUMMARIZE_GAMES_CHUNK_SIZE:
                summarize_games.delay(chunk, day)
                chunk = []

            # Is this really slow? Does it need to be fixed? 
            #if game_stats_col.find({'_id.game_id': game['_id']}).count() == 0:
            chunk.append(game['_id'])
            game_count += 1

        if len(chunk) > 0:
            summarize_games.delay(chunk, day)

    return game_count


@celery.task
def summarize_games(game_ids, day):
    """Summarize the passed list of games"""
    log.info("Summarizing %d games from %s", len(game_ids), day)

    db = utils.get_mongo_database()
    games_col = db.games
    game_stats_col = db.game_stats

    games = []
    for game_id in game_ids:
        game = games_col.find_one({'_id': game_id})
        if game:
            games.append(game)
        else:
            log.warning('Found nothing for game id %s', game_id)

    return game_stats.calculate_game_stats(games, game_stats_col)
