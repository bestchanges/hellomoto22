import logging
import os
import random
import string

from bestminer import crypto_data
from bestminer.models import ConfigurationGroup
from bestminer.profit import calc_mining_profit
from finik.cryptonator import Cryptonator

logger = logging.getLogger(__name__)
cryptonator = Cryptonator()


def round_to_n(num, max_=2):
    '''
    round to the not more that max_ value digits after comma. (0.00034)
    But if int part > 0 then just N digits after comma (360.00)
    с точностью не более n "значащих цифр", после запятой.
    '''
    if not num:
        return num
    vals = str(num).split('.')
    left = vals[0]
    if len(vals) > 1:
        right = vals[1]
    else:
        right = ""
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

def get_client_version():
    '''
    returns client version stored in ../client/version.txt
    :param dir:
    :return:
    '''
    version_filename = os.path.join('..', 'client', 'version.txt')
    file = open(version_filename, 'r', encoding='ascii')
    return file.readline().strip()


def assert_expr(expr, msg=None):
    '''
    check if expr is True.
    :param expr:
    :param msg: If expr False raise Exception with this message
    :return:
    '''
    if not expr:
        if not msg:
            msg = "Assert failed"
        raise Exception(msg)


def server_address(server):
    """
    return server part of servername "servername:8888" => "servername"
    :param server:
    :return:
    """
    server, port = server.split(":")
    return server


def server_port(server):
    """
    return port part of servername "servername:8888" => "8888"
    :param server:
    :return:
    """
    server, port = server.split(":")
    return port


def gen_password(min_len=8, max_len=10, chars=string.ascii_lowercase + string.digits):
    size = random.randint(min_len, max_len)
    return ''.join(random.choice(chars) for x in range(size))


def expand_command_line(configuration_group, worker='worker'):
    expand_vars = {}
    if configuration_group.pool_server:
        expand_vars["POOL_SERVER"] = server_address(configuration_group.pool_server)
        expand_vars["POOL_PORT"] = server_port(configuration_group.pool_server)
    else:
        expand_vars["POOL_SERVER"] = server_address(configuration_group.pool.server)
        expand_vars["POOL_PORT"] = server_port(configuration_group.pool.server)
    expand_vars["POOL_ACCOUNT"] = configuration_group.pool_login
    expand_vars["POOL_PASSWORD"] = configuration_group.pool_password
    expand_vars["CURRENCY"] = configuration_group.currency.code
    if configuration_group.is_dual:
        if configuration_group.dual_pool_server:
            expand_vars["DUAL_POOL_SERVER"] = server_address(configuration_group.dual_pool_server)
            expand_vars["DUAL_POOL_PORT"] = server_port(configuration_group.dual_pool_server)
        else:
            expand_vars["DUAL_POOL_SERVER"] = server_address(configuration_group.dual_pool.server)
            expand_vars["DUAL_POOL_PORT"] = server_port(configuration_group.dual_pool.server)
        expand_vars["DUAL_POOL_ACCOUNT"] = configuration_group.dual_pool_login
        expand_vars["DUAL_POOL_PASSWORD"] = configuration_group.dual_pool_password
        expand_vars["DUAL_CURRENCY"] = configuration_group.dual_currency.code
    else:
        expand_vars["DUAL_POOL_SERVER"] = ''
        expand_vars["DUAL_POOL_PORT"] = ''
        expand_vars["DUAL_POOL_ACCOUNT"] = ''
        expand_vars["DUAL_POOL_PASSWORD"] = ''
        expand_vars["DUAL_CURRENCY"] = ''
    expand_vars["WORKER"] = worker
    command_line = configuration_group.command_line
    if not command_line:
        command_line = configuration_group.miner_program.command_line
    for var, value in expand_vars.items():
        command_line = command_line.replace('%' + var + "%", value)
    # do it twice because of %POOL_LOGIN% contains %WORKER%
    for var, value in expand_vars.items():
        command_line = command_line.replace('%' + var + "%", value)
    return command_line


def get_exchange_rate(from_, to):
    try:
        return cryptonator.get_exchange_rate(from_, to)
    except:
        return None


def calculate_profit_converted(rig, target_currency):
    """
    calculate current profit for given rig. Convert profit to given currency.
    :param rig:
    :param target_currency: currency code which convert to: 'USD', 'RUR', 'BTC'
    :return: value of profit in given currency or None in case if cannot convert
    """
    currency = rig.configuration_group.currency
    profit = 0
    if currency.algo in rig.hashrate:
        profit = calc_mining_profit(currency, rig.hashrate[currency.algo])
    dual_profit = 0
    if rig.configuration_group.is_dual:
        dual_currency = rig.configuration_group.dual_currency
        if dual_currency.algo in rig.hashrate:
            dual_profit = calc_mining_profit(currency, rig.hashrate[currency.algo])
    try:
        exchange_rate = cryptonator.get_exchange_rate(currency.code, target_currency)
        profit_target_currency = profit * exchange_rate
        if dual_profit:
            exchange_rate_dual = cryptonator.get_exchange_rate(dual_currency.code, target_currency)
            profit_target_currency = profit_target_currency + dual_profit * exchange_rate_dual
        return profit_target_currency
    except:
        logger.error("Error calculate_current_profit to {} for rig={}".format(target_currency, rig))
        return None


def get_profit(currency_code, hashrate):
    """
    return daily profit for given currency and hashrate
    !!!! deprecated use calc_mining_profit()
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

# TODO: move as query to ConfigurationGroup ?
def list_configurations_applicable_to_rig(rig):
    configs = ConfigurationGroup.objects(user=rig.user, )
    select_config = []
    for config in configs:
        if rig.pu not in config.miner_program.supported_pu:
            continue
        if rig.os not in config.miner_program.supported_os:
            continue
        select_config.append(config)
    return select_config
