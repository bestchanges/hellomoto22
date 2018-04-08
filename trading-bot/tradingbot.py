from datetime import datetime, timedelta
from mongoengine import *
from poloniex import Poloniex
import pprint

poloniex_configurations = {
    'egor.fedorov@gmail.com': {
        'APIKEY': 'YLNDY1WS-LRUDLWDP-YEBKYKO2-ZUQHJO07',
        'SECRET': 'bf95c7f41ee308b1b7b953a4595aff0f2ecf4e9235516942ae2ebe3c8f7a1bc97fa5fe0ee14e4ffbbec524637769d43f9955c4450430d28a1daefb6d61ff92e7',
    }
}

poloniex_account = 'egor.fedorov@gmail.com'
settings = poloniex_configurations[poloniex_account]

connect("okminer")

TX_STATUSES = ['SKIP', 'IN_PROCESS', '']


class TransactionFromPoolToExchange(Document):
    txid = StringField(max_length=300, primary_key=True)
    from_address = StringField(max_length=300)
    to_address = StringField(max_length=300)
    currency = StringField(max_length=10)
    amount = FloatField(precision=22, rounding='ROUND_FLOOR')
    confirmations = IntField()
    created = DateTimeField()
    accepted_by_exchange = BooleanField()
    state = StringField(max_length=20, choices=TX_STATUSES)


class PoolAccount(Document):
    name = StringField(max_length=100)
    account = StringField(max_length=100)
    password = StringField(max_length=100)
    currency = StringField(max_length=10)
    servers = ListField(StringField(max_length=100))


class ExchangeAccount(Document):
    name = StringField(max_length=100)
    supported_pairs = ListField(StringField(max_length=21))
    meta = {'allow_inheritance': True}


class PoloniexExchangeAccount(ExchangeAccount):
    name = StringField(max_length=100)
    api_key = StringField(max_length=100)
    api_value = StringField(max_length=100)


pp = pprint.PrettyPrinter(indent=4, width=100)

polo = Poloniex(settings['APIKEY'], settings['SECRET'])
ticker = polo.returnTicker()['BTC_ETH']
balances = polo.returnBalances()
coin = 'DCR'
print(balances[coin])
print(polo.return24hVolume()['BTC_DCR'])

# проверяем поступления за последние N минут
check_intraval_minutes = 15000
to_time = datetime.now()
from_time = to_time - timedelta(minutes=check_intraval_minutes)
deposits = polo.returnDeposits(start=1509397242, end=to_time.timestamp())
for deposit in deposits:
    pp.pprint(deposit.items())
    print(deposit)
    if deposit['status'] != 'COMPLETE':
        # do not take this deposit until it complete
        continue
    tx = TransactionFromPoolToExchange(
        txid=deposit['txid'],
        to_address=deposit['address'],
        currency=coin,
        amount=deposit['amount'],
        accepted_by_exchange=(deposit['status'] == 'COMPLETE'),
    )

    tx = TransactionFromPoolToExchange.objects.query(txid=deposit['txid'])
    print(tx)
    exit()
    tx = TransactionFromPoolToExchange()
    tx.to_address = deposit['address']
    tx.save(force_insert=True)
    tx.reload()

ticker = polo.returnTicker()['BTC_DCR']
# print(ticker)
sum = tx.amount
rate = ticker['highestBid']

btc_sum = sum * rate
# poloniex total must be at least 0.0001 BTC
minumum_total_trade = 0.0001
print("SUM %s %s in BTC %.6f (the minimum is %.6f)" % (sum, coin, btc_sum, minumum_total_trade))

#order = polo.sell('BTC_DCR', rate, sum, fillOrKill=1)
#print(order)
del polo

# poloniex()

# print(polo.returnBalances())
