import datetime
import logging
import threading

import time

from bestminer.models import Rig

logger = logging.getLogger(__name__)

class MonitoringManager():
    def __init__(self, sleep_time=30, offline_timeout=90):
        self.sleep_time = sleep_time
        self.offline_timeout = offline_timeout

    def start(self):
        self.thread = threading.Thread(target=self.run, name='Monitoring manager')
        self.thread.start()

    def run(self):
        while True:
            rigs = Rig.objects(is_online=True)
            for rig in rigs:
                last_online = rig.last_online_at
                timedelta = datetime.datetime.now() - last_online
                if timedelta.total_seconds() > self.offline_timeout:
                    logger.debug("rig {} goes offline: {} ({} ago)".format(rig, last_online, timedelta))
                    rig.is_online = False
                    rig.is_miner_run = False
                    rig.hashrate = {}
                    rig.cards_temp = []
                    rig.cards_fan = []
                    rig.save()
            time.sleep(self.sleep_time)