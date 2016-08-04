# -*- coding: utf-8 -*-
from calmjs.module import ModuleRegistry


class NotRegistry(object):
    def __init__(self):
        """This should never be initialized."""


class CustomModuleRegistry(ModuleRegistry):
    """
    Slightly customized module registry for testing purposes.
    """
