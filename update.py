 #!/usr/bin/python

"""Standard update script to keep data up-to-date."""

import celery
import collections
import datetime
import logging
import time

import analyze
import analyze2
import background.tasks
import count_buys
import dominionstats.utils.log
import goal_stats
import load_leaderboard
import optimal_card_ratios
import run_trueskill
import scrape_leaderboard
import utils


# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def summarize_task_status(c):
    """Return a string summarize the state of the task and its children"""
    return "{tot_tasks} subtasks: {detail}".format(tot_tasks=sum(c.values()),
                                                   detail=str(c))


def watch_and_log(signature, log_interval=15, timeout=600):
    """Invoke the celery task via the passed signature, wait for it an
    all its children to complete, and log progress along the way.

    log_interval: number of seconds between checking and logging the
    status

    timeout: number of seconds after which to return, when there have
    been no subtask status updates"""
    task_name = signature.task
    log.info("Calling background task %s", task_name)

    async_result = signature.apply_async()

    all_done = False
    last_status_summary = None
    last_status_update = time.time()
    while not all_done:
        # Wait for the log_interval, then check the status
        time.sleep(log_interval)

        c = collections.Counter()
        try:
            # Setting intermediate to False should cause the
            # IncompleteStream exception to be thrown if the task and
            # its children aren't all complete.
            for parent, child in async_result.iterdeps(intermediate=False):
                c[child.state] += 1
            all_done = True
        except celery.exceptions.IncompleteStream:
            status_summary = summarize_task_status(c)
            log.info("Waiting for %s: %s", task_name, status_summary)

            # Check on timeout condition
            if (last_status_summary is not None
                and status_summary == last_status_summary
                and (time.time() - last_status_update) > timeout):
                break
            else:
                last_status_summary = status_summary
                last_status_update = time.time()

    if all_done:
        log.info("Done with background task %s: %s", task_name, summarize_task_status(c))
    else:
        log.warning("Returning due to timeout during background task %s: %s", task_name, summarize_task_status(c))
    return async_result


def main(parsed_args):
    """Primary update cycle"""

    # Scrape and load the data from goko, proceeding from the
    # previous day backwards, until no games are inserted
    today = datetime.date.today()
    log.info("Starting scrape for raw games")
    dates = utils.daterange(datetime.date(2010,10,14), today, reverse=True)
    for date in dates:
        log.info("Invoking scrape_raw_games async task for %s", date)
        async_result = watch_and_log(background.tasks.scrape_raw_games.s(date))
        inserted = async_result.get()

        if inserted is None:
            log.info("Nothing processed for %s", date)
        elif inserted == 0:
            log.info("No games inserted for %s", date)
            break

    # Invoke the analyze script
    log.info("Starting analyze")
    analyze.main(parsed_args)

    # Check for goals
    log.info("Starting search for goals acheived")
    # Check for game_stats
    log.info("Starting game_stats summarization")
    dates = utils.daterange(datetime.date(2010,10,14), today, reverse=True)
    for date in dates:
        log.info("Invoking calc_goals_for_days async task for %s", date)
        async_result = watch_and_log(background.tasks.calc_goals_for_days.s([date]))
        inserted = async_result.get()

        log.info("Invoking summarize_game_stats_for_days async task for %s", date)
        async_result = watch_and_log(background.tasks.summarize_game_stats_for_days.s([date]))
        if inserted == 0:
            log.info("No games parsed for goals on %s", date)
            break


    # Invoke the count_buys script
    log.info("Counting buys")
    count_buys.main(parsed_args)

    # Invoke the run_trueskill script
    log.info("Calculating trueskill")
    run_trueskill.main(parsed_args)

    # Invoke the optimal_card_ratios script
    log.info("Calculating optimal card ratios")
    optimal_card_ratios.main(parsed_args)

    # Invoke the goal_stats script
    log.info("Calculating goal stats")
    goal_stats.main(parsed_args)

    # Invoke the scrape_leaderboard script
    log.info("Scraping the leaderboard")
    scrape_leaderboard.main()

    # Invoke the load_leaderboard script
    log.info("Loading the leaderboard")
    load_leaderboard.main()

    log.info("Starting analyze2") # This is slow. Is it fast enough on cr?
    analyze2.main(parsed_args)
    log.info("Done with the update.py process")


if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main(args)
