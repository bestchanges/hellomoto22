import logging

import initial_data
import views
import flask

from logging_server import LoggingServer
from models import *

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
#        format='%(relativeCreated)5d %(name)-15s %(levelname)-8s %(message)s')  # %(client_id)-15s

db.init_app(app)

# prepare data for work
app.add_url_rule('/client/rig_config', view_func=views.client_config, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat_and_task', view_func=views.acceptData, methods=["GET", "POST", "PUT"])

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
    app.run(use_reloader=False, use_debugger=True, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    main()

