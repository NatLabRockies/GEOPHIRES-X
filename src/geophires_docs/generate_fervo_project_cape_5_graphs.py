from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import pyplot as plt
from pint.facets.plain import PlainQuantity

from geophires_docs import _FPC5_INPUT_FILE_PATH
from geophires_docs import _FPC5_RESULT_FILE_PATH
from geophires_docs import _PROJECT_ROOT
from geophires_docs import _get_input_parameters_dict
from geophires_docs import _get_logger
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters

_log = _get_logger(__name__)

_YOE_LABEL = 'Years of Operation'


def _get_full_net_production_profile(input_and_result: tuple[GeophiresInputParameters, GeophiresXResult]):
    return _get_full_profile(input_and_result, 'Net Electricity Production')


def _get_full_total_electricity_generation_profile(input_and_result: tuple[GeophiresInputParameters, GeophiresXResult]):
    return _get_full_profile(input_and_result, 'Total Electricity Production')


def _get_full_production_temperature_profile(input_and_result: tuple[GeophiresInputParameters, GeophiresXResult]):
    return _get_full_profile(input_and_result, 'Produced Temperature')


def _get_full_thermal_drawdown_profile(input_and_result: tuple[GeophiresInputParameters, GeophiresXResult]):
    return _get_full_profile(input_and_result, 'Thermal Drawdown')


def _get_full_profile(input_and_result: tuple[GeophiresInputParameters, GeophiresXResult], profile_key: str):
    input_params: GeophiresInputParameters = input_and_result[0]
    result = GeophiresXClient().get_geophires_result(input_params)

    with open(result.json_output_file_path, encoding='utf-8') as f:
        full_result_obj = json.load(f)

    net_gen_obj = full_result_obj[profile_key]
    net_gen_obj_unit = net_gen_obj['CurrentUnits'].replace('CELSIUS', 'degC')
    profile = [PlainQuantity(it, net_gen_obj_unit) for it in net_gen_obj['value']]
    return profile


def _get_redrilling_event_indexes(
    input_and_result: tuple[GeophiresInputParameters, GeophiresXResult], threshold_degc: float = 0.5
) -> list[float]:
    """
    Detect redrilling events from a production temperature profile.

    A redrilling event is identified when a datapoint's temperature is more than
    `threshold_degc` higher than the previous datapoint (indicating a sudden temperature
    recovery from drilling new wells).

    TODO include redrilling events in GEOPHIRES results so they don't need to be calculated here

    :param threshold_degc: Temperature increase threshold to detect redrilling (default 1.0°C)

    :return: List of fractional year positions where redrilling events occur (COD = Year 1)
    """
    temperatures_celsius: list[float] = [
        it.to('degC').magnitude for it in _get_full_production_temperature_profile(input_and_result)
    ]

    input_params_dict: dict[str, Any] = _get_input_parameters_dict(input_and_result[0])
    time_steps_per_year: int = int(input_params_dict['Time steps per year'])

    redrilling_positions = []

    step_size = 6
    for i in range(ceil(time_steps_per_year * 0.25), len(temperatures_celsius) - (step_size - 1), step_size):
        temp_increase = temperatures_celsius[i] - temperatures_celsius[i - step_size]
        if temp_increase >= threshold_degc:
            # The temperature jump is detected at index i, but the redrilling event
            # occurred somewhere in the step range when the minimum was reached.
            # Find the actual local minimum within the step range.
            search_start = max(0, i - (2 * step_size - 1))
            search_end = i + 1  # exclusive
            local_min_idx = search_start + min(
                range(search_end - search_start), key=lambda offset: temperatures_celsius[search_start + offset]
            )

            # Convert to fractional year position (COD = Year 1)
            year_position = 1 + local_min_idx / time_steps_per_year
            redrilling_positions.append(year_position)

    return redrilling_positions


