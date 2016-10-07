# -*- coding: utf-8 -*-
"""
Various exceptions.
"""


class ValueSkip(ValueError):
    """Hint for marking certain values to be skiped."""


class RuntimeAbort(RuntimeError):
    """Base exception for known abort conditions."""
