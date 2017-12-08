import json
import logging
import string
from _sha256 import sha256

from bestminer import profit_manager, app
from bestminer.models import *
from bestminer.server_commons import assert_expr, gen_password

logger=logging.getLogger(__name__)

DEFAULT_MINER_ENV = {
    'GPU_MAX_HEAP_SIZE': '100',
    'GPU_USE_SYNC_OBJECTS': '1',
    'GPU_MAX_ALLOC_PERCENT': '100',
    'GPU_SINGLE_ALLOC_PERCENT': '100',
}

def initial_data():
    # let's create static data according with GET_OR_CREATE technique as in https://stackoverflow.com/questions/8447502/how-to-do-insert-if-not-exist-else-update-with-mongoengine
    profit_manager.update_currency_data_from_whattomine(json.load(open('coins1.json', 'r')))
    Currency.objects(code="BTC").update_one(algo='SHA256', upsert=True)
    Currency.objects(code="BCC").update_one(algo='SHA256', upsert=True)

    Exchange.objects(name="Poloniex").update_one(handler='PoloniexExchange', upsert=True)

    miner_program = MinerProgram.objects(name='Claymore Dual').modify(
        upsert=True,
        set__family = 'claymore',
        set__code = 'claymore_dual',
        set__dir = 'claymore10_win',
        set__win_exe = 'EthDcrMiner64.exe',
        set__dir_linux = 'claymore10_linux',
        set__linux_bin = 'ethdcrminer64',
        set__command_line = '-epool %POOL_SERVER%:%POOL_PORT% -ewal %POOL_ACCOUNT% -psw %POOL_PASSWORD% -r 1 -dbg 0 -logfile log_noappend.txt -mport 3333 -retrydelay 3 -mode 0 -erate 1 -estale 0 -dpool %DUAL_POOL_SERVER%:%DUAL_POOL_PORT% -dwal %DUAL_POOL_ACCOUNT% -dpsw %DUAL_POOL_PASSWORD% -ftime 10 -dcri 26 -asm 1',
        set__env = DEFAULT_MINER_ENV,
        set__algos = ['Ethash+Blake (14r)',],
        set__supported_os = ['Windows', 'Linux'],
        set__supported_pu = ['nvidia', 'amd'],
        set__is_enabled=True,
    )

    miner_program = MinerProgram.objects(name='Claymore').modify(
        upsert=True,
        set__family = 'claymore',
        set__code = 'claymore',
        set__dir = 'claymore10_win',
        set__win_exe = 'EthDcrMiner64.exe',
        set__dir_linux = 'claymore10_linux',
        set__linux_bin = 'ethdcrminer64',
        set__command_line = '-epool %POOL_SERVER%:%POOL_PORT% -ewal %POOL_ACCOUNT% -psw %POOL_PASSWORD% -r 1 -dbg 0 -logfile log_noappend.txt -mport 3333 -retrydelay 3 -mode 1 -erate 1 -estale 0 -ftime 10 -asm 1',
        set__env=DEFAULT_MINER_ENV,
        set__algos=['Ethash', ],
        set__supported_os = ['Windows', 'Linux'],
        set__supported_pu=['nvidia', 'amd'],
        set__is_enabled=True,
    )

    miner_program = MinerProgram.objects(name='Claymore Zcash AMD').modify(
        upsert=True,
        set__family = 'claymore',
        set__code = 'claymore_zcash_amd',
        set__dir = 'claymore_zcash_amd',
        set__win_exe = 'ZecMiner64.exe',
        set__dir_linux = 'claymore_zcash_amd_linux',
        set__linux_bin = 'ethdcrminer64',
        set__command_line = '-zpool %POOL_SERVER%:%POOL_PORT% -zwal %POOL_ACCOUNT% -zpsw %POOL_PASSWORD% -allpools 1 -r 1 -dbg 0 -logfile log_noappend.txt -mport 3333 -retrydelay 3 -ftime 30 -asm 1 -tstop 85 -i 7',
        set__env=DEFAULT_MINER_ENV,
        set__algos=['Equihash', ],
        set__supported_os = ['Windows'], # TODO: add linux later
        set__supported_pu=['amd'],
        set__is_enabled=True,
    )

    miner_program = MinerProgram.objects(name='EWBF').modify(
        upsert=True,
        set__family = 'ewbf',
        set__code = 'ewbf',
        set__dir = 'ewbf_win',
        set__win_exe = 'miner.exe',
        set__dir_linux = 'ewbf_linux',
        set__linux_bin = 'miner',
        set__command_line = '--server %POOL_SERVER% --port %POOL_PORT% --user %POOL_ACCOUNT% --log 2 --pass %POOL_PASSWORD% --eexit 3 --fee 0.5',
        set__env=DEFAULT_MINER_ENV,
        set__algos=['Equihash', ],
        set__supported_os=['Windows', 'Linux'],
        set__supported_pu = ['nvidia', ],
        set__is_enabled=True,
    )

    poloniex = Exchange.objects(name="Poloniex").modify(
        upsert=True,
        set__name="Poloniex"
    )


    pool = Pool.objects(name="Ethermine").modify(
        upsert=True,
    	set__pool_family = "ethermine",
    	set__info = "",
    	set__website = "https://ethermine.org",
    	set__currency = Currency.objects.get(code="ETH"),
    	set__fee = 0.01,
    	set__servers = ['us1.ethermine.org:4444', 'us1.ethermine.org:14444', 'eu1.ethermine.org:4444',
                    'eu1.ethermine.org:14444'],
    	set__server = 'eu1.ethermine.org:4444',
    )

    pool = Pool.objects(name="ZEN suprnova").modify(
        upsert=True,
    	set__pool_family = "suprnova",
    	set__info = "",
    	set__website = "https://zen.suprnova.cc",
    	set__currency = Currency.objects.get(code="ZEN"),
    	set__fee = 0.01,
    	set__servers = ['zen.suprnova.cc:3618'],
    	set__server = 'zen.suprnova.cc:3618',
    )

    pool = Pool.objects(name="BTG suprnova").modify(
        upsert=True,
    	set__pool_family = "suprnova",
    	set__info = "",
    	set__website = "https://btg.suprnova.cc",
    	set__currency = Currency.objects.get(code="BTG"),
    	set__fee = 0.01,
    	set__servers = ['btg.suprnova.cc:8816'],
    	set__server = 'btg.suprnova.cc:8816',
    )

    pool = Pool.objects(name= "FlyPool").modify(
        upsert=True,
        set__pool_family = "ethermine",
    	set__info = "Zcash 	pool",
    	set__website = "http://zcash.flypool.org",
    	set__currency = Currency.objects.get(code="ZEC"),
    	set__fee = 0.01,
    	set__servers = ['asia1-zcash.flypool.org:3333', 'eu1-zcash.flypool.org:3333', 'eu1-zcash.flypool.org:13333'],
    	set__server = 'eu1-zcash.flypool.org:3333',
    )

    pool = Pool.objects(name="Decred Coinmine").modify(
        upsert = True,
        set__pool_family = "coinmine",
        set__info = "",
        set__website = "https://www2.coinmine.pl/dcr/index.php?page=statistics&action=pool",
        set__currency = Currency.objects.get(code="DCR"),
        set__fee = 0.01,
        set__servers = ['dcr.coinmine.pl:2222', 'dcr-eu.coinmine.pl:2222', 'dcr-us.coinmine.pl:2222',
                'dcr-as.coinmine.pl:2222'],
        set__server = 'dcr.coinmine.pl:2222',
    )




