from deuces import Card, Evaluator

from websocket import create_connection
import math
import random
import json
import numpy as np
import sys, traceback

# OK;
def roundup(x, to):
    return int(math.floor(x / to)) * to

# OK; Input 'AH' -> Ouptut: 'Ah'
def convert_card_str(card_str):
    card_str_list = list(card_str)
    
    card_str_list[0] = card_str[0]
    if card_str[1] == 'H':
        card_str_list[1] = 'h'
    elif card_str[1] == 'D':
        card_str_list[1] = 'd'
    elif card_str[1] == 'S':
        card_str_list[1] = 's'
    elif card_str[1] == 'C':
        card_str_list[1] = 'c'
    else:
        print ("Invalid input: ", card_str)

    return "".join(card_str_list)

# OK; Output: ['2s', '3s', '4s', '5s', '6s' ... 'Tc', 'Jc', 'Qc', 'Kc', 'Ac' ]
def get_all_cardstr():
    tbl= []
    suit = ['s', 'h', 'd', 'c']
    rank = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    
    for s in suit:
        for r in rank:
            tbl.append("".join(r + s))
    return tbl

# OK; Output: [Card.new('2s'), ...]
def get_all_card():
    output = []
    tbl = get_all_cardstr()
    
    for c in tbl:
        output.append(Card.new(c))
        
    return output


# OK; Output: [ ['playerName' => v, 'chips' => ...], [...]]
def rebuild_player_table(players_json):
    tbl = []
    for p in players_json:
        this = [
                {'playerName': p['playerName'], 
                 'chips': p['chips'],
                 'action': [],
                 'alive': p['isSurvive']
                 }
                ]
        tbl.append(this)
    print (tbl)
    return tbl

# OK;
def get_hole_power(hole):  
    ha = Card.get_rank_int(hole[0])
    hb = Card.get_rank_int(hole[1])
    
    power = ha + hb

    if Card.get_suit_int(hole[0]) == Card.get_suit_int(hole[1]):
        power += 25
            
    if ha == hb:
        power += 50
        
    if ha >= 8:
        power += ha * 3
        
    if hb >= 8:
        power += hb * 3

    if power >= 100:
        power = 100

    return power

# OK;
def calc_mont_win_rate(holes, boards, max_sample):
    global my_evaluator
    i = 0
    
    mypow = my_evaluator.evaluate(boards, holes)
    
    alltbl = get_all_card()
    unused_tbl = []
    
    used = holes + boards

    unused_tbl = [x for x in alltbl if not x in used]
    
    win_cnt = 0
    while i < max_sample:
        i += 1
        ohole = random.sample(unused_tbl, 2)
        opow = my_evaluator.evaluate(boards, ohole)
        if (mypow < opow):
            win_cnt += 1
    
    return 100 * (win_cnt / float(max_sample))

# OK;
def get_bet_percent(my_call_bet, my_chips):
    if my_call_bet > my_chips:
        print (" * CAUTION: call bet is too large: ", my_call_bet, " > ", my_chips)
        my_call_bet = my_chips
    
    rate = my_call_bet / float(my_chips)
    rate = rate * 100

    if (rate > 100):
        rate = 100

    return rate
   
# OK;
def get_my_power(holes, boards, my_chips, my_call_bet, playernum):
    global my_evaluator
    
    # Calc strengh.
    strengh = my_evaluator.evaluate(boards, holes)
    
    # Normalize strengh to 0 ~ 100
    if strengh >= 6800:
        strengh = 6800

    strengh = (6800 - strengh) / float(6800)
    strengh = strengh * 100
    
    mypow = strengh
    
    # Guess win rate by random pickup
    win_rate = calc_mont_win_rate(holes, boards, 32768)
    print ("...pow / win-rate: ", mypow, win_rate, "user: ", playernum)
    
    if win_rate <= 40 and strengh > win_rate:
        mypow = win_rate
    else:
        mypow = (mypow + (win_rate)) / float(2)
        print ("...mypow avg: ", mypow)
    
    # Decrease power if chips is in danger
    rate = get_bet_percent(my_call_bet, my_chips)
    rate = 100 - rate
    
    if mypow < 75:
        mypow = mypow * (rate / 100)
    
    print ("...my final power is: ", mypow)
    return mypow
    
