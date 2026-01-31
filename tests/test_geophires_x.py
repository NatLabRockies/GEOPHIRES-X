from __future__ import annotations

import math
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from geophires_x.GeoPHIRESUtils import sig_figs
from geophires_x.OptionList import PlantType
from geophires_x.OptionList import WellDrillingCostCorrelation
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult

# noinspection PyProtectedMember
from geophires_x_client import _get_logger
from geophires_x_client.geophires_input_parameters import EndUseOption
from geophires_x_client.geophires_input_parameters import GeophiresInputParameters
from geophires_x_client.geophires_input_parameters import ImmutableGeophiresInputParameters
from geophires_x_tests.test_options_list import WellDrillingCostCorrelationTestCase

# noinspection PyProtectedMember
# ruff: noqa: I001  # Successful module initialization is dependent on this specific import order.
from geophires_x.EconomicsSam import _cash_flow_profile_row

from tests.base_test_case import BaseTestCase


# noinspection PyTypeChecker
class GeophiresXTestCase(BaseTestCase):
    def test_geophires_x_end_use_direct_use_heat(self):
        client = GeophiresXClient()
        result = client.get_geophires_result(
            GeophiresInputParameters(
                {
                    'Print Output to Console': 0,
                    'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value,
                    'Reservoir Model': 1,
                    'Time steps per year': 1,
                    'Reservoir Depth': 3,
                    'Gradient 1': 50,
                    'Maximum Temperature': 250,
                }
            )
        )

        assert result is not None
        self.assertIsNotNone(result)
        self.assertEqual(result.result['metadata']['End-Use Option'], 'DIRECT_USE_HEAT')
        self.assertEqual(
            result.result['RESERVOIR PARAMETERS']['Reservoir Model'], 'Multiple Parallel Fractures Model (Gringarten)'
        )
        self.assertEqual(result.result['RESERVOIR PARAMETERS']['Fracture model'], 'Circular fracture with known area')
        self.assertEqual(
            result.result['RESERVOIR SIMULATION RESULTS']['Production Wellbore Heat Transmission Model'], 'Ramey Model'
        )
        self.assertEqual(result.result['ECONOMIC PARAMETERS']['Economic Model'], 'Standard Levelized Cost')

        result_same_input = client.get_geophires_result(
            GeophiresInputParameters(
                {
                    'Print Output to Console': 0,
                    'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value,
                    'Reservoir Model': 1,
                    'Time steps per year': 1,
                    'Reservoir Depth': 3,
                    'Gradient 1': 50,
                    'Maximum Temperature': 250,
                }
            )
        )

        del result.result['metadata']
        if 'metadata' in result_same_input.result:
            del result_same_input.result['metadata']

        del result.result['Simulation Metadata']['Calculation Time']
        del result_same_input.result['Simulation Metadata']['Calculation Time']

        self.assertDictEqual(result.result, result_same_input.result)

    # noinspection PyMethodMayBeStatic
    def test_geophires_x_end_use_electricity(self):
        client = GeophiresXClient()
        result = client.get_geophires_result(
            GeophiresInputParameters(
                {
                    'Print Output to Console': 0,
                    'End-Use Option': EndUseOption.ELECTRICITY.value,
                    'Reservoir Model': 1,
                    'Time steps per year': 1,
                    'Reservoir Depth': 3,
                    'Gradient 1': 50,
                    'Maximum Temperature': 300,
                }
            )
        )

        assert result is not None
        assert result.result['metadata']['End-Use Option'] == 'ELECTRICITY'

    def test_reservoir_model_2(self):
        client = GeophiresXClient()
        result = client.get_geophires_result(
            GeophiresInputParameters(
                {
                    'Print Output to Console': 0,
                    'Time steps per year': 6,
                    'Reservoir Model': 2,
                    'Reservoir Depth': 5,
                    'Gradient 1': 35,
                    'Maximum Temperature': 250,
                    'Number of Production Wells': 2,
                    'Number of Injection Wells': 2,
                    'Production Well Diameter': 5.5,
                    'Injection Well Diameter': 5.5,
                    'Ramey Production Wellbore Model': 1,
                    'Injection Wellbore Temperature Gain': 0,
                    'Production Flow Rate per Well': 30,
                    'Fracture Shape': 4,
                    'Fracture Height': 100,
                    'Fracture Width': 100,
                    'Reservoir Volume Option': 3,
                    'Number of Fractures': 10,
                    'Fracture Separation': 40,
                    'Reservoir Volume': 125000000,
                    'Productivity Index': 10,
                    'Injectivity Index': 10,
                    'Injection Temperature': 50,
                    'Reservoir Heat Capacity': 774,
                    'Reservoir Density': 2600,
                    'Reservoir Thermal Conductivity': 3,
                    'Reservoir Porosity': 0.04,
                    'Water Loss Fraction': 0.02,
                    'Maximum Drawdown': 1,
                    'End-Use Option': 1,
                    'Power Plant Type': 2,
                    'Circulation Pump Efficiency': 0.8,
                    'Utilization Factor': 0.9,
                    'Surface Temperature': 20,
                    'Ambient Temperature': 20,
                    'Plant Lifetime': 35,
                    'Economic Model': 3,
                    'Fraction of Investment in Bonds': 0.75,
                    'Inflated Bond Interest Rate': 0.05,
                    'Inflated Equity Interest Rate': 0.1,
                    'Inflation Rate': 0.02,
                    'Combined Income Tax Rate': 0.3,
                    'Gross Revenue Tax Rate': 0,
                    'Investment Tax Credit Rate': 0.3,
                    'Property Tax Rate': 0,
                    'Inflation Rate During Construction': 0.05,
                    'Well Drilling and Completion Capital Cost Adjustment Factor': 1,
                    'Well Drilling Cost Correlation': 1,
                    'Reservoir Stimulation Capital Cost Adjustment Factor': 1,
                    'Surface Plant Capital Cost Adjustment Factor': 1,
                    'Field Gathering System Capital Cost Adjustment Factor': 1,
                    'Exploration Capital Cost Adjustment Factor': 1,
                    'Wellfield O&M Cost Adjustment Factor': 1,
                    'Surface Plant O&M Cost Adjustment Factor': 1,
                    'Water Cost Adjustment Factor': 1,
                }
            )
        )

        assert result is not None

    def test_geophires_examples(self):
        log = _get_logger()
        client = GeophiresXClient()

        def get_output_file_for_example(example_file: str):
            return self._get_test_file_path(Path('examples', f'{example_file.split(".txt")[0]}.out'))

        # fmt:off
        # @formatter:off
        example_files = list(
            filter(
                lambda example_file_path_: example_file_path_.startswith(
                    ('example', 'Beckers_et_al', 'SUTRA', 'Wanju', 'Fervo', 'S-DAC-GT')
                )
                # TOUGH not enabled for testing - see https://github.com/NREL/GEOPHIRES-X/issues/318
                and not example_file_path_.startswith(('example6.txt', 'example7.txt'))
                and '.out' not in example_file_path_
                and '.json' not in example_file_path_
                and '.csv' not in example_file_path_,
                self._list_test_files_dir(test_files_dir='examples'),
            )
        )
        # @formatter:on
        # fmt:on
        # (2 types of formatting control markers above to prevent both ruff/black and PyCharm from applying formatting)

        # Run SBT examples last because they take an inordinately long time (tens of seconds even on a fast machine).
        # This reduces time spent waiting for tests to run if you are iterating on changes that affect non-SBT examples.
        for ef in [_ef for _ef in example_files if _ef.startswith('example_SBT')]:
            example_files.remove(ef)
            example_files.append(ef)

        # Test integrity check - no files means something is misconfigured
        assert len(example_files) > 0, 'Test integrity check failed: example files is misconfigured.'
        if self._is_github_actions():
            # Additional integrity check to catch when temporary local overrides to example file list are accidentally
            # checked in.
            assert len(example_files) > 10, 'Test integrity check failed: list of example files is too small.'

        regenerate_cmds = []
        for example_file_path in example_files:
            with self.subTest(msg=example_file_path):
                print(f'Running example test {example_file_path}')
                input_params = GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('examples', example_file_path))
                )
                geophires_result: GeophiresXResult = client.get_geophires_result(input_params)
                del geophires_result.result['metadata']
                del geophires_result.result['Simulation Metadata']

                expected_result: GeophiresXResult = GeophiresXResult(get_output_file_for_example(example_file_path))
                del expected_result.result['metadata']
                del expected_result.result['Simulation Metadata']

                self._sanitize_nan(geophires_result)
                self._sanitize_nan(expected_result)

                try:
                    self.assertDictEqual(
                        expected_result.result, geophires_result.result, msg=f'Example test: {example_file_path}'
                    )
                except AssertionError as ae:
                    # Float deviation is observed across processor architecture in some test cases - see example
                    # https://github.com/softwareengineerprogrammer/python-geophires-x-nrel/actions/runs/6475850654/job/17588523571
                    # Adding additional test cases that require this fallback should be avoided if possible.
                    cases_to_allow_almost_equal = [
                        'Beckers_et_al_2023_Tabulated_Database_Coaxial_water_heat.txt',
                        'Beckers_et_al_2023_Tabulated_Database_Uloop_water_elec.txt',
                        'Wanju_Yuan_Closed-Loop_Geothermal_Energy_Recovery.txt',
                    ]
                    allow_almost_equal = example_file_path in cases_to_allow_almost_equal

                    cmd_script = (
                        './tests/regenerate-example-result.sh'
                        if os.name != 'nt'
                        else './tests/regenerate-example-result.ps1'
                    )
                    regenerate_cmd = f'{cmd_script} {example_file_path.split(".")[0]}'
                    regenerate_cmds.append(regenerate_cmd)

                    if allow_almost_equal:
                        log.warning(
                            f"Results aren't exactly equal in {example_file_path}, falling back to almostEqual..."
                        )
                        self.assertDictAlmostEqual(
                            expected_result.result,
                            geophires_result.result,
                            percent=0.01,
                            msg=f'Example test: {example_file_path}',
                        )
                        regenerate_cmds.pop()
                    else:

                        msg = 'Results are not approximately equal within any percentage <100.'
                        percent_diff = self._get_unequal_dicts_approximate_percent_difference(
                            expected_result.result, geophires_result.result
                        )

                        if percent_diff is not None:
                            msg = f'Results are approximately equal within {percent_diff}%.'

                        msg += f' (Run `{regenerate_cmd}` if this is expected due to calculation updates)'

                        raise AssertionError(msg) from ae

        if len(regenerate_cmds) > 0:
            print(f'Command to regenerate {len(regenerate_cmds)} failed examples:\n{" && ".join(regenerate_cmds)}')

    # noinspection PyMethodMayBeStatic
    def _sanitize_nan(self, r: GeophiresXResult) -> None:
        """
        Workaround for float('nan') != float('nan')
        See https://stackoverflow.com/questions/51728427/unittest-how-to-assert-if-the-two-possibly-nan-values-are-equal

        TODO generalize beyond After-tax IRR
        """
        irr_key = 'After-tax IRR'
        if irr_key in r.result['ECONOMIC PARAMETERS']:
            try:
                if math.isnan(r.result['ECONOMIC PARAMETERS'][irr_key]['value']):
                    r.result['ECONOMIC PARAMETERS'][irr_key]['value'] = 'NaN'
            except TypeError:
                pass

    def _get_unequal_dicts_approximate_percent_difference(self, d1: dict, d2: dict) -> float | None:
        for i in range(99):
            try:
                self.assertDictAlmostEqual(d1, d2, percent=i)
                return i
            except AssertionError:
                pass

        return None

    def test_clgs_depth_greater_than_5km(self):
        """
        TODO update test to check result when https://github.com/NREL/GEOPHIRES-X/issues/125 is addressed
          (currently just verifies that input results in RuntimeError rather than previous behavior of sys.exit())
        """

        input_content = """Is AGS, True
Closed-loop Configuration, 1
End-Use Option, 1
Heat Transfer Fluid, 2
Number of Production Wells, 1
Number of Injection Wells, 0
All-in Vertical Drilling Costs, 1000.0
All-in Nonvertical Drilling Costs, 1000.0
Production Flow Rate per Well, 40
Cylindrical Reservoir Input Depth, 5001.0 meter
Gradient 1, 60.0
Total Nonvertical Length, 9000
Production Well Diameter, 8.5
Injection Temperature, 60.0
Plant Lifetime, 40
Ambient Temperature, 20
Electricity Rate, 0.10
Circulation Pump Efficiency, 0.8
CO2 Turbine Outlet Pressure, 200
Economic Model, 4
Reservoir Stimulation Capital Cost, 0
Exploration Capital Cost, 0
Print Output to Console, 1"""
        input_file = Path(tempfile.gettempdir(), f'{uuid.uuid4()!s}.txt')
        with open(input_file, 'w') as f:
            f.write(input_content)

        with self.assertRaises(RuntimeError):
            client = GeophiresXClient()
            client.get_geophires_result(GeophiresInputParameters(from_file_path=input_file))

    def test_runtime_error_with_error_code(self):
        client = GeophiresXClient()

        with self.assertRaises(RuntimeError) as re:
            # Note that error-code-5500.txt is expected to fail with error code 5500 as of the time of the writing
            # of this test. If this expectation is voided by future code updates (possibly such as addressing
            # https://github.com/NREL/python-geophires-x/issues/13), then error-code-5500.txt should be updated with
            # different input that is still expected to result in error code 5500.
            input_params = GeophiresInputParameters(
                from_file_path=self._get_test_file_path(Path('geophires_x_tests/error-code-5500.txt'))
            )
            client.get_geophires_result(input_params)

        self.assertEqual(
            str(re.exception), 'GEOPHIRES encountered an exception: failed with the following error codes: [5500.]'
        )

    def test_parameter_value_outside_of_allowable_range_error(self):
        client = GeophiresXClient()

        with self.assertRaises(RuntimeError) as re:
            input_params = GeophiresInputParameters(
                {
                    'Print Output to Console': 0,
                    'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value,
                    'Reservoir Model': 1,
                    'Time steps per year': 1,
                    'Reservoir Depth': 3000,
                    'Gradient 1': 50,
                    'Maximum Temperature': 250,
                }
            )

            client.get_geophires_result(input_params)

        self.assertTrue(
            'GEOPHIRES encountered an exception: Error: Parameter given (3000.0) for Reservoir Depth outside of valid range.'
            in str(re.exception)
        )

    def test_RTES_name(self):
        self.assertEqual(PlantType.RTES.value, 'Reservoir Thermal Energy Storage')

    def test_input_unit_conversion(self):
        def delete_metadata(r: GeophiresXResult) -> None:
            del r.result['metadata']
            del r.result['Simulation Metadata']['Calculation Time']

        client = GeophiresXClient()

        result_meters_input = client.get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(
                    Path('geophires_x_tests/cylindrical_reservoir_input_depth_meters.txt')
                )
            )
        )
        delete_metadata(result_meters_input)

        result_kilometers_input = client.get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(
                    Path('geophires_x_tests/cylindrical_reservoir_input_depth_kilometers.txt')
                )
            )
        )
        delete_metadata(result_kilometers_input)

        self.assertDictEqual(result_kilometers_input.result, result_meters_input.result)

        result_gradient_c_per_m_input = client.get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(Path('examples/example1.txt')),
                params={
                    'Gradient 1': 0.017  # Values less than 1.0 interpreted as being in degC/m (instead of degC/km)
                },
            )
        )
        del result_gradient_c_per_m_input.result['metadata']

        self.assertEqual(
            result_gradient_c_per_m_input.result['SUMMARY OF RESULTS']['Geothermal gradient']['value'], 17.0
        )
        self.assertEqual(
            result_gradient_c_per_m_input.result['SUMMARY OF RESULTS']['Geothermal gradient']['unit'], 'degC/km'
        )

    def test_fcr_sensitivity(self):
        def input_for_fcr(fcr: float) -> GeophiresInputParameters:
            return GeophiresInputParameters(
                from_file_path=self._get_test_file_path('examples/example1.txt'), params={'Fixed Charge Rate': fcr}
            )

        def get_fcr_lcoe(fcr: float) -> float:
            return (
                GeophiresXClient()
                .get_geophires_result(input_for_fcr(fcr))
                .result['SUMMARY OF RESULTS']['Electricity breakeven price']['value']
            )

        self.assertAlmostEqual(8.82, get_fcr_lcoe(0.05), places=1)
        self.assertAlmostEqual(3.19, get_fcr_lcoe(0.0001), places=1)
        self.assertAlmostEqual(93.48, get_fcr_lcoe(0.8), places=0)

    def test_vapor_pressure_above_critical_temperature(self):
        """https://github.com/NREL/GEOPHIRES-X/issues/214"""

        input_params = GeophiresInputParameters(
            {
                'End-Use Option': 2,
                'Reservoir Depth': 6,
                'Gradient 1': 75,
                'Reservoir Model': 1,
                'Time steps per year': 1,
                'Maximum Temperature': 500,
                'Print Output to Console': 0,
            }
        )

        result = GeophiresXClient().get_geophires_result(input_params)
        self.assertIsNotNone(result)
        self.assertIn('SUMMARY OF RESULTS', result.result)

    def test_heat_price(self):
        def input_for_heat_prices(params) -> GeophiresInputParameters:
            return GeophiresInputParameters(
                from_file_path=self._get_test_file_path('examples/example1.txt'), params=params
            )

        result_escalating = GeophiresXClient().get_geophires_result(
            input_for_heat_prices({'Starting Heat Sale Price': 0.015, 'Ending Heat Sale Price': 0.015})
        )
        self.assertIsNotNone(result_escalating)
        cashflow_constant = result_escalating.result['REVENUE & CASHFLOW PROFILE']
        self.assertEqual(cashflow_constant[0][4], 'Heat Price (cents/kWh)')

        # First entry (index 1 - header is index 0) is hardcoded to zero per
        # https://github.com/NREL/GEOPHIRES-X/blob/becec79cc7510a35f7a9cb01127dabc829720015/src/geophires_x/Economics.py#L2920-L2925
        # so start test at index 2.
        for i in range(2, len(cashflow_constant[0])):
            self.assertEqual(cashflow_constant[i][4], 1.5)

        result_escalating = GeophiresXClient().get_geophires_result(
            input_for_heat_prices(
                {
                    'Starting Heat Sale Price': 0.015,
                    'Ending Heat Sale Price': 0.030,
                    'Heat Escalation Rate Per Year': 0.005,
                    'Heat Escalation Start Year': 0,
                }
            )
        )
        cashflow_escalating = result_escalating.result['REVENUE & CASHFLOW PROFILE']

        self.assertEqual(cashflow_escalating[2][4], 1.5)
        self.assertEqual(cashflow_escalating[-1][4], 3.0)

    def test_disabled_currency_conversion_exceptions(self):
        """
        TODO: this test can be removed once https://github.com/NREL/GEOPHIRES-X/issues/236 is addressed. (Its purpose
            is to ensure currency conversion failure behavior is as expected in the interim.)
        """

        with self.assertRaises(RuntimeError) as re_ec:
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('examples/example1_outputunits.txt')),
                    params={'Units:Exploration cost,MEUR': 'MEUR'},
                )
            )

        e_msg = str(re_ec.exception)

        self.assertIn(
            'Error: GEOPHIRES failed to convert your currency for Exploration cost to something it understands.', e_msg
        )
        self.assertIn('You gave MEUR', e_msg)
        self.assertIn('https://github.com/NREL/GEOPHIRES-X/issues/236', e_msg)

        with self.assertRaises(RuntimeError) as re_omwc:
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('examples/example1_outputunits.txt')),
                    params={'Units:O&M Make-up Water costs': 'MEUR/yr'},
                )
            )

        e_msg = str(re_omwc.exception)

        self.assertIn(
            'Error: GEOPHIRES failed to convert your currency for O&M Make-up Water costs to something it understands.',
            e_msg,
        )
        self.assertIn('You gave MEUR', e_msg)
        self.assertIn('https://github.com/NREL/GEOPHIRES-X/issues/236', e_msg)

    def test_project_red_larger_fractures(self):
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(Path('examples/Fervo_Norbeck_Latimer_2023.txt')),
                params={
                    'Fracture Height': 320,
                    'Fracture Width': 320,
                },
            )
        )

        self.assertEqual(result.result['RESERVOIR PARAMETERS']['Well separation: fracture height']['value'], 320.0)
        self.assertEqual(result.result['RESERVOIR PARAMETERS']['Well separation: fracture height']['unit'], 'meter')

        self.assertEqual(result.result['RESERVOIR PARAMETERS']['Fracture width']['value'], 320.0)
        self.assertEqual(result.result['RESERVOIR PARAMETERS']['Fracture width']['unit'], 'meter')

    def test_convert_output_psi_to_kpa(self):
        GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(Path('examples/example_SHR-2.txt')),
                params={
                    'Production Wellhead Pressure': '64.69 psi',
                },
            )
        )

        # TODO validate output values (for now we are just testing an exception isn't thrown)

    def test_multilateral_section_nonvertical_length(self):
        def s(r):
            del r.result['metadata']
            del r.result['Simulation Metadata']
            return r

        deprecated_param = s(
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('multilateral-section-nonvertical-length.txt')),
                    params={'Total Nonvertical Length': 6000.0},
                )
            )
        )

        non_deprecated_param = s(
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('multilateral-section-nonvertical-length.txt')),
                    params={'Nonvertical Length per Multilateral Section': 6000.0},
                )
            )
        )

        self.assertDictEqual(deprecated_param.result, non_deprecated_param.result)

        both_params = s(
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(Path('multilateral-section-nonvertical-length.txt')),
                    params={'Nonvertical Length per Multilateral Section': 6000.0, 'Total Nonvertical Length': 4000.0},
                )
            )
        )

        # deprecated is ignored if both are present.
        self.assertDictEqual(both_params.result, non_deprecated_param.result)

    def test_discount_rate_and_fixed_internal_rate(self):
        is_github_actions = 'CI' in os.environ or 'TOXPYTHON' in os.environ

        def input_params(discount_rate=None, fixed_internal_rate=None):
            params = {
                'End-Use Option': EndUseOption.ELECTRICITY.value,
                'Reservoir Model': 1,
                'Reservoir Depth': 3,
                'Gradient 1': 50,
            }

            if discount_rate is not None:
                params['Discount Rate'] = discount_rate

            if fixed_internal_rate is not None:
                params['Fixed Internal Rate'] = fixed_internal_rate

            return GeophiresInputParameters(params)

        client = GeophiresXClient()

        try:
            with self.assertLogs(level='INFO') as logs:
                result = client.get_geophires_result(input_params(discount_rate='0.042'))

                self.assertHasLogRecordWithMessage(
                    logs, 'Set Fixed Internal Rate to 4.2 percent because Discount Rate was provided (0.042)'
                )
        except AssertionError as ae:
            if is_github_actions:
                # TODO to investigate and fix
                self.skipTest('Skipping due to intermittent failure on GitHub Actions')
            else:
                raise ae

        self.assertIsNotNone(result)
        self.assertEqual(4.2, result.result['ECONOMIC PARAMETERS']['Interest Rate']['value'])
        self.assertEqual('%', result.result['ECONOMIC PARAMETERS']['Interest Rate']['unit'])

        try:
            with self.assertLogs(level='INFO') as logs2:
                result2 = client.get_geophires_result(input_params(fixed_internal_rate='4.2'))

                self.assertHasLogRecordWithMessage(
                    logs2, 'Set Discount Rate to 0.042 because Fixed Internal Rate was provided (4.2 percent)'
                )
        except AssertionError as ae:
            if is_github_actions:
                # TODO to investigate and fix
                self.skipTest('Skipping due to intermittent failure on GitHub Actions')
            else:
                raise ae

        self.assertIsNotNone(result2)
        self.assertEqual(4.2, result2.result['ECONOMIC PARAMETERS']['Interest Rate']['value'])
        self.assertEqual('%', result2.result['ECONOMIC PARAMETERS']['Interest Rate']['unit'])

    def test_discount_initial_year_cashflow(self):
        def _get_result(base_example: str, do_discount: bool) -> GeophiresXResult:
            return GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    # TODO switch over to generic EGS case to avoid thrash from example updates
                    # from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                    from_file_path=self._get_test_file_path(f'examples/{base_example}.txt'),
                    params={
                        'Discount Initial Year Cashflow': do_discount,
                    },
                )
            )

        def _npv(r: GeophiresXResult) -> dict:
            return r.result['ECONOMIC PARAMETERS']['Project NPV']['value']

        self.assertEqual(4580.36, _npv(_get_result('Fervo_Project_Cape-3', False)))
        self.assertEqual(4280.71, _npv(_get_result('Fervo_Project_Cape-3', True)))

        def _extended_economics_npv(r: GeophiresXResult) -> dict:
            return r.result['EXTENDED ECONOMICS']['Project NPV   (including AddOns)']['value']

        add_ons_result_without_discount = _get_result('example1_addons', False)
        add_ons_result_with_discount = _get_result('example1_addons', True)

        self.assertGreater(_npv(add_ons_result_without_discount), _npv(add_ons_result_with_discount))

        ee_npv_without_discount = _extended_economics_npv(add_ons_result_without_discount)
        assert ee_npv_without_discount < 0, (
            'Test is expecting example1_addons extended economics NPV to be negative '
            'as a precondition - if this error is encountered, '
            'create a test-only copy of the previous version of example1_addons and '
            'use it in this test (like geophires_x_tests/generic-egs-case.txt).'
        )

        # Discounting first year causes negative NPVs to be less negative (according to Google Sheets,
        # which was used to manually validate the expected NPVs here).
        self.assertLess(ee_npv_without_discount, _extended_economics_npv(add_ons_result_with_discount))

    def test_transmission_pipeline_cost(self):
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path(Path('examples/Fervo_Norbeck_Latimer_2023.txt')),
                params={'Surface Piping Length': 5},
            )
        )

        self.assertAlmostEqual(
            result.result['CAPITAL COSTS (M$)']['Transmission pipeline cost']['value'], 3.75, delta=0.5
        )

    def test_well_drilling_and_completion_capital_cost_adjustment_factor(self):
        base_file = self._get_test_file_path('geophires_x_tests/generic-egs-case.txt')
        r_no_adj = GeophiresXClient().get_geophires_result(GeophiresInputParameters(from_file_path=base_file))

        r_noop_adj = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=base_file,
                params={'Well Drilling and Completion Capital Cost Adjustment Factor': 1.0},
            )
        )

        r_adj = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=base_file,
                params={'Well Drilling and Completion Capital Cost Adjustment Factor': 1.175},
            )
        )

        def c_well(r, prod: bool = False, inj: bool = False):
            well_type = 'production ' if prod else 'injection ' if inj else ''
            try:
                c = r.result['CAPITAL COSTS (M$)'][f'Drilling and completion costs per {well_type}well']['value']

                if not prod and not inj:
                    # indirect cost is not applied to prod/inj-specific per-well cost;
                    # see TODO re:parameterizing at src/geophires_x/Economics.py:652
                    default_indirect_cost_factor = 1.05
                    c = c / default_indirect_cost_factor

                return c
            except TypeError:
                return None

        self.assertEqual(c_well(r_no_adj), c_well(r_noop_adj))

        self.assertAlmostEqual(1.175 * c_well(r_no_adj), c_well(r_adj), delta=0.1)

        r_adj_diff_prod_inj = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=base_file,
                params={
                    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.175,
                    'Injection Well Drilling and Completion Capital Cost Adjustment Factor': 3,
                },
            )
        )

        c_well_no_adj = c_well(r_no_adj)
        c_prod_well_adj = c_well(r_adj_diff_prod_inj, prod=True)
        c_inj_well_adj = c_well(r_adj_diff_prod_inj, inj=True)
        self.assertAlmostEqual(1.175 * c_well_no_adj, c_prod_well_adj, delta=0.1)
        self.assertAlmostEqual(3 * c_well_no_adj, c_inj_well_adj, delta=0.1)

    def test_egs_laterals(self):
        def _get_result(num_laterals: int) -> GeophiresXResult:
            return GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                    params={
                        'Well Geometry Configuration': 4,
                        'Number of Multilateral Sections': num_laterals,
                    },
                )
            )

        def _c_non_vert(r: GeophiresXResult) -> dict:
            return r.result['CAPITAL COSTS (M$)']['Drilling and completion costs per non-vertical section']

        self.assertIsNone(_c_non_vert(_get_result(0)))

        r_1 = _get_result(1)
        self.assertIsNotNone(_c_non_vert(r_1)['value'])

        self.assertEqual(_c_non_vert(r_1)['value'], _c_non_vert(_get_result(2))['value'])

    def test_single_time_step_per_year(self):
        result_1 = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={'Time steps per year': 1},
            )
        )

        result_1_final_val = result_1.heat_electricity_extraction_generation_profile[-1][1]
        self.assertGreater(result_1_final_val, 0)

        result_2 = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={'Time steps per year': 2},
            )
        )

        result_2_final_val = result_2.heat_electricity_extraction_generation_profile[-1][1]
        self.assertAlmostEqual(result_2_final_val, result_1_final_val, delta=1.5)

        # TODO enable once https://github.com/NREL/GEOPHIRES-X/issues/352 is resolved
        # result_1_1 = GeophiresXClient().get_geophires_result(
        #     GeophiresInputParameters(
        #         from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
        #         params={
        #             'Time steps per year': 1,
        #             'Plant Lifetime': 1
        #         },
        #     )
        # )
        #
        # self.assertIsNotNone(result_1_1)

    def test_multiple_construction_years(self):
        construction_years = 2
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={'Construction Years': construction_years},
            )
        )

        total_capex = result.result['CAPITAL COSTS (M$)']['Total capital costs']['value']

        rcp = result.result['REVENUE & CASHFLOW PROFILE']
        project_lifetime = 25
        self.assertEqual(project_lifetime + construction_years, len(rcp) - 1)  # Subtract 1 for headers
        net_rev_idx = 14
        net_cashflow_idx = 15

        # Example expected output for first 2 years:
        # [
        #    ...
        #   [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -657.4, -657.4]
        #   [1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -657.4, -1314.79]
        #   ...
        # ]

        yearly_net_rev = -1 * total_capex / construction_years
        self.assertAlmostEqual(yearly_net_rev, rcp[1][net_rev_idx], places=1)
        self.assertAlmostEqual(yearly_net_rev, rcp[1][net_cashflow_idx], places=1)
        self.assertAlmostEqual(yearly_net_rev, rcp[2][net_rev_idx], places=1)
        self.assertEqual(-1 * total_capex, rcp[2][net_cashflow_idx])

        pre_rev_idx = min(net_rev_idx, net_cashflow_idx)
        self.assertListEqual([0] * pre_rev_idx, rcp[1][:pre_rev_idx])
        self.assertListEqual([1] + [0] * (pre_rev_idx - 1), rcp[2][:pre_rev_idx])

    def test_drilling_cost_curves(self):
        """
        Note this is similar to
        geophires_x_tests.test_options_list.WellDrillingCostCorrelationTestCase.test_drilling_cost_curve_correlations;
        this test ensures that the indirect cost factor is responsible for the discrepancy between GEOPHIRES-calculated
        drilling cost per well and the raw value calculated by the curve.
        """

        indirect_cost_factor = 1.05

        for test_case in WellDrillingCostCorrelationTestCase.COST_CORRELATION_TEST_CASES:
            correlation: WellDrillingCostCorrelation = test_case[0]
            depth_m = test_case[1]
            expected_cost_musd = test_case[2]
            with self.subTest(msg=str(f'{correlation.name}, {depth_m}m')):
                result = GeophiresXClient().get_geophires_result(
                    GeophiresInputParameters(
                        from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                        params={
                            'Well Drilling Cost Correlation': correlation.int_value,
                            'Reservoir Depth': f'{depth_m} meter',
                            'Number of Production Wells': 1,
                            'Number of Injection Wells': 1,
                            'Well Drilling and Completion Capital Cost Adjustment Factor': 1,
                        },
                    )
                )

                cost_per_well_val = result.result['CAPITAL COSTS (M$)']['Drilling and completion costs per well'][
                    'value'
                ]
                self.assertAlmostEqual(indirect_cost_factor * expected_cost_musd, cost_per_well_val, delta=0.1)

    def test_segment_thickness_output(self):
        thickness_1 = 0.793
        thickness_2 = 1.646
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={
                    'Number of Segments': 3,
                    'Gradient 1': 42.69972,
                    'Gradient 2': 51.66667,
                    'Thickness 1': thickness_1,
                    'Gradient 3': 46.9697,
                    'Thickness 2': thickness_2,
                },
            )
        )

        self.assertEqual(thickness_1, result.result['SUMMARY OF RESULTS']['Segment 1   Thickness']['value'])
        self.assertEqual(thickness_2, result.result['SUMMARY OF RESULTS']['Segment 2   Thickness']['value'])

    def test_field_gathering_cost(self):
        fg_cost = 2.99
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={
                    'Field Gathering System Capital Cost': fg_cost,
                },
            )
        )

        self.assertEqual(fg_cost, result.result['CAPITAL COSTS (M$)']['Field gathering system costs']['value'])

    def test_heat_pump_lcoh_bicycle(self):
        result = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=self._get_test_file_path('examples/example10_HP.txt'),
                params={
                    'Economic Model': 3,
                },
            )
        )

        lcoh = result.result['SUMMARY OF RESULTS']['Direct-Use heat breakeven price (LCOH)']['value']
        self.assertTrue(10 < lcoh < 20)  # Sanity-check that value is non-zero and broadly within the expected range.

    def test_ags_temperature_limitations(self):
        client = GeophiresXClient()

        with self.assertRaises(RuntimeError) as e:
            params = GeophiresInputParameters(
                {
                    'Is AGS': True,
                    'Well Geometry Configuration': 1,
                    'Injection Temperature': 60,
                    'Gradient 1': 60,
                    'Reservoir Depth': 8,
                    'Cylindrical Reservoir Input Depth': 8,
                    'Economic Model': 3,
                }
            )
            client.get_geophires_result(params)
        self.assertIn(' exceeds ', str(e.exception))

        with self.assertRaises(RuntimeError) as e:
            params = GeophiresInputParameters(
                {
                    'Is AGS': True,
                    'Closed-loop Configuration': 2,
                    'Gradient 1': 25,
                    'Reservoir Depth': 3,
                    'Injection Temperature': 60,
                    'Economic Model': 4,
                }
            )
            client.get_geophires_result(params)
        self.assertIn('failed to validate CLGS input value', str(e.exception))

    def test_negative_electricity_production_raises_error(self):
        client = GeophiresXClient()
        with self.assertRaises(RuntimeError) as e:
            params = GeophiresInputParameters(
                {
                    'Reservoir Depth': 5,
                    'Gradient 1': 112,
                    'Power Plant Type': 2,
                    'Maximum Temperature': 600,
                }
            )
            client.get_geophires_result(params)
        self.assertIn('Electricity production calculated as negative', str(e.exception))

    def test_sbt_coaxial_raises_error(self):
        client = GeophiresXClient()
        with self.assertRaises(RuntimeError) as e:
            params = GeophiresInputParameters(
                {
                    'Reservoir Model': 8,
                    'Well Geometry Configuration': 2,
                }
            )
            client.get_geophires_result(params)
        self.assertIn('SBT with coaxial configuration is not implemented', str(e.exception))

    def test_production_well_stimulation_cost(self):
        def _get_result(
            prod_well_stim_MUSD: int | None = None,
            inj_well_stim_MUSD: int | None = None,
            additional_params: dict[str, Any] | None = None,
        ) -> GeophiresXResult:
            if additional_params is None:
                additional_params = {}

            p = {}
            if prod_well_stim_MUSD is not None:
                p['Reservoir Stimulation Capital Cost per Production Well'] = prod_well_stim_MUSD
            if inj_well_stim_MUSD is not None:
                p['Reservoir Stimulation Capital Cost per Injection Well'] = inj_well_stim_MUSD

            input_params: ImmutableGeophiresInputParameters = ImmutableGeophiresInputParameters(
                from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                params={**p, **additional_params},
            )
            return GeophiresXClient().get_geophires_result(input_params)

        result_no_prod_stim: GeophiresXResult = _get_result()

        result_prod_stim: GeophiresXResult = _get_result(1.25)

        default_contingency_factor = 1.15
        indirect_and_contingency = 1.05 * default_contingency_factor  # default indirect cost factor and contingency

        self.assertAlmostEqual(
            (
                2
                * (
                    result_no_prod_stim.result['CAPITAL COSTS (M$)']['Stimulation costs']['value']
                    / indirect_and_contingency
                )
            )
            * indirect_and_contingency,
            result_prod_stim.result['CAPITAL COSTS (M$)']['Stimulation costs']['value'],
            places=1,
        )

        doublets = 59
        # fmt:off
        result_4M_per_well: GeophiresXResult = _get_result(
            4,
            4,
            {
                'Reservoir Stimulation Indirect Capital Cost Percentage': 0,
                'Number of Production Wells': doublets,
                'Number of Injection Wells': doublets,

                # offset contingency
                'Reservoir Stimulation Capital Cost Adjustment Factor': 1 / default_contingency_factor,
            }
        )
        # fmt:on

        self.assertAlmostEqual(
            (4 * doublets * 2),
            result_4M_per_well.result['CAPITAL COSTS (M$)']['Stimulation costs']['value'],
            places=1,
        )

    def test_indirect_costs(self):
        def _get_result(
            indirect_cost_percent: int | None = None,
            stimulation_indirect_cost_percent: int | None = None,
            wellfield_indirect_cost_percent: int | None = None,
            input_file_path: str = 'geophires_x_tests/generic-egs-case.txt',
        ) -> float:
            p = {}

            if indirect_cost_percent is not None:
                p['Indirect Capital Cost Percentage'] = indirect_cost_percent

            if stimulation_indirect_cost_percent is not None:
                p['Reservoir Stimulation Indirect Capital Cost Percentage'] = stimulation_indirect_cost_percent

            if wellfield_indirect_cost_percent is not None:
                p['Well Drilling and Completion Indirect Capital Cost Percentage'] = wellfield_indirect_cost_percent

            return (
                GeophiresXClient()
                .get_geophires_result(
                    ImmutableGeophiresInputParameters(
                        from_file_path=self._get_test_file_path(input_file_path),
                        params=p,
                    )
                )
                .result['CAPITAL COSTS (M$)']
            )

        result_default_indirect_cost: GeophiresXResult = _get_result()

        def capex(result_cap_costs):
            if result_cap_costs.get('Total CAPEX') is not None:
                return result_cap_costs['Total CAPEX']['value']

            return result_cap_costs['Total capital costs']['value']

        lower_indirect = 10
        result_lower_indirect_cost: GeophiresXResult = _get_result(indirect_cost_percent=lower_indirect)
        self.assertGreater(
            capex(result_default_indirect_cost),
            capex(result_lower_indirect_cost),
        )

        def stim_cost(result_cap_costs):
            return result_cap_costs['Stimulation costs']['value']

        higher_stim_indirect = 12
        result_higher_stim_indirect_cost: GeophiresXResult = _get_result(
            stimulation_indirect_cost_percent=higher_stim_indirect
        )

        self.assertAlmostEqual(
            stim_cost(result_default_indirect_cost) / 1.05,
            stim_cost(result_higher_stim_indirect_cost) / (1 + (higher_stim_indirect / 100)),
            places=1,
        )

        self.assertAlmostEqual(
            stim_cost(result_default_indirect_cost) / 1.05,
            stim_cost(result_higher_stim_indirect_cost) / (1 + (higher_stim_indirect / 100)),
            places=1,
        )

        def wellfield_cost(result_cap_costs):
            return result_cap_costs['Drilling and completion costs']['value']

        result_default_indirect_cost_2: GeophiresXResult = _get_result(
            input_file_path='examples/Fervo_Project_Cape-4.txt'
        )

        higher_wellfield_indirect = 15
        result_higher_wellfield_indirect_cost: GeophiresXResult = _get_result(
            wellfield_indirect_cost_percent=higher_wellfield_indirect,
            input_file_path='examples/Fervo_Project_Cape-4.txt',
        )
        self.assertGreater(
            wellfield_cost(result_higher_wellfield_indirect_cost), wellfield_cost(result_default_indirect_cost_2)
        )

        self.assertGreater(capex(result_higher_wellfield_indirect_cost), capex(result_default_indirect_cost_2))

        self.assertEqual(stim_cost(result_higher_wellfield_indirect_cost), stim_cost(result_default_indirect_cost_2))

        result_higher_wellfield_lower_default: GeophiresXResult = _get_result(
            indirect_cost_percent=lower_indirect,
            wellfield_indirect_cost_percent=higher_wellfield_indirect,
            input_file_path='examples/Fervo_Project_Cape-4.txt',
        )

        self.assertEqual(
            wellfield_cost(result_higher_wellfield_indirect_cost), wellfield_cost(result_higher_wellfield_lower_default)
        )
        self.assertLess(
            capex(result_higher_wellfield_lower_default),
            capex(result_higher_wellfield_indirect_cost),
            # Note this is not necessarily true for all cases, but generally would be expected,
            # and is true for Fervo_Project_Cape-4 specifically.
        )

    def test_contingency(self):
        def _get_result(
            contingency_percentage: int | None = None,
            input_file_path: str = 'geophires_x_tests/generic-egs-case.txt',
        ) -> float:
            p = {}

            if contingency_percentage is not None:
                p['Contingency Percentage'] = contingency_percentage

            return (
                GeophiresXClient()
                .get_geophires_result(
                    ImmutableGeophiresInputParameters(
                        from_file_path=self._get_test_file_path(input_file_path),
                        params=p,
                    )
                )
                .result['CAPITAL COSTS (M$)']
            )

        def capex(result_cap_costs):
            if result_cap_costs.get('Total CAPEX') is not None:
                return result_cap_costs['Total CAPEX']['value']

            return result_cap_costs['Total capital costs']['value']

        default_contingency_percent = 15

        for contingency_percent in range(5, 35, 5):
            if contingency_percent == default_contingency_percent:
                continue

            for input_file_path_ in [
                'geophires_x_tests/generic-egs-case.txt',
                'examples/example10_HP.txt',
                'examples/example11_AC.txt',
            ]:
                with self.subTest(msg=f'contingency={contingency_percent}, input_file_path={input_file_path_}'):
                    result_default = _get_result(input_file_path=input_file_path_)

                    self.assertEqual(
                        # Test assumption check, update default_contingency_percent
                        # if GEOPHIRES default value is changed.
                        capex(result_default),
                        capex(
                            _get_result(
                                contingency_percentage=default_contingency_percent,
                                input_file_path=input_file_path_,
                            )
                        ),
                    )

                    result_different_contingency = _get_result(
                        contingency_percentage=contingency_percent, input_file_path=input_file_path_
                    )

                    if contingency_percent > default_contingency_percent:
                        self.assertGreater(
                            capex(result_different_contingency),
                            capex(result_default),
                        )
                    else:
                        self.assertLess(
                            capex(result_different_contingency),
                            capex(result_default),
                        )

                    self.assertEqual(
                        # Contingency is not applied to drilling costs
                        result_default['Drilling and completion costs']['value'],
                        result_different_contingency['Drilling and completion costs']['value'],
                    )

                    for cost_category in [
                        'Stimulation costs',
                        'Surface power plant costs',
                        'Field gathering system costs',
                        'Total surface equipment costs',
                        'Exploration costs',
                    ]:
                        default_contingency_factor = 1.0 + (default_contingency_percent / 100.0)
                        different_contingency_factor = 1.0 + (contingency_percent / 100.0)

                        expected = (
                            result_default[cost_category]['value']
                            / default_contingency_factor
                            * different_contingency_factor
                        )

                        actual = result_different_contingency[cost_category]['value']

                        # Rounding throws off by a few percent
                        max_allowed_delta_percent = max(
                            # TODO to audit more thoroughly and avoid usage of these tuned constants
                            2.5 if contingency_percent > default_contingency_percent else 5.4,
                            (contingency_percent - default_contingency_percent) / 2.0,
                        )

                        self.assertAlmostEqualWithinPercentage(
                            expected,
                            actual,
                            percent=max_allowed_delta_percent,
                        )

    def test_exploration_cost(self):
        for exploration_cost_MUSD in [0, 500, 1000]:
            result = GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('geophires_x_tests/generic-egs-case.txt'),
                    params={'Exploration Capital Cost': exploration_cost_MUSD},
                )
            )

            self.assertEqual(exploration_cost_MUSD, result.result['CAPITAL COSTS (M$)']['Exploration costs']['value'])
            self.assertEqual('MUSD', result.result['CAPITAL COSTS (M$)']['Exploration costs']['unit'])

    def test_redrilling_costs(self):
        total_capex_specified_result = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=self._get_test_file_path('examples/Fervo_Project_Cape-4.txt'),
                params={'Total Capital Cost': 2500},
            )
        )

        for result in [
            GeophiresXResult(self._get_test_file_path('examples/Fervo_Project_Cape-4.out')),
            total_capex_specified_result,
        ]:
            result_redrills = result.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
            self.assertGreater(result_redrills, 0)

            result_opex = result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']
            opex_sum = 0
            expected_opex_line_items = [
                'Wellfield maintenance costs',
                'Power plant maintenance costs',
                'Water costs',
                'Redrilling costs',
            ]
            for opex_line_item in expected_opex_line_items:
                opex_sum += result_opex[opex_line_item]['value']

            self.assertAlmostEqual(result_opex['Total operating and maintenance costs']['value'], opex_sum, places=1)

            result_capex = result.result['CAPITAL COSTS (M$)']
            capex_field_suffix = (
                '' if result_capex.get('Drilling and completion costs') is not None else ' (for redrilling)'
            )
            # @formatter:off
            expected_annual_redrilling_cost = (
                (
                    result_capex[f'Drilling and completion costs{capex_field_suffix}']['value']
                    + result_capex[f'Stimulation costs{capex_field_suffix}']['value']
                )
                * result_redrills
            ) / result.result['ECONOMIC PARAMETERS']['Project lifetime']['value']
            # @formatter:on

            self.assertAlmostEqual(expected_annual_redrilling_cost, result_opex['Redrilling costs']['value'], places=2)

    def test_royalty_rate(self):
        royalties_output_name = 'Average Annual Royalty Cost'

        zero_royalty_npv = None
        for royalty_rate in [0, 0.1]:
            with self.subTest(msg=f'royalty_rate={royalty_rate}'):

                def _get_result(
                    _royalty_rate: float, additional_params: dict[str, Any] | None = None
                ) -> GeophiresXResult:
                    if additional_params is None:
                        additional_params = {}
                    return GeophiresXClient().get_geophires_result(
                        ImmutableGeophiresInputParameters(
                            from_file_path=self._get_test_file_path(
                                'geophires_x_tests/generic-egs-case-2_sam-single-owner-ppa.txt'
                            ),
                            params={'Royalty Rate': _royalty_rate, **additional_params},
                        )
                    )

                result = _get_result(royalty_rate)
                opex_result = result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']

                self.assertIsNotNone(opex_result[royalties_output_name])
                self.assertEqual('MUSD/yr', opex_result[royalties_output_name]['unit'])

                total_opex_MUSD = opex_result['Total operating and maintenance costs']['value']

                opex_line_item_sum = 0
                for line_item_names in [
                    'Wellfield maintenance costs',
                    'Power plant maintenance costs',
                    'Water costs',
                    royalties_output_name,
                ]:
                    opex_line_item_sum += opex_result[line_item_names]['value']

                self.assertEqual(opex_line_item_sum, total_opex_MUSD)

                def _royalty_holder_npv_MUSD(r: GeophiresXResult) -> float:
                    econ_result = r.result['EXTENDED ECONOMICS']
                    return econ_result['Royalty Holder NPV']['value']

                # econ_result = result.result['EXTENDED ECONOMICS']
                royalty_holder_npv_MUSD = _royalty_holder_npv_MUSD(
                    result
                )  #  econ_result['Royalty Holder NPV']['value']

                if royalty_rate > 0.0:
                    self.assertEqual(58.88, opex_result[royalties_output_name]['value'])
                    self.assertGreater(royalty_holder_npv_MUSD, 0)

                    # Owner NPV is lower when royalty rate is non-zero
                    self.assertGreater(zero_royalty_npv, result.result['ECONOMIC PARAMETERS']['Project NPV']['value'])

                    royalties_cash_flow_MUSD = [
                        it * 1e-6
                        for it in _cash_flow_profile_row(
                            result.result['SAM CASH FLOW PROFILE'], 'O&M production-based expense ($)'
                        )
                    ]

                    self.assertAlmostEqual(
                        np.average(royalties_cash_flow_MUSD[1:]), opex_result[royalties_output_name]['value'], places=1
                    )

                    if royalty_rate == 0.1:
                        base_expected_royalty_holder_npv_MUSD = 708.07
                        self.assertAlmostEqual(base_expected_royalty_holder_npv_MUSD, royalty_holder_npv_MUSD, places=2)

                        result_multiple_construction_years = _get_result(
                            royalty_rate, additional_params={'Construction Years': 5}
                        )
                        mcy_royalty_npv = _royalty_holder_npv_MUSD(result_multiple_construction_years)
                        self.assertLess(mcy_royalty_npv, base_expected_royalty_holder_npv_MUSD)

                if royalty_rate == 0.0:
                    self.assertEqual(0, opex_result[royalties_output_name]['value'])
                    self.assertEqual(0, royalty_holder_npv_MUSD)
                    zero_royalty_npv = result.result['ECONOMIC PARAMETERS']['Project NPV']['value']

    def test_royalty_rate_escalation(self):
        royalties_output_name = 'Average Annual Royalty Cost'

        base_royalty_rate = 0.05
        escalation_rate = 0.01

        for max_rate in [0.08, 1.0]:
            with self.subTest(msg=f'max_rate={max_rate}'):
                result = GeophiresXClient().get_geophires_result(
                    ImmutableGeophiresInputParameters(
                        from_file_path=self._get_test_file_path(
                            'geophires_x_tests/generic-egs-case-2_sam-single-owner-ppa.txt'
                        ),
                        params={
                            'Royalty Rate': base_royalty_rate,
                            'Royalty Rate Escalation': escalation_rate,
                            'Royalty Rate Maximum': max_rate,
                        },
                    )
                )
                opex_result = result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']

                self.assertIsNotNone(opex_result[royalties_output_name])
                self.assertEqual('MUSD/yr', opex_result[royalties_output_name]['unit'])

                total_opex_MUSD = opex_result['Total operating and maintenance costs']['value']

                opex_line_item_sum = 0
                for line_item_names in [
                    'Wellfield maintenance costs',
                    'Power plant maintenance costs',
                    'Water costs',
                    royalties_output_name,
                ]:
                    opex_line_item_sum += opex_result[line_item_names]['value']

                self.assertAlmostEqual(opex_line_item_sum, total_opex_MUSD, places=4)

                project_lifetime_yrs = result.result['ECONOMIC PARAMETERS']['Project lifetime']['value']

                royalties_cash_flow_MUSD = [
                    it * 1e-6
                    for it in _cash_flow_profile_row(
                        result.result['SAM CASH FLOW PROFILE'], 'O&M production-based expense ($)'
                    )
                ][1:]

                ppa_revenue_MUSD = [
                    it * 1e-6
                    for it in _cash_flow_profile_row(result.result['SAM CASH FLOW PROFILE'], 'PPA revenue ($)')
                ][1:]

                actual_royalty_rate = [None] * len(ppa_revenue_MUSD)
                for i in range(len(ppa_revenue_MUSD)):
                    actual_royalty_rate[i] = royalties_cash_flow_MUSD[i] / ppa_revenue_MUSD[i]

                max_expected_rate = (
                    max_rate if max_rate < 1.0 else base_royalty_rate + escalation_rate * (project_lifetime_yrs - 1)
                )

                expected_last_year_revenue = ppa_revenue_MUSD[-1] * max_expected_rate
                self.assertAlmostEqual(expected_last_year_revenue, royalties_cash_flow_MUSD[-1], places=3)

    def test_royalty_rate_with_addon(self):
        """
        Verifies that custom EXTENDED ECONOMICS header print logic in Outputs works as expected
        (geophires_x.Outputs.Outputs._print_extended_economics_header)
        """

        addon_profit_MUSD = 15

        result = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=self._get_test_file_path(
                    'examples/example_SAM-single-owner-PPA-4.txt'  # Royalty rate example
                ),
                params={
                    'AddOn Nickname 1': 'Waste Heat Absorption Chiller',
                    'AddOn CAPEX 1': 50,
                    'AddOn OPEX 1': 1,
                    'AddOn Profit Gained 1': addon_profit_MUSD,
                },
            )
        )

        self.assertEqual(50, sig_figs(result.result['EXTENDED ECONOMICS']['Royalty Holder NPV']['value'], 1))

        addon_cash_flow = _cash_flow_profile_row(result.result['SAM CASH FLOW PROFILE'], 'Capacity payment revenue ($)')
        self.assertEqual(0, addon_cash_flow[0])
        self.assertTrue(all(it == addon_profit_MUSD * 1e6 for it in addon_cash_flow[1:]))

    def test_royalty_rate_not_supported_for_non_sam_economic_models(self):
        with self.assertRaises(RuntimeError) as re:
            GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('examples/Fervo_Project_Cape-3.txt'),
                    params={
                        'Royalty Rate': 0.1,
                    },
                )
            )

        self.assertIn('Royalty Rate is only supported for SAM Economic Models', str(re.exception))

    def test_royalty_rate_with_multiple_construction_years(self):
        royalty_rate_example_stem = 'examples/example_SAM-single-owner-PPA-4'  # Royalty rate example

        royalty_rate_example_input_file_path = self._get_test_file_path(f'{royalty_rate_example_stem}.txt')

        # Test assumes example has 1 construction year; if this changes for some reason, a version of the example with
        # a single construction year should be used instead.
        assert (
            BaseTestCase.get_input_parameter(
                ImmutableGeophiresInputParameters(
                    from_file_path=royalty_rate_example_input_file_path,
                ),
                'Construction Years',
            )
            == 1
        )

        base_result = GeophiresXResult(self._get_test_file_path(f'{royalty_rate_example_stem}.out'))

        mcy_result = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=royalty_rate_example_input_file_path,
                params={
                    'Construction Years': 3,
                },
            )
        )

        def _royalty_holder_npv(r: GeophiresXResult) -> float:
            econ_result = r.result['EXTENDED ECONOMICS']
            return econ_result['Royalty Holder NPV']['value']

        self.assertGreater(_royalty_holder_npv(base_result), _royalty_holder_npv(mcy_result))

    def test_sam_em_add_ons_with_multiple_construction_years(self):
        example_stem = 'examples/example_SAM-single-owner-PPA-3'  # SAM-EM Add-Ons example

        example_input_file_path = self._get_test_file_path(f'{example_stem}.txt')

        # Test assumes example has 1 construction year; if this changes for some reason, a version of the example with
        # a single construction year should be used instead.
        assert (
            BaseTestCase.get_input_parameter(
                ImmutableGeophiresInputParameters(
                    from_file_path=example_input_file_path,
                ),
                'Construction Years',
            )
            == 1
        )

        base_result = GeophiresXResult(self._get_test_file_path(f'{example_stem}.out'))

        mcy_years = 3
        mcy_result = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=example_input_file_path,
                params={'Construction Years': mcy_years},
            )
        )

        def _add_on_cash_flow(r: GeophiresXResult) -> list[float]:
            return _cash_flow_profile_row(r.result['SAM CASH FLOW PROFILE'], 'Capacity payment revenue ($)')

        base_addon_cash_flow = _add_on_cash_flow(base_result)
        mcy_addon_cash_flow = _add_on_cash_flow(mcy_result)

        self.assertListEqual(base_addon_cash_flow, mcy_addon_cash_flow[mcy_years - 1 :])
