# Copyright

import logging as _logging
import sys as _sys

from . import LOG as _LOG
from . import common as _common
from . import error as _error


class AssuanClient (object):
    """A single-threaded Assuan client based on the `devolpment suggestions`_

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
        self.input = self.output = None

    def connect(self):
        if not self.input:
            self.logger.info('read from stdin')
            self.input = _sys.stdin
        if not self.output:
            self.logger.info('write to stdout')
            self.output = _sys.stdout

    def disconnect(self):
        if self.close_on_disconnect:
            self.logger.info('disconnecting')
            self.input = None
            self.output = None

    def raise_error(self, error):
        self.logger.error(str(error))
        raise(error)

    def read_response(self):
        line = self.input.readline()
        if not line:
            self.raise_error(
                _error.AssuanError(message='IPC accept call failed'))
        if not line.endswith('\n'):
            self.raise_error(
                _error.AssuanError(message='Invalid response'))
        line = line[:-1]  # remove trailing newline
        # TODO, line length?
        response = _common.Response()
        try:
            response.from_string(line)
        except _error.AssuanError as e:
            self.logger.error(str(e))
            raise
        self.logger.info('S: {}'.format(response))
        return response

    def make_request(self, request, response=True, expect=['OK']):
        rstring = str(request)
        self.logger.info('C: {}'.format(rstring))
        self.output.write(rstring)
        self.output.write('\n')
        try:
            self.output.flush()
        except IOError:
            raise
        if response:
            return self.get_responses(request=request, expect=expect)

    def get_responses(self, request=None, expect=['OK']):
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
            if request is not None:
                error.request = request
            error.responses = responses
            raise error
        if expect:
            assert responses[-1].type in expect, [str(r) for r in responses]
        data = []
        for response in responses:
            if response.type == 'D':
                data.append(response.parameters)
        if data:
            data = ''.join(data)
        else:
            data = None
        return (responses, data)

    def responses(self):
        while True:
            response = self.read_response()
            yield response
            if response.type not in ['S', '#', 'D']:
                break
