#!python
"""
Script to generate Fervo_Project_Cape-5.md from its jinja template.
This ensures the markdown documentation stays in sync with actual GEOPHIRES results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from jinja2 import Environment
from jinja2 import FileSystemLoader
from pint.facets.plain import PlainQuantity

from geophires_docs import _PROJECT_ROOT
from geophires_docs import _get_fpc5_input_file_path
from geophires_docs import _get_fpc5_result_file_path
from geophires_docs import _get_input_parameters_dict
from geophires_docs import _get_logger
from geophires_docs import _get_project_root
from geophires_x.GeoPHIRESUtils import is_int
from geophires_x.GeoPHIRESUtils import sig_figs
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters

# Module-level variable to hold the current project root for schema access
_current_project_root: Path | None = None

_log = _get_logger(__name__)
_NON_BREAKING_SPACE = '\xa0'


def _get_schema(schema_file_name: str) -> dict[str, Any]:
    project_root = _current_project_root if _current_project_root is not None else _get_project_root()
    schema_file = project_root / 'src/geophires_x_schema_generator' / schema_file_name
    with open(schema_file, encoding='utf-8') as f:
        return json.loads(f.read())


def _get_geophires_request_schema() -> dict[str, Any]:
    return _get_schema('geophires-request.json')


def _get_input_parameter_schema(param_name: str) -> dict[str, Any]:
    return _get_geophires_request_schema()['properties'][param_name]


def _get_input_parameter_schema_type(param_name: str) -> dict[str, Any]:
    return _get_input_parameter_schema(param_name)['type']


def _get_input_parameter_category(param_name: str) -> str:
    return _get_input_parameter_schema(param_name)['category']


def _get_input_parameter_units(param_name: str) -> str | None:
    unit = _get_geophires_request_schema()['properties'][param_name]['units']

    if unit == '':
        return 'dimensionless'

    return unit


def _get_geophires_result_schema() -> dict[str, Any]:
    return _get_schema('geophires-result.json')


def _get_output_parameter_schema(param_name: str) -> dict[str, Any]:
    categorized_schema: dict[str, dict[str, Any]] = _get_geophires_result_schema()['properties']

    for _category, category_data in categorized_schema.items():
        if param_name in category_data['properties']:
            return category_data['properties'][param_name]

    raise ValueError(f'Parameter "{param_name}" not found in GEOPHIRES result schema.')


def _get_output_parameter_description(param_name: str) -> str:
    return _get_output_parameter_schema(param_name)['description']


def _get_unit_display(parameter_units_from_schema: str) -> str:
    if parameter_units_from_schema is None:
        return ''

    display_unit_prefix = (
        ' '
        if not (parameter_units_from_schema and any(it in parameter_units_from_schema for it in ['%', 'USD', 'MUSD']))
        else ''
    )
    display_unit = parameter_units_from_schema
    for replacement in [
        ('kilometer', 'km'),
        ('degC', '℃'),
        ('meter', 'm'),
        ('m**3', 'm³'),
        ('m**2', 'm²'),
        ('MUSD', 'M'),
        ('USD', ''),
    ]:
        display_unit = display_unit.replace(replacement[0], replacement[1])

    return f'{display_unit_prefix}{display_unit}'


def generate_fpc_reservoir_parameters_table_md(input_params: GeophiresInputParameters, result: GeophiresXResult) -> str:
    params_to_exclude = [
        'Maximum Temperature',
        'Reservoir Porosity',
        'Reservoir Volume Option',
    ]

    return get_fpc_category_parameters_table_md(input_params, 'Reservoir', params_to_exclude)


def generate_fpc_well_bores_parameters_table_md(
    input_params: GeophiresInputParameters, result: GeophiresXResult
) -> str:
    return get_fpc_category_parameters_table_md(
        input_params,
        'Well Bores',
        parameters_to_exclude=['Number of Multilateral Sections'],
    )


def generate_fpc_surface_plant_parameters_table_md(
    input_params: GeophiresInputParameters, result: GeophiresXResult
) -> str:
    return get_fpc_category_parameters_table_md(
        input_params,
        'Surface Plant',
        parameters_to_exclude=['End-Use Option', 'Construction Years'],
    )


def generate_fpc_construction_parameters_table_md(
    input_params: GeophiresInputParameters, result: GeophiresXResult
) -> str:
    input_params_dict = _get_input_parameters_dict(
        input_params, include_parameter_comments=True, include_line_comments=True
    )
    schedule_param_name = 'Construction CAPEX Schedule'
    construction_input_params = {}
    for construction_param in ['Construction Years', schedule_param_name]:
        construction_input_params[construction_param] = input_params_dict[construction_param]

    # Comment hardcoded here for now because handling of array parameters with comments might be buggy in client or
    # web interface...
    schedule_param_comment = (
        'Array of fractions of overnight capital cost expenditure for each year, starting with '
        'lower costs during initial years for exploration and increasing to higher costs during '
        'later years as buildout progresses.'
    )
    construction_input_params[schedule_param_name] = (
        f'{construction_input_params[schedule_param_name]}' f', -- {schedule_param_comment}'
    )

    return get_fpc_category_parameters_table_md(
        ImmutableGeophiresInputParameters(params=construction_input_params), None
    )


def generate_fpc_economics_parameters_table_md(input_params: GeophiresInputParameters, result: GeophiresXResult) -> str:
    stim_cost_per_well_additional_display_data = f' baseline cost; ${_stim_costs_per_well_musd(result)}M all-in cost'

    drilling_cost_per_well_additional_display_data = (
        f' (Yields all-in cost of ' f'${sig_figs(_drilling_costs_per_well_musd(result),3)}M/well)'
    )

    # Doesn't seem to work as intended...
    drilling_cost_per_well_additional_display_data = drilling_cost_per_well_additional_display_data.replace(
        ' ', _NON_BREAKING_SPACE
    )

    return get_fpc_category_parameters_table_md(
        input_params,
        'Economics',
        parameters_to_exclude=[
            'Ending Electricity Sale Price',
            'Electricity Escalation Start Year',
            'Construction CAPEX Schedule',
            'Time steps per year',
            'Print Output to Console',
        ],
        additional_display_data_by_param_name={
            'Reservoir Stimulation Capital Cost per Production Well': stim_cost_per_well_additional_display_data,
            'Reservoir Stimulation Capital Cost per Injection Well': stim_cost_per_well_additional_display_data,
            'Well Drilling and Completion Capital Cost Adjustment Factor': drilling_cost_per_well_additional_display_data,
        },
    )


def get_fpc_category_parameters_table_md(
    input_params: GeophiresInputParameters,
    category_name: str | None,
    parameters_to_exclude: list[str] | None = None,
    additional_display_data_by_param_name: dict[str, str] | None = None,
) -> str:
    if parameters_to_exclude is None:
        parameters_to_exclude = []

    if additional_display_data_by_param_name is None:
        additional_display_data_by_param_name = {}

    input_params_dict = _get_input_parameters_dict(
        input_params, include_parameter_comments=True, include_line_comments=True
    )

    # noinspection MarkdownIncorrectTableFormatting
    table_md = f"""
