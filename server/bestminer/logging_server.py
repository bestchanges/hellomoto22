import json
import logging
import logging.handlers
import os
import pickle
import re
import socketserver
import struct
import threading
from threading import Thread

# name of logger that is root for client loggers (need to make stop propogate processing to the main root logger)
from bestminer.models import *

CLIENT_LOGGER_ROOT = "client_logger"

my_logger = logging.getLogger(__name__)


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


LIMIT_LOG_ENTRIES_TO_KEEP = 30
# uuid -> LimitedList
rigs_memory_log = {}


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """Handler for a streaming logging request.
    This handler captures all logging output client send to the server
    To distinguish client id additional parameter shall be set on the client side via LogFilter


    class LogFilter(logging.Filter):
    def filter(self, record):
        record.rig_id = config['rig_id']
        return True

    All records missing that parameter will be ignored

    """

    def __init__(self, request, client_address, server):
        self.uuid = None
        thread_name = threading.current_thread().name
        my_logger.info("Thread={} client={} uuid={} connection opened".format(thread_name, client_address, self.uuid))
        super().__init__(request, client_address, server)

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            try:
                chunk = self.connection.recv(4)
            except Exception as e:
                thread_name = threading.current_thread().name
                my_logger.info("Thread={} client={} uuid={} connection closed: {}".format(thread_name, self.client_address, self.uuid, e))

                # TODO: close client log!
                break
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return pickle.loads(data)

    def handleLogRecord(self, record):
        if not hasattr(record, 'rig_id'):
            # ignore unauthorized message
            return
        if self.uuid is None:
            self.uuid = record.rig_id
            thread_name = threading.current_thread().name
            my_logger.info("Thread={} client={} uuid={} UUID detected".format(thread_name, self.client_address, self.uuid))

        # logger name record.name defined in client. Sample: 'miner_ewbf', 'statistic'
        # combine logging_server root logger and record logger received from client
        name = CLIENT_LOGGER_ROOT + "." + record.name
        # the handlers for these loggers is set up in class LoggingServer
        # possible DDOS with millions record.name instances for abusing getLogger()
        # TODO: check if rig_id is registered rig
        client_logger = logging.getLogger(name)
        try:
            client_logger.handle(record)
        except Exception as e:
            # we shall be able to keep working
            my_logger.error("Error processing log from client: %s" % e)
            pass

        # save tail of the log
        history_logger = logging.getLogger("history_logger")
        history_logger.handle(record)


