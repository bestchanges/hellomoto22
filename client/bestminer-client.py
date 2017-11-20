import calendar
import datetime
import json
import logging
import os, subprocess
import re
import shlex
import threading
import time
import urllib
from logging import handlers
from uuid import uuid5

import requests
import uuid
import psutil

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

logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s|%(name)-10s|%(levelname)-4s: %(message)s')


def get_cpu_id():
    '''
    :return: array of CPUIDs
    '''
    cpu_ids = []
    proc = subprocess.run("wmic cpu get ProcessorId /format:csv", stdout=subprocess.PIPE, encoding="ASCII")
    for line in proc.stdout.split():
        node, cpu_id = line.split(",")
        if cpu_id == 'ProcessorId':
            # skip head of CSV
            continue
        cpu_ids.append(cpu_id)
    return cpu_ids


def get_reboot_time():
    '''
    :return: datetime object of moment of boot
    '''
    line = ""
    try:
        proc = subprocess.run("wmic os get lastbootuptime", stdout=subprocess.PIPE, encoding="ASCII")
        head = True
        for line in proc.stdout.split():
            if head:
                # skip head
                head = False
                continue
            # line = 20171118020936.495470+180
            m = re.findall("(\d+)\.\d+([+\-])(\d+)", line)
            date_time, tz_sign, timezone_offset = m[0]
            # need to convert timzeone offset to the form +HHMM as need %z
            # https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
            hh = int(timezone_offset) / 60
            mm = int(timezone_offset) - hh * 60
            tz = tz_sign + "%02d%02d" % (hh,mm)
            p = datetime.datetime.strptime(date_time+tz, "%Y%m%d%H%M%S%z")
            logger.debug("Reboot time: %s" % p)
            return p
    except Exception:
        logger.error("Cannot get reboot time. Line: %s" % line)
    return None


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


def get_config():
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
        if newconfig['rig_id']:
            # Save config from server as new
            config = newconfig
            save_config()
            return config
    except requests.exceptions.ConnectionError as e:
        logging.error("Cannot connect to server %s" % e)
        return None


def server_log(msg, level=logging.INFO, data={}):
    logger.log(level, msg)
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
    miner_dir = miner_config["miner_directory"]
    if not os.path.exists(miner_dir):
        server_log("TODO: Download miner to %s" % miner_dir)
    miner_exe = miner_config["miner_exe"]
    # elif minerConfig.minerVersion > $minerDir.version.txt - downloadMiner
    args = shlex.split(miner_config["miner_command_line"])
    args.insert(0, miner_exe)
    server_log("Run miner from '%s' %s" % (miner_dir, " ".join(args)))
    env = miner_config["env"]
    full_env = {**os.environ, **env}
    miner_process = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                                     env=full_env, universal_newlines=True, cwd=miner_dir, encoding="utf-8", errors='ignore')

    miner_out_reader = threading.Thread(target=read_miner_output)
    miner_out_reader.start()
    logger.info("Runned miner %s PID %s" % (miner_exe, miner_process.pid))


def restart_miner():
    run_miner(config['miner_config'])


def set_current_hashrate(algo, value):
    """
    Store current hashrate in global variables. Also adjust target hashrate if required

    :param algo:
    :param value:
    :return:
    """
    global current_hashrate, target_hashrate
    algo_hashrate = {"value": value, "when": int(time.time())}
    current_hashrate[algo] = algo_hashrate
    global config
    if "target_hashrate" not in config:
        config["target_hashrate"] = {}
    target_hashrate = config["target_hashrate"]
    if not algo in target_hashrate:
        target_hashrate[algo] = algo_hashrate
        print(target_hashrate)
    else:
        if target_hashrate[algo]["value"] < algo_hashrate["value"]:
            target_hashrate[algo] = algo_hashrate
            print(target_hashrate)


