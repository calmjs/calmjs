# -*- coding: utf-8 -*-
import json
import tempfile
import textwrap
import os
import sys
import warnings
from os import makedirs
from os.path import exists
from os.path import join
from os.path import dirname
from os.path import isdir
from os.path import realpath
from shutil import rmtree as rmtree_
from types import ModuleType
from unittest import TestCase
from unittest import SkipTest

import pkg_resources
from pkg_resources import PathMetadata
from pkg_resources import Distribution
from pkg_resources import WorkingSet

# Do not invoke/import the root calmjs namespace here.  If modules from
# there are needed, the import must be done from within the scope that
# requires it to avoid possible circular imports.
from . import module3
from .mocks import StringIO

TMPDIR_ID = '_calmjs_testing_tmpdir'
tests_suffix = '.tests'


def rmtree(path):
    try:
        rmtree_(path)
    except (IOError, OSError):
        # As it turns out nested node_modules directories are a bad
        # idea, especially on Windows.  It turns out this situation
        # is rather common, so we need a way to deal with this.  As
        # it turns out a workaround exists around this legacy win32
        # issue through this proprietary prefix:
        path_ = '\\\\?\\' + path if sys.platform == 'win32' else path

        # and try again
        try:
            rmtree_(path_)
        except (IOError, OSError):
            pass

        # Don't blow the remaining teardown up if it fails anyway.
        if exists(path):
            warnings.warn("rmtree failed to remove %r" % path)


def _cleanup_mkdtemp_mark(testcase_inst):
    if hasattr(testcase_inst, TMPDIR_ID):
        delattr(testcase_inst, TMPDIR_ID)


def fake_error(exception):
    def stub(*a, **kw):
        raise exception
    return stub


def mkdtemp_realpath():
    return realpath(tempfile.mkdtemp())


def create_fake_bin(path, name):
    """
    Create a fake executable with name at path.  For windows we will
    need a valid PATHEXT; typically .exe will suffice.
    """

    fn = name if sys.platform != 'win32' else name + '.exe'
    target = join(path, fn)
    with open(target, 'w'):
        pass
    os.chmod(target, 0o777)
    return target


