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

import sys
import uptime as uptime


class LimitedList(list):
    '''
    Limit list for no more than LIMIT entries.
    If number of entries exceed limit, then delete first items until it ok
    '''

    def __init__(self, limit) -> None:
        self.limit = limit
        super().__init__()

    def append(self, object) -> None:
        super().append(object)
        self.trunc()

    def insert(self, index: int, object) -> None:
        super().insert(index, object)
        self.trunc()

    def trunc(self):
        while len(self) > self.limit:
            self.pop(0)


stdout_history = LimitedList(30)


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
compute_units_info = []  #
compute_units_fan = []
compute_units_temp = []

my_logger = logging.getLogger('')
my_logger.setLevel(logging.DEBUG)
logging.basicConfig(format='%(asctime)s|%(name)-10s|%(levelname)-4s: %(message)s')


def get_system_id():
    '''
    :return: array of CPUIDs
    '''
    system = platform.system()
    if system == 'Windows':
        system_id = ''
        # >wmic cpu get ProcessorId
        # ProcessorId
        # 178BFBFF00100F53
        proc = subprocess.run("wmic cpu get ProcessorId", stdout=subprocess.PIPE)
        firstline = True
        for line in proc.stdout.split():
            line = line.decode().strip()
            if firstline:
                # skip head
                firstline = False
                continue
            system_id = system_id + ',' + line
        # >wmic baseboard get serialnumber
        # SerialNumber
        # QB08727640
        proc = subprocess.run("wmic baseboard get serialnumber", stdout=subprocess.PIPE)
        firstline = True
        for line in proc.stdout.split():
            line = line.decode().strip()
            if firstline:
                # skip head
                firstline = False
                continue
            system_id = system_id + ',' + line
            return system_id
    elif system == 'Linux':
        # PROC: sudo dmidecode -t 4 | grep ID | sed 's/.*ID://;s/ //g'
        # 76060100FFFBEBBF
        system_id = ''
        proc = subprocess.run("sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g'", shell=True, stdout=subprocess.PIPE)
        id = proc.stdout.decode().strip()
        system_id = system_id + ',' + id
        # MB: sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g' | tr '[:upper:]' '[:lower:]'
        # czc8493tp3
        # MAC: ifconfig | grep eth0 | awk '{print $NF}' | sed 's/://g'
        # 002264bbfc3a
        proc = subprocess.run("sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g'", shell=True, stdout=subprocess.PIPE)
        id = proc.stdout.decode().strip()
        system_id = system_id + ',' + id
        return system_id
    else:
        raise Exception("Unsupported platform %s" % platform)
    raise Exception("Cannot get system unique id")


def get_reboot_time():
    '''
    :return: datetime object of moment of boot
    '''
    boottime = uptime.boottime()
    tz_offset = datetime.datetime.now() - datetime.datetime.utcnow()
    utcboottime = boottime - tz_offset
    return utcboottime


def get_rig_id():
    global config_ini
    email = config_ini['email']
    unique_systemid_components = []
    unique_systemid_components.append(email)
    unique_systemid_components.append(get_system_id())
    rigid_key = ",".join(unique_systemid_components)
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
        newconfig = call_server_api("client/rig_config", data=config, server_address=server_address)
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
    json.dump(config, file, indent=2, sort_keys=True)


def kill_process(miner_process):
    # Kill currently running process
    logging.info("Terminating process ...")

    if not is_run(miner_process):
        logging.info("Process not run. No need to terminate")
        # process not run
        return
    process = psutil.Process(miner_process.pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()
    time.sleep(2)
    my_logger.debug("Process has stopped. Process run: {}".format(is_run(miner_process)))


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
    my_logger.info("Downloading latest program from {}".format(url))
    request.urlretrieve(url, zip_filename)
    with ZipFile(zip_filename, 'r') as myzip:
        myzip.extractall(update_dir)
    os.remove(zip_filename)
    my_logger.info("Download complete. Going to install program.")
    global miner_process
    kill_process(miner_process)
    os._exit(200)

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

    # запустить майнер хэндлер по типу семейства
    miner_handler_method = globals()[miner_config['miner_family'] + '_handler']
    my_logger.debug("Going to start handler: {}".format(miner_handler_method))
    miner_handler = threading.Thread(target=miner_handler_method)
    miner_handler.start()
    time.sleep(0.3)

    if miner_config['read_output']:
        # we've got some problem using stdout=PIPE because of system buffer of stdout (about 8k).
        # thus we cannot read stdout in realtime, which is quite useless.
        # Workaround is to parse miner's log (at least claymore and ewbf write logs)
        miner_process = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                                         env=full_env, cwd=miner_dir, universal_newlines=True)
        miner_out_reader = threading.Thread(target=read_miner_output)
        miner_out_reader.start()
    else:
        miner_process = subprocess.Popen(args, shell=True, stdout=None, stderr=None, bufsize=0,
                                         env=full_env, cwd=miner_dir, universal_newlines=True)

    my_logger.info("Runned miner %s PID %s" % (miner_exe, miner_process.pid))


