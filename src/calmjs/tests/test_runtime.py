# -*- coding: utf-8 -*-
import unittest
import json
import os
import sys
import warnings
from argparse import ArgumentParser
from inspect import currentframe
from os.path import join
from os.path import exists
from logging import DEBUG
from logging import INFO
from logging import WARNING
from types import ModuleType

import pkg_resources

from calmjs import argparse as calmjs_argparse
from calmjs import cli
from calmjs import dist
from calmjs import exc
from calmjs import runtime
from calmjs import toolchain
from calmjs.utils import pretty_logging
from calmjs.utils import which

from calmjs.testing import mocks
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import stub_item_attr_value
from calmjs.testing.utils import stub_base_which
from calmjs.testing.utils import stub_check_interactive
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_os_environ
from calmjs.testing.utils import stub_stdin
from calmjs.testing.utils import stub_stdouts

which_npm = which('npm')


class BrokenRuntime(runtime.DriverRuntime):

    def init_argparser(self, argparser):
        raise ImportError('a fake import error')


broken = BrokenRuntime(None)


class DeprecatedRuntime(runtime.DriverRuntime):

    def init_argparser(self, argparser):
        warnings.warn("this runtime is deprecated", DeprecationWarning)


deprecated = DeprecatedRuntime(None)


class DefaultCommandRuntime(runtime.Runtime):

    def __init__(
            self, entry_point_group='broken.test', action_key='broken_test',
            *a, **kw):
        super(DefaultCommandRuntime, self).__init__(
            entry_point_group=entry_point_group, action_key=action_key,
            *a, **kw)

    def init_argparser(self, argparser):
        argparser.add_argument(
            '--valid', action='store_true', required=False)
        return super(DefaultCommandRuntime, self).init_argparser(argparser)


dummy = runtime.DriverRuntime(None)
default_cmd = DefaultCommandRuntime(working_set=mocks.WorkingSet({
    'broken.test': [
        'dummy = calmjs.tests.test_runtime:dummy',
    ],
}))


