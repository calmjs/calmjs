# -*- coding: utf-8 -*-
import unittest
import logging
import json
import tempfile
import warnings
from collections import OrderedDict
from functools import partial
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
from calmjs.loaderplugin import LoaderPluginRegistry
from calmjs.loaderplugin import BaseLoaderPluginRegistry
from calmjs.loaderplugin import BaseLoaderPluginHandler

from calmjs.toolchain import CALMJS_TOOLCHAIN_ADVICE
from calmjs.toolchain import CALMJS_TOOLCHAIN_ADVICE_APPLY_SUFFIX
from calmjs.toolchain import AdviceRegistry
from calmjs.toolchain import AdviceApplyRegistry
from calmjs.toolchain import Spec
from calmjs.toolchain import Toolchain
from calmjs.toolchain import NullToolchain
from calmjs.toolchain import ES5Toolchain
from calmjs.toolchain import ToolchainSpecCompileEntry
from calmjs.toolchain import dict_setget
from calmjs.toolchain import dict_setget_dict
from calmjs.toolchain import dict_update_overwrite_check
from calmjs.toolchain import spec_update_sourcepath_filter_loaderplugins
from calmjs.toolchain import spec_update_loaderplugin_registry
from calmjs.toolchain import toolchain_spec_compile_entries
from calmjs.toolchain import toolchain_spec_prepare_loaderplugins

from calmjs.toolchain import SETUP
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

from calmjs.testing.mocks import WorkingSet
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


class DictSetGetTestCase(unittest.TestCase):
    """
    A special get that also creates keys.
    """

    def test_dict_setget(self):
        items = {}
        value = []
        dict_setget(items, 'a_key', value)
        self.assertIs(value, items['a_key'])
        other = []
        dict_setget(items, 'a_key', other)
        self.assertIsNot(other, items['a_key'])

    def test_dict_setget_dict(self):
        items = {}
        dict_setget_dict(items, 'a_key')
        self.assertEqual(items, {'a_key': {}})

        a_key = items['a_key']
        dict_setget_dict(items, 'a_key')
        self.assertIs(items['a_key'], a_key)


class DictUpdateOverwriteTestCase(unittest.TestCase):
    """
    A function for updating specific dict/spec via a key, and ensure
    that any overwritten values are warned with the specified message.
    """

    def test_dict_key_update_overwrite_check_standard(self):
        a = {'k1': 'v1'}
        b = {'k2': 'v2'}
        self.assertEqual([], dict_update_overwrite_check(a, b))
        self.assertEqual(a, {'k1': 'v1', 'k2': 'v2'})

    def test_dict_key_update_overwrite_check_no_update(self):
        a = {'k1': 'v1'}
        b = {'k1': 'v1'}
        self.assertEqual([], dict_update_overwrite_check(a, b))
        self.assertEqual(a, {'k1': 'v1'})

    def test_dict_key_update_overwrite_check_overwritten_single(self):
        a = {'k1': 'v1'}
        b = {'k1': 'v2'}
        self.assertEqual([
            ('k1', 'v1', 'v2'),
        ], dict_update_overwrite_check(a, b))
        self.assertEqual(a, {'k1': 'v2'})

    def test_dict_key_update_overwrite_check_overwritten_multi(self):
        a = {'k1': 'v1', 'k2': 'v2'}
        b = {'k1': 'v2', 'k2': 'v4'}
        self.assertEqual([
            ('k1', 'v1', 'v2'),
            ('k2', 'v2', 'v4'),
        ], sorted(dict_update_overwrite_check(a, b)))
        self.assertEqual(a, {'k1': 'v2', 'k2': 'v4'})


class SpecResolveRegistryTestCase(unittest.TestCase):

    def test_basic(self):
        spec = {}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec)
        self.assertTrue(isinstance(registry, BaseLoaderPluginRegistry))
        self.assertIn(
            'no loaderplugin registry referenced in spec', s.getvalue())
        self.assertIn('<default_loaderplugins>', s.getvalue())

    def test_default(self):
        spec = {}
        default = BaseLoaderPluginRegistry('my.default')
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec, default=default)
        self.assertIs(registry, default)
        self.assertIn(
            'no loaderplugin registry referenced in spec', s.getvalue())
        self.assertIn('my.default', s.getvalue())

        registries = {'my.default': default}
        stub_item_attr_value(
            self, calmjs_toolchain, 'get_registry', registries.get)
        spec = {}
        with pretty_logging(stream=StringIO()) as s:
            self.assertEqual('my.default', spec_update_loaderplugin_registry(
                spec, default='my.default').registry_name)

    def test_wrong(self):
        spec = {'calmjs_loaderplugin_registry': object()}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec)
        self.assertIn(
            "object referenced in spec is not a valid", s.getvalue())
        # still got the base instance instead.
        self.assertTrue(isinstance(registry, BaseLoaderPluginRegistry))

    def test_wrong_registry_type(self):
        advice = AdviceRegistry('adv', _working_set=WorkingSet({}))
        registries = {'adv': advice}
        stub_item_attr_value(
            self, calmjs_toolchain, 'get_registry', registries.get)

        spec = {'calmjs_loaderplugin_registry_name': 'adv'}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec)
        self.assertIn(
            "object referenced in spec is not a valid", s.getvalue())
        self.assertIsNot(registry, advice)
        self.assertTrue(isinstance(registry, BaseLoaderPluginRegistry))

        spec = {}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec, default='adv')
        self.assertIn(
            "provided default is not a valid loaderplugin registry",
            s.getvalue())
        self.assertIsNot(registry, advice)
        self.assertTrue(isinstance(registry, BaseLoaderPluginRegistry))

    def test_provided(self):
        spec = {'calmjs_loaderplugin_registry': LoaderPluginRegistry(
            'some.registry', _working_set=WorkingSet({})
        )}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec)
        self.assertIn(
            "loaderplugin registry 'some.registry' already assigned to spec",
            s.getvalue())
        self.assertTrue(isinstance(registry, LoaderPluginRegistry))

    def test_resolve_and_order(self):
        fake = LoaderPluginRegistry('fake_registry', _working_set=WorkingSet({
            'fake_registry': [
                'foo = calmjs.tests.test_toolchain:MockLPHandler']}))
        registries = {'fake_registry': fake}
        stub_item_attr_value(
            self, calmjs_toolchain, 'get_registry', registries.get)

        spec = {'calmjs_loaderplugin_registry_name': 'fake_registry'}
        with pretty_logging(stream=StringIO()) as s:
            registry = spec_update_loaderplugin_registry(spec)
        self.assertIn(
            "using loaderplugin registry 'fake_registry'", s.getvalue())
        self.assertIs(registry, fake)

        spec = {
            'calmjs_loaderplugin_registry_name': 'fake_registry',
            'calmjs_loaderplugin_registry': BaseLoaderPluginRegistry('raw'),
        }


