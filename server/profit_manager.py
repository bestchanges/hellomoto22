import json
import logging
from threading import Thread
from urllib.request import Request, urlopen

from models import Currency

logger = logging.getLogger(__name__)

def load_data_from_whattomine():
    logging.info("Loading currencies data from WhatToMine")
    try:
        q = Request('http://whattomine.com/coins.json')
        q.add_header('User-agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5')
        a = urlopen(q)
        return json.load(a)
    except Exception as e:
        logging.error("Error loading currencies: {} ".format(e))
        raise e


def update_currency_data_from_whattomine(wtm):
    '''
    :param wtm: What To Mine JSON decoded
    :return:
    '''
    for currency, data in wtm['coins'].items():
        Currency.objects(
            code=data['tag'],
        ).update_one(
            algo=data["algorithm"],
            block_reward=data["block_reward"],
            difficulty=data["difficulty"],
            nethash=data["nethash"],
            upsert=True
        )


class ProfitManager(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)

    def run(self):
        super().run()

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    data = load_data_from_whattomine()
    update_currency_data_from_whattomine(data)