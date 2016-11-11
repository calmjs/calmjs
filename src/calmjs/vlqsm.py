# -*- coding: utf-8 -*-
"""
Module for dealing with VLQ encodings and source maps
"""

from __future__ import unicode_literals

import logging

logger = logging.getLogger(__name__)

B64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

VLQ_SINGLE = 16

# for bit shifting
VLQ_SHIFT = 5

# 100000 = 32, since we have two sets of representation of 16, ignoring
# the bit sign; also for the continuation
VLQ_CONT = VLQ_BASE = 1 << VLQ_SHIFT

# 111111
VLQ_CONT_MASK = 63

# 011111
VLQ_BASE_MASK = 31


def encode_vlq(i):
    """
    Encode integer `i` into a VLQ encoded string.
    """

    # shift in the sign to least significant bit
    raw = (-i << 1) + 1 if i < 0 else i << 1
    if raw < VLQ_SINGLE:
        # short-circuit simple case as it doesn't need continuation
        return B64_CHARS[raw]

    result = []
    while raw:
        # assume continue
        result.append(raw & VLQ_BASE_MASK | VLQ_CONT)
        # shift out processed bits
        raw = raw >> VLQ_SHIFT
    # discontinue the last unit
    result[-1] &= VLQ_BASE_MASK
    return ''.join(B64_CHARS[i] for i in result)


def encode_vlqs(ints):
    return ''.join(encode_vlq(i) for i in ints)


def encode_mappings(mappings):
    def encode_line(line):
        return ','.join(encode_vlqs(frags) for frags in line)
    return ';'.join(encode_line(line) for line in mappings)


def create_sourcemap(filename, mappings, sources, names=[]):
    return {
        "version": 3,
        "sources": sources,
        "names": names,
        "mappings": encode_mappings(mappings),
        "file": filename,
    }


class SourceWriter(object):
    """
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
