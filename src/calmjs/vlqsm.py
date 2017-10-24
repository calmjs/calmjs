# -*- coding: utf-8 -*-
"""
Deprecated module that used to contain VLQ encoding and sourcemap
handling; only the lazy (and deprecated) SourceWriter class remains.
"""

from __future__ import unicode_literals
from __future__ import absolute_import

import logging

from calmjs.parse.vlq import (
    encode_vlq,
    encode_vlqs,
    decode_vlqs,
    encode_mappings,
    decode_mappings,
)
from calmjs.parse.sourcemap import encode_sourcemap as create_sourcemap

__all__ = [
    'encode_vlq',
    'encode_vlqs',
    'decode_vlqs',
    'encode_mappings',
    'decode_mappings',
    'create_sourcemap',
    'SourceWriter',
]

logger = logging.getLogger(__name__)


class SourceWriter(object):
    """
    Note: this class is deprecated.  For a more comprehensive
    implementation that works with actual JavaScript AST, please refer
    to the calmjs.parse package.

    This is a _very_ lazy implementation that only works for cases where
    no partial lines from the original source is discarded (i.e. removal
    of indentation from original source file is NOT supported), and for
    adding headers and footers to make the source file work for some
    module system like AMD, plus addition of indentation.

    Please refer to the test case for this for actual implemented
    mapping support.  All other cases that do not fit into those
    patterns are officially NOT supported by this class, as the goal of
    this implementation is to generate source maps for the simple
    header/footer "transpilation" for getting coverage report generation
    correct.
    """

    def __init__(self, stream):
        self.stream = stream
        self.generated_col = 0  # this value resets
        self.row = 0  # initial row.

        self.col_current = 0
        self.col_last = 0  # the last col value that got written out

        self.index = 0  # file index, always 0 in this case
        self.mappings = []
        self._newline()
        self.warn = False

    def _newline(self):
        self.current_mapping = []
        self.mappings.append(self.current_mapping)
        # this is always reset whenever a new line happens
        self.generated_col = 0

    def write(self, s):
        """
        Standard write, for standard sources part of the original file.
        """

        lines = s.splitlines(True)
        for line in lines:
            self.current_mapping.append(
                (self.generated_col, self.index, self.row, self.col_last))
            self.stream.write(line)
            if line[-1] in '\r\n':
                # start again.
                self._newline()
                self.row = 1
                self.col_current = 0
            else:
                self.col_current += len(line)
                self.generated_col = self.col_last = len(line)

    def discard(self, s):
        """
        Discard from original file.
        """

        lines = s.splitlines(True)
        for line in lines:
            if line[-1] not in '\r\n':
                if not self.warn:
                    logger.warning(
                        'partial line discard UNSUPPORTED; source map '
                        'generated will not match at the column level'
                    )
                    self.warn = True
            else:
                # simply increment row
                self.row += 1

    def write_padding(self, s):
        """
        Write string that are not part of the original file.
        """

        lines = s.splitlines(True)
        for line in lines:
            self.stream.write(line)
            if line[-1] in '\r\n':
                self._newline()
            else:
                # this is the last line
                self.generated_col += len(line)

    def getvalue(self):
        return self.stream.getvalue()
