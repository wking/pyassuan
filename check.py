"""Checking some things."""

import re
from typing import TypeVar, Union

VarText = Union[bytes, str]

T = TypeVar('T', bytes, str)

LINE_LENGTH = 1002  # 1000 + [CR,]LF
ENCODE_PATTERN = '(' + '|'.join(['%', '\r', '\n']) + ')'
REQUEST_REGEXP = re.compile(r'^(\w+)( *)(.*)\Z')


# @overload
# def encode(data: bytes) -> bytes: ...
#
#
# @overload
# def encode(data: str) -> str: ...


def encode(data: T) -> T:
    r"""Encode data.

    .. doctest::

        >>> encode('It grew by 5%!\n')
        'It grew by 5%25!%0A'
        >>> encode(b'It grew by 5%!\n')
        b'It grew by 5%25!%0A'
    """
    if isinstance(data, bytes):
        regexp = re.compile(ENCODE_PATTERN.encode('utf-8'))
    else:
        regexp = re.compile(ENCODE_PATTERN)
    return regexp.sub(lambda x: to_hex(x.group()), data)


# @overload
# def decode(data: bytes) -> bytes: ...
#
#
# @overload
# def decode(data: str) -> str: ...


def decode(data: T) -> T:
    r"""Decode data.

    .. doctest::

        >>> decode('%22Look out!%22%0AWhere%3F')
        '"Look out!"\nWhere?'
        >>> decode(b'%22Look out!%22%0AWhere%3F')
        b'"Look out!"\nWhere?'
    """
    if isinstance(data, bytes):
        regexp = re.compile(b'(%[0-9A-Fa-f]{2})')
    else:
        regexp = re.compile('(%[0-9A-Fa-f]{2})')
    return regexp.sub(lambda x: from_hex(x.group()), data)


# @overload
# def from_hex(code: bytes) -> bytes: ...
#
#
# @overload
# def from_hex(code: str) -> str: ...


def from_hex(code: T) -> T:
    r"""Convert hex to char.

    .. doctest::

        >>> from_hex('%22')
        '"'
        >>> from_hex('%0A')
        '\n'
        >>> from_hex(b'%0A')
        b'\n'
    """
    c = chr(int(code[1:], 16))
    if isinstance(code, bytes):
        c = c.encode('utf-8')  # type: ignore
    return c  # type: ignore


# @overload
# def to_hex(char: bytes) -> bytes: ...
#
#
# @overload
# def to_hex(char: str) -> str: ...


def to_hex(char: T) -> T:
    r"""Convert char to hex.

    .. doctest::

        >>> to_hex('"')
        '%22'
        >>> to_hex('\n')
        '%0A'
        >>> to_hex(b'\n')
        b'%0A'
    """
    hx = '%{:02X}'.format(ord(char))
    if isinstance(char, bytes):
        hx = hx.encode('utf-8')  # type: ignore
    return hx


assert encode('It grew by 5%!\n') == 'It grew by 5%25!%0A'
assert encode(b'It grew by 5%!\n') == b'It grew by 5%25!%0A'

assert decode('%22Look out!%22%0AWhere%3F') == '"Look out!"\nWhere?'
assert decode(b'%22Look out!%22%0AWhere%3F') == b'"Look out!"\nWhere?'

assert from_hex('%22') == '"'
assert from_hex('%0A') == '\n'
assert from_hex(b'%0A') == b'\n'

assert to_hex('"') == '%22'
assert to_hex('\n') == '%0A'
assert to_hex(b'\n') == b'%0A'
