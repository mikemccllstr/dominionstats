#!/usr/bin/python

import collections
import logging
import operator

from keys import TRASHES
import dominioncards
import dominionstats.utils.log
import game
import incremental_scanner
import name_merger
import utils


# Module-level logging instance
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def GroupFuncs(funcs, group_name):
    """Attach group and priority to functions in funcs so they are sortable."""
    for idx, func in enumerate(funcs):
        func.group = group_name
        func.priority = idx

def achievement(player, reason, sort_key=None):
    ach = {'player': player,
           'reason': reason}
    if sort_key is not None:
        if type(sort_key) != type(0):
            sort_key = str(sort_key)
        ach['sort_key'] = sort_key
    return ach

def CheckMatchBOM(g):
    """Bought only money and Victory."""
    ret = []
    cards_per_player = g.cards_accumalated_per_player()
    for player, card_list in cards_per_player.iteritems():
        treasures = []
        bad = False
        if g.get_player_deck(player).Resigned():
            continue
        for card in card_list:
            if card.is_action():
                bad = True
                break
            if card.is_treasure():
                treasures.append(card.singular)
        if not bad:
            reason = 'Bought only money and vp : %s' % (', '.join(treasures))
            ret.append(achievement(player, reason))
    return ret

def CheckMatchBOMMinator(g):
    """Won buying only money and Victory."""
    cands = CheckMatchBOM(g)
    ret = []
    for match_dict in cands:
        player = match_dict['player']
        if g.get_player_deck(player).WinPoints() > 1.0:
            ret.append(achievement(player, match_dict['reason'] + ' and won'))
    return ret

# Salted Earth: Had a negative score.

def CheckMatchGolfer(g):
    """Winning with a negative score"""
    if g.any_resigned():
        return []
    ret = []
    for player in g.get_player_decks():
        if player.WinPoints() > 1.0 and player.Points() < 0:
            points = player.Points()
            ret.append(achievement(player.name(),
                        'Won with a negative score, %d points' % points,
                        points))
    return ret

def CollectedAllCopies(g):
    """Return a dict mapping a player to a list of all the card
       names that the player gained all the copies of"""
    accumed_per_player = g.cards_accumalated_per_player()
    gain_map = collections.defaultdict(list)
    game_size = len(g.get_player_decks())

    for player, card_dict in accumed_per_player.iteritems():
        for card, quant in card_dict.iteritems():
            if quant >= card.num_copies_per_game(game_size):
                gain_map[player].append(card)
    return gain_map

def CheckMatchPileDriver(g):
    """Gained all copies of a card and won."""
    gain_map = CollectedAllCopies(g)
    ret = []
    for player, piles_gained in gain_map.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            if len(piles_gained)==1:
                card = piles_gained[0]
                if card == dominioncards.Curse:
                    continue
                ret.append(
                    achievement(player, 'Gained all copies of %s (and won)' % card.singular, card.index))
    return ret

def CheckMatchPurplePileDriver(g):
    """Gained all the curses and won."""
    gain_map = CollectedAllCopies(g)
    ret = []

    for player, piles_gained in gain_map.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            for card in piles_gained:
                if card == dominioncards.Curse:
                    ret.append(
                        achievement(player, 'Gained all the curses (and won)'))
    return ret

def CheckMatchDoublePileDriver(g):
    """Gained all copies of twp different cards and won."""
    gain_map = CollectedAllCopies(g)
    ret = []

    for player, piles_gained in gain_map.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            if len(piles_gained)==2:
                ret.append(
                    achievement(player, 'Gained all copies of %s AND %s (and won)' % (
                            piles_gained[0].singular, piles_gained[1].singular), [c.index for c in piles_gained]))
    return ret

def CheckMatchTriplePileDriver(g):
    """Gained all copies of three different cards and won."""
    gain_map = CollectedAllCopies(g)
    ret = []

    for player, piles_gained in gain_map.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            if len(piles_gained)==3:
                ret.append(
                    achievement(player, 'Gained all copies of %s, %s AND %s (and won)' % (
                            piles_gained[0].singular, piles_gained[1].singular, piles_gained[2].singular), [c.index for c in piles_gained]))
    return ret

