import calendar
import datetime
import re
import subprocess


def get_reboot_time():
    '''
    :return: timestamp of reboot
    '''
    cpu_ids = []
    proc = subprocess.run("wmic os get lastbootuptime", stdout=subprocess.PIPE, encoding="ASCII")
    for line in proc.stdout.split():
        if line == 'LastBootUpTime':
            # skip head
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
        p = calendar.timegm(p.utctimetuple())
        return p
    return None


print(get_reboot_time())
