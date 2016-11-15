# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from io import StringIO

from calmjs import vlqsm
from calmjs.utils import pretty_logging


class VLQTestCase(unittest.TestCase):

    def test_vlq_encode_basic(self):
        self.assertEqual(vlqsm.encode_vlq(0), 'A')
        self.assertEqual(vlqsm.encode_vlq(1), 'C')
        self.assertEqual(vlqsm.encode_vlq(-1), 'D')
        self.assertEqual(vlqsm.encode_vlq(2), 'E')
        self.assertEqual(vlqsm.encode_vlq(-2), 'F')

    def test_vlq_encode_edge(self):
        self.assertEqual(vlqsm.encode_vlq(15), 'e')
        self.assertEqual(vlqsm.encode_vlq(-15), 'f')
        self.assertEqual(vlqsm.encode_vlq(16), 'gB')
        self.assertEqual(vlqsm.encode_vlq(-16), 'hB')
        self.assertEqual(vlqsm.encode_vlq(511), '+f')
        self.assertEqual(vlqsm.encode_vlq(-511), '/f')
        self.assertEqual(vlqsm.encode_vlq(512), 'ggB')
        self.assertEqual(vlqsm.encode_vlq(-512), 'hgB')

    def test_vlq_encode_multi(self):
        self.assertEqual(vlqsm.encode_vlq(456), 'wc')
        self.assertEqual(vlqsm.encode_vlq(-456), 'xc')
        self.assertEqual(vlqsm.encode_vlq(789), 'qxB')
        self.assertEqual(vlqsm.encode_vlq(-789), 'rxB')

    def test_encode_vlqs(self):
        self.assertEqual(vlqsm.encode_vlqs((0, 1, 2, 3, 4)), 'ACEGI')
        self.assertEqual(vlqsm.encode_vlqs((123, 456, 789)), '2HwcqxB')

    def test_decode_vlqs(self):
        self.assertEqual((0, 1, 2, 3, 4), vlqsm.decode_vlqs('ACEGI'))
        self.assertEqual((123, 456, 789), vlqsm.decode_vlqs('2HwcqxB'))

    def test_encode_mappings(self):
        self.assertEqual(vlqsm.encode_mappings([
            [(0, 0, 0, 0,), (6, 0, 0, 6,), (6, 0, 0, 6,)],
            []
        ]), 'AAAA,MAAM,MAAM;')

        self.assertEqual(vlqsm.encode_mappings([
            [(0, 0, 0, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            []
        ]), 'AAAA;AACA;AACA;')

        self.assertEqual(vlqsm.encode_mappings([
            [],
            [],
            [(8, 0, 0, 0,)],
            [],
            [(8, 0, 2, 0,)],
            [(8, 0, 1, 0,)],
            [(8, 0, 1, 0,)],
            [],
            [],
        ]), ';;QAAA;;QAEA;QACA;QACA;;')

    def test_decode_mappings(self):
        self.assertEqual([
            [(0, 0, 0, 0,), (6, 0, 0, 6,), (6, 0, 0, 6,)],
            []
        ], vlqsm.decode_mappings('AAAA,MAAM,MAAM;'))

        self.assertEqual([
            [(0, 0, 0, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            []
        ], vlqsm.decode_mappings('AAAA;AACA;AACA;'))

        self.assertEqual([
            [],
            [],
            [(8, 0, 0, 0,)],
            [],
            [(8, 0, 2, 0,)],
            [(8, 0, 1, 0,)],
            [(8, 0, 1, 0,)],
            [],
            [],
        ], vlqsm.decode_mappings(';;QAAA;;QAEA;QACA;QACA;;'))


class SourceWriterTestCase(unittest.TestCase):

    def test_writer_base(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write('hello\n')
        writer.write('hello\n')
        writer.write('hello\n')

        self.assertEqual(stream.getvalue(), 'hello\nhello\nhello\n')
        self.assertEqual(writer.mappings, [
            [(0, 0, 0, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
        ])

    def test_writer_single_line(self):
        # just documenting the partial support for line tracking.
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write('hello ')
        writer.write('hello ')
        writer.write('hello ')

        self.assertEqual(stream.getvalue(), 'hello hello hello ')
        self.assertEqual(writer.mappings, [
            [(0, 0, 0, 0,), (6, 0, 0, 6,), (6, 0, 0, 6,)]
        ])

    def test_writer_write_padding(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('hello\n')
        writer.write_padding('hello\n')
        writer.write_padding('hello\n')

        self.assertEqual(stream.getvalue(), 'hello\nhello\nhello\n')
        self.assertEqual(writer.mappings, [
            [], [], [], []
        ])

    # Following are the actual practical cases where this is used.

    def test_writer_simple_header_footer(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(function(require, exports, module) {\n')
        writer.write('console.log("hello world");\n')
        writer.write('console.log("welcome");\n')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [(0, 0, 0, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(function(require, exports, module) {\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_deindented_source(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(function(require, exports, module) {\n')

        with pretty_logging(stream=StringIO()) as s:
            writer.discard('    ')
            writer.write('console.log("hello world");\n')
            writer.discard('    ')
            writer.write('console.log("welcome");\n')
            writer.discard('    ')
            writer.write('console.log("goodbye world");\n')
            writer.write_padding('});\n')

        self.assertIn('partial line discard UNSUPPORTED;', s.getvalue())
        self.assertEqual(1, len(s.getvalue().splitlines()))

        self.assertEqual(writer.mappings, [
            [],
            # if this is supported, it should be this:
            # [(0, 0, 0, 4,)],
            # with remaining
            # [(0, 0, 1, 0,)],
            # however, to track this it will take more work than I
            # care to give to figure this out for all the possible
            # cases
            [(0, 0, 0, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(function(require, exports, module) {\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_indented_source(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(function(require, exports, module) {\n')
        writer.write_padding('    ')
        writer.write('console.log("hello world");\n')
        writer.write_padding('    ')
        writer.write('console.log("welcome");\n')
        writer.write_padding('    ')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [(4, 0, 0, 0,)],
            [(4, 0, 1, 0,)],
            [(4, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(function(require, exports, module) {\n'
            '    console.log("hello world");\n'
            '    console.log("welcome");\n'
            '    console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_discarded_indented_source(self):
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(function(require, exports, module) {\n')
        writer.discard('\n')
        writer.write('console.log("hello world");\n')
        writer.write('console.log("welcome");\n')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(function(require, exports, module) {\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_use_strict(self):
        # this mimicks calmjs.rjs umd header/footer
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(\n')
        writer.write_padding('    function(require, exports, module) {\n')
        writer.write('"use strict";\n')
        writer.write_padding('        var exports = {}\n')
        writer.write('console.log("hello world");\n')
        writer.write('console.log("welcome");\n')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [],
            [(0, 0, 0, 0,)],
            [],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(\n'
            '    function(require, exports, module) {\n'
            '"use strict";\n'
            '        var exports = {}\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_interspersed_source(self):
        # this mimicks calmjs.rjs umd header/footer
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(\n')
        writer.write_padding('    function(require, exports, module) {\n')
        writer.write('"use strict";\n')
        writer.write_padding('        var exports = {}\n')
        writer.discard('\n')
        writer.discard('\n')
        writer.discard('\n')
        writer.write('console.log("hello world");\n')
        writer.write('console.log("welcome");\n')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [],
            [(0, 0, 0, 0,)],
            [],
            [(0, 0, 4, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(\n'
            '    function(require, exports, module) {\n'
            '"use strict";\n'
            '        var exports = {}\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_interspersed_indented_source(self):
        # this mimicks calmjs.rjs umd header/footer
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(\n')
        writer.write_padding('    function(require, exports, module) {\n')
        writer.write_padding('        ')
        writer.write('"use strict";\n')
        writer.write_padding('        var exports = {}\n')
        writer.discard('\n')
        writer.discard('\n')
        writer.discard('\n')
        writer.write_padding('        ')
        writer.write('console.log("hello world");\n')
        writer.write_padding('        ')
        writer.write('console.log("welcome");\n')
        writer.write_padding('        ')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [],
            [(8, 0, 0, 0,)],
            [],
            [(8, 0, 4, 0,)],
            [(8, 0, 1, 0,)],
            [(8, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(\n'
            '    function(require, exports, module) {\n'
            '        "use strict";\n'
            '        var exports = {}\n'
            '        console.log("hello world");\n'
            '        console.log("welcome");\n'
            '        console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_interspersed_indented_source_discarded_single(self):
        # this mimicks calmjs.rjs umd header/footer
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding('define(\n')
        writer.write_padding('    function(require, exports, module) {\n')
        writer.write_padding('        ')
        writer.write('"use strict";\n')
        writer.write_padding('        var exports = {}\n')
        writer.discard('\n')
        writer.write_padding('        ')
        writer.write('console.log("hello world");\n')
        writer.write_padding('        ')
        writer.write('console.log("welcome");\n')
        writer.write_padding('        ')
        writer.write('console.log("goodbye world");\n')
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [],
            [(8, 0, 0, 0,)],
            [],
            [(8, 0, 2, 0,)],
            [(8, 0, 1, 0,)],
            [(8, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(stream.getvalue(), (
            'define(\n'
            '    function(require, exports, module) {\n'
            '        "use strict";\n'
            '        var exports = {}\n'
            '        console.log("hello world");\n'
            '        console.log("welcome");\n'
            '        console.log("goodbye world");\n'
            '});\n'
        ))

    def test_writer_hf_interspersed_indented_source_discarded_stacked(self):
        # this mimicks calmjs.rjs umd header/footer
        stream = StringIO()
        writer = vlqsm.SourceWriter(stream)
        writer.write_padding(
            'define(\n'
            '    function(require, exports, module) {\n'
            '        var exports = {}\n'
        )
        writer.discard('\n')
        writer.write(
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
        )
        writer.write_padding('});\n')

        self.assertEqual(writer.mappings, [
            [],
            [],
            [],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [(0, 0, 1, 0,)],
            [],
            [],
        ])

        self.assertEqual(writer.getvalue(), (
            'define(\n'
            '    function(require, exports, module) {\n'
            '        var exports = {}\n'
            'console.log("hello world");\n'
            'console.log("welcome");\n'
            'console.log("goodbye world");\n'
            '});\n'
        ))


class SourceMapTestCase(unittest.TestCase):

    def test_create_sourcemap(self):
        result = vlqsm.create_sourcemap(
            filename='bundle.js', sources=['original.js'], mappings=[
                [(0, 0, 0, 0,)], [(0, 0, 1, 0,)], [(0, 0, 1, 0,)], [],
            ]
        )

        self.assertEqual({
            "version": 3,
            "sources": ['original.js'],
            "names": [],
            "mappings": 'AAAA;AACA;AACA;',
            "file": 'bundle.js',
        }, result)
