# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import json
import os
import sys
from logging import getLogger
from logging import DEBUG
from os import makedirs
from os.path import join
from os.path import exists

from setuptools.dist import Distribution
from pkg_resources import WorkingSet

from calmjs import npm
from calmjs import cli
from calmjs import dist
from calmjs.ui import prompt_overwrite_json
from calmjs.utils import pretty_logging
from calmjs.utils import which

from calmjs.testing.mocks import StringIO
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import stub_item_attr_value
from calmjs.testing.utils import stub_base_which
from calmjs.testing.utils import stub_check_interactive
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_os_environ
from calmjs.testing.utils import stub_stdin
from calmjs.testing.utils import stub_stdouts

which_npm = which('npm')


class LocatePackageTestCase(unittest.TestCase):

    def test_locate_package_entry_module_not_found(self):
        working_dir = mkdtemp(self)
        pkg_name = 'demo'
        with pretty_logging(stream=StringIO()) as stream:
            self.assertIsNone(
                npm.locate_package_entry_file(working_dir, pkg_name))

        self.assertIn(
            "could not locate package.json for the npm package 'demo' "
            "in the current working directory '%s'" % working_dir,
            stream.getvalue(),
        )

    def test_plugin_package_missing_required_entries(self):
        working_dir = mkdtemp(self)
        pkg_name = 'demo'
        pkg_dir = join(working_dir, 'node_modules', pkg_name)
        makedirs(pkg_dir)

        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{}')

        with pretty_logging(stream=StringIO(), level=DEBUG) as stream:
            self.assertIsNone(
                npm.locate_package_entry_file(working_dir, pkg_name))

        self.assertIn(
            "package.json for the npm package 'demo' does not "
            "contain a main entry point", stream.getvalue(),
        )

    def test_plugin_package_with_main(self):
        working_dir = mkdtemp(self)
        pkg_name = 'demo'
        pkg_dir = join(working_dir, 'node_modules', pkg_name)
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"main": "base.js"}')

        with pretty_logging(stream=StringIO(), level=DEBUG) as stream:
            self.assertEqual(
                join(pkg_dir, 'base.js'),
                npm.locate_package_entry_file(working_dir, pkg_name))

        self.assertEqual("", stream.getvalue())

    def test_plugin_package_success_browser(self):
        working_dir = mkdtemp(self)
        pkg_name = 'demo'
        pkg_dir = join(working_dir, 'node_modules', pkg_name)
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"browser": "browser/index.js"}')

        with pretty_logging(stream=StringIO(), level=DEBUG) as stream:
            self.assertEqual(
                join(pkg_dir, 'browser', 'index.js'),
                npm.locate_package_entry_file(working_dir, pkg_name),
            )
        self.assertEqual("", stream.getvalue())

    def test_plugin_package_success_implied_index_js(self):
        working_dir = mkdtemp(self)
        pkg_name = 'demo'
        pkg_dir = join(working_dir, 'node_modules', pkg_name)
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{}')

        with open(join(pkg_dir, 'index.js'), 'w') as fd:
            fd.write('(function () { return {} })();')

        with pretty_logging(stream=StringIO(), level=DEBUG) as stream:
            self.assertEqual(
                join(pkg_dir, 'index.js'),
                npm.locate_package_entry_file(working_dir, pkg_name),
            )
        self.assertEqual("", stream.getvalue())


