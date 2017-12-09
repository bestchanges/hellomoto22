import datetime

from mongoengine import StringField, Document, BooleanField, DateTimeField, DecimalField, FloatField, URLField, \
    ReferenceField, ListField, DictField, UUIDField, IntField, EmbeddedDocument, EmbeddedDocumentField, \
    queryset_manager, LongField

# we do net restric algorithms anymore
# ALGORITHMS = (
#    'Ethash', 'Equihash', 'SHA256', 'Scrypt', 'Blake', 'X11', 'Pascal', 'LBRY', 'X11Gost', 'CryptoNight', 'NeoScrypt')

# TODO: no way. Switch to PoolManager
POOLS_FAMILY = ('ethermine', 'flypool', 'openethpool', 'coinmine', 'suprnova')
SUPPORTED_OS = ('Windows', 'Linux')
OS_TYPE = (('Windows', 'Windows'), ('Linux', 'Linux'))

GPU_RX_470 = 'amd_rx_470'  # possible template is 'amd_rx_470_4g_samsung'
GPU_RX = 'amd_rx'
PU_TYPE = (('amd', 'amd'), ('nvidia', 'nvidia'))


# that's cause circular dependency
# MANAGERS = (
#     (rig_manager.AUTOPROFIT, rig_manager.AUTOPROFIT)
#     ,(rig_manager.BENCHMARK, rig_manager.BENCHMARK)
#     ,(rig_manager.MANUAL, rig_manager.MANUAL)
# )


class Currency(Document):
    code = StringField(max_length=20, unique=True)
    difficulty = FloatField()
    algo = StringField(max_length=50)  # actually should be named 'algorithm' TODO: rename
    block_time = FloatField()  # seconds
    block_reward = FloatField()
    nethash = LongField()
    updated_at = DateTimeField()
    listed_in = ListField(StringField(), default=[]) # exchange_code from exchanges
    exchange_rates_btc = DictField(default={}) # exchange_code : data {'volume_24h': xx, 'rate': xx, 'updated': ... }

    def __unicode__(self):
        return self.code


# make 2 tuple such ugly staff because of bug in model_form
PROFIT_CURRENCIES = (
    ('USD', 'USD'),
    ('EUR', 'EUR'),
    ('RUR', 'RUR'),
    ('BTC', 'BTC'),
    ('ETH', 'ETH'),
    ('ZEC', 'ZEC'),
)


class UserSettings(EmbeddedDocument):
    profit_currency = StringField(choices=PROFIT_CURRENCIES, default='RUR', required=True)
    default_configuration_group = ReferenceField('ConfigurationGroup')


class User(Document):
    name = StringField()
    email = StringField(unique=True)
    api_key = StringField(unique=True, min_length=20, max_length=20)
    password = StringField(min_length=8)
    client_secret = StringField(required=True)
    target_currency = StringField()  # deprecated. user settings.profit_currency instead
    settings = EmbeddedDocumentField(UserSettings)

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
    name = StringField(max_length=100, unique_with='user')
    user = ReferenceField(User)  # if exist then this is user's specific pool
    pool_family = StringField(max_length=30, choices=POOLS_FAMILY)
    info = StringField()
    website = URLField()
    currency = ReferenceField(Currency, required=True)
    fee = FloatField(required=True, default=0, min_value=0, max_value=1)  # fee rate. For 1% == 0.01
    servers = ListField(StringField(max_length=100, regex='[\w\.\-]+:\d+'))
    server = StringField(required=True, max_length=100, regex='[\w\.\-]+:\d+')  # server:port
    is_online = BooleanField(default=True)

    def __unicode__(self):
        return self.name


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
    is_enabled = BooleanField(default=True)

    @queryset_manager
    def enabled(doc_cls, queryset):
        return queryset.filter(is_enabled=True)

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
    name = StringField(max_length=100, required=True, verbose_name="Configuration Name")
    user = ReferenceField(User, required=True)
    miner_program = ReferenceField(MinerProgram, required=True, verbose_name="Miner")
    # algo: for single currency has taken from currency algo, for dual concatenate using '+'
    # example: 'Ethash', 'Ethash+Blake'
    algo = StringField(required=True)
    command_line = StringField()
    env = DictField(default={})
    currency = ReferenceField(Currency, required=True, verbose_name="Coin",
                              radio=True)  # PERHAPS NOT NEED AS SOON AS POOL MINE ONLY ONE COIN
    pool = ReferenceField(Pool, verbose_name="Pool")
    pool_server = StringField(required=True, max_length=100, regex='[\w\.\-]+:\d+',
                              verbose_name="Startum server")  # server:port
    pool_login = StringField(required=True, max_length=200, verbose_name="Pool login")
    pool_password = StringField(max_length=50, verbose_name="Pool password")
    exchange = ReferenceField(Exchange)
    wallet = StringField(max_length=200)
    is_dual = BooleanField(default=False)
    dual_currency = ReferenceField(Currency, verbose_name="Coin (dual)")
    dual_pool = ReferenceField(Pool)
    # so you thins regexp (...|) looks ugly? Complain to wtforms+mongoengine which trace '' as string value for field (instead of None)
    dual_pool_server = StringField(max_length=100, regex='([\w\.\-]+:\d+|)',
                                   verbose_name="Startum server (dual)")  # server:port
    dual_pool_login = StringField(max_length=200, verbose_name="Pool login")
    dual_pool_password = StringField(max_length=50, verbose_name="Pool password")
    dual_exchange = ReferenceField(Exchange)
    dual_wallet = StringField(max_length=200)
    is_active = BooleanField(default=True)

    @queryset_manager
    def active(doc_cls, queryset):
        return queryset.filter(is_active=True)

    def __unicode__(self):
        return self.name


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
    manager = StringField()  # required=True, default='AutoProfitRigManager', choices=MANAGERS,
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
    is_miner_run = BooleanField(default=False)
    log_to_file = BooleanField(defaul=False)  # TODO: implement filter in logging_server. Now logs all

    def __unicode__(self):
        return "rig '{}' (uuid={})".format(self.worker, self.uuid)

    def __eq__(self, other):
        return self.uuid.__eq__(other.uuid)

    def get_target_hashrate_for_algo_and_miner_code(self, algo, miner_code):
        if self.target_hashrate and algo in self.target_hashrate and miner_code in self.target_hashrate[algo]:
            return self.target_hashrate[algo][miner_code]

    def set_target_hashrate_for_algo_and_miner_code(self, algo, miner_code, hashrate):
        self.target_hashrate[algo][miner_code] = hashrate