# OK;
def get_random_hit(hitrate):
    obj = random.SystemRandom()
    num = obj.randrange(0, 100, 1) 
    if num <= hitrate:
        return True
    else:
        return False
 
# OK;
def may_i_allin(my_power, my_raise_bet, my_chips):
    if my_chips < 1000 and my_power >= 75:
        return True

    if my_chips >= 3000:
        return False
    
    if my_power >= 85:
        return True
    
    return False
    
# OK;
def may_i_raise(my_power, my_raise_bet, my_chips):
    if my_raise_bet == 0:
        return False
    
    if my_power >= random.randrange(81, 85):
        return True
    
    if my_power <= 75:
        return False
    
    rate = get_bet_percent(my_raise_bet, my_chips)   
    return get_random_hit(100 - rate)
 
# OK;
def may_i_raise_at_river(my_power, my_raise_bet, my_chips):
    if my_raise_bet == 0:
        return False
    
    if my_power >= random.randrange(85, 90):
        return True
    
    if my_power <= 75:
        return False
    
    rate = get_bet_percent(my_raise_bet, my_chips)   
    return get_random_hit(100 - rate)


# OK; For preflop to decide to gamble or not.
def may_i_call_at_preflop(my_hole, my_chips, my_call_bet, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)
    
    if bet_percent < 5:
        print ("...Cheap preflop. Go Go Go.")
        return True
    
    if my_chips <= 640 and bet_percent <= 50:
        # Poor mode
        print ("...Poor-guy gambling mode: active")
        return True

    if my_spend == 0 and my_call_bet > 640 and my_chips > 1000:
        print ("...Anti-raise bot. Give up this round.")
        return False

    #
    # If I have a lot of chips, raise the gamble rate!
    #
    if my_spend > 0 and my_call_bet > (my_spend * 4):
        print ("...Sombody gamble at preflop. Defend?")
        if my_call_bet > my_chips / 5:
            print ("...Defend!")
            return False

    basic_rate = 100 - bet_percent
    
    # Evaulate my hole cards
    my_hole_power = get_hole_power(my_hole)
    
    if my_hole_power == 100 and my_chips <= 1000:
        # Attack! Attack! Kill you damn buster.
        print ("...Danger gambling mode: active")
        return True
    else:
        if bet_percent >= 25:
            return False
    
    gamble_rate = ((basic_rate * 4) + my_hole_power) / 5
    
    print("...Gamble rate: ", gamble_rate)
    return get_random_hit(gamble_rate)

# OK
def may_i_call_at_flop(my_power, my_call_bet, my_chips, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)
    
    if my_call_bet <= (my_chips / 30):
        return True
    
    if my_power <= 10:
        print ("...power is very low. Give up")
        return False
    elif my_power <= random.randrange(10, 25):
        if bet_percent < 5:
            return True
        else:
            print ("...power is low. Give up")
            return False
    elif my_power >= 80:
        # power is high
        return True
    else:
        if bet_percent >= 25:
            return False
    
    if bet_percent <= 5:
        return True
    else:
        return get_random_hit(105 - bet_percent)

# OK;
def may_i_call_at_turn(my_power, my_call_bet, my_chips, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)
       
    if my_power <= 15:
        print ("...power is very low. Give up")
        return False
    elif my_power <= random.randrange(15, 25):
        if bet_percent < 5:
            return True
        else:
            print ("...power is low. Give up")
            return False
    elif my_power >= 80:
        # power is high
        return True
    else:
        if bet_percent >= 25:
            return False
        
    if bet_percent < 5:
        return True
           
    #
    # Normal power...
    #
    if bet_percent <= 20:
        return True
    else:
        return get_random_hit(120 - bet_percent)

# OK;
def may_i_call_at_river(my_power, my_call_bet, my_chips, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)

    if my_power <= 30:
        print ("...power is very low. Give up")
        return False
    elif my_power <= random.randrange(30, 45):
        if bet_percent < 5:
            return True
        else:
            print ("...power is low. Give up")
            return False
    elif my_power >= random.randrange(80, 83):
        # power is high
        return True
    else:
        if bet_percent >= 25:
            return False

    if bet_percent <= 20:
        return True
    else:
        return get_random_hit(120 - bet_percent)

# OK;
def may_i_bet(my_power, my_call_bet, my_chips, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)
    
    if my_power < random.randrange(67, 75):
        return False
        
    if bet_percent < 20:
        print ("...Bet Bet Bet ... man")
        return True
    
    return False