class BaseRuntimeTestCase(unittest.TestCase):

    def tearDown(self):
        runtime._reset_global_runtime_attrs()

    def test_base_version(self):
        # The version information should be missing but shouldn't result
        # in catastrophic errors.
        stub_stdouts(self)
        rt = runtime.BaseRuntime()
        with self.assertRaises(SystemExit):
            rt(['-V'])
        out = sys.stdout.getvalue()
        self.doCleanups()
        self.assertEqual(out, 'no package information available.')

    def test_norm_args(self):
        stub_item_attr_value(self, sys, 'argv', ['script'])
        self.assertEqual(runtime.norm_args(None), [])
        self.assertEqual(runtime.norm_args([]), [])
        self.assertEqual(runtime.norm_args(['arg']), ['arg'])

        stub_item_attr_value(self, sys, 'argv', ['script', '-h'])
        self.assertEqual(runtime.norm_args(None), ['-h'])
        self.assertEqual(runtime.norm_args([]), [])
        self.assertEqual(runtime.norm_args(['arg']), ['arg'])

    def test_base_runtime_unknown_args(self):
        stub_stdouts(self)
        bt = runtime.BaseRuntime()
        with self.assertRaises(SystemExit):
            bt(['unknown'])
        self.assertIn('unrecognized arguments: unknown', sys.stderr.getvalue())

    def test_global_flags(self):
        def fake_parse(args):
            warnings.warn('fake deprecation', DeprecationWarning)
            return fake_parse.parse_known_args(args)

        stub_stdouts(self)
        bt = runtime.BaseRuntime()
        fake_parse.parse_known_args = bt.argparser.parse_known_args
        bt.argparser.parse_known_args = fake_parse

        with pretty_logging(stream=mocks.StringIO()) as s:
            bt(['-v'])
        self.assertIn("WARNING calmjs.runtime fake deprecation", s.getvalue())

    def test_argparse_levels(self):
        stub_stdouts(self)
        bt = runtime.BaseRuntime()
        bt(['-vvv', '-qq', '-d'])

        # should be a global state.
        rt = runtime.BaseRuntime()
        self.assertEqual(rt.verbosity, 1)
        self.assertEqual(rt.debug, 1)
        self.assertEqual(rt.log_level, INFO)
        self.assertEqual(rt.bootstrap_log_level, WARNING)

    def test_argparse_bootstrap_debug(self):
        stub_stdouts(self)
        bt = runtime.BaseRuntime()
        bt(['-vvv'])

        # should be a global state.
        rt = runtime.BaseRuntime()
        self.assertEqual(rt.log_level, DEBUG)
        self.assertEqual(rt.bootstrap_log_level, DEBUG)

    def test_bad_global_flags(self):
        stub_stdouts(self)
        runtime._global_runtime_attrs.update({'debug': 'string'})
        runtime._global_runtime_attrs.update({'trash': 'string'})
        # it doesn't belong, but show that it's here.
        self.assertIn('trash', runtime._global_runtime_attrs)
        rt = runtime.BaseRuntime()
        # always return an integer.
        self.assertEqual(rt.debug, 0)
        runtime._reset_global_runtime_attrs()
        self.assertNotIn('trash', runtime._global_runtime_attrs)

    def test_error_msg(self):
        # not normally triggered, but implementing just in case
        stub_stdouts(self)
        bt = runtime.BaseRuntime()
        with self.assertRaises(SystemExit):
            bt.error(bt.argparser, None, 'error message')
        self.assertIn('error message', sys.stderr.getvalue())

    def test_runtime_run_empty(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [],
        })
        rt = runtime.Runtime(working_set=working_set, prog='dummy')
        result = rt.run(rt.argparser, runtime='dummy')
        self.assertIs(result, NotImplemented)

    def test_runtime_error_deprecation(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'deprecated = calmjs.tests.test_runtime:deprecated',
        ]})
        rt = runtime.Runtime(working_set=working_set, prog='dummy')
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            with self.assertRaises(SystemExit):
                rt.error(rt.argparser, 'deprecated', 'simulated')
        self.assertIn('Runtime.error is deprecated', str(w[-1].message))

    def test_runtime_run_abort(self):
        class CustomRuntime(runtime.BaseRuntime):
            def run(self, export_target=None, **kwargs):
                raise exc.RuntimeAbort

        stub_stdouts(self)
        rt = CustomRuntime()
        rt([])
        self.assertEqual('', sys.stdout.getvalue())
        stderr = sys.stderr.getvalue()
        self.assertIn(
            'terminating due to expected unrecoverable condition', stderr)

        stub_stdouts(self)
        rt(['-vvd'])
        self.assertEqual('', sys.stdout.getvalue())
        stderr = sys.stderr.getvalue()
        self.assertNotIn('unexpected', stderr)

    def test_runtime_entry_point_load_logging(self):
        # sometimes the ImportError may be due to the target module
        # failing to load its imports, not that the target module being
        # absent
        ep = pkg_resources.EntryPoint.parse('broken = some.broken:instance')
        ep.load = fake_error(ImportError)

        rt = runtime.Runtime()
        with pretty_logging(stream=mocks.StringIO()) as stream:
            rt.entry_point_load_validated(ep)

        err = stream.getvalue()
        self.assertIn(
            "bad 'calmjs.runtime' entry point 'broken = some.broken:instance'",
            err
        )
        self.assertIn(': ImportError', err)
        self.assertNotIn('Traceback', err)

        # again, with more stringent logging
        runtime._global_runtime_attrs.update({'debug': 1})
        with pretty_logging(stream=mocks.StringIO()) as stream:
            rt.entry_point_load_validated(ep)
        err = stream.getvalue()
        self.assertIn('Traceback', err)

        # of course, if that module misbehaves completely, it shouldn't
        # blow our stuff up.
        ep.load = fake_error(Exception)
        runtime._global_runtime_attrs.update({'debug': 0})
        with pretty_logging(stream=mocks.StringIO()) as stream:
            rt.entry_point_load_validated(ep)
        err = stream.getvalue()
        # traceback logged even without debug.
        self.assertNotIn('Traceback', err)
        self.assertIn(': Exception', err)

    def test_runtime_entry_point_broken_at_main(self):
        # try the above, but do this through main
        stub_stdouts(self)
        ep = pkg_resources.EntryPoint.parse('broken = some.broken:instance')
        ep.load = fake_error(ImportError)
        working_set = mocks.WorkingSet({'calmjs.runtime': [ep]})
        with self.assertRaises(SystemExit):
            runtime.main(
                ['-h'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        self.assertNotIn('broken', out)
        self.assertIn('broken', err)

    def test_runtime_entry_point_preparse_warning(self):
        # see next test for the condition for warning to appear.
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'deprecated = calmjs.tests.test_runtime:deprecated',
        ]})
        with self.assertRaises(SystemExit):
            runtime.main(
                ['deprecated'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )
        err = sys.stderr.getvalue()
        self.assertNotIn('Traceback', err)
        self.assertNotIn('this runtime is deprecated', err)

    def test_runtime_entry_point_preparse_warning_verbose_logged(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'deprecated = calmjs.tests.test_runtime:deprecated',
        ]})
        with self.assertRaises(SystemExit):
            # use the verbose flag to increase the log level
            runtime.main(
                ['-v', 'deprecated'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )
        err = sys.stderr.getvalue()
        self.assertNotIn('Traceback', err)
        self.assertIn('this runtime is deprecated', err)
        self.assertNotIn('DeprecationWarning triggered at', err)

    def test_runtime_entry_point_preparse_warning_verbose_debug_logged(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'deprecated = calmjs.tests.test_runtime:deprecated',
        ]})
        with self.assertRaises(SystemExit):
            # use the verbose flag to increase the log level
            runtime.main(
                ['-vvv', 'deprecated'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )
        err = sys.stderr.getvalue()
        self.assertNotIn('Traceback', err)
        self.assertIn('this runtime is deprecated', err)
        self.assertIn('DeprecationWarning triggered at', err)

    def test_runtime_main_with_broken_runtime(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'broken = calmjs.tests.test_runtime:broken',
        ]})
        with self.assertRaises(SystemExit):
            runtime.main(
                ['-vvd', '-h'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        self.assertIn('broken', err)
        self.assertIn('Traceback', err)
        self.assertIn('a fake import error', err)
        self.assertNotIn('broken', out)

    def test_runtime_command_list_ordered(self):
        def cleanup():
            del mocks.a_tool
            del mocks.b_tool
            del mocks.h_tool
        self.addCleanup(cleanup)
        stub_stdouts(self)

        mocks.a_tool = runtime.DriverRuntime(None, description='a tool.')
        mocks.b_tool = runtime.DriverRuntime(None, description='base tool.')
        mocks.h_tool = runtime.DriverRuntime(None, description='help tool.')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'base = calmjs.testing.mocks:b_tool\n'
            'tool = calmjs.testing.mocks:a_tool\n'
            'helper = calmjs.testing.mocks:h_tool\n'
        ),), 'example.package', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        with self.assertRaises(SystemExit):
            runtime.main(
                ['-h'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )

        self.assertIn('tool.', sys.stdout.getvalue())
        lines = [
            line.strip().split()[0]
            for line in sys.stdout.getvalue().splitlines()
            if ' tool.' in line
        ]

        self.assertEqual(lines, ['base', 'helper', 'tool'])


class ToolchainRuntimeTestCase(unittest.TestCase):
    """
    Test cases for the toolchain runtime.
    """

    def setUp(self):
        remember_cwd(self)
        self.cwd = mkdtemp(self)
        os.chdir(self.cwd)

    def test_toolchain_runtime_basic_config(self):
        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        text = rt.argparser.format_help()
        self.assertIn(
            "--build-dir", text,
        )

        self.assertTrue(isinstance(rt.create_spec(), toolchain.Spec))

    def test_standard_run(self):
        stub_stdouts(self)
        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)

        err = mocks.StringIO()
        with pretty_logging(logger='calmjs.runtime', level=DEBUG, stream=err):
            result = rt.run(export_target='dummy')
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)

    def test_basic_execution(self):
        stub_stdouts(self)
        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        result = rt(['--export-target=dummy'])
        # as result returned not defined for these lower level runtimes
        # not registered as console entry points, any result can be
        # returned.
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)
        self.assertEqual(result['link'], 'linked')

    def test_prompt_export_target_export_target_undefined(self):
        stub_stdouts(self)
        spec = toolchain.Spec()
        err = mocks.StringIO()
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        with pretty_logging(logger='calmjs.runtime', level=DEBUG, stream=err):
            rt.check_export_target_exists(spec)
        self.assertIn("spec missing key 'export_target'; ", err.getvalue())

    def test_check_export_target_exists_not_exists(self):
        stub_stdouts(self)
        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        spec = toolchain.Spec(export_target=export_target)
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        rt.check_export_target_exists(spec)
        self.assertEqual(sys.stdout.getvalue(), '')

    def test_check_export_target_exists_exists_no(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'n\n')
        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file
        spec = toolchain.Spec(export_target=export_target)
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        with self.assertRaises(exc.ToolchainCancel):
            rt.check_export_target_exists(spec)
        self.assertIn('already exists, overwrite?', sys.stdout.getvalue())

    def test_check_export_target_exists_exists_yes(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')
        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file
        spec = toolchain.Spec(export_target=export_target)
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        rt.check_export_target_exists(spec)
        self.assertIn('already exists, overwrite?', sys.stdout.getvalue())

    def test_check_export_target_exists_exists_non_interactive(self):
        stub_check_interactive(self, False)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')
        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file
        spec = toolchain.Spec(export_target=export_target)
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        with pretty_logging(
                logger='calmjs', level=DEBUG, stream=mocks.StringIO()) as err:
            with self.assertRaises(exc.ToolchainCancel):
                rt.check_export_target_exists(spec)
        self.assertIn(
            'non-interactive mode; auto-selected default option [No]',
            err.getvalue()
        )

    def test_prompted_execution_exists(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        result = rt(['--export-target', export_target])
        self.assertIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        self.assertNotIn(
            "export target location '%s' already exists; it may be overwritten"
            % export_target,
            sys.stderr.getvalue()
        )
        self.assertNotIn('CRITICAL', sys.stderr.getvalue())
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)
        self.assertEqual(result['link'], 'linked')

    def test_prompted_execution_with_working_dir_flag(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        result = rt([
            '--export-target', 'export_file', '--working-dir', target_dir])
        self.assertTrue(isinstance(result, toolchain.Spec))

        self.assertIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )

        # also check the logs.
        err = sys.stderr.getvalue()
        self.assertNotIn('CRITICAL', err)
        self.assertIn('WARNING', err)
        self.assertIn(
            "WARNING calmjs.toolchain realpath of 'export_target' resolved to",
            err)
        self.assertIn(export_target, err)
        # prove that it did at least run
        self.assertEqual(result['export_target'], export_target)
        self.assertEqual(result['link'], 'linked')

    def test_prompted_execution_without_export_target(self):
        class ToolchainRuntime(runtime.ToolchainRuntime):
            def create_spec(self, **kwargs):
                if not kwargs.get('export_target'):
                    kwargs['export_target'] = join(
                        kwargs.get('working_dir') or self.cwd,
                        'default_location'
                    )
                return super(ToolchainRuntime, self).create_spec(**kwargs)

        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')

        target_dir = mkdtemp(self)
        # write an empty file at expected location
        export_target = join(target_dir, 'default_location')
        open(export_target, 'w').close()

        tc = toolchain.NullToolchain()
        rt = ToolchainRuntime(tc)
        result = rt(['--working-dir', target_dir])
        self.assertIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        # also check the logs.
        err = sys.stderr.getvalue()
        self.assertNotIn('CRITICAL', err)
        self.assertNotIn('WARNING', err)
        # since it was joined with a proper working dir.
        self.assertNotIn(
            "WARNING calmjs.toolchain realpath of 'export_target' resolved to",
            err)
        self.assertNotIn(export_target, err)
        # prove that it did at least run
        self.assertEqual(result['export_target'], export_target)
        self.assertEqual(result['link'], 'linked')

    def test_prompted_execution_exists_overwrite(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        result = rt(['--export-target', export_target, '-w'])
        self.assertNotIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        self.assertIn(
            "export target location '%s' already exists; it may be overwritten"
            % export_target,
            sys.stderr.getvalue()
        )
        self.assertNotIn('CRITICAL', sys.stderr.getvalue())
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)
        self.assertEqual(result['link'], 'linked')

    def test_prompted_overwrite_for_modified_create_spec(self):
        """
        Test execution for runtime that completely overrides create_spec
        to return an bare minimum spec.
        """

        class CustomToolchainRuntime(runtime.ToolchainRuntime):
            def create_spec(self, export_target=None, **kwargs):
                return toolchain.Spec(export_target=export_target)

        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'y\n')

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file

        tc = toolchain.NullToolchain()
        rt = CustomToolchainRuntime(tc)
        result = rt(['--export-target', export_target, '-w'])
        self.assertNotIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        self.assertNotIn('CRITICAL', sys.stderr.getvalue())
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)
        self.assertEqual(result['link'], 'linked')

        stub_stdouts(self)
        stub_stdin(self, u'y\n')
        result = rt(['--export-target', export_target])
        self.assertIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        self.assertNotIn('CRITICAL', sys.stderr.getvalue())
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that it did at least run
        self.assertIn('build_dir', result)
        self.assertEqual(result['link'], 'linked')

    def test_transpiler_error(self):
        source_dir = mkdtemp(self)
        malformed_js_filename = join(source_dir, 'malformed.js')
        malformed_code = 'function(){};\n'

        with open(malformed_js_filename, 'w') as fd:
            fd.write(malformed_code)

        class ES5ToolchainRuntime(runtime.ToolchainRuntime):
            def create_spec(self, export_target=None, **kwargs):
                return toolchain.Spec(
                    export_target=export_target,
                    transpile_sourcepath={
                        'malformed': malformed_js_filename,
                    },
                )

        stub_check_interactive(self, True)
        stub_stdouts(self)

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')

        tc = toolchain.ES5Toolchain()
        ES5ToolchainRuntime(tc)(['--export-target', export_target])

        self.assertIn('CRITICAL', sys.stderr.getvalue())
        self.assertIn(
            'ECMASyntaxError: Function statement requires a name at 1:9 in',
            sys.stderr.getvalue()
        )
        self.assertIn('malformed.js', sys.stderr.getvalue())

    def test_prompted_execution_exists_cancel(self):
        stub_check_interactive(self, True)
        stub_stdouts(self)
        stub_stdin(self, u'n\n')

        target_dir = mkdtemp(self)
        export_target = join(target_dir, 'export_file')
        open(export_target, 'w').close()  # write an empty file

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        result = rt(['--export-target', export_target])
        self.assertIn(
            "export target '%s' already exists, overwrite? " % export_target,
            sys.stdout.getvalue()
        )
        self.assertNotIn('CRITICAL', sys.stderr.getvalue())
        self.assertTrue(isinstance(result, toolchain.Spec))
        # prove that the cancel really happened.
        self.assertIn('build_dir', result)
        self.assertNotIn('link', result)

        # Should not have unexpected warnings logged.
        stderr = sys.stderr.getvalue()
        self.assertNotIn('WARNING', stderr)
        self.assertNotIn("spec missing key 'export_target';", stderr)

    def test_excution_missing_export_file(self):
        # as the null toolchain does not automatically provide one
        stub_stdouts(self)
        rt = runtime.ToolchainRuntime(toolchain.NullToolchain())
        rt([])
        self.assertEqual('', sys.stdout.getvalue())
        stderr = sys.stderr.getvalue()
        self.assertIn('WARNING', stderr)
        self.assertIn("spec missing key 'export_target';", stderr)

    def test_spec_nodebug(self):
        stub_stdouts(self)
        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()) as s:
            result = rt(['--export-target', 'dummy'])
        self.assertEqual(result['debug'], 0)
        self.assertIn(
            "'export_target' resolved to '%s'" % join(self.cwd, 'dummy'),
            s.getvalue())

    def test_spec_debugged(self):
        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()) as s:
            result = rt(['-dd', '--export-target', join(self.cwd, 'dummy')])
        self.assertEqual(result['debug'], 2)
        # also test for the export_target resolution
        self.assertNotIn(
            "'export_target' resolved to '%s'" % join(self.cwd, 'dummy'),
            s.getvalue())

    def test_spec_debugged_via_cmdline(self):
        stub_stdouts(self)
        stub_item_attr_value(
            self, mocks, 'dummy',
            runtime.ToolchainRuntime(toolchain.NullToolchain()),
        )
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'tool = calmjs.testing.mocks:dummy',
            ],
        })
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()) as s:
            result = rt(['tool', '--export-target', 'dummy', '-d'])
        self.assertEqual(result['debug'], 1)
        # also test for the export_target resolution
        self.assertIn(
            "'export_target' resolved to '%s'" % join(self.cwd, 'dummy'),
            s.getvalue())

    def test_spec_optional_advice(self):
        from calmjs.registry import _inst as root_registry
        key = toolchain.CALMJS_TOOLCHAIN_ADVICE
        stub_stdouts(self)

        def cleanup_fake_registry():
            # pop out the fake advice registry that was added.
            root_registry.records.pop(key, None)

        self.addCleanup(cleanup_fake_registry)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:Toolchain = calmjs.tests.test_toolchain:bad\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        root_registry.records[key] = toolchain.AdviceRegistry(
            key, _working_set=working_set)

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)

        result = rt([
            '--export-target', 'dummy',
            '--optional-advice', 'example.package', '-vv',
        ])

        self.assertEqual(result['dummy'], ['dummy', 'bad'])
        err = sys.stderr.getvalue()
        err_lines = err.splitlines()

        self.assertIn('sourcing optional advices from ', err_lines[0])
        self.assertIn('example.package', err_lines[0])
        self.assertIn('as specified', err_lines[0])
        self.assertIn("applying advice package 'example.package'", err)
        self.assertIn('failure encountered while setting up advices', err)

        # Doing it normally should not result in that optional key.
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()):
            result = rt(['--export-target', 'dummy'])
        self.assertNotIn('dummy', result)

    def test_spec_toolchain_advice_apply(self):
        # This mostly just run through the toolchain to ensure that the
        # advice is applied without any arguments.
        from calmjs.registry import _inst as root_registry
        key_t_a = toolchain.CALMJS_TOOLCHAIN_ADVICE
        key_t_a_a = toolchain.CALMJS_TOOLCHAIN_ADVICE + '.apply'
        stub_stdouts(self)

        self.addCleanup(root_registry.records.pop, key_t_a, None)
        self.addCleanup(root_registry.records.pop, key_t_a_a, None)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:NullToolchain'
            ' = calmjs.testing.spec:advice_marker\n'
            '\n'
            '[calmjs.toolchain.advice.apply]\n'
            'example.package = example.package\n'
        ),), 'example.package', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice.apply]\n'
            'example.package = example.package[argument]\n'
        ),), 'example.other_package', '1.0')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'example.package',
                'example.other_package',
            ])),
            ('entry_points.txt', '',),
        ), 'dependent', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        root_registry.records[key_t_a] = toolchain.AdviceRegistry(
            key_t_a, _working_set=working_set)
        root_registry.records[key_t_a_a] = toolchain.AdviceApplyRegistry(
            key_t_a_a, _working_set=working_set)

        tc = toolchain.NullToolchain()
        rt = runtime.SourcePackageToolchainRuntime(tc)

        result = rt([
            '--export-target', join(self.cwd, 'dummy_export'),
            'example.package', '-v',
        ])

        self.assertEqual([([], [])], result['marker_too_soon'])
        self.assertEqual([(['example.package'], [])], result['marker_delayed'])
        err = sys.stderr.getvalue()
        err_lines = err.splitlines()

        self.assertIn(
            "source package 'example.package' specified 1 advice package(s) "
            "to be applied", err_lines[0])
        self.assertIn('example.package', err_lines[0])
        self.assertIn('to be applied', err_lines[0])

        # Doing it normally should not result in that optional key.
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()) as s:
            result = rt([
                '--export-target', join(self.cwd, 'dummy_export'),
                'example.other_package', '-v',
            ])

        # arguments will be passed, but the advice_packages key won't be
        # assigned.
        self.assertEqual([([], ['argument'])], result['marker_too_soon'])
        # naturally, it would be available in the setup.
        self.assertEqual(
            [(['example.package[argument]'], ['argument'])],
            result['marker_delayed']
        )

        err_lines = s.getvalue().splitlines()
        self.assertIn(
            "source package 'example.other_package' specified 1 advice "
            "package(s) to be applied", err_lines[0])

        # This tests the dependent case where the dependent package
        # declares both as dependents, but it doesn't declare the
        # records for the relevant registries.
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()) as s:
            result = rt([
                '--export-target', join(self.cwd, 'dummy_export'),
                'dependent', '-v',
            ])

        # shouldn't have anything.
        self.assertNotIn('marker_too_soon', result)
        self.assertNotIn('marker_delayed', result)
        self.assertEqual('', s.getvalue())

    def test_spec_toolchain_advice_apply_missing_requirement(self):
        # This mostly just run through the toolchain to ensure that the
        # advice is applied without any arguments.
        from calmjs.registry import _inst as root_registry
        key_t_a = toolchain.CALMJS_TOOLCHAIN_ADVICE
        key_t_a_a = toolchain.CALMJS_TOOLCHAIN_ADVICE + '.apply'
        stub_stdouts(self)

        self.addCleanup(root_registry.records.pop, key_t_a, None)
        self.addCleanup(root_registry.records.pop, key_t_a_a, None)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice.apply]\n'
            'example.package = example.package[argument]\n'
        ),), 'example.other_package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        root_registry.records[key_t_a] = toolchain.AdviceRegistry(
            key_t_a, _working_set=working_set)
        root_registry.records[key_t_a_a] = toolchain.AdviceApplyRegistry(
            key_t_a_a, _working_set=working_set)

        tc = toolchain.NullToolchain()
        rt = runtime.SourcePackageToolchainRuntime(tc)

        # Doing it normally should not result in that optional key.
        with pretty_logging(logger='calmjs', stream=mocks.StringIO()):
            result = rt([
                '--export-target', join(self.cwd, 'dummy_export'),
                'example.other_package', '-v',
            ])

        # shouldn't have anything.
        self.assertNotIn('marker_too_soon', result)
        self.assertNotIn('marker_delayed', result)

    def test_spec_advise_debugger(self):
        # this is meant for advanced usage, thus undocumented.
        from calmjs import utils
        stub_stdouts(self)
        skipped = []
        traced = []

        class FakePdb(object):
            def __init__(self, skip, *a, **kw):
                skipped.append(skip)

            def set_trace(self):
                traced.append(True)

        stub_item_attr_value(self, utils, 'Pdb', FakePdb)

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)

        rt([
            '--export-target', 'dummy',
            '--optional-advice', 'calmjs[welp,debug_before_assemble]', '-vv',
        ])

        self.assertEqual(0, len(skipped))
        self.assertEqual(0, len(traced))

        # now with the debug flag
        rt([
            '--export-target', 'dummy', '-d',
            '--optional-advice', 'calmjs[welp,debug_before_assemble]', '-vv',
        ])

        self.assertEqual(skipped[0], ['calmjs.utils'])
        self.assertEqual(1, len(traced))
        err = sys.stderr.getvalue()
        self.assertIn("debugger advised at 'before_assemble'", err)

    def test_spec_optional_advice_extras(self):
        from calmjs.registry import _inst as root_registry
        key = toolchain.CALMJS_TOOLCHAIN_ADVICE
        stub_stdouts(self)

        def cleanup_fake_registry():
            # pop out the fake advice registry that was added.
            root_registry.records.pop(key, None)

        self.addCleanup(cleanup_fake_registry)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.tests.test_toolchain:dummy\n'
        ),), 'example.package', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        root_registry.records[key] = toolchain.AdviceRegistry(
            key, _working_set=working_set)

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)

        result = rt([
            '--export-target', 'dummy',
            '--optional-advice', 'example.package[extra1,extra2]', '-vv',
        ])

        self.assertEqual(result['extras'], ['extra1', 'extra2'])

    def test_spec_deferred_addition(self):
        """
        This turns out to be critical - the advices provided by the
        packages should NOT be added immediately, as it is executed
        before a number of very important advices were added by the
        toolchain itself.

        However, given that the functionality has been moved from the
        runtime to the toolchain itself, this should be less of an issue
        but this test will remain as a check against regression of sort.
        """

        from calmjs.registry import _inst as root_registry
        key = toolchain.CALMJS_TOOLCHAIN_ADVICE
        stub_stdouts(self)

        def cleanup_fake_registry():
            # pop out the fake advice registry that was added.
            root_registry.records.pop(key, None)

        self.addCleanup(cleanup_fake_registry)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.toolchain.advice]\n'
            'calmjs.toolchain:NullToolchain = '
            'calmjs.testing.spec:advice_order\n'
        ),), 'example.package', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        root_registry.records[key] = toolchain.AdviceRegistry(
            key, _working_set=working_set)

        tc = toolchain.NullToolchain()
        rt = runtime.ToolchainRuntime(tc)

        result = rt([
            '--export-target', join(mkdtemp(self), 'dummy'),
            '--optional-advice', 'example.package',
        ])

        self.assertEqual(sys.stderr.getvalue(), '')
        self.assertIsNotNone(result)

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_spec_debugged_via_cmdline_target_exists_export_cancel(self):
        stub_item_attr_value(
            self, mocks, 'dummy',
            runtime.ToolchainRuntime(toolchain.NullToolchain()),
        )
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'tool = calmjs.testing.mocks:dummy',
            ],
        })
        tmpdir = mkdtemp(self)
        target = join(tmpdir, 'target')
        open(target, 'w').close()
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        stub_stdouts(self)
        stub_stdin(self, u'n\n')
        stub_check_interactive(self, True)
        result = rt(['tool', '--export-target', target, '-dd', '-vv'])
        self.assertEqual(result['debug'], 2)
        # This is an integration test of sort for the debug advice output
        self.assertIn("advise 'cleanup' invoked by", sys.stderr.getvalue())
        self.assertIn("toolchain.py", sys.stderr.getvalue())
        self.assertIn(
            'advise(AFTER_PREPARE, self.check_export_target_exists, spec)',
            sys.stderr.getvalue(),
        )


