import calendar
import datetime
import json
import logging
import os, subprocess
import platform
import pprint
import re
import shlex
import threading
import time
import urllib
from logging import handlers
from queue import Queue, Empty
from urllib import request
from uuid import uuid5

import requests
import uuid
import psutil

from zipfile import ZipFile

import sys
import uptime as uptime

logging.basicConfig(
    format='%(asctime)-10s|%(name)-10s|%(levelname)-4s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('client')
server_only_logger = logging.getLogger('server_logger')
server_only_logger.setLevel(logging.INFO)


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



server_logger_handler = None  # will be created after log file received
miner_monitor = None
miner_monitor_tasks = Queue()

config_ini = load_config_ini()
config = {}
stat_manager = None
task_manager = None

def get_system_id():
    '''
    :return: array of CPUIDs
    '''
    system = platform.system()
    if system == 'Windows':
        components = []
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
            components.append(line)
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
            components.append(line)
        if components:
            return ','.join(components)
    elif system == 'Linux':
        # PROC: sudo dmidecode -t 4 | grep ID | sed 's/.*ID://;s/ //g'
        # 76060100FFFBEBBF
        components = []
        proc = subprocess.run("sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g'", shell=True,
                              stdout=subprocess.PIPE)
        id = proc.stdout.decode().strip()
        if id:
            components.append(id)
        # MB: sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g' | tr '[:upper:]' '[:lower:]'
        # czc8493tp3
        # MAC: ifconfig | grep eth0 | awk '{print $NF}' | sed 's/://g'
        # 002264bbfc3a
        proc = subprocess.run("sudo dmidecode --string baseboard-serial-number | sed 's/.*ID://;s/ //g'", shell=True,
                              stdout=subprocess.PIPE)
        id = proc.stdout.decode().strip()
        if id:
            components.append(id)
        if components:
            return ','.join(components)
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
        if newconfig['rig_id']:
            # Save config from server as new
            config = newconfig
            save_config()
        return config
    except requests.exceptions.ConnectionError as e:
        logging.error("Cannot connect to server %s" % e)
        return None


def save_config():
    if not config["server"]:
        raise Exception("Broken config. Not saving")
    file = open("settings.json", "w")
    json.dump(config, file, indent=2, sort_keys=True)


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
    logger.info("Downloading latest program from {}".format(url))
    request.urlretrieve(url, zip_filename)
    with ZipFile(zip_filename, 'r') as myzip:
        myzip.extractall(update_dir)
    os.remove(zip_filename)
    logger.info("Download complete. Going to stop miner and install update.")

    global miner_monitor
    if miner_monitor:
        miner_monitor.shutdown()
    logging.shutdown()
    os._exit(200)


class LogReaderThread(threading.Thread):

    def __init__(self, log_fp, miner_manager):
        """
        When input finished notify miner_manager

        :return:
        :param log_fp: File handler shall be opened and ready to read
        :param miner_manager:
        """
        super().__init__(name="LogReader")
        self.log_fp = log_fp
        self.miner_manager = miner_manager

    def run(self):
        while True:
            line = self.log_fp.readline()
            # Once all lines are read this just returns ''
            # until the file changes and a new line appears
            if line:
                try:
                    self.miner_manager.handle_log_line(line.strip())
                except:
                    logger.warning("Exception handle log: %s" % sys.exc_info()[0])
                    pass
            else:
                # check if miner_process is alive. If not then exit
                # A None value indicates that the process hasn't terminated yet
                if self.miner_manager.is_run():
                    # wait for new line
                    time.sleep(0.1)
                    pass
                else:
                    return # EXIT FROM this THREAD


class MinerManager():
    """
    1. run miner
    2. get statistics
    3. check miner health
    4. restart miner if required
    5. log from miner to given logger
    6. shutdown miner
    """

    def __init__(self, miner_config):
        self.miner_process = None
        self.miner_config = miner_config
        self.logger = server_only_logger
        self.current_hashrate = {}  # 'Algo' => { hashrate: 123.56, when: 131424322}
        self.target_hashrate = {}  # 'Algo' => { hashrate: 123.56, when: 131424322}
        self.compute_units_info = []  #
        self.compute_units_fan = []
        self.compute_units_temp = []
        self.pu_types = []
        self.is_shutdown = False

    def __start_miner_process(self):
        pass

    def is_run(self):
        # https://docs.python.org/3/library/subprocess.html#popen-objects
        return self.miner_process is not None and self.miner_process.poll() is None

    def kill_miner(self):
        """
        if miner process is run when finish it
        :return:
        """
        if self.is_run():
            # Kill currently running process
            self.logger.info("Terminating process ...")
            process = psutil.Process(self.miner_process.pid)
            for proc in process.children(recursive=True):
                proc.kill()
            process.kill()
            time.sleep(2)
            self.logger.debug("Process has stopped. Process run: {}".format(self.is_run()))

    def shutdown(self):
        self.logger.info("Shutdown miner")
        self.is_shutdown = True
        self.kill_miner()

    def restart_miner(self):
        """
        cancel shutdown state (if was set)
        start miner again
        :return:
        """
        self.is_shutdown = False
        self.run_miner()

    def get_miner_version(self, miner_dir):
        miner_version_filename = os.path.join(miner_dir, 'version.txt')
        file = open(miner_version_filename, 'r', encoding='ascii')
        return file.readline().strip()

    def download_miner_if_required(self):
        # Let's download miner if required to update
        miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        if not os.path.exists(miner_dir) or self.get_miner_version(miner_dir) != self.miner_config['miner_version']:
            url = "http://%s/static/miners/%s.zip" % (config['server'], self.miner_config["miner_directory"])
            self.logger.info(
                "Downloading miner '%s' (ver %s) from %s" % (
                self.miner_config['miner'], self.miner_config['miner_version'], url))
            zip_file = 'miners/%s.zip' % (self.miner_config["miner_directory"])
            if not os.path.exists('miners'): os.mkdir('miners')
            request.urlretrieve(url, zip_file)
            with ZipFile(zip_file, 'r') as myzip:
                myzip.extractall('miners')
            os.remove(zip_file)
            self.logger.info("Successfully download miner.")

    def handle_log_line(self, line):
        self.logger.info(line)


    # TODO: remove
    def __miner_stdout_reader_thread(self):
        """
        read miner process line by line and give it to logger.
        Also print lines to stdout for user
        :return:
        """
        while True:
            # possble we not need it
            if not self.is_run():
                self.on_miner_terminated()
                break
            line = self.miner_process.stdout.readline()
            if line != '':
                line = line.rstrip()
                print(line)
                self.logger.info(line)
            else:
                self.on_miner_terminated()
                break

    def on_miner_terminated(self):
        """
        this method called when it is detected what miner process no longer alive.
        :return:
        """
        self.logger.info("Miner was terminated")


    def run_miner(self):
        """
        Run miner for specified config.
        Shut down currently runned miner if nessessary.
        Update config file to given miner_config
        Run given miner

        :return:
        """

        if self.is_run():
            self.logger.warning("Miner already run. Not going to run.")
            return

        if self.is_shutdown:
            self.logger.info("Miner was shutdown. Not going to run.")
            return

        self.download_miner_if_required()

        miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        miner_exe = self.miner_config["miner_exe"]
        args = shlex.split(self.miner_config["miner_command_line"])
        args.insert(0, miner_exe)
        self.logger.info("Going to run miner from '%s' %s" % (miner_dir, " ".join(args)))
        env = self.miner_config["env"]
        full_env = {**os.environ, **env}

        if self.miner_config['read_output']:
            # we've got some problem using stdout=PIPE because of system buffer of stdout (about 8k).
            # thus we cannot read stdout in realtime, which is quite useless.
            # Workaround is to parse miner's log (at least claymore and ewbf write logs)
            self.miner_process = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                  bufsize=0,
                                                  env=full_env, cwd=miner_dir, universal_newlines=True)

            log_reader = LogReaderThread(self.miner_process.stdout, self)
            log_reader.start()

        else:
            self.miner_process = subprocess.Popen(args, shell=True, stdout=None, stderr=None, bufsize=0,
                                                  env=full_env, cwd=miner_dir, universal_newlines=True)

        self.logger.info("Runned miner process %s PID %s" % (miner_exe, self.miner_process.pid))


