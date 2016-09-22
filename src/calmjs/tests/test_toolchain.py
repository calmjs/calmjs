# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import tempfile
from os import makedirs
from os.path import basename
from os.path import exists
from os.path import join
from os.path import pardir
from os.path import realpath

from calmjs.exc import ValueSkip
from calmjs.utils import pretty_logging
from calmjs.toolchain import Spec
from calmjs.toolchain import Toolchain
from calmjs.toolchain import NullToolchain

from calmjs.testing.mocks import StringIO
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
        with pretty_logging(stream=StringIO()) as s:
            spec.do_callbacks('cleanup')
        self.assertIn('Traceback', s.getvalue())


class ToolchainTestCase(unittest.TestCase):
    """
    Base toolchain class test case.
    """

    def setUp(self):
        self.toolchain = Toolchain()

    def tearDown(self):
        pass

    def test_toolchain_calf_not_spec(self):
        # can't just use a normal dict
        with self.assertRaises(TypeError):
            self.toolchain({})

    def test_toolchain_standard_not_implemented(self):
        spec = Spec()

        with self.assertRaises(NotImplementedError):
            self.toolchain(spec)

        with self.assertRaises(NotImplementedError):
            self.toolchain.assemble(spec)

        with self.assertRaises(NotImplementedError):
            self.toolchain.link(spec)

        # Check that the build_dir is set on the spec based on tempfile
        self.assertTrue(spec['build_dir'].startswith(
            realpath(tempfile.gettempdir())))
        # Also that it got deleted properly.
        self.assertFalse(exists(spec['build_dir']))

    def test_toolchain_calf_with_build_dir_null(self):
        spec = Spec(build_dir=None)

        with self.assertRaises(NotImplementedError):
            self.toolchain(spec)

        # While build_dir is defined, no value was assigned.  See that
        # the process will give it a new one.
        self.assertTrue(spec['build_dir'].startswith(
            realpath(tempfile.gettempdir())))
        # Also that it got deleted properly.
        self.assertFalse(exists(spec['build_dir']))

    def test_toolchain_standard_compile(self):
        spec = Spec()
        self.toolchain.compile(spec)
        self.assertEqual(spec['transpiled_paths'], {})
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

        # Manually specified build_dirs do not get deleted from the
        # filesystem
        self.assertTrue(exists(spec['build_dir']))

        not_exist = join(spec['build_dir'], 'not_exist')

        spec['build_dir'] = not_exist
        with self.assertRaises(OSError):
            # well, dir does not exist
            self.toolchain(spec)

        # Manually specified build_dirs do not get modified if they just
        # simply don't exist.
        self.assertEqual(spec['build_dir'], not_exist)

    def test_toolchain_standard_build_dir_remapped(self):
        """
        This can either be caused by relative paths or symlinks.  Will
        result in the manually specified build_dir being remapped to its
        real location
        """

        fake = mkdtemp(self)
        real = mkdtemp(self)
        real_base = basename(real)
        spec = Spec()
        spec['build_dir'] = join(fake, pardir, real_base)

        with pretty_logging(stream=StringIO()) as s:
            with self.assertRaises(NotImplementedError):
                self.toolchain(spec)

        self.assertIn('realpath of build_dir resolved to', s.getvalue())
        self.assertEqual(spec['build_dir'], real)

    def test_toolchain_target_build_dir_inside(self):
        """
        Mostly a sanity check; who knows if anyone will write some
        config that will break this somehow.
        """

        source = mkdtemp(self)
        build_dir = mkdtemp(self)

        with open(join(source, 'source.js'), 'w') as fd:
            fd.write('Hello world.')

        spec = Spec(
            build_dir=build_dir,
            transpile_source_map={
                # lol ``.`` being valid namespace in node
                '../source': join(source, 'source'),
            },
        )
        with self.assertRaises(ValueError):
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
        target = 'target.js'

        with open(source, 'w') as fd:
            fd.write(js_code)

        spec = Spec(build_dir=tmpdir)
        modname = 'dummy'
        self.toolchain.transpile_modname_source_target(
            spec, modname, source, target)

        with open(join(tmpdir, target)) as fd:
            result = fd.read()

        self.assertEqual(js_code, result)

    def test_toolchain_naming(self):
        s = Spec()
        self.assertEqual(self.toolchain.modname_source_to_modname(
            s, 'example/module', '/tmp/example.module/src/example/module.js'),
            'example/module',
        )
        self.assertEqual(self.toolchain.modname_source_to_source(
            s, 'example/module', '/tmp/example.module/src/example/module.js'),
            '/tmp/example.module/src/example/module.js',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'example/module', '/tmp/example.module/src/example/module.js'),
            'example/module.js',
        )

    def test_toolchain_gen_modname_source_target_modpath(self):
        spec = Spec()
        toolchain = self.toolchain
        result = sorted(toolchain._gen_modname_source_target_modpath(spec, {
            'ex/mod1': '/src/ex/mod1.js',
            'ex/mod2': '/src/ex/mod2.js',
        }))

        self.assertEqual(result, [
            ('ex/mod1', '/src/ex/mod1.js', 'ex/mod1.js', 'ex/mod1'),
            ('ex/mod2', '/src/ex/mod2.js', 'ex/mod2.js', 'ex/mod2'),
        ])

    def test_toolchain_gen_modname_source_target_modpath_alt_names(self):
        class AltToolchain(NullToolchain):
            def modname_source_target_modnamesource_to_modpath(
                    self, spec, modname, source, target, modname_source):
                return '/-'.join(modname_source)

        spec = Spec()
        toolchain = AltToolchain()
        result = sorted(toolchain._gen_modname_source_target_modpath(spec, {
            'ex/m1': '/src/ex/m1.js',
            'ex/m2': '/src/ex/m2.js',
        }))

        self.assertEqual(result, [
            ('ex/m1', '/src/ex/m1.js', 'ex/m1.js', 'ex/m1/-/src/ex/m1.js'),
            ('ex/m2', '/src/ex/m2.js', 'ex/m2.js', 'ex/m2/-/src/ex/m2.js'),
        ])

    def test_toolchain_gen_modname_source_target_modpath_failure_safe(self):
        # allow subclasses to raise ValueError to trigger a skip.
        class FailToolchain(NullToolchain):
            def modname_source_to_target(self, spec, modname, source):
                if 'fail' in source:
                    raise ValueError('source cannot fail')
                elif 'skip' in source:
                    raise ValueSkip('skipping source')
                return super(FailToolchain, self).modname_source_to_target(
                    spec, modname, source)

        spec = Spec()
        toolchain = FailToolchain()

        with pretty_logging(stream=StringIO()) as s:
            result = sorted(toolchain._gen_modname_source_target_modpath(
                spec, {
                    'ex/mod1': '/src/ex/mod1.js',
                    'ex/mod2': 'fail',
                    'ex/mod3': '/src/ex/mod3.js',
                },
            ))

        self.assertIn("WARNING", s.getvalue())
        self.assertIn(
            "failed to acquire name with 'modname_source_to_target' where "
            "modname='ex/mod2', source='fail'", s.getvalue(),
        )

        self.assertEqual(result, [
            ('ex/mod1', '/src/ex/mod1.js', 'ex/mod1.js', 'ex/mod1'),
            ('ex/mod3', '/src/ex/mod3.js', 'ex/mod3.js', 'ex/mod3'),
        ])

        with pretty_logging(stream=StringIO()) as s:
            self.assertEqual(sorted(
                toolchain._gen_modname_source_target_modpath(
                    spec, {'skip': 'skip'})), [])

        self.assertIn("INFO", s.getvalue())
        self.assertIn(
            "toolchain purposely skipping on 'modname_source_to_target' where "
            "modname='skip', source='skip'", s.getvalue(),
        )

    def test_null_toolchain_transpile_sources(self):
        source_dir = mkdtemp(self)
        build_dir = mkdtemp(self)
        source_file = join(source_dir, 'source.js')

        with open(source_file, 'w') as fd:
            fd.write('var dummy = function () {};\n')

        spec = Spec(
            build_dir=build_dir,
            transpile_source_map={
                'namespace.dummy.source': source_file,
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'transpile_source_map': {
                'namespace.dummy.source': source_file,
            },

            'bundled_paths': {},
            'transpiled_paths': {
                'namespace.dummy.source': 'namespace.dummy.source',
            },
            'module_names': ['namespace.dummy.source'],
            'prepare': 'prepared',
            'assemble': 'assembled',
            'link': 'linked',
        })
        self.assertTrue(exists(join(build_dir, 'namespace.dummy.source.js')))

    def test_null_toolchain_bundle_sources(self):
        source_dir = mkdtemp(self)
        bundle_dir = mkdtemp(self)
        build_dir = mkdtemp(self)

        source_file = join(source_dir, 'source.js')

        with open(source_file, 'w') as fd:
            fd.write('var dummy = function () {};\n')

        with open(join(bundle_dir, 'bundle.js'), 'w') as fd:
            fd.write('var dummy = function () {};\n')

        spec = Spec(
            build_dir=build_dir,
            bundle_source_map={
                'bundle1': source_file,
                'bundle2': bundle_dir,
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'bundle_source_map': {
                'bundle1': source_file,
                'bundle2': bundle_dir,
            },

            'bundled_paths': {
                'bundle1': 'bundle1',
                'bundle2': 'bundle2',
            },
            'transpiled_paths': {},
            'module_names': ['bundle1'],
            'prepare': 'prepared',
            'assemble': 'assembled',
            'link': 'linked',
        })
        self.assertTrue(exists(join(build_dir, 'bundle1.js')))
        self.assertTrue(exists(join(build_dir, 'bundle2', 'bundle.js')))

    def test_null_toolchain_transpile_js_ns_directory_sources(self):
        """
        Ensure that directory structures are copied, if needed, because
        JavaScript uses directories for namespaces, too, however the
        names are verbatim from directories and `.`s are valid module
        names which can result in some really hilarious side effects
        when combined with its completely transparent model on top of
        the filesystem (think ``..``), but that's for another time.
        """

        source_dir = mkdtemp(self)
        build_dir = mkdtemp(self)

        namespace_root = join(source_dir, 'namespace', 'dummy')
        makedirs(namespace_root)
        source_file = join(namespace_root, 'source.js')
        with open(source_file, 'w') as fd:
            fd.write('var dummy = function () {};\n')

        spec = Spec(
            build_dir=build_dir,
            transpile_source_map={
                'namespace/dummy/source': source_file,
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'transpile_source_map': {
                'namespace/dummy/source': source_file,
            },

            'bundled_paths': {},
            'transpiled_paths': {
                'namespace/dummy/source': 'namespace/dummy/source',
            },
            'module_names': ['namespace/dummy/source'],
            'prepare': 'prepared',
            'assemble': 'assembled',
            'link': 'linked',
        })
        self.assertTrue(exists(join(
            build_dir, 'namespace', 'dummy', 'source.js')))
