from __future__ import annotations

import csv
import json
import tempfile
import uuid
from pathlib import Path

from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters
from geophires_x_client.geophires_input_parameters import EndUseOption
from geophires_x_client.geophires_input_parameters import GeophiresInputParameters
from tests.base_test_case import BaseTestCase


# noinspection PyTypeChecker
class GeophiresXClientTestCase(BaseTestCase):
    """
    Note that these are tests of the geophires_x_client package only and not of the core geophires_x package.
    If a test calls geophires_x_client.GeophiresXClient.get_geophires_result then it generally belongs in
    test_geophires_x.GeophiresXTestCase.
    """

    def test_geophires_x_result_1(self):
        test_result_path = self._get_test_file_path('geophires-result_example-1.out')

        result = GeophiresXResult(test_result_path)

        assert result is not None

        expected_price = 7.06

        assert result.direct_use_heat_breakeven_price_USD_per_MMBTU == expected_price
        assert result.result['SUMMARY OF RESULTS']['Direct-Use heat breakeven price']['value'] == expected_price
        assert result.result['SUMMARY OF RESULTS']['Direct-Use heat breakeven price']['unit'] == 'USD/MMBTU'
        assert result.result['SUMMARY OF RESULTS']['End-Use Option']['value'] == 'Direct-Use Heat'

        assert 'GEOPHIRES Version' in result.result['Simulation Metadata']
        assert '3.' in result.result['Simulation Metadata']['GEOPHIRES Version']['value']

    def test_geophires_x_result_2(self):
        test_result_path = self._get_test_file_path('geophires-result_example-2.out')
        result = GeophiresXResult(test_result_path)

        assert result is not None
        assert result.direct_use_heat_breakeven_price_USD_per_MMBTU is None
        assert result.result['SUMMARY OF RESULTS']['Average Net Electricity Production']['value'] == 5.39
        assert result.result['ENGINEERING PARAMETERS']['Power plant type']['value'] == 'Supercritical ORC'
        assert result.result['SUMMARY OF RESULTS']['End-Use Option']['value'] == 'Electricity'
        assert (
            'Ramey Model'
            == result.result['RESERVOIR SIMULATION RESULTS']['Production Wellbore Heat Transmission Model']
        )
        assert result.result['RESERVOIR SIMULATION RESULTS']['Wellbore Heat Transmission Model'] is None

    def test_geophires_x_result_3(self):
        test_result_path = self._get_test_file_path('geophires-result_example-3.out')
        result = GeophiresXResult(test_result_path)
        assert (
            result.result['SUMMARY OF RESULTS']['End-Use Option']['value']
            == 'Cogeneration Topping Cycle, Heat sales considered as extra income'
        )

    def test_geophires_x_result_4(self):
        test_result_path = self._get_test_file_path('geophires-result_example-4.out')
        result = GeophiresXResult(test_result_path)

        assert result is not None
        assert result.result['SUMMARY OF RESULTS']['Annual District Heating Demand']['value'] == 242.90
        assert result.result['SUMMARY OF RESULTS']['Annual District Heating Demand']['unit'] == 'GWh/year'

        assert (
            result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Annual District Heating O&M Cost']['value']
            == 0.39
        )
        assert (
            result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Annual District Heating O&M Cost']['unit']
            == 'MUSD/yr'
        )

        assert (
            result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Average Annual Peaking Fuel Cost']['value']
            == 3.01
        )
        assert (
            result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Average Annual Peaking Fuel Cost']['unit']
            == 'MUSD/yr'
        )

    def test_direct_use_heat_property(self):
        test_result_path = self._get_test_file_path('examples/example12_DH.out')
        result = GeophiresXResult(test_result_path)

        with open(test_result_path) as f:
            self.assertIn('Direct-Use heat breakeven price (LCOH)', f.read())

        # Don't care about the value in this test - just that it's being read with the (LCOH)-suffixed name
        self.assertIsNotNone(result.direct_use_heat_breakeven_price_USD_per_MMBTU)

    def test_surface_application_field(self):
        for example_file, surface_application in [
            ('examples/example10_HP.out', 'Heat Pump'),
            ('examples/example11_AC.out', 'Absorption Chiller'),
            ('examples/example12_DH.out', 'District Heating'),
        ]:
            with self.subTest(msg=example_file):
                test_result_path = self._get_test_file_path(example_file)
                result = GeophiresXResult(test_result_path)

                assert result.result['SUMMARY OF RESULTS']['Surface Application']['value'] == surface_application

    def test_example_multiple_gradients_result(self):
        test_result_path = self._get_test_file_path('examples/example_multiple_gradients.out')
        result = GeophiresXResult(test_result_path)

        categories = ['SUMMARY OF RESULTS', 'RESOURCE CHARACTERISTICS']
        for category in categories:
            assert result.result[category]['Segment 1   Geothermal gradient']['value'] == 50
            assert result.result[category]['Segment 1   Geothermal gradient']['unit'] == 'degC/km'
            assert result.result[category]['Segment 1   Thickness']['value'] == 1
            assert result.result[category]['Segment 1   Thickness']['unit'] == 'kilometer'

            assert result.result[category]['Segment 2   Geothermal gradient']['value'] == 40
            assert result.result[category]['Segment 2   Geothermal gradient']['unit'] == 'degC/km'
            assert result.result[category]['Segment 2   Thickness']['value'] == 1
            assert result.result[category]['Segment 2   Thickness']['unit'] == 'kilometer'

            assert result.result[category]['Segment 3   Geothermal gradient']['value'] == 30
            assert result.result[category]['Segment 3   Geothermal gradient']['unit'] == 'degC/km'
            assert result.result[category]['Segment 3   Thickness']['value'] == 1
            assert result.result[category]['Segment 3   Thickness']['unit'] == 'kilometer'

            assert result.result[category]['Segment 4   Geothermal gradient']['value'] == 50
            assert result.result[category]['Segment 4   Geothermal gradient']['unit'] == 'degC/km'

    def test_example_absorption_chiller_result(self):
        test_result_path = self._get_test_file_path('examples/example11_AC.out')
        result = GeophiresXResult(test_result_path).result

        assert result['CAPITAL COSTS (M$)']['of which Absorption Chiller Cost']['value'] == 3.74
        assert result['CAPITAL COSTS (M$)']['of which Absorption Chiller Cost']['unit'] == 'MUSD'

    def test_geophires_x_result_generation_profiles(self):
        test_result_path = self._get_test_file_path('geophires-result_example-3.out')
        result = GeophiresXResult(test_result_path)

        assert result.power_generation_profile is not None
        assert len(result.power_generation_profile) == 36
        self.assertListEqual(
            result.power_generation_profile[0],
            [
                'YEAR',
                'THERMAL DRAWDOWN',
                'GEOFLUID TEMPERATURE (deg C)',
                'PUMP POWER (MW)',
                'NET POWER (MW)',
                'NET HEAT (MW)',
                'FIRST LAW EFFICIENCY (%)',
            ],
        )
        self.assertListEqual(result.power_generation_profile[1], [0, 1.0, 225.24, 0.1791, 20.597, 11.6711, 16.5771])
        self.assertListEqual(
            result.power_generation_profile[19], [18, 0.9877, 222.47, 0.1791, 20.0002, 11.3001, 16.3717]
        )
        self.assertListEqual(
            result.power_generation_profile[35], [34, 0.9248, 208.31, 0.1791, 17.1102, 9.2569, 15.3214]
        )

        assert result.heat_electricity_extraction_generation_profile is not None
        assert len(result.heat_electricity_extraction_generation_profile) == 36
        self.assertListEqual(
            result.heat_electricity_extraction_generation_profile[0],
            [
                'YEAR',
                'HEAT PROVIDED (GWh/year)',
                'ELECTRICITY PROVIDED (GWh/year)',
                'HEAT EXTRACTED (GWh/year)',
                'RESERVOIR HEAT CONTENT (10^15 J)',
                'PERCENTAGE OF TOTAL HEAT MINED (%)',
            ],
        )
        self.assertListEqual(
            result.heat_electricity_extraction_generation_profile[1], [1, 93.2, 164.4, 1090.2, 80.03, 4.67]
        )
        self.assertListEqual(
            result.heat_electricity_extraction_generation_profile[-1], [35, 72.5, 134.2, 958.47, -48.48, 157.75]
        )

    def test_ags_clgs_result_generation_profiles(self):
        test_result_path = self._get_test_file_path('geophires-result_example-5.out')
        result = GeophiresXResult(test_result_path)

        assert result.power_generation_profile is not None
        assert len(result.power_generation_profile) == 41
        self.assertListEqual(
            result.power_generation_profile[0],
            [
                'YEAR',
                'THERMAL DRAWDOWN',
                'GEOFLUID TEMPERATURE (degC)',
                'PUMP POWER (MW)',
                'NET POWER (MW)',
                'FIRST LAW EFFICIENCY (%)',
            ],
        )
        self.assertListEqual(result.power_generation_profile[1], [1, 1.0000, 108.39, 0.0000, 0.2930, 9.5729])
        self.assertListEqual(result.power_generation_profile[-1], [40, 0.8649, 96.86, 0.0000, 0.2070, 6.7646])

        assert result.heat_electricity_extraction_generation_profile is not None
        assert len(result.heat_electricity_extraction_generation_profile) == 41
        self.assertListEqual(
            result.heat_electricity_extraction_generation_profile[0],
            [
                'YEAR',
                'ELECTRICITY PROVIDED (GWh/year)',
                'HEAT EXTRACTED (GWh/year)',
                'RESERVOIR HEAT CONTENT (10^15 J)',
                'PERCENTAGE OF TOTAL HEAT MINED (%)',
            ],
        )
        self.assertListEqual(result.heat_electricity_extraction_generation_profile[1], [1, 2.6, 30.1, 3.68, 2.86])
        self.assertListEqual(result.heat_electricity_extraction_generation_profile[-1], [40, 1.8, 22.7, 0.32, 91.57])

    def test_extended_economic_profile(self):
        """
        TODO make this less tedious to update when expected result values change
            (https://github.com/NREL/GEOPHIRES-X/issues/107)
        """

        test_result_path = self._get_test_file_path('examples/example1_addons.out')
        result = GeophiresXResult(test_result_path)
        eep = result.result['EXTENDED ECONOMIC PROFILE']

        self.assertListEqual(
            [
                [
                    'Year Since Start',
                    'Electricity Price (cents/kWh)',
                    'Electricity Revenue (MUSD/yr)',
                    'Heat Price (cents/kWh)',
                    'Heat Revenue (MUSD/yr)',
                    'Add-on Revenue (MUSD/yr)',
                    'Annual AddOn Cash Flow (MUSD/yr)',
                    'Cumm. AddOn Cash Flow (MUSD)',
                    'Annual Project Cash Flow (MUSD/yr)',
                    'Cumm. Project Cash Flow (MUSD)',
                ],
                [1, 0.0, 0.0023, 0.0, 0.0, 1.14, -70.0, -70.0, -95.67, -95.67],
                [2, 0.09, 0.0023, 0.012, 0.0, 1.14, 1.14, -68.86, 5.75, -89.92],
                [3, 0.09, 0.0023, 0.012, 0.0, 1.14, 1.14, -67.72, 5.79, -84.14],
                [4, 0.09, 0.0023, 0.012, 0.0, 1.14, 1.14, -66.59, 5.8, -78.34],
                [5, 0.09, 0.0023, 0.012, 0.0, 1.14, 1.14, -65.45, 5.81, -72.53],
                [6, 0.09, 0.0023, 0.012, 0.0, 1.14, 1.14, -64.31, 5.81, -66.72],
                [7, 0.09, 0.0026, 0.012, 0.0, 1.14, 1.14, -63.17, 5.82, -60.9],
                [8, 0.102, 0.003, 0.012, 0.0, 1.14, 1.14, -62.03, 6.33, -54.57],
                [9, 0.114, 0.0033, 0.012, 0.0, 1.14, 1.14, -60.89, 6.84, -47.73],
                [10, 0.126, 0.0036, 0.022, 0.0, 1.14, 1.14, -59.75, 7.36, -40.37],
                [11, 0.138, 0.0039, 0.032, 0.0, 1.14, 1.14, -58.61, 7.87, -32.5],
                [12, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -57.47, 8.38, -24.12],
                [13, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -56.33, 8.39, -15.73],
                [14, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -55.19, 8.39, -7.34],
                [15, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -54.05, 8.39, 1.05],
                [16, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -52.91, 8.39, 9.44],
                [17, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -51.77, 8.4, 17.84],
                [18, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -50.63, 8.4, 26.24],
                [19, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -49.49, 8.4, 34.63],
                [20, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -48.35, 8.4, 43.03],
                [21, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -47.21, 8.4, 51.44],
                [22, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -46.07, 8.4, 59.84],
                [23, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -44.93, 8.4, 68.25],
                [24, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -43.8, 8.41, 76.65],
                [25, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -42.66, 8.41, 85.06],
                [26, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -41.52, 8.41, 93.47],
                [27, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -40.38, 8.41, 101.88],
                [28, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -39.24, 8.41, 110.29],
                [29, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -38.1, 8.41, 118.7],
                [30, 0.15, 0.0039, 0.036, 0.0, 1.14, 1.14, -36.96, 8.41, 127.11],
            ],
            eep,
        )

    def test_revenue_and_cashflow_profile(self):
        example_result_path = self._get_test_file_path('examples/example1_addons.out')
        example_result = GeophiresXResult(example_result_path)
        example_profile = example_result.result['REVENUE & CASHFLOW PROFILE']
        self.assertIsNotNone(example_profile)

        profile_headers = [
            'Year Since Start',
            'Electricity Price (cents/kWh)',
            'Electricity Ann. Rev. (MUSD/yr)',
            'Electricity Cumm. Rev. (MUSD)',
            'Heat Price (cents/kWh)',
            'Heat Ann. Rev. (MUSD/yr)',
            'Heat Cumm. Rev. (MUSD)',
            'Cooling Price (cents/kWh)',
            'Cooling Ann. Rev. (MUSD/yr)',
            'Cooling Cumm. Rev. (MUSD)',
            'Carbon Price (USD/lb)',
            'Carbon Ann. Rev. (MUSD/yr)',
            'Carbon Cumm. Rev. (MUSD)',
            'Project OPEX (MUSD/yr)',
            'Project Net Rev. (MUSD/yr)',
            'Project Net Cashflow (MUSD)',
        ]

        self.assertListEqual(profile_headers, example_profile[0])

        rcf_path = self._get_test_file_path('result_with_revenue_and_cashflow_profile.out')
        rcf_result = GeophiresXResult(rcf_path)
        rcf_profile = rcf_result.result['REVENUE & CASHFLOW PROFILE']
        self.assertIsNotNone(rcf_profile)

        self.assertListEqual(
            [
                profile_headers,
                [1, 0.09, -32.63, 0.0, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -32.63, -32.63],
                [2, 0.09, 1.58, 0.78, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.58, -31.05],
                [3, 0.09, 1.62, 1.6, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.62, -29.43],
                [4, 0.09, 1.63, 2.43, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.63, -27.8],
                [5, 0.09, 1.64, 3.27, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.64, -26.15],
                [6, 0.09, 1.65, 4.12, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.65, -24.5],
                [7, 0.1, 1.65, 4.97, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.65, -22.85],
                [8, 0.11, 1.77, 5.94, 0.01, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.77, -21.08],
                [9, 0.13, 1.89, 7.03, 0.02, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 1.89, -19.19],
                [10, 0.14, 2.01, 8.24, 0.03, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.01, -17.19],
                [11, 0.15, 2.12, 9.56, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.12, -15.06],
                [12, 0.15, 2.24, 11.0, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.24, -12.82],
                [13, 0.15, 2.25, 12.44, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.25, -10.57],
                [14, 0.15, 2.25, 13.89, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.25, -8.33],
                [15, 0.15, 2.25, 15.34, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.25, -6.08],
                [16, 0.15, 2.25, 16.79, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.25, -3.82],
                [17, 0.15, 2.25, 18.24, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.25, -1.57],
                [18, 0.15, 2.26, 19.7, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 0.69],
                [19, 0.15, 2.26, 21.15, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 2.94],
                [20, 0.15, 2.26, 22.61, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 5.2],
                [21, 0.15, 2.26, 24.07, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 7.46],
                [22, 0.15, 2.26, 25.53, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 9.73],
                [23, 0.15, 2.26, 26.99, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 11.99],
                [24, 0.15, 2.26, 28.46, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.26, 14.25],
                [25, 0.15, 2.27, 29.92, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 16.52],
                [26, 0.15, 2.27, 31.39, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 18.79],
                [27, 0.15, 2.27, 32.85, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 21.06],
                [28, 0.15, 2.27, 34.32, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 23.32],
                [29, 0.15, 2.27, 35.79, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 25.59],
                [30, 0.15, 2.27, 37.26, 0.04, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, -0.8, 2.27, 27.87],
            ],
            rcf_profile,
        )

    def test_carbon_revenue_profile(self):
        result_example1 = GeophiresXResult(self._get_test_file_path('examples/example1.out'))
        self.assertTrue(GeophiresXResult.CARBON_REVENUE_PROFILE_NAME not in result_example1.result)

        result_addons = GeophiresXResult(self._get_test_file_path('examples/example1_addons.out'))
        carbon_revenue_profile = result_addons.result['CARBON REVENUE PROFILE']
        self.assertIsNotNone(carbon_revenue_profile)
        self.assertListEqual(
            carbon_revenue_profile[0],
            ['Year Since Start', 'Carbon Price (USD/lb)', 'Carbon Ann. Rev. (MUSD/yr)', 'Carbon Cumm. Rev. (MUSD)'],
        )

        self.assertListEqual([0, 0.0, 0.0, 0.0], carbon_revenue_profile[1])
        self.assertListEqual([1, 0.01, 0.51, 0.51], carbon_revenue_profile[2])
        self.assertListEqual([29, 0.1, 3.5, 72.36], carbon_revenue_profile[30])
        self.assertListEqual([30, 0.1, 3.5, 75.86], carbon_revenue_profile[31])

    def test_ccus_profile_legacy(self):
        test_result_path = self._get_test_file_path('result_with_ccus_profile_legacy.out')
        result = GeophiresXResult(test_result_path)
        ccus_profile_legacy = result.result['CCUS PROFILE']

        self.assertListEqual(
            [
                [
                    'Year Since Start',
                    'Carbon Avoided (pound)',
                    'CCUS Price (USD/lb)',
                    'CCUS Revenue (MUSD/yr)',
                    'CCUS Annual Cash Flow (MUSD/yr)',
                    'CCUS Cumm. Cash Flow (MUSD)',
                    'Project Annual Cash Flow (MUSD/yr)',
                    'Project Cumm. Cash Flow (MUSD)',
                ],
                [1, None, None, None, None, None, -32.63, -32.63],
                [2, 7101870.358, 0.015, 0.11, 0.11, 0.11, 1.69, -30.95],
                [3, 7470391.043, 0.015, 0.11, 0.11, 0.22, 1.73, -29.21],
                [4, 7595168.229, 0.015, 0.11, 0.11, 0.33, 1.75, -27.46],
                [5, 7669074.1, 0.015, 0.12, 0.12, 0.45, 1.76, -25.71],
                [6, 7720883.286, 0.015, 0.12, 0.12, 0.56, 1.76, -23.94],
                [7, 7760409.892, 0.015, 0.12, 0.12, 0.68, 1.77, -22.17],
                [8, 7792164.418, 0.025, 0.19, 0.19, 0.87, 1.97, -20.21],
                [9, 7818583.043, 0.035, 0.27, 0.27, 1.15, 2.16, -18.04],
                [10, 7841125.517, 0.045, 0.35, 0.35, 1.5, 2.36, -15.69],
                [11, 7860732.801, 0.055, 0.43, 0.43, 1.93, 2.56, -13.13],
                [12, 7878045.387, 0.065, 0.51, 0.51, 2.45, 2.75, -10.37],
                [13, 7893518.049, 0.075, 0.59, 0.59, 3.04, 2.84, -7.54],
                [14, 7907484.797, 0.085, 0.67, 0.67, 3.71, 2.92, -4.62],
                [15, 7920197.818, 0.095, 0.75, 0.75, 4.46, 3.0, -1.61],
                [16, 7931851.962, 0.1, 0.79, 0.79, 5.26, 3.05, 1.43],
                [17, 7942600.746, 0.1, 0.79, 0.79, 6.05, 3.05, 4.48],
                [18, 7952567.147, 0.1, 0.8, 0.8, 6.84, 3.05, 7.53],
                [19, 7961851.088, 0.1, 0.8, 0.8, 7.64, 3.05, 10.58],
                [20, 7970534.743, 0.1, 0.8, 0.8, 8.44, 3.06, 13.64],
                [21, 7978686.355, 0.1, 0.8, 0.8, 9.24, 3.06, 16.7],
                [22, 7986363.027, 0.1, 0.8, 0.8, 10.03, 3.06, 19.76],
                [23, 7993612.777, 0.1, 0.8, 0.8, 10.83, 3.06, 22.82],
                [24, 8000476.061, 0.1, 0.8, 0.8, 11.63, 3.06, 25.89],
                [25, 8006986.902, 0.1, 0.8, 0.8, 12.43, 3.07, 28.95],
                [26, 8013173.735, 0.1, 0.8, 0.8, 13.24, 3.07, 32.02],
                [27, 8019060.033, 0.1, 0.8, 0.8, 14.04, 3.07, 35.09],
                [28, 8024664.782, 0.1, 0.8, 0.8, 14.84, 3.07, 38.16],
                [29, 8030002.83, 0.1, 0.8, 0.8, 15.64, 3.07, 41.24],
                [30, 8035085.158, 0.1, 0.8, 0.8, 16.45, 3.07, 44.31],
                [31, 6703146.945, 0.1, 0.67, 0.67, 17.12, 2.7, 47.01],
            ],
            ccus_profile_legacy,
        )

    def test_non_vertical_section_cost(self):
        result_path = self._get_test_file_path('examples/Fervo_Norbeck_Latimer_2023.out')
        result = GeophiresXResult(result_path)
        cap_costs = result.result['CAPITAL COSTS (M$)']
        entry = cap_costs['Drilling and completion costs per non-vertical section']
        self.assertIsNotNone(entry['value'])
        self.assertEqual(entry['unit'], 'MUSD')

        total_wells = (
            result.result['SUMMARY OF RESULTS']['Number of production wells']['value']
            + result.result['SUMMARY OF RESULTS']['Number of injection wells']['value']
        )

        self.assertAlmostEqual(
            cap_costs['Drilling and completion costs']['value'],
            (
                cap_costs['Drilling and completion costs per vertical production well']['value']
                + cap_costs['Drilling and completion costs per non-vertical section']['value']
            )
            * total_wells,
            places=1,
        )  # (test assumes Number of Multilateral Sections = total_wells)

    def test_input_hashing(self):
        input1 = ImmutableGeophiresInputParameters(
            {'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value, 'Gradient 1': 50, 'Maximum Temperature': 250}
        )

        input2 = ImmutableGeophiresInputParameters(
            {'Maximum Temperature': 250, 'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value, 'Gradient 1': 50}
        )

        self.assertEqual(hash(input1), hash(input2))

        input3 = ImmutableGeophiresInputParameters(
            {'Maximum Temperature': 420, 'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value, 'Gradient 1': 69}
        )

        self.assertNotEqual(hash(input1), hash(input3))

    def test_input_with_non_default_units(self):
        def delete_metadata(r: GeophiresXResult) -> GeophiresXResult:
            del r.result['metadata']
            del r.result['Simulation Metadata']['Calculation Time']

            return r

        client = GeophiresXClient()
        result_default_units = delete_metadata(
            client.get_geophires_result(
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
        ).result

        result_non_default_units = delete_metadata(
            client.get_geophires_result(
                GeophiresInputParameters(
                    {
                        'Print Output to Console': 0,
                        'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value,
                        'Reservoir Model': 1,
                        'Time steps per year': 1,
                        'Reservoir Depth': '3000 meter',
                        'Gradient 1': 50,
                        'Maximum Temperature': 250,
                    }
                )
            )
        ).result

        self.assertDictEqual(result_default_units, result_non_default_units)

    def test_csv(self):
        """
        Note: example1_addons.csv will be updated automatically when `regenerate-example-result.sh example1_addons` is
        run.

        If needed, example1_addons.csv can also be updated manually with the following steps:
         1. In your IDE, set a breakpoint on the line after `as_csv = result.as_csv()`
         2. Debug this test and hit the break point
         3. Copy-paste the value of `as_csv` (in Threads & Variables tab in PyCharm) to example1_addons.csv
        """

        def assert_csv_equal(case_report_file_path, expected_csv_file_path):
            test_result_path = self._get_test_file_path(case_report_file_path)
            result = GeophiresXResult(test_result_path)
            as_csv = result.as_csv()
            self.assertIsNotNone(as_csv)

            result_file = Path(tempfile.gettempdir(), f'test_csv-result_{uuid.uuid1()!s}.csv')
            with open(result_file, 'w', newline='', encoding='utf-8') as rf:
                rf.write(as_csv)
            self.assertCsvFileContentsEqual(self._get_test_file_path(expected_csv_file_path), result_file)

        for case in [
            ('examples/example1_addons.out', 'example1_addons.csv'),
            ('geophires-result_example-3.out', 'geophires-result_example-3.csv'),
        ]:
            with self.subTest(msg=case[0]):
                assert_csv_equal(case[0], case[1])

        op_example_file = 'examples/example_overpressure.out'
        with self.subTest(msg=op_example_file):
            # Ensure overpressure-specific RESERVOIR POWER REQUIRED PROFILES doesn't cause issues
            op_result = GeophiresXResult(self._get_test_file_path(op_example_file))
            op_csv = op_result.as_csv()
            self.assertIsNotNone(op_csv)

        sam_example_file = 'examples/example_SAM-single-owner-PPA.out'
        with self.subTest(msg=sam_example_file):
            sam_result = GeophiresXResult(self._get_test_file_path(sam_example_file))
            sam_csv = sam_result.as_csv()
            self.assertIsNotNone(sam_csv)
            sam_cf_lines = [line.split(',') for line in sam_csv.split('\n') if line.startswith('SAM CASH FLOW PROFILE')]
            self.assertGreater(len(sam_cf_lines), 250)
            # TODO test more of the content (but not full result given how big/complex it is, which would add undue
            #  maintenance overhead)

    def assertCsvFileContentsEqual(self, expected_file_path, actual_file_path, tol=0.01):
        with open(expected_file_path, encoding='utf-8') as ef:
            expected_lines = ef.readlines()
        with open(actual_file_path, encoding='utf-8') as af:
            actual_lines = af.readlines()

        self.assertEqual(len(expected_lines), len(actual_lines), 'The number of lines in the files do not match.')

        for line_index, (expected_line, actual_line) in enumerate(zip(expected_lines, actual_lines), start=1):
            expected_parts = expected_line.strip().split(',')
            actual_parts = actual_line.strip().split(',')
            self.assertEqual(
                len(expected_parts),
                len(actual_parts),
                f'The number of columns in line {line_index} does not match.',
            )
            for col_index, (expected, actual) in enumerate(zip(expected_parts, actual_parts), start=1):
                try:
                    expected_float = float(expected)
                    actual_float = float(actual)
                    self.assertTrue(
                        abs(expected_float - actual_float) < tol,
                        f'Float values differ at line {line_index}, column {col_index}: {expected} != {actual}',
                    )
                except ValueError:
                    self.assertEqual(
                        expected,
                        actual,
                        f'String values differ at line {line_index}, column {col_index}: {expected} != {actual}',
                    )

    def test_parse_chp_percent_cost_allocation(self):
        result = GeophiresXResult(self._get_test_file_path('examples/example3.out'))
        self.assertEqual(
            result.result['ECONOMIC PARAMETERS']['CHP: Percent cost allocation for electrical plant']['value'], 93.48
        )

    def test_parse_annualized_capital_costs(self):
        result = GeophiresXResult(self._get_test_file_path('examples/example1_addons.out'))
        self.assertIsNotNone(result.result['CAPITAL COSTS (M$)']['Annualized capital costs']['value'])

    def test_parse_number_with_commas(self):
        result = GeophiresXResult(self._get_test_file_path('examples/S-DAC-GT.out'))
        sdac_e = result.result['S-DAC-GT ECONOMICS']
        self.assertAlmostEqualWithinPercentage(499_311_405.59, sdac_e['Total Cost of Capture']['value'])

        self.assertAlmostEqualWithinPercentage(0.0017, sdac_e['Geothermal LCOH']['value'])

        self.assertAlmostEqualWithinPercentage(20.7259, sdac_e['Geothermal Ratio (electricity vs heat)']['value'])

    def test_parse_sdacgt_profile(self):
        result = GeophiresXResult(self._get_test_file_path('examples/S-DAC-GT.out'))
        sdacgt_profile = result.result['S-DAC-GT PROFILE']
        self.assertIsNotNone(sdacgt_profile)
        self.assertEqual(
            sdacgt_profile[0],
            [
                'Year Since Start',
                'Carbon Captured (tonne/yr)',
                'Cumm. Carbon Captured (tonne)',
                'S-DAC-GT Annual Cost (USD/yr)',
                'S-DAC-GT Cumm. Cash Flow (USD)',
                'Cumm. Cost Per Tonne (USD/tonne)',
                'Annual Carbon Revenue (USD/yr)',
            ],
        )

        # Values below need to be synchronized if S-DAC-GT example output values change.
        self.assertEqual([1, 78330.8, 78330.8, 17411627.98, 17411627.98, 222.28, 14099544.46], sdacgt_profile[1])

        self.assertEqual(
            [15, 76263.89, 1167207.48, 16952186.81, 259450710.33, 222.28, 13727499.34],
            sdacgt_profile[15],
        )

        self.assertEqual([30, 68860.68, 2253170.17, 15306577.89, 500842063.38, 222.28, 12394922.28], sdacgt_profile[30])

    def test_parse_economic_model(self):
        result = GeophiresXResult(self._get_test_file_path('examples/example3.out'))
        em = result.result['ECONOMIC PARAMETERS']['Economic Model']
        self.assertEqual(em, 'BICYCLE')

        # Test backwards compatibility with previous versions of GEOPHIRES that included an extra space before the
        # equal sign.
        result_legacy_em = GeophiresXResult(self._get_test_file_path('examples/example3.out'))
        result_legacy_em._lines = ['   Economic Model  = BICYCLE']
        em_legacy = result_legacy_em._get_equal_sign_delimited_field('Economic Model')
        self.assertEqual(em_legacy, 'BICYCLE')

    def test_parse_sam_cash_flow_profile(self):
        result = GeophiresXResult(self._get_test_file_path('examples/example_SAM-single-owner-PPA.out'))
        em = result.result['ECONOMIC PARAMETERS']['Economic Model']
        self.assertEqual(em, 'SAM Single Owner PPA')
        self.assertIn('SAM CASH FLOW PROFILE', result.result)

        cash_flow = result.result['SAM CASH FLOW PROFILE']
        self.assertIsNotNone(cash_flow)
        self.assertListEqual([''] + [f'Year {y}' for y in range(21)], cash_flow[0])

    def test_stash_cwd(self):
        start_cwd = Path.cwd()
        GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                {
                    'End-Use Option': EndUseOption.DIRECT_USE_HEAT.value,
                    'Reservoir Model': 1,
                    'Time steps per year': 1,
                    'Reservoir Depth': 3,
                    'Gradient 1': 50,
                }
            )
        )

        self.assertEqual(start_cwd, Path.cwd())

    def _assert_fpc5_input_dict_csv(self, parse_units_and_comments: bool):
        with open(self._get_test_file_path('fpc5-input-params-dict.json'), encoding='utf-8') as f:
            fpc5_input_dict = json.loads(f.read())

            fpc_input_dict_as_csv = ImmutableGeophiresInputParameters(params=fpc5_input_dict).as_csv(
                parse_units_and_comments=parse_units_and_comments
            )
            self.assertEqual(len(fpc5_input_dict.keys()), len(fpc_input_dict_as_csv.splitlines()))

    def test_csv_with_input_parameters(self):
        with self.assertRaises(NotImplementedError):
            # This should fail because CSV from file path is not implemented.
            ImmutableGeophiresInputParameters(from_file_path=self._get_test_file_path('input_comments.txt')).as_csv()

        # Simulate the main use case of adding input parameters to the CSV download from the web interface.
        csv_input = ImmutableGeophiresInputParameters(params={'Reservoir Depth': 3, 'Gradient 1': 50}).as_csv()
        csv_output = GeophiresXResult(self._get_test_file_path('geophires-result_example-1.out')).as_csv()
        csv_parts = csv_output.split(csv.excel.lineterminator, 1)
        csv_result = csv_parts[0] + csv.excel.lineterminator + csv_input + csv_parts[1]

        # Ensure the returned CSV are as expected.
        csv_lines = csv_result.splitlines()
        self.assertEqual('Category,Field,Year,Value,Units', csv_lines[0])
        self.assertEqual('INPUT PARAMETERS,Reservoir Depth,,3,,', csv_lines[1])
        self.assertEqual('INPUT PARAMETERS,Gradient 1,,50,,', csv_lines[2])
        self.assertEqual('SUMMARY OF RESULTS,End-Use Option,,Direct-Use Heat,', csv_lines[3])
        self.assertEqual(
            'HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE,PERCENTAGE OF TOTAL HEAT MINED,25,42.7,%',
            csv_lines[len(csv_lines) - 1],
        )

        # Export the CSV for testing in Excel (or other spreadsheet software).
        result_file = Path(tempfile.gettempdir(), f'geophires-result_{uuid.uuid1()!s}.csv')
        with open(result_file, 'w', newline='', encoding='utf-8') as rf:
            rf.write(csv_result)

        self._assert_fpc5_input_dict_csv(parse_units_and_comments=False)

    def test_csv_with_input_parameters_parse_units_and_comments(self):
        csv_input_with_units_and_comments = ImmutableGeophiresInputParameters(
            params={
                '_COMMENT-0': '# My parameters',
                'Reservoir Depth': '3000 m',
                'Gradient 1': 50,
                'End-Use Option': '1, -- Direct-Use Heat',
                'Construction CAPEX Schedule': '0.014,0.027,0.139,0.431,0.389',
                'Drawdown Parameter Schedule': '0.003,0.001,0.0 * 10,0.001 * 3,0.002 * 3,0.003 * 3,0.004 * 3,0.005 * 4,0.006, -- No drawdown for first 10 years, then 0.005/year',
            }
        ).as_csv(parse_units_and_comments=True)

        # Export the CSV for testing in Excel (or other spreadsheet software).
        result_file = Path(tempfile.gettempdir(), f'geophires-result_{uuid.uuid1()!s}.csv')
        with open(result_file, 'w', newline='', encoding='utf-8') as rf:
            rf.write(csv_input_with_units_and_comments)

        self.assertIsNotNone(csv_input_with_units_and_comments)
        self.assertCsvFileContentsEqual(
            self._get_test_file_path('input-parameters-with-parsed-units-and-comments.csv'), result_file
        )

        self._assert_fpc5_input_dict_csv(parse_units_and_comments=True)
