import datetime
import logging
import re
from random import randint
from uuid import UUID

import flask
from flask import Blueprint, request

from bestminer import task_manager, models, rig_managers
from bestminer.client_api import get_miner_config_for_configuration
from bestminer.models import Rig, ConfigurationGroup, User, TargetHashrate, MinerProgram
from bestminer.server_commons import assert_expr, get_client_version, round_to_n, \
    get_exchange_rate

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
    config['pu'] = rig.pu
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


def set_target_hashrate_from_current(rig):
    '''
    Update this rig target hashrate. If current hashrate for given algo exceedes the target hashrate then update target
    Rig object not saved.
    :param rig: rig model
    :return: boolean if was updated
    '''
    algo = rig.configuration_group.algo
    current_hashrate = rig.hashrate
    miner_program = rig.configuration_group.miner_program
    found = TargetHashrate.objects(rig=rig, miner_program=miner_program, algo=algo)
    if found:
        rig_miner_algo_hashrate = found[0]
    else:
        rig_miner_algo_hashrate = TargetHashrate()
        rig_miner_algo_hashrate.rig = rig
        rig_miner_algo_hashrate.miner_program = miner_program
        rig_miner_algo_hashrate.algo = algo
        algorithms = algo.split('+')
        rig_miner_algo_hashrate.algorithm = algorithms[0]
        if len(algorithms) > 1:
            rig_miner_algo_hashrate.algorithm_dual = algorithms[1]
        rig_miner_algo_hashrate.save()
    # for dual algos we use only first algoritm to find max value
    algorithms = algo.split('+')
    algorithm = algorithms[0] # 'Ethash' from 'Ethash+Blake'
    if algorithm in current_hashrate and current_hashrate[algorithm] > rig_miner_algo_hashrate.hashrate:
        rig_miner_algo_hashrate.hashrate = current_hashrate[algorithm]
        # if is_dual and current_hashrate has value for dual
        if len(algorithms)>1 and algorithms[1] in current_hashrate:
            rig_miner_algo_hashrate.hashrate_dual = current_hashrate[algorithms[1]]
        rig_miner_algo_hashrate.save()


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
  "pu_types": ['amd']
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
    set_target_hashrate_from_current(rig)
    rig.is_online = True
    do_run_benchmark = False
    if not rig.pu and 'pu_types' in stat and stat['pu_types']:
        # WE GOT PU TYPE FROM CLIENT. AND THAT's NEW INFORMATION FOR US
        # do not overwrite pu if already set
        # Note: now rig supports only ONE PU family
        rig.pu = stat['pu_types'][0]
        do_run_benchmark = True
    rig.last_online_at = datetime.datetime.now
    rig.is_miner_run = stat['miner']['is_run']
    rig.save()
    # If server has newer client version - then add client update task
    if stat['client_version'] != get_client_version():
        task_manager.add_task(task_name="self_update", data={}, rig_uuid=rig.uuid)
    # if configuration grup from client different when send task to change miner
    if not stat['config']['miner_config'] or stat['config']['miner_config']['config_name'] != rig.configuration_group.name:
        task_manager.add_switch_miner_task(rig, rig.configuration_group)
    if do_run_benchmark:
        rig_managers.set_rig_manager(rig, rig_managers.BENCHMARK)
    conf = rig.configuration_group
    profit_currency = rig.user.settings.profit_currency
    profit_btc = rig.get_current_profit_btc()
    rate = get_exchange_rate('BTC', profit_currency)
    if rate is None:
        profit_str = '? {}'.format(profit_currency)
    else:
        profit_str = '{} {}'.format(round_to_n(profit_btc * rate), profit_currency)
    response = {
        'worker': rig.worker,
        'mining': conf.name,
        'profit': profit_str,
        'current hashrate': rig.hashrate,
        'target  hashrate': rig.target_hashrate,
    }
    return flask.jsonify(response)

