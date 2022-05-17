# Copyright (C) 2012 W. Trevor King <wking@tremily.us>
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

"""Items common to both the client and server."""

import array
import re as re
import socket as _socket

from . import LOG, error


LINE_LENGTH = 1002  # 1000 + [CR,]LF
_ENCODE_PATTERN = '(' + '|'.join(['%', '\r', '\n']) + ')'
_ENCODE_STR_REGEXP = re.compile(_ENCODE_PATTERN)
_ENCODE_BYTE_REGEXP = re.compile(_ENCODE_PATTERN.encode('ascii'))
_DECODE_STR_REGEXP = re.compile('(%[0-9A-Fa-f]{2})')
_DECODE_BYTE_REGEXP = re.compile(b'(%[0-9A-Fa-f]{2})')
_REQUEST_REGEXP = re.compile(r'^(\w+)( *)(.*)\Z')


def encode(data):
    r"""Encode data.

    >>> encode('It grew by 5%!\n')
    'It grew by 5%25!%0A'
    >>> encode(b'It grew by 5%!\n')
    b'It grew by 5%25!%0A'
    """
    if isinstance(data, bytes):
        regexp = _ENCODE_BYTE_REGEXP
    else:
        regexp = _ENCODE_STR_REGEXP
    return regexp.sub(lambda x: to_hex(x.group()), data)


def decode(data):
    r"""Decode data.

    >>> decode('%22Look out!%22%0AWhere%3F')
    '"Look out!"\nWhere?'
    >>> decode(b'%22Look out!%22%0AWhere%3F')
    b'"Look out!"\nWhere?'
    """
    if isinstance(data, bytes):
        regexp = _DECODE_BYTE_REGEXP
    else:
        regexp = _DECODE_STR_REGEXP
    return regexp.sub(lambda x: from_hex(x.group()), data)


def from_hex(code):
    r"""Convert hex string.

    >>> from_hex('%22')
    '"'
    >>> from_hex('%0A')
    '\n'
    >>> from_hex(b'%0A')
    b'\n'
    """
    c = chr(int(code[1:], 16))
    if isinstance(code, bytes):
        c = c.encode('ascii')
    return c


def to_hex(char):
    r"""Convert string to hex.

    >>> to_hex('"')
    '%22'
    >>> to_hex('\n')
    '%0A'
    >>> to_hex(b'\n')
    b'%0A'
    """
    hx = '%{:02X}'.format(ord(char))
    if isinstance(char, bytes):
        hx = hx.encode('ascii')
    return hx


class Request(object):
    """Represent a client request.

    http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html

    .. doctest::
        >>> r = Request(command='BYE')
        >>> str(r)
        'BYE'
        >>> r = Request(command='OPTION', parameters='testing at 5%')
        >>> str(r)
        'OPTION testing at 5%25'
        >>> bytes(r)
        b'OPTION testing at 5%25'
        >>> r.from_bytes(b'BYE')
        >>> r.command
        'BYE'
        >>> print(r.parameters)
        None
        >>> r.from_bytes(b'OPTION testing at 5%25')
        >>> r.command
        'OPTION'
        >>> print(r.parameters)
        testing at 5%
        >>> r.from_bytes(b' invalid')
        Traceback (most recent call last):
          ...
        pyassuan.error.AssuanError: 170 Invalid request
        >>> r.from_bytes(b'in-valid')
        Traceback (most recent call last):
          ...
        pyassuan.error.AssuanError: 170 Invalid request
    """

    def __init__(self, command=None, parameters=None, encoded=False):
        """Initialize a client request object."""
        self.command = command
        self.parameters = parameters
        self.encoded = encoded

    def __str__(self):
        """Provide string representation of request."""
        if self.parameters:
            if self.encoded:
                encoded_parameters = self.parameters
            else:
                encoded_parameters = encode(self.parameters)
            return '{} {}'.format(self.command, encoded_parameters)
        return self.command

    def __bytes__(self):
        """Provide bytes representation of request."""
        if self.parameters:
            if self.encoded:
                encoded_parameters = self.parameters
            else:
                encoded_parameters = encode(self.parameters)
            return '{} {}'.format(self.command, encoded_parameters).encode(
                'utf-8'
            )
        return self.command.encode('utf-8')

    def from_bytes(self, line):
        """Convert request from bytes."""
        if len(line) > 1000:  # TODO: byte-vs-str and newlines?
            raise error.AssuanError(message='Line too long')
        line = str(line, encoding='utf-8')
        match = _REQUEST_REGEXP.match(line)
        if not match:
            raise error.AssuanError(message='Invalid request')
        self.command = match.group(1)
        if match.group(3):
            if match.group(2):
                self.parameters = decode(match.group(3))
            else:
                raise error.AssuanError(message='Invalid request')
        else:
            self.parameters = None


