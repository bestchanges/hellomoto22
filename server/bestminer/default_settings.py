class Config(object):
    DEBUG = False
    TESTING = False
    MONGODB_SETTINGS = {'DB': 'testing'}
    SECRET_KEY= 'flask+mongoengine<=3'
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 465,
    MAIL_USE_SSL = True,
    MAIL_USERNAME = 'set_in_settings',
    MAIL_PASSWORD = 'password?'
    MAIL_DEFAULT_SENDER = 'same_as_username'

class ProductionConfig(Config):
    MONGODB_SETTINGS = {'DB': 'bestminer'}

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = True

class TestingConfig(Config):
    TESTING = True