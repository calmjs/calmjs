# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import json
import os
import sys
from os.path import join
from os.path import exists

from distutils.errors import DistutilsOptionError
from setuptools.dist import Distribution
from pkg_resources import WorkingSet

from calmjs import npm
from calmjs import cli

from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_dist_flatten_package_json
from calmjs.testing.utils import stub_stdin
from calmjs.testing.utils import stub_stdouts
from calmjs.testing.utils import stub_mod_check_interactive


class NpmTestCase(unittest.TestCase):

    def setUp(self):
        # keep copy of original os.environ
        self.original_env = {}
        self.original_env.update(os.environ)
        # working directory
        self.cwd = os.getcwd()
        # Forcibly enable interactive mode.
        self.inst_interactive, npm._inst.interactive = (
            npm._inst.interactive, True)

    def tearDown(self):
        npm._inst.interactive = self.inst_interactive
        # restore original os.environ from copy
        os.environ.clear()
        os.environ.update(self.original_env)
        os.chdir(self.cwd)

    def test_npm_no_path(self):
        # XXX should be in npm
        os.environ['PATH'] = ''
        self.assertIsNone(npm.get_npm_version())

    @unittest.skipIf(npm.get_npm_version() is None, 'npm not found.')
    def test_npm_version_get(self):
        version = npm.get_npm_version()
        self.assertIsNotNone(version)

    def test_npm_install_package_json(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # This is faked.
        npm.npm_install()
        # However we make sure that it's been fake called
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))
        self.assertFalse(exists(join(tmpdir, 'package.json')))

    def test_npm_install_package_json_no_overwrite_interactive(self):
        """
        Most of these package_json testing will be done in the next test
        class specific for ``npm init``.
        """

        # Testing the implied init call
        stub_mod_call(self, cli)
        stub_stdouts(self)
        stub_stdin(self, 'n\n')
        stub_mod_check_interactive(self, [cli], True)
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
        npm.npm_install('foo')

        self.assertIn(
            "Overwrite 'package.json' in current working directory? "
            "(Yes/No) [No] ",
            sys.stdout.getvalue())
        # No log level set, otherwise it will complain that npm install
        # cannot be continued
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
        self.cwd = os.getcwd()

        # All the pre-made setup.
        stub_mod_call(self, cli)
        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')
        named = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~3.0.0'},
                'name': 'named-js',
            })),
        ), 'named', '2.0.0')
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
        working_set.add(named, self._calmjs_testing_tmpdir)
        stub_dist_flatten_package_json(self, [cli], working_set)
        stub_mod_check_interactive(self, [cli], True)
        # also save this
        self.inst_interactive = npm._inst.interactive

    def tearDown(self):
        # so it can be restored.
        npm._inst.interactive = self.inst_interactive
        # restore original os.environ from copy
        os.chdir(self.cwd)

    def test_npm_init_new_non_interactive(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        self.assertTrue(npm.npm_init('foo', interactive=False))
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
        self.assertFalse(npm.npm_init('foo', interactive=False))

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

        # force autodetected interactivity to be True
        npm._inst.interactive = True
        self.assertFalse(npm.npm_init('foo', interactive=True))

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
            # name already in file, but not part of the defined
            # package.json.
            'name': 'dummy',
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
        self.assertTrue(npm.npm_init(
            'foo', merge=True, overwrite=True, interactive=True))

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
            'name': 'dummy',
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
        self.assertFalse(npm.npm_init('foo', merge=True, interactive=True))

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
        npm._inst.interactive = False

        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        self.assertFalse(npm.npm_init('foo'))
        with open(join(tmpdir, 'package.json')) as fd:
            self.assertEqual('{', fd.read())

    def test_npm_init_existing_broken_yes_overwrite(self):
        tmpdir = mkdtemp(self)
        # Broken json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('{')
        os.chdir(tmpdir)
        self.assertTrue(npm.npm_init('foo', overwrite=True))

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
        with self.assertRaises(IOError):
            npm.npm_init('foo')


class DistCommandTestCase(unittest.TestCase):
    """
    Test case for the commands within.
    """

    def setUp(self):
        self.cwd = os.getcwd()

        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')

        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)

        # Stub out the flatten_package_json calls with one that uses our
        # custom working_set here.
        stub_dist_flatten_package_json(self, [cli], working_set)
        # Quiet stdout from distutils logs
        stub_stdouts(self)
        # Force auto-detected interactive mode to True, because this is
        # typically executed within an interactive context.
        stub_mod_check_interactive(self, [cli], True)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_no_args(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm'],
            name='foo',
        ))
        dist.parse_command_line()
        with self.assertRaises(DistutilsOptionError):
            dist.run_commands()

    def test_interactive_only(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '-i'],
            name='foo',
        ))
        dist.parse_command_line()
        with self.assertRaises(DistutilsOptionError):
            dist.run_commands()

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

        self.assertIn(
            "generating a flattened 'package.json' for 'foo' "
            "into current working directory (%s)\n"
            "Generated 'package.json' differs from one in current working "
            "directory" % (tmpdir),
            stdout
        )

        # That the diff additional block is inside
        self.assertIn(
            '+     "dependencies": {\n'
            '+         "jquery": "~1.11.0"\n'
            '+     },',
            stdout,
        )

        self.assertIn(
            "'package.json' exists in current working directory; "
            "not overwriting\n",
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

    def test_install_no_init(self):
        stub_mod_call(self, cli)
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
        })
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))

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

    def test_install_false(self):
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
