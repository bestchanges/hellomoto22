
import logging
import os
from datetime import datetime

from bestminer.server_commons import expand_command_line

logger = logging.getLogger(__name__)

# TODO: Move to rig_manager.py
class TaskManager():
    """
    This class do client's task management.

    Each task client has own tasks queue.
    Tasks dispatched as FIFO.
    """

    def __init__(self):
        self.clients_tasks = {}

    def add_switch_miner_task(self, rig, configuration_group):
        """
        Add to task manager command for rig to switch miner to current configuration_group.
        :param rig:
        :return:
        """
        logger.debug("add_switch_miner_task: rig={} configuration_group={}".format(rig, configuration_group))
        self.add_task(
            "switch_miner",
            {"miner_config": get_miner_config_for_configuration(configuration_group, rig)},
            rig.uuid
        )

    def reboot_task(self, rig):
        """
        Add to task manager command for rig to switch miner to current configuration_group.
        :param rig:
        :return:
        """
        self.add_task(
            "reboot",
            {},
            rig.uuid
        )

    def add_task(self, task_name, data, rig_uuid):
        """
        add new task in the end of queue
        There are can be only one task for client with given task_name.
        If you add task with existing task_name, then your new task replace existing one
        :param task_name:
        :param data:
        :param rig_uuid:
        :return:
        """
        if not rig_uuid in self.clients_tasks:
            self.clients_tasks[rig_uuid] = []
        task = {
            'name': task_name,
            'data': data,
            'when_add': datetime.now,
        }
        tasks = self.clients_tasks[rig_uuid]
        for index, exist_task in enumerate(tasks):
            # replace existing task with same name
            if task['name'] == exist_task['name']:
                tasks[index] = task
                return
        tasks.append(task)

    def pop_task(self, rig_uuid):
        """
        get the first task to dispatch and remove it from task queue
        :param rig_uuid:
        :return: the first task in queue
        """
        if not rig_uuid in self.clients_tasks:
            return None
        if len(self.clients_tasks[rig_uuid]) > 0:
            return self.clients_tasks[rig_uuid].pop(0)


def get_miner_config_for_configuration(conf, rig):
    os = rig.os
    if not os in conf.miner_program.supported_os:
        raise Exception("rig '%s' os %s not supported in miner %s" % (rig.name, os, conf.miner_program))
    if os == "Linux":
        bin = conf.miner_program.linux_bin
        dir = conf.miner_program.dir_linux
    elif os == "Windows":
        bin = conf.miner_program.win_exe
        dir = conf.miner_program.dir
    else:
        raise Exception("usupported os %s" % os)
    # TODO: check if miner supports OS of rig
    # TODO: check if miner supports PU of rig
    conf = {
        "config_name": conf.name,
        "miner": conf.miner_program.name,
        "miner_family": conf.miner_program.family,
        "miner_code": conf.miner_program.code,
        "miner_directory": dir,
        "miner_exe": bin,
        "miner_command_line": expand_command_line(configuration_group=conf, worker=rig.worker),
        "miner_version": get_miner_version(dir),
        "env": conf.env,
        "read_output": False,
    }
    return conf


def get_miner_version(dir):
    # let's get miner version from viersion.txt of the client
    miner_version_filename = os.path.join('../client/miners', dir, 'version.txt')
    file = open(miner_version_filename, 'r', encoding='ascii')
    return file.readline().strip()