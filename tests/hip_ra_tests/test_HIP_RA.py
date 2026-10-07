import tempfile
from pathlib import Path

from hip_ra import HipRaClient
from hip_ra import HipRaInputParameters
from hip_ra import HipRaResult
from tests.base_test_case import BaseTestCase


# noinspection PyTypeChecker
class HIP_RATestCase(BaseTestCase):
    def test_HIP_RA_examples(self):
        example_files = list(
            filter(
                lambda example_file_path: example_file_path.startswith('HIPexample')
                and '.out' not in example_file_path,
                self._list_test_files_dir(test_files_dir='./examples'),
            )
        )
        assert len(example_files) > 0  # test integrity check - no files means something is misconfigured

        client = HipRaClient()

        def get_output_file_for_example(example_file: Path):
            return self._get_test_file_path(Path(example_file).with_suffix('.out'))

        for example_file_path in example_files:
            with self.subTest(msg=example_file_path):
                input_file_path = self._get_test_file_path(Path('./examples', example_file_path))
                result = client.get_hip_ra_result(HipRaInputParameters(input_file_path))

                assert result is not None
                expected_result_output_file_path = get_output_file_for_example(input_file_path)

                expected_result = HipRaResult(expected_result_output_file_path)
                self.assertDictEqual(expected_result.result, result.result)

                self.assertFileContentsEqual(expected_result_output_file_path, result.output_file_path)

    def test_result_parsing_1(self):
        result = HipRaResult(self._get_test_file_path('hip-result_example-1.out'))
        self.assertIsNotNone(result.result)
        self.assertDictEqual(
            {
                'Reservoir Temperature': {'value': 250.0, 'unit': 'degC'},
                'Reservoir Volume': {'value': 13.75, 'unit': 'km**3'},
                'Stored Heat': {'value': 7420000000000000.0, 'unit': 'kJ'},
                'Fluid Produced': {'value': 1100000000000.0, 'unit': 'kilogram'},
                'Enthalpy': {'value': 181.43, 'unit': 'kJ/kg'},
                'Wellhead Heat': {'value': 827000000000000.0, 'unit': 'kJ'},
                'Recovery Factor': {'value': 11.15, 'unit': '%'},
                'Available Heat': {'value': 14700000000000.0, 'unit': 'kJ'},
                'Producible Heat': {'value': 5860000000000.0, 'unit': 'kJ'},
                'Producible Electricity': {'value': 185.85, 'unit': 'MW'},
            },
            result.result,
        )

    def test_result_parsing_2(self):
        result = HipRaResult(self._get_test_file_path('hip-result_example-2.out'))
        self.assertIsNotNone(result.result)
        self.assertDictEqual(
            {
                'Reservoir Temperature': {'value': 250.00, 'unit': 'degC'},
                'Reservoir Volume (reservoir)': {'value': 13.75, 'unit': 'km**3'},
                'Reservoir Volume (rock)': {'value': 12.38, 'unit': 'km**3'},
                'Reservoir Volume (fluid)': {'value': 0.69, 'unit': 'km**3'},
                'Stored Heat (reservoir)': {'value': 5.52e15, 'unit': 'kJ'},
                'Stored Heat (rock)': {'value': 5.01e15, 'unit': 'kJ'},
                'Stored Heat (fluid)': {'value': 5.09e14, 'unit': 'kJ'},
                'Mass of Reservoir (total)': {'value': 3.21e13, 'unit': 'kilogram'},
                'Mass of Reservoir (rock)': {'value': 3.16e13, 'unit': 'kilogram'},
                'Mass of Reservoir (fluid)': {'value': 5.49e11, 'unit': 'kilogram'},
                'Enthalpy (reservoir)': {'value': 49.31, 'unit': 'kJ/kg'},
                'Enthalpy (rock)': {'value': -333.72, 'unit': 'kJ/kg'},
                'Enthalpy (fluid)': {'value': 383.04, 'unit': 'kJ/kg'},
                'Wellhead Heat (reservoir)': {'value': 5.52e15, 'unit': 'kJ'},
                'Wellhead Heat (rock)': {'value': 5.01e15, 'unit': 'kJ'},
                'Wellhead Heat (fluid)': {'value': 5.09e14, 'unit': 'kJ'},
                'Recovery Factor (reservoir)': {'value': -49.39, 'unit': '%'},
                'Recovery Factor (rock)': {'value': -55.51, 'unit': '%'},
                'Recovery Factor (fluid)': {'value': 10.91, 'unit': '%'},
                'Available Heat (reservoir)': {'value': -6.81e15, 'unit': 'kJ'},
                'Available Heat (rock)': {'value': -6.95e15, 'unit': 'kJ'},
                'Available Heat (fluid)': {'value': 1.39e14, 'unit': 'kJ'},
                'Producible Heat (reservoir)': {'value': -2.72e15, 'unit': 'kJ'},
                'Producible Heat (rock)': {'value': -2.78e15, 'unit': 'kJ'},
                'Producible Heat (fluid)': {'value': 5.55e13, 'unit': 'kJ'},
                'Producible Heat/Unit Area (reservoir)': {'value': -4.95e13, 'unit': 'KJ/km**2'},
                'Producible Heat/Unit Area (rock)': {'value': -5.05e13, 'unit': 'KJ/km**2'},
                'Producible Heat/Unit Area (fluid)': {'value': 1.01e12, 'unit': 'KJ/km**2'},
                'Producible Electricity (reservoir)': {'value': -86399.37, 'unit': 'MW'},
                'Producible Electricity (rock)': {'value': -88159.67, 'unit': 'MW'},
                'Producible Electricity (fluid)': {'value': 1760.30, 'unit': 'MW'},
                'Producible Electricity/Unit Area (reservoir)': {'value': -1570.90, 'unit': 'MW/km**2'},
                'Producible Electricity/Unit Area (rock)': {'value': -1602.90, 'unit': 'MW/km**2'},
                'Producible Electricity/Unit Area (fluid)': {'value': 32.01, 'unit': 'MW/km**2'},
            },
            result.result,
        )

    def test_parse_fields_captures_non_numeric_values(self):
        """
        Report fields whose values are text (such as GRMS classification
        designations) are parsed alongside numeric fields.
        """

        report = (
            '                               *********************\n'
            '                               ***HIP CASE REPORT***\n'
            '                               *********************\n'
            '\n'
            '      ***SUMMARY OF RESULTS***\n'
            '      Reservoir Temperature:          250.00 degC\n'
            '      Reservoir Stored Heat:        1.23e+15 kJ\n'
            '\n'
            '      ***GRMS CLASSIFICATION***\n'
            '      Resource Class:                 Reserves\n'
            '      Cumulative Category:            2P\n'
            '      Uncertainty Category:           Proved (P1)\n'
            '      Reserves Status:                Developed Producing\n'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / 'HIP.out'
            report_path.write_text(report, encoding='UTF-8')

            parsed = HipRaResult(report_path).result

        # Numeric fields are unchanged by the non-numeric pass
        self.assertEqual({'value': 250.0, 'unit': 'degC'}, parsed['Reservoir Temperature'])
        self.assertEqual({'value': 1.23e15, 'unit': 'kJ'}, parsed['Reservoir Stored Heat'])

        # Text fields are now captured, with no unit
        self.assertEqual({'value': 'Reserves', 'unit': None}, parsed['Resource Class'])

        # '2P' must stay a string: the numeric pattern splits it into 2.0 with
        # unit 'P' because it does not require whitespace before the unit.
        self.assertEqual({'value': '2P', 'unit': None}, parsed['Cumulative Category'])
        self.assertEqual({'value': 'Proved (P1)', 'unit': None}, parsed['Uncertainty Category'])
        self.assertEqual({'value': 'Developed Producing', 'unit': None}, parsed['Reserves Status'])

        # Banner lines carry no colon-delimited field and must not become keys
        for key in parsed:
            self.assertNotIn('*', key)
