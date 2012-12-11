import logging
import utils
import game
from keys import *
from name_merger import norm_name

def calculate_game_stats(log, games, game_stats):
    """ Save game statistics for each game and player

    log: Logging Object
    games: List of games to analyze, each in dict format
    game_stats: Destination MongoDB collection
    """
    log.debug("Beginning to analyze game statistics for %d games", len(games))
    game_stats.ensure_index(NAME)
    for game_dict in games:
        game_val = game.Game(game_dict)
        g_id = game_dict['_id']
        date = game_dict['game_date']
        supply = game_dict[SUPPLY]

        for p in get_game_stat_entries(game_val, g_id, date, supply):
            game_stats.save(p)
            

def get_game_stat_entries(game_val, g_id, date, supply):
    ret = []
    if game_val.dubious_quality():
        return ret
    all_p = game_val.all_player_names()
    for full_name in all_p:
        m = {}
        name = norm_name(full_name)
        m['_id'] = "%s/%s" % (g_id, name)
        m[NAME] = name
        m[PLAYERS] = [p for p in all_p if p != full_name]
        m['game_date'] = date

        pd = game_val.get_player_deck(full_name)
        m[WIN_POINTS] = pd.WinPoints()
        m[RESULT] = game_val.win_loss_tie(full_name)
        m[ORDER] = pd.TurnOrder()
        m[SUPPLY] = supply
        ret.append(m)

    return ret

if __name__=='__main__':            
    log = logging.getLogger(__name__)
    db = utils.get_mongo_database()
    games = db.games
    game_stats = db.game_stats

    norm_target_player = 'hawaiian shirts'
    games_coll = games.find({PLAYERS: norm_target_player})

    calculate_game_stats(log, list(games_coll), game_stats)



