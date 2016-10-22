# -*- coding: utf-8 -*-
"""
Various exceptions.
"""


class ValueSkip(ValueError):
    """Hint for marking certain values to be skiped."""


class RuntimeAbort(RuntimeError):
    """Base exception for known abort conditions."""


class ToolchainAbort(RuntimeAbort):
    """
    Events can raise this to abort a toolchain execution if a condition
    required this to be done.
    """


class ToolchainCancel(ToolchainAbort):
    """
    Events that interact with user input during a toolchain execution
    may raise this to signify user cancellation.
    """