class SpecUpdatePluginsSourcepathDictTestCase(unittest.TestCase):
    """
    A function for updating the spec with a sourcepath dict for target
    keys, in such a way that makes it compatible with the base system.
    """

    def test_standard_modules_base(self):
        sourcepath_dict = {
            'standard/module': 'standard/module',
            'standard.module': 'standard.module',
        }
        spec = {}
        spec_update_sourcepath_filter_loaderplugins(
            spec, sourcepath_dict, 'sourcepath_key', 'plugins_key')
        self.assertTrue(isinstance(spec.pop(
            'calmjs_loaderplugin_registry'), BaseLoaderPluginRegistry))
        self.assertEqual(spec, {
            'plugins_key': {},
            'sourcepath_key': {
                'standard/module': 'standard/module',
                'standard.module': 'standard.module',
            }
        })

    def test_standard_modules_id(self):
        sourcepath_dict = {
            'standard/module': 'standard/module',
        }
        base_map = {}
        spec = {'sourcepath_key': base_map}

        spec_update_sourcepath_filter_loaderplugins(
            spec, sourcepath_dict, 'sourcepath_key', 'plugins_key')
        self.assertTrue(isinstance(spec.pop(
            'calmjs_loaderplugin_registry'), BaseLoaderPluginRegistry))
        self.assertIs(spec['sourcepath_key'], base_map)
        self.assertEqual(base_map, {
            'standard/module': 'standard/module',
        })

    def test_various_modules(self):
        sourcepath_dict = {
            'plugin/module': 'path/to/plugin/module',
            'plugin/module!argument': 'some/filesystem/path',
            'plugin/module!css!argument': 'some/style/file.css',
            'text!argument': 'some/text/file.txt',
            'css?module!target.css': 'some/stylesheet/target.css',
            'css!main.css': 'some/stylesheet/main.css',
        }
        spec = {}

        spec_update_sourcepath_filter_loaderplugins(
            spec, sourcepath_dict, 'sourcepath_key', 'plugins_key')
        self.assertTrue(isinstance(spec.pop(
            'calmjs_loaderplugin_registry'), BaseLoaderPluginRegistry))
        self.assertEqual(spec, {
            'plugins_key': {
                'plugin/module': {
                    'plugin/module!argument': 'some/filesystem/path',
                    'plugin/module!css!argument': 'some/style/file.css',
                },
                'text': {
                    'text!argument': 'some/text/file.txt',
                },
                'css': {
                    'css?module!target.css': 'some/stylesheet/target.css',
                    'css!main.css': 'some/stylesheet/main.css',
                },
            },
            'sourcepath_key': {
                'plugin/module': 'path/to/plugin/module',
            },
        })

        # subsequent update will do update, not overwrite.
        spec_update_sourcepath_filter_loaderplugins(spec, {
            'text!argument2': 'some/text/file2.txt',
        }, 'sourcepath_key', 'plugins_key')

        self.assertEqual(spec['plugins_key']['text'], {
            'text!argument': 'some/text/file.txt',
            'text!argument2': 'some/text/file2.txt',
        })


