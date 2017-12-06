import flask
import flask_login
from flask import Blueprint, request
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired

from bestminer import server_email, flask_mail

mod = Blueprint('promo', __name__, template_folder='templates')


# from promo site
@mod.route("/subscribe-to-beta", methods=['GET', 'POST'])
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


@mod.route("/", methods=['GET', 'POST'])
def index():
    return flask.redirect('static/promo/coming-soon.html')


@login_required
@mod.route("/support", methods=['GET', 'POST'])
def support():
    user = flask_login.current_user.user

    class UserFeedback(FlaskForm):
        subject = StringField(label="Subject", validators=[DataRequired()])
        message = TextAreaField(label="Message", validators=[DataRequired()])

    form = UserFeedback(request.form)
    if form.is_submitted() and form.validate():
        server_email.send_feedback_message(flask_mail, user.email, user.name, form.message.data,
                                           subject='Feedback: ' + form.subject.data)
        flask.flash("Your email message was sent.")
    return flask.render_template('support.html', user=user, form=form)


# Feedback from promo site
@mod.route("/send-feedback", methods=['GET', 'POST'])
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
