# -*- coding: utf-8 -*-
import io

from pkg_resources import Distribution
from pkg_resources import EntryPoint
from pkg_resources import EmptyProvider

from setuptools.command.egg_info import egg_info

_dist = Distribution()
dummy = object()


class WorkingSet(object):

    def __init__(self, items, dist=_dist):
        self.items = items
        self.dist = dist

    def iter_entry_points(self, name):
        items = self.items.get(name, [])
        for item in items:
            entry_point = item if isinstance(
                item, EntryPoint) else EntryPoint.parse(item)
            entry_point.dist = self.dist
            yield entry_point

    def find(self, name):
        # just always return the dist.
        return self.dist


class Mock_egg_info(egg_info):

    def initialize_options(self):
        egg_info.initialize_options(self)
        self.called = {}

    def write_or_delete_file(self, what, filename, data, force=True):
        """
        Stub out the actual called function
        """

        self.called[filename] = data


class MockProvider(EmptyProvider):
    """
    Extends upon the emptiness of that.
    """

    def __init__(self, metadata):
        self._metadata = {}
        self._metadata.update(metadata)

    def has_metadata(self, name):
        return name in self._metadata

    def get_metadata(self, name):
        results = self._metadata.get(name)
        if results is None:
            raise IOError('emulating an IOError')
        return results


class StringIO(io.StringIO):
    """
    A "safely" wrapped version
    """

    def write(self, msg):
        io.StringIO.write(self, msg.encode(
            'utf8', 'backslashreplace').decode('utf8'))
