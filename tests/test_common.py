# Copyright (C) 2012-2018 W. Trevor King <wking@tremily.us>
#
# This file is part of pyassuan.
#
# pyassuan is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pyassuan is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# pyassuan.  If not, see <http://www.gnu.org/licenses/>.
# type: ignore

import doctest
# import unittest

from pyassuan import common

# NOTE: moved doctests here as users should rarely need to access theses


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(common))
    return tests


def test_encode():
    assert common._encode('It grew by 5%!\n') == 'It grew by 5%25!%0A'
    assert common._encode(b'It grew by 5%!\n') == b'It grew by 5%25!%0A'


def test_decode():
    assert (
        common._decode('%22Look out!%22%0AWhere%3F') == '"Look out!"\nWhere?'
    )
    assert (
        common._decode(b'%22Look out!%22%0AWhere%3F') == b'"Look out!"\nWhere?'
    )


def test_from_hex():
    assert common._from_hex('%22') == '"'
    assert common._from_hex('%0A') == '\n'
    assert common._from_hex(b'%0A') == b'\n'


def test_to_hex():
    assert common._to_hex('"') == '%22'
    assert common._to_hex('\n') == '%0A'
    assert common._to_hex(b'\n') == b'%0A'


def test_to_str():
    assert isinstance(common._to_str(b'A byte string'), str)
    assert isinstance(common._to_str('A string'), str)


def test_to_bytes():
    assert isinstance(common._to_bytes(b'A byte string'), bytes)
    assert isinstance(common._to_bytes('A string'), bytes)
