from __future__ import annotations

import json
from typing import Any

from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters
from tests.base_test_case import BaseTestCase


class GeophiresXResultTestCase(BaseTestCase):

    def test_get_sam_cash_flow_row_name_unit_split(self) -> None:
        cases = [
            ('Electricity to grid (kWh)', ['Electricity to grid', 'kWh']),
            ('Federal tax benefit (liability) ($)', ['Federal tax benefit (liability)', '$']),
            ('Underwater baskets', ['Underwater baskets', '']),
        ]

        for case in cases:
            with self.subTest(msg=case[0]):
                actual = GeophiresXResult._get_sam_cash_flow_row_name_unit_split(case[0])
                self.assertListEqual(actual, case[1])

    def test_get_lines_by_category(self) -> None:
        r: GeophiresXResult = GeophiresXResult(self._get_test_file_path('../examples/example2.out'))
        lines_by_cat = r._get_lines_by_category()
        res_params_lines = lines_by_cat['RESERVOIR PARAMETERS']
        self.assertGreater(len(res_params_lines), 0)

    def test_reservoir_volume_calculation_note(self) -> None:
        r: GeophiresXResult = GeophiresXResult(self._get_test_file_path('../examples/example2.out'))
        field_name = 'Reservoir volume calculation note'
        self.assertIn(field_name, r.result['RESERVOIR PARAMETERS'])
        self.assertEqual(
            r.result['RESERVOIR PARAMETERS'][field_name],
            'Number of fractures calculated with reservoir volume and fracture separation as input',
        )

    def test_sam_econ_model_capex_in_summary(self) -> None:
        r: GeophiresXResult = GeophiresXResult(self._get_test_file_path('../examples/example_SAM-single-owner-PPA.out'))
        field_name = 'Total CAPEX'
        self.assertIn(field_name, r.result['SUMMARY OF RESULTS'])
        self.assertIn('value', r.result['SUMMARY OF RESULTS'][field_name])
        self.assertGreater(r.result['SUMMARY OF RESULTS'][field_name]['value'], 1)
        self.assertEqual(r.result['SUMMARY OF RESULTS'][field_name]['unit'], 'MUSD')

    def test_sam_economic_model_result_csv(self) -> None:
        r: GeophiresXResult = GeophiresXResult(self._get_test_file_path('sam-em-csv-test.out'))
        as_csv = r.as_csv()
        self.assertIsNotNone(as_csv)

    def test_multicategory_fields_only_in_case_report_category(self) -> None:
        r: GeophiresXResult = GeophiresXResult(
            self._get_test_file_path('../examples/example_SAM-single-owner-PPA-3.out')
        )
        self.assertIsNone(r.result['EXTENDED ECONOMICS']['Total Add-on CAPEX'])
        self.assertIsNone(r.result['EXTENDED ECONOMICS']['Total Add-on OPEX'])

        self.assertIn('Total Add-on CAPEX', r.result['CAPITAL COSTS (M$)'])
        self.assertIn('Total Add-on OPEX', r.result['OPERATING AND MAINTENANCE COSTS (M$/yr)'])

        self.assertIsNone(r.result['RESERVOIR SIMULATION RESULTS']['Average Net Electricity Production'])
        self.assertIsNotNone(r.result['SUMMARY OF RESULTS']['Average Net Electricity Production'])
        self.assertIsNotNone(r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Average Net Electricity Generation'])

    def test_ags_clgs_style_output(self) -> None:
        r: GeophiresXResult = GeophiresXResult(
            self._get_test_file_path('../examples/Beckers_et_al_2023_Tabulated_Database_Uloop_sCO2_elec.out')
        )
        self.assertIsNotNone(r.result['SUMMARY OF RESULTS']['LCOE'])

    def test_sutra_reservoir_model_in_summary(self) -> None:
        r: GeophiresXResult = GeophiresXResult(self._get_test_file_path('../examples/SUTRAExample1.out'))
        self.assertEqual('SUTRA Model', r.result['SUMMARY OF RESULTS']['Reservoir Model'])

    def test_produced_temperature_json_output(self) -> None:
        r: GeophiresXResult = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(from_file_path=self._get_test_file_path('client_test_input_1.txt'))
        )
        with open(r.json_output_file_path, encoding='utf-8') as f:
            r_json_obj: dict[str, Any] = json.load(f)

        prod_temp_key: str = 'Produced Temperature'
        self.assertIn(prod_temp_key, r_json_obj)
        self.assertGreater(len(r_json_obj[prod_temp_key]['value']), 100)
        self.assertTrue(all(it > 0 for it in r_json_obj[prod_temp_key]['value']))
