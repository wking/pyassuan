"""Checking some things."""

from pyassuan import common


r = common.Response(message='OK')
assert str(r) == 'OK'

r = common.Response(message='ERR', parameters='1 General error')
assert str(r) == 'ERR 1 General error'
assert bytes(r) == b'ERR 1 General error'

r.from_bytes(b'OK')
assert r.message == 'OK'

print(r.parameters is None)

r.from_bytes(b'ERR 1 General error')
assert r.message == 'ERR'
assert r.parameters == '1 General error'

# r.from_bytes(b' invalid')
# Traceback (most recent call last):
#   ...
# pyassuan.error.AssuanError: 76 Invalid response
# r.from_bytes(b'in-valid')
# Traceback (most recent call last):
#   ...
# pyassuan.error.AssuanError: 76 Invalid response
