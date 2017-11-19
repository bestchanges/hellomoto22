import collections
import json
import operator

from poloniex import Poloniex
from urllib.request import Request, urlopen

def intersect(a,b):
    c = []
    for e in a:
        if e in b:
            c.append(e)
    return c

def in_first_not_in_second(a,b):
    c = []
    for e in a:
        if not e in b:
            c.append(e)
    return c

polo = Poloniex()

tickers = polo.returnTicker()

pos = 0
coins_in_poloniex = []
for pair, ticker in tickers.items():
    pos = pos + 1
    coins_in_pair = pair.split('_')
    coin = coins_in_pair[1]
    if len(coins_in_pair) == 2 and not coin in coins_in_poloniex:
        coins_in_poloniex.append(coin)
    print('%4d %10s %s' % (pos, pair, ticker))

coins_in_poloniex.sort()
print("There are %d coins in trade in Poloniex. They are " % len(coins_in_poloniex), coins_in_poloniex)

# volume = polo.return24hVolume()
# for pair,vol in volume.items():
#    print('%4d %10s %s' % (pos, pair, vol))


q = Request('http://whattomine.com/coins.json')
q.add_header('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5')
a = urlopen(q)
#a = open('coins.json')
#print(a.read())

coins_in_whattomine = []
whattomine = json.load(a)
#print(json.dumps(whattomine, indent=4))
for coinname,data in whattomine['coins'].items():
    coin = data['tag']
    if not coin in coins_in_whattomine:
        coins_in_whattomine.append(coin)
#    print(json.dumps(data, indent=4))

'''
        "DigitalNote": {
            "id": 104,
            "tag": "XDN",
            "algorithm": "CryptoNight",
            "block_time": "255.0",
            "block_reward": 150.0,
            "block_reward24": 150.0,
            "last_block": 444749,
            "difficulty": 472099127.0,
            "difficulty24": 500168701.16087,
            "nethash": 1851369,
            "exchange_rate": 3.013e-07,
            "exchange_rate24": 3.37478288100209e-07,
            "exchange_rate_vol": 408.50968884,
            "exchange_rate_curr": "BTC",
            "market_cap": "$13,321,185.24",
            "estimated_rewards": "60.0485",
            "estimated_rewards24": "56.6824",
            "btc_revenue": "0.00001809",
            "btc_revenue24": "0.00001708",
            "profitability": 3,
            "profitability24": 3,
            "lagging": false,
            "timestamp": 1509507746
        }
    }
'''

coins_in_whattomine.sort()
print("There are %d coins to mine on WhatToMine. They are: " % len(coins_in_whattomine), coins_in_whattomine)

# find intersection of two lists
coins_in_wtm_and_poloniex = intersect(coins_in_poloniex,coins_in_whattomine)
coins_in_wtm_and_poloniex.sort()
print("There are %d coins to mine and trade on Poloniex. They are: %s" % (len(coins_in_wtm_and_poloniex), coins_in_wtm_and_poloniex))

#### now with bittrex
from bittrex.bittrex import Bittrex

'''
{
    "MarketCurrency": "TIX",
    "BaseCurrency": "ETH",
    "MarketCurrencyLong": "Blocktix",
    "BaseCurrencyLong": "Ethereum",
    "MinTradeSize": 1e-08,
    "MarketName": "ETH-TIX",
    "IsActive": true,
    "Created": "2017-10-25T21:01:08.287",
    "Notice": null,
    "IsSponsored": null,
    "LogoUrl": "https://bittrexblobstorage.blob.core.windows.net/public/6f96c101-30a6-4d22-88c2-fe0e2ae9ae1f.png"
}

'''

my_bittrex = Bittrex(None, None)  # or defaulting to v1.1 as Bittrex(None, None)
bittrex = my_bittrex.get_markets()

coins_in_bittrex = []
for data in bittrex['result']:
#    print(json.dumps(data, indent=4))
    coin = data["MarketCurrency"]
    if not coin in coins_in_bittrex:
        coins_in_bittrex.append(coin)

coins_in_bittrex.sort()
print("There are %d coins to trade on Bittrex. They are: " % len(coins_in_bittrex), coins_in_bittrex)
# find intersection of two lists
coins_in_wtm_and_bittrex = intersect(coins_in_whattomine, coins_in_bittrex)
coins_in_wtm_and_bittrex.sort()
print("There are %d coins to mine and trade on Bittrex. They are: %s" % (len(coins_in_wtm_and_bittrex), coins_in_wtm_and_bittrex))
coins_not_in_bittrex = in_first_not_in_second(coins_in_whattomine, coins_in_bittrex)
print("Missed coins. They are: %s" % (coins_not_in_bittrex))


##########################################################################
#### NOW FIND BEST COIN

import choose_best_coin
user_hashrates = {
    'Ethash': 135.5e6,
    'Groestl': 123e6,
    'X11Gost': 43.2e6,
    'CryptoNight': 2580,
    'Equihash': 1620,
    'Lyra2REv2': 121800e3,
    'NeoScrypt': 3000e3,
    'LBRY': 1020e6,
    'Blake (2b)': 5940e6,
    'Blake (14r)': 9300e6,
    'Pascal': 500e3,
    'Skunkhash': 108e6,
    'Myriad-Groestl': 123e6,  # no data in calc
}
coin_income = {}
coins = {}
for coin_name, coin_data in whattomine['coins'].items():
    currency = coin_data["tag"]
    coins[currency] = coin_data
    if currency == 'NICEHASH':
        continue
    income_currency = choose_best_coin.calc_daily_income(coin_data, user_hashrates)
    exchange_rate = coin_data['exchange_rate']
    income_btc = income_currency * exchange_rate
    coin_income[currency] = income_btc
#    print("For %10s income %10.05f BTC/day (%f %s with rate %.6f)" % (
#        currency, income_btc, income_currency, currency, exchange_rate))
coins_rated = collections.OrderedDict(sorted(coin_income.items(), key=operator.itemgetter(1)))
for coin, income in coins_rated.items():
    in_poloniex = coin in coins_in_poloniex
    print("%10s %10.5f (%s) %s" % (coin, income, in_poloniex, coins[coin]['algorithm']))

del polo
