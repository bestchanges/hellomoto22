import logging
import os
import random
import string

from bestminer.models import Currency
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
    vals = "{:.12f}".format(num).split('.')
    left = vals[0]
    if len(vals) > 1:
        right = vals[1]
    else:
        right = ""
    if len(left) > max_:
        return str(left) # if int part longer when max_ return only it
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


def expand_command_line(configuration_group, rig = None):
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
    if not rig:
        expand_vars["WORKER"] = 'worker'
        expand_vars["RIG_UUID"] = '00000000-0000-0000-0000-000000000000'
    else:
        expand_vars["WORKER"] = rig.worker
        expand_vars["RIG_UUID"] = str(rig.uuid)
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
    """
    return current exchange rate from currency to curreny.
    :param from_:
    :param to:
    :return: value or None if cannot be found
    """
    try:
        if to == 'BTC':
            found = Currency.objects(code=from_)
            if found:
                currency = found[0]
                return currency.get_median_btc_rate()
        return cryptonator.get_exchange_rate(from_, to)
    except:
        return None


def compact_hashrate(hashrate, algorithm, compact_for='rig', return_as_string=False):
    """
    Convetr value if hashrate to compact form: 123000000 -> 123 Mh/s
    :param hashrate:
    :param algorithm:
    :param compact_for: 'rig' or 'net' - there are different compact rules for them
    :param return_string:
    :return: tuple of value and units. If return_as_string return rounded string presentation
    """
    compact_maps = {
        'rig': {
            "CryptoNight": '',
            "Equihash": '',
            "Lyra2REv2": 'k',
            "NeoScrypt": 'k',
            "Blake (14r)": 'M',
            '__default__': 'M',
        },
        'net': {
            "CryptoNight": 'M',
            "Equihash": 'M',
            "Lyra2REv2": 'T',
            "NeoScrypt": 'G',
            "Blake (14r)": 'T',
            '__default__': 'G',
        },
    }
    algo_map = compact_maps[compact_for]
    mult_map = {
        '': 1,
        'k': 1e3,
        'M': 1e6,
        'G': 1e9,
        'T': 1e12,
        'P': 1e15,
    }
    if algorithm in algo_map:
        letter = algo_map[algorithm]
    else:
        letter = algo_map['__default__']
    value = hashrate / mult_map[letter]
    units = "{}h/s".format(letter)
    if return_as_string:
        return "{} {}".format(round_to_n(value), units)
    return value, units
