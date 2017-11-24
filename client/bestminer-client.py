import calendar
import datetime
import json
import logging
import os, subprocess
import platform
import re
import shlex
import threading
import time
import urllib
from logging import handlers
from urllib import request
from uuid import uuid5

import requests
import uuid
import psutil

from zipfile import ZipFile

import uptime as uptime


def load_config_ini():
    result = {}
    with open("config.txt") as file:
        for line in file:
            m = re.findall('([\w\d_]+)\s*=(.*)', line)
            if len(m) > 0:
                (param, value) = m[0]
                value = value.strip()
                result[param] = value
    return result


config_ini = load_config_ini()
config = {}
miner_process = None
miner_stdout = []  # last N lines from STDOUT of process
current_hashrate = {}  # 'Algo' => { hashrate: 123.56, when: 131424322}
target_hashrate = {}  # 'Algo' => { hashrate: 123.56, when: 131424322}

my_logger = logging.getLogger('')
my_logger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s|%(name)-10s|%(levelname)-4s: %(message)s')


def get_cpu_id():
    '''
    :return: array of CPUIDs
    '''
    system = platform.system()
    if system == 'Windows':
        cpu_ids = []
        proc = subprocess.run("wmic cpu get ProcessorId /format:csv", stdout=subprocess.PIPE)
        for line in proc.stdout.split():
            node, cpu_id = line.decode().split(",")
            if cpu_id == 'ProcessorId':
                # skip head of CSV
                continue
            cpu_ids.append(cpu_id)
        return cpu_ids
    elif system == 'Linux':
        # PROC: sudo dmidecode -t 4 | grep ID | sed 's/.*ID://;s/ //g'
        # 76060100FFFBEBBF
        # MB: sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g' | tr '[:upper:]' '[:lower:]'
        # czc8493tp3
        # MAC: ifconfig | grep eth0 | awk '{print $NF}' | sed 's/://g'
        # 002264bbfc3a
        proc = subprocess.run("sudo dmidecode -t 4 | grep ID | sed 's/.*ID://;s/ //g'", shell=True, stdout=subprocess.PIPE)
        id = proc.stdout.decode().strip()
        return [id]
    else:
        raise Exception("Unsupported platform %s" % platform)


def get_reboot_time():
    '''
    :return: datetime object of moment of boot
    '''
    return uptime.boottime()


def get_rig_id():
    global config_ini
    email = config_ini['email']
    list = get_cpu_id()
    list.append(email)
    rigid_key = ",".join(list)
    import hashlib
    rigid_hash = uuid5(uuid.NAMESPACE_OID, rigid_key)
    #    print(rigid_key, rigid_hash)
    return rigid_hash


# ... ahhh too bad code style... TODO: Make it differently...
rig_id = get_rig_id()


class BestMinerSocketHandler(handlers.SocketHandler):
    def emit(self, record):
        global rig_id
        # Add rig id for server can recognize client id
        record.rig_id = rig_id
        super().emit(record)


def register_on_server():
    """
    Get/update config from server. Save updated config
    :return:
    """
    global config, config_ini
    try:
        config = json.load(open('settings.json'))
    except Exception as e:
        # json config not exists. OK, we will request it from server
        pass
    # default server
    # TODO: set default public server here
    server_address = 'localhost:5000'
    if 'server' in config:
        # last contacted server
        server_address = config['server']
    if 'server' in config_ini:
        # can override from user configuration
        server_address = config_ini['server']
    # Ok. Now we call server and update config from it
    try:
        # send current config to the server for update and review
        newconfig = call_server_api("client/rig_config", server_address=server_address)
        print(newconfig)
        if newconfig['client_version'] != get_client_version():
            logging.info("New version available! Going to install version {}".format(newconfig['client_version']))
            self_update()
        if newconfig['rig_id']:
            # Save config from server as new
            config = newconfig
            save_config()
            return config
    except requests.exceptions.ConnectionError as e:
        logging.error("Cannot connect to server %s" % e)
        return None


def server_log(msg, level=logging.INFO, data={}):
    my_logger.log(level, msg)
    pass


