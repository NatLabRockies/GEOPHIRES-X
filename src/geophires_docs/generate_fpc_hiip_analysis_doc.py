import logging
import shutil
from pathlib import Path

from jinja2 import Environment
from jinja2 import FileSystemLoader
from tabulate import tabulate

from geophires_docs import _get_input_parameters_dict
from geophires_docs import _get_logger
from geophires_monte_carlo import GeophiresMonteCarloClient
from geophires_monte_carlo import MonteCarloRequest
from geophires_monte_carlo import MonteCarloResult
from geophires_monte_carlo import SimulationProgram
from hip_ra import HipRaInputParameters
from hip_ra_x import HipRaXClient
from hip_ra_x import HipRaXResult

_log = _get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_DIR = _PROJECT_ROOT / 'build' / 'fpc_hiip_analysis'
_IMAGES_DIR = _PROJECT_ROOT / 'docs' / '_images'


def _get_baseline_input_params_table_md(baseline_input_params):
    params_dict = _get_input_parameters_dict(baseline_input_params, include_parameter_comments=True)

    table = []

    for k, v_c in params_dict.items():
        v = v_c.split(',')[0].strip()
        c = v_c.split(',')[1].replace(' -- ', '').strip()

        # Prevent tabulate from trying to convert boolean strings to float
        if v.lower() in ('true', 'false'):
            v = f' {v}'

        if c == '':
            # c = ' .. N/A'
            continue  # omit commentless params for now

        table.append([k, v, c])

    return tabulate(table, ['Parameter', 'Value', 'Comment'], tablefmt='github', floatfmt='')


