# Copyright

"Python module and tools for communicating in the Assuan protocol."

from distutils.core import setup as _setup
import os.path as _os_path

from pyassuan import __version__


_this_dir = _os_path.dirname(__file__)

_setup(
    name='pyassuan',
    version=__version__,
    maintainer='W. Trevor King',
    maintainer_email='wking@drexel.edu',
    url='http://blog.tremily.us/posts/pyassuan/',
    download_url='http://git.tremily.us/?p=pyassuan.git;a=snapshot;h=v{};sf=tgz'.format(__version__),
    license = 'GNU General Public License (GPL)',
    platforms = ['all'],
    description = __doc__,
    long_description=open(_os_path.join(_this_dir, 'README'), 'r').read(),
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3',
        'Topic :: Security :: Cryptography',
        'Topic :: Software Development'
        ],
    scripts = ['bin/get-info.py', 'bin/pinentry.py'],
    packages = ['pyassuan'],
    provides = ['pyassuan'],
    )