class ClaymoreMinerManager(MinerManager):

    def handle_log_line(self, line):

        # NVIDIA Cards available: 3
        # AMD Cards available: 8
        m = re.findall('(AMD|NVIDIA) Cards available:', line)
        if len(m) > 0:
            family = m[0]
            if family == 'AMD':
                if 'amd' not in self.pu_types:
                    self.pu_types.append('amd')
            elif family == 'NVIDIA':
                if 'nvidia' not in self.pu_types:
                    self.pu_types.append('nvidia')
            if stat_manager:
                stat_manager.send_stat()

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
                    card = 'amd_rx_470'
                else:
                    card = 'amd_rx'
            else:
                self.logger.warning('Cannot recognize AMD family %s' % family)
            if gpu_num == 0:
                self.compute_units_info.clear()
            if card:
                self.compute_units_info.append(card)

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
                card = 'nvidia_gtx_{}_{}gb'.format(model, memory)
            else:
                self.logger.warning('Cannot recognize NVIDIA family %s' % family)
            if gpu_num == 0:
                self.compute_units_info.clear()
            if card:
                self.compute_units_info.append(card)

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
            elif code == "ZEC":
                # take into consideration when mining single Blake
                algorithm = 'Equihash'
            else:
                self.logger.warning("Unexpected currency code={}".format(code))
                algorithm = None
            if algorithm:
                self.current_hashrate[algorithm] = hashrate_from_units(val, units)

        # now take care about temperaure and fan speed
        # GPU0 t=55C fan=52%, GPU1 t=50C fan=43%, GPU2 t=57C fan=0%, GPU3 t=52C fan=48%, GPU4 t=49C fan=0%, GPU5 t=53C
        m = re.findall('GPU(\d+) t=(\d+). fan=(\d+)', line)
        if len(m) > 0:
            temps = []
            fans = []
            for num, temp, fan in m:
                temps.append(temp)
                fans.append(fan)
            self.compute_units_temp = temps
            self.compute_units_fan = fans

        # TODO: detect error level of message
        self.logger.info(line.strip())

        return True

    def run_miner(self):

        if self.is_run():
            self.logger.warning("Miner already run. Not going to run.")
            return

        if self.is_shutdown:
            self.logger.info("Miner was shutdown. Not going to run.")
            return

        # before we start at first delete old miner.log from miner dir
        # miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        # log_file = os.path.join(miner_dir, 'log_noappend.txt')
        # if os.path.isfile(log_file):
        #     os.unlink(log_file)

        super().run_miner()
        # give time for miner to start
        time.sleep(6)

        miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        fn = os.path.join(miner_dir, 'log_noappend.txt')
        try:
            fp = open(fn, 'r', encoding='866', newline='')
            # actually no need to seek. in claymore if filename has "noappend" the log will be truncated at start
            fp.seek(0, 2)
        except:
            self.logger.error("Cannot open miner log %s" % fn)
            self.kill_miner()
            self.on_miner_terminated()
            return

        log_reader = LogReaderThread(fp, self)
        log_reader.start()


