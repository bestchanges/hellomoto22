import datetime
import logging
import math
import traceback

import flask
import flask_login
from copy import deepcopy

import sys
from flask import request, render_template, Blueprint, url_for
from flask_login import login_required
from flask_mongoengine.wtf import model_form

from bestminer import client_api, logging_server, rig_managers
from bestminer.dbq import list_supported_currencies
from bestminer.distr import client_zip_windows_for_user
from bestminer.models import ConfigurationGroup, PoolAccount, Rig, MinerProgram, Currency, UserSettings
from bestminer.server_commons import round_to_n, list_configurations_applicable_to_rig, \
    get_exchange_rate, compact_hashrate, assert_expr

mod = Blueprint('user', __name__, template_folder='templates')
logger = logging.getLogger(__name__)

@mod.route('/download')
@login_required
def download():
    return flask.render_template('download.html')


@mod.route("/download_win")
@login_required
def download_win():
    user = flask_login.current_user.user
    zip_file = client_zip_windows_for_user(user, request.host)
    return flask.redirect(request.host_url + zip_file)


@mod.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = flask_login.current_user.user
    field_args = {
        'default_configuration_group': {
            'queryset': ConfigurationGroup.objects(user=user)
        }
    }
    formtype = model_form(UserSettings, field_args=field_args)

    obj = user.settings

    if request.method == 'POST':
        form = formtype(request.form)
        if form.validate():
            # do something
            form.populate_obj(obj)
            obj.save()
            flask.flash("Updated OK")
            return flask.redirect(url_for('.settings'))
    else:
        form = formtype(obj=obj)
    return render_template('settings.html', form=form)


@mod.route("/configs")
@login_required
def config_list():
    return render_template('configs.html')


@mod.route("/configs.json")
@login_required
def config_list_json():
    user = flask_login.current_user.user
    configs = ConfigurationGroup.objects(user=user)
    data = []
    for config in configs:
        currencies = [config.currency.code]
        if config.is_dual:
            currencies.append(config.dual_currency.code)
        data.append({
            'id': str(config.id),
            'name': config.name,
            'currency': currencies,
            'miner_programm': config.miner_program.name,
            'supported_pu': config.miner_program.supported_pu,
        })
    return flask.jsonify({'data': data})


@mod.route('/config_miner_program_data.json')
@login_required
def config_miner_data_json():
    # TODO: filter queried data
    miner_program_id = request.args.get('id')
    if not miner_program_id:
        return flask.jsonify({})
    miner_program = MinerProgram.objects.get(id=miner_program_id)
    algos = miner_program.algos[0].split('+')
    currencies = Currency.objects(algo=algos[0])
    currencies_dual = []
    is_dual = False
    if len(algos) > 1:
        is_dual = True
        currencies_dual = Currency.objects(algo=algos[1])
    return flask.jsonify({
        'miner_program': miner_program,
        'is_dual': is_dual,
        'currencies': currencies,
        'currencies_dual': currencies_dual,
    })


@mod.route('/config/', defaults={'id': None}, methods=["GET", "POST"])
@mod.route('/config/<id>', methods=["GET", "POST"])
@login_required
def config_edit(id=''):
    field_args = {
        'miner_program': {'allow_blank': True},
        'currency': {'allow_blank': True},
    }
    formtype = model_form(ConfigurationGroup, field_args=field_args, only=
    [
        'name', 'miner_program',
        'currency', 'pool_server', 'pool_login', 'pool_password',
        'dual_currency', 'dual_pool_server', 'dual_pool_login', 'dual_pool_password',
        'is_active', 'command_line',
    ])
    user = flask_login.current_user.user

    if id:
        config = ConfigurationGroup.objects.get(id=id)
    else:
        config = ConfigurationGroup()

    if request.method == 'POST':
        formdata = request.form.copy()
        form = formtype(formdata)
        if form.validate():
            # do something
            form.populate_obj(config)
            config.user = user
            config.algo = config.miner_program.algos[0]
            config.save()
            return flask.redirect(url_for('.config_list'))
        else:
            return flask.render_template('config.html', form=form)
    else:
        form = formtype(obj=config)
        return flask.render_template('config.html', form=form)


