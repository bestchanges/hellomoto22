'''
Выбор валюты для майнинга
* считаем сколько монет в час можем получить на данном оборудовании
N = (t*R*H)/(D*2^32)
где:
N - доход в монетах
t - период майнинга в секундах (например, сутки = 86400)
R - награда за блок в монетах
H - хэшрейт в секунду (например, 1ГХш = 1000000000)
D - сложность

доход с фермы в сутки = ( мощность фермы / мощность сети ) Х кол-во монет в сутки
кол-во монет в сутки  = ( 86400 Х монет за блок ) / время нахождения блока
86400 - секунд в сутки


'''
import collections
import json
import operator

def calc_daily_income(coin_data, user_hashrates):
    # print(coin_data)
    period = 86400
    algorith = coin_data["algorithm"]
    net_hash = coin_data["nethash"]
    if not algorith in user_hashrates.keys():
        raise Exception("Unknown hashrate for algoritm '%s'" % algorith)
    user_hash = user_hashrates[algorith]
    block_time = float(coin_data["block_time"])
    # некорректно считает например для FTC difficulty == 56
    # block_time = coin_data["difficulty"] / net_hash
    block_reward = float(coin_data["block_reward"])
    user_ratio = user_hash / net_hash
    net_reward = period / block_time * block_reward
    user_reward = net_reward * user_ratio
    return user_reward

def main():
    whattomine_data = json.load(open('coins1.json'))

    user_hashrates = {
        'Ethash': 135.5e6,
        'Groestl': 123e6,
        'X11Gost': 43.2e6,
        'CryptoNight': 2580,
        'Equihash': 1620,
        'Lyra2REv2': 121800e3,
        'NeoScrypt': 3000e3,
        'LBRY': 1020e6,
        'Blake (2b)': 5940e6,
        'Blake (14r)': 9300e6,
        'Pascal': 500e3,
        'Skunkhash': 108e6,
        'Myriad-Groestl': 123e6,  # no data in calc
    }
    coin_income = {}
    for coin_name,coin_data in whattomine_data['coins'].items():
        currency = coin_data["tag"]
        if currency == 'NICEHASH':
            continue
        income_currency = calc_daily_income(coin_data, user_hashrates)
        exchange_rate = coin_data['exchange_rate']
        income_btc = income_currency * exchange_rate
        coin_income[currency] = income_btc
        print("For %10s income %10.05f BTC/day (%f %s with rate %.6f)" % (
            currency, income_btc, income_currency, currency, exchange_rate))
    coins_rated = collections.OrderedDict(sorted(coin_income.items(), key=operator.itemgetter(1)))
    for coin, income in coins_rated.items():
        print("%10s %10.5f" % (coin, income))



if __name__ == "__main__":
    main()