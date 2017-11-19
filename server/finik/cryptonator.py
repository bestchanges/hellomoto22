#!/usr/bin/env/ python
# encoding: utf-8

"""
Cryptonator API wrapper library.
Meant to be as simple as possible.

Updated: add caching for 1 minute
"""

import requests
from expiringdict import ExpiringDict
from logging import getLogger

__author__ = 'aldur'

API_CURRENCIES = "https://www.cryptonator.com/api/currencies"
API_SIMPLE_TICKER = "https://api.cryptonator.com/api/ticker/{}-{}"


class CryptonatorException(Exception):
    """Custom exception to be thrown on API error."""
    pass


def get_available_currencies():
    """Return a list of all available Cryptonator currencies."""
    r = requests.get(API_CURRENCIES)
    if r.status_code != requests.codes.ok:
        raise CryptonatorException(
            ("An error occurred while getting available currencies "
             "({} from Cryptonator).").format(r.status_code)
        )

    return [currency['code'] for currency in r.json()['rows']]


class Cryptonator(object):

    """
    Cryptonator API object.
    """

    def __init__(self):
        self.session = requests.Session()  # Use connection pooling for multiple requests.
        self.cache = ExpiringDict(max_len=500, max_age_seconds=60)

    def get_exchange_rate(self, base, target, raise_errors=True):
        """Return the ::base:: to ::target:: exchange rate."""
        assert base and target

        base, target = base.lower(), target.lower()

        key = "%s-%s" % (base, target)
        if key in self.cache.keys() and self.cache.get(key):
            price = self.cache[key]['ticker']['price']
            return float(price)

        r = self.session.get(API_SIMPLE_TICKER.format(base, target))
        if r.status_code != requests.codes.ok:
            if not raise_errors:
                return None
            raise CryptonatorException(
                ("An error occurred while getting requested exchange rate "
                 "({} from Cryptonator).").format(r.status_code)
            )

        j = r.json()
        if not j['success'] or j['error']:
            if not raise_errors:
                return None
            raise CryptonatorException(
                ("An error occurred while getting requested exchange rate ({}, {})"
                 "('{}').").format(base, target, j['error'])
            )
        self.cache[key] = j
        return float(j['ticker']['price'])

    def get_exchange_rates(self, base, targets=None):
        """Return the ::base:: to ::targets:: exchange rate (as a dictionary)."""
        if targets is None:
            targets = get_available_currencies()

        return {t: self.get_exchange_rate(base, t, raise_errors=False) for t in targets}


def get_exchange_rate(base, target, *args, **kwargs):
    """
    Return the ::base:: to ::target:: exchange rate.
    Wraps around ::Cryptonator.get_exchange_rate::.
    """
    return Cryptonator().get_exchange_rate(base, target, *args, **kwargs)
