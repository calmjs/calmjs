# -*- coding: utf-8 -*-
import unittest
import os
from os.path import join
from os.path import normcase
from os.path import pathsep

from pkg_resources import EntryPoint
from pkg_resources import Distribution
from pkg_resources import WorkingSet
from pkg_resources import safe_name

from calmjs import base
from calmjs.utils import pretty_logging
from calmjs.testing import mocks
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import create_fake_bin
from calmjs.testing.utils import make_dummy_dist


class DummyModuleRegistry(base.BaseModuleRegistry):

    def _map_entry_point_module(self, entry_point, module):
        return {module.__name__: {module.__name__: module}}


class PackageKeyMappingTestCase(unittest.TestCase):
    """
    The package key mapping test cases
    """

    def test_repr(self):
        mapping = base.PackageKeyMapping()
        self.assertEqual('{}', repr(mapping))
        mapping['a'] = 1
        self.assertEqual("{'a': 1}", repr(mapping))

    def test_len(self):
        mapping = base.PackageKeyMapping()
        self.assertEqual(0, len(mapping))
        mapping['foo'] = 1
        self.assertEqual(1, len(mapping))

    def test_delete(self):
        mapping = base.PackageKeyMapping(foo=1)
        del mapping['foo']
        self.assertEqual(0, len(mapping))

    def test_membership(self):
        mapping = base.PackageKeyMapping(foo=1)
        self.assertIn('foo', mapping)
        self.assertNotIn('bar', mapping)

    def test_get(self):
        mapping = base.PackageKeyMapping(foo=1)
        self.assertEqual(mapping['foo'], 1)
        self.assertEqual(mapping.get('foo'), 1)

    def test_iter(self):
        mapping = base.PackageKeyMapping({'foo': 1, 'bar': 2})
        values = {v for k, v in mapping.items()}
        self.assertEqual({1, 2}, values)

    def test_distribution_as_key(self):
        mapping = base.PackageKeyMapping()
        mapping[Distribution(project_name='not_normalized')] = 1
        self.assertEqual(1, mapping['not_normalized'])
        self.assertEqual(1, mapping[safe_name('not_normalized')])

    def test_membership_normalized(self):
        mapping = base.PackageKeyMapping(not_normalized=1)
        self.assertIn(safe_name('not_normalized'), mapping)
        self.assertIn('not_normalized', mapping)

    def test_pop_normalized(self):
        mapping = base.PackageKeyMapping(not_normalized=1)
        mapping.pop('not_normalized')
        self.assertEqual(0, len(mapping))


class BaseRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def test_empty(self):
        working_set = mocks.WorkingSet({__name__: []})
        registry = base.BaseRegistry(__name__, _working_set=working_set)
        self.assertEqual(registry.raw_entry_points, [])

    def test_entry_points(self):
        working_set = mocks.WorkingSet({__name__: [
            'module1 = calmjs.testing.module1',
            'module2 = calmjs.testing.module2',
            'module3 = calmjs.testing.module3',
        ]})

        registry = base.BaseRegistry(__name__, _working_set=working_set)
        self.assertEqual(len(registry.raw_entry_points), 3)

    def test_not_implemented(self):
        registry = base.BaseRegistry(__name__)

        with self.assertRaises(NotImplementedError):
            registry.get_record('something')

        with self.assertRaises(NotImplementedError):
            registry.iter_records()


class BasePkgRefRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def test_empty(self):
        working_set = mocks.WorkingSet({__name__: []})
        registry = base.BasePkgRefRegistry(__name__, _working_set=working_set)
        self.assertEqual(list(registry.iter_records()), [])

    def test_no_op_default(self):
        working_set = mocks.WorkingSet({'regname': [
            'calmjs.testing.module1 = calmjs.testing.module1',
        ]}, dist=Distribution(project_name='some.project', version='1.0'))
        with pretty_logging(stream=mocks.StringIO()) as s:
            base.BasePkgRefRegistry('regname', _working_set=working_set)
        self.assertIn(
            "registering 1 entry points for registry 'regname'", s.getvalue())
        self.assertIn(
            "registering entry point 'calmjs.testing.module1 = "
            "calmjs.testing.module1' from 'some.project 1.0'", s.getvalue())
        self.assertIn(
            "registration of entry point 'calmjs.testing.module1 = "
            "calmjs.testing.module1' from 'some.project 1.0' to registry "
            "'regname' failed",
            s.getvalue())
        self.assertIn('NotImplemented', s.getvalue())


class BaseModuleRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def setUp(self):
        self.original_working_set = base.working_set

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_bad_record(self):
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.not_a_module = calmjs.testing.not_a_module',
        ]})
        with pretty_logging(stream=mocks.StringIO()) as s:
            registry = base.BaseModuleRegistry(
                __name__, _working_set=working_set)
            self.assertIn(
                'ImportError: calmjs.testing.not_a_module not found; '
                'skipping registration', s.getvalue(),
            )
        self.assertEqual(len(registry.raw_entry_points), 1)
        self.assertEqual(registry.get_record('module'), {})
        self.assertEqual(list(registry.iter_records()), [])

    def test_no_op_default(self):
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing.module1',
        ]})
        with pretty_logging(stream=mocks.StringIO()) as s:
            base.BaseModuleRegistry(__name__, _working_set=working_set)
        self.assertIn('NotImplemented', s.getvalue())

    def test_dummy_implemented(self):
        from calmjs.testing import module1
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing.module1',
        ]})
        registry = DummyModuleRegistry(__name__, _working_set=working_set)
        result = registry.get_record('calmjs.testing.module1')
        self.assertEqual(result, {'calmjs.testing.module1': module1})
        self.assertEqual(list(registry.iter_records()), [
            ('calmjs.testing.module1', {'calmjs.testing.module1': module1}),
        ])

    def test_dummy_implemented_multiple_modules(self):
        from calmjs.testing import module1
        from calmjs.testing import module2
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing.module1',
            'calmjs.testing.module2 = calmjs.testing.module2',
        ]}, dist=Distribution(project_name='calmjs.testing'))
        registry = DummyModuleRegistry(__name__, _working_set=working_set)

        # it should be merged like so:
        result = registry.get_records_for_package('calmjs.testing')
        self.assertEqual(result, {
            'calmjs.testing.module1': module1,
            'calmjs.testing.module2': module2,
        })

        # root will not work
        result = registry.get_records_for_package('calmjs')
        self.assertEqual(result, {})
        # likewise not for the module.
        result = registry.get_records_for_package('calmjs.testing.module1')
        self.assertEqual(result, {})

        # singular result at the module level should still work
        result = registry.get('calmjs.testing.module2')
        self.assertEqual(result, {'calmjs.testing.module2': module2})

    def test_dummy_implemented_manual_entrypoint(self):
        from calmjs.testing import module1
        registry = DummyModuleRegistry(__name__)
        with pretty_logging(stream=mocks.StringIO()) as s:
            registry.register_entry_point(
                EntryPoint.parse(
                    'calmjs.testing.module1 = calmjs.testing.module1')
            )
            # no dist.
            self.assertIn('manually registering entry_point', s.getvalue())
        result = registry.get_record('calmjs.testing.module1')
        self.assertEqual(result, {'calmjs.testing.module1': module1})

    def test_dummy_implemented_manual_entrypoint_double_regisetr(self):
        from calmjs.testing import module1
        registry = DummyModuleRegistry(__name__)
        with pretty_logging(stream=mocks.StringIO()) as s:
            registry.register_entry_point(
                EntryPoint.parse(
                    'calmjs.testing.module1 = calmjs.testing.module1'))
            registry.register_entry_point(
                EntryPoint.parse(
                    'calmjs.testing.module1 = calmjs.testing.module1'))
            # no dist.
            self.assertIn('manually registering entry_point', s.getvalue())
        result = registry.get_record('calmjs.testing.module1')
        # just merged together.
        self.assertEqual(result, {'calmjs.testing.module1': module1})

    def test_got_record_cloned(self):
        # returned records should clones.
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing.module1',
        ]})
        registry = DummyModuleRegistry(__name__, _working_set=working_set)
        record1 = registry.get_record('calmjs.testing.module1')
        record2 = registry.get_record('calmjs.testing.module1')
        self.assertIsNot(record1, record2)

    def test_dupe_register(self):
        # returned records should clones.
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing',
            'calmjs.testing.module2 = calmjs.testing',
        ]})
        with pretty_logging(stream=mocks.StringIO()) as s:
            DummyModuleRegistry(__name__, _working_set=working_set)
        self.assertIn("overwriting keys: ['calmjs.testing']", s.getvalue())

    def test_record_internal_normalization(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[modules]\n'
            'record = calmjs.module:ModuleRegistry\n'
        ),), 'unsafe_name', '1.0')

        working_set = WorkingSet([self._calmjs_testing_tmpdir])
        registry = DummyModuleRegistry('modules', _working_set=working_set)
        self.assertEqual(
            1, len(registry.get_records_for_package('unsafe_name')))


