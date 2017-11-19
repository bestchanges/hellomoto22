# staticstic from various exchanges using BitEx library
# https://github.com/nlsdfnbch/bitex

from bitex.api.REST.rest import KrakenREST

k = KrakenREST()
k.query('GET','public/Depth', params={'pair': 'BTCUSD'})
