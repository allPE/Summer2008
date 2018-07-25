#!/usr/bin/python3
import time
import re
from random import shuffle
import selectors
import socket
from select import select
from hashlib import md5
from pprint import pprint
from multiprocessing.dummy import Pool as ThreadPool

# Some global variables
COMMAND_TIMEOUT  = 1.0      # How long to give clients to respond
SHOE_MIN_PERCENT = 20       # How low to let the shoe get in percentage before forcing a reshuffle.
GAME_WAIT_TIME   = 0.01     # How long to pause between games
START_CURRENCY   = 10000    # How much currency to start new clients with
MINIMUM_DECKS    = 6        # The fewest number of decks to have on the table.  We will have more than this if the number
                            # of players requires it.
SHOW_COMMS       = 0        # Set to 1 to have server dump out on its console all client communications

cmd_regex = re.compile("([\w]+)( (.*))?")
card_values = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 10, "Q": 10, "K": 10,
               "A": 1, "+": 0, ".": 0}  # Special symbols we use to track hand status.

house_currency = 0          # Track how much the house has won or lost.
house_total = 0             # Total amount of bets made
saved_tokens = {}           # Tokens from clients that have logged out, disappeared, or were there when we saved.
                            # Values are the player classes themselves.  Pickled to disk as needed.


def global_set(param: str, val: str):
    global COMMAND_TIMEOUT, SHOE_MIN_PERCENT, GAME_WAIT_TIME, START_CURRENCY, MINIMUM_DECKS, SHOW_COMMS
    """Called on authenticated remote call to change global variables."""
    if param == "TIMEOUT":
        COMMAND_TIMEOUT = float(val)
    elif param == "SHOE":
        SHOE_MIN_PERCENT = int(val)
    elif param == "WAIT":
        GAME_WAIT_TIME = float(val)
    elif param == "START":
        START_CURRENCY = int(val)
    elif param == "DECKS":
        MINIMUM_DECKS = int(val)
    elif param == "COMMS":
        SHOW_COMMS = int(val)


def save_state(objtype: str, objid: str, objdata: object):
    """Ensure this state information is saved on disk.  Old data of a matching objtype and objid will be overwritten
    with the data, or a new entry created if that pair doesn't already exist.

    :param objtype: A simple table identifier.
    :param objid: A key for the table.
    :param objdata: The object to encode - must be convertable."""
    pass


def sock_readline(sock: socket, timeout_left: float):
    """Read a line from a socket, respecting timeout_left.  Returns a string on success, or None on timeout."""
    if sock is None:
        try:
            return input("C:")
        except EOFError:
            return None  # This way we can test timeouts by sending ^D.
    else:
        try:
            select([sock], [], [], timeout_left)
            c = ""
            ret = ""
            while c != "\n":
                ret += c
                c = str(sock.recv(1), "utf-8")
                if len(c) == 0:  # Nothing left in the buffer, but we didn't get a newline.
                    return None
            return ret
        except BlockingIOError:  # The recv() would have blocked, i.e. no data.
            return None
        except ValueError:  # Generally, timeout was 0 or negative.
            return None
        except:
            raise ConnectionError