GroupFuncs([CheckMatchPileDriver, CheckMatchDoublePileDriver, CheckMatchTriplePileDriver], 'piledriver')

def CheckMatchOneTrickPony(g):
    """Bought only one type of action"""
    if g.any_resigned():
        return []
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    for player, card_dict in accumed_per_player.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            actions_quants = [(c, q) for c, q in card_dict.iteritems() if
                              c.is_action()]
            if len(actions_quants) != 1:
                continue
            if actions_quants[0][1] < 7:
                continue
            action, quant = actions_quants[0]
            ret.append(
                achievement(player,
                            'Bought no action other than %d %s' % (
                        quant, action.pluralize(quant)),
                            action))
    return ret

def CheckMatchMrGreenGenes(g):
    """Bought 6 differently named Victory cards"""
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    for player, card_dict in accumed_per_player.iteritems():
        victory_quants = [(c, q) for c, q in card_dict.iteritems() if
                          c.is_victory()]
        if len(victory_quants) >= 6:
            ret.append(achievement(player,
                    'Bought %d differently named Victory cards' %
                    len(victory_quants), len(victory_quants)))
    return ret

def CheckScore(g, low, high=None):
    ret = []
    for player in g.get_player_decks():
        score = player.points
        if score >= low and (high is None or score < high):
            ret.append(achievement(player.name(),
                                   "Scored more than %d points" % low, score))
    return ret

def CheckMatchPeer(g):
    """Scored more than 60 points"""
    return CheckScore(g, 60, 70)

def CheckMatchRegent(g):
    """Scored more than 70 points"""
    return CheckScore(g, 70, 80)

def CheckMatchRoyalHeir(g):
    """Scored more than 80 points"""
    return CheckScore(g, 80, 90)

def CheckMatchMonarch(g):
    """Scored more than 90 points"""
    return CheckScore(g, 90, 100)

def CheckMatchImperial(g):
    """Scored more than 100 points"""
    return CheckScore(g, 100, 110)

def CheckMatchArchon(g):
    """Scored more than 110 points"""
    return CheckScore(g, 110)

GroupFuncs([CheckMatchPeer, CheckMatchRegent, CheckMatchRoyalHeir,
            CheckMatchMonarch, CheckMatchImperial, CheckMatchArchon], 'vp')

# Win by X points
# Come From X points behind
# "Subjugation" ... win a 3-player game with more points than the other 2 players combined
# "Domination"... win a 4-player game with more points than the other 3 players combined

# == How the game ends
def CheckMatchBuzzerBeater(g):
    """Won by exactly one point"""
    if g.any_resigned():
        return []
    scores = {}
    for player in g.get_player_decks():
        score = player.points
        scores[player.name()] = score
    s_scores = sorted(scores.iteritems(),
                      key=operator.itemgetter(1), reverse=True)
    if len(s_scores)>1 and s_scores[0][1] == s_scores[1][1] + 1:
        return [achievement(s_scores[0][0], "Won by exactly one point")]
    else:
        return []

def CheckMatchAnticlimactic(g):
    """Shared a victory with two or more opponents"""
    num_players = len(g.get_player_decks())

    if num_players == 3:
        max_score = 1.0
    elif num_players == 4:
        max_score = 4.0/3
    else:
        return []

    ret = []
    for player in g.get_player_decks():
        wp = player.WinPoints()
        if wp > max_score:
            return ret
        elif wp!=0.0:
            ret.append(
                achievement(player.name(),
                            'Shared a victory with two or more opponents'))

    return ret

def CheckMatchTheFlash(g):
    """Won in less than 10 turns"""
    if g.any_resigned():
        return []
    for player in g.get_player_decks():
        if player.WinPoints() > 1.0 and player.num_turns() < 10:
            return [achievement(player.name(), "Won in %d turns" % player.num_turns())]

    return []

# "Walk-off Home Run" -- when you come from behind on your last turn to both end and win the game.
#("The Biggest Loser") Losing with over 60 points.
# Surprise Attack - end the game on supply piles when those three piles had totaled at least 5 cards at the start of your turn.
# Badges? We Don't Need No Stinking Badges: Win a game while holding no VP Tokens and your opponent holds 25 or more.

