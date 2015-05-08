import unittest
from datetime import datetime

import cctool

dt = datetime(datetime.today().year, 1, 1)


class TestMultiDict(unittest.TestCase):
	def setUp(self):
		self.d = cctool.MultiDict()

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
			cctool.MultiDict({'dtstart': [dt], 'summary': ['foo']}),
			cctool.MultiDict({'bday': [dt], 'name': ['bar']}),
		]
		self.text = '01/01\tfoo\n01/01*\tbar\n'

	def test_load(self):
		pass


@unittest.skipIf(isinstance(cctool.vobject, Exception), 'vobject not available')
class TestICal(_TestFormat):
	def setUp(self):
		self.format = cctool.ICal()
		self.data = [cctool.MultiDict({u'uid': [u'20140519T210153Z-13022@tobias-eee']})]
		self.text = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//PYVOBJECT//NONSGML Version 1//EN\r\nBEGIN:VEVENT\r\nUID:20140519T210153Z-13022@tobias-eee\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'


class TestABook(_TestFormat):
	def setUp(self):
		self.format = cctool.ABook()
		self.data = [cctool.MultiDict([
			('name', ['foo']),
			('bday', [datetime(1970, 1, 1)]),
		])]
		self.text = '[0]\nname = foo\nbday = 1970-01-01\n\n'


@unittest.skipIf(isinstance(cctool.ldif, Exception), 'ldif not available')
class TestLDIF(_TestFormat):
	def setUp(self):
		self.format = cctool.LDIF()
		self.data = [cctool.MultiDict({'dn': ['foo']})]
		self.text = '[0]\ndn = foo\n\n'

	def test_dump(self):
		pass


class TestJSON(_TestFormat):
	def setUp(self):
		self.format = cctool.JSON()
		self.text = '[\n    {\n        "name": [\n            "foo"\n        ]\n    }\n]'


class TestPickle(_TestFormat):
	def setUp(self):
		self.format = cctool.Pickle()
		self.text = '(lp0\nccctool\nMultiDict\np1\n((lp2\n(lp3\nS\'name\'\np4\na(lp5\nS\'foo\'\np6\naaatp7\nRp8\na.'


class TestArgs(unittest.TestCase):
	def test_args(self):
		args = cctool.parse_args(['-f', 'abook', '-t', 'bsdcal'])
		self.assertEqual(args.informat, 'abook')
		self.assertEqual(args.outformat, 'bsdcal')


if __name__ == '__main__':
    unittest.main()
