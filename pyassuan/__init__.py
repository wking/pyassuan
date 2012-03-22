# Copyright

"""A Python implementation of the `Assuan protocol`_.

.. _Assuan protocol: http://www.gnupg.org/documentation/manuals/assuan/
"""

import logging as _logging
import logging.handlers as _logging_handlers


__version__ = '0.1'

LOG = _logging.getLogger('pyassuan')
LOG.setLevel(_logging.ERROR)
LOG.addHandler(_logging.StreamHandler())
#LOG.addHandler(_logging.FileHandler('/tmp/pinentry.log'))
#LOG.addHandler(_logging_handlers.SysLogHandler(address='/dev/log'))
LOG.handlers[0].setFormatter(
    _logging.Formatter('%(name)s: %(levelname)s: %(message)s'))
