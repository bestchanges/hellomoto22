import datetime

from mongoengine import StringField, Document, BooleanField, DateTimeField, DecimalField, FloatField, URLField, \
    ReferenceField, ListField, DictField, UUIDField, IntField

# we do net restric algorithms anymore
# ALGORITHMS = (
#    'Ethash', 'Equihash', 'SHA256', 'Scrypt', 'Blake', 'X11', 'Pascal', 'LBRY', 'X11Gost', 'CryptoNight', 'NeoScrypt')

# TODO: no way. Switch to PoolManager
POOLS_FAMILY = ('ethermine', 'flypool', 'openethpool', 'coinmine', 'suprnova')
SUPPORTED_OS = ('Windows', 'Linux')
OS_TYPE = (('Windows', 'Windows'), ('Linux', 'Linux'))


GPU_RX_470 = 'amd_rx_470'  # possible template is 'amd_rx_470_4g_samsung'
GPU_RX = 'amd_rx'
PU_TYPE = (('amd', 'amd'),('nvidia', 'nvidia'))


# that's cause circular dependency
# MANAGERS = (
#     (rig_manager.AUTOPROFIT, rig_manager.AUTOPROFIT)
#     ,(rig_manager.BENCHMARK, rig_manager.BENCHMARK)
#     ,(rig_manager.MANUAL, rig_manager.MANUAL)
# )

class Todo(Document):
    title = StringField(max_length=60)
    text = StringField()
    done = BooleanField(default=False)
    pub_date = DateTimeField(default=datetime.datetime.now)


class Currency(Document):
    code = StringField(max_length=20, unique=True)
    difficulty = DecimalField()
    algo = StringField(max_length=50)  # actually should be named 'algorithm' TODO: rename
    block_time = FloatField()  # seconds
    block_reward = DecimalField()
    nethash = DecimalField()

    def __unicode__(self):
        return self.code


class User(Document):
    name = StringField()
    email = StringField(unique=True)
    api_key = StringField(unique=True, min_length=20, max_length=20)
    password = StringField(min_length=8)
    client_secret = StringField(required=True)
    target_currency = StringField(required=True)  # code of currency user want to see income

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.email

    def __unicode__(self):
        return self.name


class Pool(Document):
    name = StringField(max_length=100, unique=True)
    pool_family = StringField(max_length=30, choices=POOLS_FAMILY)
    info = StringField()
    website = URLField()
    currency = ReferenceField(Currency, required=True)
    fee = FloatField(required=True, default=0, min_value=0, max_value=1)  # fee rate. For 1% == 0.01
    servers = ListField(StringField(max_length=100, regex='[\w\.\-]+:\d+'))
    server = StringField(required=True, max_length=100, regex='[\w\.\-]+:\d+')  # server:port

    def __unicode__(self):
        return self.name

    def server_address(self):
        server, port = self.server.split(":")
        return server

    def server_port(self):
        server, port = self.server.split(":")
        return port


class MinerProgram(Document):
    name = StringField(max_length=200)  # human readable miner name
    code = StringField(max_length=100, unique=True)
    family = StringField(
        max_length=50)  # family has the same output handlers TODO: switch to miner_class + logger_name
    miner_class = StringField()  # class name of this miner program
    logger_name = StringField()  # logger from the client side using for this
    command_line = StringField(max_length=500)
    dir = StringField(max_length=200)
    win_exe = StringField(max_length=100)
    dir_linux = StringField(max_length=200)
    linux_bin = StringField(max_length=100)
    version = StringField()
    env = DictField(default={})
    # TODO: use String instead of List (because each algo has separate command line)
    # TODO: OR introduce Map 'algo' -> 'command'
    algos = ListField(StringField(),
                         required=True)  # supported algos (not only currencies but also duals like 'Ethash+pascal')
    supported_os = ListField(StringField(choices=OS_TYPE), required=True)
    supported_pu = ListField(StringField(choices=PU_TYPE), required=True)

    def __unicode__(self):
        return self.name


class Exchange(Document):
    name = StringField(max_length=50, unique=True)
    website = StringField(max_length=200)
    handler = StringField(max_length=200)  # subclass of Exchange

    def __unicode__(self):
        return self.name


class PoolAccount(Document):
    name = StringField(max_length=200)
    user = ReferenceField(User, required=True)
    pool = ReferenceField(Pool, required=True)