def generate_integration_working_set(
        working_dir, registry_id='calmjs.module.simulated',
        pkgman_filename='package.json', extras_calmjs_key='fake_modules',
        extra_working_sets=sys.path):
    """
    Generate a comprehensive integration testing environment for test
    cases in other packages that integrates with calmjs.

    Arguments:

    working_dir
        The working directory to write all the distribution information
        and dummy test scripts to.

    registry_id
        The registry id to be used for the dummy module registry.
        Default is 'calmjs.module.simulated'

    pkgman_filename
        The package manager's expected filename.  Defaults to the npm
        default of 'package.json'.

    extras_calmjs_key
        The extras keys for the extras_calmjs definition.  Defaults to
        fake_modules.

    Returns a tuple of the mock working set and the registry.
    """

    from calmjs.loaderplugin import MODULE_LOADER_SUFFIX
    from calmjs.dist import EXTRAS_CALMJS_JSON

    def make_entry_points(registry_id, *raw):
        return '\n'.join(['[%s]' % registry_id] + list(raw))

    make_dummy_dist(None, (
        ('entry_points.txt', '\n'.join([
            make_entry_points(
                'calmjs.registry',
                registry_id + ' = calmjs.module:ModuleRegistry',
                registry_id + '.tests = calmjs.module:ModuleRegistry',
                registry_id + MODULE_LOADER_SUFFIX +
                ' = calmjs.loaderplugin:ModuleLoaderRegistry',
            ),
            make_entry_points(
                'calmjs.extras_keys',
                '%s = enabled' % extras_calmjs_key,
            ),
        ])),
        ('calmjs_module_registry.txt', registry_id),
    ), 'calmjs.simulated', '420', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
        ])),
    ), 'security', '9999', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
            'security',
            'calmjs.simulated',
        ])),
        (pkgman_filename, json.dumps({
            'dependencies': {
                'left-pad': '~1.1.1',
            },
            'devDependencies': {
                'sinon': '~1.15.0',
            },
        })),
        ('entry_points.txt', make_entry_points(
            registry_id,
            'framework = framework',
        )),
        (EXTRAS_CALMJS_JSON, json.dumps({
            extras_calmjs_key: {
                'jquery': 'jquery/dist/jquery.min.js',
                'underscore': 'underscore/underscore-min.js',
            },
        })),
    ), 'framework', '2.4', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
            'framework>=2.1',
        ])),
        (pkgman_filename, json.dumps({
            'dependencies': {
                'jquery': '~2.0.0',
                'underscore': '~1.7.0',
            },
        })),
        (EXTRAS_CALMJS_JSON, json.dumps({
            extras_calmjs_key: {
                'jquery': 'jquery/dist/jquery.min.js',
            },
        })),
        ('entry_points.txt', '\n'.join([
            make_entry_points(
                registry_id,
                'widget = widget',
            ),
            make_entry_points(
                registry_id + MODULE_LOADER_SUFFIX,
                'css = css[css]',
            )
        ])),
    ), 'widget', '1.1', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
            'framework>=2.2',
            'widget>=1.0',
        ])),
        (pkgman_filename, json.dumps({
            'dependencies': {
                'backbone': '~1.3.0',
                'jquery-ui': '~1.12.0',
            },
        })),
        ('entry_points.txt', make_entry_points(
            registry_id,
            'forms = forms',
        )),
    ), 'forms', '1.6', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
            'framework>=2.1',
        ])),
        (pkgman_filename, json.dumps({
            'dependencies': {
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0',
            },
        })),
        (EXTRAS_CALMJS_JSON, json.dumps({
            extras_calmjs_key: {
                'underscore': 'underscore/underscore.js',
            },
            '_bad_dir_': {
                'unsupported': 'unsupported',
            },
        })),
        ('entry_points.txt', make_entry_points(
            registry_id,
            'service = service',
            'service.rpc = service.rpc',
        )),
    ), 'service', '1.1', working_dir=working_dir)

    make_dummy_dist(None, (
        ('requires.txt', '\n'.join([
            'framework>=2.1',
            'widget>=1.1',
            'forms>=1.6',
        ])),
        (pkgman_filename, json.dumps({
            'name': 'site',
            'dependencies': {
                'underscore': '~1.8.0',
                'jquery': '~3.0.0',
            },
        })),
        (EXTRAS_CALMJS_JSON, json.dumps({
            extras_calmjs_key: {
                'jquery': 'jquery/dist/jquery.js',
                'underscore': 'underscore/underscore.js',
            },
        })),
    ), 'site', '2.0', working_dir=working_dir)

    # The mocked mock_working_set
    mock_working_set = WorkingSet([working_dir] + extra_working_sets)

    contents = (
        (('framework', 'lib.js'), '''
            exports.Core = 'framework.lib.Core';
        '''),
        (('widget', 'core.js'), '''
            var framework_lib = require('framework/lib');
            var Core = framework_lib.Core;
            exports.Core = Core + '/' + 'widget.core.Core';
        '''),
        (('widget', 'richedit.js'), '''
            var core = require('widget/core');
            exports.RichEditWidget = 'widget.richedit.RichEditWidget';
        '''),
        (('widget', 'datepicker.js'), '''
            var _ = require('underscore');
            var core = require('widget/core');
            exports.DatePickerWidget = 'widget.datepicker.DatePickerWidget';
        '''),
        (('forms', 'ui.js'), '''
            var $ = require('jquery');
            var richedit = require('widget/richedit');
            var datepicker = require('widget/datepicker');
            exports.RichForm = [
                'forms.ui.RichForm',
                richedit.RichEditWidget,
                datepicker.DatePickerWidget,
            ];
        '''),
        (('service', 'endpoint.js'), '''
            var framework_lib = require('framework/lib');
            var Core = framework_lib.Core;
            exports.Endpoint = 'service.endpoint.Endpoint';
        '''),
        (('service', 'rpc', 'lib.js'), '''
            var framework_lib = require('framework/lib');
            var Core = framework_lib.Core;
            exports.Library = 'service.rpc.lib.Library';
        '''),
    )

    extras_sources = [
        'jquery/dist/jquery.js',
        'jquery/dist/jquery.min.js',
        'underscore/underscore.js',
        'underscore/underscore-min.js',
    ]

    # Generate the extras, too
    for source in extras_sources:
        fn = source.split('/')
        target = join(working_dir, extras_calmjs_key, *fn)
        base = dirname(target)
        if not isdir(base):
            makedirs(base)
        with open(target, 'w') as fd:
            # return a module that returns the name of the file.
            fd.write("define([], function () { return '%s'; });" % source)

    # These attributes are directly
    records = {}
    package_module_map = {}

    # I kind of want to do something like
    # registry = ModuleRegistry(registry_id, _working_set=mock_working_set)
    # However, this requires actually stubbing out a bunch of other
    # stuff and I really don't want to muck about with imports for a
    # setup... so we are going to mock the registry like so:

    for ep in mock_working_set.iter_entry_points(registry_id):
        package_module_map[ep.dist.project_name] = package_module_map.get(
            ep.dist.project_name, [])
        package_module_map[ep.dist.project_name].append(ep.module_name)

    for fn, content in contents:
        target = join(working_dir, *fn)
        modname = '/'.join(fn)[:-3]
        record_key = '.'.join(fn[:-1])
        records[record_key] = records.get(record_key, {})
        records[record_key][modname] = target
        base = dirname(target)
        if not isdir(base):
            makedirs(base)
        with open(target, 'w') as fd:
            fd.write(textwrap.dedent(content).lstrip())

    makedirs(join(working_dir, '_bad_dir_'))
    with open(join(working_dir, '_bad_dir_', 'unsupported'), 'w') as fd:
        pass

    return mock_working_set


