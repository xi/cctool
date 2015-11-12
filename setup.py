#!/usr/bin/env python

import os
import re
from setuptools import setup

DIRNAME = os.path.abspath(os.path.dirname(__file__))
rel = lambda *parts: os.path.abspath(os.path.join(DIRNAME, *parts))

MAIN = open(rel('cctool.py')).read()
VERSION = re.search("__version__ = '([^']+)'", MAIN).group(1)


setup(
    name='cctool',
    version=VERSION,
    description="A tool for managing contacts and calendars.",
    author='Tobias Bengfort',
    author_email='tobias.bengfort@gmx.net',
    platforms='any',
    py_modules=['cctool'],
    extras_require={
        'ldif': ['ldif3>=1.1.0'],
        'ical': ['icalendar'],
        'yaml': ['PyYAML'],
    },
    license='GPLv3+',
    entry_points={'console_scripts': 'cctool=cctool:main'},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'License :: OSI Approved :: GNU General Public License v3 or later '
            '(GPLv3+)',
    ])
