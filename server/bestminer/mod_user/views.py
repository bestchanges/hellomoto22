import datetime
import logging
import math

import flask
import flask_login
from flask import request, render_template, Blueprint, url_for
from flask_login import login_required
from flask_mongoengine.wtf import model_form

from bestminer import crypto_data, cryptonator, task_manager, logging_server
from bestminer.dbq import list_supported_currencies
from bestminer.distr import client_zip_windows_for_user
from bestminer.models import ConfigurationGroup, PoolAccount, Rig, MinerProgram, Currency, UserSettings
from bestminer.server_commons import round_to_n

mod = Blueprint('user', __name__, template_folder='templates')

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
    formtype = model_form(UserSettings)
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
#        'dual_pool': {'allow_blank': True},
#        'dual_currency': {'allow_blank': True},
    }
    formtype = model_form(ConfigurationGroup, field_args=field_args, only=
    [
        'name', 'miner_program',
        'currency', 'pool_server', 'pool_login', 'pool_password',
        'dual_currency', 'dual_pool_server', 'dual_pool_login', 'dual_pool_password'
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


def get_profit(currency_code, hashrate):
    """
    return daily profit for given currency and hashrate
    :param currency_code: 'ETH' 'Nicehash-Ethash'
    :param hashrate: 141000000 (as hashers in second)
    :return:
    """
    try:
        profit = crypto_data.calc_profit(crypto_data.for_currency(currency_code), hashrate, 86400)
        return profit
    except Exception as e:
        logging.error("Exception get_profit: %s" % e)
        raise e


@mod.route('/rigs.json')
@login_required
def rig_list_json():
    user = flask_login.current_user.user
    rigs_state = Rig.objects(user=user)
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
            profit = get_profit(currency.code, rig.hashrate[currency.algo])
        dual_profit = 0
        if rig.configuration_group.is_dual:
            dual_currency = rig.configuration_group.dual_currency
            if dual_currency.algo in rig.hashrate:
                dual_profit = get_profit(currency.code, rig.hashrate[currency.algo])
        try:
            # try to convert to user target currency
            target_currency = rig.user.settings.profit_currency
            exchange_rate = cryptonator.get_exchange_rate(currency.code, target_currency)
            profit_target_currency = profit * exchange_rate
            if dual_profit:
                exchange_rate_dual = cryptonator.get_exchange_rate(dual_currency.code, target_currency)
                profit_target_currency = profit_target_currency + dual_profit * exchange_rate_dual
            profit_string = "%s %s" % (round_to_n(profit_target_currency, 2), target_currency)
        except:
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
                'configuration_id': str(rig.configuration_group.id),
                'configuration_name': rig.configuration_group.name,
            },
            'temp': rig_state.cards_temp,
            'fan': rig_state.cards_fan,
            'comment': rig.comment,
            'info': 'longlong description',
        })
    return flask.jsonify({'data': data})


@mod.route('/rigs')
@login_required
def rig_list():
    return flask.render_template("rigs.html")


@mod.route('/rig/<uuid>/info', methods=["GET", "POST"])
@login_required
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
    # TODO: SECURITY: check if it user's config
    rig = Rig.objects.get(uuid=uuid)
    config = ConfigurationGroup.objects.get(id=config_id)
    rig.configuration_group = config
    rig.save()
    task_manager.add_switch_miner_task(rig, config)
    return rig_info(uuid)