class SourcePackageToolchainRuntimeTestCase(unittest.TestCase):
    """
    Test cases for the toolchain runtime that provides interaction with
    source registry and source packages.
    """

    def test_source_package_toolchain_basic(self):
        tc = toolchain.NullToolchain()
        rt = runtime.SourcePackageToolchainRuntime(tc)
        text = rt.argparser.format_help()
        self.assertNotIn("--loaderplugin-registry", text)
        self.assertIn("--source-registry", text)
        self.assertTrue(isinstance(rt.create_spec(), toolchain.Spec))

    def test_source_package_toolchain_argparser(self):
        stub_stdouts(self)
        parser = ArgumentParser()
        tc = toolchain.NullToolchain()
        rt = runtime.SourcePackageToolchainRuntime(tc)
        rt.init_argparser(parser)
        known, extras = parser.parse_known_args(
            ['--source-registry', 'reg1,reg2', 'example.package'])
        self.assertEqual(
            known.calmjs_module_registry_names, ['reg1', 'reg2'])
        self.assertEqual(
            known.source_package_names, ['example.package'])

    def test_source_package_toolchain_default(self):
        stub_stdouts(self)
        parser = ArgumentParser()
        tc = toolchain.NullToolchain()
        rt = runtime.SourcePackageToolchainRuntime(tc)
        rt.init_argparser(parser)
        known, extras = parser.parse_known_args(['example.package'])
        self.assertEqual(known.calmjs_module_registry_names, None)

    def test_source_package_toolchain_argparser_default_registry(self):
        class CustomRuntime(runtime.SourcePackageToolchainRuntime):
            def init_argparser_source_registry(self, argparser):
                super(CustomRuntime, self).init_argparser_source_registry(
                    argparser, default=('default_reg',))

        stub_stdouts(self)
        parser = ArgumentParser()
        tc = toolchain.NullToolchain()
        rt = CustomRuntime(tc)
        rt.init_argparser(parser)
        known, extras = parser.parse_known_args(['example.package'])
        self.assertEqual(
            known.calmjs_module_registry_names, ('default_reg',))
        self.assertEqual(
            known.source_package_names, ['example.package'])


