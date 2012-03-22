#!/usr/bin/env python3
#
# Copyright

"""Simple pinentry program for getting server info.
"""

import socket as _socket

from pyassuan import __version__
from pyassuan import client as _client
from pyassuan import common as _common


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
    client.input = socket.makefile('r')
    client.output = socket.makefile('w')
    client.connect()
    try:
        response = client.read_response()
        assert response.type == 'OK', response
        responses = client.make_request(_common.Request('HELP'))
        responses = client.make_request(_common.Request('HELP GETINFO'))
        for attribute in ['version', 'pid', 'socket_name', 'ssh_socket_name']:
            responses = client.make_request(
                _common.Request('GETINFO', attribute))
    finally:
        responses = client.make_request(_common.Request('BYE'))
        client.disconnect()
