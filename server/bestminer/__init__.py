import logging.handlers

logging.basicConfig(format='%(asctime)-10s|%(name)-10s|%(levelname)s|%(message)s', level=logging.DEBUG)

l = logging.getLogger("bestminer")
l.setLevel(logging.DEBUG)

l = logging.getLogger("werkzeug")
h = logging.handlers.TimedRotatingFileHandler("log/web_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.propagate = False

l = logging.getLogger('bestminer.rig_manager')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/rig_manager.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

l = logging.getLogger('bestminer.benchmark_manager')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/benchmark_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

l = logging.getLogger('bestminer.logging_server')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/logging_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

from bestminer.monitoring import MonitoringManager
import flask
from flask_login import LoginManager, UserMixin

from bestminer.models import User


from bestminer.logging_server import LoggingServer

from flask import Flask
from flask_mail import Mail
from flask_mongoengine import MongoEngine, json

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

profit_manager = ProfitManager(
    sleep_time=app.config.get('BESTMINER_UPDATE_WTM_DELAY', 500),
    save_wtm_to_file='coins.json'
)
if app.config.get('BESTMINER_UPDATE_WTM', False):
    profit_manager.start()
else:
    profit_manager.update_currency_data_from_whattomine(json.load(open('coins.json')))

crypto_data = CryptoDataProvider("coins.json")
cryptonator = Cryptonator()

rig_manager.distribute_all_rigs()

logging_server_o = LoggingServer()
logging_server_o.start()

monitoring = MonitoringManager()
monitoring.start()

# REGISTER ALL VIEWS

import bestminer.mod_auth.views
import bestminer.mod_promosite.views
import bestminer.mod_user.views
import bestminer.mod_admin.views
import bestminer.api_client.api

@app.route("/")
def index():
    return flask.render_template('index.html')

app.register_blueprint(bestminer.mod_auth.views.mod, url_prefix='/auth')
app.register_blueprint(bestminer.mod_promosite.views.mod, url_prefix='/promo')
app.register_blueprint(bestminer.mod_user.views.mod, url_prefix='/user')
app.register_blueprint(bestminer.mod_admin.views.mod, url_prefix='/admin')
app.register_blueprint(bestminer.api_client.api.mod, url_prefix='/client')

import bestminer.initial_data

initial_data.initial_data()
initial_data.sample_data()
initial_data.test_data()


