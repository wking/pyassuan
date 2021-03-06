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

import logging as _logging
import re as _re
import socket as _socket
import sys as _sys
import threading as _threading
import traceback as _traceback

from . import LOG as _LOG
from . import common as _common
from . import error as _error


_OPTION_REGEXP = _re.compile('^-?-?([-\w]+)( *)(=?) *(.*?) *\Z')


class AssuanServer (object):
    """A single-threaded Assuan server based on the `devolpment suggestions`_

    Extend by subclassing and adding ``_handle_XXX`` methods for each
    command you want to handle.

    .. _development suggestions:
      http://www.gnupg.org/documentation/manuals/assuan/Server-code.html
    """
    def __init__(self, name, logger=_LOG, use_sublogger=True,
                 valid_options=None, strict_options=True,
                 single_request=False, listen_to_quit=False,
                 close_on_disconnect=False):
        self.name = name
        if use_sublogger:
            logger = _logging.getLogger('{}.{}'.format(logger.name, self.name))
        self.logger = logger
        if valid_options is None:
            valid_options = []
        self.valid_options = valid_options
        self.strict_options = strict_options
        self.single_request = single_request
        self.listen_to_quit = listen_to_quit
        self.close_on_disconnect = close_on_disconnect
        self.input = self.output = None
        self.options = {}
        self.reset()

    def reset(self):
        self.stop = False
        self.options.clear()

    def run(self):
        self.reset()
        self.logger.info('running')
        self.connect()
        try:
            self.handle_requests()
        finally:
            self.disconnect()
            self.logger.info('stopping')

    def connect(self):
        if not self.input:
            self.logger.info('read from stdin')
            self.input = _sys.stdin.buffer
        if not self.output:
            self.logger.info('write to stdout')
            self.output = _sys.stdout.buffer

    def disconnect(self):
        if self.close_on_disconnect:
            self.logger.info('disconnecting')
            self.input = None
            self.output = None

    def handle_requests(self):        
        self.send_response(_common.Response('OK', 'Your orders please'))
        self.output.flush()
        while not self.stop:
            line = self.input.readline()
            if not line:
                break  # EOF
            if len(line) > _common.LINE_LENGTH:
                self.raise_error(
                    _error.AssuanError(message='Line too long'))
            if not line.endswith(b'\n'):
                self.logger.info('C: {}'.format(line))
                self.send_error_response(
                    _error.AssuanError(message='Invalid request'))
                continue
            line = line[:-1]  # remove the trailing newline
            self.logger.info('C: {}'.format(line))
            request = _common.Request()
            try:
                request.from_bytes(line)
            except _error.AssuanError as e:
                self.send_error_response(e)
                continue
            self.handle_request(request)

    def handle_request(self, request):
        try:
            handle = getattr(
                self, '_handle_{}'.format(request.command))
        except AttributeError:
            self.logger.warn('unknown command: {}'.format(request.command))
            self.send_error_response(
                _error.AssuanError(message='Unknown command'))
            return
        try:
            responses = handle(request.parameters)
            for response in responses:
                self.send_response(response)
        except _error.AssuanError as error:
            self.send_error_response(error)
            return
        except Exception as e:
            self.logger.error(
                'exception while executing {}:\n{}'.format(
                    handle, _traceback.format_exc().rstrip()))
            self.send_error_response(
                _error.AssuanError(message='Unspecific Assuan server fault'))
            return

    def send_response(self, response):
        """For internal use by ``.handle_requests()``
        """
        rstring = str(response)
        self.logger.info('S: {}'.format(response))
        self.output.write(bytes(response))
        self.output.write(b'\n')
        try:
            self.output.flush()
        except IOError:
            if not self.stop:
                raise

    def send_error_response(self, error):
        """For internal use by ``.handle_requests()``
        """
        self.send_response(_common.error_response(error))

    # common commands defined at
    # http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html

    def _handle_BYE(self, arg):
        if self.single_request:
            self.stop = True
        yield _common.Response('OK', 'closing connection')

    def _handle_RESET(self, arg):
        self.reset()

    def _handle_END(self, arg):
        raise _error.AssuanError(
            code=175, message='Unknown command (reserved)')

    def _handle_HELP(self, arg):
        raise _error.AssuanError(
            code=175, message='Unknown command (reserved)')

    def _handle_QUIT(self, arg):
        if self.listen_to_quit:
            self.stop = True
            yield _common.Response('OK', 'stopping the server')
        raise _error.AssuanError(
            code=175, message='Unknown command (reserved)')

    def _handle_OPTION(self, arg):
        """

        >>> s = AssuanServer(name='test', valid_options=['my-op'])
        >>> list(s._handle_OPTION('my-op = 1 '))  # doctest: +ELLIPSIS
        [<pyassuan.common.Response object at ...>]
        >>> s.options
        {'my-op': '1'}
        >>> list(s._handle_OPTION('my-op 2'))  # doctest: +ELLIPSIS
        [<pyassuan.common.Response object at ...>]
        >>> s.options
        {'my-op': '2'}
        >>> list(s._handle_OPTION('--my-op 3'))  # doctest: +ELLIPSIS
        [<pyassuan.common.Response object at ...>]
        >>> s.options
        {'my-op': '3'}
        >>> list(s._handle_OPTION('my-op'))  # doctest: +ELLIPSIS
        [<pyassuan.common.Response object at ...>]
        >>> s.options
        {'my-op': None}
        >>> list(s._handle_OPTION('inv'))
        Traceback (most recent call last):
          ...
        pyassuan.error.AssuanError: 174 Unknown option
        >>> list(s._handle_OPTION('in|valid'))
        Traceback (most recent call last):
          ...
        pyassuan.error.AssuanError: 90 Invalid parameter
        """
        match = _OPTION_REGEXP.match(arg)
        if not match:
            raise _error.AssuanError(message='Invalid parameter')
        name,space,equal,value = match.groups()
        if value and not space and not equal:
            # need either space or equal to separate value
            raise _error.AssuanError(message='Invalid parameter')
        if name not in self.valid_options:
            if self.strict_options:
                raise _error.AssuanError(message='Unknown option')
            else:
                self.logger.info('skipping invalid option: {}'.format(name))
        else:
            if not value:
                value = None
            self.options[name] = value
        yield _common.Response('OK')

    def _handle_CANCEL(self, arg):
        raise _error.AssuanError(
            code=175, message='Unknown command (reserved)')

    def _handle_AUTH(self, arg):
        raise _error.AssuanError(
            code=175, message='Unknown command (reserved)')


