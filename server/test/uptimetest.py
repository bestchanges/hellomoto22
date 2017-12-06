import datetime
from time import gmtime, localtime

import uptime

time = uptime.boottime()
tz_offset = datetime.datetime.now() - datetime.datetime.utcnow()
utcboottime = time - tz_offset
print(time, tz_offset, utcboottime)