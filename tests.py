from __future__ import unicode_literals

import unittest
from datetime import datetime
from io import BytesIO

import cctool

dt = datetime(datetime.today().year, 1, 1)


class TestMultiDict(unittest.TestCase):
	def setUp(self):
		self.d = cctool.MultiDict()

	def test_construct_list(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
		])

		self.assertEqual(list(d.keys()), ['foo', 'bar'])
		self.assertEqual(d['foo'], [1, 2])
		self.assertEqual(d['bar'], [3, 4])

	def test_construct_dict(self):
		d = cctool.MultiDict({
			'foo': [1, 2],
			'bar': [3, 4],
		})

		self.assertEqual(set(d.keys()), set(['foo', 'bar']))
		self.assertEqual(d['foo'], [1, 2])
		self.assertEqual(d['bar'], [3, 4])

	def test_containes(self):
		self.assertFalse('foo' in self.d)
		self.d['foo'] = [1, 2, 3]
		self.assertTrue('foo' in self.d)
		self.d['foo'] = []
		self.assertFalse('foo' in self.d)

	def test_get(self):
		self.assertEqual(self.d['foo'], [])
		self.d['foo'] = [1, 2, 3]
		self.assertEqual(self.d['foo'], [1, 2, 3])

	def test_first(self):
		self.assertRaises(KeyError, self.d.first, 'foo')
		self.assertEqual(self.d.first('foo', default='bar'), 'bar')
		self.d['foo'] = [1, 2, 3]
		self.assertEqual(self.d.first('foo'), 1)

	def test_join(self):
		self.d['foo'] = ['1', '2', '3']
		self.assertEqual(self.d.join('foo'), '1,2,3')
		self.assertEqual(self.d.join('bar', default='baz'), 'baz')

	def test_join_missing_key(self):
		with self.assertRaises(KeyError):
			self.d.join('foo', default=None)

	def test_update(self):
		self.d['foo'] = [1]
		self.d['bar'] = [1, 2]

		md = cctool.MultiDict()
		md['foo'] = [2, 3]
		md['baz'] = [1, 2, 4]

		self.d.update(md)
		self.assertEqual(self.d['foo'], [1, 2, 3])
		self.assertEqual(self.d['bar'], [1, 2])
		self.assertEqual(self.d['baz'], [1, 2, 4])


class TestMerged(unittest.TestCase):
	def test_merged(self):
		data = [
			cctool.MultiDict({'foo': [1], 'bar': [1, 2]}),
			cctool.MultiDict({'foo': [1], 'bar': [2, 3]}),
			cctool.MultiDict({'foo': [2], 'bar': [4]}),
			cctool.MultiDict({'bar': [5]}),
		]
		expected = [
			cctool.MultiDict({'foo': [1], 'bar': [1, 2, 3]}),
			cctool.MultiDict({'foo': [2], 'bar': [4]}),
			cctool.MultiDict({'bar': [5]}),
		]
		actual = cctool.merged(data, key='foo')
		for item in expected:
			self.assertIn(item, actual)
		for item in actual:
			self.assertIn(item, expected)


