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

try:
	from StringIO import StringIO
except ImportError:
	from io import StringIO

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


NOTSET = object()


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

	def update(self, other):
		for key in other:
			self[key] = list(set(self[key] + other[key]))


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
	"""Baseclass with an API similar to the marshal, pickle and json modules."""

	@classmethod
	def load(cls, fh):
		raise NotImplementedError

	@classmethod
	def loads(cls, s):
		return cls.load(StringIO(s))

	@classmethod
	def dump(cls, data, fh):
		raise NotImplementedError

	@classmethod
	def dumps(cls, data):
		fh = StringIO()
		cls.dump(data, fh)
		return fh.getvalue()


class BSDCal(Format):
	@classmethod
	def dump(cls, data, fh):
		for item in data:
			if u'dtstart' in item and u'summary' in item:
				dt = item.first('dtstart')
				if dt.year == datetime.today().year:
					fh.write('%s\t%s\n' % (dt.strftime('%m/%d'), item.join('summary')))
			if u'bday' in item and u'name' in item:
				dt = item.first('bday')
				fh.write('%s\t%s\n' % (dt.strftime('%m/%d*'), item.join('name')))


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
		config_parser = ConfigParser()
		config_parser.readfp(fh)
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
		cp = ConfigParser()
		i = 0
		for item in data:
			section = str(i)
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
		cp.write(fh)


if not isinstance(ldif, Exception):
	class LDIFParser(ldif.LDIFParser):
		def __init__(self, fh):
			ldif.LDIFParser.__init__(self, fh)
			self.entries = {}

		def handle(self, dn, entry):
			self.entries[dn] = entry


class LDIF(Format):
	fields = ['dn', 'objeclass', 'modifytimestamp',
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
		for entry in parser.entries.itervalues():
			yield MultiDict(entry)

	@classmethod
	def dump(cls, data, fh):
		if isinstance(ldif, Exception):
			raise ldif
		raise NotImplementedError


class DateTimeJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime):
			return obj.isoformat()
		else:
			return super(DateTimeJSONEncoder, self).default(obj)


class JSON(Format):
	@classmethod
	def load(cls, fh):
		return [MultiDict(i) for i in json.load(fh)]

	@classmethod
	def dump(cls, data, fh):
		json.dump(list(data), fh, indent=4, cls=DateTimeJSONEncoder)


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
	parser.add_argument('--from', '-f', choices=informats.keys(),
		metavar='FORMAT', dest='informat')
	parser.add_argument('--to', '-t', choices=outformats.keys(),
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

	sys.setdefaultencoding('utf-8')

	outformat = get_outformat(args)

	data = []
	for filename in args.input:
		if args.informat is not None:
			informat = args.informat
		else:
			informat = get_informat(filename)

		infile = sys.stdin if filename == '-' else open(filename)
		try:
			data += informats[informat]().load(infile)
		except Exception as err:
			log.error(err)
			sys.exit(1)
		if filename != '-':
			infile.close()

	if args.merge is not None:
		data = merged(data, key=args.merge)

	if args.sort is not None:
		data = sorted(data, key=lambda x: x[args.sort])

	outfile = sys.stdout if args.output is None else open(args.output, 'w')
	try:
		outformats[outformat]().dump(data, outfile)
	except Exception as err:
		log.error(err)
		sys.exit(1)


if __name__ == '__main__':
	main()