class AssuanSocketServer (object):
    """A threaded server spawning ``AssuanServer``\s for each connection
    """
    def __init__(self, name, socket, server, kwargs={}, max_threads=10,
                 logger=_LOG, use_sublogger=True):
        self.name = name
        if use_sublogger:
            logger = _logging.getLogger('{}.{}'.format(logger.name, self.name))
        self.logger = logger
        self.socket = socket
        self.server = server
        assert 'name' not in kwargs, kwargs['name']
        assert 'logger' not in kwargs, kwargs['logger']
        kwargs['logger'] = self.logger
        assert 'use_sublogger' not in kwargs, kwargs['use_sublogger']
        kwargs['use_sublogger'] = True
        if 'close_on_disconnect' in kwargs:
            assert kwargs['close_on_disconnect'] == True, (
                kwargs['close_on_disconnect'])
        else:
            kwargs['close_on_disconnect'] = True
        self.kwargs = kwargs
        self.max_threads = max_threads
        self.threads = []

    def run(self):
        self.logger.info('listen on socket')
        self.socket.listen()
        thread_index = 0
        while True:
            socket,address = self.socket.accept()
            self.logger.info('connection from {}'.format(address))
            self.cleanup_threads()
            if len(threads) > self.max_threads:
                self.drop_connection(socket, address)
            self.spawn_thread(
                'server-thread-{}'.format(thread_index), socket, address)
            thread_index = (thread_index + 1) % self.max_threads

    def cleanup_threads(self):
        i = 0
        while i < len(self.threads):
            thread = self.threads[i]
            thread.join(0)
            if thread.is_alive():
                self.logger.info('joined thread {}'.format(thread.name))
                self.threads.pop(i)
                thread.socket.shutdown()
                thread.socket.close()
            else:
                i += 1

    def drop_connection(self, socket, address):
        self.logger.info('drop connection from {}'.format(address))
        # TODO: proper error to send to the client?

    def spawn_thread(self, name, socket, address):
        server = self.server(name=name, **self.kwargs)
        server.input = socket.makefile('rb')
        server.output = socket.makefile('wb')
        thread = _threading.Thread(target=server.run, name=name)
        thread.start()
        self.threads.append(thread)
