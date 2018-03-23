import logging
import os
import string
from _sha256 import sha256

import yaml

from bestminer import app
from bestminer.models import *
from bestminer.server_commons import assert_expr, gen_password

logger=logging.getLogger(__name__)

def decode_field(object, field_name, field_value):
    field = object._fields[field_name]
    if isinstance(field, ReferenceField):
        ref_object_type = field.document_type
        try:
            # object = ConfigurationGroup.objects(__raw__={'name': 'ETH+DCR'}).first()
            referenced_objects = ref_object_type.objects(__raw__=field_value)
            if len(referenced_objects) != 1:
                raise Exception(
                    "reference filed '{}' has query '{}'. Returned {} entries instead of expected 1".format(
                       field_name, field_value, len(referenced_objects)))
            setattr(object, field_name, referenced_objects[0])
        except Exception as e:
            raise Exception(
                "reference filed '{}' has query '{}'. During query raised exception: {}".format(
                    field_name, field_value, e))
    elif isinstance(field, EmbeddedDocumentField):
        embedded_object = field.document_type()
        for field, value in field_value.items():
            decode_field(embedded_object, field, value)
        setattr(object, field_name, embedded_object)
    else:
        setattr(object, field_name, field_value)


def load_documents_from_yaml(yaml_content, doc_class, primary_key_field):
    object_num = 0
    for data in yaml.load_all(yaml_content):
        object_num += 1
        # load existing object by provided primary key and it's value in data
        if not data or not data[primary_key_field]:
            raise Exception("For {}, entry #{}, primary key '{}' not definied: {}".format(doc_class._class_name, object_num, primary_key_field, data))
        try:
            objects = doc_class.objects(__raw__={primary_key_field: data[primary_key_field]})
        except Exception as e:
            raise Exception("For {}, entry #{}, {}".format(doc_class._class_name, object_num, e))
        if len(objects) > 1:
            raise Exception(
                "For {}, entry #{}, for primary key '{}' = '{}' was found {} entries instead of expected 1".format(
                    doc_class._class_name, object_num, primary_key_field, data[primary_key_field], len(objects)))
        if not objects:
            # create new instance
            object = doc_class()
        else:
            object = objects[0]
        # now fill all fields to values
        for field_name, field_value in data.items():
            try:
                decode_field(object, field_name, field_value)
            except Exception as e:
                raise Exception("For {}, entry #{}, {}".format(doc_class._class_name, object_num, e))
        logger.debug("Store {} '{}'".format(doc_class._class_name, data[primary_key_field]))
        object.save()


def load_initial_data_for_doc_class(filename_prefix, platform_type, doc_class, primary_key_field):
    directory = 'data'
    logger.info("Loading data for {}".format(doc_class._class_name))
    for suffix in ['_common', '_' + platform_type, '']:
        load_filename = filename_prefix + suffix + '.yaml'
        full_filename = os.path.join(directory, load_filename)
        if os.path.isfile(full_filename):
            logger.info("Parsing file {}".format(full_filename))
            file = open(full_filename, 'r')
            data = file.read()
            # TODO: catch exception and display message with filename and entry
            try:
                load_documents_from_yaml(data, doc_class, primary_key_field)
            except Exception as e:
                raise Exception("Exception during loading data from file '{}'. {}".format(load_filename, e))


def load_data(platform):
    """
    Refer to: https://github.com/bestchanges/hellomoto22/wiki/Inital-Data

    :param platform: one of 'development', 'testing', 'production'
    """

    load_initial_data_for_doc_class('currency', platform, Currency, 'code')
    load_initial_data_for_doc_class('miner_program', platform, MinerProgram, 'name')
    load_initial_data_for_doc_class('exchange', platform, Exchange, 'name')
    load_initial_data_for_doc_class('pool', platform, Pool, 'name')
    load_initial_data_for_doc_class('pool_account', platform, PoolAccount, 'name')
    load_initial_data_for_doc_class('configuration_group', platform, ConfigurationGroup, 'code')
    load_initial_data_for_doc_class('user', platform, User, 'name')


