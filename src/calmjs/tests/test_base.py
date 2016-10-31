# -*- coding: utf-8 -*-
import unittest
import os
from os.path import normcase

from pkg_resources import EntryPoint
from pkg_resources import Distribution

from calmjs import base
from calmjs.utils import pretty_logging
from calmjs.testing import mocks
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import create_fake_bin


class DummyModuleRegistry(base.BaseModuleRegistry):

    def _map_entry_point_module(self, entry_point, module):
        return {module.__name__: {module.__name__: module}}


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


class BaseModuleRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def setUp(self):
        self.original_working_set = base.working_set

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_empty(self):
        working_set = mocks.WorkingSet({__name__: []})
        registry = base.BaseModuleRegistry(__name__, _working_set=working_set)
        self.assertEqual(list(registry.iter_records()), [])

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

    def test_not_implemented(self):
        working_set = mocks.WorkingSet({__name__: [
            'calmjs.testing.module1 = calmjs.testing.module1',
        ]})
        with self.assertRaises(NotImplementedError):
            base.BaseModuleRegistry(__name__, _working_set=working_set)

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

    def test_which_with_node_modules(self):
        driver = base.BaseDriver()
        # no binary, no nothing.
        self.assertIsNone(driver.which_with_node_modules())

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