def instantiate_integration_registries(
        mock_working_set, root_registry, *registry_names):
    """
    Provide a root registry instance, and the remaining arguments being
    the identifiers that should be instantiated.
    """

    # In order for the registries to become instantiated with all the
    # intended data through the system, the "modules" defined above will
    # need to be available in the Python import system with the paths
    # set correctly.  Fortunately, the actual import is done through a
    # function provided by the calmjs.base module, such that the root
    # Python module/import system do not need to be polluted.  That
    # said, this function must not effect any other permanent changes to
    # the runtime environment.

    from types import ModuleType
    from calmjs import base as calmjs_base
    import calmjs.registry

    def _import_module(module_name):
        try:
            return original_import_module(module_name)
        except ImportError:
            # pretend all modules are real by providing stubs
            module = ModuleType(module_name)
            module._fake = True
            return module

    if root_registry is None:
        root_registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=mock_working_set,
            reserved=None,
        )
    else:
        # refresh the _entry_points by transplanting one from a fresh
        # instance, to ensure that any new entry points added to the
        # working set is also recorded.
        root_registry._entry_points = calmjs.registry.Registry(
            root_registry.registry_name, _working_set=mock_working_set,
            reserved=None,
        )._entry_points

    try:
        (original_import_module, calmjs_base._import_module) = (
            calmjs_base._import_module, _import_module)
        pkg_resources.working_set, _pkg_resources_ws = (
            mock_working_set, pkg_resources.working_set)
        calmjs_base.working_set, _calmjs_base_ws = (
            mock_working_set, calmjs_base.working_set)
        original_inst, calmjs.registry._inst = (
            calmjs.registry._inst, root_registry)
        for name in registry_names:
            # drop the old one
            root_registry.records.pop(name, None)
            root_registry.get(name)
    finally:
        calmjs.registry._inst = original_inst
        pkg_resources.working_set = _pkg_resources_ws
        calmjs_base.working_set = _calmjs_base_ws
        calmjs_base._import_module = original_import_module

    # also tie the knot before returning the registry.
    root_registry.records[root_registry.registry_name] = root_registry
    return root_registry


