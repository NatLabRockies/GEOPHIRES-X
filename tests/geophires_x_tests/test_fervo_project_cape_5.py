from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from pint.facets.plain import PlainQuantity

from base_test_case import BaseTestCase
from geophires_docs import generate_fervo_project_cape_5_md
from geophires_x.GeoPHIRESUtils import quantity
from geophires_x.GeoPHIRESUtils import sig_figs
from geophires_x.Parameter import HasQuantity
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters


class FervoProjectCape5TestCase(BaseTestCase):

    def test_internal_consistency(self):

        fpc5_result: GeophiresXResult = GeophiresXResult(
            self._get_test_file_path('../examples/Fervo_Project_Cape-5.out')
        )
        fpc5_input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-5.txt')
        )
        fpc5_input_params_dict: dict[str, Any] = self._get_input_parameters(fpc5_input_params)

        def _q(dict_val: str) -> PlainQuantity:
            spl = dict_val.split(' ')
            return quantity(float(spl[0]), spl[1])

        lateral_length_q = _q(fpc5_input_params_dict['Nonvertical Length per Multilateral Section'])
        frac_sep_q = quantity(float(fpc5_input_params_dict['Fracture Separation']), 'meter')
        number_of_fracs_per_well = int(fpc5_input_params_dict['Number of Fractures per Stimulated Well'])

        self.assertLess(number_of_fracs_per_well * frac_sep_q, lateral_length_q)

        result_number_of_wells: int = self._number_of_wells(fpc5_result)
        number_of_fracs = int(fpc5_result.result['RESERVOIR PARAMETERS']['Number of fractures']['value'])
        self.assertEqual(number_of_fracs, result_number_of_wells * number_of_fracs_per_well)

        input_num_production_wells: int = int(fpc5_input_params_dict['Number of Production Wells'])
        input_num_injection_wells: int = math.ceil(
            float(fpc5_input_params_dict['Number of Injection Wells per Production Well']) * input_num_production_wells
        )
        fpc5_input_params_number_of_wells = input_num_production_wells + input_num_injection_wells
        self.assertEqual(result_number_of_wells, fpc5_input_params_number_of_wells)

        num_redrills = fpc5_result.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
        total_wells_over_project_lifetime = (1 + num_redrills) * fpc5_input_params_number_of_wells

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
        TODO consolidate with src/geophires_docs/generate_fervo_project_cape_5_md.py:30 as a common utility function.
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
                ret[f'_COMMENT-{comment_idx}'] = line.strip()
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

    def test_fervo_project_cape_5_results_against_reference_values(self):
        """
        Asserts that the results conform to some of the key reference values claimed in
        docs/Fervo_Project_Cape-5.md{.jinja}.
        """

        r = GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-5.txt'))
        )

        min_net_gen = r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Minimum Net Electricity Generation']['value']
        self.assertGreater(min_net_gen, 500)
        self.assertLess(min_net_gen, 505)

        max_total_gen = r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Maximum Total Electricity Generation'][
            'value'
        ]
        self.assertGreater(max_total_gen, 550)
        self.assertLess(max_total_gen, 600)

        lcoe = r.result['SUMMARY OF RESULTS']['Electricity breakeven price']['value']
        self.assertGreater(lcoe, 7.5)
        self.assertLess(lcoe, 8.5)

        redrills = r.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
        self.assertGreater(redrills, 1)
        self.assertLess(redrills, 6)
        max_phase_2_permitted_wells = 320
        self.assertLess(self._number_of_wells(r) * redrills, max_phase_2_permitted_wells)
        self.assertGreater(self._number_of_wells(r) * redrills, max_phase_2_permitted_wells * 0.75)

        well_cost = r.result['CAPITAL COSTS (M$)']['Drilling and completion costs per well']['value']
        self.assertLess(well_cost, 5.0)
        self.assertGreater(well_cost, 4.0)

        pumping_power_pct = r.result['SURFACE EQUIPMENT SIMULATION RESULTS'][
            'Initial pumping power/net installed power'
        ]['value']
        self.assertGreater(pumping_power_pct, 5)
        self.assertLess(pumping_power_pct, 15)

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
        src/geophires_docs/generate_fervo_project_cape_5_md.py, meaning this test is somewhat redundant,
        but it still serves as a useful sanity check for the generated documentation.
        """

        def generate_documentation_markdown() -> None:
            generate_fervo_project_cape_5_md.main(project_root=Path(self._get_test_file_path('../../')).absolute())

        generate_documentation_markdown()  # Ensure we're testing the latest version of the generated doc

        documentation_file_content = '\n'.join(
            self._get_test_file_content('../../docs/Fervo_Project_Cape-5.md', encoding='utf-8')
        )
        inputs_in_markdown = self.parse_markdown_inputs_structured(documentation_file_content)
        results_in_markdown = self.parse_markdown_results_structured(documentation_file_content)

        example_result = GeophiresXResult(self._get_test_file_path('../examples/Fervo_Project_Cape-5.out'))

        expected_drilling_cost_MUSD_per_well = 4.46
        # number_of_doublets = inputs_in_markdown['Number of Doublets']['value']
        number_of_wells = self._number_of_wells(example_result)
        self.assertAlmostEqualWithinPercentage(
            expected_drilling_cost_MUSD_per_well * number_of_wells,
            results_in_markdown['Well Drilling and Completion Costs']['value'],
            percent=5,
        )
        self.assertEqual('MUSD', results_in_markdown['Well Drilling and Completion Costs']['unit'])

        expected_base_stim_cost_MUSD_per_well = 4.0
        expected_all_in_stim_cost_MUSD_per_well = 4.83
        self.assertAlmostEqualWithinSigFigs(
            expected_all_in_stim_cost_MUSD_per_well * number_of_wells,
            results_in_markdown['Stimulation Costs']['value'],
            3,
        )
        self.assertEqual('MUSD', results_in_markdown['Stimulation Costs']['unit'])

        self.assertEqual(
            expected_base_stim_cost_MUSD_per_well,
            inputs_in_markdown['Reservoir Stimulation Capital Cost per Production Well']['value'],
        )
        self.assertEqual('MUSD', inputs_in_markdown['Reservoir Stimulation Capital Cost per Production Well']['unit'])

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

    def test_fervo_project_cape_6(self) -> None:
        """
        Fervo_Project_Cape-6 is derived from Fervo_Project_Cape-5 - see tests/regenerate-example-result.sh
        """

        fpc5_result: GeophiresXResult = GeophiresXResult(
            self._get_test_file_path('../examples/Fervo_Project_Cape-6.out')
        )

        min_net_gen_dict = fpc5_result.result['SURFACE EQUIPMENT SIMULATION RESULTS'][
            'Minimum Net Electricity Generation'
        ]
        fpc5_min_net_gen_mwe = quantity(min_net_gen_dict['value'], min_net_gen_dict['unit']).to('MW').magnitude
        self.assertGreater(fpc5_min_net_gen_mwe, 100)

        max_total_gen_dict = fpc5_result.result['SURFACE EQUIPMENT SIMULATION RESULTS'][
            'Maximum Total Electricity Generation'
        ]
        fpc5_max_total_net_gen_mwe = (
            quantity(max_total_gen_dict['value'], max_total_gen_dict['unit']).to('MW').magnitude
        )
        self.assertLess(fpc5_max_total_net_gen_mwe, 120)
