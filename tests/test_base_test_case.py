from __future__ import annotations

import unittest

from tests.base_test_case import BaseTestCase


class TestBaseTestCase(BaseTestCase):
    def test_assertAlmostEqualWithinPercentage(self):
        self.assertAlmostEqualWithinPercentage(100, 100, percent=5)
        self.assertAlmostEqualWithinPercentage(100, 95, percent=5)
        self.assertAlmostEqualWithinPercentage(100, 105, percent=5)
        self.assertAlmostEqualWithinPercentage(-100, -95, percent=5)
        self.assertAlmostEqualWithinPercentage(-100, -105, percent=5)

        with self.assertRaises(AssertionError):
            self.assertAlmostEqualWithinPercentage(100, 0, percent=5)

        with self.assertRaises(AssertionError):
            self.assertAlmostEqualWithinPercentage(100, 94.5, percent=5)

        with self.assertRaises(AssertionError):
            self.assertAlmostEqualWithinPercentage(100, 105.5, percent=5)

        self.assertListAlmostEqual([1, 2, 3], [1.1, 2.2, 3.3], percent=10.5)

        with self.assertRaises(AssertionError):
            self.assertListAlmostEqual([1, 2, 3], [1.1, 2.2, 3.3], percent=5)

    def test_assertAlmostEqualWithinPercentage_bad_arguments(self):
        with self.assertRaises(ValueError) as msg_type_error:
            self.assertAlmostEqualWithinPercentage(100, 100, 10)

            self.assertIn(str(msg_type_error), '(you may have meant to pass percent=10)')

        with self.assertLogs('tests.base_test_case', level='INFO') as logs:
            with self.assertRaises(AssertionError):
                self.assertAlmostEqualWithinPercentage([1, 2, 3], [1.1, 2.2, 3.3], percent=10.5)

            self.assertHasLogRecordWithMessage(
                logs,
                'Got 2 lists, you probably meant to call:\n\t'
                'self.assertListAlmostEqual([1, 2, 3], [1.1, 2.2, 3.3], msg=None, percent=10.5)',
            )

    def test_assertHasLogRecordWithMessage(self):
        class _Message:
            def __init__(self, msg: str):
                self.message = msg

        class _Logs:
            def __init__(self, records: list[str]):
                self.records: list[_Message] = [_Message(record) for record in records]

        logs = _Logs(
            [
                'Parameter given (0.0) for Property Tax Rate is the same as the default value. Consider removing Property '
                'Tax Rate from the input file unless you wish to change it from the default value of (0.0)',
                'Construction CAPEX Schedule length (2) did not match construction years (4). It has been adjusted to: '
                '[0.25, 0.25, 0.25, 0.25]',
                "complete <class 'geophires_x.Economics.Economics'>: read_parameters",
            ]
        )
        self.assertHasLogRecordWithMessage(logs, 'has been adjusted to', treat_substring_match_as_match=True)


if __name__ == '__main__':
    unittest.main()
