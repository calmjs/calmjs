# -*- coding: utf-8 -*-
import unittest
import json
import tempfile
from inspect import currentframe
from os import makedirs
from os.path import basename
from os.path import exists
from os.path import join
from os.path import pardir
from os.path import realpath

import pkg_resources

from calmjs.exc import ValueSkip
from calmjs.exc import AdviceAbort
from calmjs.exc import AdviceCancel
from calmjs.exc import ToolchainAbort
from calmjs.exc import ToolchainCancel
from calmjs import toolchain as calmjs_toolchain
from calmjs.utils import pretty_logging
from calmjs.registry import get
from calmjs.toolchain import CALMJS_TOOLCHAIN_ADVICE
from calmjs.toolchain import AdviceRegistry
from calmjs.toolchain import Spec
from calmjs.toolchain import Toolchain
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
from calmjs.testing.spec import create_spec_advise_fault
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import stub_stdouts
from calmjs.testing.utils import stub_item_attr_value


def bad(spec, extras):
    """A simple bad function"""

    items = spec['dummy'] = spec.get('dummy', [])
    items.append('bad')
    raise Exception('bad')


def dummy(spec, extras):
    """A simple dummy function"""

    items = spec['dummy'] = spec.get('dummy', [])
    items.append('dummy')
    if extras:
        spec['extras'] = extras


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

    def test_spec_repr_standard(self):
        spec = Spec(key1='value', key2=33)
        self.assertIn('Spec object', repr(spec))
        self.assertNotIn("'key1': 'value'", repr(spec))

        self.assertIn('Spec object', repr(Spec(debug='not an int')))

    def test_spec_repr_debug(self):
        spec = Spec(key1='value', key2=33, debug=2)
        self.assertNotIn('Spec object', repr(spec))
        self.assertIn("'key1': 'value'", repr(spec))

    def test_spec_repr_debug_recursion(self):
        spec = Spec(key1='value', key2=33, debug=2)
        spec['spec'] = spec
        # if a better implementation is done...
        self.assertIn("'spec': {...}", repr(spec))