class NpmTestCase(unittest.TestCase):

    def setUp(self):
        remember_cwd(self)
        stub_os_environ(self)
        stub_check_interactive(self, True)

    def test_npm_no_path(self):
        os.environ['PATH'] = ''
        with pretty_logging(stream=StringIO()) as stderr:
            self.assertIsNone(npm.get_npm_version())
            self.assertIn("failed to execute 'npm'", stderr.getvalue())

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_npm_version_get(self):
        version = npm.get_npm_version()
        self.assertTrue(isinstance(version, tuple))
        self.assertGreater(len(version), 0)

    # For a number of the following tests, the which function in the
    # calmjs.base module will be stubbed out to return the initial
    # response we got above with the real function, to better mimic the
    # expected output.

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_npm_install_package_json(self):
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # This is faked.
        with pretty_logging(stream=StringIO()) as stderr:
            npm.npm_install()
            self.assertIn(
                "no package name supplied, "
                "not continuing with 'npm install'", stderr.getvalue())
        # However we make sure that it's been fake called
        self.assertIsNone(self.call_args)
        self.assertFalse(exists(join(tmpdir, 'package.json')))

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_npm_install_package_json_no_overwrite_interactive(self):
        """
        Most of these package_json testing will be done in the next test
        class specific for ``npm init``.
        """

        # Testing the implied init call
        stub_mod_call(self, cli)
        stub_stdouts(self)
        stub_stdin(self, 'n\n')
        stub_check_interactive(self, True)
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
        stub_item_attr_value(self, dist, 'default_working_set', working_set)

        # We are going to have a fake package.json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({}, fd)

        # capture the logging explicitly as the conditions which
        # determines how the errors are outputted differs from different
        # test harnesses.  Verify that later.
        with pretty_logging(stream=StringIO()) as stderr:
            # This is faked.
            npm.npm_install('foo', callback=prompt_overwrite_json)

        self.assertIn(
            "Overwrite '%s'? (Yes/No) [No] " % join(tmpdir, 'package.json'),
            sys.stdout.getvalue())
        # Ensure the error message.  Normally this is printed through
        # stderr via distutils custom logger and our handler bridge for
        # that which is tested elsewhere.
        self.assertIn("not continuing with 'npm install'", stderr.getvalue())

        with open(join(tmpdir, 'package.json')) as fd:
            result = fd.read()
        # This should remain unchanged as no to overwrite is default.
        self.assertEqual(result, '{}')

    @unittest.skipIf(which_npm is None, 'npm not found.')
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
        stub_item_attr_value(self, dist, 'default_working_set', working_set)

        # We are going to have a fake package.json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({}, fd)

        # This is faked.
        npm.npm_install('foo', overwrite=True)

        with open(join(tmpdir, 'package.json')) as fd:
            config = json.load(fd)

        # Overwritten
        self.assertEqual(config, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })

        # No log level set.
        self.assertEqual(sys.stdout.getvalue(), '')
        self.assertEqual(sys.stderr.getvalue(), '')


