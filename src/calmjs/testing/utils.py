import tempfile
from os import makedirs
from os.path import join
from shutil import rmtree
from types import ModuleType
from unittest import TestCase

from pkg_resources import PathMetadata
from pkg_resources import Distribution

from calmjs.testing import module3


TMPDIR_ID = '_calmjs_testing_tmpdir'


def _cleanup_mkdtemp_mark(testcase_inst):
    if hasattr(testcase_inst, TMPDIR_ID):
        delattr(testcase_inst, TMPDIR_ID)


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


def mkdtemp_single(testcase_inst):
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
                    pkgname='dummydist', version='0.0'):
    """
    Test case helper function for creating a distribution dummy that
    uses PathMetadata for the foundation for integration level testing.
    """

    tmpdir = mkdtemp_single(testcase_inst)
    egg_info = '%s-%s.egg-info' % (pkgname, version)
    egg_info_dir = join(tmpdir, egg_info)
    makedirs(egg_info_dir)
    metadata = PathMetadata(tmpdir, egg_info_dir)

    for fn, data in metadata_map:
        with open(join(egg_info_dir, fn), 'w') as fd:
            fd.write(data)

    return Distribution(
        tmpdir, project_name=pkgname, metadata=metadata, version=version)
