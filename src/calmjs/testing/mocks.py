# -*- coding: utf-8 -*-
from pkg_resources import Distribution
from pkg_resources import EntryPoint

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
