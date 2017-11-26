import datetime
import json
import logging
import re
from uuid import UUID

import models
import task_manager
from globals import assert_expr
import math
from logging import Logger
from random import random, randint

import os
from flask import request, Blueprint, render_template, redirect

import flask
from flask_mongoengine.wtf import model_form
from flask_mongoengine.wtf.fields import ModelSelectField
from flask_mongoengine.wtf.orm import ModelConverter, converts

import logging_server
from finik.crypto_data import CryptoDataProvider
from finik.cryptonator import Cryptonator
from models import User, Rig, MinerProgram, Pool, Currency, ConfigurationGroup, Todo

# DEFAULT_CONFIGURATION_GROUP = "ETH(poloniex)"
DEFAULT_CONFIGURATION_GROUP = "Test ETH+DCR"

crypto_data = CryptoDataProvider("coins1.json")
cryptonator = Cryptonator()


def todo():
    # As a list to test debug toolbar
    Todo.objects().delete()  # Removes
    Todo(title="Simple todo A", text="12345678910").save()  # Insert
    Todo(title="Simple todo B", text="12345678910").save()  # Insert
    Todo.objects(title__contains="B").update(set__text="Hello world")  # Update
    todos = list(Todo.objects[:10])
    todos = Todo.objects.all()
    return flask.render_template('todo.html', todos=todos)


def pagination():
    Todo.objects().delete()
    for i in range(10):
        Todo(title='Simple todo {}'.format(i), text="12345678910").save()  # Insert

    page_num = int(flask.request.args.get('page') or 1)
    todos_page = Todo.objects.paginate(page=page_num, per_page=3)

    return flask.render_template('pagination.html', todos_page=todos_page)


def config_list():
    return render_template('configs.html')


def config_list_json():
    configs = ConfigurationGroup.objects()
    #    list = Todo.objects.paginate(page=page_num, per_page=3)
    data = []
    for config in configs:
        data.append({
            'id': str(config.id),
            'name': config.name,
            'currency': config.currency.code,
            'pool': config.pool.name,
            'exchange': config.exchange.name,
            'wallet': config.wallet,
            'miner_programm': config.miner_program.name,
        })
    return flask.jsonify({'data': data})


def config_edit(id=''):
    class AConverter(ModelConverter):
        ''' not using now .... but in future may be '''

        @converts('ReferenceField')
        def conv_Reference(self, model, field, kwargs):
            return ModelSelectField(model=field.document_type, **kwargs)

    field_args = {
        'dual_pool': {'allow_blank': True},
        'dual_exchange': {'allow_blank': True},
        'dual_currency': {'allow_blank': True},
        'exchange': {'allow_blank': True},
    }
    formtype = model_form(ConfigurationGroup, field_args=field_args)

    if id:
        config = ConfigurationGroup.objects.get_or_404(id=id)
    else:
        config = ConfigurationGroup()

    if request.method == 'POST':
        form = formtype(request.form)
        if (form.validate()):
            # do something
            form.populate_obj(config)
            config.save()
            return redirect('configs')
        else:
            return flask.render_template('config.html', form=form)
    else:
        form = formtype(obj=config)
        return flask.render_template('config.html', form=form)


def get_uptime(rig_state):
    '''
    :return: human readable uptime in form of '1d 12h' for longer period or '12m' for minutes
    '''
    if not rig_state.rebooted:
        return '?'
    delta = datetime.datetime.now() - rig_state.rebooted
    days = delta.days
    hours = math.trunc(delta.seconds / 3600)
    minutes = math.trunc(delta.seconds / 60)
    if days > 0 or hours > 0:
        s = "%dd %dh" % (days, hours)
    else:
        s = "%dm" % (minutes)
    return s


def get_profit(currency_code, hashrate):
    '''
    return daily profit for given currency and hashrate
    :param currency_code: 'ETH' 'Nicehash-Ethash'
    :param hashrate: 141000000 (as hashers in second)
    :return:
    '''
    try:
        profit = crypto_data.calc_profit(crypto_data.for_currency(currency_code), hashrate, 86400)
        return profit
    except Exception as e:
        logging.error("Exception get_profit: %s" % e)
        raise e


def round_to_n(num, max_=2):
    '''
    round to the not more that max_ value digits after comma. (0.00034)
    But if int part > 0 then just N digits after comma (360.00)
    с точностью не более n "значащих цифр", после запятой.
    '''
    left, right = str(num).split('.')
    if left != "0":
        nums = []
        for n in right:
            nums.append(n)
            if len(nums) >= max_:
                break
        return '.'.join([left, ''.join(nums)])
    else:
        zero, nums = zero_nums = [], []
        for n in right:
            zero_nums[0 if not nums and n == '0' else 1].append(n)
            if len(nums) == max_:
                break
        return '.'.join([left, ''.join(zero) + ''.join(nums)])


