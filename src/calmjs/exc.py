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


class AdviceAbort(ToolchainAbort):
    """
    An advice step can raise this to signal an abort when it enters into
    a completely irrecoverable state or conditions, but not in an
    irrecoverable manner for the toolchain as a whole.
    """


class AdviceCancel(ToolchainCancel):
    """
    An advice step can raise this to simply cancel itself; toolchain
    execution should continue unimpeded.
    """
