# -*- coding: utf-8 -*-
"""
Module for dealing with VLQ encodings and source maps
"""

from __future__ import unicode_literals

import logging

logger = logging.getLogger(__name__)

# While base64 is used, it not used for the string encoding but the
# characters map to corresponding bits.  The lowest 5 bits map to the
# actual number, with the highest (6th) bit being the continuation mark;
# if set, denote the next character is to build on the current.  Do note
# that a given set of bits, the lowest bit is the sign bit; if set, the
# number is negative.
#
# Examples:  (c = continuation bit, s = negative sign bit)
#
# (A) A is 0th char               (E) E is 5th char
# A | c - - - - s |               E | c - - - - s |
# 0 | 0 0 0 0 0 0 | = 0           5 | 0 0 0 1 0 0 | = 2
#
# (F) F has sign bit, negative   (2H) 2 has continuation bit, H does not
# F | c - - - - s |             2 H | c - - - - s | c - - - - s |
# 0 | 0 0 0 1 0 1 | = -2       54 7 | 1 1 0 1 1 0 | 0 0 0 1 1 1 | = 123
#
# For the 2H example, note that it's only the `2` character that carry
# the sign bit as it has the lowest bit, the other characters form
# further higher bits until the last one without one.  The bits would
# look like ( 0 0 1 1 1, 1 0 1 1 + ) for the conversion to the interger
# value of +123.
#
# Thus arbitrary long integers can be represented by arbitrary long
# string of the following 64 characters.  In the source map case, each
# character that has no continuation bit marks the end of the current
# element, following characters form the next element in the list of
# integers that describes a given line in the mapped file.  Each line in
# the mapped file (which is typically the generated artifact) has a
# corresponding line in the mapping denoted by the number of semicolons
# before it (0th line has no semicolons in front of the list of integers
# encoded in VLQ).  Each of these lines are broken into segments of
# either 1, 4 or 5 tuple of integers encoded in VLQ, delimited by commas
# for all the segments within the line that maps to the original source
# file.
#
# For full details please consult the source map v3 specification.

INT_B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
B64_INT = dict((c, i) for i, c in enumerate(INT_B64))

# smallest number that need two characters
VLQ_MULTI_CHAR = 16

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
    if raw < VLQ_MULTI_CHAR:
        # short-circuit simple case as it doesn't need continuation
        return INT_B64[raw]

    result = []
    while raw:
        # assume continue
        result.append(raw & VLQ_BASE_MASK | VLQ_CONT)
        # shift out processed bits
        raw = raw >> VLQ_SHIFT
    # discontinue the last unit
    result[-1] &= VLQ_BASE_MASK
    return ''.join(INT_B64[i] for i in result)


def encode_vlqs(ints):
    return ''.join(encode_vlq(i) for i in ints)


def decode_vlqs(s):
    """
    Decode str `s` into a list of integers.
    """

    ints = []
    i = 0
    shift = 0

    for c in s:
        raw = B64_INT[c]
        cont = VLQ_CONT & raw
        i = ((VLQ_BASE_MASK & raw) << shift) | i
        shift += VLQ_SHIFT
        if not cont:
            sign = -1 if 1 & i else 1
            ints.append((i >> 1) * sign)
            i = 0
            shift = 0

    return tuple(ints)


def encode_mappings(mappings):
    def encode_line(line):
        return ','.join(encode_vlqs(frags) for frags in line)
    return ';'.join(encode_line(line) for line in mappings)


def decode_mappings(mappings_str):
    def decode_line(line):
        return list(decode_vlqs(frags) for frags in line.split(',') if frags)
    return list(decode_line(line) for line in mappings_str.split(';'))


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
