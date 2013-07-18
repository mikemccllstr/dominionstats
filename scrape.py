#!/usr/bin/python

# taken from 
# http://stackoverflow.com/questions/1060279/iterating-through-a-range-of-dates-in-python

import datetime
import glob
import logging
import shutil
import os
import os.path
import subprocess
import sys
import tempfile
import time
import urllib
import utils
import re
import tarfile

# if the size of the game log is less than this assume we got an error page
SMALL_FILE_SIZE = 5000 

default_startdate = datetime.date(2010, 10, 15)

DEBUG = True

GOOD = 0
MISSING = 1
ERROR = 2
DOWNLOADED = 3
REPACKAGED = 4

CR_SOURCE = 5
GOKO_SOURCE = 6
ISO_SOURCE = 7

GOKO_LOG_RE = re.compile('"(log.\w+.\w+.txt)"', re.MULTILINE)

# Councilroom format is more similar to old isotropic format. 
GOKO_FORMAT = '%(year)d%(month)02d%(day)02d/'
ISOTROPIC_FORMAT =   '%(year)d%(month)02d/%(day)02d/all.tar.bz2'
COUNCILROOM_FORMAT = '%(year)d%(month)02d%(day)02d/%(year)d%(month)02d%(day)02d.all.tar.bz2'

def FormatDate(fmt, cur_date):
    return fmt % {
        'year': cur_date.year, 'month': cur_date.month, 'day': cur_date.day
        }

def IsotropicGamesCollectionUrl(cur_date):
    host = 'http://dominion.isotropic.org/gamelog/'
    return host + FormatDate(ISOTROPIC_FORMAT, cur_date)

def GokoGamesCollectionUrl(cur_date):
    host = 'http://archive-dominionlogs.goko.com/'
    return host+FormatDate(GOKO_FORMAT, cur_date)

def GokoSingleGameUrl(cur_date, cur_game):
    return GokoGamesCollectionUrl(cur_date)+cur_game

def CouncilroomGamesCollectionUrl(cur_date):
    host = 'http://councilroom.com/static/scrape_data/'
    return host + FormatDate(COUNCILROOM_FORMAT, cur_date)

def RemoveSmallFileIfExists(fn):
    if (os.path.exists(fn) and 
        os.stat(fn).st_size <= SMALL_FILE_SIZE):
        print 'removing small existing file', fn
        os.unlink(fn)

def download_date(str_date, cur_date, saved_games_bundle):
    urls_by_priority = [
                        (CR_SOURCE, CouncilroomGamesCollectionUrl(cur_date)),
                        (GOKO_SOURCE, GokoGamesCollectionUrl(cur_date)),
                        (ISO_SOURCE, IsotropicGamesCollectionUrl(cur_date))
                        ] 

    for (source, url) in urls_by_priority:
        if DEBUG:
            print 'getting', saved_games_bundle, 'at', url

        try:
            contents = urllib.urlopen(url).read()
        except IOError:
            contents = "0"

        if len(contents) > SMALL_FILE_SIZE:
            if DEBUG:
                print 'yay, success from', url, 'no more requests for', \
                    str_date, 'needed'
            if source == CR_SOURCE or source == ISO_SOURCE:
                open(saved_games_bundle, 'w').write(contents)
            elif source == GOKO_SOURCE:
                games = re.findall(GOKO_LOG_RE, contents)
                bundle_goko_games(cur_date, games, saved_games_bundle)
            return True
        elif DEBUG:
            print 'request to', url, 'failed to find large file'
    return False

def bundle_goko_games(cur_date, games, saved_games_bundle):
    progressfile = tempfile.mktemp()
    bundle = tarfile.open(progressfile,'w:bz2')

    orig_dir = os.getcwd()
    directory_name = tempfile.mkdtemp()
    os.chdir(directory_name)

    if DEBUG:
        print len(games), " games to download..."
    for cur_game in games:
        url = GokoSingleGameUrl(cur_date, cur_game)
        retries_remaining = 3
        while retries_remaining > 0:
            try:
                game_text = urllib.urlopen(url).read()
                if '<title>403 Forbidden' not in game_text and '<title>404 Not Found' not in game_text:
                    game =  open(cur_game,'a')
                    game.write(game_text)
                    game.close() 

                    bundle.add(cur_game)
                    break
                else:
                    retries_remaining = retries_remaining - 1
                    if(DEBUG):
                        print "Failed to download game: ", cur_game

            except:
                retries_remaining = retries_remaining - 1
                if(DEBUG):
                    print "Failed to download game: ", cur_game
    bundle.close();
    os.chdir(orig_dir)
    os.rename(progressfile, saved_games_bundle)
    shutil.rmtree(directory_name)

