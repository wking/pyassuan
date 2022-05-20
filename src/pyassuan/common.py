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

import re
import socket as _socket
from array import array
from typing import (
    TYPE_CHECKING, Dict, List, Optional, Tuple, TypeVar, Union
)

from pyassuan import LOG
from pyassuan.error import AssuanError

if TYPE_CHECKING:
    from logging import Logger
    from socket import socket as Socket

__all__: List[str] = [
    'LINE_LENGTH',
    'Request',
    'Response',
    '_encode',
    '_decode',
    '_to_str',
    '_to_bytes',
    'error_response',
    'receive_fds',
    'send_fds',
]

# Template bytes / str so input / output types match
T = TypeVar('T', bytes, str)

# Handle when bytes / str concrete types
VarText = Union[bytes, str]

LINE_LENGTH = 1002  # 1000 + [CR,]LF
ENCODE_PATTERN = '(' + '|'.join(['%', '\r', '\n']) + ')'
REQUEST_REGEXP = re.compile(r'^(\w+)( *)(.*)\Z')


def _encode(data: T) -> T:
    if isinstance(data, bytes):
        regexp = re.compile(ENCODE_PATTERN.encode('utf-8'))
    else:
        regexp = re.compile(ENCODE_PATTERN)
    return regexp.sub(lambda x: _to_hex(x.group()), data)


def _decode(data: T) -> T:
    if isinstance(data, bytes):
        regexp = re.compile(b'(%[0-9A-Fa-f]{2})')
    else:
        regexp = re.compile('(%[0-9A-Fa-f]{2})')
    return regexp.sub(lambda x: _from_hex(x.group()), data)


def _from_hex(code: T) -> T:
    if isinstance(code, bytes):
        char = chr(int(code[1:], 16)).encode('utf-8')
    else:
        char = chr(int(code[1:], 16))
    return char


def _to_hex(char: T) -> T:
    if isinstance(char, bytes):
        hx = '%{:02X}'.format(ord(char)).encode('utf-8')
    else:
        hx = '%{:02X}'.format(ord(char))
    return hx


def _to_str(data: VarText) -> str:
    return data.decode() if isinstance(data, bytes) else data


def _to_bytes(data: VarText) -> bytes:
    return data.encode('utf-8') if isinstance(data, str) else data


class Request:
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
          ...self.socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        pyassuan.error.AssuanError: 170 Invalid request
    """

    def __init__(
        self,
        command: str = '',  # HACK: this is not designed correctly
        parameters: Optional[VarText] = None,
        encoded: bool = False
    ) -> None:
        """Initialize a client request object."""
        self.command = command
        self.parameters = parameters
        self.encoded = encoded

    def __str__(self) -> str:
        """Provide string representation of request."""
        if self.parameters:
            parameters = _to_str(self.parameters)
            if self.encoded:
                encoded_parameters = parameters
            else:
                encoded_parameters = _encode(parameters)
            return f"{self.command} {encoded_parameters}"
        return self.command

    def __bytes__(self) -> bytes:
        """Provide bytes representation of request."""
        if self.parameters:
            parameters = _to_str(self.parameters)
            if self.encoded:
                encoded_parameters = parameters
            else:
                encoded_parameters = _encode(parameters)
            return f"{self.command} {encoded_parameters}".encode('utf-8')
        return self.command.encode('utf-8')

    def from_bytes(self, line: bytes) -> None:
        """Convert request from bytes."""
        if len(line) > 1000:  # TODO: byte-vs-str and newlines?
            raise AssuanError(message='Line too long')

        string = line.decode('utf-8')
        match = REQUEST_REGEXP.match(string)
        if not match:
            raise AssuanError(message='Invalid request')

        self.command = match.group(1)
        if match.group(3):
            if match.group(2):
                self.parameters = _decode(match.group(3))
            else:
                raise AssuanError(message='Invalid request')
        else:
            self.parameters = None


class Response:
    """Represent a server response.

    http://www.gnupg.org/documentation/manuals/assuan/Server-responses.html

    .. doctest::

        >>> r = Response(message='OK')
        >>> str(r)
        'OK'
        >>> r = Response(message='ERR', parameters='1 General error')
        >>> str(r)
        'ERR 1 General error'
        >>> bytes(r)
        b'ERR 1 General error'
        >>> r.from_bytes(b'OK')
        >>> r.message
        'OK'
        >>> print(r.parameters)
        None
        >>> r.from_bytes(b'ERR 1 General error')
        >>> r.message
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

    messages: Dict[str, str] = {
        'O': 'OK',
        'E': 'ERR',
        'S': 'S',
        '#': '#',
        'D': 'D',
        'I': 'INQUIRE',
    }

    def __init__(
        self,
        message: str = '',  # HACK: this is not designed correctly
        parameters: Optional[VarText] = None,
    ) -> None:
        """Inititialize a server response."""
        self.message = message
        self.parameters = parameters

    def __str__(self) -> str:
        """Provide string representation."""
        if self.parameters:
            params = _to_str(self.parameters)
            return f"{self.message} {_encode(params)}"
        return self.message

    def __bytes__(self) -> bytes:
        """Provide bytes representation."""
        if self.parameters:
            if self.message == 'D':
                dparams = _to_bytes(self.parameters)
                return b' '.join((b'D', dparams))
            else:
                sparams = _to_str(self.parameters)
                return f"{self.message} {_encode(sparams)}".encode('utf-8')
        return self.message.encode('utf-8')

    def from_bytes(self, line: bytes) -> None:
        """Convert from bytes."""
        if len(line) > 1000:  # TODO: byte-vs-str and newlines?
            raise AssuanError(message='Line too long')

        string = line.decode('utf-8')
        if string.startswith('D'):
            self.command = s = 'D'
        else:
            s = string[0]

        try:
            message = self.messages[s]
        except KeyError:
            raise AssuanError(message='Invalid response')

        self.message = message
        if message == 'D':  # data
            self.parameters = _decode(string[2:])
        elif message == '#':  # comment
            self.parameters = _decode(string[2:])
        else:
            match = REQUEST_REGEXP.match(string)
            if not match:
                raise AssuanError(message='Invalid request')
            if match.group(3):
                if match.group(2):
                    self.parameters = _decode(match.group(3))
                else:
                    raise AssuanError(message='Invalid request')
            else:
                self.parameters = None


