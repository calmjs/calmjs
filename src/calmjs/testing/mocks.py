# -*- coding: utf-8 -*-
from pkg_resources import Distribution
from pkg_resources import EntryPoint

from setuptools.command.egg_info import egg_info

dist = Distribution()


class WorkingSet(object):

    def __init__(self, items):
        self.items = items

    def iter_entry_points(self, name):
        # no distinction on name whatsoever because this is a mock
        for item in self.items:
            entry_point = EntryPoint.parse(item)
            entry_point.dist = dist
            yield entry_point


class Mock_egg_info(egg_info):

    def initialize_options(self):
        egg_info.initialize_options(self)
        self.called = {}

    def write_or_delete_file(self, what, filename, data, force=True):
        """
        Stub out the actual called function
        """

        self.called[filename] = data
