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

"""Simple pinentry program for getting pins from a terminal.
"""

import copy as _copy
import os as _os
import os.path as _os_path
import pprint as _pprint
import re as _re
import signal as _signal
import sys as _sys
import termios as _termios

from pyassuan import __version__
from pyassuan import server as _server
from pyassuan import common as _common
from pyassuan import error as _error


class PinEntry (_server.AssuanServer):
    """pinentry protocol server

    See ``pinentry-0.8.0/doc/pinentry.texi`` at::

      ftp://ftp.gnupg.org/gcrypt/pinentry/
      http://www.gnupg.org/aegypten/

    for details on the pinentry interface.

    Alternatively, you can just watch the logs and guess ;).  Here's a
    trace when driven by GnuPG 2.0.28 (libgcrypt 1.6.3)::

      S: OK Your orders please
      C: OPTION grab
      S: OK
      C: OPTION ttyname=/dev/pts/6
      S: OK
      C: OPTION ttytype=xterm
      S: OK
      C: OPTION lc-ctype=en_US.UTF-8
      S: OK
      C: OPTION lc-messages=en_US.UTF-8
      S: OK
      C: OPTION allow-external-password-cache
      S: OK
      C: OPTION default-ok=_OK
      S: OK
      C: OPTION default-cancel=_Cancel
      S: OK
      C: OPTION default-yes=_Yes
      S: OK
      C: OPTION default-no=_No
      S: OK
      C: OPTION default-prompt=PIN:
      S: OK
      C: OPTION default-pwmngr=_Save in password manager
      S: OK
      C: OPTION default-cf-visi=Do you really want to make your passphrase visible on the screen?
      S: OK
      C: OPTION default-tt-visi=Make passphrase visible
      S: OK
      C: OPTION default-tt-hide=Hide passphrase
      S: OK
      C: GETINFO pid
      S: D 14309
      S: OK
      C: SETKEYINFO u/S9464F2C2825D2FE3
      S: OK
      C: SETDESC Enter passphrase%0A
      S: OK
      C: SETPROMPT Passphrase
      S: OK
      C: GETPIN
      S: D testing!
      S: OK
      C: BYE
      S: OK closing connection
    """
    _digit_regexp = _re.compile(r'\d+')

    # from proc(5): pid comm state ppid pgrp session tty_nr tpgid
    _tpgrp_regexp = _re.compile(r'\d+ \(\S+\) . \d+ \d+ \d+ \d+ (\d+)')

    def __init__(self, name='pinentry', strict_options=False,
                 single_request=True, **kwargs):
        self.strings = {}
        self.connection = {}
        super(PinEntry, self).__init__(
            name=name, strict_options=strict_options,
            single_request=single_request, **kwargs)
        self.valid_options.append('ttyname')

    def reset(self):
        super(PinEntry, self).reset()
        self.strings.clear()
        self.connection.clear()

    # user interface

    def _connect(self):
        self.logger.info('connecting to user')
        self.logger.debug('options:\n{}'.format(_pprint.pformat(self.options)))
        tty_name = self.options.get('ttyname', None)
        if tty_name:
            self.connection['tpgrp'] = self._get_pgrp(tty_name)
            self.logger.info(
                'open to-user output stream for {}'.format(tty_name))
            self.connection['to_user'] = open(tty_name, 'w')
            self.logger.info(
                'open from-user input stream for {}'.format(tty_name))
            self.connection['from_user'] = open(tty_name, 'r')
            self.logger.info('get current termios line discipline')
            self.connection['original termios'] = _termios.tcgetattr(
                self.connection['to_user']) # [iflag, oflag, cflag, lflag, ...]
            new_termios = _copy.deepcopy(self.connection['original termios'])
            # translate carriage return to newline on input
            new_termios[0] |= _termios.ICRNL
            # do not ignore carriage return on input
            new_termios[0] &= ~_termios.IGNCR
            # do not echo input characters
            new_termios[3] &= ~_termios.ECHO
            # echo input characters
            #new_termios[3] |= _termios.ECHO
            # echo the NL character even if ECHO is not set
            new_termios[3] |= _termios.ECHONL
            # enable canonical mode
            new_termios[3] |= _termios.ICANON
            self.logger.info('adjust termios line discipline')
            _termios.tcsetattr(
                self.connection['to_user'], _termios.TCSANOW, new_termios)
            self.logger.info('send SIGSTOP to pgrp {}'.format(
                    self.connection['tpgrp']))
            #_os.killpg(self.connection['tpgrp'], _signal.SIGSTOP)
            _os.kill(-self.connection['tpgrp'], _signal.SIGSTOP)
            self.connection['tpgrp stopped'] = True
        else:
            self.logger.info('no TTY name given; use stdin/stdout for I/O')
            self.connection['to_user'] = _sys.stdout
            self.connection['from_user'] = _sys.stdin
        self.logger.info('connected to user')
        self.connection['to_user'].write('\n')  # give a clean line to work on
        self.connection['active'] = True

    def _disconnect(self):
        self.logger.info('disconnecting from user')
        try:
            if self.connection.get('original termios', None):
                self.logger.info('restore original termios line discipline')
                _termios.tcsetattr(
                    self.connection['to_user'], _termios.TCSANOW,
                    self.connection['original termios'])
            if self.connection.get('tpgrp stopped', None) is True:
                self.logger.info(
                    'send SIGCONT to pgrp {}'.format(self.connection['tpgrp']))
                #_os.killpg(self.connection['tpgrp'], _signal.SIGCONT)
                _os.kill(-self.connection['tpgrp'], _signal.SIGCONT)
            if self.connection.get('to_user', None) not in [None, _sys.stdout]:
                self.logger.info('close to-user output stream')
                self.connection['to_user'].close()
            if self.connection.get('from_user',None) not in [None,_sys.stdout]:
                self.logger.info('close from-user input stream')
                self.connection['from_user'].close()
        finally:
            self.connection = {'active': False}
            self.logger.info('disconnected from user')

    def _get_pgrp(self, tty_name):
        self.logger.info('find process group contolling {}'.format(tty_name))
        proc = '/proc'
        for name in _os.listdir(proc):
            path = _os_path.join(proc, name)
            if not (self._digit_regexp.match(name) and _os_path.isdir(path)):
                continue  # not a process directory
            self.logger.debug('checking process {}'.format(name))
            fd_path = _os_path.join(path, 'fd', '0')
            try:
                link = _os.readlink(fd_path)
            except OSError as e:
                self.logger.debug('not our process: {}'.format(e))
                continue  # permission denied (not one of our processes)
            if link != tty_name:
                self.logger.debug('wrong tty: {}'.format(link))
                continue  # not attached to our target tty
            stat_path = _os_path.join(path, 'stat')
            stat = open(stat_path, 'r').read()
            self.logger.debug('check stat for pgrp: {}'.format(stat))
            match = self._tpgrp_regexp.match(stat)
            assert match != None, stat
            pgrp = int(match.group(1))
            self.logger.info('found pgrp {} for {}'.format(pgrp, tty_name))
            return pgrp
        raise ValueError(tty_name)

    def _write(self, string):
        "Write text to the user's terminal."
        self.connection['to_user'].write(string + '\n')
        self.connection['to_user'].flush()

    def _read(self):
        "Read and return a line from the user's terminal."
        # drop trailing newline
        return self.connection['from_user'].readline()[:-1]

    def _prompt(self, prompt='?', add_colon=True):
        if add_colon:
            prompt += ':'
        self.connection['to_user'].write(prompt)
        self.connection['to_user'].write(' ')
        self.connection['to_user'].flush()
        return self._read()

    # assuan handlers

    def _handle_GETINFO(self, arg):
        if arg == 'pid':
            yield _common.Response('D', str(_os.getpid()).encode('ascii'))
        elif arg == 'version':
            yield _common.Response('D', __version__.encode('ascii'))
        else:
            raise _error.AssuanError(message='Invalid parameter')
        yield _common.Response('OK')

    def _handle_SETKEYINFO(self, arg):
        self.strings['key info'] = arg
        yield _common.Response('OK')

    def _handle_SETDESC(self, arg):
        self.strings['description'] = arg
        yield _common.Response('OK')

    def _handle_SETPROMPT(self, arg):
        self.strings['prompt'] = arg
        yield _common.Response('OK')

    def _handle_SETERROR(self, arg):
        self.strings['error'] = arg
        yield _common.Response('OK')

    def _handle_SETTITLE(self, arg):
        self.strings['title'] = arg
        yield _common.Response('OK')

    def _handle_SETOK(self, arg):
        self.strings['ok'] = arg
        yield _common.Response('OK')

    def _handle_SETCANCEL(self, arg):
        self.strings['cancel'] = arg
        yield _common.Response('OK')

    def _handle_SETNOTOK(self, arg):
        self.strings['not ok'] = arg
        yield _common.Response('OK')

    def _handle_SETQUALITYBAR(self, arg):
        """Adds a quality indicator to the GETPIN window.

        This indicator is updated as the passphrase is typed.  The
        clients needs to implement an inquiry named "QUALITY" which
        gets passed the current passphrase (percent-plus escaped) and
        should send back a string with a single numerical vauelue
        between -100 and 100.  Negative values will be displayed in
        red.

        If a custom label for the quality bar is required, just add
        that label as an argument as percent escaped string.  You will
        need this feature to translate the label because pinentry has
        no internal gettext except for stock strings from the toolkit
        library.

        If you want to show a tooltip for the quality bar, you may use

            C: SETQUALITYBAR_TT string
            S: OK

        With STRING being a percent escaped string shown as the tooltip.

        Here is a real world example of these commands in use:

            C: SETQUALITYBAR Quality%3a
            S: OK
            C: SETQUALITYBAR_TT The quality of the text entered above.%0aPlease ask your administrator for details about the criteria.
            S: OK
        """
        self.strings['qualitybar'] = arg
        yield _common.Response('OK')

    def _handle_SETQUALITYBAR_TT(self, arg):
        self.strings['qualitybar_tooltip'] = arg
        yield _common.Response('OK')

    def _handle_GETPIN(self, arg):
        try:
            self._connect()
            self._write(self.strings['description'])
            if 'key info' in self.strings:
                self._write('key: {}'.format(self.strings['key info']))
            if 'qualitybar' in self.strings:
                self._write(self.strings['qualitybar'])
            pin = self._prompt(self.strings['prompt'], add_colon=False)
        finally:
            self._disconnect()
        yield _common.Response('D', pin.encode('ascii'))
        yield _common.Response('OK')

    def _handle_CONFIRM(self, arg):
        try:
            self._connect()
            self._write(self.strings['description'])
            self._write('1) '+self.strings['ok'])
            self._write('2) '+self.strings['not ok'])
            value = self._prompt('?')
        finally:
            self._disconnect()
        if value == '1':
            yield _common.Response('OK')
        else:
            raise _error.AssuanError(message='Not confirmed')

    def _handle_MESSAGE(self, arg):
        self._write(self.strings['description'])
        yield _common.Response('OK')

    def _handle_CONFIRM(self, args):
        assert args == '--one-button', args
        try:
            self._connect()
            self._write(self.strings['description'])
            self._write('1) '+self.strings['ok'])
            value = self._prompt('?')
        finally:
            self._disconnect()
        assert value == '1', value
        yield _common.Response('OK')


if __name__ == '__main__':
    import argparse
    import logging
    import traceback

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s {}'.format(__version__))
    parser.add_argument(
        '-V', '--verbose', action='count', default=0,
        help='increase verbosity')
    parser.add_argument(
        '--display',
        help='set X display (ignored by this implementation)')

    args = parser.parse_args()

    p = PinEntry()

    if args.verbose:
        p.logger.setLevel(max(
                logging.DEBUG, p.logger.level - 10*args.verbose))

    try:
        p.run()
    except:
        p.logger.error(
            'exiting due to exception:\n{}'.format(
                traceback.format_exc().rstrip()))
        raise
