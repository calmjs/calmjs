# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import json
import os
import sys
from os.path import exists
from os.path import join
from os.path import normcase
from os.path import pathsep
import pkg_resources
import warnings

from calmjs import cli
from calmjs import dist
from calmjs.utils import pretty_logging
from calmjs.utils import finalize_env
from calmjs.utils import which
from calmjs.testing import mocks
from calmjs.testing.mocks import MockProvider
from calmjs.testing.utils import create_fake_bin
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import stub_check_interactive
from calmjs.testing.utils import stub_item_attr_value
from calmjs.testing.utils import stub_base_which
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_mod_check_output
from calmjs.testing.utils import stub_os_environ

which_node = which('node')
isatty = sys.stdin.isatty()


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


class CliDriverTestCase(unittest.TestCase):
    """
    Base cli driver class test case.
    """

    def setUp(self):
        self.cwd = mkdtemp(self)
        remember_cwd(self)
        os.chdir(self.cwd)

    def test_get_bin_version_long(self):
        stub_mod_check_output(self, cli)
        stub_base_which(self)
        self.check_output_answer = b'Some app v.1.2.3.4. All rights reserved'
        results = cli.get_bin_version('some_app')
        self.assertEqual(results, (1, 2, 3, 4))

    def test_get_bin_version_longer(self):
        stub_mod_check_output(self, cli)
        stub_base_which(self)
        # tags are ignored for now.
        self.check_output_answer = b'version.11.200.345.4928-what'
        results = cli.get_bin_version('some_app')
        self.assertEqual(results, (11, 200, 345, 4928))

    def test_get_bin_version_short(self):
        stub_mod_check_output(self, cli)
        stub_base_which(self)
        self.check_output_answer = b'1'
        results = cli.get_bin_version('some_app')
        self.assertEqual(results, (1,))

    def test_get_bin_version_unexpected(self):
        stub_mod_check_output(self, cli)
        stub_base_which(self)
        self.check_output_answer = b'Nothing'
        with pretty_logging(stream=mocks.StringIO()) as err:
            results = cli.get_bin_version('some_app')
        self.assertIn(
            "encountered unexpected error while trying to find version of "
            "'some_app'", err.getvalue())
        self.assertIsNone(results)

    def test_get_bin_version_no_bin(self):
        stub_mod_check_output(self, cli, fake_error(OSError))
        stub_base_which(self)
        with pretty_logging(stream=mocks.StringIO()) as err:
            results = cli.get_bin_version('some_app')
        self.assertIn("failed to execute 'some_app'", err.getvalue())
        self.assertIsNone(results)

    def test_node_no_path(self):
        stub_os_environ(self)
        os.environ['PATH'] = ''
        with pretty_logging(stream=mocks.StringIO()) as err:
            self.assertIsNone(cli.get_node_version())
        self.assertIn("failed to execute 'node'", err.getvalue())

    def test_node_version_mocked(self):
        stub_mod_check_output(self, cli)
        stub_base_which(self)
        self.check_output_answer = b'v0.10.25'
        version = cli.get_node_version()
        self.assertEqual(version, (0, 10, 25))

    # live test, no stubbing
    @unittest.skipIf(which_node is None, 'Node.js not found.')
    def test_node_version_get(self):
        version = cli.get_node_version()
        self.assertIsNotNone(version)

    def test_node_run_no_path(self):
        stub_os_environ(self)
        os.environ['PATH'] = ''
        with self.assertRaises(OSError):
            cli.node('process.stdout.write("Hello World!");')

    # live test, no stubbing
    # some of these may take a long time on Windows for some reason.
    @unittest.skipIf(which_node is None, 'Node.js not found.')
    def test_node_run(self):
        stdout, stderr = cli.node('process.stdout.write("Hello World!");')
        self.assertEqual(stdout, 'Hello World!')
        stdout, stderr = cli.node('window')
        self.assertIn('window is not defined', stderr)

    # live test, no stubbing
    @unittest.skipIf(cli.get_node_version() is None, 'Node.js not found.')
    def test_node_run_bytes(self):
        stdout, stderr = cli.node(b'process.stdout.write("Hello World!");')
        self.assertEqual(stdout, b'Hello World!')

    # Note that for the following tests with the mock 'mgr' binary, both
    # call calmjs.cli and calmjs.base.which are stubbed.  This is due to
    # how the _exec method uses the which function to locate the binary,
    # and as mgr is not there it will fail.  The alternative is to keep
    # creating a dummy binary, but the tests for those are already done
    # so we can skip that for with mocks for the following tests.

    def test_helper_attr(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with self.assertRaises(AttributeError) as e:
            driver.no_such_attr_here
        self.assertIn('no_such_attr_here', str(e.exception))
        self.assertIsNot(driver.mgr_init, None)
        self.assertIsNot(driver.get_mgr_version, None)
        self.assertTrue(driver.mgr_install(['calmjs']))
        self.assertEqual(self.call_args[0], (['mgr', 'install'],))

    def test_install_failure(self):
        stub_mod_call(self, cli, fake_error(IOError))
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with pretty_logging(stream=mocks.StringIO()) as stderr:
            with self.assertRaises(IOError):
                driver.mgr_install(['calmjs'])
        val = stderr.getvalue()
        self.assertIn("invocation of the 'mgr' binary failed", val)

    def test_install_arguments(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'], args=('--pedantic',))
        self.assertEqual(
            self.call_args[0], (['mgr', 'install', '--pedantic'],))

    def test_alternative_install_cmd(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', install_cmd='sync')
        driver.pkg_manager_install(['calmjs'])
        self.assertEqual(self.call_args[0], (['mgr', 'sync'],))

        # Naturally, the short hand call will be changed.
        # note that args is NOT the package_name, and thus this just
        # means that the installation may not operate as expected off
        # the package.
        driver.mgr_sync(['calmjs'], args=('all',))
        self.assertEqual(self.call_args[0], (['mgr', 'sync', 'all'],))

    def test_install_other_environ(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        stub_os_environ(self)
        # pop out NODE_PATH if available
        os.environ.pop('NODE_PATH', '')
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'], env={
                'MGR_ENV': 'production'})
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': finalize_env({'MGR_ENV': 'production'}),
        }))

    def test_set_node_path(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        node_path = mkdtemp(self)
        driver = cli.PackageManagerDriver(
            node_path=node_path, pkg_manager_bin='mgr')

        # ensure env is passed into the call.
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'])
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': finalize_env({'NODE_PATH': node_path}),
        }))

        # will be overridden by instance settings.
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'], env={
                'PATH': '.',
                'MGR_ENV': 'dev',
                'NODE_PATH': '/tmp/somewhere/else/node_mods',
            })
        self.assertEqual(self.call_args, ((['mgr', 'install'],), {
            'env': finalize_env(
                {'NODE_PATH': node_path, 'MGR_ENV': 'dev', 'PATH': '.'}),
        }))

    def test_predefined_path(self):
        # ensure that the various paths are passed to env or cwd.
        stub_mod_call(self, cli)
        stub_base_which(self)
        somepath = mkdtemp(self)
        cwd = self.cwd
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', env_path=somepath, working_dir=cwd)
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'])
        args, kwargs = self.call_args
        self.assertEqual(kwargs['env']['PATH'].split(pathsep)[0], somepath)
        self.assertEqual(kwargs['cwd'], cwd)

    def test_env_path_not_exist(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        bad_path = '/no/such/path/for/sure/at/here'
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', env_path=bad_path)
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'])
        args, kwargs = self.call_args
        self.assertNotEqual(kwargs['env']['PATH'].split(pathsep)[0], bad_path)

    def test_paths_unset(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'])
        args, kwargs = self.call_args
        self.assertNotIn('PATH', kwargs)
        self.assertNotIn('cwd', kwargs)

    def test_working_dir_set(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        some_cwd = self.cwd
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', working_dir=some_cwd)
        with pretty_logging(stream=mocks.StringIO()):
            driver.pkg_manager_install(['calmjs'])
        args, kwargs = self.call_args
        self.assertNotIn('PATH', kwargs)
        self.assertEqual(kwargs['cwd'], some_cwd)

    def test_set_binary_no_package(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='bower')
        with pretty_logging(stream=mocks.StringIO()) as fd:
            driver.pkg_manager_install()
            self.assertIn(
                "no package name supplied, "
                "not continuing with 'bower install'", fd.getvalue())
        self.assertIsNone(self.call_args)

    def test_set_binary_with_package(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='bower')
        # this will call ``bower install`` instead.
        driver.pkg_manager_install(['calmjs'])
        self.assertEqual(self.call_args[0], (['bower', 'install'],))

    def test_which_is_none(self):
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        self.assertIsNone(driver.which())
        driver.env_path = mkdtemp(self)
        self.assertIsNone(driver.which())

    def create_fake_mgr_bin(self, root):
        return create_fake_bin(root, 'mgr')

    def test_which_is_set(self):
        stub_os_environ(self)
        tmpdir = mkdtemp(self)
        mgr_bin = self.create_fake_mgr_bin(tmpdir)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        driver.env_path = tmpdir
        self.assertEqual(normcase(driver.which()), normcase(mgr_bin))

        driver.env_path = None
        self.assertIsNone(driver.which())

    def test_which_is_set_env_path(self):
        stub_os_environ(self)
        tmpdir = mkdtemp(self)
        mgr_bin = self.create_fake_mgr_bin(tmpdir)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        # With both env_path attr and environ PATH set
        os.environ['PATH'] = driver.env_path = tmpdir
        self.assertEqual(normcase(driver.which()), normcase(mgr_bin))

        # the autodetection should still work through ENV_PATH
        driver.env_path = None
        self.assertEqual(normcase(driver.which()), normcase(mgr_bin))

    def test_set_env_path_with_node_modules_fail(self):
        stub_os_environ(self)
        tmpdir = mkdtemp(self)
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', working_dir=tmpdir)
        self.assertFalse(driver._set_env_path_with_node_modules())
        self.assertIsNone(driver.env_path)
        self.assertIsNone(driver.which_with_node_modules())

    def fake_mgr_bin(self):
        tmpdir = mkdtemp(self)
        # fake an executable in node_modules
        bin_dir = join(tmpdir, 'node_modules', '.bin')
        os.makedirs(bin_dir)
        fake_bin = self.create_fake_mgr_bin(bin_dir)
        return tmpdir, bin_dir, fake_bin

    def test_set_env_path_with_node_modules_success(self):
        tmpdir, bin_dir, mgr_bin = self.fake_mgr_bin()
        # constructor with an explicit working directory.
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', working_dir=tmpdir)
        self.assertIsNone(driver.env_path)
        # the which_with_node_modules should work immediately
        self.assertEqual(
            normcase(driver.which_with_node_modules()), normcase(mgr_bin))
        self.assertTrue(driver._set_env_path_with_node_modules())
        self.assertEqual(driver.env_path, bin_dir)
        # should still result in the same thing.
        self.assertTrue(driver._set_env_path_with_node_modules())
        self.assertEqual(driver.env_path, bin_dir)

    def test_set_env_path_with_node_path_success(self):
        tmpdir, bin_dir, mgr_bin = self.fake_mgr_bin()
        other_dir = mkdtemp(self)
        # default constructor
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', working_dir=other_dir)
        # the which_with_node_modules will not work immeidately in this
        # case
        self.assertIsNone(driver.which_with_node_modules())
        self.assertIsNone(driver.env_path)
        # using NODE_PATH set to a valid node_modules
        driver.node_path = join(tmpdir, 'node_modules')
        # this should work now.
        self.assertEqual(
            normcase(driver.which_with_node_modules()), normcase(mgr_bin))
        self.assertTrue(driver._set_env_path_with_node_modules())
        self.assertEqual(driver.env_path, bin_dir)
        # should still result in the same thing.
        self.assertTrue(driver._set_env_path_with_node_modules())
        self.assertEqual(driver.env_path, bin_dir)

    def test_set_env_path_with_node_path_with_environ(self):
        stub_os_environ(self)
        tmpdir, bin_dir, mgr_bin = self.fake_mgr_bin()
        # define a NODE_PATH set to a valid node_modules
        os.environ['NODE_PATH'] = join(tmpdir, 'node_modules')
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        self.assertTrue(driver._set_env_path_with_node_modules())
        self.assertEqual(driver.env_path, bin_dir)

    def test_set_env_path_with_node_path_multiple_with_environ(self):
        tmp = mkdtemp(self)
        tmp1, bin_dir1, _ = self.fake_mgr_bin()
        tmp2, bin_dir2, _ = self.fake_mgr_bin()
        node_path = pathsep.join(
            join(d, 'node_modules') for d in (tmp, tmp1, tmp2))
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', node_path=node_path)
        self.assertTrue(driver._set_env_path_with_node_modules())
        # First one.  Whether the node modules loads correctly, that's
        # up to the nodejs circus.
        self.assertEqual(driver.env_path, bin_dir1)

        # ensure the kws generated correctly.
        env = driver._gen_call_kws()['env']
        self.assertEqual(env['NODE_PATH'], node_path)
        self.assertEqual(env['PATH'].split(pathsep)[0], bin_dir1)

    def test_driver_run_failure(self):
        # testing for success may actually end up being extremely
        # annoying, so we are going to avoid that and let the integrated
        # subclasses deal with it.
        stub_os_environ(self)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        os.environ['PATH'] = ''
        with self.assertRaises(OSError):
            driver.run()

    # Helpers for getting a module level default instance up

    def test_driver_create_failure(self):
        with self.assertRaises(TypeError):
            # can't create the parent one as it is not subclassed like
            # the following
            cli.PackageManagerDriver.create()

    def test_driver_create(self):
        class Driver(cli.PackageManagerDriver):
            def __init__(self, **kw):
                kw['pkg_manager_bin'] = 'mgr'
                super(Driver, self).__init__(**kw)

        inst = Driver.create()
        self.assertTrue(isinstance(inst, Driver))

    def test_create_for_module_vars_and_warning(self):
        stub_os_environ(self)
        tmpdir = mkdtemp(self)
        values = {}

        class MgrDriver(cli.PackageManagerDriver):
            def __init__(self, *a, **kw):
                kw['pkg_manager_bin'] = 'mgr'
                kw['working_dir'] = tmpdir
                super(MgrDriver, self).__init__(*a, **kw)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            driver = MgrDriver.create_for_module_vars(values)
            self.assertTrue(issubclass(w[-1].category, RuntimeWarning))
            self.assertIn(
                "Unable to locate the 'mgr' binary or runtime",
                str(w[-1].message))

        self.assertTrue(isinstance(driver, MgrDriver))
        # Normally, these will be global names.
        self.assertIn('mgr_install', values)
        self.assertIn('mgr_init', values)
        self.assertIn('get_mgr_version', values)

    # Should really put more tests of these kind in here, but the more
    # concrete implementations have done so.  This weird version here
    # is mostly just for laughs.

    def setup_requirements_json(self):
        # what kind of bizzaro world do the following users live in?
        requirements = {"require": {"setuptools": "25.1.6"}}
        mock_provider = MockProvider({
            'requirements.json': json.dumps(requirements),
        })
        # seriously lolwat?
        mock_dist = pkg_resources.Distribution(
            metadata=mock_provider, project_name='calmpy.pip', version='0.0.0')
        working_set = pkg_resources.WorkingSet()
        working_set.add(mock_dist)
        stub_item_attr_value(self, dist, 'default_working_set', working_set)
        return working_set

    def test_pkg_manager_view(self):
        self.setup_requirements_json()
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        result = driver.pkg_manager_view('calmpy.pip')
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })
        result2 = driver.mgr_view('calmpy.pip')
        self.assertEqual(result, result2)

    def test_pkg_manager_init(self):
        # we still need a temporary directory, but the difference is
        # that whether the instance contains it or not.
        self.setup_requirements_json()
        cwd = self.cwd

        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        driver.pkg_manager_init('calmpy.pip')

        target = join(cwd, 'requirements.json')
        self.assertTrue(exists(target))
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_working_dir(self):
        self.setup_requirements_json()
        original = mkdtemp(self)
        os.chdir(original)
        cwd = mkdtemp(self)
        target = join(cwd, 'requirements.json')

        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
            working_dir=cwd,
        )
        driver.pkg_manager_init('calmpy.pip')

        self.assertFalse(exists(join(original, 'requirements.json')))
        self.assertTrue(exists(target))

        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_exists_and_overwrite(self):
        self.setup_requirements_json()
        cwd = mkdtemp(self)
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
            working_dir=cwd,
        )
        target = join(cwd, 'requirements.json')
        with open(target, 'w') as fd:
            result = json.dump({"require": {}}, fd)

        with pretty_logging(stream=mocks.StringIO()) as err:
            driver.pkg_manager_init('calmpy.pip', overwrite=False)

        self.assertIn('not overwriting existing ', err.getvalue())
        self.assertIn('requirements.json', err.getvalue())
        with open(target) as fd:
            result = json.load(fd)
        self.assertNotEqual(result, {"require": {"setuptools": "25.1.6"}})

        stub_mod_call(self, cli)
        with pretty_logging(stream=mocks.StringIO()) as err:
            # ensure the return value is False
            self.assertFalse(
                driver.pkg_manager_install('calmpy.pip', overwrite=False))

        driver.pkg_manager_init('calmpy.pip', overwrite=True)
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_merge(self):
        self.setup_requirements_json()
        cwd = mkdtemp(self)
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
            working_dir=cwd,
        )
        target = join(cwd, 'requirements.json')
        with open(target, 'w') as fd:
            result = json.dump({"require": {"calmpy": "1.0.0"}}, fd)

        driver.pkg_manager_init('calmpy.pip', merge=True, overwrite=True)
        self.assertNotEqual(result, {
            "require": {
                "calmpy": "1.0.0",
                "setuptools": "25.1.6",
            },
            "name": "calmpy.pip",
        })

        stub_mod_call(self, cli)
        stub_base_which(self)
        with pretty_logging(stream=mocks.StringIO()):
            # ensure the return value is True, assuming successful
            self.assertTrue(
                driver.pkg_manager_install('calmpy.pip', overwrite=True))

    def test_pkg_manager_view_requires(self):
        working_set = self.setup_requirements_json()
        working_set.add(pkg_resources.Distribution(
            metadata=MockProvider({
                'requires.txt': 'calmpy.pip',
            }),
            project_name='site',
            version='0.0.0',
        ))
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        result = driver.pkg_manager_view('site')
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "site",
        })
        # try explicit
        result = driver.pkg_manager_view('site', explicit=True)
        self.assertEqual(result, {
            "require": {},
            "name": "site",
        })

    def test_pkg_manager_view_extras_requires(self):
        working_set = self.setup_requirements_json()
        working_set.add(pkg_resources.Distribution(
            metadata=MockProvider({
                'requires.txt': '[dev]\ncalmpy.pip',
            }),
            project_name='site',
            version='0.0.0',
        ))
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        result = driver.pkg_manager_view('site')
        self.assertEqual(result, {
            "require": {},
            "name": "site",
        })
        result = driver.pkg_manager_view('site[dev]')
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            # should be "site[dev]", but npm fails on that.
            "name": "site",
        })

    def test_pkg_manager_view_bad_entry_point(self):
        self.setup_requirements_json()
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        with self.assertRaises(ValueError) as e:
            driver.pkg_manager_view('calmpy.pip [dev]')
        self.assertIn(
            'malformed package name(s) specified: [dev]',
            str(e.exception))

        with self.assertRaises(ValueError) as e:
            driver.pkg_manager_view('{foo} /r')
        self.assertIn(
            'malformed package name(s) specified: {foo}, /r',
            str(e.exception))

    def test_pkg_manager_cmd_prodev_flag_basic(self):
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        with pretty_logging(stream=mocks.StringIO()) as log:
            # production has priority
            self.assertEqual(driver._prodev_flag(True, True, False), [
                '--production=true'])
            self.assertEqual(driver._prodev_flag(False, True, False), [
                '--production=false'])
            self.assertEqual(driver._prodev_flag(True, False, True), [
                '--production=true'])
            self.assertEqual(driver._prodev_flag(False, False, True), [
                '--production=false'])
        self.assertEqual(log.getvalue(), '')

        with pretty_logging(stream=mocks.StringIO()) as log:
            self.assertEqual(driver._prodev_flag(True, None, False), [
                '--production=true'])
            self.assertEqual(driver._prodev_flag(False, None, False), [
                '--production=false'])
            self.assertEqual(driver._prodev_flag(True, None, True), [
                '--production=true'])
            self.assertEqual(driver._prodev_flag(False, None, True), [
                '--production=false'])
        self.assertEqual(log.getvalue(), '')

        with pretty_logging(stream=mocks.StringIO()) as log:
            self.assertEqual(driver._prodev_flag(None, True, False), [
                '--production=false'])
            self.assertEqual(driver._prodev_flag(None, False, False), [
                '--production=true'])
            self.assertEqual(driver._prodev_flag(None, True, True), [
                '--production=false'])
            self.assertEqual(driver._prodev_flag(None, False, True), [
                '--production=true'])
        self.assertEqual(log.getvalue(), '')

        with pretty_logging(stream=mocks.StringIO()) as log:
            self.assertEqual(driver._prodev_flag(None, None, False), [])
        self.assertNotIn('WARNING', log.getvalue())
        self.assertIn('DEBUG', log.getvalue())
        self.assertIn(
            "no packages defined in 'devDependencies' section", log.getvalue())

    def test_pkg_manager_cmd_production_flag_warnings_interactive(self):
        stub_check_interactive(self, True)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr', devkey='blah')
        with pretty_logging(stream=mocks.StringIO()) as log:
            self.assertEqual(driver._prodev_flag(None, None, True), [])
        self.assertIn('WARNING', log.getvalue())
        self.assertIn(
            'undefined production flag may result in unexpected installation '
            'behavior', log.getvalue()
        )
        self.assertNotIn("non-interactive", log.getvalue())
        self.assertIn("'blah' may be installed", log.getvalue())

    def test_pkg_manager_cmd_production_flag_warnings_noninteractive(self):
        stub_check_interactive(self, False)
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr', devkey='blah')
        with pretty_logging(stream=mocks.StringIO()) as log:
            self.assertEqual(driver._prodev_flag(None, None, True), [])
        self.assertIn('WARNING', log.getvalue())
        self.assertIn(
            'undefined production flag may result in unexpected installation '
            'behavior', log.getvalue()
        )
        self.assertIn("non-interactive", log.getvalue())
        self.assertIn("'blah' may be ignored", log.getvalue())

    def test_pkg_manager_cmd_production_flag_unset(self):
        stub_check_interactive(self, False)
        stub_mod_call(self, cli)
        stub_base_which(self)
        self.setup_requirements_json()
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',), devkey='require',
        )

        with pretty_logging(stream=mocks.StringIO()) as log:
            driver.pkg_manager_install(['calmpy.pip'])

        self.assertIn('WARNING', log.getvalue())
        self.assertIn(
            'undefined production flag may result in unexpected installation '
            'behavior', log.getvalue()
        )
        self.assertIn("non-interactive", log.getvalue())
        self.assertIn("'require' may be ignored", log.getvalue())
        self.assertEqual(self.call_args[0], (['mgr', 'install'],))

    def test_pkg_manager_cmd_production_flag_set(self):
        stub_mod_call(self, cli)
        stub_base_which(self)
        self.setup_requirements_json()
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',), devkey='require',
        )

        with pretty_logging(stream=mocks.StringIO()) as log:
            driver.pkg_manager_install(['calmpy.pip'], production=True)
        self.assertNotIn('WARNING', log.getvalue())
        self.assertEqual(self.call_args[0], (
            ['mgr', 'install', '--production=true'],))

        with pretty_logging(stream=mocks.StringIO()) as log:
            driver.pkg_manager_install(['calmpy.pip'], production=False)
        self.assertNotIn('WARNING', log.getvalue())
        self.assertEqual(self.call_args[0], (
            ['mgr', 'install', '--production=false'],))