@mod.route('/poolaccounts', methods=["GET", "POST"])
@login_required
def poolaccount_list():
    return render_template('poolaccounts.html')


@mod.route('/poolaccounts.json')
@login_required
def poolaccount_list_json():
    user = flask_login.current_user.user
    objects = PoolAccount.objects(user=user)
    data = []
    for o in objects:
        data.append({
            'id': str(o.id),
            'name': o.name,
            'currency': o.pool.currency.code,
            'login': o.login,
            'server': o.pool.server,
            'active': o.pool.is_online and o.is_active,
        })
    return flask.jsonify({'data': data})


@mod.route('/poolaccount/', methods=["GET", "POST"])
def poolaccount_add():
    user = flask_login.current_user.user

    field_args = {
        'pool': {'allow_blank': True},
    }
    formtype = model_form(PoolAccount, only=['name', 'pool', 'login', 'password', 'is_active'], field_args=field_args)

    obj = PoolAccount()

    if request.method == 'POST':
        form = formtype(request.form)
        if form.validate():
            form.populate_obj(obj)
            obj.user = user
            obj.save()
            return flask.redirect('poolaccounts')
        else:
            return flask.render_template('poolaccount_add.html', form=form)
    else:
        form = formtype(obj=obj)
        return flask.render_template('poolaccount_add.html', form=form, currencies=list_supported_currencies())


@mod.route('/poolaccount/<id>', methods=["GET", "POST"])
@login_required
def poolaccount_edit(id=''):
    user = flask_login.current_user.user

    field_args = {
        'pool': {'allow_blank': True},
    }
    formtype = model_form(PoolAccount, only=['name', 'pool', 'login', 'password', 'is_active'], field_args=field_args)

    if id:
        obj = PoolAccount.objects.get(id=id)
    else:
        obj = PoolAccount()

    if request.method == 'POST':
        form = formtype(request.form)
        if form.validate():
            form.populate_obj(obj)
            obj.user = user
            obj.save()
            return flask.redirect('poolaccounts')
        else:
            return flask.render_template('poolaccount.html', form=form)
    else:
        form = formtype(obj=obj)
        return flask.render_template('poolaccount.html', form=form)


def get_uptime(rig_state):
    """
    :return: human readable uptime in form of '1d 12h' for longer period or '12m' for minutes
    """
    if not rig_state.rebooted:
        return '?'
    delta = datetime.datetime.now() - rig_state.rebooted
    days = delta.days
    hours = math.trunc(delta.seconds / 3600)
    minutes = math.trunc((delta.seconds - hours * 3600)/ 60)
    if days > 0:
        s = "%dd %dh" % (days, hours)
    elif hours > 0:
        s = "%dh %dm" % (hours,minutes)
    else:
        s = "%dm" % minutes
    return s


@mod.route('/rigs.json')
@login_required
def rigs_json():
    user = flask_login.current_user.user
    rigs = Rig.objects(user=user)
    data = []
    for rig in rigs:
        hashrate = []
        algo = rig.configuration_group.algo
        if rig.hashrate:
            for algorithm in algo.split("+"):
                if algorithm in rig.hashrate:
                    hashrate.append(compact_hashrate(rig.hashrate[algorithm], algorithm, return_as_string=True))
        profit_currency = rig.user.settings.profit_currency
        profit_btc = rig.get_current_profit_btc()
        rate = get_exchange_rate('BTC', profit_currency)
        profit = profit_btc * rate
        data.append({
            'name': rig.worker,
            'online': {
                'is_online': rig.is_online,
                'uptime': get_uptime(rig),
            },
            'uuid': rig.uuid,
            'rebooted': rig.rebooted,
            'hashrate': hashrate,
            'profit': '{} {}'.format(round_to_n(profit), profit_currency),
            'miner': {
                'is_run': rig.is_miner_run,
                'configuration_id': str(rig.configuration_group.id),
                'configuration_name': rig.configuration_group.name,
            },
            'temp': rig.cards_temp,
            'fan': rig.cards_fan,
            'comment': rig.comment,
            'info': 'longlong description',
        })
    return flask.jsonify({'data': data})


