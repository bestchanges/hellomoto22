# ETH: GPU0 23.739 Mh/s, GPU1 23.766 Mh/s, GPU2 23.663 Mh/s, GPU3 23.746 Mh/s
# DCR: GPU0 743.812 Mh/s, GPU1 750.343 Mh/s, GPU2 570.301 Mh/s, GPU3 581.771 Mh/s, GPU4 744.605 Mh/s, GPU5 454.443 Mh/s
# ETH - Total Speed: 94.892 Mh/s, Total Shares: 473, Rejected: 0, Time: 05:22
# DCR - Total Speed: 3890.426 Mh/s, Total Shares: 8655, Rejected: 96


import re

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