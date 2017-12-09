import datetime
import logging
import re
from random import randint
from uuid import UUID

import flask
from flask import Blueprint, request

from bestminer import task_manager, models, app
from bestminer.models import Rig, ConfigurationGroup, User
from bestminer.server_commons import assert_expr, get_client_version, calculate_profit_converted, round_to_n
from bestminer.task_manager import get_miner_config_for_configuration

logger = logging.getLogger(__name__)

mod = Blueprint('client', __name__, template_folder='templates')


@mod.route("/rig_config", methods=["GET", "POST", "PUT"])
def register_rig():
    """
    Get config from client. Validate and update it.
    :return: updated config
    """
    email = request.args.get('email')
    assert_expr(re.match(r'^[^@]+@[^@]+$', email), "valid mail requred")
    rig_os = request.args.get('os')
    assert_expr(rig_os in models.SUPPORTED_OS, "invalid os '%s' passed. Possible: %s" % (rig_os, models.OS_TYPE))
    rig_uuid = request.args.get('rig_id')
    assert_expr(UUID(rig_uuid))
    api_key = request.args.get('rig_id')
    config = request.get_json()
    if config is None:
        config = {}
    user = User.objects.get(email=email)
    # TODO: create new user(?)
    rigs = Rig.objects(uuid=rig_uuid)
    if len(rigs) == 0:
        # register new rig
        user_rigs = Rig.objects(user=user)
        nrigs = len(user_rigs)
        rig = Rig()
        rig.os = rig_os
        rig.uuid = rig_uuid
        rig.user = user
        rig.worker = 'worker%03d' % (nrigs + 1)
        if user.settings.default_configuration_group:
            rig.configuration_group = user.settings.default_configuration_group
        rig.manager = 'ManualRigManager'
        rig.log_to_file = True
        rig.save()
    else:
        # register existing rig
        # update os. May be user has switched from Windows to Linux
        rig = rigs[0]
        rig.os = rig_os
        rig.save()
    # if miner config empty then set default miner config
    if user.settings.default_configuration_group and (not "miner_config" in config or not config["miner_config"]):
        rig.configuration_group = user.settings.default_configuration_group
        rig.save()
    conf = rig.configuration_group
    config["miner_config"] = get_miner_config_for_configuration(conf, rig)
    config['server'] = request.host  # 127.0.0.1:5000
    config['rig_id'] = rig_uuid
    config['email'] = email
    config['worker'] = rig.worker
    config['client_version'] = get_client_version()
    server_host = request.host.split(":")[0]
    # TODO: get settings from logging_server
    config['logger'] = {
        'server': server_host,
        'port': logging.handlers.DEFAULT_TCP_LOGGING_PORT
    }
    config['task_manager'] = {
        "request_interval_sec": 15,
    }
    config['statistic_manager'] = {
        "request_interval_sec": 30,
    }
    return flask.jsonify(config)


def test_get_random_config(rig):
    configs = ["Test ETH", "Test ZEC", "Test ETH+DCR"]
    name_new_config = configs[randint(0, len(configs) - 1)]
    return ConfigurationGroup.objects.get(name=name_new_config)


def set_target_hashrate_from_current(rig, miner_code):
    '''
    Update this rig target hashrate. If current hashrate for given algo exceedes the target hashrate then update target
    Rig object not saved.
    :param rig: rig model
    :return: boolean if was updated
    '''
    algo = rig.configuration_group.algo
    current_hashrate = rig.hashrate
    if not algo in rig.target_hashrate:
        rig.target_hashrate[algo] = {}
    if not miner_code in rig.target_hashrate[algo]:
        rig.target_hashrate[algo][miner_code] = {}
    for algorithm in algo.split('+'):
        if algorithm in rig.target_hashrate[algo]:
            target_value = rig.target_hashrate[algo][algorithm]
        else:
            target_value = 0
        if algorithm in current_hashrate and current_hashrate[algorithm] > target_value:
            # update value
            # TODO: better use setter Rig.set_target_hashrate_for_algo_and_miner_code
            rig.target_hashrate[algo][miner_code][algorithm] = current_hashrate[algorithm]
    return False


@mod.route("/stat_and_task", methods=["GET", "POST", "PUT"])
def recieve_stat_and_return_task():
    receive_stat()
    return send_task()


@mod.route("/task", methods=["GET", "POST", "PUT"])
def send_task():
    rig_uuid = request.args.get('rig_id')
    rig = Rig.objects.get(uuid=rig_uuid)
    # TODO: authorize uuid
    task = task_manager.pop_task(rig.uuid)
    tasks = []
    if task:
        tasks.append({
            "task": task['name'],
            "data": task['data'],
        })
    return flask.jsonify(tasks)


@mod.route("/stat", methods=["GET", "POST", "PUT"])
def receive_stat():
    '''
{
  "hashrate": {
    "current": {
      "Ethash": 27000000,
    },
    "target": {}
  },
  "miner": {
    "config": {
      "config_name": "Test ETH",
      ...
    },
    "is_run": true,
  },
  "miner_stdout": [],
  "processing_units": [
    "nvidia_gtx_1060_3gb",
    "nvidia_gtx_1060_3gb",
    "nvidia_gtx_1060_3gb"
  ],
  "pu_fanspeed": [
    "45",
    "34",
    "30"
  ],
  "pu_temperatire": [
    "53",
    "48",
    "46"
  ],
  "reboot_timestamp": 1511326434
  "client_version": "0.9"
}
    '''
    stat = request.get_json()
    rig_uuid = request.args.get('rig_id')
    rig = Rig.objects.get(uuid=rig_uuid)
    # TODO: validate all data received from the client to the server!
    rig.cards_fan = stat['pu_fanspeed']
    rig.cards_temp = stat['pu_temperatire']
    rig.rebooted = datetime.datetime.fromtimestamp(stat['reboot_timestamp'])
    rig.hashrate = stat["hashrate"]["current"]
    set_target_hashrate_from_current(rig, stat['miner']['config']['miner_code'])
    rig.is_online = True
    rig.last_online_at = datetime.datetime.now
    rig.is_miner_run = stat['miner']['is_run']
    rig.save()
    # If server has newer client version - then add client update task
    if stat['client_version'] != get_client_version():
        task_manager.add_task(task_name="self_update", data={}, rig_uuid=rig.uuid)
    # if configuration grup from client different when send task to change miner
    if stat['miner']['config']['config_name'] != rig.configuration_group.name:
        task_manager.add_switch_miner_task(rig, rig.configuration_group)
    conf = rig.configuration_group
    profit_currency = rig.user.settings.profit_currency
    profit = calculate_profit_converted(rig, profit_currency)
    responce = {
        'worker': rig.worker,
        'mining': conf.name,
        'profit': '{} {}'.format(round_to_n(profit), profit_currency),
        'current hashrate': rig.hashrate,
        'target  hashrate': rig.target_hashrate,
    }
    return flask.jsonify(responce)