#("Penny Pincher") Winning by buying out the Coppers
#("Estate Sale") Winning by buying out the Estates
# Denied: Won the game by ending it on piles after a turn featuring 10 or more buys

# == Value of victory points
def CheckMatchVintner(g):
    """Obtained at least 30 VP from Vineyards"""
    ret = []
    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        if dominioncards.Vineyard not in deck:
            continue
        vy_pts = game.score_vineyard(deck)
        if vy_pts >= 30:
            ret.append(achievement(player,
                                   '%d VP from Vineyards' % vy_pts, vy_pts))
    return ret

def CheckMatchCarny(g):
    """Obtained at least 30 VP from Fairgrounds"""
    # Original suggestion: Blue ribbon - ended game with a Fairgrounds worth
    # 8 VP
    ret = []
    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        if dominioncards.Fairgrounds not in deck:
            continue
        fg_pts = game.score_fairgrounds(deck)
        if fg_pts >= 30:
            ret.append(achievement(player,
                                   '%d VP from Fairgrounds' % fg_pts, fg_pts))
    return ret

def CheckMatchGardener(g):
    """Obtained at least 20 VP from Gardens"""
    # Original suggestion: ended game with a Gardens worth 6 VP
    ret = []
    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        if dominioncards.Gardens not in deck:
            continue
        g_pts = game.score_gardens(deck)
        if g_pts >= 20:
            ret.append(achievement(player,
                                   '%d VP from Gardens' % g_pts, g_pts))

    return ret

def CheckMatchDukeOfEarl(g):
    """Obtained at least 42 points from Dukes and Duchies"""
    # originally suggested as Duchebag
    ret = []
    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        if dominioncards.Duke not in deck:
            continue
        duke_pts = game.score_duke(deck)
        duchy_pts = deck.get(dominioncards.Duchy, 0) * 3
        d_pts = duke_pts + duchy_pts
        if d_pts >= 42:
            ret.append(achievement(player, '%d VP from Dukes and Duchies' %
                                   d_pts, d_pts))
    return ret

def CheckMatchSilkTrader(g):
    """ Obtained at least 20 points from Silk Road"""
    ret = []
    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        if dominioncards.SilkRoad not in deck:
            continue
        g_pts = game.score_silk_road(deck)
        if g_pts >= 20:
            ret.append(achievement(player,
                                   '%d VP from Silk Road' % g_pts, g_pts))

    return ret

# Who Needs Green Cards?
# vineyards award would be nice. how about "sideways" ... http://www.sideways-movie.com/sideways.jpg
# Underboss/Mafia Don/Godfather for scoring 30/40/50 VP with Goons?
# DHARMA Initiative: set aside 8+ Islands

GroupFuncs([CheckMatchCarny, CheckMatchGardener, CheckMatchDukeOfEarl,
            CheckMatchSilkTrader, CheckMatchVintner], 'vvp')

# == Use of one card in a turn
#("Puppet Master") Play more than 4 Possession in one turn.
# Crucio: Use the Torturer three times in a single turn.
# Imperio: Use Possession three times in a single turn.
# Time Lord: played 10 (20?) Duration actions in one turn
# Buy-More: Used 10 Buy-actions in one turn (or 15?)

# == Every Turn
# Protego: Reacted to all attacks against you (and at least 5).
# Tour de France: Cycled through entire deck in 5 consecutive turns

def CheckMatchBully(g):
    """Played an attack every turn after turn 4"""
    if g.any_resigned():
        return []
    players = set(g.all_player_names())

    for turn in g.get_turns():
        if turn.get_turn_no() <= 4:
            continue
        player = turn.player.player_name
        if player not in players:
            continue
        attack = False
        for play in turn.plays:
            if play.is_attack():
                attack = True
                break
        if not attack:
            players.remove(player)
            if len(players) == 0:
                break
    return [achievement(player, 'Played an attack every turn after turn 4') for player in players]

# == Never Use Cards
# Empty Throne Room
# Empty Kings Court
# Arrested Development: Bought 3+ Develop cards without ever using them

