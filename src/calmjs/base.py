# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from logging import getLogger

try:
    from pkg_resources import working_set
except ImportError:  # pragma: no cover
    working_set = None

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
        self._init()

    def _init(self):
        """
        Subclasses can override this instead to set instance attributes.
        """

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

        if cls.entry_point_name is NotImplemented:
            raise NotImplementedError(
                '%s must provide a valid ``entry_point_name`` attribute',
                cls.__name__
            )

        # used for testing and/or very implementation specific stuff.
        _working_set = kw.pop('_working_set', None)

        if _working_set is None:
            if working_set is None:
                logger.error(
                    'Autoloading of the `%s` registry is disabled as the '
                    'available setuptools package is missing the '
                    '`pkg_resources` module.  Registry will empty.',
                    registry_name,
                )
            else:
                _working_set = working_set

        entry_points = [] if _working_set is None else list(
            _working_set.iter_entry_points(cls.entry_point_name))

        # Then create the default registry based on that.
        inst = cls(registry_name, *a, **kw)
        inst.register_entry_points(entry_points)
        return inst
