#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: Add copyright notice here

"""Scraping support for Goko.
"""

import boto.s3.connection
import bson.binary
import bz2
import cStringIO
import datetime
import io
import logging
import sys
import tarfile
import urllib2

import utils
import os
import shutil
import subprocess
import tempfile
import time


# Module-level logging instance
log = logging.getLogger(__name__)

#s3_location = 'ftl-goko-councilroom-test-bucket'
s3_location = 'static.councilroom.mccllstr.com'

class GokoProcessingDate(object):
    # TODO: This is a partial implementation

    tracker = None
    date = None
    date_dict = None

    class Key(object):
        """Names of MongoDB keys"""
        GAME_DATE = 'game_date'
        STEPS = 'steps'

    def __init__(self, tracker, date):
        self.tracker = tracker
        self.date = date

        self.date_dict = tracker.tracker_col.find_one({self.Key.GAME_DATE: date,})
        if self.date_dict == None:
            self.date_dict = {self.Key.GAME_DATE: date,
                              self.Key.STEPS: []}
            tracker.tracker_col.save(self.date_dict)


class GokoTracker(object):
    """
    """
    # TODO: This is a partial implementation

    db = None
    tracker_col = None
    leaderboard_history_col = None
    raw_games_col = None

    def __init__(self, db):
        self.db = db
        self.tracker_col = db.goko_tracker
        self.raw_games_col = db.raw_games

    def scraped_game_count(self, date):
        """Count the number of raw games loaded for the specified date

        date is a string in the format 'YYYYMMDD'
        """
        return self.raw_games_col.find({'game_date': date}).count()




def dates_needing_scraping(db):
    # TODO: This is a partial implementation
    it = GokoTracker(db)

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    for cur_datetime in utils.datetimerange(datetime.date(2012,8,5),
                                            yesterday):
        str_date = time.strftime("%Y%m%d", cur_date.timetuple())

        # Check on the status of the day in our scraper tracker
        raw_game_count = raw_games_col.find({'game_date': str_date}).count()


class ScrapeError(Exception):
    """Indicates an error with the requested scrape."""
    def __init__(self, reason):
        self.args = reason,
        self.reason = reason

    def __str__(self):
        return '<scrape error %s>' % self.reason