#    currency = ReferenceField(Currency, required=True, verbose_name="Currency", radio=True)  # PERHAPS NOT NEED AS SOON AS POOL MINE ONLY ONE COIN
    login = StringField(required=True, max_length=200, help_text="Login for pool connection")
    password = StringField(max_length=100)
    is_active = BooleanField(default=True)

    def __unicode__(self):
        return "PoolAccount: {}, login=".format(self.server, self.pool_login)


class ConfigurationGroup(Document):
    name = StringField(max_length=100, required=True, verbose_name="Name")
    user = ReferenceField(User, required=True)
    miner_program = ReferenceField(MinerProgram, required=True, verbose_name="Miner")
    # algo: for single currency has taken from currency algo, for dual concatenate using '+'
    # example: 'Ethash', 'Ethash+Blake'
    algo = StringField(required=True)
    command_line = StringField()
    env = DictField(default={})
    currency = ReferenceField(Currency, required=True, verbose_name="Coin",
                                 radio=True)  # PERHAPS NOT NEED AS SOON AS POOL MINE ONLY ONE COIN
    pool = ReferenceField(Pool, required=True, verbose_name="Pool")
    pool_login = StringField(required=True, max_length=200)
    pool_password = StringField(max_length=50)
    exchange = ReferenceField(Exchange)
    wallet = StringField(required=True, max_length=200)
    is_dual = BooleanField(default=False)
    dual_currency = ReferenceField(Currency)
    dual_pool = ReferenceField(Pool)
    dual_pool_login = StringField(max_length=200)
    dual_pool_password = StringField(max_length=50)
    dual_exchange = ReferenceField(Exchange)
    dual_wallet = StringField(max_length=200)

    def __unicode__(self):
        return self.name

    def expand_command_line(self, rig=None):
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
        if rig:
            expand_vars["WORKER"] = rig.worker
        else:
            expand_vars["WORKER"] = 'worker'
        command_line = self.command_line
        if not command_line:
            command_line = self.miner_program.command_line
        for var, value in expand_vars.items():
            command_line = command_line.replace('%' + var + "%", value)
        # do it twice because of %POOL_LOGIN% contains %WORKER%
        for var, value in expand_vars.items():
            command_line = command_line.replace('%' + var + "%", value)
        return command_line


class ExchangeRate(Document):
    exchange = ReferenceField(Exchange, unique_with=["from_currency", "to_currency"])
    from_currency = ReferenceField(Currency)
    to_currency = ReferenceField(Currency)
    rate = FloatField()
    when = DateTimeField()


class ExchangeRateHistory(Document):
    exchange = ReferenceField(Exchange)
    from_currency = ReferenceField(Currency)
    to_currency = ReferenceField(Currency)
    rate = FloatField()
    when = DateTimeField()


class Rig(Document):
    uuid = UUIDField(required=True, binary=False, unique=True)
    worker = StringField(regex='^[a-zA-Z0-9_]+$', max_length=50)
    configuration_group = ReferenceField(ConfigurationGroup, required=True)
    os = StringField(choices=OS_TYPE)
    pu = StringField(choices=PU_TYPE)
    user = ReferenceField(User)
    manager = StringField() # required=True, default='AutoProfitRigManager', choices=MANAGERS,
    comment = StringField(max_length=100)
    system_gpu_list = ListField(StringField(), default=[])
    rebooted = DateTimeField()
    cards_temp = ListField(IntField(), default=list)
    cards_fan = ListField(IntField(), default=list)
    hashrate = DictField(default={})
    target_hashrate = DictField(
        default={})  # miner_code: { 'Ethash+Blake': { 'Ethash': 23, 'Blake': 4456 },}, miner_code: { 'Ethash': { 'Ethash': 25 }
    is_online = BooleanField(default=False)
    last_online_at = DateTimeField()
    log_to_file = BooleanField(defaul=False) # TODO: implement filter in logging_server. Now logs all

    def __unicode__(self):
        return "rig '{}' (uuid={})".format(self.worker, self.uuid)

    def __eq__(self, other):
        return self.uuid.__eq__(other.uuid)

    def get_target_hashrate_for_algo_and_miner_code(self, algo, miner_code):
        if self.target_hashrate and algo in self.target_hashrate and miner_code in self.target_hashrate[algo]:
            return self.target_hashrate[algo][miner_code]

    def set_target_hashrate_for_algo_and_miner_code(self, algo, miner_code, hashrate):
        self.target_hashrate[algo][miner_code] = hashrate

