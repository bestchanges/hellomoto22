import logging
import threading
import traceback
from datetime import datetime
from time import sleep

from bestminer.models import *



class RigManager():

    def __init__(self, papa) -> None:
        """
        :param papa: RigManagers instance which is contains all of managers
        """
        self.papa = papa

    def accept_rig(self, rig, data=None):
        pass

    def remove_rig(self, rig):
        pass

    def list_rigs(self):
        pass

    def switch_miner(self, rig, configuration_group):
        pass

    def reboot(self, rig):
        import bestminer
        bestminer.task_manager.reboot_task(rig)

    def update_client_program(self, rig):
        pass

    def start(self):
        pass

    def _switch_rig_to(self, rig, configuration_group):
        rig.configuration_group = configuration_group
        rig.save()
        import bestminer
        bestminer.task_manager.add_switch_miner_task(rig, configuration_group)


class ManualRigManager(RigManager):

    def accept_rig(self, rig, data=None):
        cg = rig.configuration_group
        # if current configuration group is not belongs to user when set to default configuration group
        if cg.user != rig.user:
            rig.configuration_group = rig.user.settings.default_configuration_group
            rig.save()
            import bestminer
            bestminer.task_manager.add_switch_miner_task(rig, cg)

    def switch_miner(self, rig, configuration_group):
        if rig.manager != self.__class__.__name__:
            raise Exception("Cannot switch while miner in conttrol of {}".format(rig.manager))
        self._switch_rig_to(rig, configuration_group)


class AutoSwitchRigManager(RigManager):

    logger = logging.getLogger(__name__)

    def __init__(self, papa, sleep_time=30):
        super().__init__(papa)
        self.managed_rigs = []  # rig_uuid -> [ config_group: ..., switched_at: ..., profit: ... ]
        self.sleep_time = sleep_time

    def accept_rig(self, rig, data=None):
        super().accept_rig(rig, data)
        best_config, best_profit = self.detect_best_config_and_profit(rig)
        self.managed_rigs.append({
            'rig': rig, 'configuration_group': best_config,
            'switched_at': datetime.datetime.now(), 'profit': best_profit
        })
        if rig.configuration_group != best_config:
            self._switch_rig_to(rig, best_config)

    def remove_rig(self, rig):
        super().remove_rig(rig)
        somelist = [x for x in self.managed_rigs if x['rig'].id != rig.id]
        self.managed_rigs = somelist


    def __del__(self):
        # TODO: is it correct of stop thread?
        self.thread._stop()

    def start(self):
        self.thread = threading.Thread(target=self.run, name='Autoswitch manager')
        self.thread.start()

    def run(self):
        self.logger.info('Starting autoswitch server...')
        while True:
            # note: make copy to avoid 'dictionary changed size during iteration'
            for data in self.managed_rigs:
                try:
                    rig = data['rig']
                    rig.reload() # things can be changed during the sleep
                    if not rig.is_online:
                        # skip offline rigs
                        continue
                    best_config, best_profit = self.detect_best_config_and_profit(rig)
                    self.logger.info("best is '{}' ({} BTC) for rig {}".format(best_config, best_profit, rig))
                    if rig.configuration_group != best_config:
                        data['switched_at'] = datetime.datetime.now()
                        data['configuration_group'] = best_config
                        data['profit'] = best_profit
                        self._switch_rig_to(rig, best_config)
                except Exception as e:
                    self.logger.error("Exception during execution. {}".format(e))
                    print(e)
            # ok. now sleep for next iteration
            sleep(self.sleep_time)

    def list_configuration_group_profit_for_rig(self, rig):
        """
        Get all configuration_groups applicable for given rig which profit can be calculated using target_hashrate
        :param rig:
        :return: sorted list of tuple (configuration_group, profit). The first is most profit
        """
        # walk over all applicable configs
        result = []
        configs = ConfigurationGroup.list_for_user(rig.user)
        for config in ConfigurationGroup.filter_applicable_for_rig(configs, rig):
            # find target hashrate value for miner and algo
            found = TargetHashrate.objects(rig=rig, miner_program=config.miner_program, algo=config.algo)
            if found:
                target_hashrate = found[0]
            else:
                continue
            # check profit for every one.
            profit_btc = config.calc_profit_for_target_hashrate(target_hashrate)
            if profit_btc is None:
                self.logger.error("Cannot calc profit for config '{}' for target_hashrate '{}'".format(config, target_hashrate))
                profit_btc = 0
            result.append((config, profit_btc))
        result.sort(key=lambda tup: tup[1], reverse=True)
        return result

    def detect_best_config_and_profit(self, rig):
        # if rig do not have any target hashrate - start benchmark
        list_config_profit = self.list_configuration_group_profit_for_rig(rig)
        best_config, best_profit = None, None
        if list_config_profit:
            best_config, best_profit = list_config_profit[0]
        if not best_config or best_profit == 0:
            # if not found any best config
            default_config = rig.user.settings.default_configuration_group
            self.logger.warning("Cannot find best configuration for {}. Fallback to default {}".format(rig, default_config))
            best_config = default_config
            best_profit = 0
        else:
            if rig.configuration_group == best_config:
                # already at best config
                pass
            elif rig.configuration_group.user != rig.user:
                # current config not belongs to user - set best config anyway
                pass
            else:
                # change best config to current if not exceed threshold
                threshold = rig.user.settings.auto_profit_switch_thresold
                current_config = rig.configuration_group
                current_profit = None
                # find current config profit
                for config, profit in list_config_profit:
                    if config == current_config:
                        current_profit = profit
                        break
                if current_profit and current_profit * (1 + threshold / 100) >= best_profit:
                    # if we found that current profit is same as
                    best_config = current_config
                    best_profit = current_profit
                else:
                    self.logger.debug("Threshold {}% not passed. Current={} Best={}".format(
                        threshold, current_profit, best_profit
                    ))
        return best_config, best_profit

