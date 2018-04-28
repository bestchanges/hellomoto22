import datetime
import json
import logging
import threading
from urllib.request import Request, urlopen
from bestminer import exit_event

import sys

from bestminer.models import Currency, Rig

logger = logging.getLogger(__name__)


class WTMManager():
    def __init__(self, sleep_time=300, save_wtm_to_file=None):
        self.sleep_time = sleep_time
        self.save_wtm_to_file = save_wtm_to_file

    def start(self):
        self.thread = threading.Thread(target=self.run, name='Profit manager')
        self.thread.start()

    def load_wtm_data(self):
        logger.info("Loading currencies data from WhatToMine")
        try:
            q = Request('http://whattomine.com/coins.json')
            q.add_header('User-agent',
                         'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5')
            a = urlopen(q)
            response = a.read().decode('utf-8')
            result = json.loads(response)
            return result
        except Exception as e:
            logging.error("Error loading currencies: {} ".format(e))

    def update_currency_from_wtm(self, wtm):
        '''
        :param wtm: What To Mine JSON decoded
        :return:
        '''
        logger.info("Update currency data {} items.".format(len(wtm['coins'].items())))
        now = datetime.datetime.now()
        for currency, data in wtm['coins'].items():
            Currency.objects(
                code=data['tag'],
            ).update_one(
                algo=data["algorithm"],
                block_reward=data["block_reward"],
                block_time=data["block_time"],
                difficulty=data["difficulty"],
                nethash=data["nethash"],
                updated_at=now,
                upsert=True
            )

    def run(self):
        # False = disable periodical load
        while True:
            logger.info("Load data from what to mine")
            try:
                wtm_data = self.load_wtm_data()
            except:
                e = sys.exc_info()[0]
                logger.error("Exception load WTM data: {}".format(e))
                continue
            if self.save_wtm_to_file and wtm_data:
                fout = open(self.save_wtm_to_file, 'w')
                json.dump(wtm_data, fout, indent=2)
                fout.close()
            try:
                if wtm_data:
                    self.update_currency_from_wtm(wtm_data)
            except Exception as e:
                logger.error("Exception update_currency_data_from_whattomine: {}".format(e))
            logger.info("Load data from what to mine after {} ".format(self.sleep_time))
            exit_event.wait(self.sleep_time)


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    # data = pm.load_data_from_whattomine()
    data = json.load(open('coins.json'))
    profit_manager = WTMManager()
    profit_manager.update_currency_from_wtm(data)
    rig = Rig.objects.get(worker="worker002")


if __name__ == '__main__':
    main()
