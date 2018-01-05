# -*- coding: utf-8 -*-
import unittest
import sys
from os.path import pathsep

import argparse
from argparse import _

from calmjs.argparse import ArgumentParser
from calmjs.argparse import HyphenNoBreakHelpFormatter
from calmjs.argparse import Namespace
from calmjs.argparse import MultiChoice
from calmjs.argparse import SortedHelpFormatter
from calmjs.argparse import StoreCommaDelimitedList
from calmjs.argparse import StoreDelimitedListBase
from calmjs.argparse import StorePathSepDelimitedList
from calmjs.argparse import StoreRequirementList
# test for Version done as part of the runtime.

from calmjs.testing.mocks import StringIO
from calmjs.testing.utils import stub_stdouts


class NamespaceTestCase(unittest.TestCase):
    """
    Test the namespace assignment operates with special consideration
    for list of values.
    """

    def test_assigment_standard(self):
        ns = Namespace()
        ns.a = 'a'
        self.assertEqual(ns.a, 'a')
        ns.a = 'b'
        self.assertEqual(ns.a, 'b')
        ns.a = 'b'
        self.assertEqual(ns.a, 'b')

    def test_assigment_list(self):
        ns = Namespace()
        ns.a = ['value1']
        self.assertEqual(ns.a, ['value1'])
        ns.a = ['value2']
        self.assertEqual(ns.a, ['value1', 'value2'])

        # overridden.
        ns.a = None
        self.assertEqual(ns.a, None)
        ns.a = ['value1']
        ns.a = 'b'
        self.assertEqual(ns.a, 'b')

    def test_assigment_dict(self):
        ns = Namespace()
        ns.a = {'a': '1'}
        self.assertEqual(ns.a, {'a': '1'})
        ns.a = {'b': '2'}
        self.assertEqual(ns.a, {'a': '1', 'b': '2'})

        # overridden.
        ns.a = None
        self.assertEqual(ns.a, None)
        ns.a = {'b': '1'}
        ns.a = 'b'
        self.assertEqual(ns.a, 'b')


class MultiChoiceTestCase(unittest.TestCase):

    def test_empty(self):
        choices = MultiChoice(choices=())
        self.assertNotIn('', choices)
        self.assertNotIn('something', choices)

    def test_singular(self):
        choices = MultiChoice(choices=('foo',))
        self.assertIn('foo', choices)
        self.assertIn('foo,foo', choices)
        self.assertNotIn('bar', choices)

    def test_multiple(self):
        choices = MultiChoice(choices=('foo', 'bar', 'baz'))
        self.assertIn('foo', choices)
        self.assertIn('foo,foo', choices)
        self.assertIn('bar', choices)
        self.assertIn('foo,bar,baz', choices)
        self.assertNotIn('foo,bar,bad', choices)
        self.assertNotIn('bad', choices)


