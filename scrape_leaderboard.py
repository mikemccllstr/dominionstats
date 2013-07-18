#!/usr/bin/python
# -*- coding: utf-8 -*-

import StringIO
import bz2
import datetime
import gzip
import httplib
import logging
import os
import re
import socket

import dominionstats.utils.log
import utils

# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


output_directory = 'static/leaderboard/'

def date_from_http_header_time(http_header_time):
    return datetime.datetime.strptime(http_header_time, '%a, %d %b %Y %H:%M:%S %Z').date()

def get_date_of_last_cached_leaderboard():
    filename_pattern = re.compile(r'^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)\.html\.bz2$')
    filenames = os.listdir(output_directory)
    filenames.sort(reverse=True)

    for filename in filenames:
        match = filename_pattern.search(filename)
        if not match:
            continue
        return datetime.date(int(match.group('year')), int(match.group('month')), int(match.group('day')))

    # return the day before the first day on http://bggdl.square7.ch/leaderboard/
    return datetime.date(2011, 3, 10)

def save_file(date, data, is_gzipped):
    if is_gzipped:
        f = gzip.GzipFile(fileobj=StringIO.StringIO(data))
        try:
            decompressed_data = f.read()
            data = decompressed_data
        except IOError, ioe:
            log.warning('Received data was not in gzip format')
        f.close()

    data = bz2.compress(data)

    f = open(output_directory + str(date) + '.html.bz2', 'w')
    f.write(data)
    f.close()

def scrape_leaderboard(date, host, url, is_gzipped, assert_same_date):
    try:
        connection = httplib.HTTPConnection(host, timeout=30)
        connection.request('GET', url, headers={'Accept-Encoding': 'gzip'} if is_gzipped else {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
    except socket.error:
        return 'socket error'

    if assert_same_date:
        headers = dict(response.getheaders())
        if date != date_from_http_header_time(headers['last-modified']):
            return 'leaderboard updated'

    if response.status == 200:
        save_file(date, data, is_gzipped)

    return response.status

def scrape_leaderboard_from_councilroom(date):
    return scrape_leaderboard(date, 'councilroom.com', '/static/leaderboard/' + str(date) + '.html.bz2', False, False)

def scrape_leaderboard_from_bggdl(date):
    return scrape_leaderboard(date, 'bggdl.square7.ch', '/leaderboard/leaderboard-' + str(date) + '.html', True, False)

def scrape_leaderboard_from_goko(date):
    if (datetime.date.today() != date):
        return None
    else:
        return scrape_leaderboard(date, 'www.goko.com', '/games/Dominion/leaders', False, False)

def run_scrape_function_with_retries(scrape_function, date):
    num_attempts = 0

    while True:
        num_attempts += 1

        status = scrape_function(date)

        if status == 200:
            log.info('successful')
            break
        elif status == 404:
            log.info('file not found')
            break
        elif status == 'leaderboard updated':
            log.warning('the leaderboard was updated after this script was started, so re-run this script')
            break
        else:
            if num_attempts < 3:
                log.info('Status was %s, retrying', status)
            else:
                log.error('reached 3 attempts, aborting')
                break

    return status

def main():
    utils.ensure_exists(output_directory)

    date_of_last_cached_leaderboard = get_date_of_last_cached_leaderboard()
    log.info('date of the last cached leaderboard is %s', date_of_last_cached_leaderboard)

    date_of_last_goko_leaderboard = datetime.date.today()

    one_day_delta = datetime.timedelta(1)
    date = date_of_last_cached_leaderboard + one_day_delta

    while date <= datetime.date.today():
        log.info('Processing %s', date)

        if date == datetime.date.today():
            log.info('scraping from goko')
            status = run_scrape_function_with_retries(scrape_leaderboard_from_goko, date)
        else:
            log.info('scraping from councilroom')
            status = run_scrape_function_with_retries(scrape_leaderboard_from_councilroom, date)

            if status != 200 and date <= datetime.date(2013,01,01):
                log.info('scraping from bggdl')
                status = run_scrape_function_with_retries(scrape_leaderboard_from_bggdl, date)

        if status == 200:
            pass
        elif status == 404:
            log.warning('file not found, so we will assume that it does not exist, and go to the next day')
        else:
            log.warning('Unexpected status of %d, please try again later', status)
            break

        date += one_day_delta

if __name__ == '__main__':
    parser = utils.incremental_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main()
