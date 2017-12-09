# shell be first before any logger created
import threading

import os

import bestminer.logging_config

import json
from bestminer.monitoring import MonitoringManager
import flask
from flask_login import LoginManager, UserMixin

from bestminer.models import User


from bestminer.logging_server import LoggingServer

from flask import Flask
from flask_mail import Mail
from flask_mongoengine import MongoEngine

from bestminer.rig_manager import rig_managers
from bestminer.profit import ProfitManager
from bestminer import server_email, rig_manager, exchanges
from bestminer.task_manager import TaskManager

app = Flask(__name__)

# one of: production,testing,development



running_platform = os.getenv("BESTMINER_PLATFORM")

if running_platform:
    # load default platform specific settings
    app.config.from_object('settings_default.{}'.format(running_platform))
else:
    app.config.from_object('settings_default.base')

if os.path.isfile('settings.py'):
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
    profit_manager.update_currency_data_from_whattomine(json.load(open('coins1.json')))

rig_manager.distribute_all_rigs()

logging_server_o = LoggingServer()
logging_server_o.start()

monitoring = MonitoringManager()
monitoring.start()

# Start exchanges update
if app.config.get('BESTMINER_EXCHANGES_UPDATE_ONCE_AT_START'):
    # update in background
    updater = threading.Thread(target=exchanges.update_all_exchanges, name="update exchanges once")
    updater.start()

if app.config.get('BESTMINER_EXCHANGES_AUTOUPDATE'):
    # update in background
    exchanges.start_auto_update(app.config.get('BESTMINER_EXCHANGES_AUTOUPDATE_PERIOD'))

# REGISTER ALL VIEWS

import bestminer.mod_auth.views
import bestminer.mod_promosite.views
import bestminer.mod_user.views
import bestminer.mod_admin.views
import bestminer.api_client.api

@app.route("/")
def index():
    return flask.redirect('/static/promo/coming-soon.html')

app.register_blueprint(bestminer.mod_auth.views.mod, url_prefix='/auth')
app.register_blueprint(bestminer.mod_promosite.views.mod, url_prefix='/promo')
app.register_blueprint(bestminer.mod_user.views.mod, url_prefix='/user')
app.register_blueprint(bestminer.mod_admin.views.mod, url_prefix='/admin')
app.register_blueprint(bestminer.api_client.api.mod, url_prefix='/client')

import bestminer.initial_data

initial_data.initial_data()
if app.config.get('TESTING', False):
    initial_data.sample_data()