class GokoScraper:
    """Implements the functions necessary to scrape data (games, not yet
    leaderboards) from Goko or its related mirrors.
    """

    db = None
    rawgames_col = None
    s3conn = None

    def __init__(self, db, rawgames_name='raw_games'):
        self.db = db
        if db:
            self.rawgames_col = db[rawgames_name]


    def our_gamelog_filename(self, gamedate):
        """Returns our filename of the rawgame archive for the specified datetime.date"""
        return '{date.year:04d}{date.month:02d}{date.day:02d}.all.tar.bz2'.format(date=gamedate)

    def gamelog_local_filename(self,gamedate):
        """Returns the local path to the rawgame archive for the specified datetime.date"""
        return 'static/scrape_data/{filename}'.format(filename=self.our_gamelog_filename(gamedate))

    def gamelog_s3_keyname(self, gamedate):
        """Returns the S3 keyname for the rawgame archive for the specified datetime.date"""
        return 'scrape_data/{filename}'.format(filename=self.our_gamelog_filename(gamedate))


    def goko_rawgame_url(self, gamedate):
        """Returns the URL to the rawgame folder at goko for the specified datetime.date"""
        return 'http://archive-dominionlogs.goko.com/{date.year:04d}{date.month:02d}{date.day:02d}/'.format(date=gamedate)


    def s3_rawgame_url(self, gamedate):
        """Returns the URL to the rawgame archive in S3 for the specified datetime.date"""
        return 'http://'+s3_location+'/{keyname}'.format(keyname=self.gamelog_s3_keyname(gamedate))


    def establish_s3_connection(self):
        """Get a boto connection for s3 operations using credentials from the ini file"""
        if self.s3conn is None:
            self.s3conn = boto.s3.connection.S3Connection(**utils.get_aws_credentials())


    def is_rawgames_in_s3(self, date):
        """Returns true if there is a whole-day rawgame archive in S3 for the specified date"""
        self.establish_s3_connection()

        bucket = self.s3conn.get_bucket(s3_location)
        return bucket.get_key(self.gamelog_s3_keyname(date)) is not None


    def copy_rawgames_to_s3(self, date):
        """Copy the day's archive of rawgames from goko to our S3 bucket.
        Does not save a local copy."""

        current_directory = os.getcwd()
        directory_name = tempfile.mkdtemp()
        os.chdir(directory_name)
        str_date = time.strftime("%Y%m%d", date.timetuple())
        try:
            subprocess.check_call([current_directory + '/multi_scrape.sh', str_date])
        except subprocess.CalledProcessError, e:
            logging.warning("Unexpected return from scraper: {msg}".format(msg=e.output))
            os.chdir(orig_dir)
            shutil.rmtree(directory_name)
            raise

        os.chdir(current_directory)

        self.establish_s3_connection()

        # Upload the contents to s3 in the appropriate key
        bucket = self.s3conn.get_bucket(s3_location)
        key = bucket.get_key(self.gamelog_s3_keyname(date))
        if not key:
            log.debug("Creating new key")
            key = bucket.new_key(self.gamelog_s3_keyname(date))
            log.debug("Starting upload from local copy to s3")
            key.set_contents_from_filename(directory_name+'/'+self.our_gamelog_filename(date),
                                       cb=lambda sent, total: log.info('Transferred %d of %d', sent, total),
                                       replace=False, policy='public-read')
        shutil.rmtree(directory_name) 


    def get_rawgames_from_s3(self, date):
        """Return the whole-day rawgame archive from our S3 bucket for
        the specified datetime.date"""
        self.establish_s3_connection()
        bucket = self.s3conn.get_bucket(s3_location)
        key = bucket.get_key(self.gamelog_s3_keyname(date))
        return key.get_contents_as_string()


    def get_rawgames_from_s3_as_filelike(self, date):
        """Return the whole-day rawgame archive from our S3 bucket for
        the specified datetime.date, wrapped in a filelike object"""
        return cStringIO.StringIO(self.get_rawgames_from_s3(date))


    def scrape_and_store_rawgames(self, date):
        """Top-level function to scrape rawgames from goko and
        store them in the local database.

        Accepts a datetime.date as the date to scrape.
        Returns the number of games inserted.

        Will skip (noop) dates that have already been loaded.
        """
        yyyy_mm_dd = date.strftime('%Y%m%d')

        # We expect to operate from data stored in our S3 bucket, so
        # check that it is available, first.
        if not self.is_rawgames_in_s3(date):
            # Not in S3 yet, get it and store it
            self.copy_rawgames_to_s3(date)

        # Retrieve the game archive for the specified date
        rawgames_archive_contents = self.get_rawgames_from_s3_as_filelike(date)

        # Insert the individual games into MongoDB
        insert_count = 0
        with tarfile.open(fileobj=rawgames_archive_contents) as t:
            # Figure out how many raw games are in the database,
            # compared with how many are in the tarfile
            database_count = self.rawgames_col.find({'game_date': yyyy_mm_dd}).count()
            tarfile_count = len(t.getmembers())
            if tarfile_count <= database_count:
                log.info("Raw games for %s have already been loaded", yyyy_mm_dd)
            else:
                # Insert all the games
                for tarinfo in t:
                    log.debug("Working on %s", yyyy_mm_dd+'/'+tarinfo.name)
                    g = { u'_id': yyyy_mm_dd+'/'+tarinfo.name,
                          u'game_date': yyyy_mm_dd,
                          u'text': bson.Binary(bz2.compress(t.extractfile(tarinfo).read())) }
                    self.rawgames_col.save(g, safe=True)
                    insert_count += 1

        rawgames_archive_contents.close()

        return insert_count