def generate_power_production_graph(
    # result: GeophiresXResult,
    input_and_result: tuple[GeophiresInputParameters, GeophiresXResult],
    output_dir: Path,
    filename: str = 'fervo_project_cape-5-power-production.png',
) -> str:
    """
    Generate a graph of time vs net power production and save it to the output directory.
    """
    _log.info('Generating power production graph...')

    profile = _get_full_net_production_profile(input_and_result)
    total_generation_profile = _get_full_total_electricity_generation_profile(input_and_result)
    time_steps_per_year = int(_get_input_parameters_dict(input_and_result[0])['Time steps per year'])

    # profile is a list of PlainQuantity values with time_steps_per_year datapoints per year
    # Convert to numpy arrays for plotting
    net_power = np.array([p.magnitude for p in profile])
    total_power = np.array([p.magnitude for p in total_generation_profile])

    # Generate time values: each datapoint represents 1/time_steps_per_year of a year
    # Cash flow year convention: COD = Year 1, so first datapoint is at year 1
    years = np.array([1 + i / time_steps_per_year for i in range(len(profile))])

    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the data
    ax.plot(years, total_power, color='#9933e6', linewidth=2, label='Total Electricity Production (gross generation)')
    ax.plot(years, net_power, color='#3399e6', linewidth=2, label='Net Electricity Production (after parasitic losses)')

    # Set labels and title
    ax.set_xlabel(_YOE_LABEL, fontsize=12)
    ax.set_ylabel('Power Production (MW)', fontsize=12)
    ax.set_title('Power Production Over Project Lifetime', fontsize=14)

    # Set axis limits
    ax.set_xlim(years.min(), years.max())
    ax.set_ylim(480, 630)

    # Add horizontal reference lines
    hline_x = 1.5
    ax.axhline(y=500, color='#e69500', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(hline_x, 498, 'PPA Minimum Production Requirement', ha='left', va='top', fontsize=9, color='#e69500')

    ax.axhline(y=600, color='#33a02c', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(
        hline_x,
        602,
        'Nameplate capacity (combined capacity of individual ORCs)',
        ha='left',
        va='bottom',
        fontsize=9,
        color='#33a02c',
    )

    # Add grid for better readability
    ax.grid(True, linestyle='--', alpha=0.7)

    # Add legend
    ax.legend(loc='best')

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the figure
    save_path = output_dir / filename
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    _log.info(f'✓ Generated {save_path}')
    return filename


def generate_production_temperature_and_drawdown_graph(
    input_and_result: tuple[GeophiresInputParameters, GeophiresXResult],
    output_dir: Path,
    filename: str = 'fervo_project_cape-5-production-temperature.png',
) -> str:
    """
    Generate a graph of time vs production temperature with a horizontal line
    showing the temperature threshold at which maximum drawdown is reached.
    """
    _log.info('Generating production temperature graph...')

    temp_profile = _get_full_production_temperature_profile(input_and_result)
    input_params_dict = _get_input_parameters_dict(input_and_result[0])
    time_steps_per_year = int(input_params_dict['Time steps per year'])

    # Get maximum drawdown from input parameters (as a decimal, e.g., 0.03 for 3%)
    max_drawdown = float(input_params_dict.get('Maximum Drawdown'))

    # Convert to numpy arrays
    temperatures_celsius = np.array([p.magnitude for p in temp_profile])

    # Calculate the temperature at maximum drawdown threshold
    # Drawdown = (T_initial - T_threshold) / T_initial
    # So: T_threshold = T_initial * (1 - max_drawdown)
    initial_temp = temperatures_celsius[0]
    max_drawdown_temp = initial_temp * (1 - max_drawdown)

    # Generate time values: Cash flow year convention: COD = Year 1
    years = np.array([1 + i / time_steps_per_year for i in range(len(temp_profile))])

    # Get redrilling event years
    redrilling_years = _get_redrilling_event_indexes(input_and_result)

    # Colors
    COLOR_TEMPERATURE = '#e63333'
    COLOR_THRESHOLD = '#e69500'
    COLOR_REDRILLING = '#3366cc'

    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.set_xlabel(_YOE_LABEL, fontsize=12)
    ax.set_ylabel('Production Temperature (°C)', fontsize=12)
    ax.set_xlim(years.min(), years.max())
    ax.set_ylim(200, 205)

    # Enable minor ticks on x-axis
    ax.minorticks_on()
    ax.tick_params(axis='x', which='minor', bottom=True)
    ax.tick_params(axis='y', which='minor', left=False)

    # Add vertical lines for redrilling events
    for i, redrill_year in enumerate(redrilling_years):
        ax.axvline(x=redrill_year, color=COLOR_REDRILLING, linestyle=':', linewidth=1.5, alpha=0.7)
        # Only add label for the first redrilling event to avoid legend clutter
        if i == 0:
            ax.text(
                redrill_year + 0.3,
                ax.get_ylim()[0] + 0.75,
                f'Redrilling Events (n={len(redrilling_years)})',
                ha='left',
                va='top',
                fontsize=9,
                color=COLOR_REDRILLING,
            )

    # Add horizontal line for maximum drawdown threshold
    ax.axhline(y=max_drawdown_temp, color=COLOR_THRESHOLD, linestyle='--', linewidth=1.5, alpha=0.8)
    max_drawdown_pct = max_drawdown * 100
    ax.text(
        years.max() * 0.98,
        max_drawdown_temp - 0.25,
        f'Redrilling Threshold ({max_drawdown_pct:.2f}% drawdown = {max_drawdown_temp:.1f}°C)',
        ha='right',
        va='top',
        fontsize=9,
        color=COLOR_THRESHOLD,
    )

    # Plot temperature last so it renders over threshold and redrilling lines
    ax.plot(years, temperatures_celsius, color=COLOR_TEMPERATURE, linewidth=2, label='Production Temperature')

    # Title
    ax.set_title('Production Temperature Over Project Lifetime', fontsize=14)

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)

    # Legend
    ax.legend(loc='best')

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the figure
    save_path = output_dir / filename
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    _log.info(f'✓ Generated {save_path}')
    return filename


def generate_production_temperature_graph(
    result: GeophiresXResult, output_dir: Path, filename: str = 'fervo_project_cape-5-production-temperature.png'
) -> str:
    """
    Generate a graph of time vs production temperature and save it to the output directory.
    """
    _log.info('Generating production temperature graph...')

    # Extract data from power generation profile
    profile = result.power_generation_profile
    headers = profile[0]
    data = profile[1:]

    # Find the indices for YEAR and THERMAL DRAWDOWN columns
    year_idx = headers.index('YEAR')
    # Look for production temperature column - could be labeled differently
    temp_idx = headers.index('GEOFLUID TEMPERATURE (degC)')

    # Extract years and temperature values
    years = np.array([row[year_idx] for row in data])
    temperatures_celsius = np.array([row[temp_idx] for row in data])

    # Convert Celsius to Fahrenheit
    temperatures_fahrenheit = temperatures_celsius * 9 / 5 + 32

    # Create the figure - taller than wide (portrait orientation)
    fig, ax = plt.subplots(figsize=(6, 8))

    # Plot the data - just the curve, no markers
    ax.plot(years, temperatures_fahrenheit, color='#e63333', linewidth=2)

    # Set labels and title
    ax.set_xlabel('Simulation time (Years)', fontsize=12)
    ax.set_ylabel('Wellhead temperature (°F)', fontsize=12)
    # ax.set_title('Production Temperature Over Project Lifetime', fontsize=14)

    # Set axis limits
    ax.set_xlim(years.min(), years.max())
    ax.set_ylim(200, 450)

    # Set y-axis ticks every 50 degrees, with 400 explicitly labeled but not 200 or 450
    ax.set_yticks([250, 300, 350, 400])

    # Add grid for better readability
    ax.grid(True, linestyle='--', alpha=0.7)

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the figure
    save_path = output_dir / filename
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    _log.info(f'✓ Generated {save_path}')
    return filename


def generate_fervo_project_cape_5_graphs(
    base_case: tuple[GeophiresInputParameters, GeophiresXResult],
    singh_et_al_base_simulation: tuple[GeophiresInputParameters, GeophiresXResult],
    output_dir: Path,
) -> None:
    # base_case_input_params: GeophiresInputParameters = base_case[0]
    # base_case_result: GeophiresXResult = base_case[1]

    generate_power_production_graph(base_case, output_dir)
    generate_production_temperature_and_drawdown_graph(base_case, output_dir)

    if singh_et_al_base_simulation is not None:
        singh_et_al_base_simulation_result: GeophiresXResult = singh_et_al_base_simulation[1]

        # generate_net_power_graph(
        #     singh_et_al_base_simulation_result, output_dir,
        #     filename='singh_et_al_base_simulation-net-power-production.png'
        # )

        generate_production_temperature_graph(
            singh_et_al_base_simulation_result,
            output_dir,
            filename='singh_et_al_base_simulation-production-temperature.png',
        )


if __name__ == '__main__':
    docs_dir = _PROJECT_ROOT / 'docs'
    images_dir = docs_dir / '_images'

    input_params_: GeophiresInputParameters = ImmutableGeophiresInputParameters(from_file_path=_FPC5_INPUT_FILE_PATH)

    result_ = GeophiresXResult(_FPC5_RESULT_FILE_PATH)

    generate_fervo_project_cape_5_graphs(
        (input_params_, result_), None, images_dir  # TODO configure (for local development)
    )