class LoaderPluginToolchainRuntime(runtime.SourcePackageToolchainRuntime):

    def init_argparser(self, argparser):
        super(LoaderPluginToolchainRuntime, self).init_argparser(argparser)
        self.init_argparser_loaderplugin_registry(argparser)


class RuntimeLoaderPluginRegistryOptionTestCase(unittest.TestCase):
    """
    Test out the --loaderplugin-registry flag.
    """

    def test_loaderplugin_toolchain_basic(self):
        tc = toolchain.NullToolchain()
        rt = LoaderPluginToolchainRuntime(tc)
        text = rt.argparser.format_help()
        self.assertIn("--loaderplugin-registry", text)
        self.assertTrue(isinstance(rt.create_spec(), toolchain.Spec))

    def test_loaderplugin_toolchain_argparser(self):
        stub_stdouts(self)
        parser = ArgumentParser()
        tc = toolchain.NullToolchain()
        rt = LoaderPluginToolchainRuntime(tc)
        rt.init_argparser(parser)
        known, extras = parser.parse_known_args(
            ['--loaderplugin-registry', 'reg1,reg2', 'example.package'])
        self.assertEqual(
            known.calmjs_loaderplugin_registry_name, 'reg1,reg2')
        self.assertEqual(
            known.source_package_names, ['example.package'])


class ArtifactRuntimeTestCase(unittest.TestCase):
    """
    Test cases for the artifact runtime and subruntimes.
    """

    def setUp(self):
        from calmjs import artifact

        def version(bin_path, version_flag='-v', kw={}):
            return '0.0.0'

        # provide a fake version to avoid implied execution
        stub_item_attr_value(self, artifact, 'get_bin_version_str', version)

    def test_artifact_runtime_integration(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'artifact = calmjs.runtime:artifact',
        ]})
        rt = runtime.Runtime(working_set=working_set)
        # An underspecified command should also return False.
        self.assertFalse(rt(['artifact']))
        # ensure the help for the command itself is printed
        self.assertIn(
            'helpers for the management of artifacts', sys.stdout.getvalue())

    def test_artifact_build_runtime_integration(self):
        from calmjs import artifact
        from calmjs.registry import _inst as root_registry
        from calmjs.testing.artifact import generic_builder
        from calmjs.testing.artifact import fail_builder

        def die():
            raise toolchain.ToolchainAbort('desu')

        def exploding_builder(package_names, export_target):
            tc, spec = generic_builder(package_names, export_target)
            spec.advise(toolchain.BEFORE_COMPILE, die)
            return tc, spec

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.registry]\n'
            'calmjs.artifacts = calmjs.artifact:ArtifactRegistry\n'
            '[calmjs.runtime]\n'
            'artifact = calmjs.runtime:artifact\n'
            '[calmjs.runtime.artifact]\n'
            'build = calmjs.runtime:artifact_build\n'
        ),), 'calmjs', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'full.js = calmjs_testbuilder:builder\n',
        ),), 'example.package', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'other.js = calmjs_testbuilder:builder\n',
        ),), 'example.other', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'full.js = calmjs_testbuilder:explosion\n',
        ),), 'boom', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'full.js = calmjs_testbuilder:fizz\n',
        ),), 'incomplete', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'fail.js = calmjs_testbuilder:missing\n',
        ),), 'missing.single', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'full.js = calmjs_testbuilder:builder\n'
            'fail.js = calmjs_testbuilder:fail\n',
        ),), 'fizz', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'good.js = calmjs_testbuilder:builder\n'
            'fail.js = calmjs_testbuilder:missing\n',
        ),), 'missing.attribute', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.artifacts]\n'
            'good.js = calmjs_testbuilder:builder\n'
            'fail.js = no_such_module:missing\n',
        ),), 'missing.module', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        mod = ModuleType('calmjs_testbuilder')
        mod.builder = generic_builder
        mod.fail = fail_builder
        mod.explosion = exploding_builder
        self.addCleanup(sys.modules.pop, 'calmjs_testbuilder')
        sys.modules['calmjs_testbuilder'] = mod

        self.addCleanup(root_registry.records.pop, 'calmjs.artifacts')
        artifact_registry = root_registry.records[
            'calmjs.artifacts'] = artifact.ArtifactRegistry(
                'calmjs.artifacts', _working_set=working_set)

        rt = runtime.Runtime(working_set=working_set)
        command = ['artifact', 'build', 'example.package']
        rt(command)

        self.assertTrue(
            exists(artifact_registry.metadata.get('example.package')))

        stub_stdouts(self)

        # try again through the main method
        with self.assertRaises(SystemExit) as e:
            runtime.main(command, runtime_cls=lambda: rt)

        # ensure proper exit code of 0
        self.assertEqual(e.exception.args[0], 0)

        # remove artifact to try again later for multiple packages in
        # one go.
        os.unlink(artifact_registry.metadata.get('example.package'))
        with self.assertRaises(SystemExit) as e:
            runtime.main(command + ['example.other'], runtime_cls=lambda: rt)
        # ensure proper exit code of 0
        self.assertEqual(e.exception.args[0], 0)
        self.assertTrue(
            exists(artifact_registry.metadata.get('example.package')))
        self.assertTrue(
            exists(artifact_registry.metadata.get('example.other')))

        # however, if something blows up completely...
        with self.assertRaises(SystemExit) as e:
            runtime.main(['artifact', 'build', 'boom'], runtime_cls=lambda: rt)
        # ensure proper exit code of 1
        self.assertEqual(e.exception.args[0], 1)

        # also when the artificat didn't actually get produced
        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'incomplete'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

        # also when entry point references missing imports, as missing
        # dependencies for building should be flagged.
        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'missing.single'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

        # include a mix of valid entry points with ones missing actual
        # modules.

        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'fizz'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

        stub_stdouts(self)

        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'missing.attribute'],
                runtime_cls=lambda: rt,
            )
        self.assertIn(
            "unable to import the target builder for the entry point "
            "'fail.js = calmjs_testbuilder:missing' from package "
            "'missing.attribute 1.0'", sys.stderr.getvalue()
        )
        self.assertEqual(e.exception.args[0], 1)

        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'missing.module'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'empty', 'example.package', '-vv'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

        with self.assertRaises(SystemExit) as e:
            runtime.main(
                ['artifact', 'build', 'example.package', 'calmjs', '-vv'],
                runtime_cls=lambda: rt,
            )
        self.assertEqual(e.exception.args[0], 1)

    def test_artifact_build_runtime_live_integration(self):
        stub_stdouts(self)
        # using the live data this time.
        with self.assertRaises(SystemExit) as e:
            runtime.main(['artifact', 'build', 'calmjs', '-v'])
        self.assertIn(
            "package 'calmjs' has not declare", sys.stderr.getvalue())

        # since no artifacts were built, it will be non-zero
        self.assertNotEqual(e.exception.args[0], 0)


class PackageManagerRuntimeTestCase(unittest.TestCase):
    """
    Test cases for the package manager driver/runtime and argparse
    usage.
    """

    def test_command_creation(self):
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = runtime.PackageManagerRuntime(driver)
        text = cmd.argparser.format_help()
        self.assertIn(
            "run 'mgr install' with generated 'default.json';", text,
        )

    def test_root_runtime_details_dropped(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'npm = calmjs.npm:npm.runtime',
        ]})
        rt = runtime.Runtime(prog='dummy', working_set=working_set)
        rt.argparser  # populate the argparser
        rt.argparser_details.clear()
        with pretty_logging(
                logger='calmjs.runtime', stream=mocks.StringIO()) as s:
            rt(['npm', 'somepackage'])

        self.assertIn('CRITICAL', s.getvalue())
        self.assertIn(
            "provided argparser (prog='dummy') not associated with this "
            "runtime (<calmjs.runtime.Runtime",
            s.getvalue())
        self.assertIn(
            'runtime cannot continue due to missing argparser details',
            s.getvalue())

    def test_root_runtime_errors_ignored(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'foo = calmjs.nosuchmodule:no.where',
            'bar = calmjs.npm:npm',
            'npm = calmjs.npm:npm.runtime',
        ]})
        rt = runtime.Runtime(working_set=working_set)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        out = sys.stdout.getvalue()
        self.assertNotIn('foo', out)
        self.assertIn('npm', out)

    def test_npm_description(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'npm = calmjs.npm:npm.runtime',
        ]})
        rt = runtime.Runtime(working_set=working_set)
        with self.assertRaises(SystemExit):
            rt(['npm', '-h'])
        out = sys.stdout.getvalue()
        self.assertIn('npm support for the calmjs framework', out)


