# global dict
global_rig_state = {}

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