import random
import string
from _sha256 import sha256
from urllib.parse import urlparse, urljoin

import flask
import flask_login
from flask import request, url_for, Blueprint
from flask_login import login_required, login_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms import validators

from bestminer import server_email, flask_mail, initial_data
from bestminer.initial_data import create_user
from bestminer.models import User

mod = Blueprint('auth', __name__, template_folder='templates')


@mod.route('/register', methods=['GET', 'POST'])
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
            return flask.redirect(flask.url_for('.login'))

        user,user_password = create_user(email=email)

        server_email.send_welcome_email(flask_mail, user, user_password, request.host_url + 'user/download')

        flask.flash('Account registered. Email with password sent to your address.')
        return flask.redirect(flask.url_for('.login'))
    return flask.render_template('register.html', form=form)


@mod.route('/logout', methods=['GET'])
def logout():
    flask_login.logout_user()
    flask.flash('You are logged out.')
    return flask.redirect(url_for('auth.login'))


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc


@mod.route('/login', methods=['GET', 'POST'])
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

        return flask.redirect(next or flask.url_for('user.download'))
    return flask.render_template('login.html', form=form)


@mod.route("/settings")
@login_required
def settings():
    return 'OK'