class RuntimeGoingWrongTestCase(unittest.TestCase):
    """
    Test cases for handling the various things that can potentially go
    wrong from being so accepting of setup code from other packages.
    """

    def test_root_runtime_bad_names(self):
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'bad name = calmjs.npm:npm.runtime',
            'bad.name = calmjs.npm:npm.runtime',
            'badname:likethis = calmjs.npm:npm.runtime',
        ]})

        stderr = mocks.StringIO()
        with pretty_logging(
                logger='calmjs.runtime', level=DEBUG, stream=stderr):
            rt = runtime.Runtime(working_set=working_set)
            rt.argparser
        err = stderr.getvalue()

        self.assertIn("bad 'calmjs.runtime' entry point", err)

        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        out = sys.stdout.getvalue()
        # this results in unnatural argparsing situation
        self.assertNotIn('bad name', out)
        # reserved for disambiguation
        self.assertNotIn('bad.name', out)
        self.assertNotIn('badname:likethis', out)
        # command listing naturally not available.
        self.assertNotIn('npm', out)

    def test_root_runtime_bootstrap_logging(self):
        sys.modules.pop('calmjs.npm', None)
        self.addCleanup(sys.modules.pop, 'calmjs.npm', None)
        stub_stdouts(self)
        stub_os_environ(self)
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'npm = calmjs.npm:npm.runtime',
        ),), 'example.package', '1.0')

        os.environ['PATH'] = ''
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        sys.modules.pop('calmjs.npm', None)
        with self.assertRaises(SystemExit):
            runtime.main(
                [],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )

        self.assertNotIn(
            "Unable to locate the 'npm' binary", sys.stderr.getvalue())

        sys.modules.pop('calmjs.npm', None)
        with self.assertRaises(SystemExit):
            runtime.main(
                ['-qqqq'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )

        self.assertNotIn(
            "Unable to locate the 'npm' binary", sys.stderr.getvalue())

        sys.modules.pop('calmjs.npm', None)
        with self.assertRaises(SystemExit):
            runtime.main(
                ['-v'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )

        self.assertIn(
            "Unable to locate the 'npm' binary", sys.stderr.getvalue())

    def test_runtime_group_not_runtime_reported(self):
        stub_stdouts(self)
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'bs = calmjs.testing.module3.runtime:fake_bootstrap\n'
        ),), 'example.package', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        with self.assertRaises(SystemExit):
            runtime.main(
                ['-h'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set)
            )

        self.assertIn(
            "'calmjs.runtime' entry point "
            "'bs = calmjs.testing.module3.runtime:fake_bootstrap' from "
            "'example.package 1.0' invalid for instance of "
            "'calmjs.runtime.Runtime': target not an instance of "
            "'calmjs.runtime.BaseRuntime' or its subclass; not registering "
            "invalid entry point", sys.stderr.getvalue()
        )

    def test_duplication_and_runtime_duplicated(self):
        """
        Duplicated entry point names with malformed mangling.
        """

        stub_stdouts(self)
        working_set = pkg_resources.WorkingSet()
        rt = runtime.Runtime(working_set=working_set)
        # reinit
        with pretty_logging(stream=mocks.StringIO()) as s:
            rt.init_argparser(rt.argparser)
        self.assertIn('already been initialized against runner', s.getvalue())

    def setup_dupe_runtime(self):
        from calmjs.testing import utils
        from calmjs.npm import npm
        utils.foo_runtime = runtime.PackageManagerRuntime(npm.cli_driver)
        utils.runtime_foo = runtime.PackageManagerRuntime(npm.cli_driver)

        def cleanup():
            del utils.foo_runtime
            del utils.runtime_foo
        self.addCleanup(cleanup)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'bar = calmjs.testing.utils:foo_runtime\n'
        ),), 'example1.foo', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'bar = calmjs.testing.utils:foo_runtime\n'
        ),), 'example2.foo', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'bar = calmjs.testing.utils:runtime_foo\n'
            'baz = calmjs.testing.utils:runtime_foo\n'
        ),), 'example3.foo', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'bar = calmjs.testing.utils:runtime_foo\n'
            'baz = calmjs.testing.utils:runtime_foo\n'
        ),), 'example4.foo', '1.0')

        return pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

    def test_duplication_and_runtime_handling(self):
        """
        Duplicated entry point names

        Naturally, there may be situations where different packages have
        registered entry_points with the same name.  It will be great if
        that can be addressed.
        """

        stub_stdouts(self)
        working_set = self.setup_dupe_runtime()

        stderr = mocks.StringIO()
        with pretty_logging(
                logger='calmjs.runtime', level=DEBUG, stream=stderr):
            rt = runtime.Runtime(working_set=working_set)
            rt.argparser

        msg = stderr.getvalue()
        self.assertIn(
            "duplicated registration of command 'baz' via entry point "
            "'baz = calmjs.testing.utils:runtime_foo' ignored; ",
            msg
        )
        self.assertIn(
            "a calmjs runtime command named 'bar' already registered.", msg)
        self.assertIn(
            "'bar = calmjs.testing.utils:foo_runtime' from 'example", msg)
        self.assertIn(
            "'bar = calmjs.testing.utils:runtime_foo' from 'example", msg)
        # Registration order is non-deterministic, so fallback is too
        self.assertIn("fallback command 'calmjs.testing.utils:", msg)
        self.assertIn("is already registered.", msg)

        # Try to use it
        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        out = sys.stdout.getvalue()
        self.assertIn('bar', out)
        self.assertIn('baz', out)

        # Both fallbacks should be registered, to ensure disambiguation,
        # as the load order can be influenced randomly by dict ordering
        # or even the filesystem file load order.
        foo_runtime = 'calmjs.testing.utils:foo_runtime'
        runtime_foo = 'calmjs.testing.utils:runtime_foo'
        self.assertIn(runtime_foo, out)
        self.assertIn(foo_runtime, out)

    def test_duplication_and_runtime_running(self):
        """
        Duplicated entry point names on execution.
        """

        stub_stdouts(self)
        working_set = self.setup_dupe_runtime()
        rt = runtime.Runtime(working_set=working_set)  # first init
        foo_runtime = 'calmjs.testing.utils:foo_runtime'
        runtime_foo = 'calmjs.testing.utils:runtime_foo'

        # see that the full one can be invoked and actually invoke the
        # underlying runtime
        with self.assertRaises(SystemExit):
            rt([foo_runtime, '-h'])
        out = sys.stdout.getvalue()
        self.assertIn(foo_runtime, out)
        self.assertIn("run 'npm install' with generated 'package.json';", out)

        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            rt([runtime_foo, '-h'])
        out = sys.stdout.getvalue()
        self.assertIn(runtime_foo, out)
        self.assertIn("run 'npm install' with generated 'package.json';", out)

        ext_argparser = ArgumentParser()
        # Time to demonstrate how mixing external argparser will work
        rt.init_argparser(ext_argparser)  # second init

        stderr = mocks.StringIO()
        with pretty_logging(
                logger='calmjs.runtime', level=DEBUG, stream=stderr):
            # poking into privates for that actual runtime instance and
            # blow it up.
            rt._BootstrapRuntime__argparser = None
            rt.argparser  # third init

        # A forced reinit shouldn't cause a major issue
        msg = stderr.getvalue()
        self.assertNotIn(
            "Runtime instance has been used or initialized improperly.", msg)
        self.assertNotIn(
            "Runtime instance has been used or initialized improperly.",
            sys.stderr.getvalue())

        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        out = sys.stdout.getvalue()
        # The "distinctly" named commands should be reinitialized
        self.assertIn('bar', out)
        self.assertIn('baz', out)

        # the number of tracked argparsers should increase to 3 due to
        # number of calls to init
        self.assertEqual(len(rt.argparser_details), 3)

    def test_runtime_nesting_registration(self):
        """
        Nested runtime registration
        """

        from calmjs.testing import utils

        class Simple1Runtime(runtime.Runtime):
            pass

        class Simple2Runtime(Simple1Runtime):
            pass

        def cleanup():
            del utils.simple1
            del utils.simple2
            del utils.runtime
        self.addCleanup(cleanup)

        stub_stdouts(self)

        # create a dummy based
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'runtime = calmjs.testing.utils:runtime\n'
            'simple1 = calmjs.testing.utils:simple1\n'
            'simple2 = calmjs.testing.utils:simple2\n'
        ),), 'example.simple', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.simple2 = Simple2Runtime(working_set=working_set)
        utils.simple1 = Simple1Runtime(working_set=working_set)
        utils.runtime = runtime.Runtime(working_set=working_set)

        with self.assertRaises(SystemExit):
            utils.runtime(['-h'])

        stdout = sys.stdout.getvalue()
        self.assertNotIn('runtime\n', stdout)
        self.assertIn('simple1\n', stdout)
        self.assertIn('simple2\n', stdout)

        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            utils.runtime(['simple1', '-h'])
        stdout = sys.stdout.getvalue()
        self.assertNotIn('runtime\n', stdout)
        self.assertNotIn('simple1\n', stdout)
        self.assertIn('simple2\n', stdout)

    def test_duplication_and_runtime_nested_running(self):
        """
        Nested runtime registration running.
        """

        from calmjs.testing import utils
        assertIn = self.assertIn
        msg = 'executed SimpleRuntime.run %d'

        # We need to be sure that the argparser that got passed into a
        # particular given runtime.run is definitely seen by the given
        # runtime under standard registration workflow.  Create a dummy
        # runtime that will do the assertion.

        class SimpleRuntime(runtime.DriverRuntime, runtime.Runtime):
            def run(self, argparser, **kwargs):
                assertIn(argparser, self.argparser_details)
                raise Exception(msg % id(msg))

        class Dummy(runtime.DriverRuntime):
            # needed here for Python 2 to avoid early quit.
            pass

        def cleanup():
            del utils.simple
            del utils.dummy
        self.addCleanup(cleanup)

        stub_stdouts(self)

        # create a dummy based
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'simple = calmjs.testing.utils:simple\n'
            'dummy = calmjs.testing.utils:dummy\n'
        ),), 'example.simple', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.simple = SimpleRuntime(None, working_set=working_set)
        utils.dummy = Dummy(None, working_set=working_set)

        rt = runtime.Runtime(working_set=working_set)
        rt(['simple', 'dummy', '-vvd'])
        stderr = sys.stderr.getvalue()
        self.assertIn(msg[:-2], stderr)
        self.assertIn(str(id(msg)), stderr)

        # also take the opportunity to test the nested version output.
        rt = runtime.Runtime(
            working_set=working_set, package_name='example.simple')
        with self.assertRaises(SystemExit):
            rt(['simple', 'dummy', '-V'])

        stdout = sys.stdout.getvalue()
        self.assertEqual(3, len(stdout.strip().splitlines()))

    def test_duplication_and_runtime_malformed(self):
        """
        Now for the finale, where we really muck with sanity checking
        where all sorts of entry_point names are permitted.
        """

        from calmjs.testing import utils

        class BadRuntime(runtime.Runtime):
            def entry_point_load_validated(self, entry_point):
                # this_is_fine.png
                return entry_point.load()

        class BadDummy(runtime.DriverRuntime):
            # again, needed by Python 2...
            pass

        utils.foo_runtime = BadDummy(None)
        utils.runtime_foo = BadDummy(None)
        utils.bar_runtime = BadDummy(None)
        utils.runtime_bar = BadDummy(None)

        def cleanup():
            del utils.foo_runtime
            del utils.runtime_foo
            del utils.bar_runtime
            del utils.runtime_bar

        self.addCleanup(cleanup)

        stub_stdouts(self)
        # set up the duplicated and wrongly named entry points, showing
        # why naming standards are needed.
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'calmjs.testing.utils:runtime_foo'
            ' = calmjs.testing.utils:foo_runtime\n'
            'calmjs.testing.utils:foo_runtime'
            ' = calmjs.testing.utils:runtime_foo\n'
            'calmjs.testing.utils:bar_runtime'
            ' = calmjs.testing.utils:bar_runtime\n'
            'calmjs.testing.utils:runtime_bar'
            ' = calmjs.testing.utils:runtime_bar\n'
        ),), 'example5.bad', '1.0')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'calmjs.testing.utils:foo_runtime'
            ' = calmjs.testing.utils:foo_runtime\n'
            'calmjs.testing.utils:runtime_foo'
            ' = calmjs.testing.utils:runtime_foo\n'
            'calmjs.testing.utils:bar_runtime'
            ' = calmjs.testing.utils:runtime_bar\n'
            'calmjs.testing.utils:runtime_bar'
            ' = calmjs.testing.utils:bar_runtime\n'
        ),), 'example6.bad', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        stderr = mocks.StringIO()
        with pretty_logging(
                logger='calmjs.runtime', level=DEBUG, stream=stderr):
            BadRuntime(working_set=working_set).argparser

        # EXPLOSION
        msg = stderr.getvalue()
        self.assertIn("CRITICAL", msg)
        self.assertIn(
            "Runtime instance has been used or initialized improperly.", msg)
        # Naisu Bakuretsu - Megumin.

    @unittest.skipIf(currentframe() is None, 'stack frame not supported')
    def test_duplication_and_runtime_unchecked_recursion(self):
        """
        Nested runtime registration running.
        """

        from calmjs.testing.module3.runtime import BadSimpleRuntime
        from calmjs.testing import utils

        def cleanup():
            del utils.badsimple
        self.addCleanup(cleanup)

        stub_stdouts(self)

        # create a dummy based
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'badsimple = calmjs.testing.utils:badsimple\n'
        ),), 'example.badsimple', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.badsimple = BadSimpleRuntime(None, working_set=working_set)
        # at least minimally greater than expected extra frames
        utils.badsimple.recursionlimit = min(sys.getrecursionlimit(), 100) - 3

        with pretty_logging(
                logger='calmjs.runtime', stream=mocks.StringIO()) as s:
            runtime.Runtime(working_set=working_set).argparser

        # this is like a slimy recursive frog
        stderr = s.getvalue()
        # Yame... YAMEROOOOOOOO
        self.assertIn("CRITICAL", stderr)
        self.assertIn(
            "Runtime subclass at entry_point 'badsimple = "
            "calmjs.testing.utils:badsimple' has override "
            "'entry_point_load_validated' without filtering out "
            "its parent classes; this can be addressed by calling "
            "super(calmjs.testing.module3.runtime.BadSimpleRuntime, self)."
            "entry_point_load_validated(entry_point) "
            "in its implementation, or simply don't override that method",
            stderr
        )

        # as much as I like explosions, the lord of the castle^W console
        # generally dislikes it when an explosion of stack traces get
        # splatter all over the place.  Ensure they are contained, even
        # if the debug mode is enabled.
        stub_stdouts(self)

        with self.assertRaises(SystemExit):
            runtime.main(
                ['-h', '-dvv'],
                runtime_cls=lambda: runtime.Runtime(working_set=working_set),
            )

        stderr = sys.stderr.getvalue()
        stdout = sys.stdout.getvalue()
        self.assertNotIn("maximum recursion depth exceeded", stderr)
        # as much as this broken command should be filtered out, the
        # error actually happened way down the stack, so it's actually
        # available all the way down until where the exception cut it
        # out.
        self.assertIn('badsimple', stdout)

    def test_duplication_and_runtime_not_recursion(self):
        """
        Make sure it explodes normally if standard runtime error.
        """

        from calmjs.testing import utils

        class BadAtInit(runtime.DriverRuntime):
            def init_argparser(self, argparser):
                if argparser is not self.argparser:
                    raise RuntimeError('A fake explosion')

        def cleanup():
            del utils.badatinit
        self.addCleanup(cleanup)

        stub_stdouts(self)

        # create a dummy dist
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'badatinit = calmjs.testing.utils:badatinit\n'
        ),), 'example.badsimple', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.badatinit = BadAtInit(None)

        # and here lies the crimson magician, all out of hp.
        with pretty_logging(
                logger='calmjs.runtime', stream=mocks.StringIO()) as s:
            runtime.Runtime(working_set=working_set).argparser

        self.assertIn(
            "cannot register entry_point "
            "'badatinit = calmjs.testing.utils:badatinit' from "
            "'example.badsimple 1.0' ", s.getvalue()
        )

    def test_runtime_recursion_that_is_totally_our_fault(self):
        """
        If stuff does blow up, don't blame the wrong party if we can
        help it.
        """

        from calmjs.testing import utils
        stub_stdouts(self)

        # We kind of have to punt this, so punt it with a stupid
        # override using an EntryPoint that explodes.

        class TrulyBadAtInit(runtime.Runtime):
            def init_argparser(self, argparser):
                raise RuntimeError('maximum recursion depth exceeded')

        def cleanup():
            del utils.trulybad
        self.addCleanup(cleanup)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'trulybad = calmjs.testing.utils:trulybad\n'
        ),), 'example.badsimple', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.trulybad = TrulyBadAtInit(None)

        with pretty_logging(
                logger='calmjs.runtime', stream=mocks.StringIO()) as s:
            runtime.Runtime(working_set=working_set).argparser

        self.assertIn("maximum recursion depth exceeded", s.getvalue())

    def test_runtime_recursion_that_is_totally_our_fault_checks_safe(self):
        """
        If stuff does blow up, don't blame the wrong party if we can
        help it.
        """

        from calmjs.testing import utils
        stub_stdouts(self)

        # this does not actually have entry_point_load_validated
        class TrulyBadAtInit(runtime.DriverRuntime):
            def init_argparser(self, argparser):
                raise RuntimeError('maximum recursion depth exceeded')

        def cleanup():
            del utils.trulybad
        self.addCleanup(cleanup)

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.runtime]\n'
            'trulybad = calmjs.testing.utils:trulybad\n'
        ),), 'example.badsimple', '1.0')
        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        utils.trulybad = TrulyBadAtInit(None)

        with pretty_logging(
                logger='calmjs.runtime', stream=mocks.StringIO()) as s:
            runtime.Runtime(working_set=working_set).argparser

        self.assertIn("maximum recursion depth exceeded", s.getvalue())


