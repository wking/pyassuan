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

"""A Python implementation of the `Assuan protocol`_.

.. _Assuan protocol: http://www.gnupg.org/documentation/manuals/assuan/
"""

import logging as _logging
import logging.handlers as _logging_handlers


__version__ = '0.2'

LOG = _logging.getLogger('pyassuan')
LOG.setLevel(_logging.ERROR)
LOG.addHandler(_logging.StreamHandler())
#LOG.addHandler(_logging.FileHandler('/tmp/pinentry.log'))
#LOG.addHandler(_logging_handlers.SysLogHandler(address='/dev/log'))
LOG.handlers[0].setFormatter(
    _logging.Formatter('%(name)s: %(levelname)s: %(message)s'))