def generate_root_integration_environment(
        working_dir, registry_id='calmjs.module.simulated',
        pkgman_filename='package.json', extras_calmjs_key='fake_modules',
        extra_working_sets=sys.path):
    from calmjs.loaderplugin import MODULE_LOADER_SUFFIX

    mock_working_set = generate_integration_working_set(
        working_dir,
        registry_id=registry_id,
        pkgman_filename=pkgman_filename,
        extras_calmjs_key=extras_calmjs_key,
        extra_working_sets=extra_working_sets,
    )
    root_registry = instantiate_integration_registries(
        mock_working_set,
        None,
        registry_id,
        registry_id + MODULE_LOADER_SUFFIX,
        registry_id + tests_suffix,
    )
    return mock_working_set, root_registry,


def generate_integration_environment(
        working_dir, registry_id='calmjs.module.simulated',
        pkgman_filename='package.json', extras_calmjs_key='fake_modules',
        extra_working_sets=sys.path):
    """
    Compatibility with calmjs<3.3.0
    """

    from calmjs.loaderplugin import MODULE_LOADER_SUFFIX

    mock_working_set, root_registry = generate_root_integration_environment(
        working_dir,
        registry_id=registry_id,
        pkgman_filename=pkgman_filename,
        extras_calmjs_key=extras_calmjs_key,
        extra_working_sets=extra_working_sets,
    )
    return (
        mock_working_set,
        root_registry.get(registry_id),
        root_registry.get(registry_id + MODULE_LOADER_SUFFIX),
        root_registry.get(registry_id + tests_suffix),
    )


def setup_class_integration_environment(cls, **kw):
    import calmjs.registry
    from calmjs import dist as calmjs_dist
    from calmjs import base
    from calmjs.loaderplugin import MODULE_LOADER_SUFFIX
    cls.dist_dir = mkdtemp_realpath()
    working_set, inst = generate_root_integration_environment(
        cls.dist_dir, **kw)

    cls.root_registry = inst
    cls.registry_name = kw.get('registry_id', 'calmjs.module.simulated')
    cls.test_registry_name = cls.registry_name + tests_suffix
    cls.loader_registry_name = cls.registry_name + MODULE_LOADER_SUFFIX
    cls.working_set = working_set

    # stubs
    cls._old_root_registry, calmjs.registry._inst = calmjs.registry._inst, inst
    cls.root_working_set, calmjs_dist.default_working_set = (
        calmjs_dist.default_working_set, working_set)
    base.working_set = working_set


def teardown_class_integration_environment(cls):
    from calmjs import dist as calmjs_dist
    from calmjs import base
    import calmjs.registry
    rmtree(cls.dist_dir)
    calmjs_dist.default_working_set = cls.root_working_set
    base.working_set = cls.root_working_set
    calmjs.registry._inst = cls._old_root_registry


def setup_class_install_environment(cls, driver_cls, pkg_names, **kws):
    """
    For TestCase.setUpClass classmethod to build an environment for the
    duration of the lifetime of an instance of a given TestCase class.
    This also creates temporary directory assigned to cls._cls_tmpdir
    attribute which the caller is responsible for removing in its
    tearDownClass class method.

    The attributes it assign are the cls._env_root and self._env_path;
    the _env_root is the root of the environment, either the one
    specified in the alternative mode or the temporary directory.  The
    _env_path is the PATH equivalent for the location of node_modules
    binaries, and this value is safe for assignment to a Toolchain (or
    BaseDriver) instances to force usage of binaries from that location.

    It has an alternative mode, where if an environmental variable
    CALMJS_TEST_ENV is passed, that directory will be used to assign
    the _env_path variable the node_modules binary directory specified
    by that variable.

    Caller is also responsible for providing the appropriate package
    manager driver class.
    """

    from calmjs.cli import PackageManagerDriver
    if not issubclass(driver_cls, PackageManagerDriver):
        raise TypeError('driver_cls must be a PackageManagerDriver')

    test_env = os.environ.get('CALMJS_TEST_ENV')
    if not test_env:
        cls._env_root = cls._cls_tmpdir = realpath(tempfile.mkdtemp())
        driver = driver_cls(working_dir=cls._cls_tmpdir)
        driver.pkg_manager_install(pkg_names, **kws)
        # Save this as the env_path for tools.
        # reason this is done here rather than using setup_transpiler
        # method is purely because under environments that have the
        # standard node_modules/.bin part of the PATH, it never gets
        # set, and then if the test changes the working directory, it
        # will then not be able to find the runtime needed.
        cls._env_path = join(cls._cls_tmpdir, 'node_modules', '.bin')
    else:
        # This is for static test environment for development, not
        # generally suitable for repeatable tests
        cls._env_root = realpath(test_env)
        if not exists(join(cls._env_root, 'node_modules')):
            raise SkipTest("no 'node_modules' directory in %s" % cls._env_root)
        # create the root regardless to permit consistent cleanup.
        cls._cls_tmpdir = realpath(tempfile.mkdtemp())
        cls._env_path = join(cls._env_root, 'node_modules', '.bin')


