import logging
import threading
from datetime import datetime
from time import sleep

from bestminer import task_manager
from bestminer.models import *

MANUAL = 'ManualRigManager'
AUTOPROFIT = 'AutoProfitRigManager'
BENCHMARK = 'BenchmarkRigManager'


logger = logging.getLogger(__name__)

class RigManager():
    def accept_rig(self, rig):
        raise Exception("Implement it!")


class ManualRigManager(RigManager):
    def accept_rig(self, rig):
        pass


class AutoProfitRigManager(RigManager):
    def accept_rig(self, rig):
        # if rig do not have any target hashrate - start benchmark
        if not rig.target_hashrate:
            rig.manager = BENCHMARK
            rig.save()
            benchmark().accept_rig(rig)


class BenchmarkRigManager(RigManager):
    """
    Manage of benchmark process of the rigs.
    """

    def __init__(self, minimum_wait_sec=20, maximum_wait_sec=60, sleep_time=10):
        super().__init__()
        # queue of tasks for benchmark for given rig
        self.tasks = {}  # rig_uuid -> [ config_group, ... ]
        # dict of currently runiing benchmarks
        self.running_tasks = {} # rig_uuid-> { 'rig': ... 'conf_group' ..., 'started_at': ....}
        self.minimum_wait_sec = minimum_wait_sec
        self.maximum_wait_sec = maximum_wait_sec
        self.sleep_time = sleep_time
        self.thread = threading.Thread(target=self.run, name='Benchmark manager')
        self.thread.start()

    def __del__(self):
        # TODO: is it correct of stop thread?
        self.thread._stop()

    def accept_rig(self, rig):
        self.start_next_task(rig.uuid)

    def start_next_task(self, rig_uuid):
        if rig_uuid in self.running_tasks and self.running_tasks[rig_uuid]:
            # already processing
            return
        if rig_uuid not in self.tasks or not self.tasks[rig_uuid]:
            logger.warning("Nothing to start. No tasks for rig {}".format(rig_uuid))
            return
        task = self.tasks[rig_uuid].pop(0)
        task['started_at'] = datetime.now()
        self.running_tasks[rig_uuid] = task
        task_manager.add_switch_miner_task(task['rig'], task['configuration_group'])

    def add_task(self, rig, configuration_group):
        uuid = rig.uuid
        if not uuid in self.tasks:
            self.tasks[uuid] = []
        logger.debug("Add task to benchmark for algo {} with miner {} for rig {}".format(configuration_group.algo, configuration_group.miner_program, rig))
        self.tasks[uuid].append({'rig': rig, 'configuration_group': configuration_group})
        self.start_next_task(uuid)

    def run(self):
        logger.info('Starting benchmark server...')
        while True:
            # note: make copy to avoid 'dictionary changed size during iteration'
            for rig_uuid, task in self.running_tasks.copy().items():
                started_at = task['started_at']
                now = datetime.now()
                runned_time = now - started_at
                logger.debug("benchmark run for {}".format(runned_time))
                rig = task['rig']
                if runned_time.total_seconds() < self.minimum_wait_sec:
                    logger.debug("{} below mininum of {}".format(runned_time, self.minimum_wait_sec))
                    continue
                if runned_time.total_seconds() > self.maximum_wait_sec:
                    # if time above maximum: go to next task
                    logger.warning("Timeout of benchmark for {}. task: {}".format(rig, task))
                    del self.running_tasks[rig_uuid]
                    self.start_next_task(rig_uuid)  # start next task if exist
                #  if exists current hashrate: save current as target and go to
                # see set_target_hashrate_from_current() where target hashrate is stored
                rig = Rig.objects.get(uuid=rig_uuid)
                configuration_group = task['configuration_group']
                target_hashrate = rig.get_target_hashrate_for_algo_and_miner_code(configuration_group.algo, configuration_group.miner_program.code)
                if target_hashrate:
                    logger.info("It took {} to benchmark {} on {}".format(runned_time, configuration_group, rig))
                    del self.running_tasks[rig_uuid]
                    self.start_next_task(rig_uuid) # start next task if exist
            # ok. now sleep for 10 seconds
            logger.debug("Sleep for next iteration")
            sleep(self.sleep_time)


    def rig_in_benchmark(self, rig_uuid):
        return rig_uuid in self.running_tasks and len(self.running_tasks[rig_uuid]) > 0

    def benchmark_rig(self, rig, force_all=False):
        # get all applicable miners
        logger.debug("Add rig {} for benchmark".format(rig))
        miners = MinerProgram.objects(supported_os=rig.os, supported_pu=rig.pu)
        logger.debug("Foung {} of applicable miners".format(len(miners)))
        for miner in miners:
            # check if they not have target_hashrate yet
            algo = miner.algos[0]
            if force_all or (algo not in rig.target_hashrate or miner.code not in rig.target_hashrate[algo]):
                # find configuration group for this miner
                configs = ConfigurationGroup.objects(miner_program=miner)
                logger.debug("Found {} configs for miner {}".format(len(configs), miner))
                if len(configs) == 0:
                    logger.error("Found 0 configs for miner {}. Skip benchmark".format(miner))
                    continue
                self.add_task(rig, configs[0])


def distribute_all_rigs():
    """
    query all rigs and distribute them amoung corresponging manager
    :return:
    """
    for rig in Rig.objects():
        manager_name = rig.manager
        manager = rig_manager_by_name(manager_name)
        manager.accept_rig(rig)

rig_managers = {}

def __add_rig_manager(rig_manager):
    rig_managers[type(rig_manager).__name__] = rig_manager

def rig_manager_by_name(name) -> RigManager:
    return rig_managers[name]

def manual() -> ManualRigManager:
    return rig_manager_by_name(MANUAL)

def benchmark() -> BenchmarkRigManager:
    return rig_manager_by_name(BENCHMARK)

def autoprofit() -> BenchmarkRigManager:
    return rig_manager_by_name(AUTOPROFIT)

__add_rig_manager(BenchmarkRigManager())
__add_rig_manager(ManualRigManager())
__add_rig_manager(AutoProfitRigManager())

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bm = benchmark()
    mm = manual()
    # bm = BenchmarkRigManager(minimum_wait_sec=3, maximum_wait_sec=10, sleep_time=1)
    rig = Rig.objects()[0]
    group = ConfigurationGroup.objects()[0]
    bm.add_task(rig, group)
    logger.info("OK")