class ArgumentHandlingTestCase(unittest.TestCase):
    """
    The runtime uses argparser with subparsers underneath and argparser
    does not generate useful error messages if it doesn't actually track
    where the bad flags actually got raised.  Here are some of the cases
    that need checking.
    """

    known_cmd = 'cmd'

    def setUp(self):
        stub_stdouts(self)

    def setup_runtime(self):
        # create a working set with our custom runtime entry point
        # TODO should really improve the test case to provide custom
        # runtime instances separate from actual data.
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'cmd = calmjs.npm:npm.runtime',
            ],
        })
        return runtime.Runtime(working_set=working_set, prog='calmjs')

    # for the test, we use the -u flag for the unknown tests as it is
    # unknown to bootstrap and target parser.  Next two are using known
    # flag to before, then after.

    def test_before_extras(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['-u', 'cmd', 'pkg'])
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        self.assertEqual("calmjs: error: unrecognized arguments: -u", err)

    def test_after_extras(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['cmd', 'pkg', '-u'])
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        self.assertEqual("calmjs cmd: error: unrecognized arguments: -u", err)

    def test_before_and_after_extras(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['--view', 'cmd', 'pkg', '-n', '-v'])
        err = sys.stderr.getvalue()
        # --view is recognized in calmjs cmd
        self.assertIn("calmjs: error: unrecognized arguments: --view", err)
        self.assertIn("calmjs cmd: error: unrecognized arguments: -n", err)

    def test_before_known_and_after_unknown(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['-v', 'cmd', 'pkg', '-u'])
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        self.assertEqual("calmjs cmd: error: unrecognized arguments: -u", err)

    def test_before_known_to_after_but_not_after(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['--view', 'cmd', 'pkg'])
        err = sys.stderr.getvalue()
        errline = err.splitlines()[-1].strip()
        self.assertNotIn('calmjs cmd: error:', err)
        self.assertEqual(
            "calmjs: error: unrecognized arguments: --view", errline)

    def test_before_and_after_extras_scattered(self):
        # previously test_before_and_after_extras_known_before, as
        # scattering the -v after will not work.  Since the bootstrap
        # picks up that anyway, might as well force global enablement of
        # this flag.
        rt = self.setup_runtime()
        rt(['-v', 'cmd', 'pkg', '-v'])
        self.assertEqual(rt.log_level, DEBUG)
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        self.assertIn("generating a flattened 'package.json' for 'pkg'", err)

    def test_before_and_after_extras_known_after(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['-i', 'cmd', 'pkg', '-i'])
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        self.assertEqual("calmjs: error: unrecognized arguments: -i", err)

    # other sanity/behavior verification tests

    def test_before_and_after_extras_known_after_missing_arg(self):
        rt = self.setup_runtime()
        with self.assertRaises(SystemExit):
            rt(['-i', 'cmd', '-i'])
        err = sys.stderr.getvalue().splitlines()[-1].strip()
        # exact message differs between py2 and py3
        self.assertIn("calmjs cmd: error: ", err)

    def test_subparser_level_2_missing_argument(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'artifact = calmjs.runtime:artifact',
            ],
            'calmjs.runtime.artifact': [
                'build = calmjs.runtime:artifact_build',
            ],
        })
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['artifact', 'build'])
        # ensure the help for the command itself is printed
        self.assertIn('calmjs artifact build: error', sys.stderr.getvalue())

    def test_subparser_level_2_unrecognized_argument_final(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'artifact = calmjs.runtime:artifact',
            ],
            'calmjs.runtime.artifact': [
                'build = calmjs.runtime:artifact_build',
            ],
        })
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['artifact', 'build', 'package', '--no-such-argument'])
        # ensure the help for the command itself is printed
        self.assertIn('calmjs artifact build: error', sys.stderr.getvalue())

    def test_subparsers_unrecognized_argument_interspersed(self):
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'broken = calmjs.tests.test_runtime:default_cmd',
            ],
        })
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['--1', 'broken', '--2', 'dummy', '--3'])
        # ensure the help for the command itself is printed
        err = sys.stderr.getvalue()
        self.assertIn(
            'calmjs: error: unrecognized arguments: --1', err)
        self.assertIn(
            'calmjs broken: error: unrecognized arguments: --2', err)
        self.assertIn(
            'calmjs broken dummy: error: unrecognized arguments: --3', err)

    def test_subparsers_unrecognized_argument_skipped(self):
        rt = runtime.Runtime(prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['--1', 'artifact', 'build', 'package', '--3'])
        # ensure the help for the command itself is printed
        err = sys.stderr.getvalue()
        self.assertIn(
            'calmjs: error: unrecognized arguments: --1', err)
        self.assertNotIn('calmjs artifact: error', err)
        self.assertIn(
            'calmjs artifact build: error: unrecognized arguments: --3', err)

    def test_subparsers_first_fail(self):
        rt = runtime.Runtime(prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['--1', 'artifact', 'build', 'package'])
        # ensure the help for the command itself is printed
        err = sys.stderr.getvalue()
        self.assertIn('calmjs: error: unrecognized arguments: --1', err)
        self.assertNotIn('calmjs artifact: error', err)
        self.assertNotIn('calmjs artifact build: error', err)

    def test_subparsers_first_also_missing(self):
        rt = runtime.Runtime(prog='calmjs')
        # An underspecified command should also return False.
        with self.assertRaises(SystemExit):
            rt(['--1', 'artifact', '-v', '--2'])
        # ensure the help for the command itself is printed
        err = sys.stderr.getvalue()
        self.assertIn('calmjs: error: unrecognized arguments: --1', err)
        self.assertIn(
            'calmjs artifact: error: unrecognized arguments: --2', err)

    def test_subparsers_unrecognized_argument_issue(self):
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'broken = calmjs.tests.test_runtime:default_cmd',
            ],
        })
        rt = runtime.Runtime(working_set=working_set, prog='calmjs')
        # Emulating a "default" choice for a subparser, however it seems
        # like the default parsing behavior is to do everything on the
        # root parser until a some bare string is encountered which will
        # immediately be assigned to the command.  Still going to spit
        # this warning out, just in case as this is really not a typical
        # situation.
        rt.argparser._subparsers._actions[-1].default = 'broken'
        with self.assertRaises(SystemExit):
            rt(['-vv', '--2', '--3', '--valid'])
        # ensure the help for the command itself is printed
        err = sys.stderr.getvalue()
        self.assertIn(
            "DEBUG calmjs.runtime command for prog='calmjs' is set to "
            "'broken' without being specified as part of the input arguments "
            "- the following error message may contain misleading references",
            err
        )
        self.assertIn(
            'calmjs: error: unrecognized arguments: --2 --3 --valid', err)