def mkdtemp(testcase_inst):
    """
    A temporary directory creation helper function that cleans itself up
    by removing itself after the TestCase instance completes the current
    running test.  Requires a TestCase instance.
    """

    if not isinstance(testcase_inst, TestCase):
        raise TypeError('Must be called with a TestCase instance')

    if not callable(getattr(testcase_inst, 'addCleanup', None)):
        raise TypeError(
            '%s does not support addCleanup; package requires python2.7+ or '
            'unittest2.' % testcase_inst)

    def cleanup(tmpdir):
        cwd = os.getcwd()
        if exists(tmpdir):
            if cwd.startswith(tmpdir):
                os.chdir(join(tmpdir, os.path.pardir))
            rmtree(tmpdir)

    # create the temporary dir and add the cleanup for that immediately.
    tmpdir = mkdtemp_realpath()
    testcase_inst.addCleanup(cleanup, tmpdir)
    return tmpdir


def mkdtemp_singleton(testcase_inst):
    """
    A temporary directory creation helper function that cleans itself up
    by removing itself after the TestCase instance completes the current
    running test.  This one will reuse the initial returned path on all
    subsequent calls.  Requires a TestCase instance.
    """

    if getattr(testcase_inst, TMPDIR_ID, None):
        # If already exist, return that.
        return getattr(testcase_inst, TMPDIR_ID)

    tmpdir = mkdtemp(testcase_inst)
    testcase_inst.addCleanup(_cleanup_mkdtemp_mark, testcase_inst)

    # mark the testcase with it
    setattr(testcase_inst, TMPDIR_ID, tmpdir)

    return tmpdir


def make_multipath_module3(testcase_inst):
    """
    Test case helper function that creates a multi-pathed module that
    can be commonly found in situations where multiple Python packages
    have declared the same namespace yet lives in different package
    dirs.  This function replicates by returning a dummy Module that
    has this, and also create a dummy script file that make use of
    something that exists in the real namespace, all inside a dummy
    temporary directory that will be cleaned up.
    """

    tmpdir = mkdtemp(testcase_inst)

    # We will cheat a bit to obtain what we need to do the test.
    # First create a tmpdir where the "alternative" module path will
    # be provided with a dummy JavaScript module file
    target = join(tmpdir, 'calmjs.testing.module3', 'src',
                  'calmjs', 'testing', 'module3')
    makedirs(target)
    index_js = join(target, 'index.js')

    with open(index_js, 'w') as fd:
        fd.write('"use strict";\n')
        fd.write('var math = require("calmjs/testing/module3/math");\n')
        fd.write('exports.main = function() {\n')
        fd.write('    console.log(math.add(1 + 1));\n')
        fd.write('};\n')

    # Then we create a dummy Python module that merges the paths
    # provided by the real module3 with the fake one we have.

    fake_modpath = [target] + module3.__path__
    module = ModuleType('calmjs.testing.module3')
    module.__path__ = fake_modpath

    return module, index_js


def make_dummy_dist(testcase_inst, metadata_map=(),
                    pkgname='dummydist', version='0.0', working_dir=None):
    """
    Test case helper function for creating a distribution dummy that
    uses PathMetadata for the foundation for integration level testing.
    """

    if working_dir is None:
        working_dir = mkdtemp_singleton(testcase_inst)

    egg_info = '%s-%s.egg-info' % (pkgname, version)
    egg_info_dir = join(working_dir, egg_info)
    if not exists(egg_info_dir):
        makedirs(egg_info_dir)
    metadata = PathMetadata(working_dir, egg_info_dir)

    for fn, data in metadata_map:
        with open(join(egg_info_dir, fn), 'w') as fd:
            fd.write(data)

    return Distribution(
        working_dir, project_name=pkgname, metadata=metadata, version=version)