def rig_list_json():
    rigs_state = Rig.objects.all()
    data = []
    for rig_state in rigs_state:
        rig = rig_state
        algo = rig.configuration_group.algo
        hashrate = []
        if rig.hashrate:
            for algorithm in algo.split("+"):
                if algorithm in rig.hashrate:
                    hashrate.append({'value': rig.hashrate[algorithm] / 1e6, 'units': 'Mh/s'})
        currency = rig.configuration_group.currency
        profit = 0
        if currency.algo in rig.hashrate:
            profit = profit + get_profit(currency.code, rig.hashrate[currency.algo])
        if rig.configuration_group.is_dual:
            currency = rig.configuration_group.dual_currency
            if currency.algo in rig.hashrate:
                profit = profit + get_profit(currency.code, rig.hashrate[currency.algo])
        try:
            # try to convert to user target currency
            target_currency = rig.user.target_currency
            exchange_rate = cryptonator.get_exchange_rate(currency.code, target_currency)
            profit_target_currency = profit * exchange_rate
            profit_string = "%s %s" % (round_to_n(profit_target_currency, 2), target_currency)
        except Exception as e:
            if profit is None:
                profit_string = "? %s" % (currency.code)
            else:
                profit_string = "%s %s" % (round_to_n(profit, 2), currency.code)
        data.append({
            'name': rig.worker,
            'uuid': rig.uuid,
            'rebooted': rig_state.rebooted,
            'hashrate': hashrate,
            'profit': profit_string,
            'uptime': get_uptime(rig_state),
            'miner': {
                'currency': currency.code,
                'configuration_id': str(rig.configuration_group.id),
                'configuration_name': rig.configuration_group.name,
            },
            'temp': rig_state.cards_temp,
            'fan': rig_state.cards_fan,
            'comment': rig.comment,
            'info': 'longlong description',
        })
    return flask.jsonify({'data': data})


def rig_list():
    return flask.render_template("rigs.html")


def get_miner_version(dir):
    # let's get miner version from viersion.txt of the client
    miner_version_filename = os.path.join('../client/miners', dir, 'version.txt')
    file = open(miner_version_filename, 'r', encoding='ascii')
    return file.readline().strip()


def get_client_version():
    '''
    returns client version stored in ../client/version.txt
    :param dir:
    :return:
    '''
    version_filename = os.path.join('..', 'client', 'version.txt')
    file = open(version_filename, 'r', encoding='ascii')
    return file.readline().strip()

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
        "miner_directory": dir,
        "miner_exe": bin,
        "miner_command_line": conf.expand_command_line(rig=rig),
        "miner_version": get_miner_version(dir),
        "env": conf.env,
        "send_output": False,
    }
    return conf


def client_config1():
    """
    Get config from client. Validate and update it.
    :return: updated config
    """
    email = request.args.get('email')
    assert_expr(re.match(r'^[^@]+@[^@]+$', email), "valid mail requred")
    rig_os = request.args.get('os')
    assert_expr(rig_os in models.OS_TYPE, "invalid os '%s' passed. Possible: %s" % (os, models.OS_TYPE))
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
        rig.configuration_group = ConfigurationGroup.objects.get(name=DEFAULT_CONFIGURATION_GROUP)
        rig.save()
    else:
        # register existing rig
        # update os. May be user has switched from Windows to Linux
        rig = rigs[0]
        rig.os = rig_os
        rig.save()
    # if miner config empty then set default miner config
    if not "miner_config" in config or not config["miner_config"]:
        rig.configuration_group = ConfigurationGroup.objects.get(name=DEFAULT_CONFIGURATION_GROUP)
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


def set_target_hashrate_from_current(rig):
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
    for algorithm in algo.split('+'):
        if algorithm in rig.target_hashrate[algo]:
            target_value = rig.target_hashrate[algo][algorithm]
        else:
            target_value = 0
        if algorithm in current_hashrate and current_hashrate[algorithm] > target_value:
            # update value
            rig.target_hashrate[algo][algorithm] = current_hashrate[algorithm]
    return False

def recieve_stat_and_return_task():
    receive_stat()
    return send_task()

def send_task():
    rig_uuid = request.args.get('rig_id')
    rig = Rig.objects.get(uuid=rig_uuid)
    # TODO: authorize uuid
    task = task_manager.task_manager.pop_task(rig.uuid)
    tasks = []
    if task:
        tasks.append({
            "task": task['name'],
            "data": task['data'],
        })
    return json.dumps(tasks)


def add_switch_miner_task(rig):
    """
    Add to task manager command for rig to switch miner to current configuration_group.
    :param rig:
    :return:
    """
    task_manager.task_manager.add_task(
        "switch_miner",
        {"miner_config": get_miner_config_for_configuration(rig.configuration_group, rig)},
        rig.uuid
    )


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
    set_target_hashrate_from_current(rig)
    rig.is_online = stat['miner']['is_run']
    if rig.is_online:
        rig.last_online_at = datetime.datetime.now
    rig.save()
    # If server has newer client version - then add client update task
    if stat['client_version'] != get_client_version():
        task_manager.task_manager.add_task(task_name="self_update", data={}, client=rig.uuid)
    # if configuration grup from client different when send task to change miner
    if stat['miner']['config']['config_name'] != rig.configuration_group.name:
        add_switch_miner_task(rig)
    return flask.jsonify('OK')


def rig_info(uuid=None):
    rig = Rig.objects.get(uuid=uuid)
    configs = ConfigurationGroup.objects(user=rig.user)
    select_config = []
    for config in configs:
        select_config.append({
            'name': config.name,
            'id': str(config.id),
            'current': rig.configuration_group.id == config.id,
        })
    data = {
        'uuid': uuid,
    }
    return flask.render_template('rig.html', rig_data=rig, configs=select_config)


def rig_log(uuid):
    logs = logging_server.rigs_memery_log
    log = ''
    if uuid in logs.keys():
        log = "\n".join(logs[uuid])
    return log


def rig_set_config(uuid):
    config_id = request.args.get('config')
    # TODO: SECURITY: check if it user's config
    rig = Rig.objects.get(uuid=uuid)
    config = ConfigurationGroup.objects.get(id=config_id)
    rig.configuration_group = config
    rig.save()
    add_switch_miner_task(rig)
    return rig_info(uuid)


def index():
    return flask.render_template('index.html')
