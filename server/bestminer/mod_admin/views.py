from flask import Blueprint, render_template
from flask_login import login_required

mod = Blueprint('admin', __name__, template_folder='templates')


@mod.route('/')
@login_required
def index():
    return render_template('admin/index.html')
