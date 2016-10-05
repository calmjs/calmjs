# -*- coding: utf-8 -*-
import unittest

from argparse import Namespace
from argparse import ArgumentParser

from calmjs.argparse import StoreDelimitedList
# test for Version done as part of the runtime.


class StoreDelimitedListTestCase(unittest.TestCase):
    """
    Test out the StoreDelimitedList action
    """

    def test_basic_singlevalue(self):
        namespace = Namespace()
        parser = None
        action = StoreDelimitedList('', dest='basic')
        action(parser, namespace, ['singlevalue'])
        self.assertEqual(namespace.basic, ['singlevalue'])

    def test_basic_multivalue(self):
        namespace = Namespace()
        parser = None
        action = StoreDelimitedList('', dest='basic')
        action(parser, namespace, ['single,double,triple'])
        self.assertEqual(namespace.basic, ['single', 'double', 'triple'])

    def test_basic_multivalue_alt_sep(self):
        namespace = Namespace()
        parser = None
        action = StoreDelimitedList('', dest='basic', sep='.')
        action(parser, namespace, ['single,double.triple'])
        self.assertEqual(namespace.basic, ['single,double', 'triple'])

    def test_fail_argument(self):
        with self.assertRaises(ValueError):
            StoreDelimitedList('', dest='basic', default='default')

    def test_integration(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        with self.assertRaises(ValueError):
            argparser.add_argument(
                '-p', '--params', action=StoreDelimitedList, default='123')

        argparser.add_argument(
            '-p', '--params', action=StoreDelimitedList, default=('1', '2',))

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args(['-p', '34'])
        self.assertEqual(parsed.params, ['34'])

        parsed, extras = argparser.parse_known_args([])
        self.assertEqual(parsed.params, ('1', '2'))

    def test_integration_optional(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', action=StoreDelimitedList, required=False)

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args()
        self.assertEqual(parsed.params, None)