def save_config():
    if not config["server"]:
        raise Exception("Broken config. Not saving")
    file = open("settings.json", "w")
    json.dump(config, file, indent=2)


def kill_process(miner_process):
    # Kill currently running process
    logging.info("Terminating process ...")
    miner_process.terminate()
    time.sleep(2)

    if not is_run(miner_process):
        # process not run
        return
    process = psutil.Process(miner_process.pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()


def is_run(process):
    # https://docs.python.org/3/library/subprocess.html#popen-objects
    return process is not None and process.poll() is None


def get_miner_version(miner_dir):
    miner_version_filename = os.path.join(miner_dir, 'version.txt')
    file = open(miner_version_filename, 'r', encoding='ascii')
    return file.readline().strip()


def get_client_version():
    version_filename = 'version.txt'
    file = open(version_filename, 'r', encoding='ascii')
    return file.readline().strip()



def self_update():
    '''
    Self update
    download client.zip from the server.
    unpack it to dir 'update'
    exit with code 200.
    Runner script shall catch exit code 200 and copy content of 'update' to root dir.
    :return:
    '''
    update_dir = 'update'
    if not os.path.exists(update_dir):
        os.mkdir(update_dir)
    my_os = get_my_os()
    zip_filename = "BestMiner-{}.zip".format(my_os)
    url = "http://{}/static/client/{}".format(config['server'], zip_filename)
    my_logger.info("Downloading program from {}".format(url))
    request.urlretrieve(url, zip_filename)
    with ZipFile(zip_filename, 'r') as myzip:
        myzip.extractall(update_dir)
    os.remove(zip_filename)
    my_logger.info("Download complete. Going to install program.")
    exit(200)

def run_miner(miner_config):
    """
    Run miner for specified config.
    Shut down currently runned miner if nessessary.
    Update config file to given miner_config
    Run given miner

    :param miner_config:
    :return:
    """
    global miner_process

    if miner_config["miner"] == "":
        raise Exception("Empty miner configuration given")

    # stop_miner_if_run(config['minerConfig'))
    # Save new (hm..., possible new) config
    current_config = config['miner_config']
    if current_config["config_name"] == miner_config["config_name"]:
        # the same miner. No need to switch
        # just ensure it is run
        if is_run(miner_process):
            return
    else:
        config['miner_config'] = miner_config
        save_config()
        # going to start new miner. At first we shall stop current miner process
        kill_process(miner_process)
    # Let's download miner if required to update
    miner_dir = os.path.join('miners', miner_config["miner_directory"])
    if not os.path.exists(miner_dir) or get_miner_version(miner_dir) != miner_config['miner_version']:
        url = "http://%s/static/miners/%s.zip" % (config['server'], miner_config["miner_directory"])
        my_logger.info("Downloading miner '%s' (ver %s) from %s" % (miner_config['miner'], miner_config['miner_version'], url))
        zip_file = 'miners/%s.zip' % (miner_config["miner_directory"])
        if not os.path.exists('miners'): os.mkdir('miners')
        request.urlretrieve(url, zip_file)
        with ZipFile(zip_file, 'r') as myzip:
            myzip.extractall('miners')
        os.remove(zip_file)
        my_logger.info("Successfully download miner. Current version: %s " % get_miner_version(miner_dir))
    miner_exe = miner_config["miner_exe"]
    args = shlex.split(miner_config["miner_command_line"])
    args.insert(0, miner_exe)
    server_log("Run miner from '%s' %s" % (miner_dir, " ".join(args)))
    env = miner_config["env"]
    full_env = {**os.environ, **env}
    miner_process = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                                     env=full_env, cwd=miner_dir)

    miner_out_reader = threading.Thread(target=read_miner_output)
    miner_out_reader.start()
    my_logger.info("Runned miner %s PID %s" % (miner_exe, miner_process.pid))


def restart_miner():
    run_miner(config['miner_config'])


