from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from pint.facets.plain import PlainQuantity

from base_test_case import BaseTestCase
from geophires_docs import generate_fervo_project_cape_7_md
from geophires_docs.fervo_project_cape_7_scenarios import FlowRateParametricRow
from geophires_docs.fervo_project_cape_7_scenarios import get_fpc7_flow_rate_parametric_row
from geophires_docs.fervo_project_cape_7_scenarios import get_fpc7_flow_rate_parametric_summary
from geophires_docs.fervo_project_cape_7_scenarios import load_fpc7_flow_rate_parametric
from geophires_x.GeoPHIRESUtils import quantity
from geophires_x.GeoPHIRESUtils import sig_figs
from geophires_x.Parameter import HasQuantity
from geophires_x.ParameterUtils import COMMENT_PARAMETER_NAME_PREFIX
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters


class FervoProjectCape7TestCase(BaseTestCase):

    def test_internal_consistency(self):

        fpc7_result: GeophiresXResult = GeophiresXResult(
            self._get_test_file_path('../examples/Fervo_Project_Cape-7.out')
        )
        fpc7_input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt')
        )
        fpc7_input_params_dict: dict[str, Any] = self._get_input_parameters(fpc7_input_params)

        def _q(dict_val: str) -> PlainQuantity:
            spl = dict_val.split(' ')
            return quantity(float(spl[0]), spl[1])

        lateral_length_q = _q(fpc7_input_params_dict['Nonvertical Length per Multilateral Section'])
        frac_sep_q = quantity(float(fpc7_input_params_dict['Fracture Separation']), 'meter')
        number_of_fracs_per_well = int(fpc7_input_params_dict['Number of Fractures per Stimulated Well'])

        self.assertLess(number_of_fracs_per_well * frac_sep_q, lateral_length_q)

        result_number_of_wells: int = self._number_of_wells(fpc7_result)
        number_of_fracs = int(fpc7_result.result['RESERVOIR PARAMETERS']['Number of fractures']['value'])
        self.assertEqual(number_of_fracs, result_number_of_wells * number_of_fracs_per_well)

        input_num_production_wells: int = int(fpc7_input_params_dict['Number of Production Wells'])
        input_num_injection_wells: int = math.ceil(
            float(fpc7_input_params_dict['Number of Injection Wells per Production Well']) * input_num_production_wells
        )
        fpc7_input_params_number_of_wells = input_num_production_wells + input_num_injection_wells
        self.assertEqual(result_number_of_wells, fpc7_input_params_number_of_wells)

        num_redrills = fpc7_result.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
        total_wells_over_project_lifetime = (1 + num_redrills) * fpc7_input_params_number_of_wells

        additional_future_permitted_wells_factor = (
            1.25  # speculative - see documentation reference source for assumptions
        )
        base_blm_permitted_wells = 320

        self.assertLess(
            total_wells_over_project_lifetime, base_blm_permitted_wells * additional_future_permitted_wells_factor
        )

    @staticmethod
    def _get_input_parameters(
        params: GeophiresInputParameters, include_parameter_comments: bool = False, include_line_comments: bool = False
    ) -> dict[str, Any]:
        """
        TODO consolidate with src/geophires_docs/generate_fervo_project_cape_7_md.py:30 as a common utility function.
            Note doing so is non-trivial because there would need to be a mechanism to ensure parsing exactly matches
            GEOPHIRES behavior, which may diverge from the below implementation under some circumstances.
        """

        comment_idx = 0
        ret: dict[str, Any] = {}
        for line in params.as_text().split('\n'):
            parts = line.strip().split(', ')  # TODO generalize for array-type params
            field = parts[0].strip()
            if len(parts) >= 2 and not field.startswith('#'):
                fieldValue = parts[1].strip()
                if include_parameter_comments and len(parts) > 2:
                    fieldValue += ', ' + (', '.join(parts[2:])).strip()
                ret[field] = fieldValue.strip()

            if include_line_comments and field.startswith('#'):
                ret[f'{COMMENT_PARAMETER_NAME_PREFIX}{comment_idx}'] = line.strip()
                comment_idx += 1

            # TODO preserve newlines

        return ret

    @staticmethod
    def _number_of_wells(result: GeophiresXResult) -> int:
        r: dict[str, dict[str, Any]] = result.result

        number_of_wells = (
            r['SUMMARY OF RESULTS']['Number of injection wells']['value']
            + r['SUMMARY OF RESULTS']['Number of production wells']['value']
        )

        return number_of_wells

    def test_fervo_project_cape_7_results_against_reference_values(self):
        """
        Asserts that the results conform to some of the key reference values claimed in
        docs/Fervo_Project_Cape-7.md{.jinja}.
        """

        r = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt'))
        )

        min_net_gen = r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Minimum Net Electricity Generation']['value']
        self.assertGreater(min_net_gen, 500)
        self.assertLess(min_net_gen, 520)

        max_total_gen = r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Maximum Total Electricity Generation'][
            'value'
        ]
        self.assertGreater(max_total_gen, 600)
        self.assertLess(max_total_gen, 660)  # Exceeding 660 MW would require a 12th 60 MWe Gen 2 ORC unit

        lcoe = r.result['SUMMARY OF RESULTS']['Electricity breakeven price']['value']
        self.assertGreater(lcoe, 9.5)
        self.assertLess(lcoe, 11.5)

        redrills = r.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
        self.assertGreater(redrills, 1)
        self.assertLess(redrills, 6)
        max_phase_2_permitted_wells = 320
        total_wells_over_project_lifetime = self._number_of_wells(r) * (1 + redrills)
        self.assertLessEqual(total_wells_over_project_lifetime, max_phase_2_permitted_wells)
        self.assertGreater(total_wells_over_project_lifetime, max_phase_2_permitted_wells * 0.75)

        # Between Fervo's best demonstrated Phase I well (adjustment factor 0.58) and the unadjusted ATB baseline (0.9)
        well_cost = r.result['CAPITAL COSTS (M$)']['Drilling and completion costs']['value'] / self._number_of_wells(r)
        self.assertLess(well_cost, 10.6)
        self.assertGreater(well_cost, 6.8)

        pumping_power_pct = r.result['SURFACE EQUIPMENT SIMULATION RESULTS'][
            'Initial pumping power/net installed power'
        ]['value']
        self.assertGreater(pumping_power_pct, 20)
        self.assertLess(pumping_power_pct, 30)

        num_prod_wells = r.result['SUMMARY OF RESULTS']['Number of production wells']['value']
        num_inj_wells = r.result['SUMMARY OF RESULTS']['Number of injection wells']['value']
        self.assertTrue(num_prod_wells * 0.5 < num_inj_wells < num_prod_wells)
        self.assertTrue(74 < num_inj_wells + num_prod_wells < 124)

    def test_case_study_documentation(self):
        """
        Parses result values from case study documentation Markdown and checks that they match the actual result.
        Useful for catching when minor updates are made to the case study which need to be manually synced to the
        documentation.

        Note that the relevant Markdown is largely generated from input and result in
        src/geophires_docs/generate_fervo_project_cape_7_md.py, meaning this test is somewhat redundant,
        but it still serves as a useful sanity check for the generated documentation.
        """

        def generate_documentation_markdown() -> None:
            generate_fervo_project_cape_7_md.main(project_root=Path(self._get_test_file_path('../../')).absolute())

        generate_documentation_markdown()  # Ensure we're testing the latest version of the generated doc

        documentation_file_content = '\n'.join(
            self._get_test_file_content('../../docs/Fervo_Project_Cape-7.md', encoding='utf-8')
        )
        inputs_in_markdown = self.parse_markdown_inputs_structured(documentation_file_content)
        results_in_markdown = self.parse_markdown_results_structured(documentation_file_content)

        example_result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-7.out'))

        expected_drilling_cost_MUSD_per_well = 8.48
        # number_of_doublets = inputs_in_markdown['Number of Doublets']['value']
        number_of_wells = self._number_of_wells(example_result)
        self.assertAlmostEqualWithinPercentage(
            expected_drilling_cost_MUSD_per_well * number_of_wells,
            results_in_markdown['Well Drilling and Completion Costs']['value'],
            percent=5,
        )
        self.assertEqual('MUSD', results_in_markdown['Well Drilling and Completion Costs']['unit'])

        expected_base_stim_cost_USD_per_m2 = 0.875
        expected_all_in_stim_cost_MUSD_per_well = 7.25
        self.assertAlmostEqualWithinSigFigs(
            expected_all_in_stim_cost_MUSD_per_well * number_of_wells,
            results_in_markdown['Stimulation Costs']['value'],
            3,
        )
        self.assertEqual('MUSD', results_in_markdown['Stimulation Costs']['unit'])

        self.assertEqual(
            expected_base_stim_cost_USD_per_m2,
            inputs_in_markdown['Reservoir Stimulation Capital Cost per Fracture Surface Area']['value'],
        )
        self.assertEqual(
            'USD/m**2', inputs_in_markdown['Reservoir Stimulation Capital Cost per Fracture Surface Area']['unit']
        )
        self.assertEqual(
            'Stimulated', inputs_in_markdown['Reservoir Stimulation Capital Cost per Production Well']['value']
        )

        class _Q(HasQuantity):
            def __init__(self, vu: dict[str, Any]):
                self.value = vu['value']

                # https://stackoverflow.com/questions/2280334/shortest-way-of-creating-an-object-with-arbitrary-attributes-in-python
                self.CurrentUnits = type('', (), {})()

                self.CurrentUnits.value = vu['unit']

        capex_q = _Q(results_in_markdown['Total CAPEX']).quantity()
        markdown_capex_USD_per_kW = (
            capex_q.to('USD').magnitude
            / _Q(results_in_markdown['Maximum Net Electricity Generation']).quantity().to('kW').magnitude
        )
        self.assertAlmostEqual(
            sig_figs(markdown_capex_USD_per_kW, 2), results_in_markdown['Total CAPEX: $/kW']['value']
        )

        field_mapping = {
            'LCOE': 'Electricity breakeven price',
            'Project capital costs: Total CAPEX': 'Total CAPEX',
            'Well Drilling and Completion Costs': 'Drilling and completion costs per well',
            'Well Drilling and Completion Costs total': 'Drilling and completion costs',
            'Stimulation Costs total': 'Stimulation costs',
            'Reservoir Volume': 'Reservoir volume',
        }

        ignore_keys = [
            'Total CAPEX: $/kW',  # See https://github.com/NREL/GEOPHIRES-X/issues/391
            'Total fracture surface area per production well',
            'Stimulation Costs',  # remapped to 'Stimulation Costs total'
        ]

        example_result_values = {}
        for key, _ in results_in_markdown.items():
            if key not in ignore_keys:
                mapped_key = field_mapping.get(key) if key in field_mapping else key
                entry = example_result._get_result_field(mapped_key)
                if entry is not None and 'value' in entry:
                    entry['value'] = sig_figs(entry['value'], 3)

                example_result_values[key] = entry

        for ignore_key in ignore_keys:
            if ignore_key in results_in_markdown:
                del results_in_markdown[ignore_key]

        result_capex_USD_per_kW = (
            _Q(example_result._get_result_field('Total CAPEX')).quantity().to('USD').magnitude
            / _Q(example_result._get_result_field('Maximum Net Electricity Generation')).quantity().to('kW').magnitude
        )
        self.assertAlmostEqual(sig_figs(result_capex_USD_per_kW, 2), sig_figs(markdown_capex_USD_per_kW, 2))

        num_prod_wells = inputs_in_markdown['Number of Production Wells']['value']
        self.assertEqual(
            example_result.result['SUMMARY OF RESULTS']['Number of production wells']['value'], num_prod_wells
        )

        # Calculate expected total fractures based on input configuration
        num_inj_per_prod = inputs_in_markdown['Number of Injection Wells per Production Well']['value']
        num_inj_wells = math.ceil(num_prod_wells * num_inj_per_prod)
        total_wells = num_prod_wells + num_inj_wells
        num_fracs_per_well = inputs_in_markdown['Number of Fractures per Stimulated Well']['value']

        # Assuming all wells are stimulated
        expected_total_fracs = total_wells * num_fracs_per_well
        self.assertEqual(
            expected_total_fracs, example_result.result['RESERVOIR PARAMETERS']['Number of fractures']['value']
        )

        self.assertAlmostEqual(
            example_result.result['RESERVOIR PARAMETERS']['Reservoir volume']['value'],
            results_in_markdown['Reservoir Volume']['value'],
            delta=1,  # Tolerance for potential formatting/float parsing differences
        )

        additional_expected_stim_indirect_cost_frac = 0.00
        expected_stim_cost_total_MUSD = (
            expected_all_in_stim_cost_MUSD_per_well
            * self._number_of_wells(example_result)
            * (1.0 + additional_expected_stim_indirect_cost_frac)
        )
        self.assertAlmostEqualWithinSigFigs(
            expected_stim_cost_total_MUSD,
            example_result.result['CAPITAL COSTS (M$)']['Stimulation costs']['value'],
            num_sig_figs=3,
        )

    def test_flow_rate_parametric_data_matches_example_result(self) -> None:
        """
        The flow rate parametric data is regenerated manually (see geophires_docs.fervo_project_cape_7_scenarios), so
        this test fails when Fervo_Project_Cape-7 changes without the data being regenerated.
        """
        input_params = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt')
        )
        result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-7.out'))
        base_flow_rate = float(self._get_input_parameters(input_params)['Production Flow Rate per Well'])

        base_row = get_fpc7_flow_rate_parametric_row(load_fpc7_flow_rate_parametric(), base_flow_rate)
        expected_base_row = FlowRateParametricRow.from_result(base_flow_rate, result)
        self.assertEqual(expected_base_row.redrills, base_row.redrills)
        for field_name in ['avg_net_mw', 'min_net_mw', 'lcoe_cents_per_kwh', 'irr_pct', 'npv_musd']:
            with self.subTest(field_name=field_name):
                self.assertAlmostEqual(getattr(expected_base_row, field_name), getattr(base_row, field_name), places=2)

    def test_get_fpc7_flow_rate_parametric_summary(self) -> None:
        def _row(flow: float, min_net_mw: float, redrills: int, irr_pct: float) -> FlowRateParametricRow:
            return FlowRateParametricRow(
                flow_kg_per_s=flow,
                avg_net_mw=min_net_mw + 10,
                min_net_mw=min_net_mw,
                redrills=redrills,
                lcoe_cents_per_kwh=10.0,
                irr_pct=irr_pct,
                npv_musd=300.0,
            )

        rows = [
            _row(90, 480, 1, 25.0),
            _row(91, 490, 2, 22.0),
            _row(92, 500, 2, 23.0),
            _row(93, 510, 2, 23.3),
            _row(94, 520, 2, 23.1),
            _row(95, 530, 3, 21.0),
        ]
        summary = get_fpc7_flow_rate_parametric_summary(rows, 92, 500)
        self.assertEqual(
            [(90, 91, 1, 2), (94, 95, 2, 3)],
            [
                (it.flow_below_kg_per_s, it.flow_at_kg_per_s, it.redrills_below, it.redrills_at)
                for it in summary.redrilling_steps
            ],
        )
        self.assertEqual(92, summary.minimum_ppa_feasible_flow_rate_kg_per_s)
        self.assertEqual(2, summary.base_redrills)
        self.assertAlmostEqual(0.3, summary.max_irr_change_above_base_within_band_pct_pts, places=6)

        with self.assertRaises(ValueError):
            # A flow rate with fewer redrilling events than the base case meets the PPA minimum.
            get_fpc7_flow_rate_parametric_summary([_row(90, 500, 1, 25.0), *rows[1:]], 92, 500)

        with self.assertRaises(ValueError):
            # Base case flow rate is not in the parametric data.
            get_fpc7_flow_rate_parametric_summary(rows, 107, 500)

    def test_scenario_input_parameters(self) -> None:
        input_params = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt')
        )
        result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-7.out'))
        # noinspection PyProtectedMember
        previous_input_params, _ = generate_fervo_project_cape_7_md._get_fpc7_previous_version(
            Path(self._get_test_file_path('../../')).absolute()
        )
        scenario_params = generate_fervo_project_cape_7_md.get_fpc7_scenario_input_parameters(
            input_params, result, previous_input_params
        )

        # Rates and utilization factors stated in the Investment Tax Credit Rate and Utilization Factor discussions and
        # used in the sensitivity analysis, the reduced redrilling scenario's fracture height (+20%), and the February
        # 2026 Update's PPA terms stated in the Modeling Overview.
        self.assertEqual(
            [
                {'Investment Tax Credit Rate': 0.2768},
                {'Utilization Factor': 0.867},
                {'Utilization Factor': 0.822},
                {'Fracture Height': 120.0},
                {
                    'Starting Electricity Sale Price': 0.095,
                    'Electricity Escalation Rate Per Year': 0.00057,
                    'Ending Electricity Sale Price': 1,
                    'Electricity Escalation Start Year': 1,
                },
            ],
            list(scenario_params.values()),
        )

    def test_result_values(self) -> None:
        result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-7.out'))
        values = generate_fervo_project_cape_7_md.get_result_values(result)

        self.assertEqual(round(result.result['ECONOMIC PARAMETERS']['Project NPV']['value'], 1), values['npv_musd'])

        # The SAM Single Owner PPA template's salvage percentage
        self.assertEqual('50', values['salvage_value_pct_of_total_capex'])

        self.assertGreaterEqual(values['min_dscr_year'], 1)
        self.assertGreater(float(values['min_dscr']), 1.0)
        self.assertGreaterEqual(values['debt_tenor_yr'], values['min_dscr_year'])
        self.assertLessEqual(values['debt_tenor_yr'], values['project_lifetime_yr'])

        # The base case redrills, and the remaining reservoir heat content in the annual profile is not reset by
        # redrilling (see the Redrilling Assumptions discussion in the case study documentation).
        self.assertGreater(values['number_of_times_redrilling'], 0)
        self.assertIsNotNone(values['reservoir_heat_content_negative_from_year'])
        self.assertGreater(float(values['final_year_pct_total_heat_mined']), 100.0)

    def test_signed_musd_display(self) -> None:
        # noinspection PyProtectedMember
        display = generate_fervo_project_cape_7_md._get_signed_musd_display

        self.assertEqual('-$13M', display(-12.6))
        self.assertEqual('$337M', display(337.31))
        self.assertEqual('$1,234M', display(1234.4))
        self.assertEqual('$0M', display(-0.4))

    def test_previous_version_comparison_tables(self) -> None:
        # noinspection PyProtectedMember
        previous_input_params, previous_result = generate_fervo_project_cape_7_md._get_fpc7_previous_version(
            Path(self._get_test_file_path('../../')).absolute()
        )
        input_params = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt')
        )
        result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-7.out'))

        input_changes_md = generate_fervo_project_cape_7_md.generate_fpc7_previous_version_input_changes_table_md(
            previous_input_params, input_params
        )
        self.assertIn('| Reservoir Depth | 2.68 km | 3.06 km | Depth at which the reservoir reaches', input_changes_md)
        self.assertIn('| Number of Multilateral Sections | 0 | Not set |', input_changes_md)
        self.assertNotIn('| Fracture Separation |', input_changes_md)  # Unchanged

        # Grouped parameters are consecutive: the removed parameter immediately follows its replacement rather than
        # being appended after this version's parameters.
        table_param_names = [it.split('|')[1].strip() for it in input_changes_md.split('\n')[2:]]
        self.assertEqual(
            table_param_names.index('Number of Multilateral Sections per Vertical Section') + 1,
            table_param_names.index('Number of Multilateral Sections'),
        )
        self.assertEqual(
            table_param_names.index('Injectivity Index') + 1,
            table_param_names.index('Productivity Index'),
        )

        with self.assertRaises(ValueError):
            # Changed parameters without a rationale are not silently omitted.
            generate_fervo_project_cape_7_md.generate_fpc7_previous_version_input_changes_table_md(
                previous_input_params,
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-7.txt'),
                    params={'Fracture Separation': 12},
                ),
            )

        result_changes_md = generate_fervo_project_cape_7_md.generate_fpc7_previous_version_result_changes_table_md(
            previous_result, result
        )
        self.assertIn('| LCOE ($/MWh) | 85.0 |', result_changes_md)
        self.assertIn('| Redrilling events | 3 |', result_changes_md)

        # Previous and this version compared to themselves
        self.assertEqual(
            '| Parameter | February 2026 Update | October 2026 Update | Rationale |\n|---|---|---|---|',
            generate_fervo_project_cape_7_md.generate_fpc7_previous_version_input_changes_table_md(
                input_params, input_params
            ),
        )
        self.assertNotIn(
            'pts',
            generate_fervo_project_cape_7_md.generate_fpc7_previous_version_result_changes_table_md(result, result),
        )

    def test_grouped_param_names(self) -> None:
        # noinspection PyProtectedMember
        grouped = generate_fervo_project_cape_7_md._get_grouped_param_names

        self.assertEqual(['a', 'b', 'c', 'd'], grouped(['a', 'b', 'c', 'd'], []))

        # Group is placed at the position of its first present member, in the listed order
        self.assertEqual(['a', 'd', 'b', 'c', 'e'], grouped(['a', 'b', 'c', 'd', 'e'], [['d', 'b']]))
        self.assertEqual(['a', 'b', 'd', 'c'], grouped(['a', 'b', 'c', 'd'], [['b', 'd']]))

        # Members not present are ignored; groups with fewer than two present members have no effect
        self.assertEqual(['a', 'c', 'b'], grouped(['a', 'b', 'c'], [['x', 'c', 'b', 'y']]))
        self.assertEqual(['a', 'b', 'c'], grouped(['a', 'b', 'c'], [['x', 'c']]))

        # Multiple groups
        self.assertEqual(
            ['b', 'a', 'e', 'c', 'd', 'f'], grouped(['a', 'b', 'c', 'd', 'e', 'f'], [['b', 'a'], ['e', 'c', 'd']])
        )

    def parse_markdown_results_structured(self, markdown_text: str) -> dict:
        """
        Parses result values from markdown into a structured dictionary with values and units.
        """
        raw_results = {}
        table_pattern = re.compile(r'^\s*\|\s*(?!-)([^|]+?)\s*\|\s*([^|]+?)\s*\|', re.MULTILINE)

        # Pattern to strip HTML tags and extract text content
        html_tag_pattern = re.compile(r'<[^>]+>')

        try:
            results_start_index = markdown_text.index('## Results')
            search_area = markdown_text[results_start_index:]

            matches = table_pattern.findall(search_area)

            # Use key_ and value_ to avoid shadowing
            for match in matches:
                key_ = match[0].strip()
                # Strip HTML tags from the key (e.g., <span title="...">LCOE</span> -> LCOE)
                key_ = html_tag_pattern.sub('', key_).strip()
                value_ = match[1].strip()
                if key_.lower() not in ('metric', 'parameter'):
                    raw_results[key_] = value_
        except ValueError:
            print("Warning: '## Results' section not found.")
            return {}

        # Consistency check
        special_case_pattern = re.compile(r'LCOE\s*=\s*(\S+)\s*and\s*IRR\s*=\s*(\S+)')
        special_case_match = special_case_pattern.search(markdown_text)
        if special_case_match:
            lcoe_text = special_case_match.group(1).rstrip('.,;')
            lcoe_table_base = raw_results.get('LCOE', '').split('(')[0].strip()
            if lcoe_text != lcoe_table_base:
                raise ValueError(
                    f'LCOE mismatch: Text value ({lcoe_text}) does not match table value ({lcoe_table_base}).'
                )

        # Now, process the raw results into the structured format
        structured_results = {}
        # Use key_ and value_ to avoid shadowing
        for key_, value_ in raw_results.items():
            if key_ in [
                'After-tax IRR',
                'Average Production Temperature',
                'LCOE',
                'Maximum Total Electricity Generation',
                'Minimum Net Electricity Generation',
                'Maximum Net Electricity Generation',
                'Number of times redrilling',
                'Reservoir Volume',
                'Total CAPEX',
                'Total CAPEX: $/kW',
                'WACC',
                'Well Drilling and Completion Costs',
                'Stimulation Costs',
            ]:
                structured_results[key_] = self._parse_value_unit(value_)

        # Handle drilling and stimulation costs in format: "$464M total ($4.46M/well)"
        for result_with_total_key in ['Well Drilling and Completion Costs', 'Stimulation Costs']:
            entry = structured_results[result_with_total_key]

            unit_str = entry['unit']
            # unit_str is like "total; $4.46M/well" after _parse_value_unit processes "$464M total ($4.46M/well)"
            # The entry['value'] is 464 (total MUSD)
            # We need to extract per-well value from unit string

            # Parse per-well value from the parenthetical part
            per_well_match = re.search(r'\$(\d+\.?\d*)M/well', unit_str)
            if per_well_match:
                per_well_value = float(per_well_match.group(1))
                # Store total in 'X total' key
                structured_results[f'{result_with_total_key} total'] = {
                    'value': entry['value'],
                    'unit': 'MUSD',
                }
                # Update entry to be per-well value
                entry['value'] = per_well_value
                entry['unit'] = 'MUSD/well'

        return structured_results

    def parse_markdown_inputs_structured(self, markdown_text: str) -> dict:
        """
        Parses all input values from all tables under the '## Inputs' section
        of a markdown file into a structured dictionary.
        """
        try:
            # Isolate the content from "## Inputs" to the next "## " header
            sections = re.split(r'(^###\s.*)', markdown_text, flags=re.MULTILINE)
            inputs_header_index = next(i for i, s in enumerate(sections) if s.startswith('### Inputs'))
            inputs_content = sections[inputs_header_index + 1]
        except (StopIteration, IndexError):
            print("Warning: '## Inputs' section not found or is empty.")
            return {}

        raw_inputs = {}
        table_pattern = re.compile(r'^\s*\|\s*(?!-)([^|]+?)\s*\|\s*([^|]+?)\s*\|', re.MULTILINE)
        matches = table_pattern.findall(inputs_content)

        for match in matches:
            key_ = match[0].strip()
            value_ = match[1].strip()
            if key_.lower() not in ('parameter', 'metric'):
                raw_inputs[key_] = value_

        structured_inputs = {}
        for key_, value_ in raw_inputs.items():
            key_ = key_.replace(' ', ' ')
            if key_ == 'Construction CAPEX Schedule':
                parsed_value_unit = {'value': value_, 'unit': 'percent'}
            else:
                parsed_value_unit = self._parse_value_unit(value_)
            structured_inputs[key_] = parsed_value_unit

        return structured_inputs

    # noinspection PyMethodMayBeStatic
    def _parse_value_unit(self, raw_string: str) -> dict:
        """
        A helper function to parse a string and extract a numerical value and its unit.
        It handles various formats like currency, percentages, text, and scientific notation.
        """
        # Split on open parenthesis '(', comma ',' (if not followed by digit), or HTML break tag '<br'
        clean_str = re.split(r'\s*\(|,(?!\s*\d)|<br', raw_string, flags=re.IGNORECASE)[0].strip()

        if clean_str.startswith('$') and ('M total' in clean_str or 'M baseline cost' in clean_str):
            return {'value': float(clean_str.split('M ')[0][1:]), 'unit': 'MUSD'}

        # LCOE format ($X.X/MWh -> cents/kWh)
        match = re.match(r'^\$(\d+\.?\d*)/MWh$', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': round(value / 10, 2), 'unit': 'cents/kWh'}

        # Billion dollar format ($X.XB -> MUSD)
        match = re.match(r'^\$(\d+\.?\d*)B$', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': value * 1000, 'unit': 'MUSD'}

        # Million dollar format ($X.XM or $X.XM/unit)
        match = re.match(r'^\$(\d+\.?\d*)M(\/.*)?$', clean_str)
        if match:
            value = float(match.group(1))
            unit_suffix = match.group(2)
            unit = 'MUSD'
            if unit_suffix:
                unit = f'MUSD{unit_suffix}'
            return {'value': value, 'unit': unit}

        # Dollar per kW format ($X/kW -> USD/kW)
        match = re.match(r'^\$(\d+\.?\d*)/kW$', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': value, 'unit': 'USD/kW'}

        # Dollar per square meter format, optionally followed by additional display data ($X/m² ... -> USD/m**2)
        match = re.match(r'^\$(\d+\.?\d*)/m²', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': value, 'unit': 'USD/m**2'}

        # Percentage format (X.X%)
        match = re.search(r'(\d+\.?\d*)%$', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': value, 'unit': '%'}

        # Temperature format (X℃ -> degC)
        match = re.search(r'(\d+\.?\d*)\s*℃$', clean_str)
        if match:
            value = float(match.group(1))
            return {'value': value, 'unit': 'degC'}

        # Scientific notation format (X.X*10⁶ Y)
        match = re.match(r'^(\d+\.?\d*)\s*[×xX]\s*10[⁶6]\s*(.*)$', clean_str)
        if match:
            base_value = float(match.group(1))
            unit = match.group(2).strip()
            return {'value': base_value * 1e6, 'unit': unit}

        # Generic number and unit parser
        if clean_str.startswith('9⅝'):
            parts = clean_str.split(' ')
            value = 9.0 + 5.0 / 8.0
            unit = parts[1] if len(parts) > 1 else 'unknown'
            return {'value': value, 'unit': unit}

        match = re.search(r'([\d\.,]+)\s*(.*)', clean_str)
        if match:
            value_str = match.group(1).replace(',', '').replace(' ', '')
            unit = match.group(2).strip()

            if '.' in value_str:
                value = float(value_str)
            else:
                value = int(value_str)

            return {'value': value, 'unit': unit if unit else 'count'}

        # Fallback for text-only values
        return {'value': clean_str, 'unit': 'text'}
