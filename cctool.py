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

"""A tool for managing contacts and calendars."""

# internal representation: iterable of dicts with unsepcified format.
# interpretation of different keys and values happens at dump

# TODO
# -	type conversion (especially dates)
# -	filter/convert for valid fields
# -	doc
# -	tests
# -	merge
# -	sort
# -	filter
# -	unicode
# -	error handling

import os
import sys
import argparse
import logging as log
from StringIO import StringIO
from ConfigParser import RawConfigParser as ConfigParser
import json

try:
	import ldif
except ImportError as e:
	ldif = e

try:
	import vobject
except ImportError as e:
	vobject = e


NOTSET = object()


class MultiDict(dict):
	"""Dict subclass with multiple values for each key.

	>>> d = MultiDict()
	>>> d['foo'] = []
	>>> 'foo' in d
	False
	>>> d['foo'] = [1, 2, 3]
	>>> 'foo' in d
	True
	>>> d['foo']
	[1, 2, 3]
	>>> d.first('foo')
	1
	"""

	def __contains__(self, key):
		return super(MultiDict, self).__contains__(key) and self[key] != []

	def first(self, key, default=NOTSET):
		if key in self:
			return self[key][0]
		elif default is not NOTSET:
			return default
		else:
			raise KeyError

	def join(self, key, default=NOTSET, sep=u','):
		if key in self and len(self[key]) == 1:
			return self[key][0]
		elif key in self:
			return sep.join(self[key])
		elif default is not NOTSET:
			return default
		else:
			raise KeyError


class Format(object):
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
				fh.write('%s\t%s\n' % (item.first('dtstart'), item.join('summary')))
			if u'bday' in item and u'name' in item:
				fh.write('%s\t%s\n' % (item.first('bday'), item.join('name')))


class ICal(Format):
	@classmethod
	def load(cls, fh):
		if isinstance(vobject, Exception):
			raise vobject

		for calendar in vobject.readComponents(fh):
			for event in calendar.vevent_list:
				d = MultiDict()
				for key, value in event.contents.iteritems():
					d[key] = [i.value for i in value]
				yield d

	@classmethod
	def dump(cls, data, fh):
		if isinstance(vobject, Exception):
			raise vobject

		ical = vobject.iCalendar()
		for event in data:
			vevent = ical.add('vevent')
			for key in event:
				vevent.add(key).value = event.join(key)
		ical.serialize(fh)


class ABook(Format):
	fields = ['name', 'nick', 'bday', 'email', 'url', 'tag',
		'address_lines', 'city', 'state', 'zip', 'country',
		'phone', 'workphone', 'mobile',
		'xmpp', 'icq', 'msn', 'twitter', 'pgp']

	@classmethod
	def load(cls, fh):
		cp = ConfigParser()
		cp.readfp(fh)
		for section in cp.sections():
			if section != u'format':
				yield MultiDict({k: v.split(',') for (k, v) in cp.items(section)})

	@classmethod
	def dump(cls, data, fh):
		cp = ConfigParser()
		i = 0
		for item in data:
			section = unicode(i)
			cp.add_section(section)
			for key in item:
				if key in cls.fields:
					cp.set(section, key, item.join(key))
				elif key in ['mail']:
					cp.set(section, 'email', item.join(key))
				elif key in ['cn']:
					cp.set(section, 'name', item.join(key))
			i += 1
		cp.write(fh)


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
		except ValueError as e:
			log.warning("ValueError after reading %i records: %s"
				% (parser.records_read, e))
		for entry in parser.entries.itervalues():
			yield MultiDict(entry)

	@classmethod
	def dump(cls, fh):
		if isinstance(ldif, Exception):
			raise ldif
		raise NotImplementedError


class VCard(Format):
	@classmethod
	def load(cls, fh):
		if isinstance(vobject, Exception):
			raise vobject

		for vcard in vobject.readComponents(fh):
			d = MultiDict()
			for key, value in vcard.contents.iteritems():
				d[key] = [i.value for i in value]
			yield d

	@classmethod
	def dump(cls, data, fh):
		if isinstance(vobject, Exception):
			raise vobject

		for item in data:
			vcard = vobject.vCard()
			for key in item:
				vcard.add(key).value = item.join(key)
			vcard.serialize(fh)


class JSON(Format):
	@classmethod
	def load(cls, fh):
		return [MultiDict(i) for i in json.load(fh)]

	@classmethod
	def dump(cls, data, fh):
		json.dump(list(data), fh, indent=4)


if __name__ == '__main__':
	informats = {
		'abook': ABook,
		'json': JSON,
	}
	outformats = {
		'bsdcal': BSDCal,
		'abook': ABook,
		'json': JSON,
	}
	if not isinstance(vobject, Exception):
		informats['ics'] = ICal
		outformats['ics'] = ICal
		informats['vcf'] = VCard
		outformats['vcf'] = VCard
	if not isinstance(ldif, Exception):
		informats['ldif'] = LDIF

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('--from', '-f', choices=informats.keys(), dest='informat')
	parser.add_argument('--to', '-t', choices=outformats.keys(), dest='outformat')
	parser.add_argument('input', nargs='?')
	parser.add_argument('--output', '-o')
	args = parser.parse_args()

	if args.informat is None and args.input is not None:
		ext = args.input.split(os.path.extsep)[-1]
		if ext in informats:
			args.informat = ext
	if args.informat is None:
		print("Missing input format")
		sys.exit(1)

	if args.outformat is None and args.output is not None:
		ext = args.output.split(os.path.extsep)[-1]
		if ext in outformats:
			args.outformat = ext
	if args.outformat is None:
		print("Missing output format")
		sys.exit(1)

	reload(sys)
	sys.setdefaultencoding('utf-8')

	infile = sys.stdin if args.input is None else open(args.input)
	outfile = sys.stdout if args.output is None else open(args.output)

	data = informats[args.informat]().load(infile)
	outformats[args.outformat]().dump(data, outfile)
