# -*- coding: utf-8 -*-
"""
Assortment of utility functions.
"""

from __future__ import absolute_import

import logging
import os
import re
import sys
from contextlib import contextmanager
from functools import partial
from json import dump
from json import dumps
from locale import getpreferredencoding
from os import strerror
from os.path import curdir
from os.path import defpath
from os.path import normcase
from os.path import pathsep
from pdb import post_mortem
from pdb import Pdb
from subprocess import Popen
from subprocess import PIPE

locale = getpreferredencoding()

# sys.platform have required keys for environment variables for Popen
_PLATFORM_ENV_KEYS = {
    # win32 specific keys
    # APPDATA
    #     Some node scripts really need this for some reason?
    # PATH
    #     Well, if it's not available, funnily enough even with a full
    #     path executable things will just also not work.
    # PATHEXT
    #     For cases where supplied argument has no PATHEXT
    # SYSTEMROOT
    #     Without this, on Windows 7 (probably others) will just result
    #     in "socket: (10106)" error.
    'win32': ['APPDATA', 'PATH', 'PATHEXT', 'SYSTEMROOT'],
}

# split comma via negative lookahead - match all things inside [] which
# includes the `,` that may be inside that to avoid splitting.
requirement_comma_list = re.compile(',(?![^\\[\\]]*\\])')

json_dumps = partial(dumps, indent=4, sort_keys=True, separators=(',', ': '))
json_dump = partial(dump, indent=4, sort_keys=True, separators=(',', ': '))


def enable_pretty_logging(logger='calmjs', level=logging.DEBUG, stream=None):
    """
    Shorthand to enable pretty logging
    """

    def cleanup():
        logger.removeHandler(handler)
        logger.level = old_level

    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)

    old_level = logger.level
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        u'%(asctime)s %(levelname)s %(name)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(level)
    return cleanup


@contextmanager
def pretty_logging(logger='calmjs', level=logging.DEBUG, stream=None):
    try:
        cleanup = enable_pretty_logging(logger, level, stream)
        yield stream
    finally:
        cleanup()


def finalize_env(env):
    """
    Produce a platform specific env for passing into subprocess.Popen
    family of external process calling methods, and the supplied env
    will be updated on top of it.  Returns a new env.
    """

    keys = _PLATFORM_ENV_KEYS.get(sys.platform, [])
    if 'PATH' not in keys:
        # this MUST be available due to Node.js (and others really)
        # needing something to look for binary locations when it shells
        # out to other binaries.
        keys.append('PATH')
    results = {
        key: os.environ.get(key, '') for key in keys
    }
    results.update(env)
    return results


def fork_exec(args, stdin='', **kwargs):
    """
    Do a fork-exec through the subprocess.Popen abstraction in a way
    that takes a stdin and return stdout.
    """

    as_bytes = isinstance(stdin, bytes)
    source = stdin if as_bytes else stdin.encode(locale)
    p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
    stdout, stderr = p.communicate(source)
    if as_bytes:
        return stdout, stderr
    return (stdout.decode(locale), stderr.decode(locale))


def raise_os_error(_errno, path=None):
    """
    Helper for raising the correct exception under Python 3 while still
    being able to raise the same common exception class in Python 2.7.
    """

    msg = "%s: '%s'" % (strerror(_errno), path) if path else strerror(_errno)
    raise OSError(_errno, msg)


def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """
    Given cmd, check where it is on PATH.

    Loosely based on the version in python 3.3.
    """

    if os.path.dirname(cmd):
        if os.path.isfile(cmd) and os.access(cmd, mode):
            return cmd

    if path is None:
        path = os.environ.get('PATH', defpath)
    if not path:
        return None

    paths = path.split(pathsep)

    if sys.platform == 'win32':
        # oh boy
        if curdir not in paths:
            paths = [curdir] + paths

        # also need to check the fileexts...
        pathext = os.environ.get('PATHEXT', '').split(pathsep)

        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # sanity
        files = [cmd]

    seen = set()
    for p in paths:
        normpath = normcase(p)
        if normpath in seen:
            continue
        seen.add(normpath)
        for f in files:
            fn = os.path.join(p, f)
            if os.path.isfile(fn) and os.access(fn, mode):
                return fn

    return None


def pdb_post_mortem(*a, **kw):
    post_mortem(*a, **kw)


def pdb_set_trace(*a, **kw):
    Pdb(skip=[__name__], *a, **kw).set_trace()
