import logging
import random
import string
from _sha256 import sha256
from urllib.parse import urlparse, urljoin

import flask_login
import os
from flask import request, url_for
from flask_login import LoginManager, login_required, login_user, UserMixin
from flask_mail import Mail
from wtforms import validators, TextAreaField
from flask_wtf import FlaskForm, Form
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea

import initial_data
import server_email
import views
import flask
import auth

from logging_server import LoggingServer
from make_client_zip import _client_zip_windows, client_zip_windows_for_user, client_zip_windows_for_update
from models import *
from profit_manager import pm

app = flask.Flask(__name__)
app.config.from_object('bestminer.default_settings')
app.config.from_envvar('BESTMINER_SETTINGS')

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
login_manager.user_callback = load_user
login_manager.session_protection = "strong"
login_manager.login_view = '/login'

flask_mail = Mail(app)

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

        user_password = gen_password(8,10)
        user = User()
        user.email = email
        user.password = sha256(user_password.encode('utf-8')).hexdigest()
        user.client_secret = gen_password(6,6)
        user.api_key = gen_password(20,20, chars=string.ascii_uppercase + string.digits)
        user.target_currency = 'USD'
        user.save()

        server_email.send_welcome_email(flask_mail, user, user_password, request.host_url + 'login')

        flask.flash('Account registered. Email with password sent to your address.')
        return flask.redirect(flask.url_for('login'))
    return flask.render_template('register.html', form=form)


@app.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    flask.flash('You are logged out.')
    return flask.redirect(url_for('login'))


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

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
        users = User.objects(email=form.email.data)
        password_hash = sha256(form.password.data.encode('utf-8')).hexdigest()
        if not users or users[0].password != password_hash:
            flask.flash('Wrong login or password')
            return flask.render_template('login.html', form=form)
        user = users[0]
        login_user(user, remember=True)

        flask.flash('Logged in successfully.')

        next = flask.request.args.get('next')
        # is_safe_url should check if the url is safe for redirects.
        # See http://flask.pocoo.org/snippets/62/ for an example.
        if not is_safe_url(next):
            return flask.abort(400)

        return flask.redirect(next or flask.url_for('index'))
    return flask.render_template('login.html', form=form)

@app.route("/settings")
@login_required
def settings():
    return 'OK'

@login_required
def download_win():
    user = flask_login.current_user.user
    zip_file = client_zip_windows_for_user(user, request.host)
    return flask.redirect(request.host_url + zip_file)

# from promo site
@app.route("/subscribe-to-beta", methods=['GET', 'POST'])
def subscribe():
    email = request.form.get('email')
    valid = True
    message = "Error"
    if not email:
        valid = False
    if valid:
        server_email.send_subscribe_email(flask_mail, email)
        message = "OK"
    return flask.jsonify({'message': message, 'valid': valid})

@app.route("/", methods=['GET', 'POST'])
def index():
    return flask.redirect('static/promo/coming-soon.html')

@login_required
@app.route("/support", methods=['GET', 'POST'])
def support():
    user = flask_login.current_user.user

    class UserFeedback(FlaskForm):
        subject = StringField(label="Subject", validators=[DataRequired()])
        message = TextAreaField(label="Message", validators=[DataRequired()])

    form = UserFeedback(request.form)
    if form.is_submitted() and form.validate():
        server_email.send_feedback_message(flask_mail, user.email, user.name, form.message.data, subject='Feedback: ' + form.subject.data)
        flask.flash("Your email message was sent.")
    return flask.render_template('support.html', user=user, form=form)



# Feedback from promo site
@app.route("/send-feedback", methods=['GET', 'POST'])
def feedback():
    email = request.form.get('email')
    name = request.form.get('name')
    message = request.form.get('message')

    valid = True
    result = {
        'emailMessage': '',
        'nameMessage': '',
        'messageMessage': '',
    }
    if not email:
        result['emailMessage'] = 'required'
        valid = False
    elif not name:
        result['nameMessage'] = 'required'
        valid = False
    elif not message:
        result['messageMessage'] = 'required'
        valid = False
    if valid:
        server_email.send_feedback_message(flask_mail, email, name, message)

    return flask.jsonify(result)

db.init_app(app)

# prepare data for work
app.add_url_rule('/client/rig_config', view_func=views.client_config1, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat_and_task', view_func=views.recieve_stat_and_return_task, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat', view_func=views.receive_stat, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/task', view_func=views.send_task, methods=["GET", "POST", "PUT"])

#app.add_url_rule('/promo', view_func=views.index)
#app.add_url_rule('/', view_func=views.index)
app.add_url_rule('/download', view_func=views.download)
app.add_url_rule('/download_win', view_func=download_win)
app.add_url_rule('/rigs', view_func=views.rig_list)
app.add_url_rule('/rigs.json', view_func=views.rig_list_json)
app.add_url_rule('/rig/<uuid>/info', view_func=views.rig_info, methods=["GET", "POST"])
app.add_url_rule('/rig/<uuid>/log', view_func=views.rig_log)
app.add_url_rule('/rig/<uuid>/set_config', view_func=views.rig_set_config)

app.add_url_rule('/poolaccounts', view_func=views.poolaccount_list, methods=["GET", "POST"])
app.add_url_rule('/poolaccounts.json', view_func=views.poolaccount_list_json)
app.add_url_rule('/poolaccount/', view_func=views.poolaccount_edit, defaults={'id': None}, methods=["GET", "POST"])
app.add_url_rule('/poolaccount/<id>', view_func=views.poolaccount_edit, methods=["GET", "POST"])

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

    login_manager.init_app(app)

    # recreate client zip
    # commented as soon as run separately in update.sh
    # client_zip_windows_for_update()

    app.run(use_reloader=False, use_debugger=True, host="0.0.0.0", port=5000)

    pm.start()


if __name__ == "__main__":
    main()