@mod.route('/rigs')
@login_required
def rigs():
    return flask.render_template("rigs.html")


@mod.route('/rig/<uuid>/start_benchmark.json', methods=["GET", "POST"])
@login_required
def rig_start_benchmark_json(uuid=None):
    try:
        user = flask_login.current_user.user
        rig = Rig.objects.get(uuid=uuid)
        assert_expr(rig.user == user)
        rig_managers.set_rig_manager(rig, rig_managers.BENCHMARK)
        return flask.jsonify({'message': "Benchmark started. It can takes 5-10 minutes to complete. You will see results of benchmark here in the table"})
    except:
        traceback.print_exc()
        logger.error("start_benchmark_json for {}.".format(uuid))
        return flask.jsonify({'error': "error while start benchmark"})


@mod.route('/rig/<uuid>/reboot.json', methods=["GET", "POST"])
@login_required
def rig_reboot_json(uuid=None):
    user = flask_login.current_user.user
    rig = Rig.objects.get(uuid=uuid)
    assert_expr(rig.user == user)
    rm = rig_managers.get_rig_manager_by_name(rig_managers.MANUAL)
    rm.reboot(rig)


@mod.route('/rig/<uuid>/profit_data.json', methods=["GET", "POST"])
@login_required
def rig_profit_data_json(uuid=None):
    user = flask_login.current_user.user
    result = []
    rig = Rig.objects.get(uuid=uuid)
    assert_expr(rig.user == user)
    algos = {}
    # get all supported algos from all miners
    for miner in MinerProgram.enabled(supported_pu=rig.pu, supported_os=rig.os):
        for algo in miner.algos:
            algos[algo] = 1
    for algo in algos:
        algorithms = algo.split('+')
        algorithm = algorithms[0]
        for currency in Currency.objects(algo=algorithm):
            row1 = {
                "currency": [],
                "hashrate": [],
                "net_hashrate": [],
                "reward": [],
                "rate": [],
                "profit_btc": [],
                "profit": None,
            }
            row1['currency'].append(currency.code)
            best_miner_code = None
            target_hashrate = {}
            if algo in rig.target_hashrate and True: # FORGOT SOMETHING!!!
                # we will find best miner for this algo
                max_hashrate = 0
                for miner_code, hashrate in rig.target_hashrate[algo].items():
                    # choosing by max hashrate on first algorithm (i.e. Ethash)
                    if algorithm in hashrate and hashrate[algorithm] > max_hashrate:
                        target_hashrate = hashrate
                        max_hashrate = hashrate[algorithm]
                        best_miner_code = miner_code
            if target_hashrate:
                h = target_hashrate[algorithms[0]]
                row1['hashrate'].append(compact_hashrate(h, algorithms[0], return_as_string=True))
            else:
                row1['hashrate'].append('Need benchmark')
            row1['net_hashrate'].append(
                compact_hashrate(currency.nethash, algorithms[0], compact_for='net', return_as_string=True))
            try:
                profit_first_currency = currency.calc_mining_profit(target_hashrate[currency.algo])
            except:
                profit_first_currency = None
            row1['reward'].append(round_to_n(profit_first_currency))
            rate = currency.get_median_btc_rate()
            row1['rate'].append(round_to_n(rate))
            if rate and profit_first_currency:
                profit_btc = rate * profit_first_currency
            else:
                profit_btc = None
            row1['profit_btc'].append(round_to_n(profit_btc))
            rate = get_exchange_rate('BTC', user.settings.profit_currency)
            if rate and profit_btc:
                profit_first_currency = rate * profit_btc
            else:
                profit_first_currency = None
            if len(algorithms) == 2: # dual
                for currency in Currency.objects(algo=algorithms[1]):
                    row2 = deepcopy(row1)
                    row2['currency'].append(currency.code)
                    if target_hashrate and algorithms[1] in target_hashrate:
                        h = target_hashrate[algorithms[1]]
                        row2['hashrate'].append(compact_hashrate(h, algorithms[1], return_as_string=True))
                    else:
                        row2['hashrate'].append('?')
                    row2['net_hashrate'].append(compact_hashrate(currency.nethash, algorithms[1], compact_for='net', return_as_string=True))
                    try:
                        profit = currency.calc_mining_profit(target_hashrate[currency.algo])
                    except:
                        profit = None
                    row2['reward'].append(round_to_n(profit))
                    rate = currency.get_median_btc_rate()
                    row2['rate'].append(round_to_n(rate))
                    if rate and profit:
                        profit_btc = rate * profit
                    else:
                        profit_btc = None
                    row2['profit_btc'].append(round_to_n(profit_btc))
                    rate = get_exchange_rate('BTC', user.settings.profit_currency)
                    if rate and profit_btc and profit_first_currency:
                        profit_total = rate * profit_btc + profit_first_currency
                    else:
                        profit_total = None
                    row2['profit'] = round_to_n(profit_total)
                    result.append(row2)
            else:
                row1['profit'] = round_to_n(profit_first_currency)
                result.append(row1)
    return flask.jsonify({'data': result})


