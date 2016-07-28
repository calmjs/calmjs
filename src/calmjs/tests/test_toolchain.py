# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import tempfile
from os.path import exists
from os.path import join

from calmjs.toolchain import Spec
from calmjs.toolchain import Toolchain
from calmjs.toolchain import NullToolchain

from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import fake_error


class SpecTestCase(unittest.TestCase):
    """
    Test out the methods offered by the Spec dictionary
    """

    def test_spec_usage(self):
        spec = Spec(a=1, b=2, c=3)
        self.assertEqual(spec['a'], 1)
        self.assertEqual(spec['b'], 2)
        self.assertEqual(spec['c'], 3)

        spec['d'] = 4
        self.assertEqual(spec['d'], 4)

    def test_spec_update_selected(self):
        spec = Spec(a=1, b=2, c=3)
        spec.update_selected({'abcd': 123, 'defg': 321, 'c': 4}, ['defg', 'c'])
        self.assertEqual(spec, {'a': 1, 'b': 2, 'c': 4, 'defg': 321})

    def test_spec_callback(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec()
        spec.add_callback('cleanup', cb, check, 1, keyword='foo')
        spec.add_callback('cleanup', cb, check, 2, keyword='bar')

        spec.do_callbacks('foo')
        self.assertEqual(check, [])

        spec.do_callbacks('cleanup')
        # cleanup done lifo
        self.assertEqual(check, [
            ((2,), {'keyword': 'bar'}),
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_callback_malformed(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec()
        spec.add_callback('cleanup', cb, check, 1, keyword='foo')
        # malformed data shouldn't be added, but just in case.
        spec._callbacks['cleanup'].append((cb,))
        spec._callbacks['cleanup'].append((cb, [], []))
        spec._callbacks['cleanup'].append((cb, {}, {}))
        spec._callbacks['cleanup'].append((None, [], {}))

        spec.do_callbacks('cleanup')
        self.assertEqual(check, [
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_callback_broken(self):
        spec = Spec()
        spec.add_callback('cleanup', fake_error(Exception))
        spec.do_callbacks('cleanup')


class ToolchainTestCase(unittest.TestCase):
    """
    Base toolchain class test case.
    """

    def setUp(self):
        self.toolchain = Toolchain()

    def tearDown(self):
        pass

    def test_toolchain_standard_not_implemented(self):
        spec = Spec()

        with self.assertRaises(NotImplementedError):
            self.toolchain(spec)

        with self.assertRaises(NotImplementedError):
            self.toolchain.assemble(spec)

        with self.assertRaises(NotImplementedError):
            self.toolchain.link(spec)

        # Check that the build_dir is set on the spec based on tempfile
        self.assertTrue(spec['build_dir'].startswith(tempfile.gettempdir()))
        # Also that it got deleted properly.
        self.assertFalse(exists(spec['build_dir']))

    def test_toolchain_standard_compile_all(self):
        spec = Spec()
        self.toolchain.compile_all(spec)
        self.assertEqual(spec['compiled_paths'], {})
        self.assertEqual(spec['bundled_paths'], {})
        self.assertEqual(spec['module_names'], [])

    def test_toolchain_standard_good(self):
        # good, with a mock
        called = []

        def mockcall(spec):
            called.append(True)

        spec = Spec()
        self.toolchain.assemble = mockcall
        self.toolchain.link = mockcall

        self.toolchain(spec)

        self.assertEqual(len(called), 2)

    def test_toolchain_standard_build_dir_set(self):
        spec = Spec()
        spec['build_dir'] = mkdtemp(self)

        with self.assertRaises(NotImplementedError):
            self.toolchain(spec)

        # Manually specified build_dirs do not get deleted.
        self.assertTrue(exists(spec['build_dir']))

        spec['build_dir'] = join(spec['build_dir'], 'not_exist')

        with self.assertRaises(OSError):
            self.toolchain(spec)


class NullToolchainTestCase(unittest.TestCase):
    """
    A null toolchain class test case.
    """

    def setUp(self):
        self.toolchain = NullToolchain()

    def tearDown(self):
        pass

    def test_null_transpiler(self):
        # a kind of silly test but shows concept
        tmpdir = mkdtemp(self)
        js_code = 'var dummy = function () {};\n'
        source = join(tmpdir, 'source.js')
        target = join(tmpdir, 'target.js')

        with open(source, 'w') as fd:
            fd.write(js_code)

        self.toolchain.compile(source, target)

        with open(target) as fd:
            result = fd.read()

        self.assertEqual(js_code, result)

    def test_null_toolchain_transpile_sources(self):
        source_dir = mkdtemp(self)
        build_dir = mkdtemp(self)

        with open(join(source_dir, 'source.js'), 'w') as fd:
            fd.write('var dummy = function () {};\n')

        spec = Spec(
            build_dir=build_dir,
            transpile_source_map={
                # note that the convention in nodejs tools, the .js
                # suffix is completely omitted.
                'namespace.dummy.source': join(source_dir, 'source'),
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'transpile_source_map': {
                'namespace.dummy.source': join(source_dir, 'source')
            },

            'bundled_paths': {},
            'compiled_paths': {
                'namespace.dummy.source': 'namespace.dummy.source',
            },
            'module_names': ['namespace.dummy.source'],
        })
        self.assertTrue(exists(join(build_dir, 'namespace.dummy.source.js')))

    def test_null_toolchain_bundled_sources(self):
        source_dir = mkdtemp(self)
        bundled_dir = mkdtemp(self)
        build_dir = mkdtemp(self)

        with open(join(source_dir, 'source.js'), 'w') as fd:
            fd.write('var dummy = function () {};\n')

        with open(join(bundled_dir, 'bundled.js'), 'w') as fd:
            fd.write('var dummy = function () {};\n')

        spec = Spec(
            build_dir=build_dir,
            bundled_source_map={
                # note that the convention in nodejs tools, the .js
                # suffix is completely omitted.
                'bundle1': join(source_dir, 'source'),
                'bundle2': join(source_dir, bundled_dir),
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'bundled_source_map': {
                'bundle1': join(source_dir, 'source'),
                'bundle2': bundled_dir,
            },

            'bundled_paths': {
                'bundle1': 'bundle1',
                'bundle2': 'bundle2',
            },
            'compiled_paths': {},
            'module_names': ['bundle1'],
        })
        self.assertTrue(exists(join(build_dir, 'bundle1.js')))
        self.assertTrue(exists(join(build_dir, 'bundle2', 'bundled.js')))
