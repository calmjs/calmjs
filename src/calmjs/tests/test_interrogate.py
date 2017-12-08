# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from codecs import open
from os.path import join
from pkg_resources import resource_filename

from calmjs.parse.asttypes import String
from calmjs.parse.asttypes import Object
from calmjs.parse import es5
from calmjs import interrogate

# an example artifact bundle that concatenated both UMD and AMD together
artifact = """
(function () {
    (function umd(root, factory) {
        if(typeof exports === 'object' && typeof module === 'object')
            module.exports = factory();
        else if(typeof define === 'function' && define.amd)
            define('lib1', [], factory);
        else if(typeof exports === 'object')
            exports["lib1"] = factory();
        else
            root["lib1"] = factory();
    })(this, function() {});
    (function(define) {
        define('lib2', ['require', 'exports', 'module'], function (
            require, exports, module) {
        });
    }(
        typeof module === 'object' &&
        module.exports &&
        typeof define !== 'function' ? function (factory) {
            module.exports = factory(require, exports, module);
        } : define
    ));
}());
"""

# enclosed define.
artifact_multiple1 = """
(function (define) {(function(define) {
    define('lib1', ['require', 'exports', 'module', 'lib2'], function (
        require, exports, module
    ) {
        var lib2 = require('lib2');
    });
})(define);

define('text', ['module'], function (module) {
});

define('lib2', ['require', 'exports', 'module'], function () {
});

}(define));
"""

# standard AMD
artifact_multiple2 = """
define('lib1',[],function () {
    require('lib2');
    require('lib3');
});

define('lib2',[],function () {
    require('lib3');
});

define('lib4',[],function () {
    require('lib1');
});

define('lib3',[],function () {
});
"""

# missing case
artifact_multiple3 = """
define('lib1',[],function () {
    require('lib4');
    require('lib2');
    require('missing');
});

define('lib2',[],function () {
    require('lib4');
    require('missing');
});

define('lib4',[],function () {
    require('missing');
});
"""

# redefinition case
artifact_multiple4 = """
define('lib1',[],function () {
    require('lib3');
});

define('lib1',[],function () {
    require('missing');
});

define('lib3',[],function () {
});
"""

# commonjs
commonjs_require = """
var mod1 = require('mod1');
var mod2 = require("name/mod/mod2");
var invalid = require();

// test out dynamic require calls.
var target = mod1.target;
var dynamic = require(target);
"""

# require/define mix
requirejs_require = """
require(['some/dummy/module1', 'some/dummy/module2'], function(mod1, mod2) {
    var mod1_alt = require('some/dummy/module1');
    var mod3_alt = require('some/dummy/module3');
});

define(['defined/alternate/module', 'some.weird.module'], function(a, b) {
});

// this is a weird one
define('some test', ['require', 'module'], function(require, module) {});

// invalid code shouldn't choke the walker.
require();
define();

// test out dynamic define calls.
var target = window.target;
var dynamic = define([target], function(target_mod) {});
"""

# amd dynamic define
requirejs_dynamic_define = """
define(a_name, ['static1', 'static2'], function(static1) {
});
"""


class SimpleConversionTestCase(unittest.TestCase):
    """
    Test the various edge cases for the simple conversion.

    Note that the LHS (encapsulated in a String) is the raw data, while
    the RHS the quote style is similar to what JavaScript also supports,
    which is also similar to what Python does.
    """

    def test_to_str_basic(self):
        self.assertEqual(interrogate.to_str(String("'hello'")), 'hello')
        self.assertEqual(interrogate.to_str(String('"hello"')), 'hello')
        # Python escaped
        self.assertEqual(interrogate.to_str(String("'hell\"o'")), 'hell"o')
        self.assertEqual(interrogate.to_str(String('"hell\'o"')), "hell'o")

    def test_to_str_backslash(self):
        # JavaScript escaped
        self.assertEqual(interrogate.to_str(String(r"'he\'llo'")), 'he\'llo')
        self.assertEqual(interrogate.to_str(String(r"'he\"llo'")), 'he\"llo')
        self.assertEqual(interrogate.to_str(String(r"'he\\llo'")), 'he\\llo')

        self.assertEqual(interrogate.to_str(String(r'"he\'llo"')), "he\'llo")
        self.assertEqual(interrogate.to_str(String(r'"he\"llo"')), "he\"llo")

    def test_identifier_extract_typical(self):
        with open(resource_filename('calmjs.testing', join(
                'names', 'typical.js')), encoding='utf-8') as fd:
            tree = es5(fd.read())
        for obj_node in interrogate.shallow_filter(
                tree, lambda node: isinstance(node, Object)):
            self.assertEqual('typical', interrogate.to_identifier(
                obj_node.properties[0].left))

    def test_identifier_extract_unusual(self):
        answers = [
            '\'"\'',
            '\'\"\'',
            "\'\"\'",
            "\n",
            "\t",
            r'\\ ',
            "\u3042",
            "\u3042",
            "    ",
        ]
        with open(resource_filename('calmjs.testing', join(
                'names', 'unusual.js')), encoding='utf-8') as fd:
            tree = es5(fd.read())
        for obj_node, answer in zip(interrogate.shallow_filter(
                tree, lambda node: isinstance(node, Object)), answers):
            self.assertEqual(answer, interrogate.to_identifier(
                obj_node.properties[0].left))


