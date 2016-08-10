# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from io import StringIO
import os
import sys
from os.path import join
from os.path import pathsep

from calmjs import cli
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_mod_check_output
from calmjs.testing.utils import stub_os_environ


class CliGenerateMergeDictTestCase(unittest.TestCase):

    def test_merge(self):
        result = cli.generate_merge_dict(
            ['key'], {'key': {'foo': 1}}, {'baz': 1}, {'key': {'bar': 1}})
        self.assertEqual(result, {'key': {
            'foo': 1,
            'bar': 1,
        }})

    def test_merge_multi(self):
        result = cli.generate_merge_dict(
            ['key', 'mm'],
            {'key': {'foo': 1}},
            {'mm': {'snek': 'best'}},
            {'key': {'foo': 2}})
        self.assertEqual(result, {
            'key': {'foo': 2},
            'mm': {'snek': 'best'},
        })

    def test_merge_none_matched(self):
        result = cli.generate_merge_dict(
            ['none', 'match'], {'key': 'foo'}, {'bar': 1}, {'key': 'bar'})
        self.assertEqual(result, {})

    def test_using_actual_use_case(self):
        spec1 = {
            'dependencies': {
                'jquery': '~3.0.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'foo',
        }

        spec2 = {
            'dependencies': {
                'jquery': '~1.11.0',
            },
            'devDependencies': {},
            'name': 'bar',
        }

        answer = {
            'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
        }

        result = cli.generate_merge_dict(
            ('dependencies', 'devDependencies'), spec1, spec2)

        # Naturally, the 'name' is missing and will need to be
        # reconciled separately... will figure this out later.
        self.assertEqual(result, answer)


class CliCheckInteractiveTestCase(unittest.TestCase):

    def test_check_interactive_fail(self):
        self.assertFalse(cli._check_interactive(StringIO(), StringIO()))

    def test_check_interactive_not_stdin(self):
        tempdir = mkdtemp(self)
        fn = join(tempdir, 'test')
        with open(fn, 'w') as fd1:
            self.assertFalse(cli._check_interactive(fd1))

        with open(fn) as fd2:
            self.assertFalse(cli._check_interactive(fd2, fd1))

    @unittest.skipIf(sys.__stdin__.name != '<stdin>', 'stdin is modified')
    def test_check_interactive_good(self):
        self.assertTrue(cli._check_interactive(sys.__stdin__, sys.__stdout__))


class MakeChoiceValidatorTestCase(unittest.TestCase):

    def setUp(self):
        self.validator = cli.make_choice_validator([
            ('foo', 'Foo'),
            ('bar', 'Bar'),
            ('baz', 'Baz'),
            ('YES', 'Yes'),
            ('yes', 'yes'),
        ])

    def test_default_choice(self):
        self.validator = cli.make_choice_validator([
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
        validator = cli.make_choice_validator([
            ('Yes', True),
            ('No', False),
        ], normalizer=cli.lower)
        with self.assertRaises(ValueError) as e:
            validator('ba')

        self.assertEqual(
            str(e.exception), 'Invalid choice.')

    def test_null_validator(self):
        # doesn't really belong in this class but similar enough topic
        self.assertEqual(cli.null_validator('test'), 'test')


class CliPromptTestCase(unittest.TestCase):

    def setUp(self):
        self.stdout = StringIO()

    def prompt(self, question, answer,
               validator=None, choices=None,
               default_key=None, normalizer=None):
        stdin = StringIO(answer)
        return cli.prompt(
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
            validator=cli.null_validator,
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


class CliDriverTestCase(unittest.TestCase):
    """
    Base cli driver class test case.
    """

    def test_get_bin_version_long(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'Some app v.1.2.3.4. All rights reserved'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1, 2, 3, 4))

    def test_get_bin_version_longer(self):
        stub_mod_check_output(self, cli)
        # tags are ignored for now.
        self.check_output_answer = b'version.11.200.345.4928-what'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (11, 200, 345, 4928))

    def test_get_bin_version_short(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'1'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1,))

    def test_get_bin_version_unexpected(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'Nothing'
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_get_bin_version_no_bin(self):
        stub_mod_check_output(self, cli, fake_error(OSError))
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_node_no_path(self):
        stub_os_environ(self)
        os.environ['PATH'] = ''
        self.assertIsNone(cli.get_node_version())

    def test_node_version_mocked(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'v0.10.25'
        version = cli.get_node_version()
        self.assertEqual(version, (0, 10, 25))

    # live test, no stubbing
    @unittest.skipIf(cli.get_node_version() is None, 'nodejs not found.')
    def test_node_version_get(self):
        version = cli.get_node_version()
        self.assertIsNotNone(version)

    def test_node_run_no_path(self):
        stub_os_environ(self)
        os.environ['PATH'] = ''
        with self.assertRaises(OSError):
            cli.node('process.stdout.write("Hello World!");')

    # live test, no stubbing
    @unittest.skipIf(cli.get_node_version() is None, 'nodejs not found.')
    def test_node_run(self):
        stdout, stderr = cli.node('process.stdout.write("Hello World!");')
        self.assertEqual(stdout, 'Hello World!')
        stdout, stderr = cli.node('window')
        self.assertIn('window is not defined', stderr)

    def test_helper_attr(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        with self.assertRaises(AttributeError) as e:
            driver.no_such_attr_here
        self.assertIn('no_such_attr_here', str(e.exception))
        self.assertIsNot(driver.mgr_init, None)
        self.assertIsNot(driver.get_mgr_version, None)
        driver.mgr_install()
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {}))

    def test_install_arguments(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        driver.pkg_manager_install(args=('--pedantic',))
        self.assertEqual(
            self.call_args, ((['mgr', 'install', '--pedantic'],), {}))

    def test_alternative_install_cmd(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr', install_cmd='sync')
        driver.pkg_manager_install()
        self.assertEqual(self.call_args, ((['mgr', 'sync'],), {}))

        # Naturally, the short hand call will be changed.
        driver.mgr_sync(args=('all',))
        self.assertEqual(self.call_args, ((['mgr', 'sync', 'all'],), {}))

    def test_install_other_environ(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        driver.pkg_manager_install(env={'MGR_ENV': 'production'})
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': {'MGR_ENV': 'production'},
        }))

    def test_set_node_path(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(node_path='./node_mods', pkg_manager_bin='mgr')

        # ensure env is passed into the call.
        driver.pkg_manager_install()
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': {'NODE_PATH': './node_mods'},
        }))

        # will be overridden by instance settings.
        driver.pkg_manager_install(env={
            'PATH': '.',
            'MGR_ENV': 'dev',
            'NODE_PATH': '/tmp/somewhere/else/node_mods',
        })
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': {'NODE_PATH': './node_mods', 'MGR_ENV': 'dev', 'PATH': '.'},
        }))

    def test_set_paths(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        driver.set_paths('some_path')
        # ensure env and cwdis passed into the call.
        driver.pkg_manager_install()
        args, kwargs = self.call_args
        self.assertEqual(kwargs['env']['PATH'].split(pathsep)[0], 'some_path')
        self.assertEqual(kwargs['cwd'], driver.working_dir)

    def test_set_paths_no_working_dir(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        # explicitly disable setting of cwd.
        driver.set_paths('some_path', None)
        # ensure env is passed into the call.
        driver.pkg_manager_install()
        args, kwargs = self.call_args
        self.assertEqual(kwargs['env']['PATH'].split(pathsep)[0], 'some_path')
        self.assertNotIn('cwd', kwargs)

    def test_set_paths_none(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        # explicitly disable setting of cwd.
        driver.set_paths(None)
        self.assertIs(driver.env_path, None)
        self.assertIs(driver.working_dir, None)
        # ensure nothing is passed through
        driver.pkg_manager_install()
        args, kwargs = self.call_args
        self.assertNotIn('PATH', kwargs)
        self.assertNotIn('cwd', kwargs)

    def test_set_paths_just_cwd(self):
        # no idea why, but sure.
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='mgr')
        # explicitly disable setting of cwd.
        driver.set_paths(None, 'some_cwd')
        self.assertIs(driver.env_path, None)
        self.assertEqual(driver.working_dir, 'some_cwd')
        # ensure nothing is passed through
        driver.pkg_manager_install()
        args, kwargs = self.call_args
        self.assertNotIn('PATH', kwargs)
        self.assertEqual(kwargs['cwd'], 'some_cwd')

    def test_set_binary(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='bower')

        # this will call ``bower install`` instead.
        driver.pkg_manager_install()
        self.assertEqual(self.call_args, ((['bower', 'install'],), {}))