class PackageManagerRuntimeAlternativeIntegrationTestCase(unittest.TestCase):
    """
    A comprehensive integration based on a customized environment for
    testing functionality requirements between changes in 1.0 and 2.0,
    where the cli interactive stuff is moved to runtime.  This series of
    tests is based on what were cli unit tests but now those features
    are provided by the runtime.
    """

    def setup_runtime(self):
        stub_stdouts(self)
        remember_cwd(self)
        cwd = mkdtemp(self)
        os.chdir(cwd)
        make_dummy_dist(self, (
            ('requirements.json', json.dumps({
                'name': 'calmpy.pip',
                'require': {
                    'setuptools': '25.1.6',
                },
            })),
        ), 'calmpy.pip', '2.0')

        make_dummy_dist(self, (
            ('requires.txt', '[dev]\ncalmpy.pip'),
        ), 'site', '1.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        # Stub out the underlying data needed for the cli for the tests
        # to test against our custom data for reproducibility.
        stub_item_attr_value(self, dist, 'default_working_set', working_set)
        stub_check_interactive(self, True)
        driver = cli.PackageManagerDriver(
            pkg_manager_bin='mgr', pkgdef_filename='requirements.json',
            dep_keys=('require',),
        )
        return cwd, runtime.PackageManagerRuntime(driver)

    # do note: the runtime is not registered to the root runtime
    # directly, but this is a good enough emulation on how this would
    # behave under real circumstances, as each of these runtime can and
    # should be able to operate as independent entities.

    def test_pkg_manager_view(self):
        cwd, runtime = self.setup_runtime()
        result = runtime.cli_driver.pkg_manager_view('calmpy.pip')
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })
        runtime(['calmpy.pip'])
        result2 = json.loads(sys.stdout.getvalue().strip())
        self.assertEqual(result, result2)

    def test_pkg_manager_init(self):
        cwd, runtime = self.setup_runtime()
        runtime(['--init', 'calmpy.pip'])
        target = join(cwd, 'requirements.json')
        self.assertTrue(exists(target))
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_exists_and_overwrite(self):
        cwd, runtime = self.setup_runtime()
        target = join(cwd, 'requirements.json')

        with open(target, 'w') as fd:
            result = json.dump({"require": {"unrelated": "1.2.3"}}, fd)

        runtime(['--init', 'calmpy.pip'])
        stderr = sys.stderr.getvalue()

        self.assertIn('not overwriting existing ', stderr)
        self.assertIn('requirements.json', stderr)

        with open(target) as fd:
            result = json.load(fd)
        self.assertNotEqual(result, {"require": {"setuptools": "25.1.6"}})

        runtime(['--init', 'calmpy.pip', '--overwrite'])
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_overwrite_interactive(self):
        cwd, runtime = self.setup_runtime()
        target = join(cwd, 'requirements.json')
        with open(target, 'w') as fd:
            result = json.dump({"require": {"unrelated": "1.2.3"}}, fd)

        stub_stdin(self, u'n\n')
        runtime(['--init', 'calmpy.pip', '-i'])
        stdout = sys.stdout.getvalue()
        self.assertIn("differs with ", stdout)
        self.assertIn("Overwrite", stdout)
        self.assertIn("requirements.json'?", stdout)
        with open(target) as fd:
            result = json.load(fd)
        self.assertNotEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

        stub_stdin(self, u'y\n')
        runtime(['--init', 'calmpy.pip', '-i'])
        stdout = sys.stdout.getvalue()
        self.assertIn("differs with ", stdout)
        self.assertIn("Overwrite", stdout)
        self.assertIn("requirements.json'?", stdout)
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_init_merge_interactive(self):
        cwd, runtime = self.setup_runtime()
        target = join(cwd, 'requirements.json')
        with open(target, 'w') as fd:
            result = json.dump({"require": {"unrelated": "1.2.3"}}, fd)

        stub_stdin(self, u'y\n')
        runtime(['--init', 'calmpy.pip', '-i', '-m'])
        stdout = sys.stdout.getvalue()
        self.assertIn("differs with ", stdout)
        self.assertIn("Overwrite", stdout)
        self.assertIn("requirements.json'?", stdout)
        with open(target) as fd:
            result = json.load(fd)
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6", "unrelated": "1.2.3"},
            "name": "calmpy.pip",
        })

    def test_pkg_manager_view_extras(self):
        cwd, runtime = self.setup_runtime()
        runtime(['site'])
        result = json.loads(sys.stdout.getvalue().strip())
        self.assertEqual(result, {
            "require": {},
            "name": "site",
        })

        stub_stdouts(self)
        runtime(['site[dev]'])
        result = json.loads(sys.stdout.getvalue().strip())
        self.assertEqual(result, {
            "require": {"setuptools": "25.1.6"},
            "name": "site",
        })

    def test_pkg_manager_view_malformed(self):
        cwd, runtime = self.setup_runtime()
        runtime(['[dev]'])
        self.assertIn(
            'ValueError: malformed package name(s) specified: [dev]',
            sys.stderr.getvalue(),
        )


