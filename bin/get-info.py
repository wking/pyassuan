#!/usr/bin/env python3
#
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

"""Simple pinentry program for getting server info.
"""

import socket as _socket

from pyassuan import __version__
from pyassuan import client as _client
from pyassuan import common as _common
from pyassuan import error as _error


if __name__ == '__main__':
    import argparse
    import logging

    parser = argparse.ArgumentParser(description=__doc__, version=__version__)
    parser.add_argument(
        '-V', '--verbose', action='count', default=0,
        help='increase verbosity')
    parser.add_argument(
        'filename',
        help="path to server's unix socket")

    args = parser.parse_args()

    client = _client.AssuanClient(name='get-info', close_on_disconnect=True)

    if args.verbose:
        client.logger.setLevel(max(
                logging.DEBUG, client.logger.level - 10*args.verbose))

    socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    socket.connect(args.filename)
    client.input = socket.makefile('rb')
    client.output = socket.makefile('wb')
    client.connect()
    try:
        response = client.read_response()
        assert response.type == 'OK', response
        client.make_request(_common.Request('HELP'))
        client.make_request(_common.Request('HELP GETINFO'))
        for attribute in ['version', 'pid', 'socket_name', 'ssh_socket_name']:
            try:
                client.make_request(_common.Request('GETINFO', attribute))
            except _error.AssuanError as e:
                if e.message.startswith('No data'):
                    pass
                else:
                    raise
    finally:
        client.make_request(_common.Request('BYE'))
        client.disconnect()
        socket.shutdown(_socket.SHUT_RDWR)
        socket.close()