class HelpFormatterTestCase(unittest.TestCase):
    """
    Test the various help formatters, possibly through Argumentparser
    """

    def test_hyphen(self):
        formatter = HyphenNoBreakHelpFormatter(prog='prog')
        result = formatter._split_lines('the flag is --flag', 15)
        self.assertEqual(result, ['the flag is', '--flag'])

    def test_sorted_standard(self):
        parser = argparse.ArgumentParser(
            formatter_class=SortedHelpFormatter, add_help=False)
        parser.add_argument('-z', '--zebra', help='make zebras')
        parser.add_argument('-a', '--alpaca', help='make alpacas')
        parser.add_argument('-s', '--sheep', help='make sheep')
        parser.add_argument('-g', '--goat', help='make goats')
        stream = StringIO()
        parser.print_help(file=stream)
        options = [
            line.split()[0]
            for line in stream.getvalue().splitlines() if
            '--' in line
        ]
        self.assertEqual(options, ['-a', '-g', '-s', '-z'])

    def test_sorted_case_insensitivity(self):
        parser = argparse.ArgumentParser(
            formatter_class=SortedHelpFormatter, add_help=False)
        parser.add_argument('-z', '--zebra', help='make zebras')
        parser.add_argument('-a', '--alpaca', help='make alpacas')
        parser.add_argument('-A', '--anteater', help='make anteater')
        parser.add_argument('-S', '--SNAKE', help='make snake')
        parser.add_argument('-s', '--sheep', help='make sheep')
        parser.add_argument('-g', '--goat', help='make goats')
        stream = StringIO()
        parser.print_help(file=stream)
        options = [
            line.split()[0]
            for line in stream.getvalue().splitlines() if
            '--' in line
        ]
        # the case is unspecified due to in-place sorting
        self.assertEqual(options, ['-a', '-A', '-g', '-S', '-s', '-z'])

    def test_sorted_simple_first(self):
        parser = argparse.ArgumentParser(
            formatter_class=SortedHelpFormatter, add_help=False)
        parser.add_argument('-z', '--zebra', help='make zebras')
        parser.add_argument('-a', '--alpaca', help='make alpacas')
        parser.add_argument('-A', '--anteater', help='make anteater')
        parser.add_argument('--SNAKE', help='make snake')
        parser.add_argument('--sheep', help='make sheep')
        parser.add_argument('--goat', help='make goats')
        stream = StringIO()
        parser.print_help(file=stream)
        options = [
            line.split()[0]
            for line in stream.getvalue().splitlines() if
            '--' in line and '[' not in line
        ]
        # the case is unspecified due to in-place sorting
        self.assertEqual(options, [
            '-a', '-A', '-z', '--goat', '--sheep', '--SNAKE'])


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

    def test_basic_emptyvalue(self):
        namespace = Namespace()
        parser = None
        action = StoreCommaDelimitedList('', dest='basic')
        action(parser, namespace, [''])
        self.assertEqual(namespace.basic, [])

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

    def test_integration_invalid_default_value(self):
        argparser = ArgumentParser(prog='prog', add_help=False)
        with self.assertRaises(ValueError):
            argparser.add_argument(
                '-p', '--params', action=StoreCommaDelimitedList,
                default='123')

    def test_integration(self):
        argparser = ArgumentParser(prog='prog', add_help=False)
        argparser.add_argument(
            '-p', '--params', action=StoreCommaDelimitedList,
            default=('1', '2',))

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args(['-p', '34'])
        self.assertEqual(parsed.params, ['34'])

        parsed, extras = argparser.parse_known_args([])
        self.assertEqual(parsed.params, ('1', '2'))

    def test_integration_edge_cases(self):
        argparser = ArgumentParser(prog='prog', add_help=False)
        argparser.add_argument(
            '-p', '--params', action=StoreCommaDelimitedList,
            default=['1', '2'])

        parsed, extras = argparser.parse_known_args(['--params=1,2'])
        self.assertEqual(parsed.params, ['1', '2'])

        parsed, extras = argparser.parse_known_args(['--params=8', '-p', '3'])
        self.assertEqual(parsed.params, ['8', '3'])

        parsed, extras = argparser.parse_known_args(['--params', ''])
        self.assertEqual(parsed.params, [])

        parsed, extras = argparser.parse_known_args(['--params='])
        self.assertEqual(parsed.params, [])

        parsed, extras = argparser.parse_known_args(['--params=,'])
        self.assertEqual(parsed.params, [''])

        parsed, extras = argparser.parse_known_args(['--params=1,'])
        self.assertEqual(parsed.params, ['1'])

    def test_integration_optional(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', action=StoreCommaDelimitedList, required=False)

        parsed, extras = argparser.parse_known_args(['-p', '3,4'])
        self.assertEqual(parsed.params, ['3', '4'])

        parsed, extras = argparser.parse_known_args()
        self.assertEqual(parsed.params, None)

    def test_integration_optional_kwargs(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', action=StoreDelimitedListBase, sep='.')

        parsed, extras = argparser.parse_known_args(['-p', '3,4.5'])
        self.assertEqual(parsed.params, ['3,4', '5'])

    def test_integration_set_limit(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', action=StoreDelimitedListBase, maxlen=1)

        parsed, extras = argparser.parse_known_args(['-p', '3,4,5'])
        self.assertEqual(parsed.params, ['3'])

    def test_integration_choices_in_list(self):
        argparser = ArgumentParser(prog='prog', add_help=False)

        argparser.add_argument(
            '-p', '--params', choices=['1', '2', '3'],
            action=StoreDelimitedListBase)

        parsed, extras = argparser.parse_known_args(['-p', '3'])
        self.assertEqual(parsed.params, ['3'])
        parsed, extras = argparser.parse_known_args(['-p', '3,2'])
        self.assertEqual(parsed.params, ['3', '2'])
        parsed, extras = argparser.parse_known_args(['-p', '3,2,1'])
        self.assertEqual(parsed.params, ['3', '2', '1'])
        parsed, extras = argparser.parse_known_args(['-p', '3,3,3'])
        self.assertEqual(parsed.params, ['3', '3', '3'])

        stub_stdouts(self)

        with self.assertRaises(SystemExit):
            argparser.parse_known_args(['-p', '3,2,1,0'])

        self.assertIn("(choose from '1', '2', '3')", sys.stderr.getvalue())

        with self.assertRaises(SystemExit):
            argparser.parse_known_args(['-p', '0'])

        argparser.add_argument(
            '--dot', choices=['a', 'b', 'c'],
            action=StoreDelimitedListBase, sep='.')
        parsed, extras = argparser.parse_known_args(['--dot', 'a.b.c'])
        self.assertEqual(parsed.dot, ['a', 'b', 'c'])

        with self.assertRaises(SystemExit):
            argparser.parse_known_args(['--dot', 'a,b,c'])

    def test_deprecation(self):
        import warnings
        argparser = ArgumentParser(prog='prog', add_help=False)
        argparser.add_argument('-n', '--normal', action='store')
        argparser.add_argument(
            '-d', '--deprecated', action='store', deprecation=True)
        argparser.add_argument(
            '--bye', action=StoreDelimitedListBase, deprecation='bye')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            # test that they store stuff
            args = argparser.parse_args(['-n', 'hello'])
            self.assertEqual(args.normal, 'hello')
            args = argparser.parse_args(['-d', 'hello'])
            self.assertEqual(args.deprecated, 'hello')
            args = argparser.parse_args(['--deprecated', 'hello'])
            self.assertEqual(args.deprecated, 'hello')
            args = argparser.parse_args(['--bye', 'hello,goodbye'])
            self.assertEqual(args.bye, ['hello', 'goodbye'])

        # and the warnings are triggered
        self.assertEqual(
            "option '-d' is deprecated", str(w[0].message))
        self.assertEqual(
            "option '--deprecated' is deprecated", str(w[1].message))
        self.assertEqual(
            "option '--bye' is deprecated: bye", str(w[2].message))

        stream = StringIO()
        argparser.print_help(file=stream)
        # deprecated options are not visible on help
        self.assertNotIn("--deprecated", stream.getvalue())
        self.assertNotIn("--bye", stream.getvalue())
        self.assertIn("--normal", stream.getvalue())


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

        # this is accumulative since previous existing values exist in
        # namespace.
        action(parser, namespace, ['single,value'])
        self.assertEqual(namespace.basic, ['singlevalue', 'single', 'value'])

    def test_extras_not_split(self):
        namespace = Namespace()
        parser = None
        action = StoreRequirementList('', dest='basic')
        action(parser, namespace, ['single[1,2,3],value'])
        self.assertEqual(namespace.basic, ['single[1,2,3]', 'value'])

    def test_dotted_not_split(self):
        namespace = Namespace()
        parser = None
        action = StoreRequirementList('', dest='basic')
        action(parser, namespace, ['single.value'])
        self.assertEqual(namespace.basic, ['single.value'])

    def test_single_extras(self):
        namespace = Namespace()
        parser = None
        action = StoreRequirementList('', dest='basic')
        action(parser, namespace, ['single[1,2,3]'])
        self.assertEqual(namespace.basic, ['single[1,2,3]'])