class BaseExternalModuleRegistryTestCase(unittest.TestCase):
    """
    Similar to previous tests, except the names are references to the
    files in locations managed by an external package manager, i.e.
    npm and node_modules.
    """

    def setUp(self):
        self.original_working_set = base.working_set

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_simple_record(self):
        working_set = mocks.WorkingSet({__name__: [
            'dummy/whatever/module.js = module',
            'dummy/whatever/module-slim.js = module',
        ]}, dist=Distribution(project_name='calmjs.testing'))

        registry = base.BaseExternalModuleRegistry(
            __name__, _working_set=working_set)

        self.assertEqual(len(registry.raw_entry_points), 2)
        self.assertEqual(registry.get_record('module'), {
            'dummy/whatever/module.js',
            'dummy/whatever/module-slim.js',
        })
        self.assertEqual(list(registry.iter_records()), [('module', {
            'dummy/whatever/module.js',
            'dummy/whatever/module-slim.js',
        })])

        self.assertEqual(registry.get_records_for_package('calmjs.testing'), [
            'dummy/whatever/module.js',
            'dummy/whatever/module-slim.js',
        ])

    def test_record_internal_normalization(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[modules]\n'
            'some/where/path.js = calmjs.module\n'
        ),), 'unsafe_name', '1.0')

        working_set = WorkingSet([self._calmjs_testing_tmpdir])
        registry = DummyModuleRegistry('modules', _working_set=working_set)
        self.assertEqual(
            1, len(registry.get_records_for_package('unsafe_name')))


