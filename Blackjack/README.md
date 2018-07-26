# Blackjack
This directory contains resources that support the Blackjack Raspberry Pi Project.  The challenge is to Program a blackjack-playing client to compete against other teams and the house.  Example client code in Python will be provided, along with a page of specifications about the API used to talk to the server.  While Python is provided, the API is simple enough that any programming language is permitted.  The server and a monitoring program are already running to handle the House side and provide a visualization.

Files contained that were provided at the all PE meeting:

Communications Format.txt - The specification for the communications format between client and server.

starter-code.py - Very basic starter code, containing only socket, send, and receive functions.

basic-client.py - A very simplistic client, that plays a horrible game.


Files added at the end of the all PE meeting:

server.py - The server that was being run.

monitor.py - The graphical monitor program.

cards.zip - A ZIP archive of the card graphics - extract this to a "cards" directory for the monitor.py script to find.


All scripts are tested with Python 3 - Python 2 is not compatible.
