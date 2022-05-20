#!/usr/bin/env python3
#
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

"""Simple pinentry program for getting server info."""

from pyassuan import AssuanClient, AssuanError, Request, __version__

if __name__ == '__main__':
    import argparse
    import logging

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version='%(prog)s {}'.format(__version__),
    )
    parser.add_argument(
        '-V', '--verbose', action='count', default=0, help='increase verbosity'
    )
    parser.add_argument('filename', help="path to server's unix socket")

    args = parser.parse_args()

    client = AssuanClient(name='get_info', close_on_disconnect=True)

    if args.verbose:
        client.logger.setLevel(
            max(logging.DEBUG, client.logger.level - 10 * args.verbose)
        )

    client.connect(socket_path=args.filename)
    try:
        response = client.read_response()
        assert response.message == 'OK', response
        client.make_request(Request('HELP'))
        client.make_request(Request('HELP GETINFO'))
        for attribute in ['version', 'pid', 'socket_name', 'ssh_socket_name']:
            try:
                client.make_request(Request('GETINFO', attribute))
            except AssuanError as err:
                if err.message.startswith('No data'):  # type: ignore
                    pass
                else:
                    raise
    finally:
        client.make_request(Request('BYE'))
        client.disconnect()