def generate_fpc_hiip_analysis_doc():
    _BUILD_DIR.mkdir(parents=True, exist_ok=True)
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    base_input_path = (
        _PROJECT_ROOT / 'tests' / 'hip_ra_x_tests' / 'examples' / 'Fervo_Project_Cape-HIIP-analysis-baseline.txt'
    )

    _log.info('Running deterministic HIP-RA-X baseline...')
    client = HipRaXClient()
    det_input_params: HipRaInputParameters = HipRaInputParameters(file_path_or_params_dict=base_input_path)
    det_result: HipRaXResult = client.get_hip_ra_x_result(det_input_params)

    det_stored_heat_kj = det_result.result['SUMMARY OF RESULTS']['Stored Heat (reservoir)']['value']
    det_elec_mw = det_result.result['SUMMARY OF RESULTS']['Producible Electricity (reservoir)']['value']

    # Convert kJ to 10^15 Joules (10^15 J = 10^12 kJ)
    det_stored_heat_15j = det_stored_heat_kj / 1e12

    # The recoverable case: the same reservoir with HIP-RA-X's recovery factors
    # applied rather than overridden to 1.0, carrying GRMS designations. This is
    # the heat recovery factor assessment D&M state is still required.
    _log.info('Running recoverable-case HIP-RA-X baseline...')
    rec_input_path = (
        _PROJECT_ROOT / 'tests' / 'hip_ra_x_tests' / 'examples' / 'Fervo_Project_Cape-HIIP-analysis-recoverable.txt'
    )
    rec_result: HipRaXResult = client.get_hip_ra_x_result(HipRaInputParameters(file_path_or_params_dict=rec_input_path))
    _rec = rec_result.result['SUMMARY OF RESULTS']
    _grms = rec_result.result['GRMS CLASSIFICATION']

    rec_stored_heat_15j = _rec['Stored Heat (reservoir)']['value'] / 1e12
    rec_available_heat_15j = _rec['Available Heat (reservoir)']['value'] / 1e12
    rec_producible_heat_15j = _rec['Producible Heat (reservoir)']['value'] / 1e12
    rec_recovery_factor = _rec['Recovery Factor (reservoir)']['value']
    rec_elec_mw = _rec['Producible Electricity (reservoir)']['value']

    rec_resource_class = _grms['Resource Class']['value']
    rec_estimate_scenario = _grms['Estimate Scenario']['value']
    rec_cumulative_category = _grms['Cumulative Category']['value']

    # D&M mean Electric Power Capacity, Project Cape Area total, from the filing.
    dm_mean_elec_mw = 14005
    dm_elec_ratio = dm_mean_elec_mw / rec_elec_mw

    # 2. Configure and Run Monte Carlo Simulation
    mc_settings_path = _BUILD_DIR / 'fpc_hiip_mc_settings.txt'
    mc_output_path = _BUILD_DIR / 'fpc_hiip_mc_results.txt'

    with open(mc_settings_path, 'w') as f:
        # The SEC HIIP methodology explicitly models productive volume (Area * Thickness),
        # density, specific heat (Rock Heat Capacity), and temperature using normal distributions.
        # 228 C is the volume-weighted mean of the temperatures implied by D&M's
        # per-interval HIIP and capacity per unit rock volume, not the 170-250 C
        # range midpoint of 210 C. See the Estimation of Heat Initially in Place
        # section of the analysis document for the reconstruction.
        f.write('INPUT, Reservoir Temperature, normal, 228.0, 15.0\n')
        f.write('INPUT, Reservoir Area, normal, 48.0, 2.4\n')
        f.write('INPUT, Reservoir Thickness, normal, 4.0, 0.2\n')
        f.write('INPUT, Rock Heat Capacity, normal, 2.212e12, 1.1e11\n')
        f.write('INPUT, Density Of Reservoir Rock, normal, 2.8e12, 0.1e12\n')

        f.write('OUTPUT, Stored Heat (reservoir)\n')
        f.write('OUTPUT, Producible Electricity (reservoir)\n')
        f.write('ITERATIONS, 1000\n')
        f.write(f'MC_OUTPUT_FILE, {mc_output_path.absolute()}\n')

    _log.info('Running Monte Carlo HIP-RA-X simulation...')

    # Initialize the Monte Carlo Request
    mc_request = MonteCarloRequest(
        simulation_program=SimulationProgram.HIP_RA_X,
        input_file=base_input_path.absolute(),
        monte_carlo_settings_file=mc_settings_path.absolute(),
        output_file=mc_output_path.absolute(),
    )

    # Execute the client
    mc_client = GeophiresMonteCarloClient()
    mc_result: MonteCarloResult = mc_client.get_monte_carlo_result(mc_request)

    # 3. Read MC JSON Results directly from the result object
    mc_stats: dict = mc_result.result['output']

    mc_stored_heat_mean_kj = mc_stats['Stored Heat (reservoir)']['mean']
    mc_stored_heat_mean_15j = mc_stored_heat_mean_kj / 1e12

    mc_elec_mean_mw = mc_stats['Producible Electricity (reservoir)']['mean']

    # Copy generated MC histogram images to the docs directory
    mc_images = ['Stored Heat (reservoir).png', 'Producible Electricity (reservoir).png']

    for img_name in mc_images:
        src = _BUILD_DIR / img_name
        dst = _IMAGES_DIR / f'fpc_hiip_mc_{img_name.replace(" ", "_").replace("(", "").replace(")", "")}'
        if src.exists():
            shutil.copy(src, dst)
            _log.info(f'Copied {src.name} to docs/_images/')

    # 4. Render Jinja Template
    _log.info('Rendering Markdown documentation...')
    docs_dir = _PROJECT_ROOT / 'docs'

    baseline_input_params_table_md = _get_baseline_input_params_table_md(det_input_params)

    template_values = {
        'baseline_input_params_table_md': baseline_input_params_table_md,
        'det_stored_heat_15j': f'{det_stored_heat_15j:,.0f}',
        'det_elec_mw': f'{det_elec_mw:,.0f}',
        'mc_stored_heat_mean_15j': f'{mc_stored_heat_mean_15j:,.0f}',
        'mc_elec_mean_mw': f'{mc_elec_mean_mw:,.0f}',
        'rec_stored_heat_15j': f'{rec_stored_heat_15j:,.0f}',
        'rec_available_heat_15j': f'{rec_available_heat_15j:,.0f}',
        'rec_producible_heat_15j': f'{rec_producible_heat_15j:,.0f}',
        'rec_recovery_factor': f'{rec_recovery_factor:,.2f}',
        'rec_elec_mw': f'{rec_elec_mw:,.0f}',
        'rec_resource_class': rec_resource_class,
        'rec_estimate_scenario': rec_estimate_scenario,
        'rec_cumulative_category': rec_cumulative_category,
        'dm_elec_ratio': f'{dm_elec_ratio:,.1f}',
    }

    env = Environment(loader=FileSystemLoader(docs_dir), autoescape=True)
    template = env.get_template('Fervo_Project_Cape_HIIP_Analysis.md.jinja')
    output = template.render(**template_values)

    output_file = docs_dir / 'Fervo_Project_Cape_HIIP_Analysis.md'
    output_file.write_text(output, encoding='utf-8')
    _log.info(f'✓ Generated {output_file}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    generate_fpc_hiip_analysis_doc()