def hand_value(hand: str) -> int:
    """Return the numerical value for the hand.  In case of Aces, a value of 11 is assumed unless that results in going
    over 21, otherwise 1."""
    ret = 0
    num_aces = 0
    for i in range(0, len(hand) // 2):
        if hand[i * 2] == "A":
            num_aces += 1
        ret += card_values[hand[i * 2]]

    # Since card_values["A"] is 1, we have already added in the minimum values for all our aces.  Add 10 (11-1) per ace
    # until we go over.
    for i in range(0, num_aces):
        if ret + 10 <= 21:
            ret += 10
    return ret


class Table:
    """Class tracking status of a table, handling cards, etc."""
    decks = 6
    hands_dealt = 0
    shoe = []
    players = {}
    monitors = {}
    dealer_holding = ""
    dealer_flipped = False

    def shuffle(self):
        """Re-shuffle the number of decks listed, re-setting cards_left and shoe.  To increase shoe size, change the
        class decks variable and call this function."""
        self.shoe = []
        for d in range(0, self.decks):
            for r in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]:
                for s in ["C", "H", "D", "S"]:
                    self.shoe.append(r + s)
        shuffle(self.shoe)

    def shuffle_if_needed(self):
        """Shuffle the deck only if needed. 'if needed' occurs if we fall below SHOE_MIN_PERCENT cards left in the shoe,
        or if we have insufficient cards left for all players to have 11 cards left."""
        cards_left = len(self.shoe)
        ideal_decks = max(MINIMUM_DECKS, round(len(self.players) / 8))

        if cards_left < (self.decks * 52 * SHOE_MIN_PERCENT / 100) or cards_left < len(self.players) * 11:
            # print(" ... shuffling")
            self.decks = ideal_decks
            self.shuffle()
            return

    def deal(self):
        """Re-init all card states and deal them, and plays a round."""
        self.shuffle_if_needed()

        self.dealer_holding = "????"
        pool.map(helper_ready, self.players)   # Send all players the READY and get their BETs.

        # Deal the cards.
        for p in self.players:
            if self.players[p].playing:
                self.players[p].holding = [self.get_card() + self.get_card()]
        self.dealer_flipped = False
        self.dealer_holding = self.get_card() + self.get_card()
        self.hands_dealt += 1

        # If dealer is showing an Ace, offer insurance to our players.
        if self.dealer_holding[0] == "A":
            pool.map(helper_insurance, self.players)
            # Peek at our card.  If we have blackjack, game over.
            if hand_value(self.dealer_holding) == 21:
                self.dealer_flipped = True
                for p in self.players:
                    if self.players[p].playing:
                        self.players[p].holding[0] += "."
                    self.players[p].Done(self)
                return
                self.update_monitors()

        k = list(self.players.keys())
        # Run the players in a random order
        # shuffle(k)
        # for p in k:
        #     # Cycle through the player's hands, looking for a hand left needing to be acted on.
        #     # Keeping in mind an ACT may change the number of hands!
        #     if self.players[p].playing:
        #         h = self.players[p].hand_left_to_play()
        #         while h is not None and self.players[p].playing:   # We need the and here in case the client disconnects
        #                                                            # in the middle of the hand.
        #             # Move this hand to the top.
        #             self.players[p].make_active_hand(h)
        #             self.update_monitors()
        #             self.players[p].Act(self)
        #             h = self.players[p].hand_left_to_play()

        # Run the players.
        pool.map(helper_act, self.players)

        # Finish.
        self.play_dealer()
        for p in k:              # We do NOT filter by .playing here, as people who aren't playing can watch the table.
            self.players[p].Done(self)
        self.update_monitors()

        # Cleanup any players that disappeared
        players_to_delete = []
        for p in k:
            if self.players[p].disconnected is True:
                players_to_delete.append(p)
        for p in players_to_delete:
            del self.players[p]

        # Cleanup any monitors that disappeared
        monitors_to_delete = []
        for p in list(self.monitors.keys()):
            if self.monitors[p].disconnected is True:
                monitors_to_delete.append(p)
        for p in monitors_to_delete:
            del self.monitors[p]

    def get_card(self, player=None):
        """Pull a card out of the shoe and optionally add it to the first hand of the player."""
        if player is None:
            return self.shoe.pop()
        else:
            player.holding[0] += self.shoe.pop()

    def get_table_state(self, viewpoint: str) -> str:
        """Return a string consisting of the current table state, from a given player's viewpoint."""
        ret = self.players[viewpoint].holding_state() + " "
        if self.dealer_flipped:
            ret += self.dealer_holding
        else:
            ret += self.dealer_holding[0:2] + "--"
        for p in self.players:
            if p != viewpoint:
                ret += " " + self.players[p].holding_state()
        return ret

    def get_table_monitor(self):
        """Return a string formatted for a monitoring client."""
        ret = str(self.hands_dealt) + "," + str(self.decks) + "," + str(len(self.shoe)) + "," + str(house_currency) + \
            "," + str(house_total) + " "

        if self.dealer_flipped:
            ret += self.dealer_holding
        else:
            ret += self.dealer_holding[0:2] + "??"

        for p in self.players:
            ret += " " + self.players[p].holding_state(monitor=True)

        return ret

    def play_dealer(self):
        """Have the dealer play his hand out."""
        self.dealer_flipped = True
        while hand_value(self.dealer_holding) < 17:
            self.dealer_holding += self.get_card()
        self.dealer_holding += "."

    def update_monitors(self):
        """Update all our attached monitors."""
        mon = self.get_table_monitor()
        for p in self.monitors:
            if self.monitors[p].disconnected is False:
                try:
                    self.monitors[p].send_to_player(mon)
                except ConnectionError:
                    self.monitors[p].discon()


