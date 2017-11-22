import datetime

import math
from flask_mongoengine import MongoEngine

db = MongoEngine()

# we do net restric algorithms anymore
#ALGORITHMS = (
#    'Ethash', 'Equihash', 'SHA256', 'Scrypt', 'Blake', 'X11', 'Pascal', 'LBRY', 'X11Gost', 'CryptoNight', 'NeoScrypt')

# TODO: rename to PoolClass
POOLS_FAMILY = ('ethermine', 'flypool', 'openethpool', 'coinmine')
OS_TYPE = ['Windows', 'Linux']
GPU_RX_470 = 'amd_rx_470' # possible template is 'amd_rx_470_4g_samsung'
GPU_RX = 'amd_rx'
PU_TYPE = ['amd', 'nvidia', 'asic']

class Todo(db.Document):
    title = db.StringField(max_length=60)
    text = db.StringField()
    done = db.BooleanField(default=False)
    pub_date = db.DateTimeField(default=datetime.datetime.now)


class User(db.Document):
    name = db.StringField()
    email = db.StringField(unique=True)
    api_key = db.StringField(unique=True)
    target_currency = db.StringField(unique=True, max_length=10)
    def __unicode__(self):
        return self.name


class Currency(db.Document):
    code = db.StringField(max_length=20, unique=True)
    difficulty = db.FloatField()
    algo = db.StringField(max_length=50) # actually should be named 'algorithm' TODO: rename
    block_time = db.IntField()  # seconds
    nethash = db.IntField()
    def __unicode__(self):
        return self.code


class Pool(db.Document):
    name = db.StringField(max_length=100, unique=True)
    pool_family = db.StringField(max_length=30, choices=POOLS_FAMILY)
    info = db.StringField(max_length=1000)
    website = db.URLField()
    currency = db.ReferenceField(Currency)
    fee = db.FloatField()  # fee rate. For 1% == 0.01
    servers = db.ListField(db.StringField())
    server = db.StringField()  # server:port
    login = db.StringField(max_length=200)
    password = db.StringField(max_length=100)

    def __unicode__(self):
        return self.name

    def server_address(self):
        server, port = self.server.split(":")
        return server

    def server_port(self):
        server, port = self.server.split(":")
        return port


class MinerProgram(db.Document):
    name = db.StringField(max_length=200)  # human readable miner name
    code = db.StringField(max_length=100, unique=True)  # TODO: no need anymore.
    family = db.StringField(max_length=50)  # family has the same output handlers TODO: switch to miner_class + logger_name
    miner_class = db.StringField() # class name of this miner program
    logger_name = db.StringField() # logger from the client side using for this
    command_line = db.StringField(max_length=500)
    dir = db.StringField(max_length=200)
    win_exe = db.StringField(max_length=100)
    dir_linux = db.StringField(max_length=200)
    linux_bin = db.StringField(max_length=100)
    version = db.StringField()
    env = db.DictField(default={})
    algos = db.ListField(db.StringField(), required=True) # supported algos (not only currencies but also duals like 'Ethash+pascal')
    supported_os = db.ListField(db.StringField(choices=OS_TYPE), required=True)
    supported_pu = db.ListField(db.StringField(choices=PU_TYPE), required=True)

    def __unicode__(self):
        return self.name


class Exchange(db.Document):
    name = db.StringField(max_length=50, unique=True)
    website = db.StringField(max_length=200)

    def __unicode__(self):
        return self.name


class ConfigurationGroup(db.Document):
    name = db.StringField(max_length=100, required=True, verbose_name="Name")
    user = db.ReferenceField(User, required=True)
    miner_program = db.ReferenceField(MinerProgram, required=True, verbose_name="Miner")
    command_line = db.StringField()
    env = db.DictField(default={})
    currency = db.ReferenceField(Currency, required=True, verbose_name="Coin", radio=True)  # PERHAPS NOT NEED AS SOON AS POOL MINE ONLY ONE COIN
    pool = db.ReferenceField(Pool, required=True, verbose_name="Pool")
    pool_login = db.StringField(required=True, max_length=200)
    pool_password = db.StringField(max_length=50)
    exchange = db.ReferenceField(Exchange, required=True)
    wallet = db.StringField(required=True, max_length=200)
    is_dual = db.BooleanField(default=False)
    dual_currency = db.ReferenceField(Currency)
    dual_pool = db.ReferenceField(Pool)
    dual_pool_login = db.StringField(max_length=200)
    dual_pool_password = db.StringField(max_length=50)
    dual_exchange = db.ReferenceField(Exchange)
    dual_wallet = db.StringField(max_length=200)

    def __unicode__(self):
        return self.name

    def expand_command_line(self, rig):
        expand_vars = {}
        expand_vars["POOL_SERVER"] = self.pool.server_address()
        expand_vars["POOL_PORT"] = self.pool.server_port()
        expand_vars["POOL_ACCOUNT"] = self.pool_login
        expand_vars["POOL_PASSWORD"] = self.pool_password
        expand_vars["CURRENCY"] = self.currency.code
        if self.is_dual:
            expand_vars["DUAL_POOL_SERVER"] = self.dual_pool.server_address()
            expand_vars["DUAL_POOL_PORT"] = self.dual_pool.server_port()
            expand_vars["DUAL_POOL_ACCOUNT"] = self.dual_pool_login
            expand_vars["DUAL_POOL_PASSWORD"] = self.dual_pool_password
            expand_vars["DUAL_CURRENCY"] = self.dual_currency.code
        else:
            expand_vars["DUAL_POOL_SERVER"] = ''
            expand_vars["DUAL_POOL_PORT"] = ''
            expand_vars["DUAL_POOL_ACCOUNT"] = ''
            expand_vars["DUAL_POOL_PASSWORD"] = ''
            expand_vars["DUAL_CURRENCY"] = ''
        expand_vars["WORKER"] = rig.worker
        the_string = self.command_line
        for var, value in expand_vars.items():
            the_string = the_string.replace('%' + var + "%", value)
        return the_string



class ExchangeRate(db.Document):
    exchange = db.ReferenceField(Exchange, unique_with=["from_currency", "to_currency"])
    from_currency = db.ReferenceField(Currency)
    to_currency = db.ReferenceField(Currency)
    rate = db.FloatField()
    when = db.DateTimeField()


class ExchangeRateHistory(db.Document):
    exchange = db.ReferenceField(Exchange)
    from_currency = db.ReferenceField(Currency)
    to_currency = db.ReferenceField(Currency)
    rate = db.FloatField()
    when = db.DateTimeField()




class Rig(db.Document):
    uuid = db.UUIDField(required=True, binary=False, unique=True)
    worker = db.StringField(regex='^[a-zA-Z0-9_]+$', max_length=50)
    configuration_group = db.ReferenceField(ConfigurationGroup, required=True)
    os = db.StringField(choises=OS_TYPE, required=True)
    user = db.ReferenceField(User)
    comment = db.StringField(max_length=100)
    system_gpu_list = db.ListField(db.StringField(), default=[])

    def __unicode__(self):
        return self.worker

class RigState(db.Document):
    rig = db.ReferenceField(Rig)
    rebooted = db.DateTimeField()
    cards_temp = db.ListField(db.IntField(), default=list)
    cards_fan = db.ListField(db.IntField(), default=list)
    hashrate = db.DictField(default={})

