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
import sys
import pygame


# PyGame defines
PI = 3.141592653
TABLE_COLOR     = [  8, 128,  18]

# Globals
CARD_IMAGES = {}
CARD_IMAGES_R = {}
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 1000
PLAYERS_PER_ROW = 8


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
            s.setblocking(False)
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
            # Get all lines, but only return the last one received.
            s = str(sock.recv(1000000), "utf-8").splitlines()
            return s[-1]
        except BlockingIOError:  # The recv() would have blocked, i.e. no data.
            return None
        except ValueError:  # Generally, timeout was 0 or negative.
            return None
        except:
            raise ConnectionError
            return ret


def send_to_server(sock: socket, s: str):
    if sock is None:
        print(s)
    else:
        try:
            sock.sendall(bytes(s + "\n", "utf-8"))
        except:
            raise ConnectionError


def load_card_images():
    ci = {}
    for suit in ("C", "D", "S", "H"):
        for value in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"):
            ci[value + suit] = pygame.image.load("cards/" + suit.lower() + value.lower() + ".png").convert_alpha()
    ci["back"] = pygame.image.load("cards/back.png").convert_alpha()
    for i in ci.keys():
        CARD_IMAGES_R[i] = pygame.transform.smoothscale(pygame.transform.rotate(ci[i], 90), (108, 75))
        CARD_IMAGES[i] = pygame.transform.smoothscale(ci[i], (75, 108))


def draw_arrow(screen:pygame.Surface, color, SX:int, SY:int, W:int, H:int, width:int):
    # print("draw_arrow at {0!s},{1!s} @ {2!s}x{3!s} x {4!s}".format(SX, SY, W, H, width))
    pygame.draw.polygon(screen, color, ((SX, SY+H/3), (SX+(3*W/5), SY+H/3), (SX+(3*W/5), SY), (SX+W, SY+H/2),
                                        (SX+(3*W/5), SY+H), (SX+(3*W/5), SY+(2*H/3)), (SX, SY+(2*H/3)), (SX, SY+H/3)),
                        width)


def draw_hand(screen:pygame.Surface, hand:str, startX:int, startY:int):
    # - Player hands end with "." if it's done, "a" if server is waiting for that client to respond,
    #   "t" if the client timed out, "p" if the client is pending, "+" if it's done and was a double down
    # print("Drawing hand " + hand + " at " + str(startX) + "," + str(startY))
    status = hand[-1:]
    for i in range(0, round(len(hand[:-1])/2)):
        value = hand[i*2]
        suit = hand[i*2+1]
        if value != "-":
            if value is "?":
                ci = "back"
            else:
                ci = value + suit

            # print("- Drawing card " + ci + " at " + str(startX + i * 25) + ", " + str(startY))
            if status == "+" and i == 2:
                screen.blit(CARD_IMAGES_R[ci], (startX, startY + 33))
            else:
                screen.blit(CARD_IMAGES[ci], (startX + i * 25, startY))

        if status == "a":
            draw_arrow(screen, (240, 0, 0), startX - 40, startY + 39, 30, 30, 0)
            draw_arrow(screen, (240, 240, 240), startX - 40, startY + 39, 30, 30, 2)


def draw_text_right(screen: pygame, text: str, color, rightX: int, startY: int):
    t = name_font.render(text, True, color)
    r = t.get_rect()
    r.right = rightX
    r.top = startY
    screen.blit(t, r)


screen_draws = 0
screen_draw_time_last_100 = None
screen_draw_count_last_100 = None
hands_played_ratio = 0.0

def draw_player(screen:pygame.Surface, hand_data:str, pSX, pSY):
    split_hands = hand_data[4].split("/")
    for j in range(0, len(split_hands)):
        hSY = pSY - 150 - (j * 120)
        draw_hand(screen, split_hands[j], pSX, hSY)
    screen.blit(name_font.render(hand_data[0], True, (0, 0, 0)), (pSX, pSY))
    screen.blit(name_font.render("R$" + "{:,}".format(int(hand_data[1])),
                                 True, (0, 0, 0)), (pSX, pSY + 20))
    player_stats = hand_data[2].split(',')

    stat_line = "W/L/P: {:,}/{:,}/{:,} ".format(int(player_stats[0]), int(player_stats[1]), int(player_stats[2]))
    if int(player_stats[1]) > 0:
        stat_line += " ({:.2f})".format(float(player_stats[0]) / float(player_stats[1]))
    screen.blit(stats_font.render(stat_line, True, (0, 0, 0)), (pSX, pSY - 34))
    total_hands_played = float(player_stats[0]) + float(player_stats[1]) + float(player_stats[2])
    if total_hands_played > 0:
        stat_line = "S: {:,} ({:.1f}%)  AvgR$:{:.2f}".format(int(player_stats[3]), \
                                                             float(player_stats[3]) / (total_hands_played + float(
                                                                 player_stats[3])) * 100.0, \
                                                             float(player_stats[4]) / total_hands_played)
        screen.blit(stats_font.render(stat_line, True, (0, 0, 0)), (pSX, pSY - 22))
    if int(player_stats[5]):
        stat_line = "C: {:,} ({:.1f} ms/xact)".format(int(player_stats[5]), \
                                                      float(player_stats[6]) / float(player_stats[5]) * 1000.0)
        screen.blit(stats_font.render(stat_line, True, (0, 0, 0)), (pSX, pSY - 10))

    if hand_data[3] is "a":
        draw_arrow(screen, (240, 0, 0), pSX - 40, pSY, 30, 30, 0)
        draw_arrow(screen, (240, 240, 240), pSX - 40, pSY, 30, 30, 2)


