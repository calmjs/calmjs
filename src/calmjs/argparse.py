# -*- coding: utf-8 -*-
"""
Extensions to the argparse library for calmjs.
"""

from __future__ import absolute_import

import sys
from os import linesep
from argparse import Action
from pkg_resources import working_set as default_working_set
from pkg_resources import Requirement

ATTR_ROOT_PKG = '_calmjs_root_pkg_name'
ATTR_RT_DIST = '_calmjs_runtime_dist'


class Version(Action):
    """
    Version reporting for a console_scripts entry_point
    """

    def __init__(self, *a, **kw):
        kw['nargs'] = 0
        super(Version, self).__init__(*a, **kw)

    def get_dist_info(self, dist, default_name='?'):
        name = getattr(dist, 'project_name', default_name)
        version = getattr(dist, 'version', '?')
        location = getattr(dist, 'location', '?')
        return name, version, location

    def __call__(self, parser, namespace, values, option_string=None):
        """
        Invoke to get version.
        """

        # I really do not like this implementation, but under Python 2.7
        # argparser is broken with subcommands and it quits with too few
        # arguments too soon.

        # Related issues:
        # http://bugs.python.org/issue9253#msg186387
        # http://bugs.python.org/issue10424
        rt_pkg_name = getattr(parser, ATTR_ROOT_PKG, None)
        results = []
        if rt_pkg_name:
            # We can use this directly as nothing else should be cached
            # where this is typically invoked.
            # if the argparser is dumber (which makes it smarter) and
            # doesn't have code that randomly call exit on its own with
            # other _default_ Actions it provides, a flag could just
            # simply be marked and/or returned to inform the caller
            # (i.e. the run time) to handle that.
            dist = default_working_set.find(Requirement.parse(rt_pkg_name))
            results.append('%s %s from %s' % self.get_dist_info(dist))
            results.append(linesep)

        rt_dist = getattr(parser, ATTR_RT_DIST, None)
        if rt_dist:
            results.append(
                parser.prog + ': %s %s from %s' % self.get_dist_info(rt_dist))
            results.append(linesep)

        if not results:
            results = ['no package information available.']
        # I'd rather return the results than just exiting outright, but
        # remember the bugs that will make an error happen otherwise...
        # quit early so they don't bug.
        for i in results:
            sys.stdout.write(i)
        sys.exit(0)
