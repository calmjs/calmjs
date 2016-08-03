# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import json
import os
import sys
from os.path import join
from os.path import exists

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
        working_set = WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)
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

        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
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

    def test_npm_init_merge_no_overwrite_if_semantically_identical(self):
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
            'name': 'dummy',
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
        })

    def test_npm_init_existing_not_readable_as_file(self):
        tmpdir = mkdtemp(self)
        # Nobody expects a package.json as a directory
        os.mkdir(join(tmpdir, 'package.json'))
        os.chdir(tmpdir)
        with self.assertRaises(IOError):
            npm.npm_init('foo')
