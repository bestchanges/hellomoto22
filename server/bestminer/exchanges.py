# coding=utf-8
import datetime
import logging
import threading

import ccxt
import time

from bestminer.models import Currency

logger = logging.getLogger(__name__)

class Exchange(object):
    def __init__(self, exchange, code):
        self.exchange = exchange()
        self.code = code

    def get_rate(self, pair):
        return self.exchange.fetch_ticker(pair)

    def update_listed(self):
        currencies = Currency.objects(listed_in=self.code)
        for currency in currencies:
            self.__update_currency(currency)


    def __update_currency(self, currency):
        try:
            ticker = self.get_rate("{}/BTC".format(currency.code))
        except:
            logger.debug('cannot get exchange rate for {} on {}'.format(currency.code, self))
            return False
        now = datetime.datetime.now()
        rate = ticker['bid']
        # https://github.com/ccxt/ccxt/wiki/Manual#price-tickers
        currency.exchange_rates_btc[self.code] = {'rate': rate, 'volume_24h': ticker['quoteVolume'], 'updated': now}
        if self.code not in currency.listed_in:
            currency.listed_in.append(self.code)
        currency.save()
        logger.debug('exchange rate for {}={} on {}'.format(currency.code, rate, self))
        return True

    def update_all(self):
        currencies = Currency.objects()
        for currency in currencies:
            updated = self.__update_currency(currency)
            if not updated and self.code in currency.listed_in:
                currency.listed_in.remove(self.code)
                currency.save()
            if not updated and self.code in currency.exchange_rates_btc:
                del currency.exchange_rates_btc[self.code]
                currency.save()

    def stop(self):
        self.stop = True

    def start_updater(self, sleep):
        self.sleep = sleep
        self.thread = threading.Thread(target=self.__run, name='exchange updater {}'.format(self.code))
        logger.info("Starting {} with sleep delay {} sec".format(self.thread, self.sleep))
        self.stop = False
        self.thread.start()

    def __run(self):
        iteration = 0
        while not self.stop:
            if iteration % 10 == 0:
                self.update_all()
            else:
                self.update_listed()
            iteration += 1
            logger.debug("Suspend updater for {} seconds.".format(self.sleep))
            time.sleep(self.sleep)

    def __str__(self) -> str:
        return "Exchange {}".format(self.code)

exchanges = {
    'bitfinex': Exchange(ccxt.bitfinex, 'bitfinex'),
    'bithumb': Exchange(ccxt.bithumb, 'bithumb'),
    'bittrex': Exchange(ccxt.bittrex, 'bittrex'),
    'poloniex': Exchange(ccxt.poloniex, 'poloniex'),
    'cryptopia': Exchange(ccxt.cryptopia, 'cryptopia'),
    'exmo': Exchange(ccxt.exmo, 'exmo'),
    'yobit': Exchange(ccxt.yobit, 'yobit'),
}


def start_auto_update(sleep=120):
    for exchange in exchanges.values():
        exchange.start_updater(sleep)

def update_all_exchanges():
    logger.info("Start update all exchanges")
    for e in exchanges.values():
        e.update_all()
    logger.info("Finish update all exchanges")
