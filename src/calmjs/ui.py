# -*- coding: utf-8 -*-
"""
calmjs.ui

This module provides helper function and classes that encapsulate user
interfacing interactions.
"""

from __future__ import unicode_literals

import sys
from locale import getpreferredencoding
from os import fstat
from stat import S_ISCHR

locale = getpreferredencoding()

if sys.version_info < (3,):  # pragma: no cover
    str = unicode  # noqa: F821

lower = str.lower


def _check_interactive(*descriptors):
    for desc in descriptors:
        try:
            if not S_ISCHR(fstat(desc.fileno()).st_mode):
                return False
        except Exception:
            # Anything broken we are going to pretend this is not
            # interactive
            return False

    return True  # pragma: no cover


def check_interactive():
    return _check_interactive(sys.stdin, sys.stdout)


def make_choice_validator(
        choices, default_key=None, normalizer=None):
    """
    Returns a callable that accepts the choices provided.

    Choices should be provided as a list of 2-tuples, where the first
    element is a string that should match user input (the key); the
    second being the value associated with the key.

    The callable by default will match, upon complete match the first
    value associated with the result will be returned.  Partial matches
    are supported.

    If a default is provided, that value will be returned if the user
    provided input is empty, i.e. the value that is mapped to the empty
    string.

    Finally, a normalizer function can be passed.  This normalizes all
    keys and validation value.
    """

    def normalize_all(_choices):
        # normalize all the keys for easier comparison
        if normalizer:
            _choices = [(normalizer(key), value) for key, value in choices]
        return _choices

    choices = normalize_all(choices)

    def choice_validator(value):
        if normalizer:
            value = normalizer(value)
        if not value and default_key:
            value = choices[default_key][0]
        results = []
        for choice, mapped in choices:
            if value == choice:
                return mapped
            if choice.startswith(value):
                results.append((choice, mapped))
        if len(results) == 1:
            return results[0][1]
        elif not results:
            raise ValueError('Invalid choice.')
        else:
            raise ValueError(
                'Choice ambiguous between (%s)' % ', '.join(
                    k for k, v in normalize_all(results))
            )

    return choice_validator


def null_validator(value):
    return value


def prompt(question, validator=None,
           choices=None, default_key=NotImplemented,
           normalizer=str.lower,
           _stdin=None, _stdout=None):
    """
    Prompt user for question, maybe choices, and get answer.

    Arguments:

    question
        The question to prompt.  It will only be prompted once.
    validator
        Defaults to None.  Must be a callable that takes in a value.
        The callable should raise ValueError when the value leads to an
        error, otherwise return a converted value.
    choices
        If choices are provided instead, a validator will be constructed
        using make_choice_validator along with the next default_value
        argument.  Please refer to documentation for that function.
    default_value
        See above.
    normalizer
        Defaults to str.lower.  See above.
    """

    if _stdin is None:
        _stdin = sys.stdin

    if _stdout is None:
        _stdout = sys.stdout

    _stdout.write(question)
    _stdout.write(' ')

    choice_keys = []

    if validator is None:
        if choices:
            validator = make_choice_validator(
                choices, default_key, normalizer)
            choice_keys = [choice for choice, mapped in choices]
        else:
            validator = null_validator

    answer = NotImplemented
    while answer is NotImplemented:
        if choice_keys:
            _stdout.write('(')
            _stdout.write('/'.join(choice_keys))
            _stdout.write(') ')
            if default_key:
                _stdout.write('[')
                _stdout.write(choice_keys[default_key])
                _stdout.write('] ')
        _stdout.flush()
        try:
            answer = validator(
                _stdin.readline().strip().encode(locale).decode(locale))
        except ValueError as e:
            _stdout.write('%s\n' % e)
            _stdout.write(question.splitlines()[-1])
            _stdout.write(' ')
        except KeyboardInterrupt:
            _stdout.write('Aborted.\n')
            answer = None

    return answer