class RequireJSHelperTestCase(unittest.TestCase):
    """
    Helpers to make this thing not suck like the other.
    """

    def test_extract_function_argument_basic(self):
        results = interrogate.extract_function_argument("""
        trial(1, 2, 'hello');
        trial(1, 2, "goodbye");
        """, 'trial', 2)
        self.assertEqual(results, ['hello', 'goodbye'])

    def test_extract_function_argument_mismatches(self):
        results = interrogate.extract_function_argument("""
        trial(1, 2);
        trial(1, 2, 23, 4, 5);
        """, 'trial', 2)
        self.assertEqual(results, [])

    def test_extract_function_argument_not_nested(self):
        # this is a very naive analysis; a more proper one will follow
        # through the scoping rules and trace through the variables so
        # that only the correctly bounded function calls be returned.
        results = interrogate.extract_function_argument("""
        (function() {
            trial(1, 2, 'hello', trial(1, 2, 'goodbye'));
            trial(1, 2, (function() { trial(1, 2, 'goodbye')})());
        })();
        """, 'trial', 2)
        self.assertEqual(results, ['hello'])

    def test_extract_function_not_sub(self):
        results = interrogate.extract_function_argument("""
        (function() {
            log('hello');
            log('');
            console.log('goodbye');
        })();
        """, 'log', 0)
        self.assertEqual(results, ['hello', ''])

    def test_extract_on_syntax_error(self):
        with self.assertRaises(SyntaxError):
            interrogate.extract_function_argument("""
            (function() {
                console.log('hello!');
                report('');
                missing_rparen(1, 2, 'hello';
            })();
            """, 'report', 0)

    def test_yield_imports_bad_type(self):
        with self.assertRaises(TypeError):
            next(interrogate.yield_module_imports('string = "invalid";'))

    def test_yield_imports_basic(self):
        self.assertEqual([
            'mod1',
            "name/mod/mod2",
        ], sorted(set(interrogate.yield_module_imports(es5(
            commonjs_require)))))

    def test_extract_all_commonjs_requires(self):
        self.assertEqual([
            'mod1',
            "name/mod/mod2",
        ], sorted(set(interrogate.extract_module_imports(commonjs_require))))

    def test_extract_all_amd_requires(self):
        self.assertEqual([
            'defined/alternate/module',
            'some.weird.module',
            'some/dummy/module1',
            'some/dummy/module2',
            'some/dummy/module3',
        ], sorted(set(interrogate.extract_module_imports(requirejs_require))))

    def test_extract_all_dynamic_amd_define_require(self):
        self.assertEqual([
            'static1',
            'static2',
        ], sorted(set(interrogate.extract_module_imports(
            requirejs_dynamic_define
        ))))

    def test_yield_imports_node_bad_type(self):
        with self.assertRaises(TypeError):
            next(interrogate.yield_module_imports_nodes('string = "invalid";'))

    def test_dynamic_amd_define_require_yield_node(self):
        self.assertEqual(2, len(list(interrogate.yield_module_imports_nodes(
            es5(requirejs_dynamic_define)))))

    def test_dynamic_define_dynamic_cjs_require(self):
        self.assertEqual(2, len(list(interrogate.yield_module_imports_nodes(
            es5("""
            var foobar = 'module';
            var mod = require(foobar);
            var mod2 = require('foobar');
            var invalid = require(foobar, 'foobar');
            """)
        ))))

    def test_dynamic_define_dynamic_amd_require(self):
        self.assertEqual(2, len(list(interrogate.yield_module_imports_nodes(
            es5("""
            require([foobar, 'foobar'], function(dyn, static) {
            });
            """)
        ))))

    def test_extract_all_amd_requires_skip_reserved(self):
        src = (
            "define('some/test', ['require', 'exports', 'module'], "
            "function(require, exports, module) {});"
        )
        self.assertEqual(
            [],
            sorted(set(interrogate.extract_module_imports(src)))
        )

        src = (
            "define('some/test', ['require', 'exports', 'module', 'mod1'], "
            "function(require, exports, module, mod1) {});"
        )
        self.assertEqual(
            ['mod1'],
            sorted(set(interrogate.extract_module_imports(src)))
        )

        # an actual real world one with the loader plugin
        src = "define('text', ['module'], function(module) {});"
        self.assertEqual(
            [],
            sorted(set(interrogate.extract_module_imports(src)))
        )

        src = "define('alt/text', ['module', 'alt'], function(module) {});"
        self.assertEqual(
            ['alt'],
            sorted(set(interrogate.extract_module_imports(src)))
        )

        src = "define('alt/text', ['alt', 'module'], function(a, module) {});"
        self.assertEqual(
            ['alt'],
            sorted(set(interrogate.extract_module_imports(src)))
        )

    def test_extract_all_amd_requires_non_standard(self):
        # shouldn't fail on certain non-standard cases.
        src = (
            "define('some/test', [], function(require, exports, module) {});"
        )
        self.assertEqual(
            [],
            sorted(set(interrogate.extract_module_imports(src)))
        )

        src = (
            "require();"
        )
        self.assertEqual(
            [],
            sorted(set(interrogate.extract_module_imports(src)))
        )
