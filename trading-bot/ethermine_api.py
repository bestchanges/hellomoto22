import json

import requests
import time

address = '0x9ba88a8bb6de98edb63a6066a7c7938cdc4793e7'
worker = 'digger1'



api_prefix = "https://api.ethermine.org"


# Get payments data
response = requests.get(api_prefix + '/miner/' + address + '/payouts')
data = json.loads(response.text)
payments = data['data']

current_payment = payments[0]
previous_payment = payments[1]

def ptime(epoch):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))

print(ptime(current_payment['paidOn']))
print(ptime(previous_payment['paidOn']))
timediff = current_payment['paidOn'] - previous_payment['paidOn']
print(previous_payment)
print(current_payment)
print(timediff / 60 / 60)

# Get historical data
response = requests.get(api_prefix + '/miner/' + address + '/history')
data = json.loads(response.text)
shares_history = data['data']
print(len(shares_history))

print(ptime(shares_history[0]['time']))
print(ptime(shares_history[1]['time']))
print(shares_history[1]['time'] - shares_history[0]['time'])

# for last N payments
def calculateSharesBetweenTimestamps(shares_history, from_, to):
    valid_shares = 0
    for entry in shares_history :
        entry_from = entry['time'] - 600
        entry_to = entry['time']
        entry_shares = entry['validShares']
        # print(entry)
        if entry_from < from_ < entry_to:
            print('in first')
            shares_before = int(round(entry_shares * ((from_ - entry_from) / (entry_to - entry_from))))
            shares_after = entry_shares - shares_before
            valid_shares += shares_after
        elif entry_from < to < entry_to:
            print('in last')
            shares_before = int(round(entry_shares * ((to - entry_from) / (entry_to - entry_from))))
            valid_shares += shares_before
        elif entry_from >= from_ and entry_to <= to:
            valid_shares += entry_shares
    return valid_shares

shares_between_payments = calculateSharesBetweenTimestamps(shares_history, previous_payment['paidOn'], current_payment['paidOn'])
print(shares_between_payments)
share_cost = current_payment['amount'] / shares_between_payments / 1e18
print("{:f}".format(share_cost))

# Get historical data for one worker

response = requests.get(api_prefix + '/miner/' + address + '/worker/' + worker + '/history')
data = json.loads(response.text)
worker_shares_history = data['data']
worker_shares_between_payments = calculateSharesBetweenTimestamps(worker_shares_history, previous_payment['paidOn'], current_payment['paidOn'])
print(worker_shares_between_payments, worker_shares_between_payments / shares_between_payments)

