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

"""A Python implementation of the `Assuan protocol`_.

.. _Assuan protocol: http://www.gnupg.org/documentation/manuals/assuan/
"""

import logging
from typing import List

from pyassuan.client import AssuanClient
from pyassuan.error import AssuanError
from pyassuan.common import Request, Response, error_response
from pyassuan.server import AssuanServer, AssuanSocketServer

__author__ = 'Jesse P. Johnson'
__author_email__ = 'jpj6652@gmail.com'
__title__ = 'pyassuan'
__description__ = 'A Python implementation of the `Assuan protocol.'
__version__ = '0.2.1b1'
__license__ = 'GPL-3.0'
__all__: List[str] = [
    'AssuanClient',
    'AssuanError',
    'AssuanServer',
    'AssuanSocketServer',
    'Request',
    'Response',
    'error_response',
]

LOG = logging.getLogger('pyassuan')
LOG.setLevel(logging.ERROR)
LOG.addHandler(logging.StreamHandler())
# LOG.addHandler(logging.FileHandler('/tmp/pinentry.log'))
# LOG.addHandler(logging_handlers.SysLogHandler(address='/dev/log'))
LOG.handlers[0].setFormatter(
    logging.Formatter('%(name)s: %(levelname)s: %(message)s')
)
