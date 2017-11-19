import re


def test_re1():
    # now take care about temperaure and fan speed
    line='GPU0 t=55C fan=52%, GPU1 t=50C fan=43%, GPU2 t=57C fan=0%, GPU3 t=52C fan=48%, GPU4 t=49C fan=0%, GPU5 t=53C fan=51%, GPU6 t=51C fan=41%, GPU7 t=54C fan=50%'
    print(line)
    m = re.findall('GPU(\d+) t=(\d+). fan=(\d+)', line)
    print(m)
    temps = []
    fans = []
    for num,temp,fan in m:
        temps.append(temp)
        fans.append(fan)
        print(num,temp,fan)
    print(temps)
    print(fans)
    #m = re.findall('GPU(\d+) t=([\d\.]+). fan=(\d+)%%', line)


if __name__ == "__main__":
    test_re1()