def test_data_for_user(user):
    mp_pc = MinerProgram.objects.get(code="pseudo_claymore_miner")
    eth = Currency.objects.get(code="ETH")
    dcr = Currency.objects.get(code="DCR")
    cg = ConfigurationGroup()
    cg.name="Test ETH+DCR"
    cg.user = user
    cg.currency = eth
    cg.miner_program = mp_pc
    cg.algo = "+".join([eth.algo, dcr.algo])
    cg.command_line=mp_pc.command_line
    cg.env=mp_pc.env
    cg.pool_server = 'eu1.ethermine.org:4444'
    cg.pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974"
    cg.pool_password = "x"
    cg.wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974"
    cg.is_dual = True
    cg.dual_currency = dcr
    cg.dual_pool_server='dcr.coinmine.pl:2222'
    cg.dual_pool_login = "egoaga19"
    cg.dual_pool_password = "x"
    cg.dual_wallet = "DsZAfQcte7c6xKoaVyva2YpNycLh2Kzc8Hq"
    cg.save()

    user.settings.default_configuration_group = cg
    user.save()


    cg = ConfigurationGroup()
    cg.name="Test ETH"
    cg.user=user
    cg.currency = eth
    cg.miner_program=mp_pc
    cg.algo = eth.algo
    cg.command_line=mp_pc.command_line
    cg.env=mp_pc.env
    cg.pool_server = 'eu1.ethermine.org:4444'
    cg.pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974"
    cg.is_dual = False
    cg.save()

    mp_pe = MinerProgram.objects.get(code="pseudo_ewbf_miner")
    zec = Currency.objects.get(code="ZEC")
    cg = ConfigurationGroup()
    cg.name="Test ZEC"
    cg.user = user
    cg.miner_program = mp_pe
    cg.algo= zec.algo
    cg.command_line=mp_pe.command_line
    cg.env=mp_pe.env
    cg.currency = zec
    cg.pool_server = 'eu1-zcash.flypool.org:3333'
    cg.pool_login = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q"
    cg.is_dual = False
    cg.save()



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
    eth = Currency.objects.get(code="ETH")
    dcr = Currency.objects.get(code="DCR")
    zec = Currency.objects.get(code="ZEC")
    
    mp_cd = MinerProgram.objects.get(code="claymore_dual")
    cg = ConfigurationGroup()
    cg.name="ETH+DCR"
    cg.user = user
    cg.command_line = mp_cd.command_line
    cg.currency = eth
    cg.miner_program = mp_cd
    cg.algo = "+".join([eth.algo, dcr.algo])
    cg.pool_server='eu1.ethermine.org:4444'
    cg.pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974"
    cg.is_dual = True
    cg.dual_currency = dcr
    cg.dual_pool_server = 'dcr.coinmine.pl:2222'
    cg.dual_pool_login = "egoaga19.%WORKER%"
    cg.dual_pool_password = "x"
    cg.dual_wallet = "DsZAfQcte7c6xKoaVyva2YpNycLh2Kzc8Hq"
    cg.save()

    mp_c = MinerProgram.objects.get(code="claymore")
    cg = ConfigurationGroup()
    cg.name="ETH"
    cg.user=user
    cg.miner_program=mp_c
    cg.algo = "+".join([eth.algo])
    cg.command_line = mp_c.command_line
    cg.env = mp_c.env
    cg.currency = eth
    cg.pool_server = 'eu1.ethermine.org:4444'
    cg.pool_login = "0x397b4b2fa22b8154ad6a92a53913d10186170974.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "0x397b4b2fa22b8154ad6a92a53913d10186170974"
    cg.is_dual = False
    cg.save()

    user.settings.default_configuration_group = cg
    user.save()

    # ZEC
    mp_e = MinerProgram.objects.get(code="ewbf")
    cg = ConfigurationGroup()
    cg.name="ZEC(nvidia)"
    cg.user=user
    cg.miner_program=mp_e
    cg.algo = "+".join([zec.algo])
    cg.command_line = mp_e.command_line
    cg.env = mp_e.env
    cg.currency = zec
    cg.pool_server = 'eu1-zcash.flypool.org:3333'
    cg.pool_login = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q"
    cg.is_dual = False
    cg.save()

    mp_e = MinerProgram.objects.get(code="claymore_zcash_amd")
    cg = ConfigurationGroup()
    cg.name="ZEC(amd)"
    cg.user=user
    cg.miner_program=mp_e
    cg.algo = "+".join([zec.algo])
    cg.command_line = mp_e.command_line
    cg.env = mp_e.env
    cg.currency = zec
    cg.pool_server = 'eu1-zcash.flypool.org:3333'
    cg.pool_login = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.%WORKER%"
    cg.pool_password = "x"
    cg.wallet = "t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q"
    cg.is_dual = False
    cg.save()

    if app.config.get("TESTING"):
        test_data_for_user(user)