# == Number of Cards acquired

def one_turn(g, player, cardList):
    """Returns true if 'player' bought/gained the cards in the cardList only on one turn"""
    found = False
    for turn in g.turns:
        if turn.player.player_name==player:
            buysgains = turn.buys + turn.gains
            for card in cardList:
                if card in buysgains:
                    if found:
                        return False
                    else:
                        found = True
                        break
    return found

def prize_check(g):
    if dominioncards.Tournament not in g.supply:
        return (False, False)

    for pdeck in g.get_player_decks():
        (player, deck) = (pdeck.player_name, pdeck.deck)
        n_prizes = 0
        for prize in dominioncards.TOURNAMENT_WINNINGS:
            if prize in deck:
                n_prizes += 1
        if n_prizes == len(dominioncards.TOURNAMENT_WINNINGS):
            return (player, one_turn(g, player, dominioncards.TOURNAMENT_WINNINGS))
    return (False, False)

def CheckMatchPrizeFighter(g):
    """Acquire all five prizes"""
    # a.k.a. King of the Joust
    (player, in_one_turn) = prize_check(g)
    ret = []
    if player and not in_one_turn:
        ret.append(achievement(player, 'Acquired all five prizes'))
    return ret

def CheckMatchChampionPrizeFighter(g):
    """Acquire all five prizes in one turn"""
    (player, in_one_turn) = prize_check(g)
    ret = []
    if player and in_one_turn:
        ret.append(achievement(player, 'Acquired all five prizes in one turn'))
    return ret


GroupFuncs([CheckMatchPrizeFighter, CheckMatchChampionPrizeFighter], 'prizes')

# "Moneyball" should be winning a game without ever buying a card costing $5 or more (base cost, can't use Highway/Bridge to get around it)
# Platinum Blonde: At game's end, have only Platinum and Gold Treasures (and at least 1 of each)
# Won without buying treasure

# Fringe Division: Finished game with 5+ Potions and exactly 2 Bishops
# Snow White: played 7 Wharves in one turn
# O Canada!: Finish with exactly 10 Provinces and 3 Duchys (territories) [obviously only attainable in 3+ player games]
# TARDIS: Finish a game with a deck where the total of all "+X Card(s)" is higher than (or if that's too easy, then over double) the number of cards. Not sure if this is an easy one to program or not.
# Paid in Pennies: Won a game with no Gold/Platinum in your deck

# Researcher: Acquire 7 Alchemists or Laboratories.
# Evil Overlord: Acquire 7 or more Minions.
# It's Good to be the King: Acquire 4 Throne Rooms or King's Courts.
# 99 Problems: Acquire the majority of Harems.
# Game of Settlers Anyone?: Acquire 7 of a single Village-type card.
# won without ever buying money
#("Dominator") Have at least one of each type of available victory card (and at least 1 chip, if available).
# buying at least one of every kingdom card in a game
# Vairagya (Renunciation of Worldly Desires): Ended the game with less cards in the deck than you started with.

# == Specific Uses
# Used Possession+Masquerade to send yourself a Province or Colony
# gifted a Province or Colony to an opponent (through Masquerade or Ambassador),
# De-model - remodeled a card into a card that costs less
# Look Out! - revealed three 6+-cost cards with Lookout
# Name it - 5 Correct wishes
#("This card sucks?") Winning with an Opening Chancellor
# Treasure Map multiple times
# "Supermodel" for having Remodelled X cards in one game...
# "The Donald" -- Trashed 3+ Apprentices


# Banker - played a Bank worth $10
def CheckMatchBanker(g):
    """Played a Bank worth $10"""
    ret = []
    if dominioncards.Bank not in g.supply:
        return ret

    for turn in g.get_turns():
        treasure_count = 0
        for card in turn.plays:
            if card.is_treasure():
                treasure_count += 1
                if card == dominioncards.Bank:
                    if treasure_count >= 10:
                        ret.append(achievement(turn.player.player_name,
                                "Played a Bank worth $%d" % treasure_count))
    return ret

