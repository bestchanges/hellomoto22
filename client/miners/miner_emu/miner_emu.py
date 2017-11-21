import sys

import time
import argparse

parser = argparse.ArgumentParser(description='Emulate miner output')
parser.add_argument('--file',
                   help='file with stdout for log', required=True)
parser.add_argument('--delay', dest='delay',
                   type=float, default=1,
                   help='delay in seconds before next line. Use 0.1, etc for smaller values ')

args = parser.parse_args()

filename = args.file
delay = args.delay

file = open(filename)

while True:
    with open(filename) as file:
        for line in file:
            line = line.rstrip()
            print(line)
            time.sleep(delay)