class TestMapKeys(unittest.TestCase):
	def test_simple(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'baz'
		})

		self.assertEqual(list(d2.keys()), ['baz'])
		self.assertEqual(d2['baz'], [1, 2])

	def test_keep_order(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
			('baz', [4, 5]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'bar',
			'bar': 'baz',
			'baz': 'foo',
		})

		self.assertEqual(list(d2.keys()), ['bar', 'baz', 'foo'])
		self.assertEqual(d2['bar'], [1, 2])
		self.assertEqual(d2['baz'], [3, 4])
		self.assertEqual(d2['foo'], [4, 5])

	def test_reverse(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
			('baz', [4, 5]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'bar',
			'bar': 'baz',
			'baz': 'foo',
		}, reverse=True)

		self.assertEqual(list(d2.keys()), ['baz', 'foo', 'bar'])
		self.assertEqual(d2['baz'], [1, 2])
		self.assertEqual(d2['foo'], [3, 4])
		self.assertEqual(d2['bar'], [4, 5])

	def test_non_exclusive(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'baz'
		}, exclusive=False)

		self.assertEqual(list(d2.keys()), ['baz', 'bar'])
		self.assertEqual(d2['baz'], [1, 2])
		self.assertEqual(d2['bar'], [3, 4])

	def test_join(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
			('baz', [4, 5]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'foo',
			'bar': 'foo',
			'baz': 'baz',
		})

		self.assertEqual(list(d2.keys()), ['foo', 'baz'])
		self.assertEqual(d2['foo'], [1, 2, 3, 4])
		self.assertEqual(d2['baz'], [4, 5])

	@unittest.skip  # non deterministic
	def test_join_reverse(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
			('baz', [4, 5]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'foo',
			'bar': 'foo',
			'baz': 'baz',
		}, reverse=True)

		self.assertEqual(list(d2.keys()), ['bar', 'baz'])
		self.assertEqual(d2['bar'], [1, 2])
		self.assertEqual(d2['baz'], [4, 5])

	def test_non_destructive(self):
		d = cctool.MultiDict([
			('foo', [1, 2]),
			('bar', [3, 4]),
			('baz', [4, 5]),
		])

		d2 = cctool.map_keys(d, {
			'foo': 'bar',
			'bar': 'baz',
			'baz': 'foo',
		})

		self.assertEqual(list(d.keys()), ['foo', 'bar', 'baz'])
		self.assertEqual(d['foo'], [1, 2])
		self.assertEqual(d['bar'], [3, 4])
		self.assertEqual(d['baz'], [4, 5])


class TestEvent2Person(unittest.TestCase):
	def test_event2person(self):
		items = list(cctool.event2person([cctool.MultiDict([
			('summary', ['some summary']),
			('dtstart', [dt]),
			('tag', ['tag1', 'tag2']),
		])]))

		self.assertEqual(list(items[0].keys()), ['name', 'bday', 'tag'])
		self.assertEqual(items[0]['name'], ['some summary'])
		self.assertEqual(items[0]['bday'], [dt])
		self.assertEqual(items[0]['tag'], ['tag1', 'tag2'])

	def test_person2event(self):
		items = list(cctool.event2person([cctool.MultiDict([
			('name', ['some name']),
			('bday', [dt]),
			('tag', ['tag1', 'tag2']),
		])], reverse=True))

		self.assertEqual(list(items[0].keys()), ['summary', 'dtstart', 'tag', 'freq'])
		self.assertEqual(items[0]['summary'], ['some name'])
		self.assertEqual(items[0]['dtstart'], [dt])
		self.assertEqual(items[0]['tag'], ['tag1', 'tag2'])
		self.assertEqual(items[0]['freq'], ['yearly'])

	def test_event2person_wo_dtstart(self):
		items = list(cctool.event2person([cctool.MultiDict([
			('summary', ['some summary']),
			('tag', ['tag1', 'tag2']),
		])]))

		self.assertEqual(list(items[0].keys()), ['name', 'tag'])
		self.assertEqual(items[0]['name'], ['some summary'])
		self.assertEqual(items[0]['tag'], ['tag1', 'tag2'])

	def test_person2event_wo_dtstart(self):
		items = list(cctool.event2person([cctool.MultiDict([
			('name', ['some name']),
			('tag', ['tag1', 'tag2']),
		])], reverse=True))

		self.assertEqual(len(items), 0)


class _TestFormat(unittest.TestCase):
	data = [cctool.MultiDict({'name': ['foo']})]

	def test_load(self):
		self.assertEqual(list(self.format.loads(self.text)), self.data)

	def test_dump(self):
		self.assertEqual(self.format.dumps(self.data), self.text)


class TestBSDCal(_TestFormat):
	def setUp(self):
		self.format = cctool.BSDCal()
		self.data = [
			cctool.MultiDict([
				('dtstart', [dt]),
				('summary', ['foo']),
			]),
			cctool.MultiDict([
				('dtstart', [dt]),
				('summary', ['bar']),
				('freq', ['yearly']),
			]),
		]
		self.text = b'01/01\tfoo\n01/01*\tbar\n'


