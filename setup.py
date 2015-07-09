#!/usr/bin/env python

from setuptools import setup

setup(
    name='cctool',
    version='0.1.0',
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