# OK;
def may_i_bet_at_river(my_power, my_call_bet, my_chips, my_spend):
    bet_percent = get_bet_percent(my_call_bet, my_chips)
    
    if my_power < random.randrange(65, 75):
        return False
        
    if bet_percent < 10:
        print ("...Bet Bet Bet ... man")
        return True
    
    return False    

class PokerSocket(object):
    ws = ""
    board = []
    hole = []
    my_raise_bet = 0
    my_call_bet = 0
    number_players = 0
    my_chips = 0
    table_bet = 0
    my_name = None
    raise_count = 0
    my_step = 0
    total_bet = 0
    player_table = []
    
    my_chips_in_round = 0
    
    def __init__(self,my_name,connect_url, pokerbot):
        self.pokerbot = pokerbot
        self.my_name = my_name
        self.connect_url = connect_url

    def next_round_action(self):
        self.my_step = 0
        self.raise_count = 0
        self.total_bet = 0
        self.board = []
        self.hole = []

    def get_action(self, data):
        roundnum = data['game']['roundName']
        players = data['game']['players']
        chips = data['self']['chips']
        hands = data['self']['cards']

        self.raise_count = data['game']['raiseCount']
        self.my_step = data['game']['betCount']
        self.my_chips = chips
        self.my_name = data['self']['playerName']

        self.number_players = len(players)
        self.my_call_bet = data['self']['minBet']
        
        if self.my_call_bet == 0:
            self.my_raise_bet = 0
        else:
            self.my_raise_bet = roundup(chips / 3, self.my_call_bet)
        
        self.hole = []
        for card in (hands):
            card = convert_card_str(card)
            card = Card.new(card)
            self.hole.append(card)
        
        print ("...roundnum: ", format(roundnum))
        print ('...my_call_bet:', format(self.my_call_bet), "my_raise_bet", format(self.my_raise_bet), "my_chips", format(self.my_chips), "table bet", format(self.table_bet))
        
        Card.print_pretty_cards (self.hole)
        Card.print_pretty_cards (self.board)

        action, amount = self.pokerbot.declareAction(
                self.hole, self.board, roundnum, self.my_raise_bet, self.my_call_bet, self.table_bet, 
                self.number_players, self.raise_count, self.my_step, self.my_chips, self.total_bet)
        
        self.total_bet += amount
        
        if action == 'bet':
            self.raise_count += 1
            self.my_step += 1
        elif action == 'call':
            self.my_step += 1
        
        return action, amount

    def get_bet(self, data):
        roundnum = data['game']['roundName']
        players = data['game']['players']
        chips = data['self']['chips']
        hands = data['self']['cards']
        
        self.raise_count = data['game']['raiseCount']
        self.my_step = data['game']['betCount']
        self.my_chips = chips
        self.my_name = data['self']['playerName'] 

        self.number_players = len(players)
        self.my_call_bet = data['self']['minBet']
        self.my_raise_bet = self.my_call_bet * 2
        self.hole = []
        for card in (hands):
            card = convert_card_str(card)
            card = Card.new(card)
            self.hole.append(card)
        
        print ("...roundnum: ", format(roundnum), " -> force bet")
        print ('...my_call_bet:', format(self.my_call_bet), "my_raise_bet", format(self.my_raise_bet), "my_chips", format(self.my_chips), "table bet", format(self.table_bet))
        
        Card.print_pretty_cards (self.hole)
        Card.print_pretty_cards (self.board)
 
        if roundnum == 'Deal' and self.my_step == 0:
            print ("...Force to bet!")
            action = 'call'
            amount = self.my_call_bet
            self.my_step += 1
            self.total_bet += amount
            return action, amount
        else:
            return self.get_action(data)

    def handle_action(self, event_name, data):
        print ("...dispatch event: ", event_name)
        
        if event_name == '__new_round':
            self.player_table = rebuild_player_table(data['players'])
        
        if event_name == "__show_action" or event_name == '__deal' :
            table = data['table']
            players = data['players']
            boards = table['board']
            self.number_players = len(players)
            self.table_bet = table['totalBet']
            self.board = []
            for card in (boards):
                card = convert_card_str(card)
                card = Card.new(card)
                self.board.append(card)
                            
            if len(self.board) > 0:
                Card.print_pretty_cards(self.board)
            else:
                print ("...board empty (preflop)")
                
            print ('...table_bet: ', format(self.table_bet), "player num: ", self.number_players)
            
            if event_name == '__show_action':
                player_action = data['action']
                
                if (player_action['playerName'] == self.my_name):
                    print ("...player: me", ", action: ", player_action['action'], ", wealth: ", player_action['chips'])
                else:
                    print ("...player: ", player_action['playerName'], ", action: ", player_action['action'], ", wealth: ", player_action['chips'])
            
        elif event_name == "__bet":
            action, amount = self.get_bet(data)
            print ("...bet action: ", format(action), "amount: ", format(amount))
            
            output_msg = json.dumps({
                "eventName": "__action",
                "data": {
                    "action": action,
                    "playerName": self.my_name,
                    "amount": amount
                }})
            self.ws.send(output_msg)
        elif event_name == "__action":
            action, amount = self.get_action(data)
            print ("...action: ", format(action), "amount: ", format(amount))

            output_msg = json.dumps({
                "eventName": "__action",
                "data": {
                    "action": action,
                    "playerName": self.my_name,
                    "amount": amount
                }})
            self.ws.send(output_msg)
        elif event_name == "__game_over" or event_name == "__game_stop":
            print("...table end w/ my chips: ", self.my_chips, "my_name: ", self.my_name, format(data))
            sys.exit()
        elif event_name == "__start_reload":
            output_msg = json.dumps({"eventName": "__reload"})
            
            print ("...auto reload")
            self.ws.send(output_msg)
        elif event_name == "__round_end":           
            players = data['players']
            is_winner = False
            my_win_chips = 0
            for player in players:
                winMoney = player['winMoney']
                playerid = player['playerName']
                if (self.my_name == playerid):
                    if (winMoney == 0):
                        is_winner = False
                    else:
                        is_winner = True
                    my_win_chips = winMoney
                    
            print ("...winPlayer:", format(is_winner), "winChips:", format(my_win_chips))
            self.pokerbot.game_over(is_winner, my_win_chips, data)
            self.next_round_action()
        else:
            print ("...skip event: ", event_name)
            
        sys.stdout.flush()

    def doListen(self):
        try:
            self.ws = create_connection(self.connect_url)
            
            print("...Join game")
            self.ws.send(json.dumps({
                "eventName": "__join",
                "data": {
                    "playerName": self.my_name
                }
            }))
    
            print ("...start event loop")
            while 1:
                result = self.ws.recv()
                print ("")
                
                msg = json.loads(result)
                
                event_name = msg["eventName"]
                data = msg["data"]
