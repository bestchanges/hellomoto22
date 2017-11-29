import json
from abc import ABC, abstractmethod

from bitex import Bitfinex
from bitex.api.REST import PoloniexREST
from poloniex import PoloniexPublic




class Exchange(ABC):
    def __init__(self, code):
        self.code = code

    @abstractmethod
    def trading_pairs(self):
        pass

    def trading_pair(self, pair):
        pass

    def supported_deposit(self):
        pass

    @abstractmethod
    def make_pair(self, currency1, currency2):
        pass

    def supported_withdraw(self):
        pass

    @abstractmethod
    def exchange_rate(self, good, money):
        pass

    def __unicode__(self):
        return self.code


class BitfinexExchange(Exchange):
    def __init__(self):
        self.e = Bitfinex()
        super().__init__("bitfinex")

    def trading_pairs(self):
        super().trading_pairs()

    def supported_withdraw(self):
        super().supported_withdraw()

    def make_pair(self, currency1, currency2):
        return currency1.lower() + currency2.lower()

    def supported_deposit(self):
        super().supported_deposit()

    def exchange_rate(self, good, money):
        pair = self.make_pair(good, money)
        resp = self.e.ticker(pair)
        # 'ethbtc'
        # resp.formatted: ('0.04889', '0.048946', '0.05237', '0.04772', None, None, '0.048856', '121996.92184212', '1511747460.4857225')
        # resp.json() {"mid":"0.048918","bid":"0.04889","ask":"0.048946","last_price":"0.048856","low":"0.04772","high":"0.05237","volume":"121996.92184212","timestamp":"1511747460.4857225"}'
        if resp.formatted:
            return float(resp.formatted[1])
        else:
            json = resp.json()
            if json['message']:
                raise Exception(json['message'])
            else:
                raise Exception("cannot convert '{}'".format(pair))


class PoloniexExchange(Exchange):
    def __init__(self):
        super().__init__("poloniex")
        self.polo = PoloniexPublic()
        self.currencies = None
        self.ticker = None

    def __ticker(self):
        if not self.ticker:
            self.ticker = self.polo.returnTicker()
        return self.ticker

    def trading_pairs(self):
        pairs = []
        for pair, ticker in self.__ticker().items():
            pairs.append(pair)
        return pairs

    def supported_withdraw(self):
        # equals for deposit and withdrawals
        self.supported_deposit()

    def make_pair(self, currency1, currency2):
        # it is very possible poloniex has reversed pair
        return currency1 + '_' + currency2

    def supported_deposit(self):
        # {'BITUSD': {'txFee': 0.15, 'id': 272, 'depositAddress': 'poloniexwallet', 'disabled': 0, 'delisted': 1, 'frozen': 0, 'minConf': 50, 'name': 'BitUSD'},
        if not self.currencies:
            self.currencies = self.polo.returnCurrencies()
        result = []
        for code, data in self.currencies.items():
            if data['disabled'] == 0 and data['delisted'] == 0:
                if data['depositAddress'] == None:  # == 'poloniexwallet':
                    result.append(code)
        return result

    def trading_pair(self, pair):
        return self.__ticker()[pair]

    def exchange_rate(self, good, money):
        """
        'ETH' 'BTC' want buy ETH for BTC
        :param pair:
        :return:
        """
        # logger.info(exchange.trading_pair('BTC_ETH'))
        # {'last': 0.05040742, 'highestBid': 0.05030052, 'lowestAsk': 0.05040737}
        # BUY ETH You have:0.02586310 BTC   Lowest Ask:0.05040734 BTC
        # SELL ETH You have:0.00000000 ETH Highest Bid:0.05030056 BTC
        # exchange.exchange_rate('BTC_ETH')
        # TODO: possible mistake in plcament of Ask and Bid
        pair = self.make_pair(money, good)
        if pair in self.__ticker():
            # direct exchange
            return self.__ticker()[pair]['lowestAsk']
        else:
            reverse_pair = self.make_pair(good, money)
            if reverse_pair in self.__ticker():
                # reverce exchange
                return 1 / self.__ticker()[reverse_pair]['highestBid']
            else:
                raise Exception("cannot find pair '{}' to exchange".format(pair))


if __name__ == "__main__":
    poloniex = PoloniexExchange()
    print(poloniex.supported_deposit())
    print(poloniex.trading_pairs())
    fout = open('currencies.json', 'w')
    d = dict(poloniex.currencies)
    for k, v in d.items():
        d[k] = dict(v)
    json.dump(d, fout, indent=2)
    fout = open('ticker.json', 'w')
    d = dict(poloniex.ticker)
    for k, v in d.items():
        d[k] = dict(v)
    json.dump(d, fout, indent=2)