class EwbfMinerManager(MinerManager):

    def handle_log_line(self, line):
        # Total speed: 1763 Sol/s
        m = re.findall('Total speed: ([\d\.]+) ([\w\/]+)', line)
        if len(m) > 0:
            value, units = m[0]
            val = float(value)
            algorithm = 'Equihash'
            self.current_hashrate[algorithm] = hashrate_from_units(val, units)

        # Temp: GPU0: 60C GPU1: 66C GPU2: 56C GPU3: 61C GPU4: 61C GPU5: 59C
        # Temp: GPU0: 56C GPU1: 52C GPU2: 50C
        # TODO: temp do not parse due to special codes for color switching before temperature value
        m = re.findall('GPU(\d+): (\d+)C', line)
        if len(m) > 0:
            temps = []
            for num, temp in m:
                temps.append(temp)
            self.compute_units_temp = temps
        # GPU0: 284 Sol/s GPU1: 301 Sol/s GPU2: 289 Sol/s GPU3: 299 Sol/s GPU4: 297 Sol/s GPU5: 293 Sol/s
        # GPU0: 281 Sol/s GPU1: 288 Sol/s GPU2: 283 Sol/s

        # TODO: detect error level of message
        self.logger.info(line.strip())

        return True

    def run_miner(self):

        if self.is_run():
            self.logger.warning("Miner already run. Not going to run.")
            return

        if self.is_shutdown:
            self.logger.info("Miner was shutdown. Not going to run.")
            return

        # before we start at first delete old miner.log from miner dir
        miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        log_file = os.path.join(miner_dir, 'miner.log')
        if os.path.isfile(log_file):
            os.unlink(log_file)

        super().run_miner()
        # wait while miner reated log file
        time.sleep(3)

        miner_dir = os.path.join('miners', self.miner_config["miner_directory"])
        fn = os.path.join(miner_dir, 'miner.log')
        try:
            fp = open(fn, 'r', encoding='866', newline='')
        except:
            self.logger.error("Cannot open miner log %s" % fn)
            self.kill_miner()
            self.on_miner_terminated()
            return

        log_reader = LogReaderThread(fp, self)
        log_reader.start()


