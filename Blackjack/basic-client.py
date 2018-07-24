#!/usr/bin/python3
import re
import socket
from select import select
import sys

cmd_regex = re.compile("([\w]+)( (.*))?")
card_values = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 10, "Q": 10, "K": 10,
               "A": 1, "+": 0, ".": 0}  # Special symbols we use to track hand status.


def connect_to_server(ip: str) -> socket:
    # Straight from https://docs.python.org/3/library/socket.html
    s = None
    for res in socket.getaddrinfo(ip, 9876, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except OSError as msg:
            s = None
            continue
        try:
            s.connect(sa)
        except OSError as msg:
            s.close()
            s = None
            continue
        break
    if s is None:
        raise ConnectionError("Could not connect to server at " + ip)
    return s


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
            return str(sock.recv(2048), "utf-8").strip()
        except BlockingIOError:  # The recv() would have blocked, i.e. no data.
            return None
        except ValueError:  # Generally, timeout was 0 or negative.
            return None
        except:
            raise ConnectionError


def send_to_server(sock: socket, s: str):
    if sock is None:
        print(s)
    else:
        try:
            sock.sendall(bytes(s + "\n", "utf-8"))
        except:
            raise ConnectionError


def get_from_server(sock: socket) -> (str, str):
    """Get a verb from the server and return it, along with any data the server provided along with as the second
    return.

    Returns: List of (verb, nouns)"""
    while True:
        ret = sock_readline(sock, 300.0)
        if ret is None:
            raise ConnectionError("No communication from server in 300 seconds.")
        m = cmd_regex.match(ret)
        if m:
            if m.group(2) is None:
                return (m.group(1).upper().strip(), "")
            return (m.group(1).upper().strip(), m.group(2).upper().strip())
        raise ValueError("Did not understand message from server: " + ret)


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


def RunClient(ip: str, my_name: str, token = None):
    # Connect to server.
    sock = connect_to_server(ip)

    # Simple state machine.  This is a very basic client.
    (verb, noun) = get_from_server(sock)
    while verb:
        if verb == "HELLO":
            if token is None:
                send_to_server(sock, "REGISTER " + my_name)
            else:
                send_to_server(sock, "LOGIN " + token)
        elif verb == "TOKEN":
            token = noun
            send_to_server(sock, "LOGIN " + token)
        elif verb == "OK":
            continue
        elif verb == "READY":
            nouns = noun.split(" ")
            my_money = int(nouns[0])
            if my_money >= 20:
                send_to_server(sock, "BET 20")
            elif my_money > 2:
                send_to_server(sock, "BET " + str((my_money // 2) * 2))  # Ensure we always bet even.
            else:
                print("I went broke!")
                exit(1)
        elif verb == "INSURANCE":
            send_to_server(sock, "NO")
        elif verb == "ACT":
            # Act based on current hand value.  We hit on less than 14, otherwise stand.
            table_hands = noun.split(" ")
            our_hand = table_hands[0]
            v = hand_value(our_hand)
            if v < 14:
                send_to_server(sock, "HIT")
            else:
                send_to_server(sock, "STAND")
        # Get next message from server.
        (verb, noun) = get_from_server(sock)


if __name__ == "__main__":
    RunClient(sys.argv[1], sys.argv[2])