def restart_miner():
    run_miner(config['miner_config'])


def read_miner_output():
    global config, miner_process
    miner_config = config['miner_config']
    # miner_family = miner_config['miner_family']
    # logger = logging.getLogger("miner_" + miner_family)
    logger = logging.getLogger("miner")
    while True:
        if not is_run(miner_process):
            logger.warning("Miner was terminated. Stop monitoring stdout")
            break
        line = miner_process.stdout.readline()
        if line != '':
            line = line.rstrip()
            logger.info(line)
        else:
            logger.warning("Miner has finished")
            break

def hashrate_from_units(value, units):
    unit_measures = {
        "h/s": 1,
        "Kh/s": 1e3,
        "Mh/s": 1e6,
        "Gh/s": 1e9,
        "Th/s": 1e12,
        "Ph/s": 1e15,
        "Sol/s": 1,
        "KSol/s": 1e3,
        "MSol/s": 1e6,
        "GSol/s": 1e9,
    }
    if units in unit_measures.keys():
        return value * unit_measures[units]
    raise Exception("Unknown measurement unit %s. Known units %s" % (units, unit_measures.keys()))


def claymore_handle_line(line):
    global current_hashrate, compute_units_info, compute_units_temp, compute_units_fan


    global stdout_history
    stdout_history.append(line.strip())

    # GPU #0: Ellesmere, 4096 MB available, 32 compute units
    # GPU #0 recognized as Radeon RX 470/570
    '''
    AMD Cards available: 5
    GPU #0: Ellesmere, 4096 MB available, 32 compute units
    GPU #0 recognized as Radeon RX 470/570
    GPU #1: Ellesmere, 4096 MB available, 32 compute units
    GPU #1 recognized as Radeon RX 470/570
    GPU #2: Ellesmere, 4096 MB available, 32 compute units
    GPU #2 recognized as Radeon RX 470/570
    GPU #3: Ellesmere, 4096 MB available, 32 compute units
    GPU #3 recognized as Radeon RX 470/570
    GPU #4: Ellesmere, 4096 MB available, 32 compute units
    GPU #4 recognized as Radeon RX 470/570        '''

    m = re.findall('GPU #(\d+) recognized as (Radeon RX) (470/570)', line)
    if len(m) > 0:
        gpu_num, family, model = m[0]
        gpu_num = int(gpu_num)
        if family == 'Radeon RX':
            if model == '470/570':
                card ='amd_rx_470'
            else:
                card = 'amd_rx'
        else:
            my_logger.error('Cannot recognize AMD family %s' % family)
        if gpu_num == 0:
            compute_units_info.clear()
        if card:
            compute_units_info.append(card)

    '''
    01:41:44:605	1d20	NVIDIA Cards available: 3 
    01:41:44:610	1d20	CUDA Driver Version/Runtime Version: 9.1/8.0
    01:41:44:615	1d20	GPU #0: GeForce GTX 1060 3GB, 3072 MB available, 9 compute units, capability: 6.1
    01:41:44:621	1d20	GPU #1: GeForce GTX 1060 3GB, 3072 MB available, 9 compute units, capability: 6.1
    01:41:44:627	1d20	GPU #2: GeForce GTX 1060 3GB, 3072 MB available, 9 compute units, capability: 6.1
    01:41:44:632	1d20	Total cards: 3 
    '''
    m = re.findall('GPU #(\d+): (GeForce GTX) ([^\s]+) (\d+)GB', line)
    if len(m) > 0:
        gpu_num, family, model, memory = m[0]
        gpu_num = int(gpu_num)
        if family == 'GeForce GTX':
            card ='nvidia_gtx_{}_{}gb'.format(model, memory)
        else:
            my_logger.error('Cannot recognize NVIDIA family %s' % family)
        if gpu_num == 0:
            compute_units_info.clear()
        if card:
            compute_units_info.append(card)

    # hashrate info
    # ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22
    # DCR - Total Speed: 3890.426 Mh/s, Total Shares: 8655, Rejected: 96
    m = re.findall('(\w+) - Total Speed: ([\d\.]+) ([\w\/]+)', line)
    if len(m) > 0:
        (code, value, units) = m[0]
        val = float(value)
        if code == "ETH":
            algorithm = 'Ethash'
        elif code == "DCR":
            # take into consideration when mining single Blake
            algorithm = 'Blake (14r)'
        else:
            my_logger.error("Unexpected currency code={}".format(code))
            algorithm = None
        if algorithm:
            current_hashrate[algorithm] = hashrate_from_units(val, units)

    # now take care about temperaure and fan speed
    # GPU0 t=55C fan=52%, GPU1 t=50C fan=43%, GPU2 t=57C fan=0%, GPU3 t=52C fan=48%, GPU4 t=49C fan=0%, GPU5 t=53C
    m = re.findall('GPU(\d+) t=(\d+). fan=(\d+)', line)
    if len(m) > 0:
        temps = []
        fans = []
        for num, temp, fan in m:
            temps.append(temp)
            fans.append(fan)
        compute_units_temp = temps
        compute_units_fan = fans
    return True