class SpecAdviceTestCase(unittest.TestCase):
    """
    Test out the Spec advice system
    """

    def test_spec_advice_standard(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec(debug=1)
        spec.advise(CLEANUP, cb, check, 1, keyword='foo')
        spec.advise(CLEANUP, cb, check, 2, keyword='bar')
        self.assertEqual(len(spec._advices), 1)

        with pretty_logging(stream=StringIO()) as s:
            spec.handle('foo')

        self.assertEqual(check, [])
        self.assertEqual('', s.getvalue())

        with pretty_logging(stream=StringIO()) as s:
            spec.handle(CLEANUP)

        self.assertIn(
            "calmjs.toolchain handling 2 advices in group 'cleanup'",
            s.getvalue(),
        )

        # cleanup done lifo
        self.assertEqual(check, [
            ((2,), {'keyword': 'bar'}),
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_advice_blackhole(self):
        spec = Spec(debug=1)
        check = []
        spec.advise(None, check.append, 1)
        self.assertEqual(len(spec._advices), 0)
        with pretty_logging(stream=StringIO()) as s:
            spec.handle(None)
        self.assertEqual(check, [])
        self.assertEqual(s.getvalue(), '')

    def test_spec_advice_empty_stack(self):
        spec = Spec(debug=1)
        with pretty_logging(stream=StringIO()) as s:
            spec.handle('cleanup')
        self.assertEqual(s.getvalue(), '')

    def test_spec_advice_malformed(self):
        def cb(sideeffect, *a, **kw):
            sideeffect.append((a, kw))

        check = []

        spec = Spec()
        spec.advise(CLEANUP, cb, check, 1, keyword='foo')
        # malformed data shouldn't be added, but just in case.
        spec._advices[CLEANUP].append((cb,))
        spec._advices[CLEANUP].append((cb, [], []))
        spec._advices[CLEANUP].append((cb, {}, {}))
        spec._advices[CLEANUP].append((None, [], {}))

        spec.handle(CLEANUP)
        self.assertEqual(check, [
            ((1,), {'keyword': 'foo'}),
        ])

    def test_spec_advice_broken(self):
        spec = Spec()
        spec.advise(CLEANUP, fake_error(Exception))
        with pretty_logging(stream=StringIO()) as s:
            spec.handle(CLEANUP)
        self.assertIn('Traceback', s.getvalue())

    def test_spec_advise_fault_standard(self):
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            create_spec_advise_fault(spec, 'broken')
        self.assertNotIn("advise 'broken' invoked by ", s.getvalue())
        self.assertNotIn("spec.py:11", s.getvalue())

    def test_spec_advise_fault_debug_1_emulate_no_currentframe(self):
        stub_item_attr_value(
            self, calmjs_toolchain, 'currentframe', lambda: None)
        spec = Spec(debug=1)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_advise_fault(spec, 'broken')
        self.assertIn("currentframe() failed to return frame", s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_advise_fault_debug_1(self):
        spec = Spec(debug=1)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_advise_fault(spec, 'broken')

        self.assertIn("advise 'broken' invoked by ", s.getvalue())
        self.assertIn("spec.py:13", s.getvalue())

        with pretty_logging(stream=StringIO()) as s:
            spec.handle('broken')
        self.assertIn('Traceback', s.getvalue())
        self.assertNotIn('Traceback for original advice', s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_advise_fault_debug_2(self):
        spec = Spec(debug=2)
        with pretty_logging(stream=StringIO()) as s:
            create_spec_advise_fault(spec, 'broken')

        self.assertIn("advise 'broken' invoked by ", s.getvalue())
        self.assertIn("spec.py:13", s.getvalue())

        with pretty_logging(stream=StringIO()) as s:
            spec.handle('broken')
        self.assertIn('Traceback for original advice', s.getvalue())
        self.assertIn('line 17, in create_spec_advise_fault', s.getvalue())

    # infinite loop protection checks.

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_advise_block_handle_further_advise_calls(self):
        spec = Spec()

        def advise():
            spec.advise(CLEANUP, add_bad_cleanup, spec)

        def add_bad_cleanup(spec):
            advise()

        # can add the advice in through any method required
        with pretty_logging(stream=StringIO()) as s:
            spec.advise(CLEANUP, add_bad_cleanup, spec)
        self.assertEqual(s.getvalue(), '')

        # The failure is raised from within handle; this case would
        # have raised an infinite loop.
        with pretty_logging(stream=StringIO()) as s:
            spec.handle(CLEANUP)

        self.assertIn(
            "indirect invocation of 'advise' by 'handle' is forbidden",
            s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_advise_block_handle_further_advise_calls_alternate(self):
        spec = Spec()

        def advise_first(spec):
            spec.advise('second', advise_second, spec)

        def advise_second(spec):
            spec.advise('first', advise_first, spec)

        # can add the advice in through any method required
        with pretty_logging(stream=StringIO()) as s:
            spec.advise('first', advise_first, spec)
        self.assertEqual(s.getvalue(), '')

        with pretty_logging(stream=StringIO()) as s:
            spec.handle('first')
        # should be clear, however...
        self.assertEqual(s.getvalue(), '')

        with pretty_logging(stream=StringIO()) as s:
            spec.handle('second')
        # the second call tries to advise back to first again, which the
        # protection code will finally trigger, even though it will not
        # exactly loop in this case.
        self.assertIn(
            "indirect invocation of 'advise' by 'handle' is forbidden",
            s.getvalue())

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_advice_block_handle_further_handle_call(self):
        spec = Spec()
        spec._advices[CLEANUP] = []

        def fake_advice_add():
            advice = (fake_advice_add, (), {})
            spec._advices[CLEANUP].append(advice)
            spec.handle(CLEANUP)

        with pretty_logging(stream=StringIO()) as s:
            fake_advice_add()
            spec.handle(CLEANUP)

        self.assertIn(
            "indirect invocation of 'handle' by 'handle' is forbidden",
            s.getvalue())

    def test_spec_advice_no_infinite_pop(self):
        spec = Spec(counter=0)
        spec._advices[CLEANUP] = []

        def fake_advice_add():
            advice = (fake_advice_add, (), {})
            spec._advices[CLEANUP].append(advice)
            spec['counter'] += 1

        with pretty_logging(stream=StringIO()) as s:
            fake_advice_add()
            self.assertEqual(spec['counter'], 1)
            spec.handle(CLEANUP)
            # ensure that it only got called once.
            self.assertEqual(spec['counter'], 2)

        self.assertEqual(s.getvalue(), '')

        # this one can work without frame protection.
        stub_item_attr_value(
            self, calmjs_toolchain, 'currentframe', lambda: None)
        with pretty_logging(stream=StringIO()) as s:
            spec.handle(CLEANUP)
        self.assertEqual(spec['counter'], 4)
        self.assertIn(
            'currentframe() returned None; frame protection disabled',
            s.getvalue())

    # that's all the standard vectors I can cover, if someone wants to
    # attack this using somewhat more advanced/esoteric methods, I guess
    # they wanted an EXPLOSION.


class AdviceRegistryTestCase(unittest.TestCase):
    """
    Test case for management of registration for package specific extra
    advice steps for toolchain/spec execution.
    """

    def test_get_package_advices(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:Toolchain = calmjs.tests.test_toolchain:dummy\n'
            'calmjs.toolchain:Alt = calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        self.assertEqual(sorted(reg.get('example.package').keys()), [
            'calmjs.toolchain:Alt',
            'calmjs.toolchain:Toolchain',
        ])

    def test_not_toolchain_process(self):
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE)
        self.assertIsNone(
            reg.process_toolchain_spec_package(object(), Spec(), 'calmjs'))

    def test_standard_toolchain_process_nothing(self):
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE)
        toolchain = Toolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(toolchain, spec, 'calmjs')
        self.assertEqual(s.getvalue(), '')

    def test_standard_toolchain_process(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:Toolchain = calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        toolchain = Toolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(
                toolchain, spec, 'example.package')

        self.assertEqual(spec, {'dummy': ['dummy']})
        self.assertIn(
            "found advice setup steps registered for package "
            "'example.package' for toolchain 'calmjs.toolchain:Toolchain'",
            s.getvalue(),
        )

    def test_standard_toolchain_no_import_process(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:Toolchain = calmjs.tests.bad.import:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        toolchain = Toolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(
                toolchain, spec, 'example.package')

        self.assertIn(
            "ImportError: entry_point 'calmjs.toolchain:Toolchain",
            s.getvalue(),
        )

    def test_standard_toolchain_failure_process(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:Toolchain = calmjs.tests.test_toolchain:bad\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        toolchain = NullToolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(
                toolchain, spec, 'example.package')

        err = s.getvalue()
        # inheritance applies.
        self.assertIn(
            "found advice setup steps registered for package "
            "'example.package' for toolchain 'calmjs.toolchain:NullToolchain'",
            err,
        )
        self.assertIn("ERROR", err)
        self.assertIn(
            "failure encountered while setting up advices through entry_point",
            err)

        # partial execution will be done, so do test stuff.
        self.assertEqual(spec, {'dummy': ['dummy', 'bad']})

    def test_standard_toolchain_advice_extras(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        toolchain = NullToolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(
                toolchain, spec, 'example.package[a,bc,d]')
        self.assertEqual(spec['extras'], ['a', 'bc', 'd'])
        self.assertIn(
            "found advice setup steps registered for package "
            "'example.package[a,bc,d]' for toolchain ", s.getvalue()
        )

    def test_toolchain_advice_integration(self):
        reg = get(CALMJS_TOOLCHAIN_ADVICE)
        self.assertTrue(isinstance(reg, AdviceRegistry))


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

    def test_toolchain_call_standard_failure_advice(self):
        cleanup, success = [], []
        spec = Spec()
        spec.advise(CLEANUP, cleanup.append, True)
        spec.advise(SUCCESS, success.append, True)

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
                (u'transpile', u'transpile', u'transpiled'),)), msg)
        self.assertIn(
            ("aborting compile step %r due to existing key" % (
                (u'bundle', u'bundle', u'bundled'),)), msg)

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

    def test_null_transpiler_sourcemap(self):
        # a kind of silly test but shows concept
        tmpdir = mkdtemp(self)
        js_code = 'var dummy = function () {};\n'
        source = join(tmpdir, 'source.js')
        target = 'target.js'

        with open(source, 'w') as fd:
            fd.write(js_code)

        spec = Spec(build_dir=tmpdir, generate_source_map=True)
        modname = 'dummy'
        self.toolchain.transpile_modname_source_target(
            spec, modname, source, target)

        with open(join(tmpdir, target + '.map')) as fd:
            result = json.load(fd)

        self.assertEqual(result['mappings'], 'AAAA;')
        self.assertEqual(result['sources'], [source])
        self.assertEqual(result['file'], join(tmpdir, target))

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

    def test_toolchain_naming_modname_source_to_target(self):
        s = Spec()
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'example/module', '/tmp/example.module/src/example/module.js'),
            'example/module.js',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s,
            'example', '/tmp/example.module/src/example'),
            'example',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s,
            'example.module.js', '/tmp/example.module/src/example/module.js'),
            'example.module.js',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s,
            'template.tmpl', '/tmp/example.module/src/template.tmpl'),
            'template.tmpl',
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
                'bundle1': source_file,  # bundle as source file.
                'bundle2': bundle_dir,  # bundle as dir.
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
                'bundle2': 'bundle2',  # dir does NOT get appended.
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

    def test_null_toolchain_call_standard_success_advice(self):
        cleanup, success = [], []
        spec = Spec()
        spec.advise(CLEANUP, cleanup.append, True)
        spec.advise(SUCCESS, success.append, True)
        self.toolchain(spec)
        self.assertEqual(len(cleanup), 1)
        self.assertEqual(len(success), 1)

    def test_null_toolchain_no_advice(self):
        cleanup, success = [], []
        spec = Spec()
        spec.advise(CLEANUP, cleanup.append, True)
        spec.advise(SUCCESS, success.append, True)
        # no advices done through the private call
        self.toolchain._calf(spec)
        self.assertEqual(len(cleanup), 0)
        self.assertEqual(len(success), 0)

    def test_null_toolchain_all_advices(self):
        # These are ordered in the same order as they should be called
        stub_stdouts(self)
        advices = (
            BEFORE_PREPARE, AFTER_PREPARE, BEFORE_COMPILE, AFTER_COMPILE,
            BEFORE_ASSEMBLE, AFTER_ASSEMBLE, BEFORE_LINK, AFTER_LINK,
            BEFORE_FINALIZE, AFTER_FINALIZE, SUCCESS, CLEANUP,
        )
        spec = Spec()
        results = []
        for advice in advices:
            spec.advise(advice, results.append, advice)

        self.toolchain._calf(spec)
        self.assertEqual(len(results), 0)

        self.toolchain(spec)
        self.assertEqual(tuple(results), advices)

    def _check_toolchain_advice(
            self, advice, error, executed=[CLEANUP], **kw):
        advices = []
        spec = Spec(**kw)
        spec.advise(BEFORE_ASSEMBLE, advice)
        spec.advise(CLEANUP, advices.append, CLEANUP)
        spec.advise(SUCCESS, advices.append, SUCCESS)

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
            "an advice in group 'before_assemble' triggered an abort: "
            "forced abort", s.getvalue()
        )
        # ensure cleanup is executed regardless, and success is not.
        self.assertEqual(advices, executed)
        return s

    def test_null_toolchain_advice_abort(self):
        def abort():
            raise ToolchainAbort('forced abort')

        self._check_toolchain_advice(abort, True)

    def test_null_toolchain_advice_cancel(self):
        def cancel():
            raise ToolchainCancel('toolchain cancel')

        self._check_toolchain_advice(cancel, False)

    def test_null_toolchain_advice_abort_itself(self):
        def abort():
            raise AdviceAbort('advice abort')

        s = self._check_toolchain_advice(
            abort, False, executed=[SUCCESS, CLEANUP])
        self.assertIn('', s.getvalue())

        self.assertIn('raised an error', s.getvalue())
        self.assertIn('will continue', s.getvalue())
        self.assertIn('advice abort', s.getvalue())
        self.assertNotIn('showing traceback for error', s.getvalue())
        self.assertNotIn('Traceback', s.getvalue())
        self.assertNotIn('test_toolchain.py', s.getvalue())

        s = self._check_toolchain_advice(
            abort, False, executed=[SUCCESS, CLEANUP], debug=1)
        self.assertIn('showing traceback for error', s.getvalue())
        self.assertIn('Traceback', s.getvalue())
        self.assertIn('test_toolchain.py', s.getvalue())

    def test_null_toolchain_advice_cancel_itself(self):
        def cancel():
            raise AdviceCancel('advice cancel')

        s = self._check_toolchain_advice(
            cancel, False, executed=[SUCCESS, CLEANUP])
        self.assertIn('signaled its cancellation', s.getvalue())
        self.assertIn('advice cancel', s.getvalue())
        self.assertNotIn('showing traceback for cancellation', s.getvalue())
        self.assertNotIn('Traceback', s.getvalue())
        self.assertNotIn('test_toolchain.py', s.getvalue())

        s = self._check_toolchain_advice(
            cancel, False, executed=[SUCCESS, CLEANUP], debug=1)
        self.assertIn('showing traceback for cancellation', s.getvalue())
        self.assertIn('Traceback', s.getvalue())
        self.assertIn('test_toolchain.py', s.getvalue())

    def test_null_toolchain_advice_keyboard_interrupt(self):
        def interrupt():
            raise KeyboardInterrupt()

        self._check_toolchain_advice(interrupt, False)