| Parameter         | Input{_NON_BREAKING_SPACE}Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
"""

    table_entries = []
    for param_name, param_val_comment in input_params_dict.items():
        if param_name.startswith(('#', '_COMMENT-')):
            continue

        if param_name in parameters_to_exclude:
            continue

        category = _get_input_parameter_category(param_name)
        if category_name is None or category == category_name:
            param_val_comment_split = param_val_comment.split(
                # ',',
                ',' if _get_input_parameter_schema_type(param_name) != 'array' else ', ',
                maxsplit=1,
            )

            param_val = param_val_comment_split[0]

            param_comment = (
                param_val_comment_split[1].replace('-- ', '') if len(param_val_comment_split) > 1 else ' .. N/A '
            )
            param_unit = _get_input_parameter_units(param_name)
            if param_unit == 'dimensionless':
                param_unit_display = '%'
                param_val = sig_figs(
                    PlainQuantity(float(param_val), 'dimensionless').to('percent').magnitude,
                    10,  # trim floating point errors
                )
            elif param_unit == 'USD/kWh':
                price_unit = 'USD/MWh'
                param_unit_display = _get_unit_display(price_unit)
                param_val = sig_figs(
                    PlainQuantity(float(param_val), 'USD/kWh').to(price_unit).magnitude,
                    10,  # trim floating point errors
                )
            elif ' ' in param_val:
                param_val_split = param_val.split(' ', maxsplit=1)
                param_val = param_val_split[0]
                param_unit_display = _get_unit_display(param_val_split[1])
            else:
                param_unit_display = _get_unit_display(param_unit)

            param_unit_display_prefix = '$' if param_unit and 'USD' in param_unit else ''

            if is_int(param_val):
                param_val = int(param_val)

            param_schema = _get_input_parameter_schema(param_name)
            if param_schema and 'enum_values' in param_schema:
                for enum_value in param_schema['enum_values']:
                    if enum_value['int_value'] == param_val:
                        enum_display = enum_value['value']
                        # param_val = f'{param_val} ({enum_display})'
                        param_val = enum_display
                        break

            param_name_display = param_name.replace(' ', _NON_BREAKING_SPACE, 2)

            additional_display_data = additional_display_data_by_param_name.get(param_name, '')

            table_entries.append(
                [
                    param_name_display,
                    f'{param_unit_display_prefix}{param_val}{param_unit_display}{additional_display_data}',
                    param_comment,
                ]
            )

    for table_entry in table_entries:
        table_md += f'| {table_entry[0]} | {table_entry[1]} | {table_entry[2]} |\n'

    return table_md.strip()


def _q(d: dict[str, Any]) -> PlainQuantity:
    return PlainQuantity(d['value'], d['unit'])


def get_fpc5_input_parameter_values(input_params: GeophiresInputParameters, result: GeophiresXResult) -> dict[str, Any]:
    _log.info('Extracting input parameter values...')

    params = _get_input_parameters_dict(input_params)
    r: dict[str, dict[str, Any]] = result.result

    exploration_cost_musd = _q(r['CAPITAL COSTS (M$)']['Exploration costs']).to('MUSD').magnitude
    assert exploration_cost_musd == float(
        params['Exploration Capital Cost']
    ), 'Exploration cost mismatch between parameters and result'

    return {
        'exploration_cost_musd': round(sig_figs(exploration_cost_musd, 2)),
        'wacc_pct': sig_figs(r['ECONOMIC PARAMETERS']['WACC']['value'], 3),
        'reservoir_volume_m3': f"{r['RESERVOIR PARAMETERS']['Reservoir volume']['value']:,}",
    }


def get_max_net_generation_mwe(result: GeophiresXResult) -> float:
    r: dict[str, dict[str, Any]] = result.result
    return _q(r['SURFACE EQUIPMENT SIMULATION RESULTS']['Maximum Net Electricity Generation']).to('MW').magnitude


def get_result_values(result: GeophiresXResult) -> dict[str, Any]:
    _log.info('Extracting result values...')

    r: dict[str, dict[str, Any]] = result.result

    econ = r['ECONOMIC PARAMETERS']

    total_capex_q: PlainQuantity = _q(r['CAPITAL COSTS (M$)']['Total CAPEX'])

    surf_equip_sim = r['SURFACE EQUIPMENT SIMULATION RESULTS']
    min_net_generation_mwe = surf_equip_sim['Minimum Net Electricity Generation']['value']
    avg_net_generation_mwe = surf_equip_sim['Average Net Electricity Generation']['value']
    max_net_generation_mwe = get_max_net_generation_mwe(result)
    max_total_generation_mwe = surf_equip_sim['Maximum Total Electricity Generation']['value']
    parasitic_loss_pct = (
        surf_equip_sim['Average Pumping Power']['value']
        / surf_equip_sim['Average Total Electricity Generation']['value']
        * 100.0
    )
    net_power_idx = result.power_generation_profile[0].index('NET POWER (MW)')

    def n_year_avg_net_power_mwe(years: int) -> float:
        return np.average([it[net_power_idx] for it in result.power_generation_profile[1:]][:years])

    two_year_avg_net_power_mwe = n_year_avg_net_power_mwe(2)
    two_year_avg_net_power_mwe_per_production_well = two_year_avg_net_power_mwe / _number_of_production_wells(result)

    total_fracture_surface_area_per_well_m2 = _total_fracture_surface_area_per_well_m2(result)

    occ_q = _q(r['CAPITAL COSTS (M$)']['Overnight Capital Cost'])

    field_gathering_cost_musd = _q(r['CAPITAL COSTS (M$)']['Field gathering system costs']).to('MUSD').magnitude
    field_gathering_cost_pct_occ = field_gathering_cost_musd / occ_q.to('MUSD').magnitude * 100.0

    redrills = r['ENGINEERING PARAMETERS']['Number of times redrilling']['value']
    total_wells_including_redrilling = (1 + redrills) * _number_of_wells(result)

    return {
        # Economic Results
        'lcoe_usd_per_mwh': sig_figs(
            _q(r['SUMMARY OF RESULTS']['Electricity breakeven price']).to('USD / MWh').magnitude, 3
        ),
        'irr_pct': sig_figs(econ['After-tax IRR']['value'], 3),
        'operations_year_of_irr': econ['Project lifetime']['value'],
        'npv_musd': sig_figs(econ['Project NPV']['value'], 3),
        'project_moic': sig_figs(econ['Project MOIC']['value'], 3),
        'project_vir': sig_figs(econ['Project VIR=PI=PIR']['value'], 3),
        # Capital Costs
        'drilling_costs_musd': round(sig_figs(_drilling_costs_musd(result), 3)),
        'drilling_costs_per_well_musd': sig_figs(_drilling_costs_per_well_musd(result), 3),
        'stim_costs_musd': round(sig_figs(_stim_costs_musd(result), 3)),
        'stim_costs_per_well_musd': sig_figs(_stim_costs_per_well_musd(result), 3),
        'surface_power_plant_costs_gusd': sig_figs(
            _q(r['CAPITAL COSTS (M$)']['Surface power plant costs']).to('GUSD').magnitude, 3
        ),
        'field_gathering_cost_musd': round(sig_figs(field_gathering_cost_musd, 3)),
        'field_gathering_cost_pct_occ': round(sig_figs(field_gathering_cost_pct_occ, 1)),
        'occ_gusd': sig_figs(occ_q.to('GUSD').magnitude, 3),
        'total_capex_gusd': sig_figs(total_capex_q.to('GUSD').magnitude, 3),
        'capex_usd_per_kw': round(
            sig_figs((total_capex_q / PlainQuantity(max_net_generation_mwe, 'MW')).to('USD / kW').magnitude, 2)
        ),
        # Technical & Engineering Results
        'bht_temp_degc': r['RESERVOIR PARAMETERS']['Bottom-hole temperature']['value'],
        'min_net_generation_mwe': round(sig_figs(min_net_generation_mwe, 3)),
        'avg_net_generation_mwe': round(sig_figs(avg_net_generation_mwe, 3)),
        'max_net_generation_mwe': round(sig_figs(max_net_generation_mwe, 3)),
        'max_total_generation_mwe': round(sig_figs(max_total_generation_mwe, 3)),
        'two_year_avg_net_power_mwe_per_production_well': sig_figs(two_year_avg_net_power_mwe_per_production_well, 2),
        'parasitic_loss_pct': sig_figs(parasitic_loss_pct, 3),
        'number_of_times_redrilling': redrills,
        'total_wells_including_redrilling': total_wells_including_redrilling,
        'initial_production_temperature_degc': round(
            sig_figs(r['RESERVOIR SIMULATION RESULTS']['Initial Production Temperature']['value'], 3)
        ),
        'average_production_temperature_degc': round(
            sig_figs(r['RESERVOIR SIMULATION RESULTS']['Average Production Temperature']['value'], 3)
        ),
        'total_fracture_surface_area_per_well_mm2': sig_figs(total_fracture_surface_area_per_well_m2 / 1e6, 2),
        'total_fracture_surface_area_per_well_mft2': round(
            sig_figs(
                PlainQuantity(total_fracture_surface_area_per_well_m2, 'm ** 2').to('foot ** 2').magnitude * 1e-6, 2
            )
        ),
        # TODO port all input and result values here instead of hardcoding them in the template
    }


def _number_of_production_wells(result: GeophiresXResult) -> int:
    return result.result['SUMMARY OF RESULTS']['Number of production wells']['value']


def _number_of_wells(result: GeophiresXResult) -> int:
    r: dict[str, dict[str, Any]] = result.result

    number_of_wells = r['SUMMARY OF RESULTS']['Number of injection wells']['value'] + _number_of_production_wells(
        result
    )

    return number_of_wells


def _drilling_costs_musd(result: GeophiresXResult) -> float:
    r: dict[str, dict[str, Any]] = result.result

    return _q(r['CAPITAL COSTS (M$)']['Drilling and completion costs']).to('MUSD').magnitude


def _drilling_costs_per_well_musd(result: GeophiresXResult) -> float:
    return _drilling_costs_musd(result) / _number_of_wells(result)


def _stim_costs_per_well_musd(result: GeophiresXResult) -> float:
    stim_costs_per_well_musd = _stim_costs_musd(result) / _number_of_wells(result)
    return stim_costs_per_well_musd


def _stim_costs_musd(result: GeophiresXResult) -> float:
    r: dict[str, dict[str, Any]] = result.result

    stim_costs_musd = _q(r['CAPITAL COSTS (M$)']['Stimulation costs']).to('MUSD').magnitude
    return stim_costs_musd


def _total_fracture_surface_area_per_well_m2(result: GeophiresXResult) -> float:
    r: dict[str, dict[str, Any]] = result.result
    res_params = r['RESERVOIR PARAMETERS']
    return (
        _q(res_params['Fracture area']).to('m ** 2').magnitude
        * res_params['Number of fractures']['value']
        / _number_of_wells(result)
    )


def generate_res_eng_reference_sim_params_table_md(
    base_case_input_params: GeophiresInputParameters, res_eng_reference_sim_params: dict[str, Any]
) -> str:
    return get_fpc_category_parameters_table_md(
        ImmutableGeophiresInputParameters(
            # from_file_path=base_case_input_params.as_file_path(),
            params=res_eng_reference_sim_params
        ),
        None,
    )


def generate_fpc_opex_output_table_md(input_params: GeophiresInputParameters, result: GeophiresXResult) -> str:
    table_md = """| Metric | Result Value | Reference Value(s) | Reference Source |
