# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
import tempfile
from inspect import currentframe
from os import makedirs
from os.path import basename
from os.path import exists
from os.path import join
from os.path import pardir
from os.path import realpath

from calmjs.exc import ValueSkip
from calmjs import toolchain as calmjs_toolchain
from calmjs.utils import pretty_logging
from calmjs.toolchain import Spec
from calmjs.toolchain import Toolchain
from calmjs.toolchain import ToolchainAbort
from calmjs.toolchain import ToolchainCancel
from calmjs.toolchain import NullToolchain

from calmjs.toolchain import CLEANUP
from calmjs.toolchain import SUCCESS
from calmjs.toolchain import AFTER_FINALIZE
from calmjs.toolchain import BEFORE_FINALIZE
from calmjs.toolchain import AFTER_LINK
from calmjs.toolchain import BEFORE_LINK
from calmjs.toolchain import AFTER_ASSEMBLE
from calmjs.toolchain import BEFORE_ASSEMBLE
from calmjs.toolchain import AFTER_COMPILE
from calmjs.toolchain import BEFORE_COMPILE
from calmjs.toolchain import AFTER_PREPARE
from calmjs.toolchain import BEFORE_PREPARE

from calmjs.testing.mocks import StringIO
from calmjs.testing.spec import create_spec_event_fault
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import stub_stdouts
from calmjs.testing.utils import stub_item_attr_value


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

    def test_spec_event_standard(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec()
        spec.on_event(CLEANUP, cb, check, 1, keyword='foo')
        spec.on_event(CLEANUP, cb, check, 2, keyword='bar')
        self.assertEqual(len(spec._events), 1)

        spec.do_events('foo')
        self.assertEqual(check, [])

        spec.do_events(CLEANUP)
        # cleanup done lifo
        self.assertEqual(check, [
            ((2,), {'keyword': 'bar'}),
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_event_blackhole(self):
        spec = Spec()
        check = []
        spec.on_event(None, check.append, 1)
        self.assertEqual(len(spec._events), 0)
        spec.do_events(None)
        self.assertEqual(check, [])

    def test_spec_event_malformed(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec()
        spec.on_event(CLEANUP, cb, check, 1, keyword='foo')
        # malformed data shouldn't be added, but just in case.
        spec._events[CLEANUP].append((cb,))
        spec._events[CLEANUP].append((cb, [], []))
        spec._events[CLEANUP].append((cb, {}, {}))
        spec._events[CLEANUP].append((None, [], {}))

        spec.do_events(CLEANUP)
        self.assertEqual(check, [
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_event_broken(self):
        spec = Spec()
        spec.on_event(CLEANUP, fake_error(Exception))
        with pretty_logging(stream=StringIO()) as s:
            spec.do_events(CLEANUP)
        self.assertIn('Traceback', s.getvalue())

    def test_spec_event_fault_standard(self):
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            create_spec_event_fault(spec, 'broken')
        self.assertNotIn("on_event 'broken' invoked by ", s.getvalue())
        self.assertNotIn("spec.py:11", s.getvalue())

    def test_spec_event_fault_debug_1_emulate_no_currentframe(self):
        stub_item_attr_value(
            self, calmjs_toolchain, 'currentframe', lambda: None)
        spec = Spec(debug=1)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_event_fault(spec, 'broken')
        self.assertIn("currentframe() failed to return frame", s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_event_fault_debug_1(self):
        spec = Spec(debug=1)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_event_fault(spec, 'broken')

        self.assertIn("on_event 'broken' invoked by ", s.getvalue())
        self.assertIn("spec.py:11", s.getvalue())

        with pretty_logging(stream=StringIO()) as s:
            spec.do_events('broken')
        self.assertIn('Traceback', s.getvalue())
        self.assertNotIn('Traceback for original event', s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_event_fault_debug_2(self):
        spec = Spec(debug=2)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_event_fault(spec, 'broken')

        self.assertIn("on_event 'broken' invoked by ", s.getvalue())
        self.assertIn("spec.py:11", s.getvalue())

        with pretty_logging(stream=StringIO()) as s:
            spec.do_events('broken')
        self.assertIn('Traceback for original event', s.getvalue())
        self.assertIn('line 15, in create_spec_event_fault', s.getvalue())

    # infinite loop protection checks.

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_event_block_do_events_further_on_event(self):
        spec = Spec()

        def on_event():
            spec.on_event(CLEANUP, add_bad_cleanup, spec)

        def add_bad_cleanup(spec):
            on_event()

        # can add the event in through any method required
        with pretty_logging(stream=StringIO()) as s:
            spec.on_event(CLEANUP, add_bad_cleanup, spec)
        self.assertEqual(s.getvalue(), '')

        # The failure is raised from within do_events; this case would
        # have raised an infinite loop.
        with pretty_logging(stream=StringIO()) as s:
            spec.do_events(CLEANUP)

        self.assertIn(
            "indirect invocation of 'on_event' by 'do_events' is forbidden",
            s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_event_block_do_events_further_do_events(self):
        spec = Spec()
        spec._events[CLEANUP] = []

        def fake_event_add():
            event = (fake_event_add, (), {})
            spec._events[CLEANUP].append(event)
            spec.do_events(CLEANUP)

        with pretty_logging(stream=StringIO()) as s:
            fake_event_add()
            spec.do_events(CLEANUP)

        self.assertIn(
            "indirect invocation of 'do_events' by 'do_events' is forbidden",
            s.getvalue())

    def test_spec_event_no_infinite_pop(self):
        spec = Spec(counter=0)
        spec._events[CLEANUP] = []

        def fake_event_add():
            event = (fake_event_add, (), {})
            spec._events[CLEANUP].append(event)
            spec['counter'] += 1

        with pretty_logging(stream=StringIO()) as s:
            fake_event_add()
            self.assertEqual(spec['counter'], 1)
            spec.do_events(CLEANUP)
            # ensure that it only got called once.
            self.assertEqual(spec['counter'], 2)
        self.assertEqual(s.getvalue(), '')

        # this one can work without frame protection.
        stub_item_attr_value(
            self, calmjs_toolchain, 'currentframe', lambda: None)
        with pretty_logging(stream=StringIO()) as s:
            spec.do_events(CLEANUP)
        self.assertEqual(spec['counter'], 4)
        self.assertIn(
            'currentframe() returned None; frame protection disabled',
            s.getvalue())

    # that's all the standard vectors I can cover, if someone wants to
    # attack this using somewhat more advanced/esoteric methods, I guess
    # they wanted an EXPLOSION.


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

    def test_toolchain_call_standard_failure_event(self):
        cleanup, success = [], []
        spec = Spec()
        spec.on_event(CLEANUP, cleanup.append, True)
        spec.on_event(SUCCESS, success.append, True)

        with self.assertRaises(NotImplementedError):
            self.toolchain(spec)

        self.assertEqual(len(cleanup), 1)
        self.assertEqual(len(success), 0)

    def test_toolchain_standard_compile(self):
        spec = Spec()
        self.toolchain.compile(spec)
        self.assertEqual(spec['transpiled_modpaths'], {})
        self.assertEqual(spec['bundled_modpaths'], {})
        self.assertEqual(spec['transpiled_targets'], {})
        self.assertEqual(spec['bundled_targets'], {})
        self.assertEqual(spec['export_module_names'], [])

    def test_toolchain_standard_compile_existing_values(self):
        # Test that in the case where existing path maps will block, and
        # the existing module_names will be kept
        transpiled_modpaths = {}
        bundled_modpaths = {}
        transpiled_targets = {}
        bundled_targets = {}
        export_module_names = ['fake_names']
        spec = Spec(
            transpiled_modpaths=transpiled_modpaths,
            bundled_modpaths=bundled_modpaths,
            transpiled_targets=transpiled_targets,
            bundled_targets=bundled_targets,
            export_module_names=export_module_names,
        )

        with pretty_logging(stream=StringIO()) as s:
            self.toolchain.compile(spec)

        msg = s.getvalue()
        self.assertIn("attempted to write 'transpiled_modpaths' to spec", msg)
        self.assertIn("attempted to write 'bundled_modpaths' to spec", msg)
        # These are absent due to early abort
        self.assertNotIn("attempted to write 'transpiled_targets'", msg)
        self.assertNotIn("attempted to write 'bundled_targets'", msg)

        # compile step error messages
        self.assertIn(
            ("aborting compile step %r due to existing key" % (
                ('transpile', 'transpile', 'transpiled'),)), msg)
        self.assertIn(
            ("aborting compile step %r due to existing key" % (
                ('bundle', 'bundle', 'bundled'),)), msg)

        # All should be same identity
        self.assertIs(spec['transpiled_modpaths'], transpiled_modpaths)
        self.assertIs(spec['bundled_modpaths'], bundled_modpaths)
        self.assertIs(spec['transpiled_targets'], transpiled_targets)
        self.assertIs(spec['bundled_targets'], bundled_targets)
        self.assertIs(spec['export_module_names'], export_module_names)

    def test_toolchain_standard_compile_existing_values_altarnate(self):
        # Test that in the case where existing path maps will block, and
        # the existing export_module_names will be kept
        transpiled_targets = {}
        bundled_targets = {}
        spec = Spec(
            transpiled_targets=transpiled_targets,
            bundled_targets=bundled_targets,
        )

        with pretty_logging(stream=StringIO()) as s:
            self.toolchain.compile(spec)

        msg = s.getvalue()
        # These are filtered first
        self.assertIn(
            "attempted to write 'transpiled_targets' to spec but key already "
            "exists; not overwriting, skipping", msg)
        self.assertIn(
            "attempted to write 'bundled_targets' to spec but key already "
            "exists; not overwriting, skipping", msg)

        # These first couple won't be written since code never hit it
        self.assertNotIn('transpiled_modpaths', spec)
        self.assertNotIn('bundled_modpaths', spec)
        self.assertIs(spec['bundled_targets'], bundled_targets)
        self.assertIs(spec['transpiled_targets'], transpiled_targets)

    def test_toolchain_standard_compile_bad_export_module_names_type(self):
        export_module_names = {}
        spec = Spec(export_module_names=export_module_names)

        with self.assertRaises(TypeError):
            self.toolchain.compile(spec)

    def test_toolchain_standard_compile_alternate_entries(self):
        # Not a standard way to override this, but good enough as a
        # demo.
        def compile_faked(spec, entries):
            return {'fake': 'nothing'}, {'fake': 'nothing.js'}, ['fake']

        self.toolchain.compile_entries = ((compile_faked, 'fake', 'faked'),)
        spec = Spec()

        self.toolchain.compile(spec)

        self.assertNotIn('transpiled_modpaths', spec)
        self.assertNotIn('bundled_modpaths', spec)
        self.assertNotIn('transpiled_targets', spec)
        self.assertNotIn('bundled_targets', spec)
        self.assertEqual(spec['faked_modpaths'], {'fake': 'nothing'})
        self.assertEqual(spec['faked_targets'], {'fake': 'nothing.js'})
        self.assertEqual(spec['export_module_names'], ['fake'])

    def test_toolchain_standard_compile_alternate_entries_not_callable(self):
        # Again, this is not the right way, should subclass/define a new
        # build_compile_entries method.
        self.toolchain.compile_entries = (('very_not_here', 'fake', 'faked'),)
        spec = Spec()

        with pretty_logging(stream=StringIO()) as s:
            self.toolchain.compile(spec)

        msg = s.getvalue()
        self.assertIn("'very_not_here' not a callable attribute for", msg)

        self.assertNotIn('transpiled_modpaths', spec)
        self.assertNotIn('bundled_modpaths', spec)
        self.assertNotIn('transpiled_targets', spec)
        self.assertNotIn('bundled_targets', spec)

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
                # lol ``.`` being valid char for namespace in node
                '../source': join(source, 'source'),
            },
        )
        with self.assertRaises(ValueError):
            self.toolchain(spec)

    def test_toolchain_compile_bundle(self):
        """
        Test out the compile bundle being actually flexible for variety
        of cases.
        """

        build_dir = mkdtemp(self)
        src_dir = mkdtemp(self)
        src = join(src_dir, 'mod.js')

        spec = {'build_dir': build_dir}

        with open(src, 'w') as fd:
            fd.write('module.export = function () {};')

        # prepare targets
        target1 = 'mod1.js'
        target2 = join('namespace', 'mod2.js')
        target3 = join('nested', 'namespace', 'mod3.js')
        target4 = 'namespace.mod4.js'

        self.toolchain.compile_bundle(spec, [
            ('mod1', src, target1, 'mod1'),
            ('mod2', src, target2, 'mod2'),
            ('mod3', src, target3, 'mod3'),
            ('mod4', src, target4, 'mod4'),
        ])

        self.assertTrue(exists(join(build_dir, target1)))
        self.assertTrue(exists(join(build_dir, target2)))
        self.assertTrue(exists(join(build_dir, target3)))
        self.assertTrue(exists(join(build_dir, target4)))


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
            "failed to acquire name with 'modname_source_to_target', "
            "reason: source cannot fail, "
            "where modname='ex/mod2', source='fail'", s.getvalue(),
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
            "toolchain purposely skipping on 'modname_source_to_target', "
            "reason: skipping source, "
            "where modname='skip', source='skip'", s.getvalue(),
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

            'bundled_modpaths': {},
            'bundled_targets': {},
            'transpiled_modpaths': {
                'namespace.dummy.source': 'namespace.dummy.source',
            },
            'transpiled_targets': {
                'namespace.dummy.source': 'namespace.dummy.source.js',
            },
            'export_module_names': ['namespace.dummy.source'],
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

            'bundled_modpaths': {
                'bundle1': 'bundle1',
                'bundle2': 'bundle2',
            },
            'bundled_targets': {
                'bundle1': 'bundle1.js',
                'bundle2': 'bundle2.js',
            },
            'transpiled_modpaths': {},
            'transpiled_targets': {},
            'export_module_names': ['bundle1'],
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

            'bundled_modpaths': {},
            'bundled_targets': {},
            'transpiled_modpaths': {
                'namespace/dummy/source': 'namespace/dummy/source',
            },
            'transpiled_targets': {
                'namespace/dummy/source': 'namespace/dummy/source.js',
            },
            'export_module_names': ['namespace/dummy/source'],
            'prepare': 'prepared',
            'assemble': 'assembled',
            'link': 'linked',
        })
        self.assertTrue(exists(join(
            build_dir, 'namespace', 'dummy', 'source.js')))

    def test_null_toolchain_call_standard_success_event(self):
        cleanup, success = [], []
        spec = Spec()
        spec.on_event(CLEANUP, cleanup.append, True)
        spec.on_event(SUCCESS, success.append, True)
        self.toolchain(spec)
        self.assertEqual(len(cleanup), 1)
        self.assertEqual(len(success), 1)

    def test_null_toolchain_no_event(self):
        cleanup, success = [], []
        spec = Spec()
        spec.on_event(CLEANUP, cleanup.append, True)
        spec.on_event(SUCCESS, success.append, True)
        # no events done through the private call
        self.toolchain._calf(spec)
        self.assertEqual(len(cleanup), 0)
        self.assertEqual(len(success), 0)

    def test_null_toolchain_all_events(self):
        # These are ordered in the same order as they should be called
        stub_stdouts(self)
        events = (
            BEFORE_PREPARE, AFTER_PREPARE, BEFORE_COMPILE, AFTER_COMPILE,
            BEFORE_ASSEMBLE, AFTER_ASSEMBLE, BEFORE_LINK, AFTER_LINK,
            BEFORE_FINALIZE, AFTER_FINALIZE, SUCCESS, CLEANUP,
        )
        spec = Spec()
        results = []
        for event in events:
            spec.on_event(event, results.append, event)

        self.toolchain._calf(spec)
        self.assertEqual(len(results), 0)

        self.toolchain(spec)
        self.assertEqual(tuple(results), events)

    def _check_toolchain_event(self, event, error):
        events = []
        spec = Spec()
        spec.on_event(BEFORE_ASSEMBLE, event)
        spec.on_event(CLEANUP, events.append, CLEANUP)
        spec.on_event(SUCCESS, events.append, SUCCESS)

        if error:
            with self.assertRaises(ToolchainAbort):
                with pretty_logging(stream=StringIO()) as s:
                    self.toolchain(spec)
            test_method = self.assertIn
        else:
            with pretty_logging(stream=StringIO()) as s:
                self.toolchain(spec)
            test_method = self.assertNotIn

        test_method(
            "an event in group 'before_assemble' triggered an abort: "
            "forced abort", s.getvalue()
        )
        # ensure cleanup is executed regardless, and success is not.
        self.assertEqual(events, [CLEANUP])

    def test_null_toolchain_event_abort(self):
        def abort():
            raise ToolchainAbort('forced abort')

        self._check_toolchain_event(abort, True)

    def test_null_toolchain_event_cancel(self):
        def cancel():
            raise ToolchainCancel('toolchain cancel')

        self._check_toolchain_event(cancel, False)

    def test_null_toolchain_event_keyboard_interrupt(self):
        def interrupt():
            raise KeyboardInterrupt()

        self._check_toolchain_event(interrupt, False)