class BenchmarkRigManager(RigManager):
    """
    Manage of benchmark process of the rigs.
    """

    logger = logging.getLogger(__name__)

    ETHASH_BLAKE = "Ethash+Blake Benchmark"
    ETHASH = "Ethash Benchmark"
    EQUIHASH_NVIDIA = "Equihash(nvidia) Benchmark"
    EQUIHASH_AMD = "Equihash(amd) benchmark"


    benchmark_configs = {
        'Windows': {
            'nvidia' : [ETHASH, ETHASH_BLAKE, EQUIHASH_NVIDIA],
            'amd' : [ETHASH, ETHASH_BLAKE, EQUIHASH_AMD],
        }
    }

    def __init__(self, papa, minimum_wait_sec=20, maximum_wait_sec=160, sleep_time=7):
        super().__init__(papa)
        # queue of scheduled tasks for rig
        self.tasks = {}  # rig_uuid -> [ config_group, ... ]
        # dict of currently running benchmarks
        self.running_tasks = {} # rig_uuid-> { 'rig': ... 'conf_group' ..., 'started_at': ....}
        self.minimum_wait_sec = minimum_wait_sec
        self.maximum_wait_sec = maximum_wait_sec
        self.sleep_time = sleep_time

    def __del__(self):
        # TODO: is it correcbenchmark_configst of stop thread?
        self.thread._stop()

    def start(self):
        self.thread = threading.Thread(target=self.run, name='Benchmark manager')
        self.thread.start()


    def start_clean_benchmark_for_rig(self, rig):
        # reset target hashrate values
        TargetHashrate.objects(rig=rig).delete()
        for cn in self.benchmark_configs[rig.os][rig.pu]:
            cg = ConfigurationGroup.objects.get(user=None, name=cn)
            self.add_task(rig, cg)

    def accept_rig(self, rig, data=None):
        if not rig.os:
            raise Exception("No os specified in rig")
        if not rig.pu:
            raise Exception("No pu specified in rig")
        self.start_clean_benchmark_for_rig(rig)
        super().accept_rig(rig, data)
        self.start_next_task(rig.uuid)

    def start_next_task(self, rig_uuid):
        """
        Gives rig command to start new benchmark.
        If there is no tasks in queue fallbacks rig to one of MANUAL or AUTOSWITCH mode
        :param rig_uuid:
        :return:
        """
        if rig_uuid in self.running_tasks and self.running_tasks[rig_uuid]:
            # already processing
            return
        rig = Rig.objects.get(uuid=rig_uuid)
        if rig_uuid not in self.tasks or not self.tasks[rig_uuid]:
            self.logger.info("Nothing to start. No tasks for rig {}".format(rig_uuid))
            # fallback to auto switch manager or manual
            next_manager = self.papa.AUTOSWITCH
            self.papa.set_rig_manager(rig, next_manager)
            return
        task = self.tasks[rig_uuid].pop(0)
        task['started_at'] = datetime.datetime.now()
        self.running_tasks[rig_uuid] = task
        rig.configuration_group = task['configuration_group']
        rig.save()
        import bestminer
        bestminer.task_manager.add_switch_miner_task(task['rig'], task['configuration_group'])

    def add_task(self, rig, configuration_group):
        uuid = rig.uuid
        if not uuid in self.tasks:
            self.tasks[uuid] = []
        self.logger.debug("Add task to benchmark for algo {} with miner {} for rig {}".format(configuration_group.algo, configuration_group.miner_program, rig))
        self.tasks[uuid].append({'rig': rig, 'configuration_group': configuration_group})
        self.start_next_task(uuid)

    def run(self):
        self.logger.info('Starting benchmark server...')
        while True:
            # note: make copy to avoid 'dictionary changed size during iteration'
            for rig_uuid, task in self.running_tasks.copy().items():
                try:
                    started_at = task['started_at']
                    now = datetime.datetime.now()
                    runned_time = now - started_at
                    self.logger.debug("benchmark run for {}".format(runned_time))
                    rig = task['rig']
                    if runned_time.total_seconds() < self.minimum_wait_sec:
                        self.logger.debug("{} below mininum of {}".format(runned_time, self.minimum_wait_sec))
                        continue
                    if runned_time.total_seconds() > self.maximum_wait_sec:
                        # if time above maximum: go to next task
                        self.logger.warning("Timeout of benchmark for {}. task: {}".format(rig, task))
                        del self.running_tasks[rig_uuid]
                        self.start_next_task(rig_uuid)  # start next task if exist
                    #  if exists current hashrate: save current as target and go to
                    rig = Rig.objects.get(uuid=rig_uuid)
                    configuration_group = task['configuration_group']
                    found = TargetHashrate.objects(rig=rig, miner_program=configuration_group.miner_program, algo=configuration_group.algo)
                    if found and found[0].hashrate:
                        self.logger.info("It took {} to benchmark {} on {}".format(runned_time, configuration_group, rig))
                        del self.running_tasks[rig_uuid]
                        self.start_next_task(rig_uuid) # start next task if exist
                except Exception as e:
                    self.logger.error("Exception during execution. {}".format(e))
                    print(e)
            # ok. now sleep for next iteration
            sleep(self.sleep_time)

    def remove_rig(self, rig):
        del self.tasks[rig.uuid]
        if rig.uuid in self.running_tasks:
            del self.running_tasks[rig.uuid]
        super().remove_rig(rig)


    def rig_in_benchmark(self, rig_uuid):
        return rig_uuid in self.running_tasks and len(self.running_tasks[rig_uuid]) > 0

