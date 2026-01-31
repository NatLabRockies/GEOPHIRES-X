from __future__ import annotations

import csv
import json
import math
import re
from io import StringIO
from pathlib import Path
from types import MappingProxyType
from typing import Any
from typing import ClassVar

from geophires_x.GeoPHIRESUtils import is_float
from geophires_x.GeoPHIRESUtils import is_int

from .common import _get_logger
from .geophires_input_parameters import EndUseOption


class _EqualSignDelimitedField:
    def __init__(self, field_name: str):
        self.field_name: str = field_name


class _StringValueField:
    def __init__(self, field_name: str):
        self.field_name: str = field_name


class _UnlabeledStringField:
    def __init__(self, field_name: str, marker_prefixes: list[str]):
        self.field_name: str = field_name
        self.marker_prefixes = marker_prefixes


class GeophiresXResult:
    _RESULT_FIELDS_BY_CATEGORY = MappingProxyType(
        {
            'SUMMARY OF RESULTS': [
                _StringValueField('End-Use Option'),
                _StringValueField('End-Use'),
                _StringValueField('Surface Application'),
                _EqualSignDelimitedField('Reservoir Model'),  # SUTRA only
                'Average Net Electricity Production',
                'Electricity breakeven price',
                'Total CAPEX',
                'Average Direct-Use Heat Production',
                'Direct-Use heat breakeven price',
                'Direct-Use heat breakeven price (LCOH)',
                'Direct-Use Cooling Breakeven Price (LCOC)',
                'Annual District Heating Demand',
                'Average Cooling Production',
                'Average Annual Geothermal Heat Production',
                'Average Annual Peaking Fuel Heat Production',
                'Direct-Use Cooling Breakeven Price',
                'Number of production wells',
                'Number of injection wells',
                'Flowrate per production well',
                'Well depth',
                'Well depth (or total length, if not vertical)',  # deprecated
                'Geothermal gradient',
                'Segment 1   Geothermal gradient',
                'Segment 1   Thickness',
                'Segment 2   Geothermal gradient',
                'Segment 2   Thickness',
                'Segment 3   Geothermal gradient',
                'Segment 3   Thickness',
                'Segment 4   Geothermal gradient',
                # AGS/CLGS
                'LCOE',
                'LCOH',
                'Lifetime Average Well Flow Rate',  # SUTRA
                'Total Avoided Carbon Emissions',
            ],
            'ECONOMIC PARAMETERS': [
                _EqualSignDelimitedField('Economic Model'),
                'Interest Rate',  # %
                'Real Discount Rate',
                'Nominal Discount Rate',
                'WACC',
                'Accrued financing during construction',
                # Displayed for economic models that don't treat inflation costs as capital costs (non-SAM-EM)
                'Inflation costs during construction',
                # Displayed as economic parameter for SAM-EM (non-SAM-EMs treat as capital cost)
                'Investment Tax Credit',
                'Project lifetime',
                'Capacity factor',
                'Project NPV',
                'Project IRR',
                'After-Tax IRR',
                'After-tax IRR',
                'Project VIR=PI=PIR',
                'Project MOIC',
                'Fixed Charge Rate (FCR)',  # SUTRA
                'Project Payback Period',
                'CHP: Percent cost allocation for electrical plant',
                'Estimated Jobs Created',
            ],
            'EXTENDED ECONOMICS': [
                'Adjusted Project LCOE (after incentives, grants, AddOns,etc)',
                'Adjusted Project LCOH (after incentives, grants, AddOns,etc)',
                'Adjusted Project CAPEX (after incentives, grants, AddOns, etc)',
                'Adjusted Project OPEX (after incentives, grants, AddOns, etc)',
                'Project NPV   (including AddOns)',
                'Project IRR   (including AddOns)',
                'Project VIR=PI=PIR   (including AddOns)',
                'Project MOIC  (including AddOns)',
                'Project Payback Period       (including AddOns)',
                'Total Add-on CAPEX',
                'Total Add-on OPEX',
                'Total Add-on Net Elec',
                'Total Add-on Net Heat',
                'Total Add-on Profit',
                'AddOns Payback Period',
                'Royalty Holder NPV',
                'Royalty Holder Average Annual Revenue',
                'Royalty Holder Total Revenue',
            ],
            'CCUS ECONOMICS': [
                'Total Avoided Carbon Production',
                'Project NPV            (including carbon credit)',
                'Project IRR            (including carbon credit)',
                'Project VIR=IR=PIR     (including carbon credit)',
                'Project MOIC           (including carbon credit)',
                'Project Payback Period (including carbon credit)',
            ],
            'S-DAC-GT ECONOMICS': [
                # TODO S-DAC-GT Report sub-titles as string value fields
                'LCOD using grid-based electricity only',
                'LCOD using natural gas only',
                'LCOD using geothermal energy only',
                'CO2 Intensity using grid-based electricity only',
                'CO2 Intensity using natural gas only',
                'CO2 Intensity using geothermal energy only',
                'Geothermal LCOH',
                'Geothermal Ratio (electricity vs heat)',
                'Percent Energy Devoted To Process',
                'Total Cost of Capture',
            ],
            'ENGINEERING PARAMETERS': [
                'Number of Production Wells',
                'Number of Injection Wells',
                'Well depth',
                'Well depth (or total length, if not vertical)',  # deprecated
                'Water loss rate',  # %
                'Pump efficiency',  # %
                'Injection temperature',
                'Injection Temperature',
                'Average production well temperature drop',
                'Flowrate per production well',
                'Injection well casing ID',
                'Production well casing ID',
                'Number of times redrilling',
                _StringValueField('Power plant type'),
                # AGS/CLGS
                _StringValueField('Fluid'),
                _StringValueField('Design'),
                'Flow rate',
                'Lateral Length',
                'Vertical Depth',
                'Wellbore Diameter',
                # SUTRA
                'Lifetime Average Well Flow Rate',
                'Injection well casing ID',
                'Production well casing ID',
            ],
            'RESOURCE CHARACTERISTICS': [
                'Maximum reservoir temperature',
                'Number of segments',
                'Geothermal gradient',
                'Segment 1   Geothermal gradient',
                'Segment 1   Thickness',
                'Segment 2   Geothermal gradient',
                'Segment 2   Thickness',
                'Segment 3   Geothermal gradient',
                'Segment 3   Thickness',
                'Segment 4   Geothermal gradient',
            ],
            'RESERVOIR PARAMETERS': [
                _EqualSignDelimitedField('Reservoir Model'),
                _EqualSignDelimitedField('Fracture model'),
                # TODO moved to power generation profile, parse from there
                #  'Annual Thermal Drawdown (%/year)',
                'Bottom-hole temperature',
                'Well separation: fracture diameter',
                'Well separation: fracture height',
                'Fracture width',
                'Fracture area',
                'Number of fractures',
                'Fracture separation',
                _UnlabeledStringField(
                    'Reservoir volume calculation note',
                    [
                        'Reservoir volume calculated',
                        'Number of fractures calculated',
                        'Fracture separation calculated',
                        'Reservoir volume provided as input',
                    ],
                ),
                'Reservoir volume',
                'Reservoir impedance',
                'Reservoir hydrostatic pressure',
                'Average reservoir pressure',
                'Plant outlet pressure',
                'Production wellhead pressure',
                'Productivity Index',
                'Injectivity Index',
                'Reservoir density',
                'Reservoir thermal conductivity',
                'Reservoir heat capacity',
                'Reservoir porosity',
                'Thermal Conductivity',
            ],
            'RESERVOIR SIMULATION RESULTS': [
                'Maximum Production Temperature',
                'Average Production Temperature',
                'Minimum Production Temperature',
                'Initial Production Temperature',
                'Average Reservoir Heat Extraction',
                _EqualSignDelimitedField('Production Wellbore Heat Transmission Model'),
                _EqualSignDelimitedField('Wellbore Heat Transmission Model'),
                'Average Production Well Temperature Drop',
                'Total Average Pressure Drop',
                'Average Injection Well Pressure Drop',
                'Average Production Pressure',  # AGS
                'Average Reservoir Pressure Drop',
                'Average Production Well Pressure Drop',
                'Average Buoyancy Pressure Drop',
                'Average Injection Well Pump Pressure Drop',
                'Average Production Well Pump Pressure Drop',
                'Average Heat Production',
                'First Year Heat Production',
                'Average Net Electricity Production',
                'First Year Electricity Production',
                'Maximum Storage Well Temperature',
                'Average Storage Well Temperature',
                'Minimum Storage Well Temperature',
                'Maximum Balance Well Temperature',
                'Average Balance Well Temperature',
                'Minimum Balance Well Temperature',
                'Maximum Annual Heat Stored',
                'Average Annual Heat Stored',
                'Minimum Annual Heat Stored',
                'Maximum Annual Heat Supplied',
                'Average Annual Heat Supplied',
                'Minimum Annual Heat Supplied',
                'Average Round-Trip Efficiency',
            ],
            'CAPITAL COSTS (M$)': [
                'Drilling and completion costs',
                'Drilling and completion costs per well',
                'Drilling and completion costs per production well',
                'Drilling and completion costs per injection well',
                'Drilling and completion costs per vertical production well',
                'Drilling and completion costs per vertical injection well',
                'Drilling and completion costs per non-vertical section',
                'Drilling and completion costs (for redrilling)',
                'Drilling and completion costs per redrilled well',
                'Stimulation costs',
                'Stimulation costs (for redrilling)',
                'Surface power plant costs',
                'of which Absorption Chiller Cost',
                'of which Heat Pump Cost',
                'of which Peaking Boiler Cost',
                'Transmission pipeline cost',
                'District Heating System Cost',
                'Field gathering system costs',
                'Total surface equipment costs',
                'Exploration costs',
                'Investment Tax Credit',
                'Overnight Capital Cost',
                # Displayed for economic models that treat inflation costs as capital costs (SAM-EM)
                'Inflation costs during construction',
                'Interest during construction',
                'Total Add-on CAPEX',
                'Total capital costs',
                'Annualized capital costs',
                # AGS/CLGS
                'Total CAPEX',
                'Drilling Cost',
                # SUTRA
                'Drilling and Completion Costs',
                'Drilling and Completion Costs per Well',
                'Drilling and completion costs per production well',
                'Drilling and completion costs per injection well',
                'Auxiliary Heater Cost',
                'Pump Cost',
                'Total Capital Costs',
            ],
            'OPERATING AND MAINTENANCE COSTS (M$/yr)': [
                'Wellfield maintenance costs',
                'Power plant maintenance costs',
                'Water costs',
                'Average Reservoir Pumping Cost',
                'Absorption Chiller O&M Cost',
                'Average Heat Pump Electricity Cost',
                'Annual District Heating O&M Cost',
                'Average Annual Peaking Fuel Cost',
                'Average annual pumping costs',
                'Average Annual Royalty Cost',
                # SUTRA
                'Average annual auxiliary fuel cost',
                'Average annual pumping cost',
                'Redrilling costs',
                'Total Add-on OPEX',
                'Total average annual O&M costs',
                'Total operating and maintenance costs',
                # AGS/CLGS
                'OPEX',
            ],
            'SURFACE EQUIPMENT SIMULATION RESULTS': [
                'Initial geofluid availability',
                'Maximum Total Electricity Generation',
                'Average Total Electricity Generation',
                'Minimum Total Electricity Generation',
                'Initial Total Electricity Generation',
                'Maximum Net Electricity Generation',
                'Average Net Electricity Generation',
                'Minimum Net Electricity Generation',
                'Initial Net Electricity Generation',
                'Average Annual Total Electricity Generation',
                'Average Annual Net Electricity Generation',
                'Maximum Net Heat Production',
                'Average Net Heat Production',
                'Minimum Net Heat Production',
                'Initial Net Heat Production',
                'Average Annual Heat Production',
                'Average Pumping Power',
                'Average Annual Heat Pump Electricity Use',
                'Maximum Cooling Production',
                'Average Cooling Production',
                'Minimum Cooling Production',
                'Initial Cooling Production',
                'Average Annual Cooling Production',
                'Annual District Heating Demand',
                'Maximum Daily District Heating Demand',
                'Average Daily District Heating Demand',
                'Minimum Daily District Heating Demand',
                'Maximum Geothermal Heating Production',
                'Average Geothermal Heating Production',
                'Minimum Geothermal Heating Production',
                'Maximum Peaking Boiler Heat Production',
                'Average Peaking Boiler Heat Production',
                'Minimum Peaking Boiler Heat Production',
                'Initial pumping power/net installed power',
                'Heat to Power Conversion Efficiency',
                # AGS/CLGS
                'Surface Plant Cost',
                # SUTRA
                'Average RTES Heating Production',
                'Average Auxiliary Heating Production',
                'Average Annual RTES Heating Production',
                'Average Annual Auxiliary Heating Production',
                'Average Annual Total Heating Production',
                'Average Annual Electricity Use for Pumping',
            ],
            'Simulation Metadata': [
                _StringValueField('GEOPHIRES Version'),
                'Calculation Time',
            ],
        }
    )

    _METADATA_FIELDS = (
        # 'End-Use Option',
        'Economic Model',
        'Reservoir Model',
    )

    _REVENUE_AND_CASHFLOW_PROFILE_HEADERS: ClassVar[list[str]] = [
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

    CCUS_PROFILE_LEGACY_NAME: ClassVar[str] = 'CCUS PROFILE'
    CARBON_REVENUE_PROFILE_NAME: ClassVar[str] = 'CARBON REVENUE PROFILE'
    _CARBON_PRICE_FIELD_NAME: ClassVar[str] = 'Carbon Price (USD/lb)'

    def __init__(self, output_file_path, logger_name=None):
        if logger_name is None:
            logger_name = __name__
        self._logger = _get_logger(logger_name)
        self.output_file_path = output_file_path

        with open(self.output_file_path, encoding='utf-8') as f:
            self._lines = list(f.readlines())

        self.is_ags_clgs_style_output = '***AGS/CLGS STYLE OUTPUT***' in [_l.strip() for _l in self._lines]

        self._lines_by_category = self._get_lines_by_category()

        # TODO generic-er result value map

        self.result = {}
        for category_fields in GeophiresXResult._RESULT_FIELDS_BY_CATEGORY.items():
            category = category_fields[0]
            fields = category_fields[1]

            self.result[category] = {}
            category_lines = self._lines_by_category.get(category, [])
            search_lines = category_lines if not self.is_ags_clgs_style_output else self._lines

            for field in fields:
                if isinstance(field, _EqualSignDelimitedField):
                    self.result[category][field.field_name] = self._get_equal_sign_delimited_field(
                        field.field_name, search_lines=search_lines
                    )
                elif isinstance(field, _UnlabeledStringField):
                    self.result[category][field.field_name] = self._get_unlabeled_string_field(
                        field.field_name, field.marker_prefixes, search_lines=search_lines
                    )
                else:
                    is_string_field = isinstance(field, _StringValueField)
                    field_name = field.field_name if is_string_field else field
                    indent = 4 if category != 'Simulation Metadata' else 1
                    self.result[category][field_name] = self._get_result_field(
                        field_name,
                        is_string_value_field=is_string_field,
                        min_indentation_spaces=indent,
                        search_lines=search_lines,
                    )

        try:
            self.result['POWER GENERATION PROFILE'] = self._get_power_generation_profile()
            self.result['HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE'] = (
                self._get_heat_electricity_extraction_generation_profile()
            )
        except Exception as e:
            # FIXME
            self._logger.error(f'Failed to parse power and/or extraction profiles: {e}')

        eep = self._get_extended_economic_profile()
        if eep is not None:
            self.result['EXTENDED ECONOMIC PROFILE'] = eep

        revenue_and_cashflow_profile = self._get_revenue_and_cashflow_profile()
        if revenue_and_cashflow_profile is not None:
            self.result['REVENUE & CASHFLOW PROFILE'] = revenue_and_cashflow_profile

        carbon_revenue_or_ccus_profile_key, carbon_revenue_or_ccus_profile = (
            self._get_carbon_revenue_or_ccus_legacy_profile()
        )
        if carbon_revenue_or_ccus_profile is not None:
            self.result[carbon_revenue_or_ccus_profile_key] = carbon_revenue_or_ccus_profile

        sdacgt_profile = self._get_sdacgt_profile()
        if sdacgt_profile is not None:
            self.result['S-DAC-GT PROFILE'] = sdacgt_profile

        sam_cash_flow_profile = self._get_sam_cash_flow_profile()
        if sam_cash_flow_profile is not None:
            self.result['SAM CASH FLOW PROFILE'] = sam_cash_flow_profile

        self.result['metadata'] = {'output_file_path': self.output_file_path}
        for metadata_field in GeophiresXResult._METADATA_FIELDS:
            self.result['metadata'][metadata_field] = self._get_equal_sign_delimited_field(metadata_field)

        if self._get_end_use_option() is not None:
            self.result['metadata']['End-Use Option'] = self._get_end_use_option().name

    def _get_lines_by_category(self) -> dict[str, list[str]]:
        """
        Parses the raw output file lines into a dictionary where keys are
        category headers and values are the lines belonging to that category.
        """
        lines_by_category = {}
        current_category = None
        known_headers = list(self._RESULT_FIELDS_BY_CATEGORY.keys())

        for line in self._lines:

            def get_header_content(h_: str) -> str:
                """
                TODO adjust this to also work with AGS/CLGS-style headers like '### Cost Results ###'
                    For now, AGS-style results are parsed from all lines according to the categories defined in
                    _RESULT_FIELDS_BY_CATEGORY.
                """

                if h_ == 'Simulation Metadata':
                    return h_
                return f'***{h_}***'

            # Check if the line is a category header
            found_header = next((h for h in known_headers if get_header_content(h) == line.strip()), None)

            if found_header:
                current_category = found_header
                if current_category not in lines_by_category:
                    lines_by_category[current_category] = []
            elif current_category:
                # Append the line to the current category if one has been found
                lines_by_category[current_category].append(line)

        return lines_by_category

    @property
    def direct_use_heat_breakeven_price_USD_per_MMBTU(self):
        summary = self.result['SUMMARY OF RESULTS']

        # LCOH suffix added in 49ff3a1213ac778ed53120626807e9a680d1ddcf,
        # check for either (could be reading result generated prior to addition of suffix)
        field_names = ['Direct-Use heat breakeven price', 'Direct-Use heat breakeven price (LCOH)']
        for field_name in field_names:
            if field_name in summary and summary[field_name] is not None:
                return summary[field_name]['value']

        return None

    def as_csv(self) -> str:
        f = StringIO()
        w = csv.writer(f)

        w.writerow(['Category', 'Field', 'Year', 'Value', 'Units'])

        csv_entries = []
        for category, fields in self.result.items():
            if category == 'metadata':
                continue

            if isinstance(fields, dict):
                for field, value_unit in fields.items():

                    class ValueUnit:
                        def __init__(self, v_u):
                            self.value_display = v_u
                            self.unit_display = ''
                            if isinstance(v_u, dict):
                                self.value_display = v_u['value']
                                self.unit_display = v_u['unit']

                    if value_unit is not None:
                        field_display = field.replace(',', r'\,')
                        v_u = ValueUnit(value_unit)
                        csv_entries.append([category, field_display, '', v_u.value_display, v_u.unit_display])
            else:
                if category in (
                    'POWER GENERATION PROFILE',
                    'HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE',
                    'EXTENDED ECONOMIC PROFILE',
                    'REVENUE & CASHFLOW PROFILE',
                    GeophiresXResult.CARBON_REVENUE_PROFILE_NAME,
                    GeophiresXResult.CCUS_PROFILE_LEGACY_NAME,
                    'S-DAC-GT PROFILE',
                ):

                    for i in range(len(fields[0][1:])):
                        field_profile = fields[0][i + 1]
                        name_unit_split = field_profile.split(' (')
                        field_display = name_unit_split[0]
                        unit_display = ''
                        if len(name_unit_split) > 1:
                            unit_display = name_unit_split[1].replace(')', '')
                        for j in range(len(fields[1:])):
                            year_entry = fields[j + 1]
                            year = year_entry[0]
                            profile_year_val = year_entry[i + 1]
                            csv_entries.append([category, field_display, year, profile_year_val, unit_display])
                elif category == 'SAM CASH FLOW PROFILE':
                    for row_num in range(len(fields) - 1):
                        row_idx = row_num + 1
                        row_data = fields[row_idx]
                        if len(row_data) > 1:
                            name_unit_split = GeophiresXResult._get_sam_cash_flow_row_name_unit_split(
                                fields[row_idx][0]
                            )
                            row_name = name_unit_split[0]
                            unit_display = name_unit_split[1]
                            for year in range(len(row_data) - 1):
                                row_datapoint = row_data[year + 1]
                                csv_entries.append([category, row_name, year, row_datapoint, unit_display])

                else:
                    raise RuntimeError(f'Unexpected category: {category}')

        for csv_entry in csv_entries:
            w.writerow(csv_entry)

        return f.getvalue()

    @staticmethod
    def _get_sam_cash_flow_row_name_unit_split(first_entry_in_row) -> list[str]:
        name_unit_split = [it[::-1] for it in first_entry_in_row[::-1].split('( ', maxsplit=1)][::-1]
        if len(name_unit_split) < 2:
            name_unit_split.append('')

        name_unit_split[1] = name_unit_split[1].replace(')', '')
        return name_unit_split

    @property
    def json_output_file_path(self) -> Path:
        return Path(self.output_file_path).with_suffix('.json')

    @property
    def _json_fields(self) -> MappingProxyType:
        # https://github.com/NREL/python-geophires-x/issues/9
        try:
            with open(self.json_output_file_path) as jf:
                return json.loads(''.join(jf.readlines()))
        except FileNotFoundError:
            return {}

    def _get_result_field(
        self,
        field_name: str,
        is_string_value_field: bool = False,
        min_indentation_spaces: int = 4,
        search_lines: list[str] | None = None,
    ):
        if search_lines is None:
            search_lines = self._lines

        # TODO make this less fragile with proper regex
        matching_lines = set(filter(lambda line: f'{min_indentation_spaces * " "}{field_name}: ' in line, search_lines))

        if len(matching_lines) == 0:
            self._logger.debug(f'Field not found: {field_name}')
            return None

        if len(matching_lines) > 1:

            def normalize_spaces(matched_line):
                return re.sub(r'\s+', r' ', matched_line)

            if len({normalize_spaces(_) for _ in matching_lines}) > 1:
                # TODO maybe this should throw a RuntimeError...
                self._logger.error(
                    f'Found multiple ({len(matching_lines)}) entries for field with different values: '
                    f'{field_name}\n\t{matching_lines}'
                )
            else:
                self._logger.debug(
                    f'Found multiple ({len(matching_lines)}) entries for field with same value: '
                    f'{field_name}\n\t{set(matching_lines)}'
                )

        matching_line = matching_lines.pop()
        val_and_unit_str = re.sub(r'\s\s+', '', matching_line.replace(f'{field_name}:', '').replace('\n', ''))
        if is_string_value_field:
            return {'value': val_and_unit_str, 'unit': None}
        val_and_unit_tuple = val_and_unit_str.strip().split(' ')
        str_val = val_and_unit_tuple[0]

        unit = None
        if len(val_and_unit_tuple) == 2:
            unit = val_and_unit_tuple[1]
        elif field_name.startswith('Number'):
            unit = 'count'

        return {'value': self._parse_number(str_val, field=f'field "{field_name}"'), 'unit': unit}

    def _get_equal_sign_delimited_field(self, field_name, search_lines: list[str] | None = None):
        if search_lines is None:
            search_lines = self._lines

        metadata_markers = (
            f'  {field_name} = ',
            # Previous versions of GEOPHIRES erroneously included an extra space after the field name so we include
            # the pattern for it for backwards compatibility with existing .out files.
            f'  {field_name}  = ',
        )
        matching_lines = set(filter(lambda line: any(m in line for m in metadata_markers), search_lines))

        if len(matching_lines) == 0:
            self._logger.debug(f'Equal sign-delimited field not found: {field_name}')
            return None

        if len(matching_lines) > 1:
            self._logger.warning(
                f'Found multiple ({len(matching_lines)}) entries for equal sign-delimited field: '
                f'{field_name}\n\t{matching_lines}'
            )

        matching_line = matching_lines.pop()
        for marker in metadata_markers:
            if marker in matching_line:
                return matching_line.split(marker)[1].replace('\n', '')

        self._logger.error(f'Unexpected error extracting equal sign-delimited field {field_name}')  # Shouldn't happen
        return None

    def _get_unlabeled_string_field(
        self, field_name: str, marker_prefixes: list[str], search_lines: list[str] | None = None
    ):
        if search_lines is None:
            search_lines = self._lines

        matching_lines = set(filter(lambda line: any(m in line for m in marker_prefixes), search_lines))

        if len(matching_lines) == 0:
            self._logger.debug(f'Unlabeled string field not found: {field_name}')
            return None

        if len(matching_lines) > 1:
            self._logger.warning(
                f'Found multiple ({len(matching_lines)}) entries for unlabeled string field: '
                f'{field_name}\n\t{matching_lines}'
            )

        matching_line = matching_lines.pop()
        for marker_prefix in marker_prefixes:
            if marker_prefix in matching_line:
                return matching_line.strip()

        self._logger.error(f'Unexpected error extracting unlabeled string  field {field_name}')  # Shouldn't happen
        return None

    @property
    def power_generation_profile(self) -> list[list[str | float]]:
        return self.result['POWER GENERATION PROFILE']

    def _get_power_generation_profile(self):
        profile_lines = None
        try:
            profile_lines = self._get_profile_lines('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE')
        except IndexError:
            profile_lines = self._get_profile_lines('POWER GENERATION PROFILE')
        return self._get_data_from_profile_lines(profile_lines)

    @property
    def heat_electricity_extraction_generation_profile(self):
        return self.result['HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE']

    def _get_heat_electricity_extraction_generation_profile(self):
        profile_lines = None
        try:
            profile_lines = self._get_profile_lines('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE')
        except IndexError:
            profile_lines = self._get_profile_lines('HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE')
        return self._get_data_from_profile_lines(profile_lines)

    def _get_revenue_and_cashflow_profile(self):
        def extract_table_header(lines: list) -> list:
            # Tried various regexy approaches to extract this programmatically but landed on hard-coding.
            return GeophiresXResult._REVENUE_AND_CASHFLOW_PROFILE_HEADERS

        try:
            lines = self._get_profile_lines('REVENUE & CASHFLOW PROFILE')
            profile = [extract_table_header(lines)]
            if re.fullmatch('^_+$', lines[5]) is not None:
                del lines[5]
            profile.extend(self._extract_addons_style_table_data(lines))
            return profile
        except BaseException as e:
            self._logger.debug(f'Failed to get revenue & cashflow profile: {e}')
            return None

    def _get_extended_economic_profile(self):
        def extract_table_header(lines: list) -> list:
            # Tried various regexy approaches to extract this programmatically but landed on hard-coding.
            return [
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
            ]

        try:
            lines = self._get_profile_lines('EXTENDED ECONOMIC PROFILE')
            profile = [extract_table_header(lines)]
            profile.extend(self._extract_addons_style_table_data(lines))
            return profile
        except BaseException as e:
            self._logger.debug(f'Failed to get extended economic profile: {e}')
            return None

    def _get_sdacgt_profile(self):
        def extract_table_header(lines: list) -> list:
            # Tried various regexy approaches to extract this programmatically but landed on hard-coding.
            return [
                'Year Since Start',
                'Carbon Captured (tonne/yr)',
                'Cumm. Carbon Captured (tonne)',
                'S-DAC-GT Annual Cost (USD/yr)',
                'S-DAC-GT Cumm. Cash Flow (USD)',
                'Cumm. Cost Per Tonne (USD/tonne)',
            ]

        try:
            lines = self._get_profile_lines('S-DAC-GT PROFILE')
            profile = [extract_table_header(lines)]
            profile.extend(self._extract_addons_style_table_data(lines))
            return profile
        except BaseException as e:
            self._logger.debug(f'Failed to get S-DAC-GT profile: {e}')
            return None

    def _get_carbon_revenue_or_ccus_legacy_profile(self) -> tuple:
        """
        :return: tuple[profile key name, profile]
        """

        profile_legacy = self._get_ccus_profile_legacy()
        if profile_legacy is not None:
            # Earlier versions of GEOPHIRES referred to the profile containing carbon revenue as the 'CCUS PROFILE';
            # the name was changed to 'CARBON REVENUE PROFILE' for technical accuracy, as it does not include data
            # for capture or storage, only revenue according to carbon avoided given a carbon price. However, we still
            # check for and parse CCUS profile if it is present in order to retain backwards compatibility in terms
            # of the client being able to read results from previous GEOPHIRES versions.
            return GeophiresXResult.CCUS_PROFILE_LEGACY_NAME, profile_legacy

        revenue_and_cashflow_profile = self._get_revenue_and_cashflow_profile()
        if revenue_and_cashflow_profile is None:
            return None, None

        headers = [
            'Year Since Start',
            # 'Carbon Avoided (pound)', # Present in legacy CCUS profile but not in Revenue & Cashflow
            GeophiresXResult._CARBON_PRICE_FIELD_NAME,  # Legacy field name: 'CCUS Price (USD/lb)'
            'Carbon Ann. Rev. (MUSD/yr)',  # Legacy field name:  'CCUS Revenue (MUSD/yr)'
            # 'CCUS Annual Cash Flow (MUSD/yr)', # Present in legacy CCUS profile but not in Revenue & Cashflow
            'Carbon Cumm. Rev. (MUSD)',  # # Legacy field name: 'CCUS Cumm. Cash Flow (MUSD)'
            # 'Project Annual Cash Flow (MUSD/yr)',  # Present in legacy CCUS profile but not in Revenue & Cashflow
            # 'Project Cumm. Cash Flow (MUSD)',  # Present in legacy CCUS profile but not in Revenue & Cashflow
        ]

        carbon_price_index = revenue_and_cashflow_profile[0].index(GeophiresXResult._CARBON_PRICE_FIELD_NAME)
        has_ccus_profile_in_revenue_and_cashflow = (
            len(revenue_and_cashflow_profile) > 1
            and GeophiresXResult._CARBON_PRICE_FIELD_NAME in revenue_and_cashflow_profile[0]
            # Treat all-zero values as not having CCUS profile
            and any(it != 0 for it in [x[carbon_price_index] for x in revenue_and_cashflow_profile[1:]])
        )

        if not has_ccus_profile_in_revenue_and_cashflow:
            return None, None

        try:
            profile = [headers]

            headers_with_rcp_index = [
                (header, GeophiresXResult._REVENUE_AND_CASHFLOW_PROFILE_HEADERS.index(header)) for header in headers
            ]

            for i in range(1, len(revenue_and_cashflow_profile)):
                ccus_entry = []
                for j in range(len(headers_with_rcp_index)):
                    rcp_index = headers_with_rcp_index[j][1]
                    ccus_entry.append(revenue_and_cashflow_profile[i][rcp_index])
                profile.append(ccus_entry)

            return GeophiresXResult.CARBON_REVENUE_PROFILE_NAME, profile
        except BaseException as e:
            self._logger.debug(f'Failed to get {GeophiresXResult.CARBON_REVENUE_PROFILE_NAME}: {e}')
            return None, None

    def _get_ccus_profile_legacy(self):
        def extract_table_header(lines: list) -> list:
            # Tried various regexy approaches to extract this programmatically but landed on hard-coding.
            return [
                'Year Since Start',
                'Carbon Avoided (pound)',
                'CCUS Price (USD/lb)',  # Carbon Price (USD/tonne)
                'CCUS Revenue (MUSD/yr)',  # Carbon Ann. Rev. (MUSD/yr)
                'CCUS Annual Cash Flow (MUSD/yr)',
                'CCUS Cumm. Cash Flow (MUSD)',  # Carbon Cumm. Rev. (MUSD)
                'Project Annual Cash Flow (MUSD/yr)',
                'Project Cumm. Cash Flow (MUSD)',
            ]

        try:
            lines = self._get_profile_lines(GeophiresXResult.CCUS_PROFILE_LEGACY_NAME)
            profile = [extract_table_header(lines)]
            profile.extend(self._extract_addons_style_table_data(lines))
            return profile
        except BaseException as e:
            self._logger.debug(f'Failed to get legacy {GeophiresXResult.CCUS_PROFILE_LEGACY_NAME}: {e}')
            return None

    def _get_sam_cash_flow_profile(self) -> list[Any]:
        profile_name = 'SAM CASH FLOW PROFILE'

        try:
            s1 = f'*  {profile_name}  *'
            _lines_joined = ''.join(self._lines)
            if s1 not in _lines_joined:
                return None

            profile_text = _lines_joined.split(s1)[1]
            profile_text = re.split(r'^\s*-{20,}\s*$\n?', profile_text, flags=re.MULTILINE)[1]
            rd = csv.reader(StringIO(profile_text), delimiter='\t', skipinitialspace=True)
            profile_lines = []
            for row in rd:
                row_clean = []
                for entry_display in row:
                    row_clean.append(
                        GeophiresXResult._get_sam_cash_flow_profile_entry_display_to_entry_val(entry_display)
                    )
                profile_lines.append(row_clean)

            return profile_lines
        except BaseException as e:
            self._logger.debug(f'Failed to get SAM cash flow profile: {e}')
            return None

    @staticmethod
    def _get_sam_cash_flow_profile_entry_display_to_entry_val(entry_display: str) -> Any:
        if entry_display is None:
            return None

        ed_san = entry_display.strip().replace(',', '') if type(entry_display) is str else entry_display
        if is_float(ed_san):
            if not math.isnan(float(ed_san)):
                return float(ed_san) if not is_int(ed_san) else int(float(ed_san))

        return entry_display.strip()

    def _extract_addons_style_table_data(self, lines: list):
        """TODO consolidate with _get_data_from_profile_lines"""

        # Skip the lines up to the header and split the rest using whitespaces
        lines_splitted = [line.replace('|', '').split() for line in lines[5:]]

        # The number of columns is determined by the line with the most elements
        num_of_columns = max(len(line) for line in lines_splitted)

        table_data = []

        # Parse the contents of each row
        for line in lines_splitted:
            row_data = ['' for _ in range(num_of_columns)]
            while len(line) < num_of_columns:
                line.insert(1, '')

            if not any(line):
                continue

            for i in range(len(line)):
                row_data[i] = self._parse_number(line[i])
            table_data.append(row_data)

        return table_data

    def _get_profile_lines(self, profile_name):
        s1 = f'*  {profile_name}  *'
        s2 = '\n\n'
        return ''.join(self._lines).split(s1)[1].split(s2)[0].split('\n')  # [5:]

    def _get_data_from_profile_lines(self, profile_lines):
        data_lines = profile_lines[5:]

        header_lines = profile_lines[2:5]
        data_headers = None
        for idx, header_line in enumerate(header_lines):
            cols = re.split(r'\s\s+', header_line)[1:]

            if idx == 0:
                data_headers = [''] * len(cols)

            for idxc, col in enumerate(cols):
                data_header_idx = idxc
                if data_headers[0] == 'YEAR' and idx > 0 and idxc >= 0:
                    data_header_idx += 1

                if data_headers[1] == 'THERMAL DRAWDOWN' and idx > 1:  # and idxc > 0:
                    data_header_idx += 1

                data_headers[data_header_idx] = f'{data_headers[data_header_idx]} {col.strip()}'.lstrip()

        data = [data_headers]
        str_entries = filter(lambda entry: len(entry) > 1, [re.split(r'\s+', line)[1:] for line in data_lines])
        data.extend([self._parse_number(str_entry) for str_entry in x] for x in str_entries)
        return data

    def _parse_number(self, number_str, field='string') -> int | float:
        if number_str == 'N/A' or number_str is None:
            return None

        try:
            number_str = number_str.replace(',', '').lower()
            if '.' in number_str or number_str == 'nan':
                # TODO should probably ideally use decimal.Decimal to preserve precision,
                #  i.e. 1.00 for USD instead of 1.0
                return float(number_str)
            else:
                return int(number_str)
        except BaseException:
            self._logger.warning(f'Unable to parse {field} as number: {number_str}')
            return None

    def _get_end_use_option(self) -> EndUseOption:
        try:
            end_use_option_snippet = next(filter(lambda x: 'End-Use Option: ' in x, self._lines)).split(
                'End-Use Option: '
            )[1]

            if 'Direct-Use Heat' in end_use_option_snippet:
                return EndUseOption.DIRECT_USE_HEAT
            elif 'Electricity' in end_use_option_snippet:
                return EndUseOption.ELECTRICITY
        except StopIteration:
            # FIXME clean up
            try:
                end_use_option_snippet = next(filter(lambda x: 'End-Use: ' in x, self._lines)).split('End-Use: ')[1]

                if 'Direct-Use Heat' in end_use_option_snippet:
                    return EndUseOption.DIRECT_USE_HEAT
                elif 'Electricity' in end_use_option_snippet:
                    return EndUseOption.ELECTRICITY
            except StopIteration:
                # FIXME
                self._logger.error('Failed to parse End-Use Option')

        return None