def test_data_for_user(user):
    miner_program = MinerProgram.objects(name='Pseudo Claymore Miner').modify(
        upsert=True,
        set__family = 'claymore',
        set__code = 'pseudo_claymore_miner',
        set__dir = 'miner_emu',
        set__win_exe = 'python',
        set__dir_linux = 'miner_emu',
        set__linux_bin = 'python',
        set__command_line = '-u miner_emu.py --file %CURRENCY%%DUAL_CURRENCY%.txt --dst_file log_noappend.txt --delay 0.3 ',
        set__env=DEFAULT_MINER_ENV,
        set__algos=['Ethash+Blake (14r)', 'Ethash'],
        set__supported_os=['Windows', 'Linux'],
        set__supported_pu=['nvidia', 'amd'],
        set__is_enabled=True,
    )

    miner_program = MinerProgram.objects(name='Pseudo EWBF Miner').modify(
        upsert=True,
        set__family = 'ewbf',
        set__code = 'pseudo_ewbf_miner',
        set__dir = 'miner_emu',
        set__win_exe = 'python',
        set__dir_linux = 'miner_emu',
        set__linux_bin = 'python',
        set__command_line = '-u miner_emu.py --file %CURRENCY%%DUAL_CURRENCY%.txt --dst_file miner.log --delay 0.5 ',
        set__env=DEFAULT_MINER_ENV,
        set__algos=['Equihash', ],
        set__supported_os=['Windows', 'Linux'],
        set__supported_pu=['nvidia', ],
        set__is_enabled=True,
    )


    mp_pc = MinerProgram.objects.get(code="pseudo_claymore_miner")
    eth = Currency.objects.get(code="ETH")
    dcr = Currency.objects.get(code="DCR")
    cg = ConfigurationGroup.objects(name="Test ETH+DCR").modify(
        upsert=True,
        set__user = user,
    	set__currency = eth,
    	set__miner_program = mp_pc,
        set__algo = "+".join([eth.algo, dcr.algo]),
        set__command_line=mp_pc.command_line,
        set__env=mp_pc.env,
        set__pool_server = 'eu1.ethermine.org:4444',
    	set__pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974",
    	set__pool_password = "x",
    	set__wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974",
    	set__is_dual = True,
    	set__dual_currency = dcr,
        set__dual_pool_server='dcr.coinmine.pl:2222',
    	set__dual_pool_login = "egoaga19",
    	set__dual_pool_password = "x",
    	set__dual_wallet = "DsZAfQcte7c6xKoaVyva2YpNycLh2Kzc8Hq",
    )
    user.settings.default_configuration_group = cg
    user.save()


    cg = ConfigurationGroup.objects(name="Test ETH").modify(
        upsert=True,
        set__user=user,
        set__currency = eth,
        set__miner_program=mp_pc,
        set__algo = eth.algo,
        set__command_line=mp_pc.command_line,
        set__env=mp_pc.env,
        set__pool_server = 'eu1.ethermine.org:4444',
    	set__pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%",
    	set__pool_password = "x",
    	set__wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974",
    	set__is_dual = False,
    )

    mp_pe = MinerProgram.objects.get(code="pseudo_ewbf_miner")
    zec = Currency.objects.get(code="ZEC")
    cg = ConfigurationGroup.objects(name="Test ZEC").modify(
        upsert=True,
        set__user = user,
        set__miner_program = mp_pe,
        set__algo= zec.algo,
        set__command_line=mp_pe.command_line,
        set__env=mp_pe.env,
        set__currency = zec,
        set__pool_server = 'eu1-zcash.flypool.org:3333',
    	set__pool_login = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.%WORKER%",
    	set__pool_password = "x",
    	set__wallet = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q",
    	set__is_dual = False,
    )





