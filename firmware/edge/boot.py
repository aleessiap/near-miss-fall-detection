# Runs at every start-up, before main.py. The pause leaves time to stop the
# firmware from Thonny (Stop button) before it takes over the board.
from time import sleep

print("Waiting 10s before starting...")
sleep(10)