class MinerHandler():
    '''
    The responcibily of this class is
    1. run miner
    2. keep miner running
    3. gather statistic's (from stdout or logs) - store to stats
    '''

def claymore_handler():
    global config
    # give time for miner to start
    time.sleep(6)
    miner_config = config['miner_config']
    miner_dir = os.path.join('miners', miner_config["miner_directory"])
    logger = logging.getLogger("miner")
    while True:
        fn = os.path.join(miner_dir, 'log_noappend.txt')
        fp = open(fn, 'r', encoding='866', newline='')
        # need to seek to the end if log file appendable by miner.
        # in claymore if filename has "noappend" the log will be truncated
        # fp.seek(0, 2)
        while True:
            new = fp.readline()
            # Once all lines are read this just returns ''
            # until the file changes and a new line appears
            if new:
                logger.info(new.strip())
                claymore_handle_line(new)
            else:
                # check if miner_process is alive. If not then exit
                # A None value indicates that the process hasn't terminated yet
                if is_run(miner_process):
                    # wait for new line
                    time.sleep(1)
                else:
                    my_logger.debug("STOP claymore_miner handler thread")
                    return

def ewbf_handle_line(line):
    global current_hashrate, compute_units_temp

    # Total speed: 1763 Sol/s
    m = re.findall('Total speed: ([\d\.]+) ([\w\/]+)', line)
    if len(m) > 0:
        value, units = m[0]
        val = float(value)
        algorithm = 'Equihash'
        current_hashrate[algorithm] = hashrate_from_units(val, units)

    # Temp: GPU0: 60C GPU1: 66C GPU2: 56C GPU3: 61C GPU4: 61C GPU5: 59C
    # Temp: GPU0: 56C GPU1: 52C GPU2: 50C
    # TODO: temp do not parse due to special codes for color switching before temperature value
    m = re.findall('GPU(\d+): (\d+)C', line)
    if len(m) > 0:
        temps = []
        for num, temp in m:
            temps.append(temp)
        compute_units_temp = temps
    # GPU0: 284 Sol/s GPU1: 301 Sol/s GPU2: 289 Sol/s GPU3: 299 Sol/s GPU4: 297 Sol/s GPU5: 293 Sol/s
    # GPU0: 281 Sol/s GPU1: 288 Sol/s GPU2: 283 Sol/s
    return True


