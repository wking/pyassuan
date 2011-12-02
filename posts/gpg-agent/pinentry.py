#!/usr/bin/env python
#
# Copyright (C) 2011 W. Trevor King <wking@drexel.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.

"""Simple pinentry program for getting pins from a terminal.
"""

import copy
import logging
import logging.handlers
import os
import os.path
import pprint
import re
import signal
import sys
import termios
import traceback


__version__ = '0.1'


# create logger
logger = logging.getLogger('pinentry')
logger.setLevel(logging.WARNING)
_h = logging.handlers.SysLogHandler(address='/dev/log')
_h.setLevel(logging.DEBUG)
_f = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
_h.setFormatter(_f)
logger.addHandler(_h)
del _h, _f


class PinEntry (object):
    """pinentry protocol server

    See the `Assuan manual`_ for a description of the protocol.

    .. _Assuan manual: http://www.gnupg.org/documentation/manuals/assuan/
    """
    _digit_regexp = re.compile(r'\d+')

    # from proc(5): pid comm state ppid pgrp session tty_nr tpgid
    _tpgrp_regexp = re.compile(r'\d+ \(\S+\) . \d+ \d+ \d+ \d+ (\d+)')

    _assuan_encode_regexp = re.compile(
        '(' + '|'.join(['%', '\r', '\n']) + ')')
    _assuan_decode_regexp = re.compile('(%[0-9A-F]{2})')

    def __init__(self):
        self.stop = False
        self.options = {}
        self.strings = {}
        self.connection = {}

    def run(self):
        logger.info('---opening pinentry---')
        logger.info('OK Your orders please')
        sys.stdout.write('OK Your orders please\n')
        sys.stdout.flush()
        try:
            while not self.stop:
                line = sys.stdin.readline()
                if not line:
                    break  # EOF
                line = line.rstrip()  # dangerous?
                logger.info(line)
                line = self._decode(line)
                fields = line.split(' ', 1)
                cmd = fields[0]
                if len(fields) > 1:
                    arg = fields[1]
                else:
                    arg = None
                handle = getattr(self, '_handle_%s' % cmd, None)
                if handle:
                    for response in handle(arg):
                        response = self._encode(response)
                        logger.info(response)
                        sys.stdout.write(response+'\n')
                        try:
                            sys.stdout.flush()
                        except IOError:
                            if not self.stop:
                                raise
                else:
                    raise ValueError(line)
        finally:
            logger.info('---closing pinentry---')

    # user interface

    def _connect(self):
        logger.info('--connecting to user--')
        logger.debug('options:\n%s' % pprint.pformat(self.options))
        tty_name = self.options.get('ttyname', None)
        if tty_name:
            self.connection['tpgrp'] = self._get_pgrp(tty_name)
            logger.info('open to-user output stream for %s' % tty_name)
            self.connection['to_user'] = open(tty_name, 'w')
            logger.info('open from-user input stream for %s' % tty_name)
            self.connection['from_user'] = open(tty_name, 'r')
            logger.info('get current termios line discipline')
            self.connection['original termios'] = termios.tcgetattr(
                self.connection['to_user']) # [iflag, oflag, cflag, lflag, ...]
            new_termios = copy.deepcopy(self.connection['original termios'])
            # translate carriage return to newline on input
            new_termios[0] |= termios.ICRNL
            # do not ignore carriage return on input
            new_termios[0] &= ~termios.IGNCR
            # do not echo input characters
            new_termios[3] &= ~termios.ECHO
            # echo input characters
            #new_termios[3] |= termios.ECHO
            # echo the NL character even if ECHO is not set
            new_termios[3] |= termios.ECHONL
            # enable canonical mode
            new_termios[3] |= termios.ICANON
            logger.info('adjust termios line discipline')
            termios.tcsetattr(
                self.connection['to_user'], termios.TCSANOW, new_termios)
            logger.info('send SIGSTOP to pgrp %d' % self.connection['tpgrp'])
            #os.killpg(self.connection['tpgrp'], signal.SIGSTOP)
            os.kill(-self.connection['tpgrp'], signal.SIGSTOP)
            self.connection['tpgrp stopped'] = True
        else:
            logger.info('no TTY name given; use stdin/stdout for I/O')
            self.connection['to_user'] = sys.stdout
            self.connection['from_user'] = sys.stdin
        logger.info('--connected to user--')
        self.connection['to_user'].write('\n')  # give a clean line to work on
        self.connection['active'] = True

    def _disconnect(self):
        logger.info('--disconnecting from user--')
        try:
            if self.connection.get('original termios', None):
                logger.info('restore original termios line discipline')
                termios.tcsetattr(
                    self.connection['to_user'], termios.TCSANOW,
                    self.connection['original termios'])
            if self.connection.get('tpgrp stopped', None) is True:
                logger.info(
                    'send SIGCONT to pgrp %d' % self.connection['tpgrp'])
                #os.killpg(self.connection['tpgrp'], signal.SIGCONT)
                os.kill(-self.connection['tpgrp'], signal.SIGCONT)
            if self.connection.get('to_user', None) not in [None, sys.stdout]:
                logger.info('close to-user output stream')
                self.connection['to_user'].close()
            if self.connection.get('from_user', None) not in [None,sys.stdout]:
                logger.info('close from-user input stream')
                self.connection['from_user'].close()
        finally:
            self.connection = {'active': False}
            logger.info('--disconnected from user--')

    def _get_pgrp(self, tty_name):
        logger.info('find process group contolling %s' % tty_name)
        proc = '/proc'
        for name in os.listdir(proc):
            path = os.path.join(proc, name)
            if not (self._digit_regexp.match(name) and os.path.isdir(path)):
                continue  # not a process directory
            logger.debug('checking process %s' % name)
            fd_path = os.path.join(path, 'fd', '0')
            try:
                link = os.readlink(fd_path)
            except OSError, e:
                logger.debug('not our process: %s' % e)
                continue  # permission denied (not one of our processes)
            if link != tty_name:
                logger.debug('wrong tty: %s' % link)
                continue  # not attached to our target tty
            stat_path = os.path.join(path, 'stat')
            stat = open(stat_path, 'r').read()
            logger.debug('check stat for pgrp: %s' % stat)
            match = self._tpgrp_regexp.match(stat)
            assert match != None, stat
            pgrp = int(match.group(1))
            logger.info('found pgrp %d for %s' % (pgrp, tty_name))
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
        self.connection['to_user'].write('%s ' % prompt)
        self.connection['to_user'].flush()
        return self._read()

    # Assuan utilities

    def _encode(self, string):
        """

        >>> p = PinEntry()
        >>> p._encode('It grew by 5%!\\n')
        'It grew by 5%25!%0A'
        """   
        return self._assuan_encode_regexp.sub(
            lambda x : self._to_hex(x.group()), string)

    def _decode(self, string):
        """

        >>> p = PinEntry()
        >>> p._decode('%22Look out!%22%0AWhere%3F')
        '"Look out!"\\nWhere?'
        """
        return self._assuan_decode_regexp.sub(
            lambda x : self._from_hex(x.group()), string)

    def _from_hex(self, code):
        """

        >>> p = PinEntry()
        >>> p._from_hex('%22')
        '"'
        >>> p._from_hex('%0A')
        '\\n'
        """
        return chr(int(code[1:], 16))

    def _to_hex(self, char):
        """

        >>> p = PinEntry()
        >>> p._to_hex('"')
        '%22'
        >>> p._to_hex('\\n')
        '%0A'
        """
        return '%%%02X' % ord(char)

    # handlers

    def _handle_BYE(self, arg):
        self.stop = True
        yield 'OK closing connection'

    def _handle_OPTION(self, arg):
        # ttytype to set TERM
        fields = arg.split('=', 1)
        key = fields[0]
        if len(fields) > 1:
            value = fields[1]
        else:
            value = True
        self.options[key] = value
        yield 'OK'

    def _handle_GETINFO(self, arg):
        if arg == 'pid':
            yield 'D %d' % os.getpid()
        else:
            raise ValueError(arg)
        yield 'OK'

    def _handle_SETDESC(self, arg):
        self.strings['description'] = arg
        yield 'OK'

    def _handle_SETPROMPT(self, arg):
        self.strings['prompt'] = arg
        yield 'OK'

    def _handle_SETERROR(self, arg):
        self.strings['error'] = arg
        yield 'OK'

    def _handle_SETTITLE(self, arg):
        self.strings['title'] = arg
        yield 'OK'

    def _handle_SETOK(self, arg):
        self.strings['ok'] = arg
        yield 'OK'

    def _handle_SETCANCEL(self, arg):
        self.strings['cancel'] = arg
        yield 'OK'

    def _handle_SETNOTOK(self, arg):
        self.strings['not ok'] = arg
        yield 'OK'

    def _handle_SETQUALITYBAR(self, arg):
        """Adds a quality indicator to the GETPIN window.  This
     indicator is updated as the passphrase is typed.  The clients
     needs to implement an inquiry named "QUALITY" which gets passed
     the current passpharse (percent-plus escaped) and should send
     back a string with a single numerical vauelue between -100 and
     100.  Negative values will be displayed in red.

     If a custom label for the quality bar is required, just add that
     label as an argument as percent escaped string.  You will need
     this feature to translate the label because pinentry has no
     internal gettext except for stock strings from the toolkit library.

     If you want to show a tooltip for the quality bar, you may use
            C: SETQUALITYBAR_TT string
            S: OK

     With STRING being a percent escaped string shown as the tooltip.
     """
        raise NotImplementedError()

    def _handle_GETPIN(self, arg):
        try:
            self._connect()
            self._write(self.strings['description'])
            pin = self._prompt(self.strings['prompt'], add_colon=False)
        finally:
            self._disconnect()
        yield 'D %s' % pin
        yield 'OK'

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
            yield 'OK'
        else:
            yield 'ASSUAN_Not_Confirmed'

    def _handle_MESSAGE(self, arg):
        self._write(self.strings['description'])
        yield 'OK'

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
        yield 'OK'


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, version=__version__)
    parser.add_argument(
        '-V', '--verbose', action='count', default=0,
        help='increase verbosity')

    args = parser.parse_args()

    if args.verbose >= 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbose >= 1:
        logger.setLevel(logging.INFO)

    try:
        p = PinEntry()
        p.run()
    except:
        logger.error('exiting due to exception:\n%s' %
                     traceback.format_exc().rstrip())
        raise
