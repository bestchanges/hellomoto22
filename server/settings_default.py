# If you want to override some of the settings
# overwrite in file 'settings.py' in server root
import socket


class base(object):
    DEBUG = False
    TESTING = False
    MONGODB_DB = 'testing'
    MONGODB_HOST = 'localhost'
    MONGODB_PORT = None
    MONGODB_USERNAME = None
    MONGODB_PASSWORD = None

    SECRET_KEY = 'secret_for_bestminer_dsfsj3wasd'

    # Flask-login
    # https://flask-login.readthedocs.io/en/latest/#flask_login.LoginManager
    SESSION_PROTECTION = 'basic'

    # mail settings
    # # DO NOT FORGET TO OVERRIDE in settings.py
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'set_in_settings'
    MAIL_PASSWORD = 'password?'
    MAIL_DEFAULT_SENDER = 'same_as_username'

    BESTMINER_UPDATE_WTM_DELAY = 600
    BESTMINER_UPDATE_WTM = False

    BESTMINER_EXCHANGES_AUTOUPDATE = False
    BESTMINER_EXCHANGES_AUTOUPDATE_PERIOD = 300
    BESTMINER_EXCHANGES_UPDATE_ONCE_AT_START = False


class development(base):
    DEBUG = True
    TESTING = True

    SECRET_KEY = 'development'
    BESTMINER_EXCHANGES_UPDATE_ONCE_AT_START = True


class production(base):
    DEBUG = False
    TESTING = False

    MONGODB_DB = 'bestminer'
    BESTMINER_UPDATE_WTM_DELAY = 300
    BESTMINER_UPDATE_WTM = True

    BESTMINER_EXCHANGES_AUTOUPDATE = True
    BESTMINER_EXCHANGES_AUTOUPDATE_PERIOD = 300

    SECRET_KEY = 'production_' + socket.getfqdn()


class testing(production):
    pass