class Player:
    """A single player that has registered with the server."""
    global GAME_WAIT_TIME
    sock = None
    name = ""
    token = ""
    currency = 0
    srcip = ""
    srcpt = 0

    cur_bet = 0
    holding = []
    start_currency = 0
    total_bets = 0              # Track the total amount this client has bet in its lifetime
    count_wins = 0
    count_losses = 0
    count_pushes = 0
    count_sitout = 0
    insured = False             # This gets set if the client opted to buy the insurance.
    disconnected = False        # This gets set if the client disappeared during a hand, and needs to be removed.
    timedout = False            # This gets set if the client timed out at some part in the past hand.
    playing = False             # This gets set if the client made a bet, otherwise it is just watching the game
    active = False              # This gets set if we are waiting for the client to respond (used mainly for monitor)
    monitor = False             # This gets set if this client is in MONITOR mode.
    interactions_count = 0      # Number of times we've asked the client for something
    interactions_time = 0.0     # Sum total of time we've waited on the client

    def __init__(self, sock: socket, table, srcip: str, srcpt: int):
        self.sock = sock
        self.srcip = srcip
        self.srcpt = srcpt
        self.table = table

        # Ensure socket is set non-blocking, if we're using a socket.
        if self.sock is not None:
            self.sock.setblocking(0)
        # Ask player to LOGIN or REGISTER.
        v, n = self.get_from_player(COMMAND_TIMEOUT, "HELLO BlackjackServer v1.00",
                                    ["LOGIN", "REGISTER", "MONITOR", "SET"], "")
        if v == "":
            # Disconnect the player and go on.
            raise ConnectionError
        else:
            if v == "REGISTER":
                if n == "Playername":
                    self.send_to_player("INVALID Please use a real name, not the example name.")
                    raise ConnectionError
                # Placeholder
                self.name = n.replace(" ", "_")
                # Calculate token
                m = md5()
                m.update(b"SaltServer")
                m.update(bytes(n, "utf-8"))
                m.update(bytes(str(time.monotonic()), "utf-8"))
                self.token = m.hexdigest()
                self.currency = START_CURRENCY
                self.send_to_player("TOKEN " + self.token)
            elif v == "MONITOR":
                # Add ourselves to the list of monitoring clients.
                self.monitor = True
                if n is None:
                    n = "Generic " + str(time.monotonic())
                self.name = "Monitor " + n
            elif v == "SET":
                set_params = n.split(" ")
                if set_params[0] == "spork":        # Password.
                    global_set(set_params[1], set_params[2])
                else:
                    self.send_to_player("BYE Invalid client.")
                    print("Client from " + self.srcip + " attempted an admin command with an invalid password.")
                raise ConnectionError

    def __del__(self):
        """Make sure we save our state."""
        save_state("Player", self.token, {"name": self.name, "token": self.token, "cur": self.currency})

    def get_from_player(self, timeout_left: float, request: str, valid_verbs: list, timeout_verb: str,
                        invalid_verbs: dict = {}) -> (str, str):
        """Sends a server string to the client and waits for timeout_left to get a response.  Returns a list of the
        client verb and client data.  The client must respond with one of the verbs in valid_verbs, or INVALID is
        returned and the prompt re-issued.  If the client times out, timeout_verb is returned as the verb, and empty
        string for the noun.  If the dictionary invalid_verbs is provided, a client passing a verb that's a key will receive
        an INVALID along with the error message specified as the value in the dictionary."""
        self.timedout = False
        self.active = True
        self.table.update_monitors()
        self.send_to_player(request)
        self.interactions_count += 1
        start_time = time.monotonic()
        timeout_at = start_time + timeout_left
        while True:
            timeout_left = timeout_at - time.monotonic()
            if SHOW_COMMS == 1:
                print("RECV waiting for " + self.name + " for " + str(timeout_left) + " seconds.")
            ret = sock_readline(self.sock, timeout_left)
            if ret is None or time.monotonic() > timeout_at:
                if SHOW_COMMS == 1:
                    print("RECV:" + self.name + ":Timed out")
                self.send_to_player("TIMEOUT")
                self.active = False
                self.timedout = True
                self.interactions_time += time.monotonic() - start_time
                return (timeout_verb, "")
            if SHOW_COMMS == 1:
                print("RECV:" + self.name + ":" + ret)
            m = cmd_regex.match(ret)
            if m:
                verb = m.group(1).upper()
                if verb in valid_verbs:
                    self.active = False
                    self.interactions_time += time.monotonic() - start_time
                    return (verb, m.group(3))
                else:
                    if verb in invalid_verbs:
                        self.send_to_player("INVALID " + invalid_verbs[verb])
                    else:
                        self.send_to_player("INVALID Bad command '" + verb + "' - valid commands: " + " ".join(valid_verbs))
            else:
                self.send_to_player("INVALID Bad command format")

    def send_to_player(self, s: str):
        if self.sock is None:
            print(s)
        else:
            try:
                if SHOW_COMMS == 1:
                    print("SEND:" + self.name + ":" + s)
                self.sock.sendall(bytes(s + "\n", "utf-8"))
            except:
                raise ConnectionError

    def holding_state(self, monitor=False):
        """Return a string for our current holding state.  Set monitor to 'True' for the monitoring mode view."""
        if monitor is False:
            ret = ""
        else:
            # Provide the Monitor the player statistics.
            ret = self.name + ":" + str(self.currency) + ":" + str(self.count_wins) + "," + \
                str(self.count_losses) + "," + str(self.count_pushes) + "," + str(self.count_sitout) + "," + \
                str(self.total_bets) + "," + str(self.interactions_count) + "," + str(self.interactions_time) + ":"
            if self.timedout is True:
                ret += "t:"
            elif self.active is True:
                ret += "a:"
            else:
                ret += "p:"

        if self.playing:
            return ret + '/'.join(self.holding)
        else:
            return ret + "----"

    def hand_left_to_play(self):
        """Returns an index of a hand that needs to be ACTed, or None if none are left."""
        for idx in range(0, len(self.holding)):
            h = self.holding[idx]
            if h[-1] != "." and h[-1] != "+":
                return idx
        return None

    def make_active_hand(self, idx: int):
        h = self.holding.pop(idx)
        self.holding.insert(0, h)

    def discon(self):
        """Called when we detect a socket error and our client has disappeared."""
        self.playing = False
        self.disconnected = True
        self.sock.close()

    def Ready(self, table: Table):
        """Perform READY step.  Initializes our state as well."""
        global house_currency, house_total
        self.insured = False
        self.cur_bet = 0
        self.playing = False
        self.holding = []
        timeout_at = time.monotonic() + COMMAND_TIMEOUT
        while True:
            if time.monotonic() > timeout_at:
                self.send_to_player("TIMEOUT")
                self.start_currency = self.currency
                self.playing = False
                return
            try:
                s = self.get_from_player(timeout_at - time.monotonic(),
                                        "READY {0!s} {1!s} {2!s}".format(self.currency, table.decks, len(table.shoe)),
                                        ["BET"], "BET")
            except ConnectionError:
                self.discon()
                return
            else:
                if s[1] == "":
                    # Assume no bet, i.e. bet_amt is 0.
                    self.start_currency = self.currency
                    self.playing = False
                    self.count_sitout += 1
                    return

                try:
                    bet_amt = int(s[1])
                    if bet_amt < 0 or (bet_amt / 2 != bet_amt // 2):
                        self.send_to_player("INVALID BET must be a positive even integer")
                    else:
                        if bet_amt > self.currency:
                            self.send_to_player("INVALID You do not have that much currency.")
                        else:
                            self.start_currency = self.currency  # So we can show win/loss at end of hand.
                            if bet_amt == 0:
                                self.playing = False
                                self.count_sitout += 1
                            else:
                                self.cur_bet = bet_amt
                                self.currency -= bet_amt
                                self.total_bets += bet_amt
                                house_currency += bet_amt
                                house_total += bet_amt
                                self.playing = True
                            return
                except ValueError:
                    self.send_to_player("INVALID BET must be a positive integer.")

    def Insurance(self, table: Table):
        """Perform INSURANCE step.  Updates the insured flag appropriately."""
        global house_currency, house_total
        insur_amt = self.cur_bet // 2
        if self.currency > insur_amt:
            try:
                s = self.get_from_player(COMMAND_TIMEOUT,
                                        "INSURANCE " + table.get_table_state(self.token),
                                        ["YES", "NO"], "NO")
            except ConnectionError:
                self.discon()
                return
            else:
                if s[0] == "YES":
                    self.insured = True
                    self.currency -= insur_amt
                    house_currency += insur_amt
                    house_total += insur_amt
        table.update_monitors()

    def Act(self, table: Table):
        """Perform a round of ACTs on a hand.  Note the number of hands held may change as a side effect of this
        function (due to SPLITs)."""
        global house_currency, house_total
        timeout_at = time.monotonic() + COMMAND_TIMEOUT
        while True:
            # Determine what's valid for the player to do.
            if hand_value(self.holding[0]) >= 21:  # No more actions allowed if player already showing 21 or more.
                self.holding[0] += "."
                return

            valid_verbs = ["HIT", "STAND"]
            invalid_verbs = {}

            # Check for double down status
            if len(self.holding[0]) == 4:
                if 9 <= hand_value(self.holding[0]) <= 11:
                    if self.currency >= self.cur_bet:
                        valid_verbs.append("DOUBLE")
                    else:
                        invalid_verbs["DOUBLE"] = "You do not have sufficient currency to double down - " \
                                                  + str(self.cur_bet) + " needed, you hold " + str(self.currency) + "."
                else:
                    invalid_verbs["DOUBLE"] = "Double down only permitted on card values between 9 and 11 - " \
                                              + "you are holding " + str(hand_value(self.holding[0])) + "."
            else:
                invalid_verbs["DOUBLE"] = "Double down only permitted on the first two cards dealt."

            # Check for split status
            if len(self.holding[0]) == 4:
                if card_values[self.holding[0][0]] == card_values[self.holding[0][2]]:
                    if self.currency >= self.cur_bet:
                        if len(self.holding) <= 4:
                            valid_verbs.append("SPLIT")
                        else:
                            invalid_verbs["SPLIT"] = "You are already holding four hands at once, the table limit."
                    else:
                        invalid_verbs["SPLIT"] = "You do not have sufficient currency to split - " + str(self.cur_bet) \
                                                 + " needed, you hold " + str(self.currency) + "."
                else:
                    invalid_verbs["SPLIT"] = "You can only split hands whose two cards are the same value."
            else:
                invalid_verbs["SPLIT"] = "You can only split on the first two cards dealt."

            try:
                s = self.get_from_player(timeout_at - time.monotonic(),
                                        "ACT " + table.get_table_state(self.token),
                                        valid_verbs, "STAND", invalid_verbs)
            except ConnectionError:
                self.discon()
                return
            else:
                if s[0] == "HIT":
                    table.get_card(self)

                if s[0] == "STAND":
                    self.holding[0] += "."
                    return

                if s[0] == "DOUBLE":
                    table.get_card(self)
                    self.holding[0] += "+"  # Add our "doubled down" marker.
                    self.currency -= self.cur_bet
                    house_currency += self.cur_bet
                    house_total += self.cur_bet
                    return

                if s[0] == "SPLIT":
                    # Get two cards from the shoe, then do the split, cards 1 & 3 with 2 & 4.
                    table.get_card(self)
                    table.get_card(self)
                    curhand = self.holding.pop(0)
                    self.holding.insert(0, curhand[2:4] + curhand[6:8])
                    self.holding.insert(0, curhand[0:2] + curhand[4:6])
                    self.currency -= self.cur_bet
                    self.total_bets += self.cur_bet
                    house_currency += self.cur_bet
                    house_total += self.cur_bet

                table.update_monitors()

    def Done(self, table: Table):
        """Perform DONE step.  Evaluates win/loss, and updates currency."""
        global house_currency
        dealer_value = hand_value(table.dealer_holding)

        for h in self.holding:
            hand_won = False
            hand_push = False
            hv = hand_value(h)
            # print("DV:" + str(dealer_value) + "  HV:" + str(hv) + "  HF:" + h[-1] + "   len(h):" + str(
            #     len(h)) + "  len(self.holding):" + str(len(self.holding)))
            if hv > 21:  # Did player bust?
                pass
            else:
                if dealer_value == 21 and len(table.dealer_holding) == 5 and self.insured is True:
                    self.currency += self.cur_bet  # Payout the insurance (which was half the bet) at 2:1.
                    house_currency -= self.cur_bet
                    hand_won = True
                if dealer_value == hv:  # Push?
                    self.currency += self.cur_bet  # Give the player their money back.  This may combine with the
                    house_currency -= self.cur_bet # insurance bet, thus the logic here.
                    hand_push = True
                elif dealer_value > 21 or hv > dealer_value:  # Did dealer bust, or did we beat the dealer?
                    self.currency += self.cur_bet  # They at least get their own bet back...
                    house_currency -= self.cur_bet
                    hand_won = True
                    if h[-1] == "+":  # If it was a double down, we award the bet again plus double the bet
                        self.currency += self.cur_bet * 3
                        house_currency -= self.cur_bet * 3
                    else:
                        # Hard 21 (aka blackjack)?  If so, pays 3:2, rounded up.
                        if hv == 21 and len(h) == 5 and len(self.holding) == 1:
                            self.currency += round(self.cur_bet * 1.5)
                            house_currency -= round(self.cur_bet * 1.5)
                        else:
                            self.currency += self.cur_bet
                            house_currency -= self.cur_bet
            if hand_won:
                self.count_wins += 1
            elif hand_push:
                self.count_pushes += 1
            else:
                self.count_losses += 1
        try:
            self.send_to_player("DONE " + table.get_table_state(self.token) + ":" +
                                str(self.currency - self.start_currency))
        except ConnectionError:
            self.discon()
            return


# Helper functions to allow us to query all the players at once for things that don't depend on the order of plays.
def helper_ready(k):
    gametable.players[k].Ready(gametable)


def helper_insurance(k):
    if gametable.players[k].playing is True:
        gametable.players[k].Insurance(gametable)

def helper_act(p):
    if gametable.players[p].playing:
        h = gametable.players[p].hand_left_to_play()
        while h is not None and gametable.players[p].playing:   # We need the and here in case the client disconnects
                                                                # in the middle of the hand.
            # Move this hand to the top.
            gametable.players[p].make_active_hand(h)
            gametable.players[p].Act(gametable)
            h = gametable.players[p].hand_left_to_play()

# k = list(self.players.keys())
# shuffle(k)
# for p in k:
#     # Cycle through the player's hands, looking for a hand left needing to be acted on.
#     # Keeping in mind an ACT may change the number of hands!
#     if self.players[p].playing:
#         h = self.players[p].hand_left_to_play()
#         while h is not None and self.players[p].playing:   # We need the and here in case the client disconnects
#                                                            # in the middle of the hand.
#             # Move this hand to the top.
#             self.players[p].make_active_hand(h)
#             self.update_monitors()
#             self.players[p].Act(self)
#             h = self.players[p].hand_left_to_play()

def AcceptClient(sock, mask):
    (clientsocket, address) = sock.accept()
    clientsocket.setblocking(False)
    print("Answering a client from source IP " + address[0] + ", source port " + str(address[1]))
    try:
        p = Player(clientsocket, gametable, address[0], address[1])
        if p.monitor is True:
            gametable.monitors[p.token] = p
        else:
            gametable.players[p.token] = p
    except ConnectionError:
        clientsocket.close()


def RunServer():
    # Set up server socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # bind the socket to a public host, and a well-known port
    # while True:
    #    try:
    #        serversocket.bind(('', 9876))
    #    except OSError:
    #        print("Port is unavailable.  Sleeping a couple and trying again.")
    #        time.sleep(2)
    #        pass
    serversocket.bind(('', 9876))

    # become a server socket
    serversocket.listen(5)
    # set nonblocking
    serversocket.setblocking(False)
    sel.register(serversocket, selectors.EVENT_READ, AcceptClient)
    print("Now accepting connections at " + socket.gethostname() + ", port 9876.")

    # Now iterate.  Listen to server socket for things.  Process other things.
    while True:
        if SHOW_COMMS == 1:
            print("Tick")
        events = sel.select(GAME_WAIT_TIME)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

        # If we have ready players, run a hand.
        if len(gametable.players) > 0:
            gametable.deal()
    exit(0)

    try:
        while True:
            if SHOW_COMMS == 1:
                print("Tick")
            events = sel.select(GAME_WAIT_TIME)
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)

            # If we have ready players, run a hand.
            if len(gametable.players) > 0:
                gametable.deal()

    except KeyboardInterrupt:
        for p in gametable.players:
            try:
                gametable.players[p].send_to_player("BYE Server is shutting down.")
            except:
                pass
        for p in gametable.monitors:
            try:
                gametable.monitors[p].send_to_player("BYE Server is shutting down.")
            except:
                pass
        serversocket.close()


# Set up our table.
gametable = Table()
# Prep selector.
sel = selectors.DefaultSelector()
# Multithreading pool
pool = ThreadPool(8)

if __name__ == "__main__":
    RunServer()
