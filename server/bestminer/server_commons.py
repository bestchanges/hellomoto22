import os
import random
import string


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
