# shell be first before any logger created
import threading

import os

import bestminer.logging_config
import json

# when you need to sleep() use exit_event.wait(seconds)
exit_event = threading.Event()

def quit(signo, _frame):
    print("Interrupted by %d, shutting down" % signo)
    exit_event.set()

# from https://stackoverflow.com/questions/5114292/break-interrupt-a-time-sleep-in-python
import signal
for sig in ('TERM', 'INT'):
    signal.signal(getattr(signal, 'SIG'+sig), quit)


from bestminer.distr import client_zip_windows_for_update
from bestminer.monitoring import MonitoringManager
import flask
from flask_login import LoginManager, UserMixin

from bestminer.models import User, Rig


from flask import Flask
from flask_mail import Mail
from flask_mongoengine import MongoEngine

from bestminer.profit import WTMManager
from bestminer import server_email, rig_manager, exchanges, client_api

app = Flask(__name__)

# one of: production,testing,development

running_platform = os.getenv("BESTMINER_PLATFORM")

app.config.BESTMINER_PLATFORM = running_platform

if running_platform:
    # load default platform specific settings
    app.config.from_object('settings_default.{}'.format(running_platform))
else:
    app.config.from_object('settings_default.base')

if os.path.isfile('settings.py'):
    app.config.from_object('settings')  # server's specific settings

###
# Start database migration (before any other database query)
###
from mongodb_migrations.cli import MigrationManager
migration_manager = MigrationManager()
migration_manager.config.mongo_database = app.config.get("MONGODB_DB")
migration_manager.config.mongo_host = app.config.get("MONGODB_HOST")
migration_manager.config.mongo_port = app.config.get("MONGODB_PORT")
# TODO: add mongo authentication config
migration_manager.run()

# TODO: if client/version.txt != zip_windows_for_update.version.txt
distr.client_zip_windows_for_update()
distr.client_zip_linux_for_update()
distr.miners_zip()

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

task_manager = client_api.TaskManager()

profit_manager = WTMManager(
    sleep_time=app.config.get('BESTMINER_UPDATE_WTM_DELAY', 500),
#    save_wtm_to_file='coins.json'
)
if app.config.get('BESTMINER_UPDATE_WTM', False):
    profit_manager.start()
else:
    profit_manager.update_currency_from_wtm(json.load(open('coins1.json')))

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

import bestminer.initial_data
initial_data.load_data(app.config.BESTMINER_PLATFORM)

# can do only after initial_data
rig_managers = bestminer.rig_manager.RigManagers()
rig_managers.distribute_all_rigs()
rig_managers.start_all()


# REGISTER ALL VIEWS

import bestminer.mod_auth.views
import bestminer.mod_promosite.views
import bestminer.mod_user.views
import bestminer.mod_admin.views
import bestminer.api_client.api

@app.route("/")
def index():
    return flask.redirect('http://www.bestminer.io')

@app.route("/stat")
def stat():
    stat_data = {
        'users': {
            'total': User.objects().count(),
            'online': len(Rig.objects(is_online=True).item_frequencies('user')),
        },
        'rigs': {
            'total': Rig.objects().count(),
            'online': Rig.objects(is_online=True).count(),
        },
    }
    return flask.jsonify(stat_data)

app.register_blueprint(bestminer.mod_auth.views.mod, url_prefix='/auth')
app.register_blueprint(bestminer.mod_promosite.views.mod, url_prefix='/promo')
app.register_blueprint(bestminer.mod_user.views.mod, url_prefix='/user')
app.register_blueprint(bestminer.mod_admin.views.mod, url_prefix='/admin')
app.register_blueprint(bestminer.api_client.api.mod, url_prefix='/client')

