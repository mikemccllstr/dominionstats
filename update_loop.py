import os
import time
from datetime import date, timedelta
import utils 

import sys

utils.ensure_exists('static/status')

cmds = [
    'python scrape.py',
    'python parse_game.py',
    'python load_parsed_data.py ',
    'python analyze.py', 
    'python goals.py',
    'python count_buys.py',
    'python run_trueskill.py',
    'python optimal_card_ratios.py',
    'python goal_stats.py',
    'python scrape_leaderboard.py',
    'python load_leaderboard.py',
]

extra_args = sys.argv[1:]

# should think about how to parrallelize this for multiprocessor machines.
while True:
    for cmd in cmds:
        month_ago = (date.today() - timedelta(days=30)).strftime('%Y%m%d')
        fmt_dict = {'month_ago': month_ago}
        cmd = (cmd % fmt_dict)
        status_fn = (cmd.replace(' ', '_') + '-' + 
                     date.today().isoformat() + '-' +
                     time.strftime('%H:%M:%S') + '.txt')
        cmd = cmd + ' ' + ' '.join(extra_args) + ' 2>&1 | tee -a ' + status_fn
        print cmd
        os.system(cmd)
        os.system('mv %s static/status' % status_fn)
    print 'sleeping'
    time.sleep(60*60*6)  # try to update every 6 hours. 

