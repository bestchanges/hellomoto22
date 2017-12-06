import datetime
import logging

import flask
import math

import flask_login
from flask import request, render_template, Blueprint
from flask_login import login_required
from flask_mongoengine.wtf import model_form
from wtforms import validators

from bestminer import crypto_data, cryptonator, logging_server_o, task_manager, logging_server
from bestminer.distr import client_zip_windows_for_user
from bestminer.models import ConfigurationGroup, PoolAccount, Rig, MinerProgram
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


@mod.route('/config/', defaults={'id': None}, methods=["GET", "POST"])
@mod.route('/config/<id>', methods=["GET", "POST"])
@login_required
def config_edit(id=''):
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
        if form.validate():
            # do something
            form.populate_obj(config)
            config.save()
            return flask.redirect('configs')
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
            'currency': o.currency.code,
            'login': o.login,
            'server': o.server,
            'active': o.is_active,
        })
    return flask.jsonify({'data': data})


@mod.route('/poolaccount/', defaults={'id': None}, methods=["GET", "POST"])
@mod.route('/poolaccount/<id>', methods=["GET", "POST"])
@login_required
def poolaccount_edit(id=''):
    user = flask_login.current_user.user

    field_args = {
        'pool': {'allow_blank': True},
        'fee': {'validators': [validators.NumberRange(min=0, max=5)]}
    }
    formtype = model_form(PoolAccount, exclude=['user'], field_args=field_args)

    if id:
        obj = PoolAccount.objects.get_or_404(id=id)
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
    minutes = math.trunc(delta.seconds / 60)
    if days > 0 or hours > 0:
        s = "%dd %dh" % (days, hours)
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


@mod.route('/rig/<uuid>/set_config')
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
