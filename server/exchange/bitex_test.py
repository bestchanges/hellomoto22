import logging

from bitex import Bitfinex

logging.basicConfig(level=logging.DEBUG)

k = Bitfinex()
resp = k.ticker("expbtc")
print(resp.formatted)
print(resp.json())