def draw_screen(screen:pygame.Surface, hand:str):
    global screen_draws, screen_draw_time_last_100, screen_draw_count_last_100, hands_played_ratio
    # Redraw screen
    screen.fill(TABLE_COLOR)
    if hand != "":
        # Draw the cards presented in the hand string, as per the standard:
        # - Like normal, except dealer's hand comes first, then players in name:money:hand format.
        # Dealer goes at top right.  Players start at bottom left and build right and up.
        hands = hand.split(" ")
        table_data = hands[0].split(",")

        # Recalculate our hands per minute if need be
        screen_draws += 1
        if screen_draws % 100 == 0:
            if screen_draw_time_last_100 is not None:
                hands_played_ratio = (float(table_data[0]) - screen_draw_count_last_100) / \
                                     (time.monotonic() - screen_draw_time_last_100) * 60.0
            screen_draw_time_last_100 = time.monotonic()
            screen_draw_count_last_100 = float(table_data[0])

        # Render table data (hands element 0, HandNumber:DecksInPlay:CardsInShoe)
        print(table_data)
        draw_text_right(screen, "Hand #{:,}, {:.2f} hands/min".format(int(table_data[0]), hands_played_ratio),
                        (0, 0, 0), WINDOW_WIDTH - 10, 10)
        draw_text_right(screen, table_data[1] + " decks, " + table_data[2] + " cards in shoe", (0, 0, 0), WINDOW_WIDTH - 10, 30)
        draw_text_right(screen, "House has won R${:,} (R${:.2f}/hand)  House Advantage: {:.1f}%".
                        format(int(table_data[3]),
                               float(table_data[3]) / float(table_data[0]),
                               float(table_data[3]) / float(table_data[4]) * 100.0),
                        (0, 0, 0), WINDOW_WIDTH - 10, 50)

        # Render dealer's hand
        draw_hand(screen, hands[1], 50, 10)

        # Render players' hands
        for i in range(2, len(hands)):
            playernum = i - 2
            pSX = (playernum % PLAYERS_PER_ROW) * 200 + 50
            pSY = WINDOW_HEIGHT - 40 - 200*(playernum // PLAYERS_PER_ROW)
            hand_data = hands[i].split(":")
            draw_player(screen, hand_data, pSX, pSY)

    # Push update to the screen
    pygame.display.update()
    pygame.event.get()


def RunMonitor(ip:str):
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Blackjack Monitor", "Blackjack Monitor")
    load_card_images()
    if ip != "test":
        draw_screen(screen, "")
        s = connect_to_server(ip)
        inp = sock_readline(s, 500.0)  # Ignore the HELLO.
        send_to_server(s, "MONITOR Andrews_Mon")
        inp = sock_readline(s, 500.0)
        previnp = ""
        while True:
            if inp is None:
                inp = ""
            if inp == previnp:
                print("MONITOR ignoring duplicate " + inp)
            else:
                print("MONITOR drawing " + inp)
                draw_screen(screen, inp)
            inp = sock_readline(s, 500.0)
    else:
        draw_screen(screen, "QS?? TestP2:318923:AC9HTD+/AHTD./ASTS./ADAHTC8H. P2:3829:6H4Sa P3:38291:QDQSp P4:12839:KCKSp")
        time.sleep(20)


if __name__ == "__main__":
    pygame.init()
    pygame.font.init()
    name_font = pygame.font.SysFont("Arial", 18)
    stats_font = pygame.font.SysFont("Arial", 12)
    print("Using backend "+pygame.display.get_driver())
    RunMonitor(sys.argv[1])