class NpmDriverInitTestCase(unittest.TestCase):
    """
    Test driver init workflow separately, due to complexities involved.
    """

    def setUp(self):
        # save working directory
        remember_cwd(self)

        # All the pre-made setup.
        stub_mod_call(self, cli)
        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')
        underscore = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'underscore': '~1.8.0'},
            })),
        ), 'underscore', '1.8.0')
        named = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~3.0.0'},
                'name': 'named-js',
            })),
        ), 'named', '2.0.0')
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
        working_set.add(underscore, self._calmjs_testing_tmpdir)
        working_set.add(named, self._calmjs_testing_tmpdir)
        stub_item_attr_value(self, dist, 'default_working_set', working_set)
        stub_check_interactive(self, True)

    def test_npm_init_new_non_interactive(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        self.assertTrue(npm.npm_init('foo'))
        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })

    def test_npm_init_new_multiple(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        self.assertTrue(
            npm.npm_init(['named', 'underscore']))
        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~3.0.0', 'underscore': '~1.8.0'},
            'devDependencies': {},
            'name': 'underscore',
        })

    def test_npm_init_with_invalid_valid_mix(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        self.assertTrue(
            npm.npm_init(['invalid', 'underscore']))
        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'underscore': '~1.8.0'},
            'devDependencies': {},
            'name': 'underscore',
        })

    def test_npm_init_existing_standard_non_interactive(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        target = join(tmpdir, 'package.json')
        with open(target, 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)

        with pretty_logging(stream=StringIO()) as stderr:
            self.assertFalse(npm.npm_init('foo'))
            self.assertIn(
                "not overwriting existing '%s'" % target, stderr.getvalue())

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

        self.assertFalse(npm.npm_init('foo', callback=prompt_overwrite_json))

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
        self.assertTrue(npm.npm_init('foo', overwrite=True))

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # name wasn't already specified, so it will be automatically
        # added
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })

    def test_npm_init_existing_merge_interactive_yes(self):
        stub_stdouts(self)
        stub_stdin(self, 'Y')
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
        self.assertTrue(npm.npm_init('foo', merge=True))

        with open(join(tmpdir, 'package.json')) as fd:
            with self.assertRaises(ValueError):
                json.loads(fd.readline())
            fd.seek(0)
            result = json.load(fd)

        # Merge results should be written when user agrees.
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'foo',
        })

    def test_npm_init_existing_merge_overwrite(self):
        stub_stdouts(self)
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
        # Overwrite will supercede interactive.
        # stub regardless, when interactive prompt failed to not trigger
        stub_stdin(self, 'n')
        self.assertTrue(npm.npm_init(
            'foo', merge=True, overwrite=True, callback=prompt_overwrite_json))

        with open(join(tmpdir, 'package.json')) as fd:
            with self.assertRaises(ValueError):
                json.loads(fd.readline())
            fd.seek(0)
            result = json.load(fd)

        # Merge results should be written when user agrees.
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'foo',
        })

    def test_npm_init_existing_interactive_merge_no(self):
        stub_stdouts(self)
        stub_stdin(self, 'N')
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
        self.assertFalse(npm.npm_init(
            'foo', merge=True, callback=prompt_overwrite_json))

        with open(join(tmpdir, 'package.json')) as fd:
            with self.assertRaises(ValueError):
                json.loads(fd.readline())
            fd.seek(0)
            result = json.load(fd)

        # Should not have written anything if user said no.
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~3.0.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            'name': 'dummy',
        })

    def test_npm_init_write_name_merge(self):
        stub_stdouts(self)
        stub_stdin(self, 'Y')
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'jquery': '~1.8.9',
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0'
            }, 'name': 'something_else'}, fd, indent=0)

        os.chdir(tmpdir)
        self.assertTrue(npm.npm_init('named', merge=True))

        with open(join(tmpdir, 'package.json')) as fd:
            with self.assertRaises(ValueError):
                json.loads(fd.readline())
            fd.seek(0)
            result = json.load(fd)

        # Merge results should be written when user agrees.
        self.assertEqual(result, {
            'dependencies': {
                'jquery': '~3.0.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0'
            },
            # name derived from the package_json field.
            'name': 'named-js',
        })

    def test_npm_init_merge_no_overwrite_if_semantically_identical(self):
        tmpdir = mkdtemp(self)

        # Write an initial thing
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'jquery': '~1.11.0',
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0'
            }, 'name': 'foo'}, fd, indent=None)

        os.chdir(tmpdir)
        self.assertTrue(npm.npm_init('foo', merge=True))

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
            'name': 'foo',
        })

    def test_npm_init_existing_broken_no_overwrite_non_interactive(self):
        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        with pretty_logging(stream=StringIO()) as stderr:
            self.assertFalse(npm.npm_init('foo'))
        self.assertIn("ignoring existing malformed", stderr.getvalue())

        with open(join(tmpdir, 'package.json')) as fd:
            self.assertEqual('{', fd.read())

    def test_npm_init_existing_broken_yes_overwrite(self):
        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        with pretty_logging(stream=StringIO()) as stderr:
            self.assertTrue(npm.npm_init('foo', overwrite=True))
        self.assertIn("ignoring existing malformed", stderr.getvalue())

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })

    def test_npm_init_existing_not_readable_as_file(self):
        tmpdir = mkdtemp(self)
        # Nobody expects a package.json as a directory
        os.mkdir(join(tmpdir, 'package.json'))
        os.chdir(tmpdir)
        with pretty_logging(stream=StringIO()) as stderr:
            with self.assertRaises(IOError):
                npm.npm_init('foo')
        self.assertIn(
            "package.json' failed; please confirm that it is a file",
            stderr.getvalue(),
        )