class BaseDriverClassTestCase(unittest.TestCase):
    """
    BaseDriver class test case.
    """

    def test_construction(self):
        driver = base.BaseDriver(
            node_path='node_path', env_path='env_path', working_dir='cwd',
            indent=2, separators=(', ', ':'))
        self.assertEqual(driver.node_path, 'node_path')
        self.assertEqual(driver.env_path, 'env_path')
        self.assertEqual(driver.working_dir, 'cwd')
        self.assertEqual(driver.indent, 2)
        self.assertEqual(driver.separators, (', ', ':'))

    def test_join_cwd(self):
        driver = base.BaseDriver()
        self.assertEqual(driver.cwd, os.getcwd())
        self.assertTrue(driver.join_cwd('bar').startswith(os.getcwd()))
        driver.working_dir = mkdtemp(self)

        self.assertEqual(driver.cwd, driver.working_dir)
        result = driver.join_cwd('bar')
        self.assertTrue(result.startswith(driver.working_dir))
        self.assertTrue(result.endswith('bar'))

        result = driver.join_cwd()
        self.assertEqual(result, driver.working_dir)

    def test_which(self):
        driver = base.BaseDriver()
        # no binary, no nothing.
        self.assertIsNone(driver.which())

    def test_find_node_modules_basedir(self):
        driver = base.BaseDriver()
        # ensure that NODE_PATH is initially None
        driver.node_path = None
        driver.working_dir = mkdtemp(self)
        # initially should be empty, since no node_modules in either
        # directories that it should check
        self.assertEqual([], driver.find_node_modules_basedir())

        # having the NODE_PATH defined will result in such
        p1 = mkdtemp(self)
        p2 = mkdtemp(self)
        driver.node_path = pathsep.join([p1, p2])
        self.assertEqual([p1, p2], driver.find_node_modules_basedir())

        # create the node_modules in the working directory defined for
        # the driver instance, and unset NODE_PATH
        driver.node_path = None
        dwd_wd_nm = join(driver.working_dir, 'node_modules')
        os.mkdir(dwd_wd_nm)
        self.assertEqual([dwd_wd_nm], driver.find_node_modules_basedir())

        # combine the two, they should be in this order, where the
        # working directory has higher precedence over NODE_PATH
        driver.node_path = p1
        self.assertEqual([dwd_wd_nm, p1], driver.find_node_modules_basedir())

    def test_which_with_node_modules(self):
        driver = base.BaseDriver()
        # ensure that NODE_PATH is initially None
        driver.node_path = None
        driver.working_dir = mkdtemp(self)
        # initially should be empty, since no node_modules in either
        # directories that it should check
        with pretty_logging(stream=mocks.StringIO()) as s:
            self.assertIsNone(driver.which_with_node_modules())
        # should not generate extra log messages.
        self.assertNotIn('will attempt', s.getvalue())

        # having the NODE_PATH defined will result in such
        p1 = mkdtemp(self)
        p2 = mkdtemp(self)
        driver.node_path = pathsep.join([p1, p2])
        with pretty_logging(stream=mocks.StringIO()) as s:
            self.assertIsNone(driver.which_with_node_modules())

        # should not generate extra log messages, binary still not
        # assigned.
        self.assertNotIn('will attempt', s.getvalue())

        driver.binary = 'dummy'
        with pretty_logging(stream=mocks.StringIO()) as s:
            self.assertIsNone(driver.which_with_node_modules())

        # now the log should show what attempted.
        log = s.getvalue()
        self.assertIn(
            "'BaseDriver' instance will attempt to locate 'dummy' binary from "
            "its NODE_PATH of", log)
        self.assertIn(p1, log)
        self.assertIn(p2, log)
        self.assertIn("'BaseDriver' instance located 2 possible paths", log)

        # try again with working directory
        driver.node_path = None
        dwd_wd_nm = join(driver.working_dir, 'node_modules')
        os.mkdir(dwd_wd_nm)
        with pretty_logging(stream=mocks.StringIO()) as s:
            self.assertIsNone(driver.which_with_node_modules())

        log = s.getvalue()
        # now the log should show what attempted.
        self.assertIn(
            "'BaseDriver' instance will attempt to locate 'dummy' binary from",
            log,
        )
        self.assertIn(dwd_wd_nm, log)
        self.assertIn("located through the working directory", log)
        self.assertIn("'BaseDriver' instance located 1 possible paths", log)

    def test_dump(self):
        driver = base.BaseDriver()
        stream = mocks.StringIO()
        driver.dump({'a': 1}, stream)
        self.assertEqual(stream.getvalue(), '{\n    "a": 1\n}')

    def test_dumps(self):
        driver = base.BaseDriver()
        self.assertEqual(driver.dumps({'a': 1}), '{\n    "a": 1\n}')

    def test_get_exec_binary_no_binary(self):
        with self.assertRaises(OSError):
            base._get_exec_binary('no_such_binary_hopefully', {})

    def test_get_exec_binary_with_binary(self):
        tmpdir = mkdtemp(self)
        prog = create_fake_bin(tmpdir, 'prog')
        self.assertEqual(normcase(prog), normcase(base._get_exec_binary(
            'prog', {'env': {'PATH': tmpdir}})))

    def test_set_env_path_with_node_modules_undefined(self):
        driver = base.BaseDriver()
        with self.assertRaises(ValueError) as e:
            driver._set_env_path_with_node_modules()
        self.assertEqual(
            str(e.exception),
            "binary undefined for 'calmjs.base:BaseDriver' instance"
        )

    def test_base_create_fail(self):
        with self.assertRaises(ValueError) as e:
            base.BaseDriver.create()
        self.assertEqual(
            str(e.exception),
            "binary undefined for 'calmjs.base:BaseDriver' instance"
        )

    def test_base_create_succeed(self):
        class BinaryDriver(base.BaseDriver):
            def __init__(self, **kw):
                super(BinaryDriver, self).__init__(**kw)
                self.binary = 'binary'

        inst = BinaryDriver.create()
        self.assertTrue(isinstance(inst, base.BaseDriver))
        self.assertEqual(inst.binary, 'binary')
