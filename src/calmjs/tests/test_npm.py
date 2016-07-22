# -*- coding: utf-8 -*-
import unittest

from calmjs import npm


class NpmTestCase(unittest.TestCase):
    """
    calmjs.npm module test case.
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_check_package_json_bad_type(self):
        with self.assertRaises(ValueError) as e:
            npm.verify_package_json(object)

        self.assertEqual(
            str(e.exception),
            'must be a JSON serializable object: '
            '<type \'object\'> is not JSON serializable'
        )

    def test_check_package_json_bad_type_in_dict(self):
        with self.assertRaises(ValueError) as e:
            npm.verify_package_json({
                'devDependencies': {
                    'left-pad': NotImplemented,
                }
            })

        self.assertEqual(
            str(e.exception),
            'must be a JSON serializable object: '
            'NotImplemented is not JSON serializable'
        )

    def test_check_package_json_bad_type_not_dict(self):
        with self.assertRaises(ValueError) as e:
            npm.verify_package_json(1)

        self.assertEqual(
            str(e.exception),
            'must be specified as a JSON serializable dict '
            'or a JSON deserializable string'
        )

        with self.assertRaises(ValueError) as e:
            npm.verify_package_json('"hello world"')

        self.assertEqual(
            str(e.exception),
            'must be specified as a JSON serializable dict '
            'or a JSON deserializable string'
        )

    def test_check_package_json_bad_encode(self):
        with self.assertRaises(ValueError) as e:
            npm.verify_package_json(
                '{'
                '    "devDependencies": {'
                '        "left-pad": "~1.1.1",'  # trailing comma
                '    },'
                '}'
            )

        self.assertEqual(
            str(e.exception),
            'JSON decoding error: '
            'Expecting property name: line 1 column 59 (char 58)'
        )

    def test_check_package_json_good_str(self):
        result = npm.verify_package_json(
            '{'
            '    "devDependencies": {'
            '        "left-pad": "~1.1.1"'
            '    }'
            '}'
        )
        self.assertTrue(result)

    def test_check_package_json_good_dict(self):
        result = npm.verify_package_json(
            # trailing commas are fine in python dicts.
            {
                "devDependencies": {
                    "left-pad": "~1.1.1",
                },
            },
        )
        self.assertTrue(result)
