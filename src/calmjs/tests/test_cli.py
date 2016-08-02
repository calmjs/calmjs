# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from io import StringIO
import json
import os
import sys
from os.path import join
from os.path import exists

from pkg_resources import WorkingSet

from calmjs import cli
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_mod_check_output
from calmjs.testing.utils import stub_dist_flatten_package_json
from calmjs.testing.utils import stub_stdin
from calmjs.testing.utils import stub_stdouts


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

    def setUp(self):
        # keep copy of original os.environ
        self.original_env = {}
        self.original_env.update(os.environ)
        # working directory
        self.cwd = os.getcwd()

        # Forcibly enable interactive mode.
        self.inst_interactive, cli._inst.interactive = (
            cli._inst.interactive, True)

    def tearDown(self):
        cli._inst.interactive = self.inst_interactive
        # restore original os.environ from copy
        os.environ.clear()
        os.environ.update(self.original_env)
        os.chdir(self.cwd)

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

    def test_npm_no_path(self):
        os.environ['PATH'] = ''
        self.assertIsNone(cli.get_npm_version())

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_version_get(self):
        version = cli.get_npm_version()
        self.assertIsNotNone(version)

    def test_set_node_path(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(node_path='./node_mods')

        # ensure env is passed into the call.
        driver.pkg_manager_install()  # npm install
        self.assertEqual(self.call_args, ((['npm', 'install'],), {
            'env': {'NODE_PATH': './node_mods'},
        }))

    def test_set_binary(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='bower')

        # this will call ``bower install`` instead.
        driver.pkg_manager_install()
        self.assertEqual(self.call_args, ((['bower', 'install'],), {}))

    def test_npm_install_package_json(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # This is faked.
        cli.npm_install()
        # However we make sure that it's been fake called
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))
        self.assertFalse(exists(join(tmpdir, 'package.json')))

    def test_npm_install_package_json_no_overwrite_interactive(self):
        # Testing the implied init call
        stub_mod_call(self, cli)
        stub_stdouts(self)
        stub_stdin(self, 'n\n')
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # All the pre-made setup.
        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
        stub_dist_flatten_package_json(self, [cli], working_set)

        # We are going to have a fake package.json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({}, fd)

        # This is faked.
        cli.npm_install('foo')

        self.assertTrue(sys.stdout.getvalue().endswith(
            'Overwrite? (Yes/No) [No] '))
        # No log level set.
        self.assertEqual(sys.stderr.getvalue(), '')

        with open(join(tmpdir, 'package.json')) as fd:
            result = fd.read()
        # This should remain unchanged as no to overwrite is default.
        self.assertEqual(result, '{}')

    def test_npm_install_package_json_overwrite_interactive(self):
        # Testing the implied init call
        stub_mod_call(self, cli)
        stub_stdin(self, 'y\n')
        stub_stdouts(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # All the pre-made setup.
        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
        stub_dist_flatten_package_json(self, [cli], working_set)

        # We are going to have a fake package.json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({}, fd)

        # This is faked.
        cli.npm_install('foo', overwrite=True)

        with open(join(tmpdir, 'package.json')) as fd:
            config = json.load(fd)

        # Overwritten
        self.assertEqual(config, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

        # No log level set.
        self.assertEqual(sys.stdout.getvalue(), '')
        self.assertEqual(sys.stderr.getvalue(), '')


class CliDriverInitTestCase(unittest.TestCase):
    """
    Test driver init workflow separately, due to complexities involved.
    """

    def setUp(self):
        # save working directory
        self.cwd = os.getcwd()
        self.inst_interactive = cli._inst.interactive

        # All the pre-made setup.
        stub_mod_call(self, cli)
        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
        stub_dist_flatten_package_json(self, [cli], working_set)

    def tearDown(self):
        # restore original os.environ from copy
        cli._inst.interactive = self.inst_interactive
        os.chdir(self.cwd)

    def test_npm_init_new_non_interactive(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        self.assertTrue(cli.npm_init('foo', interactive=False))
        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

    def test_npm_init_existing_standard_non_interactive(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        self.assertFalse(cli.npm_init('foo', interactive=False))

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Does not overwrite by default.
        self.assertEqual(result, {
            'dependencies': {},
            'devDependencies': {},
        })

    def test_npm_init_existing_standard_interactive_canceled(self):
        stub_stdouts(self)
        stub_stdin(self, 'N')
        tmpdir = mkdtemp(self)
        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)
        os.chdir(tmpdir)

        # force interactivity to be True
        cli._inst.interactive = True
        self.assertFalse(cli.npm_init('foo', interactive=True))

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Does not overwrite by default.
        self.assertEqual(result, {
            'dependencies': {},
            'devDependencies': {},
        })

    def test_npm_init_existing_overwrite(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'jquery': '~3.0.0',
                'underscore': '~1.8.0',
            }, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        # Should be a concrete option overriding interactive
        self.assertTrue(cli.npm_init('foo', overwrite=True))

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

    def test_npm_init_existing_merge(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'jquery': '~3.0.0',
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0'
            }, 'name': 'dummy'}, fd, indent=0)

        os.chdir(tmpdir)
        # Should be a concrete option overriding interactive
        self.assertTrue(cli.npm_init('foo', merge=True))

        with open(join(tmpdir, 'package.json')) as fd:
            with self.assertRaises(ValueError):
                json.loads(fd.readline())
            fd.seek(0)
            result = json.load(fd)

        # Merge results shouldn't have written
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'dummy',
        })

    def test_npm_init_no_overwrite_if_semantically_identical(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0'
            }, 'name': 'dummy'}, fd, indent=None)

        os.chdir(tmpdir)
        self.assertTrue(cli.npm_init('foo', merge=True))

        with open(join(tmpdir, 'package.json')) as fd:
            # Notes that we initial wrote a file within a line with
            # explicitly no indent, so this should parse everything to
            # show that the indented serializer did not trigger.
            result = json.loads(fd.readline())

        # Merge results shouldn't have written
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'dummy',
        })

    def test_npm_init_existing_broken_no_overwrite_non_interactive(self):
        cli._inst.interactive = False

        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        self.assertFalse(cli.npm_init('foo'))
        with open(join(tmpdir, 'package.json')) as fd:
            self.assertEqual('{', fd.read())

    def test_npm_init_existing_broken_yes_overwrite(self):
        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        self.assertTrue(cli.npm_init('foo', overwrite=True))

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

    def test_npm_init_existing_not_readable_as_file(self):
        tmpdir = mkdtemp(self)
        # Nobody expects a package.json as a directory
        os.mkdir(join(tmpdir, 'package.json'))
        os.chdir(tmpdir)
        with self.assertRaises(IOError):
            cli.npm_init('foo')