def read_miner_output():
    global config, miner_process
    miner_config = config['miner_config']
    miner_family = miner_config['miner_family']
    logger = logging.getLogger("miner_" + miner_family)
    while True:
        if not is_run(miner_process):
            logger.warning("Miner was terminated. Stop monitoring stdout")
            break
        line = miner_process.stdout.readline().decode()
        if line != '':
            line = line.rstrip()
            logger.info(line)
        else:
            logger.warning("Miner has finished")
            break


def get_state_info():
    """
    make a bunch of state information for sending to the server

    :return:
    """

    compute_units_info = {}  # get_open_hardware_monitor_statistics()

    # workersInfo(Temp, fan, config), miner(state, config, hashrate, screen, lastUpdate)
    global miner_process, target_hashrate, current_hashrate

    state_info = {
        "miner": {
            "is_run": is_run(miner_process),
            "config": config["miner_config"],
        },
        "hashrate": {
            "current": current_hashrate,
            "target": target_hashrate,
        },
        "compute_units": compute_units_info,
        "miner_stdout": miner_stdout,
        "reboot_timestamp": calendar.timegm(get_reboot_time().utctimetuple()),
    }
    return state_info


def get_my_os():
    return platform.system()


def call_server_api(path, data={}, server_address=None):
    global config, rig_id, config_ini
    vars = {
        'rig_id': rig_id,
        'email': config_ini['email'],
        'api_key': config_ini['api_key'],
        'os': get_my_os(),
    }
    if not server_address:
        server_address = config["server"]
    url = 'http://%s/%s?%s' % (server_address, path, urllib.parse.urlencode(vars))
    #    'application/json'
    response = requests.post(url=url, json=data)
    error_code = response.status_code
    if error_code != 200:
        raise Exception("Got error code %s for url %s" % (error_code, url))
    return response.json()


def execute_task(task):
    task_name = task['task']
    task_data = task['data']
    if task_name == "switch_miner":
        miner_config = task_data["miner_config"]
        run_miner(miner_config)


def task_manager():
    global config
    request_interval = 30
    state_info = {}
    while True:
        request_interval = config["task_manager"]["request_interval_sec"]
        time.sleep(request_interval)
        try:
            my_logger.info("Gather the state")
            state_info = get_state_info()
        except Exception as e:
            my_logger.error("Error getting state: %s" % str(e))
        try:
            tasks = call_server_api("client/stat_and_task", state_info)
        except Exception as e:
            my_logger.error("Error with send stat and run task: %s" % e)
            continue
        for task in tasks:
            task_name = task['task']
            task_data = task['data']
            print("Task %s: %s" % (task_name, task_data))
            execute_task(task)


class StatisticManager(threading.Thread):

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self.logger = logging.getLogger("statistic")
        super().__init__(group, target, name, args, kwargs, daemon=daemon)

    def send_stat(self):
        booted_orig = get_reboot_time()
        # remove TZ as can't subtract offset-naive and offset-aware datetimes
        booted = booted_orig.replace(tzinfo=None, microsecond=0)
        now = datetime.datetime.now()
        now = now.replace(microsecond=0)
        diff = now - booted
        data = {
            'hms': str(diff),
            'sec': diff.seconds,
            'rebooted': str(booted_orig),
            'rebooted_epoch': calendar.timegm(booted_orig.utctimetuple()),
        }
        self.logger.info("UPTIME=%s" % json.dumps(data))

    def run(self):
        while True:
            try:
                self.send_stat()
            except Exception as e:
                self.logger.error("Exception running send_stat: %s" % e)
                pass
            time.sleep(30)



if __name__ == "__main__":
    logging.info("Starting BestMiner")
    register_on_server()
    if not 'rig_id' in config:
        logging.error("Cannot load config from server. Exiting")
        exit()
    logging.info("Running as worker '%s'" % config['worker'])
    socketHandler = BestMinerSocketHandler(config['logger']['server'], config['logger']['port'])
    my_logger.addHandler(socketHandler)

    restart_miner()

    stat_manager = StatisticManager()
    stat_manager.start()
    task_manager = threading.Thread(target=task_manager)
    task_manager.start()