@unittest.skipIf(which_npm is None, 'npm not found.')
class RuntimeIntegrationTestCase(unittest.TestCase):

    def setup_runtime(self, cls=runtime.Runtime):
        make_dummy_dist(self, (
            ('package.json', json.dumps({
                'name': 'site',
                'dependencies': {
                    'jquery': '~3.1.0',
                },
            })),
        ), 'example.package1', '1.0')

        make_dummy_dist(self, (
            ('package.json', json.dumps({
                'name': 'site',
                'dependencies': {
                    'underscore': '~1.8.3',
                },
            })),
        ), 'example.package2', '2.0')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'example.package1',
                'example.package2',
            ])),
            ('package.json', json.dumps({
                'dependencies': {
                    'backbone': '~1.3.2',
                },
            })),
        ), 'example.package3', '2.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        # Stub out the underlying data needed for the cli for the tests
        # to test against our custom data for reproducibility.
        stub_item_attr_value(self, dist, 'default_working_set', working_set)
        stub_check_interactive(self, True)

        # Of course, apply a mock working set for the runtime instance
        # so it can use the npm runtime, however we will use a different
        # keyword.  Note that the runtime is invoked using foo.
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'foo = calmjs.npm:npm.runtime',
            ],
        })
        return cls(working_set=working_set)

    def test_npm_init_integration(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        rt = self.setup_runtime()
        rt(['foo', '--init', 'example.package1'])

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')

    def test_npm_install_integration(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        rt = self.setup_runtime()
        rt(['foo', '--install', 'example.package1', 'example.package2'])

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')
        # not foo install, but npm install since entry point specified
        # the actual runtime instance.
        self.assertEqual(self.call_args[0], ([which_npm, 'install'],))

    def test_npm_install_integration_dev_or_prod(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        rt = self.setup_runtime()
        rt(['foo', '--install', 'example.package1', '--development'])
        self.assertEqual(self.call_args[0], ([
            which_npm, 'install', '--production=false'],))

        stub_mod_call(self, cli)
        rt(['foo', '--install', 'example.package1', '--production'])
        self.assertEqual(self.call_args[0], ([
            which_npm, 'install', '--production=true'],))

    def test_npm_install_integration_dev_and_prod(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        rt = self.setup_runtime()
        # production flag always trumps
        rt(['foo', '--install', 'example.package1', '-D', '-P'])
        self.assertEqual(self.call_args[0], ([
            which_npm, 'install', '--production=true'],))

        stub_mod_call(self, cli)
        # production flag always trumps
        rt(['foo', '--install', 'example.package1', '-P', '-D'])
        self.assertEqual(self.call_args[0], ([
            which_npm, 'install', '--production=true'],))

    def test_npm_view(self):
        stub_stdouts(self)
        rt = self.setup_runtime()
        rt(['foo', '--view', 'example.package1', 'example.package2'])
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')

        stub_stdouts(self)
        rt(['foo', 'example.package1', 'example.package2'])
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')

    def test_npm_view_dependencies(self):
        stub_stdouts(self)
        rt = self.setup_runtime()
        rt(['foo', 'example.package3'])
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies'], {
            'jquery': '~3.1.0',
            'underscore': '~1.8.3',
            'backbone': '~1.3.2',
        })

        stub_stdouts(self)
        rt(['foo', 'example.package3', '-E'])
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies'], {
            'backbone': '~1.3.2',
        })

        stub_stdouts(self)
        rt(['foo', 'example.package3', 'example.package2', '--explicit'])
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies'], {
            'backbone': '~1.3.2',
            'underscore': '~1.8.3',
        })

    def test_npm_all_the_actions(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_stdouts(self)
        stub_mod_call(self, cli)
        stub_base_which(self, which_npm)
        rt = self.setup_runtime()
        rt(['foo', '--install', '--view', '--init',
            'example.package1', 'example.package2'])

        # inside stdout
        result = json.loads(sys.stdout.getvalue())
        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')
        # not foo install, but npm install since entry point specified
        # the actual runtime instance.
        self.assertEqual(self.call_args[0], ([which_npm, 'install'],))

    def test_npm_verbose_quiet(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()

        stub_stdouts(self)
        rt(['-v', 'foo', '--init', 'example.package1'])
        self.assertIn("generating a flattened", sys.stderr.getvalue())
        self.assertNotIn("found 'package.json'", sys.stderr.getvalue())

        # extra verbosity shouldn't blow up
        stub_stdouts(self)
        rt(['-vvvv', 'foo', '--init', 'example.package1'])
        self.assertIn("generating a flattened", sys.stderr.getvalue())
        self.assertIn("found 'package.json'", sys.stderr.getvalue())

        # q and v negates each other
        stub_stdouts(self)
        rt(['-v', '-q', 'foo', '--init', 'example.package2'])
        self.assertNotIn("generating a flattened", sys.stderr.getvalue())
        self.assertNotIn("found 'package.json'", sys.stderr.getvalue())
        self.assertIn("WARNING", sys.stderr.getvalue())

        # extra quietness shouldn't blow up
        stub_stdouts(self)
        rt(['-qqqqq', 'foo', '--install', 'example.package2'])
        self.assertNotIn("WARNING", sys.stderr.getvalue())

    def test_npm_init_existing_malform(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()

        # create an existing malformed file
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            fd.write('not a json')
        stub_stdouts(self)
        rt(['foo', '--init', 'example.package2'])
        self.assertIn("ignoring existing malformed", sys.stderr.getvalue())

    def test_npm_interrupted(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()

        stub_stdouts(self)
        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(KeyboardInterrupt))
        rt(['foo', '--install', 'example.package2'])
        self.assertIn("CRITICAL", sys.stderr.getvalue())
        self.assertIn(
            "termination requested; aborted.", sys.stderr.getvalue())

    def test_npm_binary_not_found(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()

        stub_stdouts(self)
        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(IOError))
        rt(['foo', '--install', 'example.package2'])
        self.assertIn("ERROR", sys.stderr.getvalue())
        self.assertIn(
            "invocation of the 'npm' binary failed;", sys.stderr.getvalue())

    def test_npm_binary_not_found_debug(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()
        stub_stdouts(self)

        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(IOError))
        rt(['-d', 'foo', '--install', 'example.package2'])
        stderr = sys.stderr.getvalue()
        self.assertIn("ERROR", stderr)
        self.assertIn(
            "invocation of the 'npm' binary failed;", stderr)
        self.assertIn("terminating due to unexpected error", stderr)
        self.assertIn("Traceback ", stderr)
        self.assertNotIn("(Pdb)", stderr)

    def test_npm_binary_not_found_debugger_disabled(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()
        # stub_stdin(self, u'quit\n')
        stub_stdouts(self)

        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(IOError))
        rt(['-dd', 'foo', '--install', 'example.package2'])

        stderr = sys.stderr.getvalue()
        self.assertIn("ERROR", stderr)
        self.assertIn(
            "invocation of the 'npm' binary failed;", stderr)
        self.assertIn("terminating due to unexpected error", stderr)
        self.assertIn("Traceback ", stderr)
        # Note that since 3.4.0, post_mortem must be explicitly enabled
        # for the runtime class/instance
        self.assertNotIn("(Pdb)", sys.stdout.getvalue())
        self.assertIn(
            "instances of 'calmjs.runtime.Runtime' has disabled post_mortem "
            "debugger", sys.stderr.getvalue()
        )

    def test_npm_binary_not_found_debugger_enabled(self):
        from calmjs import utils

        def fake_post_mortem(*a, **kw):
            sys.stdout.write('(Pdb) ')

        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        # use the CalmJSRuntime which has the post_mortem debugger
        # enabled.
        rt = self.setup_runtime(runtime.CalmJSRuntime)
        stub_stdouts(self)

        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(IOError))
        # utils.post_mortem references pbd.post_mortem, stub that to
        # avoid triggering certain issues.
        stub_item_attr_value(self, utils, 'post_mortem', fake_post_mortem)
        rt(['-dd', 'foo', '--install', 'example.package2'])

        stderr = sys.stderr.getvalue()
        self.assertIn("ERROR", stderr)
        self.assertIn(
            "invocation of the 'npm' binary failed;", stderr)
        self.assertIn("terminating due to unexpected error", stderr)
        self.assertIn("Traceback ", stderr)
        self.assertIn("(Pdb)", sys.stdout.getvalue())

        stub_stdouts(self)
        self.assertNotIn("(Pdb)", stderr)
        rt(['foo', '--install', 'example.package2', '--debugger'])
        self.assertIn("(Pdb)", sys.stdout.getvalue())

    def test_critical_log_exception(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        rt = self.setup_runtime()

        stub_stdouts(self)
        # ensure the binary is not found.
        stub_mod_call(self, cli, fake_error(RuntimeError('fake error')))
        rt(['foo', '--install', 'example.package2'])
        self.assertIn(
            "CRITICAL calmjs.runtime RuntimeError: fake error",
            sys.stderr.getvalue())


class MainIntegrationTestCase(unittest.TestCase):
    """
    For testing the main method
    """

    def test_calmjs_main_console_entry_point(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit) as e:
            runtime.main([])
        self.assertIn('usage', sys.stdout.getvalue())
        self.assertEqual(e.exception.args[0], 1)

    def test_calmjs_main_console_entry_point_help(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit) as e:
            runtime.main(['-h'])
        self.assertIn('npm', sys.stdout.getvalue())
        self.assertEqual(e.exception.args[0], 0)

    def test_calmjs_main_console_version(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit) as e:
            runtime.main(['-V'])
        self.assertEqual(e.exception.args[0], 0)
        self.assertIn('calmjs', sys.stdout.getvalue())

    def test_calmjs_main_console_version_broken(self):
        stub_stdouts(self)
        working_set = pkg_resources.WorkingSet([mkdtemp(self)])
        stub_item_attr_value(self, runtime, 'default_working_set', working_set)
        stub_item_attr_value(
            self, calmjs_argparse, 'default_working_set', working_set)
        # make sure the bad case doesn't just blow up...
        with self.assertRaises(SystemExit) as e:
            runtime.main(['-V'])
        self.assertEqual(e.exception.args[0], 0)
        self.assertIn('? ? from ?', sys.stdout.getvalue())

    def test_calmjs_main_runtime_console_version(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit) as e:
            runtime.main(['npm', '-V'])
        self.assertEqual(e.exception.args[0], 0)
        # reports both versions.
        value = sys.stdout.getvalue()
        self.assertEqual(2, len(value.strip().splitlines()))

    def test_calmjs_main_console_entry_point_install(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_stdouts(self)
        stub_mod_call(self, cli, fake_error(IOError))

        with self.assertRaises(SystemExit) as e:
            runtime.main(['npm', '--init', 'calmjs'])
        # this should be fine, exit code 0
        self.assertEqual(e.exception.args[0], 0)

        with self.assertRaises(SystemExit) as e:
            runtime.main(['npm', '--install', 'calmjs'])
        self.assertIn(
            "invocation of the 'npm' binary failed;", sys.stderr.getvalue())
        self.assertEqual(e.exception.args[0], 1)
