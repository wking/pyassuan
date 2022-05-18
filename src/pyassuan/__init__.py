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

__version__ = '0.2'

LOG = logging.getLogger('pyassuan')
LOG.setLevel(logging.ERROR)
LOG.addHandler(logging.StreamHandler())
# LOG.addHandler(logging.FileHandler('/tmp/pinentry.log'))
# LOG.addHandler(logging_handlers.SysLogHandler(address='/dev/log'))
LOG.handlers[0].setFormatter(
    logging.Formatter('%(name)s: %(levelname)s: %(message)s')
)
