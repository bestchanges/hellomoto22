from poloniex import Poloniex

poloniex_configurations = {
    'egor.fedorov@gmail.com': {
        'APIKEY': 'YLNDY1WS-LRUDLWDP-YEBKYKO2-ZUQHJO07',
        'SECRET': 'bf95c7f41ee308b1b7b953a4595aff0f2ecf4e9235516942ae2ebe3c8f7a1bc97fa5fe0ee14e4ffbbec524637769d43f9955c4450430d28a1daefb6d61ff92e7',
    }
}

poloniex_account = 'egor.fedorov@gmail.com'
config = poloniex_configurations[poloniex_account]
polo = Poloniex(config['APIKEY'], config['SECRET'])


def coin_to_btc(coin):
    if coin == 'BTC':
        return
    balances = polo.returnBalances()
    print(balances[coin])
    pair = 'BTC_' + coin
    sum = balances[coin]
    ticker = polo.returnTicker()[pair]
    print(ticker)
    rate = ticker['highestBid']
    btc_sum = sum * rate
    # poloniex total must be at least 0.0001 BTC
    minumum_total_trade = 0.0001
    print("Converting %f %s to BTC %.8f with rate %.8f" % (sum, coin, btc_sum, rate))
    if btc_sum < minumum_total_trade:
        print("Amount is below minimum. Will not exchange")
        return
    sell = polo.sell(pair, rate, sum)
    print(sell)
    return sell


balances = polo.returnBalances()
for coin, balance in balances.items():
    if balance > 0:
        coin_to_btc(coin)

del polo
