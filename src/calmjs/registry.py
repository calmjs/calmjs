# -*- coding: utf-8 -*-
"""
Generic registry loader

This module simply provides a function to get registries that have been
registered through its standardized, inherited initialize classmethod
constructor.
"""

from calmjs.base import _ModuleRegistry


def get_module_registry(name):
    return _ModuleRegistry.get(name)