def CheckActionsPerTurn(g, low, high=None):
    ret = []
    for turn in g.get_turns():
        action_count = 0
        for card in turn.plays:
            if card.is_action():
                action_count += 1

        if action_count >= low and (high is None or action_count < high):
            ret.append(achievement(turn.player.player_name,
                    "Played %d or more actions in one turn" % low, action_count))
    return ret

def CheckMatchActionStar(g):
    """Played at least 25 actions in a turn"""
    return CheckActionsPerTurn(g, 25, 30)

def CheckMatchMegaActionStar(g):
    """Played at least 30 actions in a turn"""
    return CheckActionsPerTurn(g, 30, 40)

def CheckMatchSuperActionStar(g):
    """Played at least 40 actions in a turn"""
    return CheckActionsPerTurn(g, 40)


GroupFuncs([CheckMatchActionStar, CheckMatchMegaActionStar, CheckMatchSuperActionStar], 'actions')

def CheckPointsPerTurn(g, low, high=None):
    ret = []
    scores = []
    players = g.all_player_names()
    for state in g.game_state_iterator():
        score = []
        for p in players:
            score.append(state.player_score(p))
        scores.append(score)

    for (i,p) in enumerate(players):
        for turn_no in range(i, len(scores)-1):
            gain = scores[turn_no+1][i] - scores[turn_no][i]
            if gain >= low and (high is None or gain < high):
                ret.append(achievement(p,
                        "Scored %d or more points in one turn" % low, gain))
    return ret

def CheckMatchSlam(g):
    """Obtained 20 or more points in one turn"""
    return CheckPointsPerTurn(g, 20, 30)

def CheckMatchCrash(g):
    """Obtained 30 or more points in one turn"""
    return CheckPointsPerTurn(g, 30, 40)

def CheckMatchCharge(g):
    """Obtained 40 or more points in one turn"""
    return CheckPointsPerTurn(g, 40, 50)

def CheckMatchKO(g):
    """Obtained 50 or more points in one turn"""
    return CheckPointsPerTurn(g, 50, 60)

def CheckMatchBlitz(g):
    """Obtained 60 or more points in one turn"""
    return CheckPointsPerTurn(g, 60, 70)

def CheckMatchOnslaught(g):
    """Obtained 70 or more points in one turn"""
    return CheckPointsPerTurn(g, 70)

GroupFuncs([CheckMatchSlam, CheckMatchCrash, CheckMatchCharge, CheckMatchKO,
            CheckMatchBlitz, CheckMatchOnslaught], 'vp_turn')

def CheckMatchMegaTurn(g):
    """Bought all the Provinces or Colonies in a single turn."""
    ret = []
    if dominioncards.Colony in g.get_supply():
        biggest_victory = dominioncards.Colony
    else:
        biggest_victory = dominioncards.Province

    victory_copies = biggest_victory.num_copies_per_game(len(g.get_player_decks()))
    for turn in g.get_turns():
        new_cards = turn.buys + turn.gains
        if len(new_cards) < victory_copies:
            continue
        if new_cards.count(biggest_victory) == victory_copies:
            ret.append(
                achievement(turn.player.name(),
                 "Obtained all of the %s cards in one turn" %
                            biggest_victory, biggest_victory))
    return ret

def CheckMatchOscarTheGrouch(g):
    """Trash more than 7 cards in one turn"""
    ret = []
    for turn in g.get_turns():
        trashes = len(turn.trashes)
        if trashes >= 7:
            ret.append(achievement(turn.player.name(),
                                   "Trashed %d cards in one turn" % trashes,
                                   trashes))
    return ret

goal_check_funcs = {}

for global_name in dict(globals()):
    if global_name.startswith('CheckMatch'):
        outer_goal = global_name[len('CheckMatch'):]
        goal_func = globals()[global_name]
        goal_check_funcs[outer_goal] = goal_func
        if not hasattr(goal_func, 'group'):
            goal_func.group = 'ungrouped'
            goal_func.priority = 0

def GetGoalImageFilename(goal_name):
    return 'static/images/%s.png' % goal_name

def GetGoalDescription(goal_name):
    return goal_check_funcs[goal_name].__doc__