def unzip_date(directory, filename):
    os.chdir(directory)
    cmd = 'tar -xjvf %s >/dev/null 2>/dev/null'%filename
    if DEBUG:
        print cmd

    ret = os.system(cmd)
    if ret==0:
        os.system('chmod -R 755 .')
        code = True
    else:
        code = False
    os.chdir('..')
    return code


def repackage_filename(orig_archive_filename):
    return orig_archive_filename.replace(".all.tar.bz2", ".bz2.tar")
    

def repackage_archive(filename):
    """ Converts a .tar.bz2 file into a .bz2.tar file in the same directory.

    Game archives are distributed as .tar.bz2 (a bzip2-compressed tar
    archive). For speed of serving, we repackage them as .bz2.tar (a
    tar archive of bzip2-compressed HTML or text files). The .bz2.tar file is
    a good bit larger, but an individual file can be extracted,
    decompressed, and served to a client in tenths of a second instead
    of tens of seconds. At the same time, storage space is still
    dramatically smaller than a raw folder of uncompressed (or even
    compressed) HTML or text files.
    """

    orig_dir = os.getcwd()

    # Extract the existing file into a temporary folder
    directory_name = tempfile.mkdtemp()
    source_filename = os.path.abspath(filename)
    
    try:
        subprocess.check_call(["tar", "--auto-compress", "-C", directory_name,
                               "-xf", source_filename])
    except subprocess.CalledProcessError, e:  
        # Not handling this yet, just re-raise
        logging.warning("Unexpected return from tar >>{msg}<<".format(msg=e.output))
        raise

    # Compress all the game*.html log*txt files. 
    # Individually, so the argument list doesn't explode from huge numbers of 
    # goko logs. 
    os.chdir(directory_name)
    game_files = glob.glob("game*.html")+glob.glob("log*.txt")
    dest_filename = repackage_filename(source_filename)

    repackaged_archive = tarfile.open(dest_filename,'w')

    for cur_game in game_files:
        try:
            subprocess.check_call(["bzip2", cur_game])
        except subprocess.CalledProcessError, e:  #(retcode, cmd, output=output)
            # Not handling this yet, just re-raise
            logging.warning("Unexpected return from bzip or tar >>{msg}<<".format(msg=e.output))
            os.chdir(orig_dir)
            shutil.rmtree(directory_name)
            raise
        repackaged_archive.add(cur_game+'.bz2')

    repackaged_archive.close();
    os.chdir(orig_dir)
    shutil.rmtree(directory_name)

def scrape_date(str_date, cur_date, passive=False):
    #directory = str_date
    games_short_name = str_date + '.all.tar.bz2'
    saved_games_bundle = games_short_name
    return_code = ERROR

    if utils.at_least_as_big_as(saved_games_bundle, SMALL_FILE_SIZE):
        if DEBUG:
            print 'skipping because exists', str_date, saved_games_bundle, \
                'and not small (size=', os.stat(saved_games_bundle).st_size, ')'
        return_code = GOOD
    else:
        RemoveSmallFileIfExists(saved_games_bundle)

        if passive:
            return_code = MISSING
        elif not download_date(str_date, cur_date, saved_games_bundle):
            return_code = ERROR
        else:
            return_code = DOWNLOADED

    # Repackage an existing file, if found
    if utils.at_least_as_big_as(saved_games_bundle, SMALL_FILE_SIZE) and \
            not os.path.exists(repackage_filename(saved_games_bundle)):
        repackage_archive(saved_games_bundle)
        return_code = REPACKAGED

    return return_code


def scrape_games():
    parser = utils.incremental_date_range_cmd_line_parser()
    utils.ensure_exists('static/scrape_data')
    os.chdir('static/scrape_data')

    args = parser.parse_args()
    last_month = ''
    
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    #Goko updates logs in real time; wait a day so the list is finalized.

    for cur_date in utils.daterange(default_startdate, yesterday, reverse=True):
        str_date = time.strftime("%Y%m%d", cur_date.timetuple())
        if not utils.includes_day(args, str_date):
            if DEBUG:
                print 'skipping', str_date, 'because not in cmd line arg daterange'
            continue
        mon = time.strftime("%b%y", cur_date.timetuple())
        if mon != last_month:
            print
            print mon, cur_date.day*"  ",
            sys.stdout.flush()
            last_month = mon
        ret = scrape_date(str_date, cur_date, passive=args.passive)
        if ret==DOWNLOADED:
            print 'o',
        elif ret==REPACKAGED:
            print 'O',
        elif ret==ERROR:
            print '!',
        elif ret==MISSING:
            print '_',
        else:
            print '.',
        sys.stdout.flush()
    print
    os.chdir('../..')


if __name__=='__main__':
    scrape_games()
                        
