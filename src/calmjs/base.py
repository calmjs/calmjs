# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from logging import getLogger

logger = getLogger(__name__)


class BaseModuleRegistry(object):
    """
    A base registry implementation that make use of ``pkg_resources``
    entry points for definition of what interesting modules in the
    current python environment are.
    """

    entry_point_name = NotImplemented

    def __init__(self, registry_name):
        """
        Arguments:

        registry_name
            The name of this registry.
        """

        self.registry_name = registry_name

    def register_entry_points(self, entry_points):
        """
        Register all entry_points provided by the list, if and only if
        the associated module can be imported.

        Arguments:

        entry_points
            a list of entry_points to be registered into this registry
            instance.
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
        """

        module = __import__(
            entry_point.module_name, fromlist=['__name__'], level=0)

        self._register_entry_point_module(entry_point, module)

    def _register_entry_point_module(self, entry_point, module):
        """
        Subclass need to implement this.
        """

        raise NotImplementedError

    @classmethod
    def initialize(cls, registry_name, *a, **kw):
        """
        Default registry constructor that will load all the entry points
        identified by the class attribute ``entry_point_name``.

        Arguments:

        registry_name
            The name for this registry

        Other arguments are passed to the default init method.
        """

        entry_points = {}

        if cls.entry_point_name is NotImplemented:
            raise NotImplementedError(
                '%s must provide a valid ``entry_point_name`` attribute',
                cls.__name__
            )

        entry_point_name = cls.entry_point_name

        try:
            from pkg_resources import iter_entry_points
        except ImportError:  # pragma: no cover
            logger.error(
                'The `%s` registry is disabled as the setuptools '
                'package is missing the `pkg_resources` module', registry_name
            )
        else:
            # Just capture all the relevant entry points for this name.
            entry_points = list(iter_entry_points(entry_point_name))

        # Then create the default registry based on that.
        inst = cls(registry_name, *a, **kw)
        inst.register_entry_points(entry_points)
        return inst