GOAL_BOX = """<table class="goal_box">
    <td>%(link)s<img src="%(img)s" title="%(goal_name)s" width="50px"></a>
    <td width="100px">%(link)s
                      <span class="goal_description">%(reason)s</span><br>
                      <span class="goal_date">%(date)s</span></a>
</table>
"""

GOAL_CHUNK = """<div onclick="javascript:toggle(\'%(goal_name)s\');" style="cursor:pointer; display: inline-block" class="cardborder2 blue" id="%(goal_name)s">
 <span style="display: inline-block; text-align: center">
  <img src="%(img)s" title="%(goal_name)s x%(freq)d" style="vertical-align: middle; display:block" id="%(goal_name)s_img">
  <span style="font-size: 14; font-weight: 700; display: block;" id="%(goal_name)s_caption">%(goal_name)s</span>
 </span>
 <span class="goal_name" id="%(goal_name)s_title" style="display: none">&nbsp; %(goal_name)s &nbsp; x%(freq)d</span>
 <div id="%(goal_name)s_list" class="goal_list"><br>
"""

def MaybeRenderGoals(db, norm_target_player):
    game_matches = list(db.goals.find({'goals.player': norm_target_player}))
    ret = ''

    if game_matches:
        ret += """<script language="javascript"> 
function toggle(item) {
	var list = document.getElementById(item + "_list");
	var img = document.getElementById(item + "_img");
	var title = document.getElementById(item + "_title");
	var caption = document.getElementById(item + "_caption");

	if(list.style.display == "block") {
        
    	list.style.display = "none";
        img.style.display = "block";
        caption.style.display = "inline";
        title.style.display = "none";
  	}
	else {
		list.style.display = "block";
        img.style.display = "inline";
        caption.style.display = "none";
        title.style.display = "inline";
	}
} 
</script>"""
        ret += '<h2>Goals achieved</h2>\n'

        goals_by_name = collections.defaultdict(list)
        goals_achieved = []
        for game_match in game_matches:
            game_id = game_match['_id']
            for goal in game_match['goals']:
                if goal['player'] != norm_target_player:
                    continue
                goal_name = goal['goal_name']
                goal['_id'] = game_id

                goals_by_name[goal_name].append(goal)
                if goal_name not in goals_achieved:
                    goals_achieved.append(goal_name)

        def GroupPriorityAndName(goal):
            if goal not in goal_check_funcs:
                return None
            func = goal_check_funcs[goal]
            return func.group, func.priority, func.__name__

        goals_achieved.sort(key = GroupPriorityAndName)

        ret += '<div style="width: 1000px">'
        for goal_name in goals_achieved:
            m = {'goal_name': goal_name}
            m['img'] = GetGoalImageFilename(goal_name)
            found_goals = goals_by_name[goal_name]
            m['freq'] = len(found_goals)
            ret += GOAL_CHUNK % m

            def KeyAndDate(goal):
                return goal.get('sort_key'), goal['_id']
            found_goals.sort(key = KeyAndDate)

            temp_ret = ''
            for match in found_goals:
                game_id = match['_id']

                m['reason'] = match.get('reason', '')
                m['link'] = game.Game.get_councilroom_link_from_id(game_id, ' class="goal"')
                m['date'] = game.Game.get_datetime_from_id(game_id).strftime("%d %b %Y")

                temp_ret += GOAL_BOX % m

            ret += temp_ret
            ret += '</div></div>'
        ret += '</div>'
        ret += '<div style="clear: both;">&nbsp;</div>'
    return ret

def print_totals(checker_output, total):
    for goal_name, count in sorted(checker_output.iteritems(),
                                    key=lambda t: t[1], reverse=True):
        log.info("Totals: %-15s %8d %5.2f", goal_name, count,
                 count / float(total))

def check_goals(game_val, goal_names=None):
    if goal_names is None:
        goal_names = goal_check_funcs.keys()

    goals = []
    for goal_name in goal_names:
        goal_checker = goal_check_funcs[goal_name]
        output = goal_checker(game_val)
        for goal in output:
            goal['goal_name'] = goal_name
            goals.append(goal)
    return goals


