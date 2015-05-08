#!/usr/bin/env python

# Copyright (C) 2014 Tobias Bengfort <tobias.bengfort@gmx.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A tool for managing contacts and calendars.

cctool can read entries from different source formats and output them to
different target formats. For example, it could be used to combine birthday
dates from an addressbook and a calendar.
"""

# internal representation: iterable of dicts with unsepcified format.
# interpretation of different keys and values happens at dump

from __future__ import print_function

import os
import sys
import argparse
import logging as log
from collections import OrderedDict
import json
from datetime import datetime
import pickle
import codecs
from io import BytesIO

try:
	from ConfigParser import RawConfigParser as ConfigParser
except ImportError:
	from configparser import RawConfigParser as ConfigParser

try:
	import ldif
except ImportError as err:
	ldif = err

try:
	import icalendar
except ImportError as err:
	icalendar = err

try:
	import yaml
except ImportError as err:
	yaml = err


NOTSET = object()


def _str(x):
	try:
		return unicode(x)
	except NameError:
		return str(x)


def formats():
	informats = {
		'abook': ABook,
		'json': JSON,
		'pickle': Pickle,
	}
	outformats = {
		'bsdcal': BSDCal,
		'abook': ABook,
		'json': JSON,
		'pickle': Pickle,
	}
	if not isinstance(icalendar, Exception):
		informats['ics'] = ICal
		outformats['ics'] = ICal
	if not isinstance(ldif, Exception):
		informats['ldif'] = LDIF
	if not isinstance(yaml, Exception):
		informats['yml'] = YAML
		outformats['yml'] = YAML
	return informats, outformats


class MultiDict(OrderedDict):
	"""Dict subclass with multiple values for each key.

	>>> d = MultiDict()
	>>> d['foo']
	[]
	>>> d['foo'] = []
	>>> 'foo' in d
	False
	>>> d['foo'] = ['a', 'b', 'c']
	>>> 'foo' in d
	True
	>>> d['foo']
	['a', 'b', 'c']
	>>> d.first('foo')
	'a'
	>>> d.join('foo')
	'a,b,c'
	>>> d.join('foo', sep=', ')
	'a, b, c'
	>>> d.join('bar', default='N/A')
	'N/A'
	"""

	def __contains__(self, key):
		return (super(MultiDict, self).__contains__(key)
			and super(MultiDict, self).__getitem__(key) != [])

	def __getitem__(self, key):
		if key in self:
			return super(MultiDict, self).__getitem__(key)
		else:
			return []

	def first(self, key, default=NOTSET):
		if key in self:
			return self[key][0]
		elif default is not NOTSET:
			return default
		else:
			raise KeyError(key)

	def join(self, key, default='', sep=','):
		if key in self:
			if len(self[key]) == 1:
				return self[key][0]
			else:
				return sep.join(self[key])
		elif default is not None:
			return default
		else:
			raise KeyError(key)

	def append(self, key, values):
		"""Add a list of values."""
		for value in values:
			if value not in self[key]:
				self[key] = self[key] + [value]

	def update(self, other):
		"""Update this MultiDict with the contentes of another one."""
		for key in other:
			self.append(key, other[key])


def merged(data, key):
	"""Outer join `data` on `key`."""
	tmp = dict()
	missing = []
	for entry in data:
		if key in entry:
			tmp_key = str(entry[key])
			if tmp_key in tmp:
				tmp[tmp_key].update(entry)
			else:
				tmp[tmp_key] = entry
		else:
			missing.append(entry)
	return list(tmp.values()) + missing


class Format(object):
	"""Baseclass with an API similar to the marshal, pickle and json modules.

	:py:meth:`load` takes a bytes stream and returns a :py:class:`MultiDict`.
	:py:meth:`dump` does the reverse.
	"""

	@classmethod
	def load(cls, fh):
		raise NotImplementedError

	@classmethod
	def loads(cls, s):
		return cls.load(BytesIO(s))

	@classmethod
	def dump(cls, data, fh):
		raise NotImplementedError

	@classmethod
	def dumps(cls, data):
		fh = BytesIO()
		cls.dump(data, fh)
		return fh.getvalue()


class BSDCal(Format):
	@classmethod
	def dump(cls, data, fh):
		_fh = codecs.getwriter('utf8')(fh)
		for item in data:
			if u'dtstart' in item and u'summary' in item:
				dt = item.first('dtstart')
				if dt.year == datetime.today().year:
					_fh.write('%s\t%s\n' % (dt.strftime('%m/%d'), item.join('summary')))
			if u'bday' in item and u'name' in item:
				dt = item.first('bday')
				_fh.write('%s\t%s\n' % (dt.strftime('%m/%d*'), item.join('name')))


class ICal(Format):
	fields = ['attach', 'categories', 'class', 'comment', 'description', 'geo',
		'location', 'percent-complete', 'priority', 'resources', 'status',
		'summary', 'completed', 'dtend', 'due', 'dtstart', 'duration', 'freebusy',
		'transp', 'tzid', 'tzname', 'tzoffsetfrom', 'tzoffsetto', 'tzurl',
		'attendee', 'contact', 'organizer', 'recurrence-id', 'related-to', 'url',
		'uid', 'exdate', 'rdate', 'rrule', 'action', 'repeat', 'trigger',
		'created', 'dtstamp', 'last-modified', 'sequence']

	@classmethod
	def _iter_events(cls, component):
		if isinstance(component, icalendar.Event):
			yield component
		elif hasattr(component, 'subcomponents'):
			for c in component.subcomponents:
				for event in cls._iter_events(c):
					yield event

	@classmethod
	def _decode(cls, key, value):
		if isinstance(value, list):
			return sum((cls._decode(key, i) for i in value), [])
		else:
			_value = value.from_ical(value)
			if key in ['DTSTART', 'DTEND']:
				if isinstance(_value, datetime) or isinstance(_value, date):
					return [_value]
				else:
					raise ValueError(value)
			else:
				s = _str(_value)
				return [s] if s else []

	@classmethod
	def load(cls, fh):
		if isinstance(icalendar, Exception):
			raise icalendar

		calendar = icalendar.Calendar.from_ical(fh.read())

		for event in cls._iter_events(calendar):
			d = MultiDict()
			for key, value in event.items():
				if key.lower() in cls.fields:
					try:
						_value = cls._decode(key, value)
						if _value:
							d[key.lower()] = _value
					except ValueError:
						break
			else:
				yield d

	@classmethod
	def dump(cls, data, fh):
		if isinstance(icalendar, Exception):
			raise icalendar

		calendar = icalendar.Calendar()
		calendar.add('prodid', '-//XI//NONSGML CCTOOL//')
		calendar.add('version', '2.0')

		for event in data:
			vevent = icalendar.Event()
			for key in event:
				if key in cls.fields:
					for value in event[key]:
						vevent.add(key.upper(), value)
			calendar.add_component(vevent)

		fh.write(calendar.to_ical())


class ABook(Format):
	fields = ['name', 'nick', 'bday', 'email', 'url', 'tag',
		'address_lines', 'city', 'state', 'zip', 'country',
		'phone', 'workphone', 'mobile',
		'xmpp', 'icq', 'msn', 'twitter', 'pgp']

	@classmethod
	def load(cls, fh):
		_fh = codecs.getreader('utf8')(fh)
		config_parser = ConfigParser()
		config_parser.readfp(_fh)
		for section in config_parser.sections():
			if section != u'format':
				d = MultiDict()
				for key, value in config_parser.items(section):
					if key == 'bday':
						if value[0] == '-':
							value = '1900' + value[1:]
						d[key] = [datetime.strptime(value, '%Y-%m-%d')]
					else:
						d[key] = value.split(u',')
				yield d

	@classmethod
	def dump(cls, data, fh):
		_fh = codecs.getwriter('utf8')(fh)
		cp = ConfigParser()
		i = 0
		for item in data:
			section = _str(i)
			cp.add_section(section)
			for key in item:
				if key == 'bday':
					dt = item.first(key)
					if dt.year == 1900:
						value = dt.strftime('--%m-%d')
					else:
						value = dt.strftime('%Y-%m-%d')
					cp.set(section, key, value)
				elif key in cls.fields:
					cp.set(section, key, item.join(key))
				elif key in ['mail']:
					cp.set(section, 'email', item.join(key))
				elif key in ['cn']:
					cp.set(section, 'name', item.join(key))
			i += 1
		cp.write(_fh)


if not isinstance(ldif, Exception):
	class LDIFParser(ldif.LDIFParser):
		def __init__(self, fh):
			ldif.LDIFParser.__init__(self, fh)
			self.entries = {}

		def handle(self, dn, entry):
			self.entries[dn] = entry


class LDIF(Format):
	fields = ['dn', 'objectclass', 'modifytimestamp',
		'mail', 'givenName', 'sn', 'cn']

	@classmethod
	def load(cls, fh):
		if isinstance(ldif, Exception):
			raise ldif
		parser = LDIFParser(fh)
		try:
			parser.parse()
		except ValueError as err:
			log.warning("ValueError after reading %i records: %s",
				parser.records_read, err)
		for entry in parser.entries.values():
			yield MultiDict(entry)


class DateTimeJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj, 'isoformat'):
			return obj.isoformat()
		else:
			return super(DateTimeJSONEncoder, self).default(obj)


class JSON(Format):
	@classmethod
	def load(cls, fh):
		_fh = codecs.getreader('utf8')(fh)
		return [MultiDict(i) for i in json.load(_fh)]

	@classmethod
	def dump(cls, data, fh):
		_fh = codecs.getwriter('utf8')(fh)
		json.dump(list(data), _fh, indent=4, cls=DateTimeJSONEncoder)


class YAML(Format):
	@classmethod
	def load(cls, fh):
		if isinstance(yaml, Exception):
			raise yaml

		return [MultiDict(d) for d in yaml.load(fh.read())]

	@classmethod
	def dump(cls, data, fh):
		if isinstance(yaml, Exception):
			raise yaml

		_fh = codecs.getwriter('utf8')(fh)
		_fh.write(yaml.safe_dump([dict(d) for d in data]))


class Pickle(Format):
	@classmethod
	def load(cls, fh):
		return pickle.load(fh)

	@classmethod
	def dump(cls, data, fh):
		pickle.dump(data, fh)


def parse_args(argv=None):
	informats, outformats = formats()

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('--from', '-f', choices=list(informats.keys()),
		metavar='FORMAT', dest='informat')
	parser.add_argument('--to', '-t', choices=list(outformats.keys()),
		metavar='FORMAT', dest='outformat')
	parser.add_argument('input', nargs='*', default=['-'], metavar='FILE')
	parser.add_argument('--output', '-o', metavar='FILENAME')
	parser.add_argument('--sort', '-s', metavar='SORTKEY',
		help="sort entries by this field")
	parser.add_argument('--merge', '-m', metavar='MERGEKEY',
		help="merge entries by this field")
	return parser.parse_args(argv)


def get_outformat(args):
	informats, outformats = formats()

	if args.outformat is not None:
		return args.outformat
	elif args.output is not None:
		ext = args.output.split(os.path.extsep)[-1]
		if ext in outformats:
			return ext

	print("Missing output format")
	sys.exit(1)


def get_informat(filename):
	informats, outformats = formats()
	ext = filename.split(os.path.extsep)[-1]

	if ext in informats:
		return ext
	else:
		print("Missing input format")
		sys.exit(1)


def main():
	informats, outformats = formats()
	args = parse_args()

	outformat = get_outformat(args)

	data = []
	for filename in args.input:
		if args.informat is not None:
			informat = args.informat
		else:
			informat = get_informat(filename)

		infile = sys.stdin if filename == '-' else open(filename, 'rb')
		data += informats[informat]().load(infile)
		if filename != '-':
			infile.close()

	if args.merge is not None:
		data = merged(data, key=args.merge)

	if args.sort is not None:
		data = sorted(data, key=lambda x: x[args.sort])

	outfile = sys.stdout if args.output is None else open(args.output, 'wb')
	outformats[outformat]().dump(data, outfile)


if __name__ == '__main__':
	main()
