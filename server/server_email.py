from flask import render_template
from flask import Flask
from flask_mail import Mail, Message

from models import User


def send_welcome_email(flask_mail, user, password, login_url):
    msg = Message(
        subject="Registration at BestMiner",
        recipients=[user.email],
        body=render_template("email/welcome_email.txt", user=user, password=password, login_url=login_url)
    )
    flask_mail.send(msg)

    '''
        send_email("[microblog] %s is now following you!" % follower.nickname,
            ADMINS[0],
            [followed.email],
            render_template("follower_email.txt",
                user = followed, follower = follower),
            render_template("follower_email.html",
                user = followed, follower = follower))
    '''