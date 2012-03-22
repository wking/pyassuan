# Copyright

"""Items common to both the client and server
"""

import re as _re

from . import error as _error


_ENCODE_REGEXP = _re.compile(
    '(' + '|'.join(['%', '\r', '\n']) + ')')
_DECODE_REGEXP = _re.compile('(%[0-9A-F]{2})')
_REQUEST_REGEXP = _re.compile('^(\w+)( *)(.*)\Z')


def encode(string):
    r"""

    >>> encode('It grew by 5%!\n')
    'It grew by 5%25!%0A'
    """   
    return _ENCODE_REGEXP.sub(
        lambda x : to_hex(x.group()), string)

def decode(string):
    r"""

    >>> decode('%22Look out!%22%0AWhere%3F')
    '"Look out!"\nWhere?'
    """
    return _DECODE_REGEXP.sub(
        lambda x : from_hex(x.group()), string)

def from_hex(code):
    r"""

    >>> from_hex('%22')
    '"'
    >>> from_hex('%0A')
    '\n'
    """
    return chr(int(code[1:], 16))

def to_hex(char):
    r"""

    >>> to_hex('"')
    '%22'
    >>> to_hex('\n')
    '%0A'
    """
    return '%{:02X}'.format(ord(char))


class Request (object):
    """A client request

    http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html

    >>> r = Request(command='BYE')
    >>> str(r)
    'BYE'
    >>> r = Request(command='OPTION', parameters='testing at 5%')
    >>> str(r)
    'OPTION testing at 5%25'
    >>> r.from_string('BYE')
    >>> r.command
    'BYE'
    >>> print(r.parameters)
    None
    >>> r.from_string('OPTION testing at 5%25')
    >>> r.command
    'OPTION'
    >>> print(r.parameters)
    testing at 5%
    >>> r.from_string(' invalid')
    Traceback (most recent call last):
      ...
    pyassuan.error.AssuanError: 170 Invalid request
    >>> r.from_string('in-valid')
    Traceback (most recent call last):
      ...
    pyassuan.error.AssuanError: 170 Invalid request
    """
    def __init__(self, command=None, parameters=None):
        self.command = command
        self.parameters = parameters

    def __str__(self):
        if self.parameters:
            return '{} {}'.format(self.command, encode(self.parameters))
        return self.command

    def from_string(self, string):
        if len(string) > 1000:  # TODO: byte-vs-str and newlines?
            raise _error.AssuanError(message='Line too long')
        match = _REQUEST_REGEXP.match(string)
        if not match:
            raise _error.AssuanError(message='Invalid request')
        self.command = match.group(1)
        if match.group(3):
            if match.group(2):
                self.parameters = decode(match.group(3))
            else:
                raise _error.AssuanError(message='Invalid request')
        else:
            self.parameters = None


class Response (object):
    """A server response

    http://www.gnupg.org/documentation/manuals/assuan/Server-responses.html

    >>> r = Response(type='OK')
    >>> str(r)
    'OK'
    >>> r = Response(type='ERR', parameters='1 General error')
    >>> str(r)
    'ERR 1 General error'
    >>> r.from_string('OK')
    >>> r.type
    'OK'
    >>> print(r.parameters)
    None
    >>> r.from_string('ERR 1 General error')
    >>> r.type
    'ERR'
    >>> print(r.parameters)
    1 General error
    >>> r.from_string(' invalid')
    Traceback (most recent call last):
      ...
    pyassuan.error.AssuanError: 76 Invalid response
    >>> r.from_string('in-valid')
    Traceback (most recent call last):
      ...
    pyassuan.error.AssuanError: 76 Invalid response
    """
    types = {
        'O': 'OK',
        'E': 'ERR',
        'S': 'S',
        '#': '#',
        'D': 'D',
        'I': 'INQUIRE',
        }

    def __init__(self, type=None, parameters=None):
        self.type = type
        self.parameters = parameters

    def __str__(self):
        if self.parameters:
            return '{} {}'.format(self.type, encode(self.parameters))
        return self.type

    def from_string(self, string):
        if len(string) > 1000:  # TODO: byte-vs-str and newlines?
            raise _error.AssuanError(message='Line too long')
        try:
            type = self.types[string[0]]
        except KeyError:
            raise _error.AssuanError(message='Invalid response')
        self.type = type
        if type == 'D':  # data
            self.parameters = decode(string[2:])
        elif type == '#':  # comment
            self.parameters = decode(string[2:])
        else:
            match = _REQUEST_REGEXP.match(string)
            if not match:
                raise _error.AssuanError(message='Invalid request')
            if match.group(3):
                if match.group(2):
                    self.parameters = decode(match.group(3))
                else:
                    raise _error.AssuanError(message='Invalid request')
            else:
                self.parameters = None


def error_response(error):
    """

    >>> from pyassuan.error import AssuanError
    >>> error = AssuanError(1)
    >>> response = error_response(error)
    >>> print(response)
    ERR 1 General error
    """
    return Response(type='ERR', parameters=str(error))