class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    """
    Simple TCP socket-based logging receiver suitable for testing.
    TODO: make it accept many connection
    """

    allow_reuse_address = 1

    def __init__(self, host='0.0.0.0',
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                 handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                       [], [],
                                       self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort


def get_rig(rig_uuid):
    rig = Rig.objects.get(uuid=rig_uuid)
    return rig


class SaveClientLogHistory(logging.Handler):
    '''
    keep client log in memeory for last LIMIT_LOG_ENTRIES_TO_KEEP lines.
    store LOG files for specified uuids
    '''
    def __init__(self, level=logging.NOTSET):
        self.uuid_file_logs = {}
        super().__init__(level)

    def add_loggable_uuid(self, uuid):
        if uuid in self.uuid_file_logs.keys():
            # already added
            return
        self.uuid_file_logs[uuid] = None

    def handle(self, record):
        global rigs_memory_log
        rig_uuid = str(record.rig_id)

        # temporaly logs all clients
        self.add_loggable_uuid(rig_uuid)

        # file log
        if rig_uuid in self.uuid_file_logs.keys():
            value = self.uuid_file_logs[rig_uuid]
            if value is None:
                dirs = os.path.join('log', 'clients')
                if not os.path.exists(dirs):
                    os.makedirs(dirs)
                client_log_file_logger = logging.getLogger("client_logger_{}".format(rig_uuid))
                log_filename = "{}.log".format(rig_uuid)
                h = logging.handlers.TimedRotatingFileHandler(os.path.join(dirs, log_filename), when='midnight', backupCount=7,
                                                              encoding='utf-8')
                #log_file = open(os.path.join(dirs, log_filename), 'a', encoding='utf-8')
                #h = logging.StreamHandler(log_file)
                h.setFormatter(logging.Formatter('%(asctime)-10s|%(name)-10s|%(levelname)s|%(message)s)'))
                client_log_file_logger.addHandler(h)
                client_log_file_logger.propagate = False
                self.uuid_file_logs[rig_uuid] = client_log_file_logger
                # TODO: close logger then client disconnects!
            client_log_file_logger = self.uuid_file_logs[rig_uuid]
            client_log_file_logger.handle(record)

        # in-memory log
        if rig_uuid in rigs_memory_log.keys():
            list = rigs_memory_log[rig_uuid]
        else:
            list = LimitedList(limit=LIMIT_LOG_ENTRIES_TO_KEEP)
            rigs_memory_log[rig_uuid] = list
        list.append(record.msg)


class ClientStatisticHandler(logging.Handler):
    '''
    Get statistic info from client and process it
    '''

    def handle(self, record):
        line = record.msg
        rig_uuid = record.rig_id
        # UPTIME={"hms": "20:44:38", "sec": 74678, "rebooted": "2017-11-18 02:09:36+03:00", "rebooted_epoch": 1510960176}
        if "UPTIME" in line:
            mark, jsons = line.split("=", 1)
            data = json.loads(jsons)
            if data['rebooted_epoch']:
                rebooted = datetime.datetime.fromtimestamp(data['rebooted_epoch'])
                rig_state = get_rig(rig_uuid)
                rig_state.rebooted = rebooted
                rig_state.save()


# TODO: remove it. This function was moved to client side
class ClaymoreHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        # local data for gather multiline records
        self.local = threading.local()
        super().__init__(level)

    def handle(self, record):
        line = record.msg
        rig_uuid = record.rig_id
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

        m = re.findall('AMD Cards available: (\d+)', line)
        if len(m) > 0:
            self.local.expect_amd_cards = int(m[0])
            self.local.amd_cards = []
        if hasattr(self.local, 'expect_amd_cards'):
            m = re.findall('GPU #(\d+) recognized as (Radeon RX) (470/570)', line)
            if len(m) > 0:
                gpu_num, family, model = m[0]
                gpu_num = int(gpu_num)
                if family == 'Radeon RX':
                    if model == '470/570':
                        card = GPU_RX_470
                    else:
                        card = GPU_RX
                else:
                    my_logger.error('Cannot recognize AMD family %s' % family)
                if card:
                    self.local.amd_cards.append(card)
                if gpu_num == self.local.expect_amd_cards - 1:
                    rig = Rig.objects.get(uuid=rig_uuid)
                    rig.system_gpu_list = self.local.amd_cards
                    rig.save()
                    del self.local.amd_cards
                    del self.local.expect_amd_cards

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
                rig_state = get_rig(rig_uuid)
                rig_state.hashrate[algorithm] = {'value': val, 'units': units}
                rig_state.save()

        # now take care about temperaure and fan speed
        # GPU0 t=55C fan=52%, GPU1 t=50C fan=43%, GPU2 t=57C fan=0%, GPU3 t=52C fan=48%, GPU4 t=49C fan=0%, GPU5 t=53C
        m = re.findall('GPU(\d+) t=(\d+). fan=(\d+)', line)
        if len(m) > 0:
            temps = []
            fans = []
            for num, temp, fan in m:
                temps.append(temp)
                fans.append(fan)
            rig_state = get_rig(rig_uuid)
            rig_state.cards_temp = temps
            rig_state.cards_fan = fans
            rig_state.save()
        return True


class EwbfHandler(logging.Handler):
    def handle(self, record):
        line = record.msg
        rig_uuid = record.rig_id
        # Total speed: 1763 Sol/s
        m = re.findall('Total speed: ([\d\.]+) ([\w\/]+)', line)
        if len(m) > 0:
            value, units = m[0]
            val = float(value)
            algorithm = 'Equihash'
            rig_state = get_rig(rig_uuid)
            rig_state.hashrate[algorithm] = {'value': val, 'units': units}
            rig_state.save()
        # Temp: GPU0: 60C GPU1: 66C GPU2: 56C GPU3: 61C GPU4: 61C GPU5: 59C
        m = re.findall('GPU(\d+): (\d+)C', line)
        if len(m) > 0:
            temps = []
            for num, temp in m:
                temps.append(temp)
            rig_state = get_rig(rig_uuid)
            rig_state.cards_temp = temps
            rig_state.save()
        # GPU0: 284 Sol/s GPU1: 301 Sol/s GPU2: 289 Sol/s GPU3: 299 Sol/s GPU4: 297 Sol/s GPU5: 293 Sol/s
        return True


class LoggingServer(Thread):
    def __init__(self):
        super().__init__()
        self.tcpserver = LogRecordSocketReceiver()
        self.clients_log_files = {} # uuid->{filename='uuid'}
        client_logs_root_logger = logging.getLogger(CLIENT_LOGGER_ROOT)
        client_logs_root_logger.propagate = False

        history_logger = logging.getLogger("history_logger")
        history_logger.addHandler(SaveClientLogHistory())
        history_logger.propagate = False

        statistic_logger = logging.getLogger(client_logs_root_logger.name + ".statistic")
        statistic_logger.addHandler(ClientStatisticHandler())
        claymore_logger = logging.getLogger(client_logs_root_logger.name + ".miner_claymore")
        claymore_logger.addHandler(ClaymoreHandler())
        ewbf_logger = logging.getLogger(client_logs_root_logger.name + ".miner_ewbf")
        ewbf_logger.addHandler(EwbfHandler())

    def run(self):
        my_logger.info('Starting TCP logging server...')
        self.tcpserver.serve_until_stopped()

# if __name__ == '__main__':
#    logging_server()
#    print("Exited from main...")