class RigManagers():
    """
    Do not forget to call start_all in order to make rig_managers work
    """
    logger = logging.getLogger(__name__)

    # constants for clients
    BENCHMARK = BenchmarkRigManager.__name__
    AUTOSWITCH = AutoSwitchRigManager.__name__
    MANUAL = ManualRigManager.__name__

    def __init__(self):
        self.rig_managers = {}
        self.__add_rig_manager(BenchmarkRigManager(self))
        self.__add_rig_manager(ManualRigManager(self))
        self.__add_rig_manager(AutoSwitchRigManager(self))

    def __add_rig_manager(self, rig_manager):
        self.rig_managers[type(rig_manager).__name__] = rig_manager

    def get_rig_manager_by_name(self, name) -> RigManager:
        return self.rig_managers[name]

    def manual(self) -> ManualRigManager:
        return self.get_rig_manager_by_name(ManualRigManager.__name__)

    def benchmark(self) -> BenchmarkRigManager:
        return self.get_rig_manager_by_name(BenchmarkRigManager.__name__)

    def autoprofit(self) -> AutoSwitchRigManager:
        return self.get_rig_manager_by_name(AutoSwitchRigManager.__name__)

    def start_all(self):
        """
        Run all required manager's threads
        :return:
        """
        for interface in self.rig_managers.values():
            interface.start()


    def distribute_all_rigs(self):
        """
        Run once in server start.
        query all rigs and distribute them amoung corresponging manager
        It cancels all benchmarking and fall em back to auto or manual
        :return:
        """
        for rig in Rig.objects():
            manager_name = rig.manager
            # fallback to auto switch manager or manual
            if manager_name == self.BENCHMARK:
                manager_name = self.AUTOSWITCH
                rig.manager = manager_name
                rig.save()
            try:
                manager = self.get_rig_manager_by_name(manager_name)
                manager.accept_rig(rig)
            except Exception as e:
                self.logger.error("Error setting manager {} for rig {}. {}".format(manager_name, rig, e))


    def set_rig_manager(self, rig, rig_manager_or_name, data=None):
        current_rig_manager_name = rig.manager
        if isinstance(rig_manager_or_name, RigManager):
            rig_manager = rig_manager_or_name
        else:
            rig_manager = self.get_rig_manager_by_name(rig_manager_or_name)
        current_rig_manager = self.get_rig_manager_by_name(current_rig_manager_name)
        self.logger.debug("Changing rig manager for {} from {} to {}".format(rig, current_rig_manager, rig_manager))
        # reassign if change to the same
        #if current_rig_manager_name == rig_manager_name:
        #    self.logger.debug("Already managed by this. No need to change")
        #    return
        # ok they different. Let's change
        current_rig_manager.remove_rig(rig)
        rig_manager.accept_rig(rig, data)
        # now save new rig_manager in rig settings
        rig.manager = rig_manager.__class__.__name__
        rig.save()
        return rig_manager



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bm = BenchmarkRigManager(minimum_wait_sec=3, maximum_wait_sec=10, sleep_time=1)
    rig = Rig.objects(worker="worker001")[0]
    bm.accept_rig(rig)