#                print ("->", event_name, ":", json.dumps(data))
                self.handle_action(event_name, data)
        except Exception, e:
            print (" * EXCEPTION: ", e.message)
            traceback.print_exc(file=sys.stdout)
            sys.exit()
            

class PokerBot(object):
    def declareAction(self,hole, board, round, my_Raise_Bet, my_Call_Bet,Table_Bet,number_players,raise_count,my_step,my_Chips,total_bet):
        err_msg = self.__build_err_msg("declare_action")
        raise NotImplementedError(err_msg)
    def game_over(self,isWin,winChips,data):
        err_msg = self.__build_err_msg("game_over")
        raise NotImplementedError(err_msg)

class my_battle_poker_bot(PokerBot):   
    raise_count = 0
    my_step = 0
    spend_money = 0
    
    def __init__(self):
        pass

    def game_over(self, is_winner, my_win_chips, data):
        # Round end
        print ("...round over: ", is_winner, my_win_chips, "spend: ", self.spend_money, "counter: ", self.my_step, "/", self.raise_count)
        # Reset counters
        self.my_step = 0
        self.raise_count = 0
        self.spend_money = 0
    
    def do_preflop(self, holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet):      
        #
        # Don't bet too much at preflop. always: call or fold.
        #
        print ("...spend money: ", self.spend_money)
        
        if may_i_call_at_preflop(holes, my_chips, my_call_bet, self.spend_money):
            self.my_step += 1
            self.spend_money += my_call_bet
            return 'call', my_call_bet
        else:
            return 'fold', 0

    def do_flop(self, holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet):
        my_power = get_my_power(holes, boards, my_chips, my_call_bet, number_players)
        
        print ("...spend money: ", self.spend_money)
        
        if may_i_allin(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_chips
            return 'allin', 0
        elif may_i_raise(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_raise_bet
            return 'raise', my_raise_bet
        
        elif may_i_bet(my_power, my_call_bet, my_chips, self.spend_money):
            add_money = roundup(my_raise_bet / 10, 10)
            
            self.my_step += 1
            self.spend_money += my_call_bet + add_money
            
            return 'bet', my_call_bet + add_money
            
        elif may_i_call_at_flop(my_power, my_call_bet, my_chips, self.spend_money):
            self.my_step += 1
            self.spend_money += my_call_bet
            return 'call', my_call_bet
        else:
            return 'fold', 0

    def do_turn(self, holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet):
        my_power = get_my_power(holes, boards, my_chips, my_call_bet, number_players)
        
        print ("...spend money: ", self.spend_money)
        
        if may_i_allin(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_chips
            return 'allin', 0
        elif may_i_raise(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_raise_bet
            return 'raise', my_raise_bet
        elif may_i_bet(my_power, my_call_bet, my_chips, self.spend_money):
            add_money = roundup(my_raise_bet / 10, 10)
            
            self.my_step += 1
            self.spend_money += my_call_bet + add_money
            
            return 'bet', (my_call_bet + add_money)
            
        elif may_i_call_at_turn(my_power, my_call_bet, my_chips, self.spend_money):
            self.my_step += 1
            self.spend_money += my_call_bet
            return 'call', my_call_bet
        else:
            return 'fold', 0

    def do_river(self, holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet):
        my_power = get_my_power(holes, boards, my_chips, my_call_bet, number_players)
        
        print ("...spend money: ", self.spend_money)
        
        # Normalize power to avoid the strengh of board is too strong, so everybody has good rating.
        emptyhole = []
        boardpow = my_evaluator.evaluate(emptyhole, boards)
        # 6184 = 1-pair: 2s + 2h
        boardpow_thold = 6200
        if boardpow <= boardpow_thold and my_power < 82:
            print (" * CAUTION: ...board card itself is powerful: ", boardpow, "<=", boardpow_thold)
            tmp = my_power * ((boardpow_thold - boardpow) / float(boardpow_thold))
            my_power = ((my_power * 3) + tmp) / 4
            print ("...Adjust power to: ", my_power)
        
        if may_i_allin(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_chips
            return 'allin', 0
        elif may_i_raise_at_river(my_power, my_raise_bet, my_chips):
            self.raise_count += 1
            self.my_step += 1
            self.spend_money += my_raise_bet
            return 'raise', my_raise_bet
        elif may_i_bet_at_river(my_power, my_call_bet, my_chips, self.spend_money):
            add_money = roundup(my_raise_bet / 5, 10)
            
            self.my_step += 1
            self.spend_money += my_call_bet + add_money
            
            return 'bet', my_call_bet + add_money
        elif may_i_call_at_river(my_power, my_call_bet, my_chips, self.spend_money):
            self.my_step += 1
            self.spend_money += my_call_bet
            return 'call', my_call_bet
        else:
            return 'fold', 0

    def declareAction(self, holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet):       
        # preflop -> Flop -> Turn -> River
        if roundnum == 'Deal':
            return self.do_preflop(holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet)
        elif roundnum == 'Flop':
            return self.do_flop(holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet)
        elif roundnum == 'Turn':
            return self.do_turn(holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet)
        elif roundnum == 'River':
            return self.do_river(holes, boards, roundnum, my_raise_bet, my_call_bet, table_bet, number_players, raise_count, my_step, my_chips, total_bet) 
        else:
            print ("BUG: Do not expect ", roundnum)
            sys.exit()
            
if __name__ == '__main__':
        if len(sys.argv) == 3: 
            name = sys.argv[1] 
        else: 
            print (sys.argv[0], " <name> <url>") 
            sys.exit() 
     
        if len(sys.argv) == 3: 
            connect_url = sys.argv[2] 
        else: 
            print (format(sys.argv[0]), " <name> <url>") 
            sys.exit()

        print ("...Start game with name: ", name, "url: ", connect_url)

        my_name=name
        print ("...name: {}".format(my_name), "url: {}".format(connect_url))

        my_evaluator = Evaluator()
        myPokerBot = my_battle_poker_bot()

        myPokerSocket = PokerSocket(my_name, connect_url, myPokerBot)
        myPokerSocket.doListen()

#;
