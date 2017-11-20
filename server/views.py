import datetime
import json
import logging
import math
from logging import Logger
from random import random, randint

from flask import request, Blueprint, render_template, redirect

import flask
from flask_mongoengine.wtf import model_form
from flask_mongoengine.wtf.fields import ModelSelectField
from flask_mongoengine.wtf.orm import ModelConverter, converts

import logging_server
from finik.crypto_data import CryptoDataProvider
from finik.cryptonator import Cryptonator
from models import User, Rig, RigState, MinerProgram, Pool, Currency, ConfigurationGroup, Todo

#DEFAULT_CONFIGURATION_GROUP = "ETH(poloniex)"
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


def get_hashrate(rig_state):
    rig = rig_state.rig
    algorithm = rig.configuration_group.currency.algo
    if rig_state.hashrate and algorithm in rig_state.hashrate:
        return rig_state.hashrate[rig.configuration_group.currency.algo]
    return {'value': 0, 'units': ""}


def get_profit(currency_code, hashrate_units, units):
    '''
    return daily profit for given currency and hashrate
    :param currency_code: 'ETH' 'Nicehash-Ethash'
    :param hashrate_units: 141
    :param units: "Mh/s"
    :return:
    '''
    try:
        hashrate = crypto_data.hashrate_from_units(hashrate_units, units)
        profit = crypto_data.calc_profit(crypto_data.for_currency(currency_code), hashrate, 86400)
        return profit
    except Exception as e:
        logging.error("Exception get_profit: %s" % e)
        return None


def rounds(num, max_=2):
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
            if len(nums)>=max_:
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
    rigs_state = RigState.objects.all()
    data = []
    for rig_state in rigs_state:
        rig = rig_state.rig
        hashrate = get_hashrate(rig_state)
        currency = rig.configuration_group.currency
        profit = get_profit(currency.code, hashrate['value'], hashrate['units'])
        try:
            # try to convert to user target currency
            target_currency = rig.user.target_currency
            exchange_rate = cryptonator.get_exchange_rate(currency.code, target_currency)
            profit_target_currency = profit * exchange_rate
            profit_string = "%s %s" % (rounds(profit_target_currency,2), target_currency)
        except Exception as e:
            if profit is None:
                profit_string = "? %s" % (currency.code)
            else:
                profit_string = "%s %s" % (rounds(profit,2), currency.code)
        data.append({
            'name': rig.worker,
            'uuid': rig.uuid,
            'rebooted': rig_state.rebooted,
            'hashrate': {'value': hashrate['value'], 'units': hashrate['units']},
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


def get_miner_config_for_configuration(conf, rig):
    return {
        "config_name": conf.name,
        "miner": conf.miner_program.name,
        "miner_family": conf.miner_program.family,
        "miner_directory": conf.miner_program.dir,
        "miner_exe": conf.miner_program.win_exe,
        "miner_command_line": conf.expand_command_line(rig=rig),
        "env": conf.env,
    }


def client_config():
    """
    Get config from client. Validate and update it.
    :return: updated config
    """
    email = request.args.get('email')
    rig_uuid = request.args.get('rig_id')
    api_key = request.args.get('rig_id')
    config = request.json
    if config is None:
        config = {}
    user = User.objects.get(email=email)
    # TODO: create new user(?)
    rigs = Rig.objects(uuid=rig_uuid)
    import server
    if len(rigs) == 0:
        user_rigs = Rig.objects(user=user)
        nrigs = len(user_rigs)
        rig = Rig()
        rig.uuid = rig_uuid
        rig.user = user
        rig.worker = 'worker%03d' % (nrigs + 1)
        rig.configuration_group = ConfigurationGroup.objects.get(name=DEFAULT_CONFIGURATION_GROUP)
        rig.save()
    else:
        rig = rigs[0]
    if not "miner_config" in config or not config["miner_config"]:
        rig.configuration_group = ConfigurationGroup.objects.get(name=DEFAULT_CONFIGURATION_GROUP)
        rig.save()
    conf = rig.configuration_group
    config["miner_config"] = get_miner_config_for_configuration(conf, rig)
    config['server'] = request.host  # 127.0.0.1:5000
    config['rig_id'] = rig_uuid
    config['email'] = email
    config['worker'] = rig.worker
    server_host = request.host.split(":")[0]
    config['logger'] = {
        'server': server_host,
        'port': logging.handlers.DEFAULT_TCP_LOGGING_PORT
    }
    config['task_manager'] = {
        "request_interval_sec": 30,
    }
    return flask.jsonify(config)


def test_get_random_config(rig):
    configs = ["Test ETH", "Test ZEC", "Test ETH+DCR"]
    name_new_config = configs[randint(0, len(configs) - 1)]
    return ConfigurationGroup.objects.get(name=name_new_config)

def sendTask():
    '''
    Send task data to the specified client
    :return:
    '''
    rig_uuid = request.args.get('rig_id')
    rig = Rig.objects.get(uuid=rig_uuid)
    return json.dumps([
        {"task": "switch_miner", "data": {"miner_config": get_miner_config_for_configuration(rig.configuration_group, rig)}}
    ])


def acceptData():
    """
    {
  "miner": {
    "is_run": false,
    "config": {
      "miner": "ewbf",
      "miner_family": "ewbf",
      "algorithm": "Equihash",
      "miner_directory": "miner_emu",
      "miner_exe": "python.exe",
      "miner_command_line": "miner_emu/miner_emu.py miner_emu/sample_output_ewbf.txt"
    }
  },
  "hashrate": {
    "current": {
      "Equihash": {
        "value": 1763.0,
        "when": 1510005374
      }
    },
    "target": {
      "Equihash": {
        "value": 1823.0,
        "when": 1510005374
      }
    }
  },
  "compute_units": {},
  "miner_stdout": [
    "00:56:14 Temp: GPU0: 60C GPU1: 66C GPU2: 56C GPU3: 61C GPU4: 61C GPU5: 59C",
    "00:56:14 GPU0: 284 Sol/s GPU1: 301 Sol/s GPU2: 289 Sol/s GPU3: 299 Sol/s GPU4: 297 Sol/s GPU5: 293 Sol/s",
    "00:56:14 Total speed: 1763 Sol/s"
  ]
}
    :return:
    """
    return sendTask()


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
    logs = logging_server.rigs_logs
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
    # TODO: SET TASK
    return rig_info(uuid)