@unittest.skipIf(isinstance(cctool.icalendar, Exception), 'icalendar not available')
class TestICal(_TestFormat):
	def setUp(self):
		self.format = cctool.ICal()
		self.data = [
			cctool.MultiDict([
				('summary', ['lorem ipsum']),
				('dtstart', [dt]),
				('freq', ['daily']),
			]),
			cctool.MultiDict([
				('summary', ['lorem ipsum2', 'lorem ipsum3']),
				('dtstart', [dt.date()]),
			]),
		]
		self.text = b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//XI//NONSGML CCTOOL//\r\nBEGIN:VEVENT\r\nSUMMARY:lorem ipsum\r\nDTSTART;VALUE=DATE-TIME:20150101T000000\r\nRRULE:FREQ=DAILY\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:lorem ipsum2\r\nSUMMARY:lorem ipsum3\r\nDTSTART;VALUE=DATE:20150101\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'


class TestABook(_TestFormat):
	def setUp(self):
		self.format = cctool.ABook()
		self.data = [cctool.MultiDict([
			('name', ['foo']),
			('bday', [datetime(1970, 1, 1)]),
		])]
		self.text = b'[0]\nname = foo\nbday = 1970-01-01\n\n'


@unittest.skipIf(isinstance(cctool.ldif3, Exception), 'ldif3 not available')
class TestLDIF(_TestFormat):
	def setUp(self):
		self.format = cctool.LDIF()
		self.data = [cctool.MultiDict([
			('name', ['foo']),
			('email', ['foo@example.com']),
		])]
		self.text = b'cn: foo\nmail:: Zm9vQGV4YW1wbGUuY29t'

	def test_dump(self):
		pass


class TestJSON(_TestFormat):
	def setUp(self):
		self.format = cctool.JSON()
		self.text = b'[\n    {\n        "name": [\n            "foo"\n        ]\n    }\n]'


class TestPickle(_TestFormat):
	def setUp(self):
		self.format = cctool.Pickle()

	# the serialization is different in py3, even with same protocol.
	# so we only test that the data is not changes by encode/decode.
	def test_combined(self):
		tmp = self.format.dumps(self.data)
		actual = self.format.loads(tmp)
		self.assertEqual(list(actual), self.data)

	def test_dump(self):
		pass

	def test_load(self):
		pass


@unittest.skipIf(isinstance(cctool.yaml, Exception), 'yaml not available')
class TestYAML(_TestFormat):
	def setUp(self):
		self.format = cctool.YAML()
		self.text = b'- name: [foo]\n'


class TestArgs(unittest.TestCase):
	def test_args(self):
		args = cctool.parse_args(['-f', 'abook', '-t', 'bsdcal'])
		self.assertEqual(args.informat, 'abook')
		self.assertEqual(args.outformat, 'bsdcal')


class ArgsMock(object):
	outformat = None
	output = None


class TestGetOutformat(unittest.TestCase):
	def test_arg(self):
		args = ArgsMock()
		args.outformat = 'json'

		self.assertEqual(cctool.get_outformat(args), 'json')

	def test_extension(self):
		args = ArgsMock()
		args.output = 'foo.json'

		self.assertEqual(cctool.get_outformat(args), 'json')


class TestGetInformat(unittest.TestCase):
	def test_extension(self):
		filename = 'foo.json'
		e, fn = cctool.get_informat(filename)

		self.assertEqual(e, 'json')
		self.assertEqual(fn, filename)

	def test_colon(self):
		filename = 'foo:json'
		e, fn = cctool.get_informat(filename)

		self.assertEqual(e, 'json')
		self.assertEqual(fn, 'foo')

	def test_both(self):
		filename = 'foo.json:json'
		e, fn = cctool.get_informat(filename)

		self.assertEqual(e, 'json')
		self.assertEqual(fn, 'foo.json')


if __name__ == '__main__':
    unittest.main()