def error_response(error: AssuanError) -> 'Response':
    """Provide error response.

    .. doctest::

        >>> from pyassuan.error import AssuanError
        >>> error = AssuanError(1)
        >>> response = error_response(error)
        >>> print(response)
        ERR 1 General error
    """
    return Response(message='ERR', parameters=str(error))


def send_fds(
    socket: 'Socket',
    msg: Optional[bytes] = None,
    fds: Optional[List[int]] = None,
    logger: Optional['Logger'] = LOG
) -> int:
    """Send a file descriptor over a Unix socket using ``sendmsg``.

    ``sendmsg`` suport requires Python >= 3.3.

    Code from
    http://docs.python.org/dev/library/socket.html#socket.socket.sendmsg

    Assuan equivalent is
    http://www.gnupg.org/documentation/manuals/assuan/Client-code.html#function-assuan_005fsendfd
    """
    if msg is None:
        msg = b''.join(
            [b'# descriptors in flight: ', str(fds).encode('utf-8'), b'\n']
        )

    if logger is not None:
        logger.debug(f"sending file descriptors {fds} down {socket}")

    arr = array('i', fds) if fds else array('i')
    return socket.sendmsg(
        [msg],
        [(_socket.SOL_SOCKET, _socket.SCM_RIGHTS, arr)],
    )


def receive_fds(
    socket: 'Socket',
    msglen: int = 200,
    maxfds: int = 10,
    logger: Optional['Logger'] = LOG
) -> Tuple[bytes, List[int]]:
    """Recieve file descriptors using ``recvmsg``.

    ``recvmsg`` suport requires Python >= 3.3.

    Code from http://docs.python.org/dev/library/socket.html

    Assuan equivalent is
    http://www.gnupg.org/documentation/manuals/assuan/Client-code.html#fun_002dassuan_005freceivedfd
    """
    fds = array('i')  # Array of ints
    msg, ancdata, flags, addr = socket.recvmsg(
        msglen, _socket.CMSG_LEN(maxfds * fds.itemsize)
    )
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if (
            cmsg_level == _socket.SOL_SOCKET
            and cmsg_type == _socket.SCM_RIGHTS
        ):
            # Append data, ignoring any truncated integers at the end.
            fds.frombytes(
                cmsg_data[: len(cmsg_data) - (len(cmsg_data) % fds.itemsize)]
            )
    if logger is not None:
        logger.debug(
            f"receiving file descriptors {fds} from {socket} ({msg!r})"
        )
    return (msg, list(fds))