class DistCommandTestCase(unittest.TestCase):
    """
    Test case for the commands within.
    """

    def setUp(self):
        remember_cwd(self)

        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')

        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)

        # Stub out the flatten_egginfo_json calls with one that uses our
        # custom working_set here.
        stub_item_attr_value(self, dist, 'default_working_set', working_set)
        # Quiet stdout from distutils logs
        stub_stdouts(self)
        # Force auto-detected interactive mode to True, because this is
        # typically executed within an interactive context.
        stub_check_interactive(self, True)

    def test_no_args(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()
        self.assertIn('\n        "jquery": "~1.11.0"', sys.stdout.getvalue())

    def test_interactive_only(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '-i'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()
        self.assertIn('\n        "jquery": "~1.11.0"', sys.stdout.getvalue())

    def test_view(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--view'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        self.assertFalse(exists(join(tmpdir, 'package.json')))
        # also log handlers removed.
        self.assertEqual(len(getLogger('calmjs.cli').handlers), 0)
        # written to stdout with the correct indentation level.
        self.assertIn('\n        "jquery": "~1.11.0"', sys.stdout.getvalue())

    def test_init_no_overwrite_default_input_interactive(self):
        tmpdir = mkdtemp(self)
        stub_stdin(self, u'')  # default should be no

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump(
                {'dependencies': {}, 'devDependencies': {}}, fd, indent=None)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--interactive'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            # Should not have overwritten
            result = json.loads(fd.readline())

        self.assertEqual(result, {
            'dependencies': {},
            'devDependencies': {},
        })

        stdout = sys.stdout.getvalue()
        self.assertTrue(stdout.startswith("running npm\n"))

        target = join(tmpdir, 'package.json')

        self.assertIn(
            "generating a flattened 'package.json' for 'foo'\n"
            "Generated 'package.json' differs with '%s'" % (target),
            stdout,
        )

        # That the diff additional block is inside
        self.assertIn(
            '+     "dependencies": {\n'
            '+         "jquery": "~1.11.0"\n'
            '+     },',
            stdout,
        )

        self.assertIn(
            "not overwriting existing '%s'\n" % target,
            sys.stderr.getvalue(),
        )

    def test_init_overwrite(self):
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--overwrite'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten anyway.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })

        stdout = sys.stdout.getvalue()
        self.assertIn("wrote '%s'\n" % join(tmpdir, 'package.json'), stdout)

    def test_init_merge(self):
        # --merge without --interactive implies overwrite
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0',
            }}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--merge'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten as we explicitly asked
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0', 'underscore': '~1.8.0'},
            'devDependencies': {'sinon': '~1.17.0'},
            'name': 'foo',
        })

    def test_init_merge_interactive_default(self):
        tmpdir = mkdtemp(self)
        stub_stdin(self, u'')

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0',
            }}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--merge', '--interactive'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        stdout = sys.stdout.getvalue()
        self.assertIn('+         "jquery": "~1.11.0",', stdout)

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Nothing happened.
        self.assertEqual(result, {
            'dependencies': {'underscore': '~1.8.0'},
            'devDependencies': {'sinon': '~1.17.0'},
        })

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_install_no_init_nodevnoprod(self):
        # install implies init
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # The cli will still automatically write to that, as install
        # implies init.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })
        self.assertEqual(self.call_args[0], ([which_npm, 'install'],))

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_install_init_install_production(self):
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--install', '--production'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })
        # Should still invoke install
        self.assertEqual(self.call_args[0], (
            [which_npm, 'install', '--production=true'],))

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_install_init_install_develop(self):
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--install', '--development'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })
        # Should still invoke install
        self.assertEqual(self.call_args[0], (
            [which_npm, 'install', '--production=false'],))

    def test_install_no_init_has_package_json_interactive_default_input(self):
        stub_stdin(self, u'')
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({
                'dependencies': {'jquery': '~3.0.0'},
                'devDependencies': {}
            }, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install', '--interactive'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Existing package.json will not be overwritten.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~3.0.0'},
            'devDependencies': {},
        })
        # Ensure that install is NOT called.
        self.assertIsNone(self.call_args)

    def test_install_dryrun(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install', '--dry-run'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        self.assertFalse(exists(join(tmpdir, 'package.json')))
        # Ensure that install is NOT called.
        self.assertIsNone(self.call_args)
        # also log handlers removed.
        self.assertEqual(len(getLogger('calmjs.cli').handlers), 0)
        # However, default action is view, the package.json should be
        # written to stdout with the correct indentation level.
        self.assertIn('\n        "jquery": "~1.11.0"', sys.stdout.getvalue())

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_install_view(self):
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install', '--view'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
            'name': 'foo',
        })
        self.assertEqual(self.call_args[0], ([which_npm, 'install'],))

    @unittest.skipIf(which_npm is None, 'npm not found.')
    def test_npm_bin_get(self):
        # also test that the cli_driver can actually run...
        bin_dir, stderr = npm.npm.cli_driver.run(['bin'])
        self.assertIn('bin', bin_dir)


class StandaloneMainTestCase(unittest.TestCase):

    def test_standalone_main(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            npm.npm.runtime(['-h'])
        # Have the help work
        self.assertIn('npm support for the calmjs', sys.stdout.getvalue())

    def test_standalone_main_version(self):
        stub_stdouts(self)
        # the default call method does NOT call sys.exit.
        with self.assertRaises(SystemExit):
            npm.npm.runtime(['-V'])
        self.assertIn('calmjs', sys.stdout.getvalue())
        self.assertIn('from', sys.stdout.getvalue())

    def test_standalone_reuse_main(self):
        stub_stdouts(self)
        # the default call method does NOT call sys.exit.
        npm.npm.runtime(['calmjs', '-vv'])
        # Have the help work
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies'], {})
        err = sys.stderr.getvalue()
        self.assertIn('DEBUG', err)
