# -*- coding: utf-8 -*-
"""
Extensions to the argparse library for calmjs.

a.k.a. nyanpasu
"""

from __future__ import absolute_import

import argparse
import sys
import textwrap
from functools import partial
from os import linesep
from os.path import pathsep
from argparse import _
from argparse import Action
from argparse import HelpFormatter
from pkg_resources import working_set as default_working_set
from pkg_resources import Requirement

from calmjs.utils import requirement_comma_list

ATTR_INFO = '_calmjs_runtime_info'
ATTR_ROOT_PKG = '_calmjs_root_pkg_name'


def metavar(name):
    return '<' + name.lower() + '>'


class Namespace(argparse.Namespace):
    """
    This implementation retains existing parsed value for matched types,
    in the context of sub-parsers.
    """

    def __setattr__(self, name, value):
        if hasattr(self, name):
            original_value = getattr(self, name)
            if isinstance(original_value, dict) and isinstance(value, dict):
                original_value.update(value)
                value = original_value
            elif isinstance(original_value, list) and isinstance(value, list):
                original_value.extend(value)
                value = original_value
        super(Namespace, self).__setattr__(name, value)


class HyphenNoBreakHelpFormatter(HelpFormatter):

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(' ', text).strip()
        return textwrap.wrap(text, width, break_on_hyphens=False)


class SortedHelpFormatter(HelpFormatter):

    def add_arguments(self, actions):
        def key_func(action):
            option_strings = getattr(action, 'option_strings', None)
            if not option_strings:
                return option_strings
            # normalize it to lower case.
            arg = option_strings[0]
            return arg.startswith('--'), arg.lower()

        actions = sorted(actions, key=key_func)
        super(SortedHelpFormatter, self).add_arguments(actions)


class CalmJSHelpFormatter(SortedHelpFormatter, HyphenNoBreakHelpFormatter):
    """
    The official formatter for this project
    """


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

        infos = getattr(parser, ATTR_INFO, [])
        for info in infos:
            prog, rt_dist = info
            results.append(
                prog + ': %s %s from %s' % self.get_dist_info(rt_dist))
            results.append(linesep)

        if not results:
            results = ['no package information available.']
        # I'd rather return the results than just exiting outright, but
        # remember the bugs that will make an error happen otherwise...
        # quit early so they don't bug.
        for i in results:
            sys.stdout.write(i)
        sys.exit(0)


class MultiChoice(object):

    def __init__(self, choices=(), sep=','):
        self.__original = choices
        self.__choices = set(choices)
        self.__sep = sep

    def __contains__(self, other):
        return not (set(other.split(self.__sep)) - self.__choices)

    def __iter__(self):
        for i in self.__original:
            yield i


class StoreDelimitedListBase(Action):

    def __init__(self, option_strings, dest, sep=',', maxlen=None, **kw):
        self.sep = sep
        self.maxlen = maxlen
        kw['nargs'] = 1
        kw['const'] = None
        default = kw.get('default')
        if 'choices' in kw:
            kw['choices'] = MultiChoice(choices=kw['choices'], sep=sep)
        if default is not None and not isinstance(default, (tuple, list)):
            raise ValueError(
                'provided default for store delimited list must be a list or '
                'tuple.'
            )
        super(StoreDelimitedListBase, self).__init__(
            option_strings=option_strings, dest=dest, **kw)

    def _convert(self, values):
        result = values[0].split(self.sep)
        if result[-1] == '':
            result.pop(-1)
        return result

    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, self.dest) or getattr(
                namespace, self.dest) is self.default:
            value = []
        else:
            value = getattr(namespace, self.dest)
        result = value + self._convert(values)
        if self.maxlen:
            result = result[:self.maxlen]
        # use the root object's version to be sure that is reset.
        object.__setattr__(namespace, self.dest, result)


class StoreCommaDelimitedList(StoreDelimitedListBase):

    def __init__(self, option_strings, dest, **kw):
        super(StoreCommaDelimitedList, self).__init__(
            option_strings=option_strings, dest=dest, sep=',', **kw)


StoreDelimitedList = StoreCommaDelimitedList


class StorePathSepDelimitedList(StoreDelimitedListBase):

    def __init__(self, option_strings, dest, **kw):
        super(StorePathSepDelimitedList, self).__init__(
            option_strings=option_strings, dest=dest, sep=pathsep, **kw)


class StoreRequirementList(StoreDelimitedListBase):

    def _convert(self, values):
        return requirement_comma_list.split(values[0])


class DeprecatedAction(Action):

    def __init__(self, original_action_cls, deprecation, *a, **kw):
        self.original_action = original_action_cls(*a, **kw)
        # copy the kwargs from within to ensure API compatibility and
        # expectations
        kw.update(self.original_action._get_kwargs())
        # only set message if it's a string.
        self.deprecation = '' if deprecation is True else deprecation
        kw['help'] = argparse.SUPPRESS
        super(DeprecatedAction, self).__init__(*a, **kw)

    def __call__(self, parser, namespace, values, option_string=None):
        import warnings
        msg = "option '%s' is deprecated" % option_string
        if self.deprecation:
            msg = msg + ': ' + self.deprecation
        warnings.warn(msg, DeprecationWarning)
        return self.original_action(
            parser, namespace, values, option_string=option_string)


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, formatter_class=CalmJSHelpFormatter, **kw):
        super(ArgumentParser, self).__init__(
            formatter_class=formatter_class, **kw)

    # In Python 3, this particular error message was removed, so we will
    # do this for Python 2 in this blunt manner.
    def error(self, message):
        if message != _('too few arguments'):
            super(ArgumentParser, self).error(message)

    def parse_known_args(self, args=None, namespace=None):
        if namespace is None:
            namespace = Namespace()
        return super(ArgumentParser, self).parse_known_args(args, namespace)

    def _pop_action_class(self, kwargs, default=None):
        deprecation = kwargs.pop('deprecation', None)
        action = super(ArgumentParser, self)._pop_action_class(kwargs, default)
        if deprecation:
            # as the deprecation class acts as a wrapper
            action = partial(
                DeprecatedAction,
                original_action_cls=action,
                deprecation=deprecation,
            )
        return action

    def soft_error(self, message):
        """
        Same as error, without the dying in a fire part.
        """

        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self._print_message(
            _('%(prog)s: error: %(message)s\n') % args, sys.stderr)

    def unrecognized_arguments_error(self, args):
        self.soft_error(_('unrecognized arguments: %s') % ' '.join(args))