def remember_cwd(testcase_inst):
    """
    Remember the current working directory and restore when test is
    done.
    """

    cwd = os.getcwd()

    def cleanup():
        os.chdir(cwd)

    testcase_inst.addCleanup(cleanup)


# I guess a bunch of the following stub functions can be replace by
# mocks, but so far it's managable and limits extra dependencies on <3.5


def stub_item_attr_value(testcase_inst, item, attr, value):
    """
    Stub item.attr with value
    """

    def cleanup():
        setattr(item, attr, original)

    original = getattr(item, attr)
    testcase_inst.addCleanup(cleanup)
    setattr(item, attr, value)


def stub_base_which(testcase_inst, fake_cmd=None):
    """
    A stub on the which in the base module so that it returns the
    identity if no specific targets are given, otherwise return that.
    """

    from calmjs import base

    def fake_which(cmd, *a, **kw):
        if fake_cmd is None:
            return cmd
        return fake_cmd

    stub_item_attr_value(testcase_inst, base, 'which', fake_which)


def stub_mod_call(testcase_inst, mod, f=None):
    def fake_call(*a, **kw):
        testcase_inst.call_args = (a, kw)

    if f is None:
        f = fake_call

    def cleanup():
        # Restore original module level functions
        mod.call = call
        if hasattr(testcase_inst, 'call_args'):
            delattr(testcase_inst, 'call_args')

    testcase_inst.addCleanup(cleanup)
    testcase_inst.call_args = None
    call, mod.call = mod.call, f


def stub_mod_check_output(testcase_inst, mod, f=None):
    def fake_check_output(*a, **kw):
        testcase_inst.check_output_args = (a, kw)
        return testcase_inst.check_output_answer

    if f is None:
        f = fake_check_output

    def cleanup():
        mod.check_output = check_output
        if hasattr(testcase_inst, 'check_output_answer'):
            delattr(testcase_inst, 'check_output_answer')

    testcase_inst.addCleanup(cleanup)
    testcase_inst.check_output_answer = None
    check_output, mod.check_output = mod.check_output, f


def stub_check_interactive(testcase_inst, result):
    """
    Replace the check_interactive function for the target module so that
    it will return result.
    """

    from calmjs import ui

    def check_interactive():
        return result

    ui.check_interactive, original_check_interactive = (
        check_interactive, ui.check_interactive)

    def restore():
        ui.check_interactive = original_check_interactive

    testcase_inst.addCleanup(restore)


def stub_mod_check_interactive(testcase_inst, module, result):
    """
    Deprecated: given that all previous invocations pretty much has the
    module argument as [cli], we can safely ignore that.
    """

    return stub_check_interactive(testcase_inst, result)


def stub_mod_working_set(testcase_inst, modules, working_set):
    """
    Replace the working_set for the target modules
    """

    def restore(module, working_set):
        module.working_set = working_set

    for module in modules:
        testcase_inst.addCleanup(restore, module, module.working_set)
        module.working_set = working_set


def stub_os_environ(testcase_inst):
    """
    Not really stubbing it, but more restoring it to whatever it was
    when test concludes.
    """

    original_environ = {}
    original_environ.update(os.environ)

    def cleanup():
        os.environ.clear()
        os.environ.update(original_environ)

    testcase_inst.addCleanup(cleanup)


def stub_stdin(testcase_inst, inputs):
    stdin = testcase_inst._stdin = sys.stdin

    def cleanup():
        sys.stdin = stdin

    testcase_inst.addCleanup(cleanup)
    sys.stdin = StringIO(inputs)


def stub_stdouts(testcase_inst):
    stderr = testcase_inst._stderr = sys.stderr
    stdout = testcase_inst._stdout = sys.stdout

    def cleanup():
        sys.stderr = stderr
        sys.stdout = stdout

    testcase_inst.addCleanup(cleanup)
    sys.stderr = StringIO()
    sys.stdout = StringIO()