class DeprecationTestCase(unittest.TestCase):
    """
    Various test cases to ensure successful deprecation.
    """

    def test_construction(self):
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                Spec(test_targets='/')

        self.assertIn(
            "Spec key 'test_targets' has been remapped to 'test_targetpaths' "
            "in calmjs-3.0.0;", str(w[-1].message)
        )
        self.assertIn(
            "Spec key 'test_targets' has been remapped to 'test_targetpaths' "
            "in calmjs-3.0.0;", s.getvalue()
        )

    def test_set(self):
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                spec = Spec()
                spec['test_source_map'] = '/'

        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", str(w[-1].message)
        )
        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", s.getvalue()
        )

    def test_get(self):
        spec = Spec(test_sourcepath='/')
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                self.assertEqual(spec.get('test_source_map', None), '/')
                self.assertEqual(spec.get('test_source_map'), '/')

        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", str(w[-1].message)
        )
        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", s.getvalue()
        )

    def test_getitem(self):
        spec = Spec(test_sourcepath='/')
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                self.assertEqual(spec['test_source_map'], '/')

        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", str(w[-1].message)
        )
        self.assertIn(
            "Spec key 'test_source_map' has been remapped to "
            "'test_sourcepath' in calmjs-3.0.0;", s.getvalue()
        )

    def test_generate_source_map(self):
        # this is an actual attribute
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                spec = Spec(generate_source_map=True)
                self.assertTrue(spec['generate_source_map'], '/')

        self.assertEqual(len(w), 0)
        self.assertEqual(s.getvalue(), '')

    def test_toolchain_attributes(self):
        # should really be read/write, but in generate these are not
        # set so...
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                toolchain = NullToolchain()
                # assert existing via old property, then set using old
                # property, to see it reflected in new.
                self.assertEqual(toolchain.sourcemap_suffix, '_sourcepath')
                toolchain.sourcemap_suffix = 'foo'
                self.assertEqual(toolchain.sourcepath_suffix, 'foo')

                self.assertEqual(toolchain.target_suffix, '_targetpaths')
                toolchain.target_suffix = 'foo'
                self.assertEqual(toolchain.targetpath_suffix, 'foo')

        self.assertIn(
            "sourcemap_suffix has been renamed to sourcepath_suffix",
            str(w[0].message)
        )
        self.assertEqual(len(w), 4)
        self.assertIn(
            "sourcemap_suffix has been renamed to sourcepath_suffix",
            s.getvalue()
        )
        self.assertIn(
            "target_suffix has been renamed to targetpath_suffix",
            s.getvalue()
        )


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

    def test_spec_advice_broken_no_traceback(self):
        spec = Spec()
        spec.advise(CLEANUP, fake_error(Exception))
        with pretty_logging(stream=StringIO()) as s:
            spec.handle(CLEANUP)
        self.assertNotIn('Traceback', s.getvalue())

    def test_spec_advice_broken_debug_traceback(self):
        spec = Spec(debug=1)
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
        working_set = pkg_resources.WorkingSet([])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        with pretty_logging(stream=StringIO()) as s:
            self.assertIsNone(
                reg.process_toolchain_spec_package(object(), Spec(), 'calmjs'))
        self.assertIn(
            "apply_toolchain_spec or process_toolchain_spec_package must be "
            "invoked with a toolchain instance, not <object",
            s.getvalue(),
        )

    def test_standard_toolchain_process_nothing(self):
        working_set = pkg_resources.WorkingSet([])
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE, _working_set=working_set)
        toolchain = Toolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(toolchain, spec, 'calmjs')
        self.assertIn(
            "no advice setup steps registered for package/requirement "
            "'calmjs'", s.getvalue(),
        )

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

        self.assertEqual(spec['dummy'], ['dummy'])
        self.assertIn(
            "found advice setup steps registered for package/requirement "
            "'example.package'; checking for compatibility with toolchain "
            "'calmjs.toolchain:Toolchain'",
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
            "found advice setup steps registered for package/requirement "
            "'example.package'; checking for compatibility with toolchain "
            "'calmjs.toolchain:NullToolchain'", err,
        )
        self.assertIn("ERROR", err)
        self.assertIn(
            "failure encountered while setting up advices through entry_point",
            err)

        # partial execution will be done, so do test stuff.
        self.assertEqual(spec['dummy'], ['dummy', 'bad'])
        self.assertEqual(spec['advice_packages_applied_requirements'], [
            pkg_resources.Requirement.parse('example.package')])

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
            "found advice setup steps registered for package/requirement "
            "'example.package[a,bc,d]'", s.getvalue()
        )
        self.assertIn(
            "entry_point 'calmjs.toolchain:NullToolchain = "
            "calmjs.tests.test_toolchain:dummy' registered by advice package "
            "'example.package[a,bc,d]' applied as an advice setup step by "
            "calmjs.toolchain:AdviceRegistry 'calmjs.toolchain.advice'",
            s.getvalue()
        )
        self.assertEqual(spec['advice_packages_applied_requirements'], [
            pkg_resources.Requirement.parse('example.package[a,bc,d]')])

    def test_standard_toolchain_advice_malformed(self):
        reg = AdviceRegistry(CALMJS_TOOLCHAIN_ADVICE)
        toolchain = Toolchain()
        spec = Spec()
        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(toolchain, spec, 'calmjs:thing')
        self.assertIn(
            "the specified value 'calmjs:thing' for advice setup is not valid",
            s.getvalue(),
        )
        self.assertNotIn('advice_packages_applied_requirements', spec)

        spec = Spec()
        spec['advice_packages'] = ['calmjs:thing']
        with pretty_logging(stream=StringIO()) as s:
            reg.apply_toolchain_spec(toolchain, spec)
        self.assertIn(
            "the specified value 'calmjs:thing' for advice setup is not valid",
            s.getvalue(),
        )
        self.assertNotIn('advice_packages_applied_requirements', spec)

    def test_apply_toolchain_spec_apply_incompatible_toolchain(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[demo.registry]\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceRegistry('demo.registry', _working_set=working_set)
        # Step registered for NullToolchain
        toolchain = Toolchain()
        spec = Spec()
        spec['advice_packages'] = ['example.package']

        with pretty_logging(stream=StringIO()) as s:
            reg.apply_toolchain_spec(toolchain, spec)

        self.assertIn(
            "'example.package'; checking for compatibility with toolchain "
            "'calmjs.toolchain:Toolchain'", s.getvalue(),
        )
        self.assertIn("no compatible advice setup steps found", s.getvalue())
        # also verify the warning log entry when missing .apply registry
        self.assertIn(
            "registry key 'demo.registry.apply' resulted in None which is not "
            "a valid advice apply registry; no package level advice apply "
            "steps will be applied", s.getvalue()
        )

    def test_apply_toolchain_spec_multiple_specified(self):
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
        spec['advice_packages'] = [
            'example.package[foo]', 'example.package[bar]']

        with pretty_logging(stream=StringIO()) as s:
            reg.apply_toolchain_spec(toolchain, spec)

        self.assertIn(
            "entry_point 'calmjs.toolchain:NullToolchain = "
            "calmjs.tests.test_toolchain:dummy' registered by advice package "
            "'example.package[foo]' applied as an advice setup step by "
            "calmjs.toolchain:AdviceRegistry 'calmjs.toolchain.advice'",
            s.getvalue(),
        )
        self.assertIn(
            "entry_point 'calmjs.toolchain:NullToolchain = "
            "calmjs.tests.test_toolchain:dummy' registered by advice package "
            "'example.package[bar]' applied as an advice setup step by "
            "calmjs.toolchain:AdviceRegistry 'calmjs.toolchain.advice'",
            s.getvalue(),
        )
        self.assertIn(
            "advice package 'example.package[bar]' was previously applied as "
            "'example.package[foo]'; the recommended usage manner is to only "
            "specify any given advice package once complete with all the "
            "required extras, and that underlying implementation be "
            "structured in a manner that support this one-shot invocation "
            "format", s.getvalue(),
        )
        self.assertEqual(spec['advice_packages_applied_requirements'], [
            pkg_resources.Requirement.parse('example.package[foo]'),
            pkg_resources.Requirement.parse('example.package[bar]'),
        ])

        # applying again, will trigger the warning showing that was blocked
        with pretty_logging(stream=StringIO(), level=logging.WARNING) as s:
            reg.apply_toolchain_spec(toolchain, spec)

        self.assertIn(
            "advice package 'example.package[foo]' already applied as "
            "'example.package[bar]'; skipping", s.getvalue(),
        )
        self.assertIn(
            "advice package 'example.package[bar]' already applied as "
            "'example.package[bar]'; skipping", s.getvalue(),
        )
        # show that no additional application was done.
        self.assertEqual(2, len(spec['advice_packages_applied_requirements']))
        # manual step will still increase it
        with pretty_logging(stream=StringIO()):
            reg.process_toolchain_spec_package(
                toolchain, spec, 'example.package[bar]')
        self.assertEqual(3, len(spec['advice_packages_applied_requirements']))

    def test_apply_spec_toolchain_not_installed(self):
        reg = AdviceRegistry('demo.advice', _working_set=WorkingSet({}))
        toolchain = NullToolchain()
        spec = Spec()

        with pretty_logging(stream=StringIO()) as s:
            reg.process_toolchain_spec_package(toolchain, spec, 'example')

        self.assertIn(
            "advice setup steps required from package/requirement 'example', "
            "however it is not found or not installed in this environment",
            s.getvalue()
        )

    def test_apply_spec_toolchain_override_apply(self):
        from calmjs.registry import _inst as root_registry

        self.addCleanup(root_registry.records.pop, 'demo.advice', None)
        self.addCleanup(root_registry.records.pop, 'demo.advice.apply', None)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[demo.advice]\n'
            'calmjs.toolchain:NullToolchain'
            ' = calmjs.testing.spec:advice_marker\n'
            '\n'
            '[demo.advice.apply]\n'
            'example.package = example.package[main]\n'
        ),), 'example.package', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[demo.advice.apply]\n'
            'example.package = example.package[other]\n'
        ),), 'example.other_package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        reg = root_registry.records['demo.advice'] = AdviceRegistry(
            'demo.advice', _working_set=working_set)
        root_registry.records['demo.advice.apply'] = AdviceApplyRegistry(
            'demo.advice.apply', _working_set=working_set)

        toolchain = NullToolchain()
        spec = Spec(
            advice_packages=['example.package[manual]'],
            source_package_names=['example.package', 'example.other_package'],
        )

        with pretty_logging(stream=StringIO()) as s:
            reg.apply_toolchain_spec(toolchain, spec)

        self.assertIn(
            "invoking apply_toolchain_spec using instance of "
            "calmjs.toolchain:AdviceRegistry named 'demo.advice'",
            s.getvalue(),
        )
        self.assertIn(
            "skipping specified advice package 'example.package[main]' as "
            "'example.package[manual]' was already applied", s.getvalue(),
        )
        self.assertIn(
            "skipping specified advice package 'example.package[other]' as "
            "'example.package[manual]' was already applied", s.getvalue(),
        )
        self.assertEqual(spec['advice_packages_applied_requirements'], [
            pkg_resources.Requirement.parse('example.package[manual]'),
        ])

    def test_toolchain_advice_integration(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[demo.advice]\n'
            'calmjs.toolchain:NullToolchain'
            ' = calmjs.testing.spec:advice_marker\n'
            '\n'
            '[demo.advice.apply]\n'
            'example.package = example.package[main]\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        stub_item_attr_value(self, calmjs_toolchain, 'get_registry', {
            'demo.advice': AdviceRegistry(
                'demo.advice', _working_set=working_set),
            'demo.advice.apply': AdviceApplyRegistry(
                'demo.advice.apply', _working_set=working_set),
        }.get)

        toolchain = NullToolchain()
        spec = Spec(source_package_names=['example.package'])
        with pretty_logging(stream=StringIO()) as s:
            toolchain.setup_apply_advice_packages(spec)

        self.assertIn(
            "registry key 'calmjs.toolchain.advice' resulted in None which is "
            "not a valid advice registry; all package advice steps will be "
            "skipped",
            s.getvalue(),
        )
        self.assertNotIn('advice_packages_applied_requirements', spec)

        spec = Spec(
            source_package_names=['example.package'],
            calmjs_toolchain_advice_registry='demo.advice',
        )
        with pretty_logging(stream=StringIO()) as s:
            toolchain.setup_apply_advice_packages(spec)

        self.assertIn(
            "setting up advices using calmjs.toolchain:AdviceRegistry "
            "'demo.advice'",
            s.getvalue(),
        )
        self.assertNotIn(spec['advice_packages_applied_requirements'], [
            pkg_resources.Requirement.parse('example.package[main]'),
        ])

    def test_toolchain_advice_registry_registration(self):
        reg = get(CALMJS_TOOLCHAIN_ADVICE)
        self.assertTrue(isinstance(reg, AdviceRegistry))
        reg = get(
            CALMJS_TOOLCHAIN_ADVICE + CALMJS_TOOLCHAIN_ADVICE_APPLY_SUFFIX)
        self.assertTrue(isinstance(reg, AdviceApplyRegistry))