def ewbf_handler():
    global config
    miner_config = config['miner_config']
    miner_dir = os.path.join('miners', miner_config["miner_directory"])
    logger = logging.getLogger("miner")
    # first delete old miner.log from miner dir
    log_file = os.path.join(miner_dir, 'miner.log')
    if os.path.isfile(log_file):
        os.unlink(log_file)
    # give time for miner to start
    time.sleep(3)
    while True:
        fn = os.path.join(miner_dir, 'miner.log')
        fp = open(fn, 'r', encoding='866', newline='')
        # need to seek to the end if log file appendable by miner.
        # in claymore if filename has "noappend" the log will be truncated
        # fp.seek(0, 2)
        while True:
            new = fp.readline()
            # Once all lines are read this just returns ''
            # until the file changes and a new line appears
            if new:
                logger.info(new.strip())
                ewbf_handle_line(new)
            else:
                # check if miner_process is alive. If not then exit
                # A None value indicates that the process hasn't terminated yet
                if is_run(miner_process):
                    # wait for new line
                    time.sleep(1)
                else:
                    my_logger.debug("STOP ewbf_miner handler thread")
                    return


def get_state_info():
    """
    make a bunch of state information for sending to the server

    :return:
    """

    # workersInfo(Temp, fan, config), miner(state, config, hashrate, screen, lastUpdate)
    global miner_process, target_hashrate, current_hashrate, compute_units_info, miner_stdout

    state_info = {
        "miner": {
            "is_run": is_run(miner_process),
            "config": config["miner_config"],
        },
        "hashrate": {
            "current": current_hashrate,
            "target": target_hashrate,
        },
        'pu_fanspeed': compute_units_fan,
        'pu_temperatire': compute_units_temp,
        "processing_units": compute_units_info,
        "miner_stdout": miner_stdout,
        "reboot_timestamp": calendar.timegm(get_reboot_time().utctimetuple()),
        'client_version': get_client_version()
    }
    return state_info


def get_my_os():
    return platform.system()


def call_server_api(path, data={}, server_address=None):
    global config, rig_id, config_ini
    vars = {
        'rig_id': rig_id,
        'email': config_ini['email'],
        'secret': config_ini['secret'],
        'os': get_my_os(),
    }
    if not server_address:
        server_address = config["server"]
    url = 'http://%s/%s?%s' % (server_address, path, urllib.parse.urlencode(vars))
    my_logger.debug("Request server API: {}".format(url))
    #    'application/json'
    response = requests.put(url=url, json=data)
    error_code = response.status_code
    if error_code != 200:
        raise Exception("Got error code %s for url %s" % (error_code, url))
    return response.json()


class TaskManager(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self.logger = logging.getLogger("task_manager")
        super().__init__(group, target, name, args, kwargs, daemon=daemon)

    def get_and_execute_task(self):
        self.logger.info("Check tasks...")
        tasks = call_server_api("client/task")
        for task in tasks:
            task_name = task['task']
            task_data = task['data']
            self.logger.info("Get task '{}'".format(task_name))
            if task_name == "switch_miner":
                miner_config = task_data["miner_config"]
                run_miner(miner_config)
            elif task_name == "self_update":
                self_update()
            else:
                raise Exception("Received unknown task '{}'".format(task_name))

    def run(self):
        request_interval = config["task_manager"]["request_interval_sec"]
        if request_interval is None or request_interval == 0:
            request_interval = 30
        while True:
            try:
                self.get_and_execute_task()
            except Exception as e:
                self.logger.error("Exception running task: %s" % e)
            time.sleep(request_interval)


class StatisticManager(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self.logger = logging.getLogger("statistic_manager")
        super().__init__(group, target, name, args, kwargs, daemon=daemon)

    def send_stat(self):
        state_info = get_state_info()
        result = call_server_api("client/stat", state_info)

    def run(self):
        request_interval = config["statistic_manager"]["request_interval_sec"]
        if request_interval is None or request_interval == 0:
            request_interval = 30
        # for first run wait while statistic will be ready
        time.sleep(request_interval)
        while True:
            try:
                self.logger.info("send stat to server")
                self.send_stat()
            except Exception as e:
                self.logger.error("Exception sending stat: %s" % e)
                pass
            time.sleep(request_interval)


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
    task_manager = TaskManager()
    task_manager.start()
