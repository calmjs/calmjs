# -*- coding: utf-8 -*-
import unittest
import sys
from os.path import pathsep

from argparse import Namespace
from argparse import _

from calmjs.argparse import ArgumentParser
from calmjs.argparse import StoreCommaDelimitedList
from calmjs.argparse import StoreDelimitedListBase
from calmjs.argparse import StorePathSepDelimitedList
from calmjs.argparse import StoreRequirementList
# test for Version done as part of the runtime.

from calmjs.testing.utils import stub_stdouts


class ArgumentParserTestCase(unittest.TestCase):

    def test_filtered(self):
        stub_stdouts(self)
        parser = ArgumentParser()
        with self.assertRaises(SystemExit):
            parser.error('some random other error')

        self.assertIn('some random other error', sys.stderr.getvalue())

    def test_error(self):
        stub_stdouts(self)
        parser = ArgumentParser()
        parser.error(_('too few arguments'))
        self.assertEqual('', sys.stdout.getvalue())
        self.assertEqual('', sys.stderr.getvalue())


class StoreCommaDelimitedListTestCase(unittest.TestCase):
    """
    Test out the StoreCommaDelimitedList action
    """

    def test_basic_singlevalue(self):
        namespace = Namespace()
        parser = None
        action = StoreCommaDelimitedList('', dest='basic')
        action(parser, namespace, ['singlevalue'])
        self.assertEqual(namespace.basic, ['singlevalue'])

    def test_basic_multivalue(self):
        namespace = Namespace()
        parser = None
        action = StoreCommaDelimitedList('', dest='basic')
        action(parser, namespace, ['single,double,triple'])
        self.assertEqual(namespace.basic, ['single', 'double', 'triple'])

    def test_basic_multivalue_alt_sep(self):
        namespace = Namespace()
        parser = None
        action = StoreDelimitedListBase('', dest='basic', sep='.')
        action(parser, namespace, ['single,double.triple'])
        self.assertEqual(namespace.basic, ['single,double', 'triple'])

    def test_fail_argument(self):
        with self.assertRaises(ValueError):
            StoreCommaDelimitedList('', dest='basic', default='default')

    def test_integration(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        with self.assertRaises(ValueError):
            argparser.add_argument(
                '-p', '--params', action=StoreCommaDelimitedList,
                default='123')

        argparser.add_argument(
            '-p', '--params', action=StoreCommaDelimitedList,
            default=('1', '2',))

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args(['-p', '34'])
        self.assertEqual(parsed.params, ['34'])

        parsed, extras = argparser.parse_known_args([])
        self.assertEqual(parsed.params, ('1', '2'))

    def test_integration_optional(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', action=StoreCommaDelimitedList, required=False)

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args()
        self.assertEqual(parsed.params, None)


class StorePathSepDelimitedListTestCase(unittest.TestCase):
    """
    For the path separator version.
    """

    def test_basic_singlevalue(self):
        namespace = Namespace()
        parser = None
        action = StorePathSepDelimitedList('', dest='basic')
        action(parser, namespace, ['singlevalue'])
        self.assertEqual(namespace.basic, ['singlevalue'])

    def test_multiple_values(self):
        namespace = Namespace()
        parser = None
        action = StorePathSepDelimitedList('', dest='basic')
        action(parser, namespace, [pathsep.join(['file1', 'file2'])])
        self.assertEqual(namespace.basic, ['file1', 'file2'])


class StoreRequirementListTestCase(unittest.TestCase):

    def test_basic_singlevalue(self):
        namespace = Namespace()
        parser = None
        action = StoreRequirementList('', dest='basic')
        action(parser, namespace, ['singlevalue'])
        self.assertEqual(namespace.basic, ['singlevalue'])

        action(parser, namespace, ['single,value'])
        self.assertEqual(namespace.basic, ['single', 'value'])

        action(parser, namespace, ['single[1,2,3],value'])
        self.assertEqual(namespace.basic, ['single[1,2,3]', 'value'])

        action(parser, namespace, ['single.value'])
        self.assertEqual(namespace.basic, ['single.value'])

        action(parser, namespace, ['single[1,2,3]'])
        self.assertEqual(namespace.basic, ['single[1,2,3]'])