def process_miner_stdout_line(line):
    """
    deprecated: Logic moved to the server. Remove from here


    Gather useful information from miner output (aka hashrate)

    :param line: one line from STDOUT of miner
    :return: nothing
    """
    global config
    miner_config = config['miner_config']
    miner_family = miner_config['miner_family']
    if miner_family == "claymore":
        # try get hashing info
        # ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22
        # DCR - Total Speed: 3890.426 Mh/s, Total Shares: 8655, Rejected: 96
        m = re.findall('(\w+) - Total Speed: ([\d\.]+) ', line)
        if len(m) > 0:
            (code, value) = m[0]
            val = float(value)
            is_dual = 'algorithm_dual' in miner_config and miner_config['algorithm_dual'] != ''
            if code == "ETH":
                if is_dual:
                    algo = 'Ethash Dual'
                else:
                    algo = 'Ethash'
                set_current_hashrate(algo, val)
            if code == "DCR":
                # take into consideration when mining single Blake
                # if miner_config["algorith_dual"] != "":
                set_current_hashrate('Blake (14r) Dual', val)
    elif miner_family == "ewbf":
        # Total speed: 1623 Sol/s
        m = re.findall('Total speed: ([\d\.]+) ', line)
        if len(m) > 0:
            value = m[0]
            val = float(value)
            current_hashrate['Equihash'] = {"value": val, "when": int(time.time())}
            set_current_hashrate('Equihash', val)


def read_miner_output():
    global config, miner_process
    miner_config = config['miner_config']
    miner_family = miner_config['miner_family']
    logger = logging.getLogger("miner_" + miner_family)
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


def get_open_hardware_monitor_statistics():
    """
    not implemented yet. There is UAC problem and also problem installing pypiwin32/pywin32
    :return:
    """
    import psutil
    if not "OpenHardwareMonitor.exe" in (p.name() for p in psutil.process_iter()):
        # not runned. Run now
        subprocess.Popen("OpenHardwareMonitor\OpenHardwareMonitor.exe")
    else:
        print("OHW runned")
    import wmi
    c = wmi.WMI()
    for s in c.Win32_Service():
        if s.State == 'Stopped':
            print(s.Caption, s.State)
            #		$os = Get-WmiCustom -class win32_operatingsystem -timeout 10
            #		$uptime = $os.ConvertToDateTime($os.LocalDateTime) - $os.ConvertToDateTime($os.LastBootUptime)

    return {"HWINFO": 1}


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


def call_server_api(path, data={}, server_address=None):
    global config, rig_id, config_ini
    vars = {
        'rig_id': rig_id,
        'email': config_ini['email'],
        'api_key': config_ini['api_key'],
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
            logger.info("Gather the state")
            state_info = get_state_info()
        except Exception as e:
            logger.error("Error getting state: %s" % str(e))
        try:
            tasks = call_server_api("client/stat_and_task", state_info)
        except Exception as e:
            logger.error("Error with send stat and run task: %s" % e)
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
    get_config()
    if not 'rig_id' in config:
        logging.error("Cannot load config from server. Exiting")
        exit(800)
    logging.info("Running as worker '%s'" % config['worker'])
    socketHandler = BestMinerSocketHandler(config['logger']['server'], config['logger']['port'])
    logger.addHandler(socketHandler)

    restart_miner()

    stat_manager = StatisticManager()
    stat_manager.start()
    task_manager = threading.Thread(target=task_manager)
    task_manager.start()

'''


def send_stat_and_got_task()
    * отправить текущее состояние
        * workersInfo(Temp, fan, config), miner (state, config, hashrate, screen, lastUpdate)
    * response.
    * response.task
        * Задания: restartMiner, reboot, runMiner
    * threading.Timer(10, send_stat_and_got_task).start()

def monitor_miner(start_periodic=False, timout_seconds=30)
    miner_config = config['minerConfig']
    # https://docs.python.org/3/library/subprocess.html#subprocess.Popen.poll
    if not task_run(miner_config['process_name'])
        server_log("Miner not run", leve="WARN")
    timout_seconds = config['miner_monitoring']['timeout']
    if start_periodic
        threading.Timer(timout_seconds, monitor_miner(...)).start()

def reboot
    * server_log ("going reboot")
    * run shutdown command

'''
