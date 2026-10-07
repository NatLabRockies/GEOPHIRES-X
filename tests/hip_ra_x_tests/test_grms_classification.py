from __future__ import annotations

from hip_ra import HipRaInputParameters
from hip_ra import HipRaResult
from hip_ra_x import HipRaXClient
from hip_ra_x.hip_ra_x_result import HipRaXResult
from tests.base_test_case import BaseTestCase


class GrmsClassificationTestCase(BaseTestCase):
    """
    End-to-end coverage of the GRMS classification designations: parameters are
    read, validated against one another, written to the case report and parsed
    back out of it.
    """

    def _run(self, reservoir_temperature: float, **grms_parameters) -> HipRaResult:
        parameters = {'Reservoir Temperature': reservoir_temperature}
        parameters.update(grms_parameters)
        return HipRaXClient().get_hip_ra_result(HipRaInputParameters(parameters))

    def _report_text(self, result: HipRaResult) -> str:
        with open(result.output_file_path, encoding='UTF-8') as f:
            return f.read()

    def _classification(self, result: HipRaResult) -> dict:
        return HipRaXResult.from_hip_ra_result(result).result.get('GRMS CLASSIFICATION') or {}

    def _values(self, result: HipRaResult) -> dict:
        return {k: v['value'] for k, v in self._classification(result).items()}

    def test_no_classification_is_reported_when_none_is_declared(self):
        """The designations are optional: declaring none leaves the report unchanged."""

        result = self._run(201)

        self.assertNotIn('GRMS CLASSIFICATION', self._report_text(result))
        self.assertEqual({}, self._classification(result))

    def test_reserves_classification_is_reported(self):
        result = self._run(
            202,
            **{
                'GRMS Resource Class': 'Reserves',
                'GRMS Estimate Scenario': 'Best Estimate',
                'GRMS Project Maturity Sub-Class': 'On Production',
                'GRMS Reserves Status': 'Developed Producing',
            },
        )

        self.assertIn('***GRMS CLASSIFICATION***', self._report_text(result))
        self.assertDictEqual(
            {
                'Resource Class': 'Reserves',
                'Estimate Scenario': 'Best Estimate',
                'Cumulative Category': '2P',
                'Project Maturity Sub-Class': 'On Production',
                'Reserves Status': 'Developed Producing',
            },
            self._values(result),
        )

    def test_contingent_classification_is_reported(self):
        result = self._run(
            203,
            **{
                'GRMS Resource Class': 'Contingent Resources',
                'GRMS Estimate Scenario': 'Low Estimate',
                'GRMS Project Maturity Sub-Class': 'Development Pending',
                'GRMS Economic Status': 'Economically Viable',
            },
        )

        self.assertDictEqual(
            {
                'Resource Class': 'Contingent Resources',
                'Estimate Scenario': 'Low Estimate',
                'Cumulative Category': '1C',
                'Project Maturity Sub-Class': 'Development Pending',
                'Economic Status': 'Economically Viable',
            },
            self._values(result),
        )

    def test_prospective_classification_is_reported(self):
        result = self._run(
            204,
            **{
                'GRMS Resource Class': 'Prospective Resources',
                'GRMS Estimate Scenario': 'High Estimate',
                'GRMS Project Maturity Sub-Class': 'Prospect',
            },
        )

        self.assertDictEqual(
            {
                'Resource Class': 'Prospective Resources',
                'Estimate Scenario': 'High Estimate',
                'Cumulative Category': '3U',
                'Project Maturity Sub-Class': 'Prospect',
            },
            self._values(result),
        )

    def test_resource_class_alone_is_sufficient(self):
        """A cumulative category needs an estimate scenario, so it is omitted without one."""

        result = self._run(205, **{'GRMS Resource Class': 'Contingent Resources'})

        self.assertDictEqual({'Resource Class': 'Contingent Resources'}, self._values(result))

    def test_designations_may_be_given_as_integer_codes(self):
        result = self._run(
            206,
            **{
                'GRMS Resource Class': '3',
                'GRMS Estimate Scenario': '1',
                'GRMS Project Maturity Sub-Class': '31',
                'GRMS Reserves Status': '4',
            },
        )

        self.assertDictEqual(
            {
                'Resource Class': 'Reserves',
                'Estimate Scenario': 'Low Estimate',
                'Cumulative Category': '1P',
                'Project Maturity Sub-Class': 'Justified for Development',
                'Reserves Status': 'Undeveloped',
            },
            self._values(result),
        )

    def test_classification_values_do_not_disturb_numeric_results(self):
        """
        The designations are text, which the result parser did not previously
        handle. Numeric fields must still parse as numbers with units.
        """

        result = self._run(
            207,
            **{
                'GRMS Resource Class': 'Reserves',
                'GRMS Estimate Scenario': 'Best Estimate',
            },
        )

        self.assertEqual('2P', result.result['Cumulative Category']['value'])
        self.assertEqual(207.0, result.result['Reservoir Temperature']['value'])
        self.assertEqual('degC', result.result['Reservoir Temperature']['unit'])

    def test_sub_class_belonging_to_another_resource_class_is_rejected(self):
        """Development Pending is a Contingent Resources sub-class, not a Reserves one."""

        with self.assertRaises(RuntimeError) as context:
            self._run(
                208,
                **{
                    'GRMS Resource Class': 'Reserves',
                    'GRMS Project Maturity Sub-Class': 'Development Pending',
                },
            )

        self.assertIn('Development Pending', str(context.exception))
        self.assertIn('Contingent Resources', str(context.exception))

    def test_economic_status_outside_contingent_resources_is_rejected(self):
        """Economic status qualifies Contingent Resources only (PRMS 2.1.3.7)."""

        with self.assertRaises(RuntimeError) as context:
            self._run(
                209,
                **{
                    'GRMS Resource Class': 'Reserves',
                    'GRMS Economic Status': 'Economically Viable',
                },
            )

        self.assertIn('Contingent Resources', str(context.exception))

    def test_unrecognized_designation_is_rejected(self):
        with self.assertRaises(RuntimeError) as context:
            self._run(210, **{'GRMS Resource Class': 'Speculative Resources'})

        self.assertIn('Speculative Resources', str(context.exception))
