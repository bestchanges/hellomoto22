import ccxt

c = ccxt.cryptopia()

t = c.fetch_ticker("HUSH/BTC")
pass