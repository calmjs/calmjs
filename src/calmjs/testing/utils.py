import tempfile
import os
import sys
from os import makedirs
from os.path import join
from shutil import rmtree
from types import ModuleType
from unittest import TestCase

from pkg_resources import PathMetadata
from pkg_resources import Distribution

# Do not invoke/import the calmjs namespace here.  If they are needed
# please import from a scope.
from . import module3
from .mocks import StringIO


TMPDIR_ID = '_calmjs_testing_tmpdir'


def _cleanup_mkdtemp_mark(testcase_inst):
    if hasattr(testcase_inst, TMPDIR_ID):
        delattr(testcase_inst, TMPDIR_ID)


def fake_error(exception):
    def stub(*a, **kw):
        raise exception
    return stub


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

    # create the temporary dir and add the cleanup for that immediately.
    tmpdir = tempfile.mkdtemp()
    testcase_inst.addCleanup(rmtree, tmpdir)
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

def stub_dist_flatten_egginfo_json(testcase_inst, modules, working_set):
    """
    Replace the flatten_egginfo_json import from dist for the specified
    modules.
    """

    from calmjs import dist
    from calmjs import npm

    original_flatten_egginfo_json = dist.flatten_egginfo_json

    def flatten_egginfo_json(
            pkg_name, filename=npm.PACKAGE_JSON, dep_keys=dist.DEP_KEYS):
        return original_flatten_egginfo_json(
            pkg_name, filename=filename, dep_keys=dep_keys,
            working_set=working_set
        )

    def restore(module):
        module.flatten_egginfo_json = original_flatten_egginfo_json

    for module in modules:
        testcase_inst.addCleanup(restore, module)
        module.flatten_egginfo_json = flatten_egginfo_json


def stub_mod_call(testcase_inst, mod, f=None):
    def fake_call(*a, **kw):
        testcase_inst.call_args = (a, kw)

    # if f:
    #     fake_call = f

    def cleanup():
        # Restore original module level functions
        mod.call = call
        if hasattr(testcase_inst, 'call_args'):
            delattr(testcase_inst, 'call_args')

    testcase_inst.addCleanup(cleanup)
    testcase_inst.call_args = None
    call, mod.call = mod.call, fake_call


def stub_mod_check_output(testcase_inst, mod, f=None):
    def fake_check_output(*a, **kw):
        testcase_inst.check_output_args = (a, kw)
        return testcase_inst.check_output_answer

    if f:
        fake_check_output = f   # noqa: F811

    def cleanup():
        mod.check_output = check_output
        if hasattr(testcase_inst, 'check_output_answer'):
            delattr(testcase_inst, 'check_output_answer')

    testcase_inst.addCleanup(cleanup)
    testcase_inst.check_output_answer = None
    check_output, mod.check_output = mod.check_output, fake_check_output


def stub_mod_check_interactive(testcase_inst, modules, result):
    """
    Replace the check_interactive function for the target module so that
    it will return result.
    """

    from calmjs import cli

    original_check_interactive = cli.check_interactive

    def check_interactive():
        return result

    def restore(module):
        module.check_interactive = original_check_interactive

    for module in modules:
        testcase_inst.addCleanup(restore, module)
        module.check_interactive = check_interactive


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