class AdviceApplyRegistryTestCase(unittest.TestCase):

    def test_get_record_key_normalised(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice.apply]\n'
            'example = example.advice[extra]\n'
        ),), 'example_namespace_package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        reg = AdviceApplyRegistry(
            CALMJS_TOOLCHAIN_ADVICE + CALMJS_TOOLCHAIN_ADVICE_APPLY_SUFFIX,
            _working_set=working_set
        )
        # key will be normalized
        record = reg.get_record('example-namespace-package')
        self.assertEqual(1, len(record))
        self.assertEqual(
            pkg_resources.Requirement.parse('example.advice[extra]'),
            record[0],
        )

    def test_manual_registration(self):
        reg = AdviceApplyRegistry('demo', _working_set=WorkingSet({}))
        entry_point = pkg_resources.EntryPoint.parse('key = value[extra]')
        entry_point.dist = pkg_resources.Distribution(
            project_name='package', version='1.0')
        with pretty_logging(stream=StringIO()) as s:
            reg._init_entry_point(entry_point)
        record = reg.get_record('package')
        self.assertEqual(1, len(record))
        self.assertEqual(
            pkg_resources.Requirement.parse('value[extra]'), record[0])
        self.assertEqual(s.getvalue(), '')

    def test_manual_incomplete_entry_point(self):
        reg = AdviceApplyRegistry('demo', _working_set=WorkingSet({}))
        with pretty_logging(stream=StringIO()) as s:
            reg._init_entry_point(
                pkg_resources.EntryPoint.parse('package = demo[extra]'))
        self.assertEqual(0, len(reg.records))
        self.assertIn('must provide a distribution', s.getvalue())

    def test_incompatible_entry_point(self):
        # one that is not compatible for use as a requirement.
        with pretty_logging(stream=StringIO()) as s:
            reg = AdviceApplyRegistry('demo', _working_set=WorkingSet({
                'demo': [
                    'example1 = some.package:welp[foo]',
                ],
            }, dist=pkg_resources.Distribution(project_name='package')))
        self.assertIn(
            'cannot be registered to calmjs.toolchain:AdviceApplyRegistry '
            'due to the following error:', s.getvalue())
        # this one actually does have a record, but without entries.
        self.assertEqual([], reg.get_record('package'))


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
        self.assertEqual(spec['transpiled_targetpaths'], {})
        self.assertEqual(spec['bundled_targetpaths'], {})
        self.assertEqual(spec['export_module_names'], [])

    def test_toolchain_standard_compile_existing_values(self):
        # Test that in the case where existing path dicts will block,
        # and the existing module_names will be kept
        transpiled_modpaths = {}
        bundled_modpaths = {}
        transpiled_targetpaths = {}
        bundled_targetpaths = {}
        export_module_names = ['fake_names']
        spec = Spec(
            transpiled_modpaths=transpiled_modpaths,
            bundled_modpaths=bundled_modpaths,
            transpiled_targetpaths=transpiled_targetpaths,
            bundled_targetpaths=bundled_targetpaths,
            export_module_names=export_module_names,
        )

        with pretty_logging(stream=StringIO()) as s:
            self.toolchain.compile(spec)

        msg = s.getvalue()
        self.assertIn("attempted to write 'transpiled_modpaths' to spec", msg)
        self.assertIn("attempted to write 'bundled_modpaths' to spec", msg)
        # These are absent due to early abort
        self.assertNotIn("attempted to write 'transpiled_targetpaths'", msg)
        self.assertNotIn("attempted to write 'bundled_targetpaths'", msg)

        # compile step error messages
        self.assertIn(
            ("aborting compile step %r due to existing key" % (
                self.toolchain.compile_entries[0],)), msg)
        self.assertIn(
            ("aborting compile step %r due to existing key" % (
                self.toolchain.compile_entries[1],)), msg)

        # All should be same identity
        self.assertIs(spec['transpiled_modpaths'], transpiled_modpaths)
        self.assertIs(spec['bundled_modpaths'], bundled_modpaths)
        self.assertIs(spec['transpiled_targetpaths'], transpiled_targetpaths)
        self.assertIs(spec['bundled_targetpaths'], bundled_targetpaths)
        self.assertIs(spec['export_module_names'], export_module_names)

    def test_toolchain_standard_compile_existing_values_altarnate(self):
        # Test that in the case where existing path maps will block, and
        # the existing export_module_names will be kept
        transpiled_targetpaths = {}
        bundled_targetpaths = {}
        spec = Spec(
            transpiled_targetpaths=transpiled_targetpaths,
            bundled_targetpaths=bundled_targetpaths,
        )

        with pretty_logging(stream=StringIO()) as s:
            self.toolchain.compile(spec)

        msg = s.getvalue()
        # These are filtered first
        self.assertIn(
            "attempted to write 'transpiled_targetpaths' to spec but key "
            "already exists; not overwriting, skipping", msg)
        self.assertIn(
            "attempted to write 'bundled_targetpaths' to spec but key already "
            "exists; not overwriting, skipping", msg)

        # These first couple won't be written since code never hit it
        self.assertNotIn('transpiled_modpaths', spec)
        self.assertNotIn('bundled_modpaths', spec)
        self.assertIs(spec['bundled_targetpaths'], bundled_targetpaths)
        self.assertIs(spec['transpiled_targetpaths'], transpiled_targetpaths)

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
        self.assertNotIn('transpiled_targetpaths', spec)
        self.assertNotIn('bundled_targetpaths', spec)
        self.assertEqual(spec['faked_modpaths'], {'fake': 'nothing'})
        self.assertEqual(spec['faked_targetpaths'], {'fake': 'nothing.js'})
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
        self.assertNotIn('transpiled_targetpaths', spec)
        self.assertNotIn('bundled_targetpaths', spec)

    def test_toolchain_standard_compile_alternate_entries_called(self):
        added = []

        class CustomToolchain(Toolchain):
            def build_compile_entries(self):
                return (('here', 'fake', 'faked'),)

            def compile_here(self, spec, entries):
                added.extend(list(entries))
                return {'here': 'mod'}, {'here': 'target'}, ['here']

        # Again, this is not the right way, should subclass/define a new
        # build_compile_entries method.
        custom_toolchain = CustomToolchain()
        spec = Spec(fake_sourcepath={'here': 'source'})

        with pretty_logging(stream=StringIO()) as s:
            custom_toolchain.compile(spec)

        msg = s.getvalue()
        self.assertNotIn("'here' not a callable attribute for", msg)

        self.assertNotIn('transpiled_modpaths', spec)
        self.assertNotIn('bundled_modpaths', spec)
        self.assertNotIn('transpiled_targetpaths', spec)
        self.assertNotIn('bundled_targetpaths', spec)

        self.assertEqual([('here', 'source', 'here', 'here')], added)
        self.assertEqual({'here': 'mod'}, spec['faked_modpaths'])
        self.assertEqual({'here': 'target'}, spec['faked_targetpaths'])
        self.assertEqual(['here'], spec['export_module_names'])

    def test_toolchain_spec_compile_entry_logging(self):
        # this test constructs a situation where the individual compile
        # entry methods are capable of generating the paths with
        # duplicated modnames (keys) - could be unusual, and
        # implementations may use the extended attributes in the
        # ToolchainSpecCompileEntry to trigger logging.

        class CustomToolchain(Toolchain):
            def build_compile_entries(self):
                return [
                    ToolchainSpecCompileEntry('silent', 'silent', 'silented'),
                    ToolchainSpecCompileEntry(
                        'logged', 'log', 'logged',
                        'calmjs_testing', logging.WARNING,
                    ),
                ]

            def compile_silent_entry(self, spec, entry):
                modname, source, target, modpath = entry
                return {'module': modpath}, {'module': source}, ['module']

            def compile_logged_entry(self, spec, entry):
                modname, source, target, modpath = entry
                return {'module': modpath}, {'module': source}, ['module']

        custom_toolchain = CustomToolchain()
        spec = Spec(
            silent_sourcepath=OrderedDict([
                ('original', 'original'),
                ('silent', 'silent'),
            ]),
            log_sourcepath=OrderedDict([
                ('original', 'static'),
                ('log', 'static'),
                ('final', 'changed'),
            ]),
        )

        with pretty_logging(logger='calmjs_testing', stream=StringIO()) as s:
            custom_toolchain.compile(spec)

        msg = s.getvalue()
        self.assertNotIn(
            "silented_modpaths['module'] is being rewritten from "
            "'original' to 'silent'", msg
        )
        self.assertNotIn(
            "silented_targetpaths['module'] is being rewritten from "
            "'original' to 'silent'", msg
        )

        self.assertIn(
            "logged_modpaths['module'] is being rewritten from "
            "'original' to 'log'", msg
        )
        self.assertNotIn(
            "logged_targetpaths['module'] is being rewritten from "
            "'static' to 'static'", msg
        )
        self.assertIn(
            "logged_targetpaths['module'] is being rewritten from "
            "'static' to 'changed'", msg
        )

        self.assertEqual({
            'module': 'silent',
        }, spec['silented_modpaths'])
        self.assertEqual({
            'module': 'silent',
        }, spec['silented_targetpaths'])
        self.assertEqual({
            'module': 'final',
        }, spec['logged_modpaths'])
        self.assertEqual({
            'module': 'changed',
        }, spec['logged_targetpaths'])

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
        with pretty_logging(stream=StringIO()) as s:
            with self.assertRaises(OSError):
                # well, dir does not exist
                self.toolchain(spec)

        # Manually specified build_dirs do not get modified if they just
        # simply don't exist.
        self.assertEqual(spec['build_dir'], not_exist)
        self.assertIn(not_exist, s.getvalue())
        self.assertIn("is not a directory", s.getvalue())

    def test_toolchain_standard_build_dir_set_not_dir(self):
        spec = Spec()
        some_file = join(mkdtemp(self), 'some_file')

        with open(some_file, 'w'):
            pass

        spec['build_dir'] = some_file
        with pretty_logging(stream=StringIO()) as s:
            with self.assertRaises(OSError):
                # well, dir is not a dir.
                self.toolchain(spec)

        self.assertEqual(spec['build_dir'], some_file)
        self.assertIn(some_file, s.getvalue())
        self.assertIn("is not a directory", s.getvalue())

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

        self.assertIn("realpath of 'build_dir' resolved to", s.getvalue())
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
            transpile_sourcepath={
                # lol ``.`` being valid char for namespace in node
                '../source': join(source, 'source'),
            },
        )
        with pretty_logging(stream=StringIO()) as s:
            with warnings.catch_warnings(record=True):
                with self.assertRaises(ValueError):
                    self.toolchain(spec)

        self.assertIn(
            "transpiler callable assigned to",
            s.getvalue(),
        )

    def test_toolchain_compile_bundle_entry(self):
        """
        Test out the compile_bundle_entry being flexible in handling the
        different cases of paths.
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

        compile_bundle = partial(
            toolchain_spec_compile_entries, self.toolchain,
            process_name='bundle')

        compile_bundle(spec, [
            ('mod1', src, target1, 'mod1'),
            ('mod2', src, target2, 'mod2'),
            ('mod3', src, target3, 'mod3'),
            ('mod4', src, target4, 'mod4'),
        ])

        self.assertTrue(exists(join(build_dir, target1)))
        self.assertTrue(exists(join(build_dir, target2)))
        self.assertTrue(exists(join(build_dir, target3)))
        self.assertTrue(exists(join(build_dir, target4)))

    def test_toolchain_setup_advice_abort_does_cleanup(self):
        spec = Spec()

        def abort(*a, **kw):
            raise ToolchainAbort()

        spec.advise(SETUP, abort)
        with pretty_logging(stream=StringIO()):
            with self.assertRaises(ToolchainAbort):
                self.toolchain(spec)
        self.assertFalse(exists(spec.get('build_dir')))


class MockLPHandler(BaseLoaderPluginHandler):

    def __call__(self, toolchain, spec, modname, source, target, modpath):
        return {modname: target}, {modname: modpath}, [modname]

    def generate_handler_sourcepath(self, toolchain, spec, value):
        return {self.name: self.name}


class ToolchainLoaderPluginTestCase(unittest.TestCase):

    def setUp(self):
        self.toolchain = Toolchain()

    def test_toolchain_compile_loaderplugin_entry_empty(self):
        """
        A rough standalone test for handling of loader plugins.
        """

        spec = Spec()
        with self.assertRaises(KeyError):
            # as the registry is not in the spec
            self.toolchain.compile_loaderplugin_entry(spec, (
                'foo!target.txt', 'foo', 'foo!target.txt', 'foo!target.txt'))

    def test_toolchain_compile_loaderplugin_entry_not_found(self):
        """
        A rough standalone test for handling of loader plugins.
        """

        src_dir = mkdtemp(self)
        src = join(src_dir, 'target.txt')
        spec = Spec(calmjs_loaderplugin_registry={})
        with pretty_logging(stream=StringIO()) as s:
            results = self.toolchain.compile_loaderplugin_entry(spec, (
                'foo!target.txt', src, 'foo!target.txt', 'foo!target.txt'))
        self.assertIn(
            "no loaderplugin handler found for plugin entry 'foo!target.txt'",
            s.getvalue())
        self.assertEqual(({}, {}, []), results)

    def test_toolchain_compile_loaderplugin_entry_registered(self):
        """
        A rough standalone test for handling of loader plugins.
        """

        reg = LoaderPluginRegistry('simple', _working_set=WorkingSet({
            'simple': [
                'foo = calmjs.tests.test_toolchain:MockLPHandler',
                'bar = calmjs.tests.test_toolchain:MockLPHandler',
            ],
        }))

        src_dir = mkdtemp(self)
        src = join(src_dir, 'target.txt')

        spec = Spec(calmjs_loaderplugin_registry=reg)
        with pretty_logging(stream=StringIO()) as s:
            bar_results = self.toolchain.compile_loaderplugin_entry(spec, (
                'bar!target.txt', src, 'bar!target.txt', 'bar!target.txt'))
            foo_results = self.toolchain.compile_loaderplugin_entry(spec, (
                'foo!target.txt', src, 'foo!target.txt', 'foo!target.txt'))

        self.assertEqual('', s.getvalue())

        self.assertEqual((
            {'foo!target.txt': 'foo!target.txt'},
            {'foo!target.txt': 'foo!target.txt'},
            ['foo!target.txt'],
        ), foo_results)

        self.assertEqual((
            {'bar!target.txt': 'bar!target.txt'},
            {'bar!target.txt': 'bar!target.txt'},
            ['bar!target.txt'],
        ), bar_results)

        # recursive lookups are generally not needed, if the target
        # supplied _is_ the target.

    def test_toolchain_spec_prepare_loaderplugins_unsupported(self):
        spec = Spec()
        # really though, providing None shouldn't be supported, but
        # leaving this in for now until it is formalized.
        toolchain_spec_prepare_loaderplugins(
            self.toolchain, spec, 'plugin', None)
        self.assertIn('plugin_sourcepath', spec)

    def test_toolchain_spec_prepare_loaderplugins_standard(self):
        reg = LoaderPluginRegistry('simple', _working_set=WorkingSet({
            'simple': [
                'foo = calmjs.tests.test_toolchain:MockLPHandler',
                'bar = calmjs.tests.test_toolchain:MockLPHandler',
            ],
        }))
        spec = Spec(
            calmjs_loaderplugin_registry=reg,
            loaderplugin_sourcepath_maps={
                'foo': {'foo!thing': 'thing'},
                'bar': {'bar!thing': 'thing'},
            },
        )
        toolchain_spec_prepare_loaderplugins(
            self.toolchain, spec, 'loaderplugin', 'loaders')
        self.assertEqual({
            'foo!thing': 'thing',
            'bar!thing': 'thing',
        }, spec['loaderplugin_sourcepath'])
        self.assertEqual({
            'foo': 'foo',
            'bar': 'bar',
        }, spec['loaders'])

    def test_toolchain_spec_prepare_loaderplugins_missing(self):
        reg = LoaderPluginRegistry('simple', _working_set=WorkingSet({
            'simple': [
                'foo = calmjs.tests.test_toolchain:MockLPHandler',
                'bar = calmjs.tests.test_toolchain:MockLPHandler',
            ],
        }))
        spec = Spec(
            calmjs_loaderplugin_registry=reg,
            loaderplugin_sourcepath_maps={
                'foo': {'foo!thing': 'thing'},
                'missing': {'missing!thing': 'thing'},
                'bar': {'bar!thing': 'thing'},
            },
        )
        with pretty_logging(stream=StringIO()) as s:
            toolchain_spec_prepare_loaderplugins(
                self.toolchain, spec, 'loaderplugin', 'loaders')
        self.assertEqual({
            'foo!thing': 'thing',
            'bar!thing': 'thing',
        }, spec['loaderplugin_sourcepath'])
        self.assertEqual({
            'foo': 'foo',
            'bar': 'bar',
        }, spec['loaders'])

        self.assertIn(
            "loaderplugin handler for 'missing' not found in loaderplugin "
            "registry 'simple'", s.getvalue())
        self.assertIn(
            "will not be compiled into the build target: ['missing!thing']",
            s.getvalue())


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

    def test_toolchain_naming_modname_source_to_target_loaderplugin(self):
        s = Spec(calmjs_loaderplugin_registry=LoaderPluginRegistry(
            'simloaders', _working_set=WorkingSet({'simloaders': [
                'foo = calmjs.loaderplugin:LoaderPluginHandler',
                'bar = calmjs.loaderplugin:LoaderPluginHandler',
                'py/loader = calmjs.loaderplugin:LoaderPluginHandler',
            ]})
        ))
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'example/module', '/tmp/example.module/src/example/module.js'),
            'example/module.js',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'foo!example/module.txt', '/tmp/example.module/src/example'),
            'example/module.txt',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'foo!bar!module.txt', '/tmp/example.module/src/example'),
            'module.txt',
        )
        # baz not handled.
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'foo!baz!bar!module.txt', '/tmp/example.module/src/example'),
            'baz!bar!module.txt',
        )
        # python provided loaders
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'py/module', '/tmp/py.module/py/module.js'),
            'py/module.js',
        )
        self.assertEqual(self.toolchain.modname_source_to_target(
            s, 'py/loader', '/tmp/py.module/py/loader.js'),
            'py/loader.js',
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
            transpile_sourcepath={
                'namespace.dummy.source': source_file,
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'transpile_sourcepath': {
                'namespace.dummy.source': source_file,
            },

            'bundled_modpaths': {},
            'bundled_targetpaths': {},
            'transpiled_modpaths': {
                'namespace.dummy.source': 'namespace.dummy.source',
            },
            'transpiled_targetpaths': {
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
            bundle_sourcepath={
                'bundle1': source_file,  # bundle as source file.
                'bundle2': bundle_dir,  # bundle as dir.
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'bundle_sourcepath': {
                'bundle1': source_file,
                'bundle2': bundle_dir,
            },

            'bundled_modpaths': {
                'bundle1': 'bundle1',
                'bundle2': 'bundle2',
            },
            'bundled_targetpaths': {
                'bundle1': 'bundle1.js',
                'bundle2': 'bundle2',  # dir does NOT get appended.
            },
            'transpiled_modpaths': {},
            'transpiled_targetpaths': {},
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
            transpile_sourcepath={
                'namespace/dummy/source': source_file,
            },
        )
        self.toolchain(spec)

        # name, and relative filename to the build_path
        self.assertEqual(spec, {
            'build_dir': build_dir,
            'transpile_sourcepath': {
                'namespace/dummy/source': source_file,
            },

            'bundled_modpaths': {},
            'bundled_targetpaths': {},
            'transpiled_modpaths': {
                'namespace/dummy/source': 'namespace/dummy/source',
            },
            'transpiled_targetpaths': {
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

        self.assertIn('encountered a known error', s.getvalue())
        self.assertIn('continuing with toolchain execution', s.getvalue())
        self.assertIn('advice abort', s.getvalue())
        self.assertNotIn('showing traceback for error', s.getvalue())
        self.assertNotIn('Traceback', s.getvalue())
        self.assertNotIn('test_toolchain.py', s.getvalue())

        s = self._check_toolchain_advice(
            abort, False, executed=[SUCCESS, CLEANUP], debug=1)
        self.assertIn('showing traceback for error', s.getvalue())
        self.assertIn('Traceback', s.getvalue())
        self.assertIn('test_toolchain.py', s.getvalue())

    def test_null_toolchain_advice_blew_up(self):
        def die():
            raise Exception('desu')

        s = self._check_toolchain_advice(
            die, False, executed=[SUCCESS, CLEANUP])
        self.assertIn('', s.getvalue())

        self.assertIn(
            'terminated due to an unexpected exception', s.getvalue())
        self.assertIn('desu', s.getvalue())
        self.assertNotIn('showing traceback for error', s.getvalue())
        self.assertNotIn('Traceback', s.getvalue())
        self.assertNotIn('test_toolchain.py', s.getvalue())

        s = self._check_toolchain_advice(
            die, False, executed=[SUCCESS, CLEANUP], debug=1)
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


class ES5ToolchainTestCase(unittest.TestCase):
    """
    A null toolchain class test case.
    """

    def setUp(self):
        self.toolchain = ES5Toolchain()

    def tearDown(self):
        pass

    def test_transpiler(self):
        # a kind of silly test but shows concept
        tmpdir = mkdtemp(self)
        js_code = 'var dummy = function() {\n};\n'
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
        self.assertFalse(exists(join(tmpdir, target + '.map')))

    def test_transpiler_sourcemap(self):
        # a kind of silly test but shows concept
        build_dir = mkdtemp(self)
        srcdir = mkdtemp(self)
        js_code = 'var dummy = function() {\n};\n'
        source = join(srcdir, 'source.js')
        target = 'target.js'

        with open(source, 'w') as fd:
            fd.write(js_code)

        spec = Spec(build_dir=build_dir, generate_source_map=True)
        modname = 'dummy'
        self.toolchain.transpile_modname_source_target(
            spec, modname, source, target)

        with open(join(build_dir, target + '.map')) as fd:
            result = json.load(fd)

        self.assertEqual(result['mappings'], 'AAAA;AACA;')
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(basename(result['sources'][0]), 'source.js')
        self.assertEqual(result['file'], target)
