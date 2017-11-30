import logging
import random
import string

import flask_login
from flask import request, url_for
from flask_login import LoginManager, login_required, login_user, UserMixin
from wtforms import validators
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField

import initial_data
import views
import flask

from logging_server import LoggingServer
from make_client_zip import client_zip_windows
from models import *
from profit_manager import pm

app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config['MONGODB_SETTINGS'] = {'DB': 'testing'}
app.config['TESTING'] = True
app.config['SECRET_KEY'] = 'flask+mongoengine<=3'
app.debug = False

logging.basicConfig(
    format='%(asctime)-10s|%(name)-10s|%(levelname)s|%(message)s',
    level=logging.INFO
)
webserver_logger = logging.getLogger("werkzeug")
# TODO: add store logs to rotating file
webserver_logger.propagate = False


#        format='%(relativeCreated)5d %(name)-15s %(levelname)-8s %(message)s')  # %(client_id)-15s


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


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.user_callback = load_user
login_manager.login_view = '/login'

@app.route("/settings")
@login_required
def settings():
    pass


def gen_password(min_len=8, max_len=10, chars = string.ascii_lowercase + string.digits):
  size = random.randint(min_len, max_len)
  return ''.join(random.choice(chars) for x in range(size))

@app.route('/register', methods=['GET', 'POST'])
def register():
    class RegisterForm(FlaskForm):
        email = StringField('Email', validators=[validators.DataRequired(), validators.Email()])
    form = RegisterForm()


    if request.method == 'POST' and form.validate():
        email = form.email.data.strip()
        email = email.lower()
        existing = User.objects(email=email)
        if existing:
            flask.flash('This email already registered')
            return login()

        user = User()
        user.email = email
        user.password = gen_password(8,10)
        user.client_secret = gen_password(6,6)
        user.api_key = gen_password(20,20, chars=string.ascii_uppercase + string.digits)
        user.target_currency = 'USD'
        user.save()

        flask.flash('Account registered. Your password: %s' % user.password)
        return login()
    return flask.render_template('register.html', form=form)


@app.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    flask.flash('You are logged out.')
    return flask.redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Here we use a class of some kind to represent and validate our
    # client-side form data. For example, WTForms is a library that will
    # handle this for us, and we use a custom LoginForm to validate.
    class LoginForm(FlaskForm):
        email = StringField('Email', validators=[validators.DataRequired(), validators.Email()])
        password = PasswordField('Password', validators=[validators.DataRequired()])
    form = LoginForm()

    if request.method == 'POST' and form.validate():
        # Login and validate the user.
        # user should be an instance of your `User` class
        user = User.objects.get(email=form.email.data)

        login_user(user, remember=True)

        flask.flash('Logged in successfully.')

        next = flask.request.args.get('next')
        # is_safe_url should check if the url is safe for redirects.
        # See http://flask.pocoo.org/snippets/62/ for an example.
        if False:  # not is_safe_url(next):
            return flask.abort(400)

        return flask.redirect(next or flask.url_for('index'))
    return flask.render_template('login.html', form=form)


db.init_app(app)

# prepare data for work
app.add_url_rule('/client/rig_config', view_func=views.client_config1, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat_and_task', view_func=views.recieve_stat_and_return_task, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat', view_func=views.receive_stat, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/task', view_func=views.send_task, methods=["GET", "POST", "PUT"])

app.add_url_rule('/promo', view_func=views.index)
app.add_url_rule('/', view_func=views.index)
app.add_url_rule('/rigs', view_func=views.rig_list)
app.add_url_rule('/rigs.json', view_func=views.rig_list_json)
app.add_url_rule('/rig/<uuid>/info', view_func=views.rig_info)
app.add_url_rule('/rig/<uuid>/log', view_func=views.rig_log)
app.add_url_rule('/rig/<uuid>/set_config', view_func=views.rig_set_config)

app.add_url_rule('/configs', view_func=views.config_list, methods=["GET", "POST"])
app.add_url_rule('/configs.json', view_func=views.config_list_json)
app.add_url_rule('/config/', view_func=views.config_edit, defaults={'id': None}, methods=["GET", "POST"])
app.add_url_rule('/config/<id>', view_func=views.config_edit, methods=["GET", "POST"])


def main():
    # Start logging server to get output from the clients
    logging_server = LoggingServer()
    logging_server.start()

    initial_data.initial_data()
    initial_data.sample_data()
    initial_data.test_data()

    # recreate client zip
    client_zip_windows()
    app.run(use_reloader=False, use_debugger=True, host="0.0.0.0", port=5000)

    pm.start()


if __name__ == "__main__":
    main()