class Response:
    """Represent a server response.

    http://www.gnupg.org/documentation/manuals/assuan/Server-responses.html

    .. doctest::
        >>> r = Response(type='OK')
        >>> str(r)
        'OK'
        >>> r = Response(type='ERR', parameters='1 General error')
        >>> str(r)
        'ERR 1 General error'
        >>> bytes(r)
        b'ERR 1 General error'
        >>> r.from_bytes(b'OK')
        >>> r.type
        'OK'
        >>> print(r.parameters)
        None
        >>> r.from_bytes(b'ERR 1 General error')
        >>> r.type
        'ERR'
        >>> print(r.parameters)
        1 General error
        >>> r.from_bytes(b' invalid')
        Traceback (most recent call last):
          ...
        pyassuan.error.AssuanError: 76 Invalid response
        >>> r.from_bytes(b'in-valid')
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
        """Inititialize a server response."""
        self.type = type
        self.parameters = parameters

    def __str__(self):
        """Provide string representation."""
        if self.parameters:
            return '{} {}'.format(self.type, encode(self.parameters))
        return self.type

    def __bytes__(self):
        """Provide bytes representation."""
        if self.parameters:
            if self.type == 'D':
                return b' '.join((b'D', self.parameters))
            else:
                return '{} {}'.format(
                    self.type, encode(self.parameters)
                ).encode('utf-8')
        return self.type.encode('utf-8')

    def from_bytes(self, line):
        """Convert from bytes."""
        if len(line) > 1000:  # TODO: byte-vs-str and newlines?
            raise error.AssuanError(message='Line too long')
        if line.startswith(b'D'):
            self.command = t = 'D'
        else:
            line = str(line, encoding='utf-8')
            t = line[0]
        try:
            type = self.types[t]
        except KeyError:
            raise error.AssuanError(message='Invalid response')
        self.type = type
        if type == 'D':  # data
            self.parameters = decode(line[2:])
        elif type == '#':  # comment
            self.parameters = decode(line[2:])
        else:
            match = _REQUEST_REGEXP.match(line)
            if not match:
                raise error.AssuanError(message='Invalid request')
            if match.group(3):
                if match.group(2):
                    self.parameters = decode(match.group(3))
                else:
                    raise error.AssuanError(message='Invalid request')
            else:
                self.parameters = None


def errorresponse(error):
    """Provide error response.

    >>> from pyassuan.error import AssuanError
    >>> error = AssuanError(1)
    >>> response = errorresponse(error)
    >>> print(response)
    ERR 1 General error
    """
    return Response(type='ERR', parameters=str(error))


def send_fds(socket, msg=None, fds=None, logger=LOG):
    """Send a file descriptor over a Unix socket using ``sendmsg``.

    ``sendmsg`` suport requires Python >= 3.3.

    Code from
    http://docs.python.org/dev/library/socket.html#socket.socket.sendmsg

    Assuan equivalent is
    http://www.gnupg.org/documentation/manuals/assuan/Client-code.html#function-assuan_005fsendfd
    """
    if msg is None:
        msg = b''.join(
            [b'# descriptors in flight: ', str(fds).encode('ascii'), b'\n']
        )

    if logger is not None:
        logger.debug('sending file descriptors {} down {}'.format(fds, socket))

    return socket.sendmsg(
        [msg],
        [(_socket.SOL_SOCKET, _socket.SCM_RIGHTS, array.array('i', fds))],
    )


def receive_fds(socket, msglen=200, maxfds=10, logger=LOG):
    """Recieve file descriptors using ``recvmsg``.

    ``recvmsg`` suport requires Python >= 3.3.

    Code from http://docs.python.org/dev/library/socket.html

    Assuan equivalent is
    http://www.gnupg.org/documentation/manuals/assuan/Client-code.html#fun_002dassuan_005freceivedfd
    """
    fds = array.array('i')  # Array of ints
    msg, ancdata, flags, addr = socket.recvmsg(
        msglen, _socket.CMSG_LEN(maxfds * fds.itemsize)
    )
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if (
            cmsg_level == _socket.SOL_SOCKET
            and cmsg_type == _socket.SCM_RIGHTS
        ):
            # Append data, ignoring any truncated integers at the end.
            fds.fromstring(
                cmsg_data[: len(cmsg_data) - (len(cmsg_data) % fds.itemsize)]
            )
    if logger is not None:
        logger.debug(
            'receiving file descriptors {} from {} ({})'.format(
                fds, socket, msg
            )
        )
    return (msg, list(fds))