|-----|-----|-----|-----|\n"""

    for output_param_name, result_value_unit_dict in result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)'].items():
        if result_value_unit_dict is None:
            continue

        unit = result_value_unit_dict['unit']
        value_unit_display = (
            f'${result_value_unit_dict["value"]}M/yr'
            if unit == 'MUSD/yr'
            else f'{result_value_unit_dict["value"]} {unit}'
        )

        reference_value_display = '.. N/A'

        if output_param_name == 'Total operating and maintenance costs':
            reference_source_display = '.. N/A '
        else:
            reference_source_display = _get_output_parameter_description(output_param_name)

            if output_param_name == 'Water costs':
                water_cost_adjustment_param_name = 'Water Cost Adjustment Factor'
                reference_source_display = reference_source_display.split(
                    f'. Provide {water_cost_adjustment_param_name}', maxsplit=1
                )[0]
                water_cost_adjustment_percent = (
                    PlainQuantity(
                        float(_get_input_parameters_dict(input_params)[water_cost_adjustment_param_name]),
                        'dimensionless',
                    )
                    .to('percent')
                    .magnitude
                )
                reference_source_display = (
                    f'{reference_source_display}. '
                    f'The default correlation is adjusted by the {water_cost_adjustment_param_name} parameter value '
                    f'of {water_cost_adjustment_percent:.0f}%.'
                )

            if reference_source_display.startswith(('O&M', 'Total O&M')):
                reference_source_display = reference_source_display.split('. ', maxsplit=1)[1]

            for suffix in ('s', ''):
                reference_source_display = reference_source_display.replace(f'O&M cost{suffix}', 'OPEX')

        table_md += (
            f'| {output_param_name} | {value_unit_display} | {reference_value_display} | {reference_source_display} |\n'
        )

        if output_param_name == 'Total operating and maintenance costs':
            opex_usd_per_kw_per_year = (
                _q(result_value_unit_dict) / PlainQuantity(get_max_net_generation_mwe(result), 'MW')
            ).to('USD / year / kilowatt')

            reference_source = '2024b ATB: 2028 Deep EGS Binary Conservative Scenario (NREL, 2025). '
            # TODO explain why we're higher than ATB (e.g. redrilling not modeled by ATB)

            table_md += f'| {output_param_name}: $/kW-yr | ${opex_usd_per_kw_per_year.magnitude:.2f}/kW-yr | $226.31/kW-yr | {reference_source} |\n'

    return table_md


def generate_fervo_project_cape_5_md(
    input_params: GeophiresInputParameters,
    result: GeophiresXResult,
    res_eng_reference_sim_params: dict[str, Any] | None = None,
    project_root: Path = _PROJECT_ROOT,
) -> None:
    if res_eng_reference_sim_params is None:
        res_eng_reference_sim_params = {}

    result_values: dict[str, Any] = get_result_values(result)

    # noinspection PyDictCreation
    template_values = {**get_fpc5_input_parameter_values(input_params, result), **result_values}

    for template_key, md_method in {
        'opex_result_outputs_table_md': generate_fpc_opex_output_table_md,
        'reservoir_parameters_table_md': generate_fpc_reservoir_parameters_table_md,
        'surface_plant_parameters_table_md': generate_fpc_surface_plant_parameters_table_md,
        'well_bores_parameters_table_md': generate_fpc_well_bores_parameters_table_md,
        'economics_parameters_table_md': generate_fpc_economics_parameters_table_md,
        'construction_parameters_table_md': generate_fpc_construction_parameters_table_md,
    }.items():
        template_values[template_key] = md_method(input_params, result)

    template_values['reservoir_engineering_reference_simulation_params_table_md'] = (
        generate_res_eng_reference_sim_params_table_md(input_params, res_eng_reference_sim_params)
    )

    docs_dir = project_root / 'docs'

    # Set up Jinja environment
    env = Environment(loader=FileSystemLoader(docs_dir), autoescape=True)
    template = env.get_template('Fervo_Project_Cape-5.md.jinja')

    # Render template
    _log.info('Rendering template...')
    output = template.render(**template_values)

    # Write output
    output_file = docs_dir / 'Fervo_Project_Cape-5.md'
    output_file.write_text(output, encoding='utf-8')

    _log.info(f'✓ Generated {output_file}')
    _log.info('\nKey results:')
    _log.info(f"\tLCOE: ${template_values['lcoe_usd_per_mwh']}/MWh")
    _log.info(f"\tIRR: {template_values['irr_pct']}%")
    _log.info(f"\tTotal CAPEX: ${template_values['total_capex_gusd']}B")


def main(project_root: Path | None = None):
    """
    Generate Fervo_Project_Cape-5.md (markdown documentation) from the Jinja template.
    """
    global _current_project_root

    if project_root is None:
        project_root = _get_project_root()

    _current_project_root = project_root

    input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
        from_file_path=_get_fpc5_input_file_path(project_root)
    )
    result = GeophiresXResult(_get_fpc5_result_file_path(project_root))
    generate_fervo_project_cape_5_md(input_params, result, project_root=project_root)


if __name__ == '__main__':
    main()
