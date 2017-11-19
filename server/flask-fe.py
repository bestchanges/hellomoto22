from flask import Flask
from flask import render_template, jsonify
from flask_mongoengine import MongoEngine

class Rig(db.Document):
    id = db.IntField()


app = Flask(__name__)
# app.config.from_pyfile('okminer.cfg')
app.config["MONGODB_SETTINGS"] = {'DB': "okminer"}
app.config["SECRET_KEY"] = "KeepThisSt"

db = MongoEngine(app)


@app.route("/")
def hello():
    return render_template("index.html")


@app.route("/data/rigs.json")
def rig_list():
    riglist = [
        {
            'name': 'digger1',
            'uptime': 'UP 1d 14h',
            'temp': '75,45,32,45',
            'comment': 'first rig of ours',
            'info': 'longlong description'
        },
        {
            'name': 'digger2',
            'uptime': 'UP 1h 12m',
            'temp': '75,45,32,45,81',
            'comment': 'first rig of ours',
            'info': 'not at all'
        },
    ]
    return jsonify({'data': riglist})


# выдать клиенту конфиг по запросу
@app.route("/allminer/config.ini")
def give_client_config():
    return '''
command_line=--server eu1-zcash.flypool.org --user t1Q99nQXpQqBbutcaFhZSe3r93R9w4HzV2Q.digger1 --pass x --port 3333 -fee 0.5
miner_dir=ewbf_0.3.4b
miner_winexe=miner.exe
version=1
'''.strip()


@app.route("/sampledata")
def sampleData():
    rigs = [
        {
            'id': 1234,
            'name': 'digger1',
        }
    ]
    return rigs


@app.route("/stat_and_task")
def acceptData():
    return 'ok'
