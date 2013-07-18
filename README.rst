dominionstats
=============
This is the code behind http://councilroom.com. Feel free to fork it to make
it do interesting new things.

The project is run by rrenaud (rrenaud@gmail.com), with contributions so far by
Larry, rspeer, David Lu, and tlstyer.


Installation
====

Turbo frontend javascript hacking
====
super easy frontend modifications without any server setup::

     checkout code from github.
     google-chrome --allow-file-access-from-files
     browse to local html pages (eg, dominionstats/supply_win.html).
     edit local javascript files.

I just want access to some data!
====
Send (rrenaud@gmail.com) a mail and I'll see what I can do.

Long, ardous but incredibly rewarding full setup
====
The code depends on:

- Python version 2.6 or 2.7
- mongodb (http://www.mongodb.org) (1.5.3+ or later)
- pymongo (http://api.mongodb.org/python/1.9%2B/index.html)
- web.py (http://webpy.org)
- argparse (included in Python 2.7/3.2)
- simplejson (http://pypi.python.org/pypi/simplejson/)

Ubuntu Installation Commands for pymongo and webpy::

     sudo pip install pymongo
     sudo easy_install web.py
     mkdir db

Run an instance of mongodb with::

     mongod --dbpath=db

After install those packages, the system can be setup by running the 
update_loop.py script, which will take a few hours to download one months of 
games logs from councilroom, and then parse through it all and load it into a 
database::

     python update_loop.py 
These instructions are outdated and no longer work. Use update.py, which is run through a worker script.


And after that is down, this starts webserver running on localhost:8080::

     python frontend_local.py 

Hacking Guidelines
====
Python code: 
  - Write it in pep8, even if I didn't all the time.  
  - Wrap lines at 80 characters.
  - Try not to write super long functions, break them up into logical subfunction even if those functions are only called once.
    
  - Did you see something in the code is fugly and offends your natural sense of what is good in the world?  I'll happily take style cleanups.

  - Anatomy of an analysis.
     + Want analysis to be incremental, can go day at a time.
        * Use an incremental_scanner.
        * Prefer using game.Game objects over raw game docs from the database.  game.Game objects are easier to work with, and make maintence easier.
        * Since we want to be incremental, store raw counts in database, normalize them with divisions, etc at presentation time.
        * Want to keep track of a random variable that has some kind of spread? Use a stats.MeanVarStat.
        * Consider using primitive_util for serializing/deserializing objects that store the aggregate information.  
   
  - How to do display?
      + Lots of existing server side templating in Python.
      + Prefer templates to programatically building up strings (even if if the existing code doesn't always).
      + Seriously consider outputting JSON from server like (/supply_win_api) and doing presententation in javascript (/supply_win), since it allows frontend development without running the whole system.  

Javascript code:
  * Keep non-trivial bits of Javascript in seperate .js files rather than embedded in HTML.  It makes my emacs happier.

Got a technical problem/question/idea?  You can send an email to the dev group,

https://groups.google.com/forum/?fromgroups#!forum/councilroom-dev

Happy hacking.
