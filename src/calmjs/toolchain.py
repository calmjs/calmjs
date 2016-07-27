# -*- coding: utf-8 -*-
"""
This provides a JavaScript "toolchain".

When I have a hammer every problem starts to look like JavaScript.

Honestly, it's a bit easier to deal with JavaScript when one treats that
as a compilation target.

How this supposed to work?

1) Write raw JS code without any UMD wrappers, but treat everything in
the file as UMD.  Remember to import everything needed using ``require``
and declare the exported things by assigning it to ``exports``.
2) Leave that file somewhere in the src directory, along with Python
code.
3) Run compile.  They will be compiled into the corresponding thing that
correlates to the Pythonic namespace identifiers.

At least this is the idea, have to see whether this idea actually end up
being sane (it won't be sane, when the entire thing was insane to begin
with).

One final thing: es6 does have modules, imports and exports done in a
different but dedicated syntax.  Though to really support them a proper
es6 compatible environment will be needed, however those are not a norm
at the moment yet, especially given the fact that browsers do not have
support for them quite just yet as of mid 2016.
"""

from __future__ import unicode_literals

import codecs
import logging
import shutil
import errno
from os import mkdir
from os import strerror
from os.path import join
from os.path import exists
from os.path import isfile
from os.path import isdir
from tempfile import mkdtemp

logger = logging.getLogger(__name__)


def raise_os_error(_errno):
    """
    Helper for raising the correct exception under Python 3 while still
    being able to raise the same common exception class in Python 2.7.
    """

    raise OSError(_errno, strerror(_errno))


def _opener(*a):
    return codecs.open(*a, encoding='utf-8')


def null_transpiler(reader, writer):
    writer.write(reader.read())


class Spec(dict):

    def __init__(self, *a, **kw):
        super(Spec, self).__init__(*a, **kw)
        self._callbacks = {}

    def update_selected(self, other, selected):
        self.update({k: other[k] for k in selected})

    def add_callback(self, name, f, *a, **kw):
        self._callbacks[name] = self._callbacks.get(name, [])
        self._callbacks[name].append((f, a, kw))

    def do_callbacks(self, name):
        callbacks = self._callbacks.get(name, [])
        while callbacks:
            try:
                # cleanup basically done lifo (last in first out)
                values = callbacks.pop()
                callback, a, kw = values
                if not ((callable(callback)) and
                        isinstance(a, tuple) and
                        isinstance(kw, dict)):
                    raise TypeError
            except ValueError:
                logger.info('Spec callback extraction error: got %s', values)
            except TypeError:
                logger.info('Spec malformed: got %s', values)
            else:
                try:
                    callback(*a, **kw)
                except Exception:
                    logger.exception('Spec callback execution: got %s', values)


class Toolchain(object):
    """
    For shared methods between all toolchains.
    """

    def __init__(self):
        self.transpiler = NotImplemented

    def compile(self, source, target):
        logger.info('Compiling %s to %s', source, target)
        with _opener(source, 'r') as reader, _opener(target, 'w') as writer:
            self.transpiler(reader, writer)

    def _gen_req_src_targets(self, d):
        # name = pythonic module name
        # reqold = the commonjs require format to the source
        # source = the source path
        # reqnew = the commonjs require format to the target
        # target = the target write path

        for name, reqold in d.items():
            source = reqold + '.js'
            reqnew = name
            target = reqnew + '.js'
            yield reqold, name, reqnew, source, target

    def compile_all(self, spec):
        compiled_paths = {}
        bundled_paths = {}
        module_names = []

        transpile_source_map = spec.get('transpile_source_map', {})
        bundled_source_map = spec.get('bundled_source_map', {})

        for reqold, name, reqnew, source, target in self._gen_req_src_targets(
                transpile_source_map):
            compiled_paths[name] = reqnew
            module_names.append(name)
            self.compile(source, join(spec['build_dir'], target))

        for reqold, name, reqnew, source, target in self._gen_req_src_targets(
                bundled_source_map):
            bundled_paths[name] = reqnew
            if isfile(source):
                module_names.append(name)
                shutil.copy(source, join(spec['build_dir'], target))
            elif isdir(reqold):
                shutil.copytree(reqold, join(spec['build_dir'], reqnew))

        spec.update_selected(locals(), [
            'compiled_paths', 'bundled_paths', 'module_names'])

    def assemble(self, spec):
        """
        Accept all compiled paths; should return the manifest.
        """

        raise NotImplementedError

    def link(self, spec):
        """
        Should pass in the manifest path to the final JS linker, which
        is typically the bundler.
        """

        raise NotImplementedError

    def finalize(self, spec):
        """
        Optional finalizing step, where further usage of the build_dir,
        scripts and/or results are needed.  This can be used to run some
        specific scripts through node's import system directly on the
        pre-linked assembled files, for instance.

        This step is optional.
        """

    def _calf(self, spec):
        """
        The main call, assuming everything is prepared.
        """

        self.compile_all(spec)
        self.assemble(spec)
        self.link(spec)
        self.finalize(spec)

    def calf(self, spec):
        """
        Typical safe usage is this, which sets everything that could be
        problematic up.

        Requires the filename which everything will be produced to.
        """

        if 'build_dir' not in spec:
            tempdir = mkdtemp()
            spec.add_callback('cleanup', shutil.rmtree, tempdir)
            build_dir = join(tempdir, 'build')
            mkdir(build_dir)
            spec['build_dir'] = build_dir
        else:
            if not exists(spec['build_dir']):
                raise_os_error(errno.ENOTDIR)

        try:
            self._calf(spec)
        finally:
            spec.do_callbacks('cleanup')

    def __call__(self, spec):
        """
        Alias, also make this callable directly.
        """

        self.calf(spec)


class NullToolchain(Toolchain):
    """
    A null toolchain that does nothing except mayble move some files
    around.
    """

    def __init__(self):
        self.transpiler = null_transpiler

    def assemble(self, spec):
        """
        Does absolutely nothing
        """

    def link(self, spec):
        """
        Does absolutely nothing
        """