@mod.route('/rig/<uuid>/info', methods=["GET", "POST"])
@login_required
def rig_info(uuid=None):
    user = flask_login.current_user.user
    rig = Rig.objects.get(uuid=uuid)
    assert_expr(rig.user == user)
    select_config = []
    for config in list_configurations_applicable_to_rig(rig):
        select_config.append({
            'name': config.name,
            'id': str(config.id),
            'current': rig.configuration_group.id == config.id,
        })

    all_algos = []
    miners = MinerProgram.objects(supported_pu=rig.pu, supported_os=rig.os)
    for miner in miners:
        # if applicable
        if not rig.os in miner.supported_os:
            continue
        if not rig.pu in miner.supported_pu:
            continue
        for algo in miner.algos:
            # we have 'Ethash+blake' - now get target hashrate for it
            target_hasrate = {}
            if rig.target_hashrate and algo in rig.target_hashrate and miner.code in rig.target_hashrate[algo]:
                target_hasrate = rig.target_hashrate[algo][miner.code]
            all_algos.append({'algo': algo, 'miner': miner, 'target_hashrate': target_hasrate})
    # for algo,target_hashrate in rig.target_hashrate.items():

    field_args = {
    }
    formtype = model_form(Rig, only=['worker', 'comment', 'os', 'pu'], field_args=field_args)
    form = formtype(obj=rig)

    if request.method == 'POST':
        form = formtype(request.form)
        if (form.validate()):
            form.populate_obj(rig)
            rig.save()

    return flask.render_template('rig.html', rig_data=rig, configs=select_config, form=form, algos=all_algos)


@mod.route('/rig/<uuid>/log')
@login_required
def rig_log(uuid):
    logs = logging_server.rigs_memory_log
    log = ''
    if uuid in logs.keys():
        log = "\n".join(logs[uuid])
    return log


@mod.route('/rig/<uuid>/set_config', methods=['GET', 'POST'])
@login_required
def rig_set_config(uuid):
    config_id = request.args.get('config')
    rig = Rig.objects.get(uuid=uuid)
    user = flask_login.current_user.user
    assert_expr(rig.user == user)
    config = ConfigurationGroup.objects.get(id=config_id)
    rig.configuration_group = config
    rig.save()
    from bestminer import task_manager
    task_manager.add_switch_miner_task(rig, config)
    return flask.redirect(url_for('.rig_info', uuid=uuid))
