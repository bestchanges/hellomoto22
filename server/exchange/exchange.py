import json
from abc import ABC, abstractmethod
from poloniex import PoloniexPublic

class Exchange(ABC):
    @abstractmethod
    def trading_pairs(self):
        pass

    def supported_deposit(self):
        pass

    def supported_withdraw(self):
        pass


class PoloniexExchange(Exchange):
    def __init__(self) :
        self.polo = PoloniexPublic()
        self.currencies = None
        self.ticker = None

    def trading_pairs(self):
        if not self.ticker:
            self.ticker = self.polo.returnTicker()
        pairs = []
        for pair, ticker in self.ticker.items():
            pairs.append(pair)
        return pairs

    def supported_withdraw(self):
        # equals for deposit and withdrawals
        self.supported_deposit()


    def supported_deposit(self):
        # {'BITUSD': {'txFee': 0.15, 'id': 272, 'depositAddress': 'poloniexwallet', 'disabled': 0, 'delisted': 1, 'frozen': 0, 'minConf': 50, 'name': 'BitUSD'},
        if not self.currencies:
            self.currencies = self.polo.returnCurrencies()
        result = []
        for code, data in self.currencies.items():
            if data['disabled'] == 0 and data['delisted'] == 0:
                if data['depositAddress'] == None: # == 'poloniexwallet':
                    result.append(code)
        return result


if __name__ == "__main__":
    poloniex = PoloniexExchange()
    print(poloniex.supported_deposit())
    print(poloniex.trading_pairs())
    fout = open('currencies.json', 'w')
    d = dict(poloniex.currencies)
    for k,v in d.items():
        d[k] = dict(v)
    json.dump(d, fout, indent=2)
    fout = open('ticker.json', 'w')
    d = dict(poloniex.ticker)
    for k,v in d.items():
        d[k] = dict(v)
    json.dump(d, fout, indent=2)