class DefaultMinerManager(MinerManager):
    pass

def killexternal_miner_process():
    """
    At start we shall check if miner program is not started yet.
    Thus we killing all processes with names of known miner's
    :return:
    """
    miners_proc = [
        'miner.exe',
        'EthDcrMiner64.exe',
    ]
    for proc in psutil.process_iter():
        if proc.name() in miners_proc:
            logger.warning("Killing stale process %s" % proc.name())
            proc.kill()


def hashrate_from_units(value, units):
    unit_measures = {
        "h/s": 1,
        "H/s": 1,
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
    logger.debug("Request server API: {}".format(url))
    #    'application/json'
    response = requests.put(url=url, json=data)
    error_code = response.status_code
    if error_code != 200:
        raise Exception("Got error code %s for url %s" % (error_code, url))
    return response.json()


class TaskManager(threading.Thread):
    def __init__(self, group=None, target=None, args=(), kwargs=None, *, daemon=None):
        self.logger = logging.getLogger("task_manager")
        super().__init__(group, target, "TaskManager", args, kwargs, daemon=daemon)

    def get_and_execute_task(self):
        global miner_monitor_tasks
        self.logger.debug("Check tasks...")
        tasks = call_server_api("client/task")
        for task in tasks:
            task_name = task['task']
            task_data = task['data']
            self.logger.info("Get task '{}'".format(task_name))
            if task_name == "switch_miner":
                miner_config = task_data["miner_config"]
                # save new config in order to start correct miner next run
                config['miner_config'] = miner_config
                save_config()
                miner_monitor_tasks.put(['start_miner', miner_config])
            elif task_name == "self_update":
                self_update()
            elif task_name == "reboot":
                self.logger.info("Receive reboot command. Going to reboot")
                os.system("shutdown /t 7 /r /f")
            else:
                raise Exception("Received unknown task '{}'".format(task_name))

    def run(self):
        request_interval = config["task_manager"]["request_interval_sec"]
        if request_interval is None or request_interval == 0:
            request_interval = 30
        while True:
            try:
                self.get_and_execute_task()
            except:
                self.logger.error("Exception running task: ")
            time.sleep(request_interval)


class StatisticManager(threading.Thread):
    def __init__(self, group=None, target=None, args=(), kwargs=None, *, daemon=None):
        self.logger = logging.getLogger("statistic_manager")
        super().__init__(group, target, "StatisticManager", args, kwargs, daemon=daemon)

    def send_stat(self):
        try:
            miner_manager = miner_monitor.get_current_miner()
            if not miner_manager:
                miner_manager = MinerManager({})

            state_info = {
                "miner": {
                    'is_run': miner_manager.is_run(),
                    'miner_config': miner_manager.miner_config, # currently runned miner config
                },
                "config": config, # current saved config
                "hashrate": {
                    "current": miner_manager.current_hashrate,
                    "target": miner_manager.target_hashrate,
                },
                'pu_fanspeed': miner_manager.compute_units_fan,
                'pu_temperatire': miner_manager.compute_units_temp,
                "processing_units": miner_manager.compute_units_info,
                "pu_types": miner_manager.pu_types,
                "miner_stdout": "",
                "reboot_timestamp": calendar.timegm(get_reboot_time().utctimetuple()),
                'client_version': get_client_version()
            }
            self.logger.info("Send stat...")
            result = call_server_api("client/stat", state_info)
            if result:
                # display several of received data
                status_strs = []
                for prop in ['profit', 'worker', 'mining', ]:
                    if prop in result:
                        status_strs.append("{}: {}".format(prop, result[prop]))
                print('#  ' + ', '.join(status_strs))
        except Exception as e:
            self.logger.error("Exception sending stat: %s" % e)
            pass

    def run(self):
        request_interval = config["statistic_manager"]["request_interval_sec"]
        if request_interval is None or request_interval == 0:
            request_interval = 30
        # for first run wait while statistic will be ready
        time.sleep(request_interval)
        while True:
            try:
                self.send_stat()
            except:
                pass
            time.sleep(request_interval)


class MinerMonitor(threading.Thread):
    def __init__(self):
        self.logger = logging.getLogger("miner_monitor")
        self.miner_manager = None
        super().__init__(name="MinerManagerMonitor")

    def shutdown(self):
        if self.miner_manager:
            self.miner_manager.shutdown()

    def get_current_miner(self):
        return self.miner_manager
    
    def get_miner_manager_for_config(self, aminer_config):
        # запустить майнер хэндлер по типу семейства
        miner_family = aminer_config['miner_family']
        if miner_family == 'claymore':
            miner_manager = ClaymoreMinerManager(aminer_config)
        elif miner_family == 'ewbf':
            miner_manager = EwbfMinerManager(aminer_config)
        else:
            miner_manager = DefaultMinerManager(aminer_config)
        return miner_manager

    def run(self):
        global config


        if "miner_config" in config:
            self.miner_manager = self.get_miner_manager_for_config(config['miner_config'])
            self.miner_manager.run_miner()

        while True:
            # restart if miner died
            try:
                if not self.miner_manager.is_run():
                    self.miner_manager.kill_miner()  # actually not nessessary
                    delay = 8
                    self.logger.warning("Miner not run. Going to restart after %d seconds" % delay)
                    time.sleep(delay)
                    self.miner_manager = self.get_miner_manager_for_config(config['miner_config'])
                    self.miner_manager.run_miner()
                    time.sleep(0.5)
            except:
                self.logger.error("Exception while restart died miner: %s" % sys.exc_info()[0])
                pass
            try:
                new_task = miner_monitor_tasks.get(True, 1)
                task_name = new_task[0]
                if task_name == 'start_miner':
                    miner_config = new_task[1]
                    # first stop current miner
                    if self.miner_manager:
                        self.miner_manager.shutdown()
                    self.miner_manager = self.get_miner_manager_for_config(miner_config)
                    self.miner_manager.run_miner()
                else:
                    self.logger.error("unknown taskname %s" % task_name)
            except Empty:
                continue
            except:
                self.logger.error("Exception when switch miner %s " % sys.exc_info()[0])
                pass


if __name__ == "__main__":
    logger.info("Starting BestMiner")

    killexternal_miner_process()
    register_on_server()
    if not 'rig_id' in config:
        logging.error("Cannot load config from server. Exiting")
        exit()
    logger.info("Running as worker '%s'" % config['worker'])

    if config['client_version'] != get_client_version():
        logger.info("New version available! Going to install version {}".format(config['client_version']))
        self_update()

    task_manager = TaskManager()
    task_manager.start()

    stat_manager = StatisticManager()
    stat_manager.start()

    # server log no need to send to stdout. So config it separately without propogate
    server_logger_handler = BestMinerSocketHandler(config['logger']['server'], config['logger']['port'])
    server_only_logger.addHandler(server_logger_handler)
    server_only_logger.propagate = False

    # TODO: hope it is thread safe to use one socket_handler for several loggers
    # send all log messages to server
    root_logger = logging.getLogger()
    root_logger.addHandler(server_logger_handler)

    miner_monitor = MinerMonitor()
    miner_monitor.start()

