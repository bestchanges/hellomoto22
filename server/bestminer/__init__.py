import logging.handlers

from flask_login import LoginManager, UserMixin

from bestminer.models import User

logging.basicConfig(
    format='%(asctime)-10s|%(name)-10s|%(levelname)s|%(message)s',
    level=logging.DEBUG
)
webserver_logger = logging.getLogger("werkzeug")
# TODO: add store logs to rotating file
webserver_logger.propagate = False
l = logging.getLogger('benchmark_manager')
h = logging.handlers.TimedRotatingFileHandler("log/benchmark_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)
l = logging.getLogger('logging_server')
h = logging.handlers.TimedRotatingFileHandler("log/logging_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

import flask

from bestminer.logging_server import LoggingServer

from flask import Flask
from flask_mail import Mail
from flask_mongoengine import MongoEngine

from bestminer.rig_manager import rig_managers
from bestminer.profit import ProfitManager
from bestminer import server_email, rig_manager
from bestminer.task_manager import TaskManager
from finik.crypto_data import CryptoDataProvider
from finik.cryptonator import Cryptonator

app = Flask(__name__)
app.config.from_object('settings_default')  # common default settings
app.config.from_object('settings')  # server's specific settings

db = MongoEngine()
db.init_app(app)

flask_mail = Mail(app)

class LoginUser(UserMixin):
    def __init__(self, user) -> None:
        self.user = user

    def get_id(self):
        return self.user.email


def load_user(user_id):
    users = User.objects(email=user_id)
    if len(users) == 1:
        return LoginUser(users[0])
    else:
        return None

login_manager = LoginManager(app=app)
login_manager.user_callback = load_user
login_manager.session_protection = "strong"
login_manager.login_view = '/auth/login'

task_manager = TaskManager()

crypto_data = CryptoDataProvider("coins1.json")
cryptonator = Cryptonator()


profit_manager = ProfitManager()
profit_manager.start()

rig_manager.distribute_all_rigs()

logging_server_o = LoggingServer()
logging_server_o.start()

# REGISTER ALL VIEWS

import bestminer.mod_auth.views
import bestminer.mod_promosite.views
import bestminer.mod_user.views
import bestminer.api_client.views

@app.route("/")
def index():
    return flask.render_template('index.html')

app.register_blueprint(bestminer.mod_auth.views.mod, url_prefix='/auth')
app.register_blueprint(bestminer.mod_promosite.views.mod, url_prefix='/promo')
app.register_blueprint(bestminer.mod_user.views.mod, url_prefix='/user')
app.register_blueprint(bestminer.api_client.views.mod, url_prefix='/client')

import bestminer.initial_data

initial_data.initial_data()
initial_data.sample_data()
initial_data.test_data()


