# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import unittest
import sys
from io import StringIO
from os.path import join

from calmjs import ui
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import mkdtemp

isatty = sys.stdin.isatty()


class CliCheckInteractiveTestCase(unittest.TestCase):

    def test_check_interactive_fail(self):
        self.assertFalse(ui._check_interactive(
            StringIO(), StringIO()))

    def test_check_interactive_not_stdin(self):
        tempdir = mkdtemp(self)
        fn = join(tempdir, 'test')
        with open(fn, 'w') as fd1:
            self.assertFalse(ui._check_interactive(fd1))

        with open(fn) as fd2:
            self.assertFalse(ui._check_interactive(fd2, fd1))

    @unittest.skipIf(not isatty, 'Environment not a tty')
    def test_check_interactive_good(self):
        self.assertTrue(ui._check_interactive(sys.__stdin__, sys.__stdout__))


class MakeChoiceValidatorTestCase(unittest.TestCase):

    def setUp(self):
        self.validator = ui.make_choice_validator([
            ('foo', 'Foo'),
            ('bar', 'Bar'),
            ('baz', 'Baz'),
            ('YES', 'Yes'),
            ('yes', 'yes'),
        ])

    def test_default_choice(self):
        self.validator = ui.make_choice_validator([
            ('foo', 'Foo'),
            ('bar', 'Bar'),
            ('baz', 'Baz'),
        ], default_key=2)
        self.assertEqual(self.validator(''), 'Baz')

    def test_matched(self):
        self.assertEqual(self.validator('f'), 'Foo')
        self.assertEqual(self.validator('foo'), 'Foo')

    def test_no_normalize(self):
        self.assertEqual(self.validator('Y'), 'Yes')
        self.assertEqual(self.validator('y'), 'yes')

    def test_ambiguous(self):
        with self.assertRaises(ValueError) as e:
            self.validator('ba')

        self.assertEqual(
            str(e.exception), 'Choice ambiguous between (bar, baz)')

    def test_normalized(self):
        validator = ui.make_choice_validator([
            ('Yes', True),
            ('No', False),
        ], normalizer=ui.lower)
        with self.assertRaises(ValueError) as e:
            validator('ba')

        self.assertEqual(
            str(e.exception), 'Invalid choice.')

    def test_null_validator(self):
        # doesn't really belong in this class but similar enough topic
        self.assertEqual(ui.null_validator('test'), 'test')


class CliPromptTestCase(unittest.TestCase):

    def setUp(self):
        self.stdout = StringIO()

    def prompt(self, question, answer,
               validator=None, choices=None,
               default_key=None, normalizer=None):
        stdin = StringIO(answer)
        return ui.prompt(
            question, validator, choices, default_key,
            _stdin=stdin, _stdout=self.stdout)

    def test_prompt_basic(self):
        result = self.prompt('How are you?', 'I am fine thank you.\n')
        self.assertEqual(result, 'I am fine thank you.')

    def test_prompt_basic_choice_overridden(self):
        # Extra choices with a specific validator will not work
        result = self.prompt(
            'How are you?', 'I am fine thank you.\n', choices=(
                ('a', 'A'),
                ('b', 'B'),
                ('c', 'C'),
            ),
            # explicit validator negates the choices
            validator=ui.null_validator,
        )
        self.assertEqual(result, 'I am fine thank you.')
        self.assertEqual(self.stdout.getvalue(), 'How are you? ')

    def test_prompt_choices_only(self):
        # Extra choices with a specific validator will not work
        result = self.prompt(
            'Nice day today.\nHow are you?', 'I am fine thank you.\n',
            choices=(
                ('a', 'A'),
                ('b', 'B'),
                ('c', 'C'),
            ),
            default_key=1,
        )
        self.assertEqual(result, 'B')
        self.assertEqual(
            self.stdout.getvalue(),
            'Nice day today.\n'
            'How are you? (a/b/c) [b] '  # I am fine thank you.\n
            'Invalid choice.\n'
            'How are you? (a/b/c) [b] '
        )

    def test_prompt_choices_canceled(self):
        # Extra choices with a specific validator will not work
        result = self.prompt(
            'How are you?', '', validator=fake_error(KeyboardInterrupt))
        self.assertIsNone(result, None)
        self.assertEqual(
            self.stdout.getvalue(),
            'How are you? Aborted.\n')
