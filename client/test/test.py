# ETH: GPU0 23.739 Mh/s, GPU1 23.766 Mh/s, GPU2 23.663 Mh/s, GPU3 23.746 Mh/s
# DCR: GPU0 743.812 Mh/s, GPU1 750.343 Mh/s, GPU2 570.301 Mh/s, GPU3 581.771 Mh/s, GPU4 744.605 Mh/s, GPU5 454.443 Mh/s
# ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22
# DCR - Total Speed: 3890.426 Mh/s, Total Shares: 8655, Rejected: 96

import re

lines = [
'2017-12-14 12:22:21,787|server_logger|INFO|Temp: GPU0 57C GPU1 51C GPU2 49C',
'2017-12-14 12:22:21,787|server_logger|INFO|GPU0: 285 Sol/s GPU1: 288 Sol/s GPU2: 281 Sol/s',
'Temp: GPU0: 50C GPU1: 28C GPU2: 39C',
]
# TODO: temp do not parse due to special codes for color switching before temperature value
for line in lines:
    m = re.findall('GPU[^\d]*(\d+)[^\d]*(\d+)C', line)
    for num, temp in m:
        print(num,temp)

exit()

line = "ETH: GPU0 23.739 Mh/s, GPU1 23.766 Mh/s, GPU2 23.663 Mh/s, GPU3 23.746 Mh/s"
m = re.findall('ETH: GPU(\d+) ([\d\.]+) ', line)
sum = 0
for (pos, str_val) in m:
    i = float(str_val)
    print(i)
    sum=sum+i

line = "ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22"
m = re.findall('ETH - Total Speed: ([\d\.]+) ', line)
print(m)
print(sum)