def calculate_goals(games, goals_col, goals_error_col, year_month_day, goals_to_check=None):
    """ Analyze games for goals and insert those found into the MongoDB.

    games: List of games to analyze, each in dict format
    goals_col: Destination MongoDB collection
    goals_error_col: MongoDB collection for goals analysis errors (for
        potential reflow later). This is a TODO for now.
    year_month_day: string in yyyymmdd format encoding date
    goals_to_check: List of goals to analyze for. If passed, only the
        listed goals will be calculated or re-calculated. Otherwise, all
        goals are calculated.

    """
    log.debug('Beginning to analyze %d games for goals, from %s', len(games), year_month_day)

    total_checked = 0
    checker_output = collections.defaultdict(int)

    for g in games:
        total_checked += 1
        game_val = game.Game(g)

        # Get existing goal set (if exists)
        game_id = game_val.get_id()
        mongo_val = goals_col.find_one({'_id': game_id})

        if mongo_val is None:
            mongo_val = collections.defaultdict( dict )
            mongo_val['_id'] = game_id
            mongo_val['goals'] = []

        # If rechecking, delete old values
        if goals_to_check is not None:
            goals = mongo_val['goals']
            for ind in range(len(goals) - 1, -1, -1):
                goal = goals[ind]
                if goal['goal_name'] in goals_to_check:
                    del goals[ind]

        # Get new values
        goals = check_goals(game_val, goals_to_check)

        # Write new values
        for goal in goals:
            goal_name = goal['goal_name']
            mongo_val['goals'].append(goal)
            checker_output[goal_name] += 1

        mongo_val = dict(mongo_val)
        goals_col.save(mongo_val)

    print_totals(checker_output, total_checked)
    return total_checked


def main(args):
    db = utils.get_mongo_database()
    games_collection = db.games
    output_collection = db.goals
    total_checked = 0

    checker_output = collections.defaultdict(int)

    if args.goals:
        valid_goals = True
        for goal_name in args.goals:
            if goal_name not in goal_check_funcs:
                valid_goals = False
                log.error("Unrecognized goal name '%s'", goal_name)
        if not valid_goals:
            exit(-1)
        goals_to_check = args.goals

        scanner = incremental_scanner.IncrementalScanner('subgoals', db)
        scanner.reset()
        main_scanner = incremental_scanner.IncrementalScanner('goals', db)
        last = main_scanner.get_max_game_id()
    else:
        goals_to_check = None
        scanner = incremental_scanner.IncrementalScanner('goals', db)
        last = None

    if not args.incremental:
        scanner.reset()
        output_collection.remove()
    output_collection.ensure_index('goals.player')

    log.info("Starting run: %s", scanner.status_msg())

    for g in utils.progress_meter(scanner.scan(games_collection, {})):
        total_checked += 1
        game_val = game.Game(g)

        # Get existing goal set (if exists)
        game_id = game_val.get_id()
        mongo_val = output_collection.find_one({'_id': game_id})

        if mongo_val is None:
            mongo_val = collections.defaultdict( dict )
            mongo_val['_id'] = game_id
            mongo_val['goals'] = []

        # If rechecking, delete old values
        if goals_to_check is not None:
            goals = mongo_val['goals']
            for ind in range(len(goals) - 1, -1, -1):
                goal = goals[ind]
                if goal['goal_name'] in goals_to_check:
                    del goals[ind]

        # Get new values
        goals = check_goals(game_val, goals_to_check)

        # Write new values
        for goal in goals:
            goal_name = goal['goal_name']
            mongo_val['goals'].append(goal)
            checker_output[goal_name] += 1

        mongo_val = dict(mongo_val)
        output_collection.save(mongo_val)

        if last and game_id == last:
            break
        if args.max_games >= 0 and total_checked >= args.max_games:
            break

    log.info("Ending run: %s", scanner.status_msg())
    scanner.save()
    print_totals(checker_output, total_checked)

if __name__ == '__main__':
    parser = utils.incremental_max_parser()
    parser.add_argument(
        '--goals', metavar='goal_name', nargs='+',
        help=('If set, check only the goals specified for all of ' +
              'the games that have already been scanned'))
    args = parser.parse_args()
    dominionstats.utils.log.initialize_logging(args.debug)
    main(args)