def sample_data():
    email = 'egor.fedorov@gmail.com'
    if not User.objects(email=email):
        user, password = create_user(email, password='123')
        logger.debug("Created sample user {} with password {}".format(user, password))


def create_user(email, name=None, password=None, settings=None):
    """

    :param email:
    :param name:
    :param password:
    :param settings: instance of UserSettings model
    :return: tuple user,user_password
    """
    assert_expr(email, "email required")
    if not name:
        name = 'user ' + email

    if not password:
        password = gen_password(8, 10)
    user = User()
    user.email = email
    user.name = name
    user.password = sha256(password.encode('utf-8')).hexdigest()
    user.client_secret = gen_password(6, 6)
    user.api_key = gen_password(20, 20, chars=string.ascii_uppercase + string.digits)
    if not settings:
        settings = UserSettings()
    user.settings = settings
    user.save()
    create_initial_objects_for_user(user)
    return user, password


def create_initial_objects_for_user(user):
    """
    Create default configuration_groups for given user.
    Set the first one as default user config group
    :param user:
    :return:
    """
    mp_cd = MinerProgram.objects.get(code="claymore_dual")
    eth = Currency.objects.get(code="ETH")
    dcr = Currency.objects.get(code="DCR")
    zec = Currency.objects.get(code="ZEC")
    cg = ConfigurationGroup.objects(name="ETH+DCR").modify(
        upsert=True,
        set__user = user,
        set__command_line = mp_cd.command_line,
        set__currency = eth,
    	set__miner_program = mp_cd,
        set__algo = "+".join([eth.algo, dcr.algo]),
        set__pool_server='eu1.ethermine.org:4444',
        set__pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%",
    	set__pool_password = "x",
    	set__wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974",
    	set__is_dual = True,
    	set__dual_currency = dcr,
    	set__dual_pool_server = 'dcr.coinmine.pl:2222',
    	set__dual_pool_login = "egoaga19.%WORKER%",
    	set__dual_pool_password = "x",
    	set__dual_wallet = "DsZAfQcte7c6xKoaVyva2YpNycLh2Kzc8Hq",
    )
    user.settings.default_configuration_group = cg
    user.save()

    mp_c = MinerProgram.objects.get(code="claymore")
    cg = ConfigurationGroup.objects(name="ETH").modify(
        upsert=True,
        set__user=user,
        set__miner_program=mp_c,
        set__algo = "+".join([eth.algo]),
        set__command_line = mp_c.command_line,
        set__env = mp_c.env,
        set__currency = eth,
    	set__pool_server = 'eu1.ethermine.org:4444',
    	set__pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%",
    	set__pool_password = "x",
    	set__wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974",
    	set__is_dual = False,
    )

    mp_e = MinerProgram.objects.get(code="ewbf")
    cg = ConfigurationGroup.objects(name="ZEC(nvidia)").modify(
        upsert=True,
        set__user=user,
        set__miner_program=mp_e,
        set__algo = "+".join([zec.algo]),
        set__command_line = mp_e.command_line,
        set__env = mp_e.env,
        set__currency = zec,
    	set__pool_server = 'eu1-zcash.flypool.org:3333',
    	set__pool_login = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.%WORKER%",
    	set__pool_password = "x",
    	set__wallet = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q",
    	set__is_dual = False,
    )

    if app.config.get("TESTING"):
        test_data_for_user(user)
