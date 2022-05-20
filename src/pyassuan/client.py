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

"""PyAssuan client for interfacing with GPG Assuan."""

import logging
import socket as _socket
import sys
from typing import (
    TYPE_CHECKING, BinaryIO, Generator, List, Optional, Tuple
)

from pyassuan import LOG, common
from pyassuan.common import Request, Response
from pyassuan.error import AssuanError

if TYPE_CHECKING:
    from logging import Logger
    from socket import socket as Socket


class AssuanClient:
    """A single-threaded Assuan client based on the `development suggestions`_.

    .. _development suggestions:

        http://www.gnupg.org/documentation/manuals/assuan/Client-code.html
    """

    def __init__(
        self,
        name: str,
        logger: 'Logger' = LOG,
        use_sublogger: bool = True,
        close_on_disconnect: bool = False
    ) -> None:
        """Initialize pyassuan client."""
        self.name = name

        if use_sublogger:
            logger = logging.getLogger('{}.{}'.format(logger.name, self.name))
        self.logger = logger

        self.close_on_disconnect = close_on_disconnect
        self.socket: Optional['Socket'] = None
        self.intake: Optional[BinaryIO] = None
        self.outtake: Optional[BinaryIO] = None

    def connect(self, socket_path: Optional[str] = None) -> None:
        """Connect."""
        if socket_path:
            self.logger.info(
                'connect to Unix socket at {}'.format(socket_path)
            )
            self.socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.socket.connect(socket_path)
            self.intake = self.socket.makefile('rb')
            self.outtake = self.socket.makefile('wb')
        else:
            if not self.intake:
                self.logger.info('read from stdin')
                self.intake = sys.stdin.buffer
            if not self.outtake:
                self.logger.info('write to stdout')
                self.outtake = sys.stdout.buffer

    def disconnect(self) -> None:
        """Disconnect."""
        if self.close_on_disconnect:
            self.logger.info('disconnecting')
            if self.intake is not None:
                self.intake.close()
                self.intake = None
            if self.outtake is not None:
                self.outtake.close()
                self.outtake = None
            if self.socket is not None:
                self.socket.shutdown(_socket.SHUT_RDWR)
                self.socket.close()
                self.socket = None

    # OPTIMIZE: log from error module instead
    # def raiseerror(self, error: AssuanError) -> None:
    #     """Raise error."""
    #     self.logger.error(str(error))
    #     raise (error)

    def read_response(self) -> 'Response':
        """Read response."""
        line = self.intake.readline() if self.intake else None
        if not line:
            raise AssuanError(message='IPC accept call failed')
        if len(line) > common.LINE_LENGTH:
            raise AssuanError(message='Line too long')
        if not line.endswith(b'\n'):
            self.logger.info('S: {!r}'.format(line))
            raise AssuanError(message='Invalid response')
        line = line[:-1]  # remove trailing newline
        response = Response()
        try:
            response.from_bytes(line)
        except AssuanError as e:
            self.logger.error(str(e))
            raise
        self.logger.info('S: {}'.format(response))
        return response

    def _write_request(self, request: 'Request') -> None:
        self.logger.info('C: {}'.format(request))
        if self.outtake is not None:
            self.outtake.write(bytes(request))
            self.outtake.write(b'\n')
            try:
                self.outtake.flush()
            except IOError:
                raise
        else:
            raise

    def make_request(
        self,
        request: 'Request',
        response: bool = True,
        expect: List[str] = ['OK']
    ) -> Optional[Tuple[List['Response'], Optional[bytes]]]:
        """Make request."""
        self._write_request(request=request)
        if response:
            return self.get_responses(requests=[request], expect=expect)
        return None

    def get_responses(
        self,
        requests: Optional[List['Request']] = None,
        expect: List[str] = ['OK']
    ) -> Tuple[List['Response'], Optional[bytes]]:
        """Get responses."""
        responses = list(self.responses)
        if responses != [] and responses[-1].message == 'ERR':
            err_response = responses[-1]
            if err_response.parameters:
                fields = common._to_str(err_response.parameters).split(' ', 1)
                code = int(fields[0])
            else:
                fields = []
                code = 1
            if len(fields) > 1:
                message = fields[1].strip()
            else:
                message = None
            error = AssuanError(code=code, message=message)
            if requests is not None:
                setattr(error, 'requests', requests)
            setattr(error, 'responses', responses)
            raise error
        if expect:
            # XXX: should be if/else/fail
            assert responses[-1].message in expect, [str(r) for r in responses]
        rsps = []
        for response in responses:
            if response.message == 'D':
                if response.parameters:
                    rsps.append(common._to_bytes(response.parameters))
        print(rsps)
        data = b''.join(rsps) if rsps != [] else None
        return (responses, data)

    @property
    def responses(self) -> Generator['Response', None, None]:
        """Iterate responses."""
        while True:
            response = self.read_response()
            yield response
            if response.message not in ['S', '#', 'D']:
                break

    def __send_data(
        self,
        data: Optional[str] = None,
        response: bool = True,
        expect: List[str] = ['OK']
    ) -> Optional[Tuple[List['Response'], Optional[bytes]]]:
        """Iterate through requests necessary to send ``data`` to a server.

        http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html
        """
        requests = []
        if data:
            encoded_data = common._encode(data)
            start = 0
            stop = min(
                common.LINE_LENGTH - 4, len(encoded_data)
            )  # 'D ', CR, CL
            self.logger.debug(
                'sending {} bytes of encoded data'.format(len(encoded_data))
            )
            while stop > start:
                # d = encoded_data[start:stop]
                request = Request(
                    command='D',
                    parameters=encoded_data[start:stop],
                    encoded=True,
                )
                requests.append(request)
                self.logger.debug('send {} byte chunk'.format(stop - start))
                self._write_request(request=request)
                start = stop
                stop = start + min(
                    common.LINE_LENGTH - 4, len(encoded_data) - start
                )
        request = Request('END')
        requests.append(request)
        self._write_request(request=request)
        if response:
            return self.get_responses(requests=requests, expect=expect)
        return None

    def __send_fds(self, fds: List[int]) -> int:
        """Send file descriptors over a Unix socket."""
        if self.socket:
            _msg = '# descriptors in flight: {}\n'.format(fds)
            self.logger.info('C: {}'.format(_msg.rstrip('\n')))
            msg = _msg.encode('utf-8')
            return common.send_fds(
                socket=self.socket, msg=msg, fds=fds, logger=None
            )
        raise AssuanError(
            code=279, message='No output source for IPC'
        )

    def __recieve_fds(self, msglen: int = 200, maxfds: int = 10) -> List[int]:
        """Receive file descriptors over a Unix socket."""
        if self.socket:
            msg, fds = common.receive_fds(
                socket=self.socket, msglen=msglen, maxfds=maxfds, logger=None
            )
            string = msg.decode('utf-8')
            self.logger.info('S: {}'.format(string.rstrip('\n')))
            return fds
        raise AssuanError(
            code=278, message='No input source for IPC'
        )
