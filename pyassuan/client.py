# Copyright (C) 2012 W. Trevor King <wking@drexel.edu>
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

import logging as _logging
import socket as _socket
import sys as _sys

from . import LOG as _LOG
from . import common as _common
from . import error as _error


class AssuanClient (object):
    """A single-threaded Assuan client based on the `development suggestions`_

    .. _development suggestions:
      http://www.gnupg.org/documentation/manuals/assuan/Client-code.html
    """
    def __init__(self, name, logger=_LOG, use_sublogger=True,
                 close_on_disconnect=False):
        self.name = name
        if use_sublogger:
            logger = _logging.getLogger('{}.{}'.format(logger.name, self.name))
        self.logger = logger
        self.close_on_disconnect = close_on_disconnect
        self.input = self.output = self.socket = None

    def connect(self, socket_path=None):
        if socket_path:
            self.logger.info(
                'connect to Unix socket at {}'.format(socket_path))
            self.socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.socket.connect(socket_path)
            self.input = self.socket.makefile('rb')
            self.output = self.socket.makefile('wb')
        else:
            if not self.input:
                self.logger.info('read from stdin')
                self.input = _sys.stdin.buffer
            if not self.output:
                self.logger.info('write to stdout')
                self.output = _sys.stdout.buffer

    def disconnect(self):
        if self.close_on_disconnect:
            self.logger.info('disconnecting')
            if self.input is not None:
                self.input.close()
                self.input = None
            if self.output is not None:
                self.output.close()
                self.output = None
            if self.socket is not None:
                self.socket.shutdown(_socket.SHUT_RDWR)
                self.socket.close()
                self.socket = None

    def raise_error(self, error):
        self.logger.error(str(error))
        raise(error)

    def read_response(self):
        line = self.input.readline()
        if not line:
            self.raise_error(
                _error.AssuanError(message='IPC accept call failed'))
        if len(line) > _common.LINE_LENGTH:
            self.raise_error(
                _error.AssuanError(message='Line too long'))
        if not line.endswith(b'\n'):
            self.logger.info('S: {}'.format(line))
            self.raise_error(
                _error.AssuanError(message='Invalid response'))
        line = line[:-1]  # remove trailing newline
        response = _common.Response()
        try:
            response.from_bytes(line)
        except _error.AssuanError as e:
            self.logger.error(str(e))
            raise
        self.logger.info('S: {}'.format(response))
        return response

    def _write_request(self, request):
        self.logger.info('C: {}'.format(request))
        self.output.write(bytes(request))
        self.output.write(b'\n')
        try:
            self.output.flush()
        except IOError:
            raise        

    def make_request(self, request, response=True, expect=['OK']):
        self._write_request(request=request)
        if response:
            return self.get_responses(requests=[request], expect=expect)

    def get_responses(self, requests=None, expect=['OK']):
        responses = list(self.responses())
        if responses[-1].type == 'ERR':
            eresponse = responses[-1]
            fields = eresponse.parameters.split(' ', 1)
            code = int(fields[0])
            if len(fields) > 1:
                message = fields[1].strip()
            else:
                message = None
            error = _error.AssuanError(code=code, message=message)
            if requests is not None:
                error.requests = requests
            error.responses = responses
            raise error
        if expect:
            assert responses[-1].type in expect, [str(r) for r in responses]
        data = []
        for response in responses:
            if response.type == 'D':
                data.append(response.parameters)
        if data:
            data = b''.join(data)
        else:
            data = None
        return (responses, data)

    def responses(self):
        while True:
            response = self.read_response()
            yield response
            if response.type not in ['S', '#', 'D']:
                break

    def send_data(self, data=None, response=True, expect=['OK']):
        """Iterate through requests necessary to send ``data`` to a server.

        http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html
        """
        requests = []
        if data:
            encoded_data = _common.encode(data)
            start = 0
            stop = min(_common.LINE_LENGTH-4, len(encoded_data)) # 'D ', CR, CL
            self.logger.debug('sending {} bytes of encoded data'.format(
                    len(encoded_data)))
            while stop > start:
                d = encoded_data[start:stop]
                request = _common.Request(
                    command='D', parameters=encoded_data[start:stop],
                    encoded=True)
                requests.append(request)
                self.logger.debug('send {} byte chunk'.format(stop-start))
                self._write_request(request=request)
                start = stop
                stop = start + min(_common.LINE_LENGTH-4,
                                   len(encoded_data) - start)
        request = _common.Request('END')
        requests.append(request)
        self._write_request(request=request)
        if response:
            return self.get_responses(requests=requests, expect=expect)

    def send_fds(self, fds):
        """Send a file descriptor over a Unix socket.
        """
        msg = '# descriptors in flight: {}\n'.format(fds)
        self.logger.info('C: {}'.format(msg.rstrip('\n')))
        msg = msg.encode('ascii')
        return _common.send_fds(
            socket=self.socket, msg=msg, fds=fds, logger=None)

    def receive_fds(self, msglen=200, maxfds=10):
        """Receive file descriptors over a Unix socket.
        """
        msg,fds = _common.receive_fds(
            socket=self.socket, msglen=msglen, maxfds=maxfds, logger=None)
        msg = str(msg, 'utf-8')
        self.logger.info('S: {}'.format(msg.rstrip('\n')))
        return fds
