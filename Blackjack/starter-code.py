#!/usr/bin/python3
import re
import socket
from select import select

cmd_regex = re.compile("([\w]+)( (.*))?")

##
##
## You do not need to modify the next four functions (here through the end of hand_value).
##
##
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
            return (m.group(1).upper().strip(), m.group(2).upper().strip())
        raise ValueError("Did not understand message from server: " + ret)


def RunClient(ip: str, my_name: str, token = None):
    #
    #
    # Put your code here!  You should probably start with a connect_to_server and then do calls
    # to get_from_server and send_to_server as appropriate.
    #
    #
    pass


if __name__ == "__main__":
    RunClient(sys.argv[1])
