import datetime
import json
import pickle
import logging
import logging.handlers
import re
import globals
import socketserver
import struct
from threading import Thread

from models import RigState, Rig

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
rigs_logs = {}

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

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            chunk = self.connection.recv(4)
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

        # combine logging_server root logger and record logger recieved from client
        name = "logging_server." + record.name
        # possible DDOS with millions record.name instances for abusing getLogger()
        # TODO: check if rig_id is registered rig
        logger = logging.getLogger(name)
        try:
            logger.handle(record)
        except Exception as e:
            # we shall be able to keep working
            print("Error processing log from cleint: %s" % e)
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

    def __init__(self, host='localhost',
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


def get_rig_state_object(rig_uuid):
    rig = Rig.objects.get(uuid=rig_uuid)
    result = RigState.objects(rig=rig)
    if len(result) == 1:
        rig_state = result[0]
    else:
        rig_state = RigState()
        rig_state.rig = rig
        rig_state.save()
    return rig_state


class SaveClientLogHistory(logging.Filter):
    def filter(self, record):
        global rigs_logs
        rig_uuid = str(record.rig_id)
        if rig_uuid in rigs_logs.keys():
            list = rigs_logs[rig_uuid]
        else:
            list = LimitedList(limit=LIMIT_LOG_ENTRIES_TO_KEEP)
            rigs_logs[rig_uuid] = list
        list.append(record.msg)


class ClientStatisticFilter(logging.Filter):
    '''
    Get statistic info from client and process it
    '''
    def filter(self, record):
        line = record.msg
        rig_uuid = record.rig_id
        #UPTIME={"hms": "20:44:38", "sec": 74678, "rebooted": "2017-11-18 02:09:36+03:00", "rebooted_epoch": 1510960176}
        if "UPTIME" in line:
            mark, jsons = line.split("=", 1)
            data = json.loads(jsons)
            if data['rebooted_epoch']:
                rebooted = datetime.datetime.fromtimestamp(data['rebooted_epoch'])
                rig_state = get_rig_state_object(rig_uuid)
                rig_state.rebooted = rebooted
                rig_state.save()


class ClaymoreFilter(logging.Filter):
    def filter(self, record):
        # hashrate info
        # ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22
        # DCR - Total Speed: 3890.426 Mh/s, Total Shares: 8655, Rejected: 96
        line = record.msg
        rig_uuid = record.rig_id
        m = re.findall('(\w+) - Total Speed: ([\d\.]+) ([\w\/]+)', line)
        if len(m) > 0:
            (code, value, units) = m[0]
            val = float(value)
            if code == "ETH":
                algorithm = 'Ethash'
            if code == "DCR":
                # take into consideration when mining single Blake
                algorithm = 'Blake (14r)'
            rig_state = get_rig_state_object(rig_uuid)
            rig_state.hashrate[algorithm] = { 'value': val, 'units': units }
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
            rig_state = get_rig_state_object(rig_uuid)
            rig_state.cards_temp = temps
            rig_state.cards_fan = fans
            rig_state.save()
        return True


class LoggingServer(Thread):
    def __init__(self):
        super().__init__()
        self.tcpserver = LogRecordSocketReceiver()
        root_logger = logging.getLogger("logging_server")
        root_logger.propagate = False
        self.root_logger = root_logger
        history_logger = logging.getLogger("history_logger")
        history_logger.addFilter(SaveClientLogHistory())
        history_logger.propagate = False

        claymore_logger = logging.getLogger(root_logger.name + ".miner_claymore")
        statistic_logger = logging.getLogger(root_logger.name + ".statistic")
        statistic_logger.addFilter(ClientStatisticFilter())
        claymore_logger.addFilter(ClaymoreFilter())

    def run(self):
        logging.info('Starting TCP logging server...')
        self.tcpserver.serve_until_stopped()

# if __name__ == '__main__':
#    logging_server()
#    print("Exited from main...")