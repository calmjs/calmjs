# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from collections import OrderedDict
from logging import getLogger
from pkg_resources import working_set

logger = getLogger(__name__)
_marker = object()


class BaseRegistry(object):
    """
    A base registry implementation that make use of ``pkg_resources``
    entry points for its definitions.
    """

    def __init__(self, registry_name, *a, **kw):
        """
        Arguments:

        registry_name
            The name of this registry.
        """

        # The container for the resolved item.
        self.records = OrderedDict()
        self.registry_name = registry_name
        _working_set = kw.pop('_working_set', working_set)
        self.raw_entry_points = [] if _working_set is None else list(
            _working_set.iter_entry_points(self.registry_name))
        self._init(*a, **kw)

    def _init(self, *a, **kw):
        """
        Subclasses can override this for setting up its single instance.
        """

    def get_record(self, name):
        raise NotImplementedError

    def iter_records(self):
        raise NotImplementedError


class BaseModuleRegistry(BaseRegistry):
    """
    Extending off the BaseRegistry, ensure that there is a registration
    step that takes place that will verify the existence of the target.
    """

    def _init(self, *a, **kw):
        self.register_entry_points(self.raw_entry_points)

    def register_entry_points(self, entry_points):
        """
        Register all entry_points provided by the list, if and only if
        the associated module can be imported.

        Arguments:

        entry_points
            a list of entry_points to be registered and activated into
            this registry instance.
        """

        for entry_point in entry_points:
            try:
                self.register_entry_point(entry_point)
            except ImportError:
                logger.warning(
                    'ImportError: %s not found; skipping registration',
                    entry_point.module_name)
                continue

    def register_entry_point(self, entry_point):
        """
        Register a lone entry_point

        Will raise ImportError if the entry_point leads to an invalid
        import.
        """

        module = __import__(
            entry_point.module_name, fromlist=['__name__'], level=0)

        self._register_entry_point_module(entry_point, module)

    def _register_entry_point_module(self, entry_point, module):
        """
        Subclass need to implement this.
        """

        raise NotImplementedError

    def get_record(self, name):
        """
        Get a record by name
        """

        return self.records.get(name)

    def iter_records(self):
        """
        Iterates through the records.
        """

        for item in self.records.items():
            yield item
