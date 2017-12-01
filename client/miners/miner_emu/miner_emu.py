import sys

import time
import argparse


# run with --file ETHDCR.txt --dst_file log_noappend.txt
parser = argparse.ArgumentParser(description='Emulate miner output')
parser.add_argument('--file',
                   help='file with saved stdout', required=True)
parser.add_argument('--dst_file',
                   help='where stdout will be written', required=False)
parser.add_argument('--delay', dest='delay',
                   type=float, default=1,
                   help='delay in seconds before next line. Use fractional like 0.1 for smaller than second values ')

args = parser.parse_args()

filename = args.file
delay = args.delay

if args.dst_file:
    dst_file = open(args.dst_file, "w", buffering=1)

while True:
    with open(filename) as file:
        for line in file:
            if args.dst_file:
                dst_file.write(line)
            else:
                print(line.strip())
            time.sleep(delay)