from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Environment
from jinja2 import FileSystemLoader
from pint.facets.plain import PlainQuantity
from scipy.interpolate import interp1d
from scipy.ndimage import maximum_filter

from geophires_docs import _NON_BREAKING_SPACE
from geophires_docs import _PROJECT_ROOT
from geophires_docs import _get_full_production_temperature_profile
from geophires_docs import _get_input_parameters_comments_dict
from geophires_docs import _get_input_parameters_dict
from geophires_docs import _get_logger
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters

_log = _get_logger(__name__)

_BUILD_DIR: Path = _PROJECT_ROOT / 'build' / 'generate_fervo_project_red_2026_docs'

_PRODUCTION_CSV_FILENAME = 'project_red_2026_production_data.csv'
_MODEL_CSV_FILENAME = 'project_red_2026_model_data.csv'
_VARIANCE_ANALYSIS_CSV_FILENAME = 'project_red_2026_variance_analysis.csv'
_GENERATED_GRAPH_FILENAME_STEM = 'fervo_project_red-2026_production-temperature-data-vs-modeling'

_STEADY_STATE_START_YEARS = 0.041625

_HOUGH_MIN_DIST_PX = 4

_MODEL_OUTLIER_STD_THRESHOLD = 2.5
_MODEL_ROLLING_WINDOW = 15

_CONTINUOUS_OPERATION_MIN_TEMP_C = 175.0
_STATISTICAL_BUFFER_SIZE = 5
_STATISTICAL_MIN_BUFFER = 3
_STATISTICAL_Z_SCORE = 2.0
_STATISTICAL_MIN_STD = 1.5

_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS = 8

NUMBER_OF_FRACTURES_PARAM_NAME = 'Number of Fractures'

_GRAPH_DPI = 300
_SAVEFIG_ARGS = {
    'dpi': _GRAPH_DPI,
    'metadata': {
        # Prevent spurious image diffs after graph/doc regeneration: Matplotlib writes its version to PNG metadata
        # (Software), so otherwise pixel-identical images differ whenever the Matplotlib version changes.
        'Date': None,
        'Software': None,
    },
}


@dataclass
class _StatsAlignmentResult:
    rmse_degc: float
    bias_degc: float
    r2: float

    @property
    def as_caption(self) -> str:
        return f'RMSE={self.rmse_degc:.2f}°C, R²={self.r2:.4f}, Bias={self.bias_degc:.2f}°C'


def extract_plot_data(
    image_path: Path | str, production_image_path: Path | str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f'Could not load image at {image_path}')

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    height, width, _ = img.shape
    x_min_px, x_max_px = int(width * 0.10), int(width * 0.96)
    y_min_px, y_max_px = int(height * 0.06), int(height * 0.80)

    x_min_val, x_max_val = 0.0, 2.0
    y_min_val, y_max_val = 0.0, 200.0

    def pixel_to_data(px: float, py: float) -> tuple[float, float]:
        x = x_min_val + (px - x_min_px) / (x_max_px - x_min_px) * (x_max_val - x_min_val)
        y = y_min_val + (y_max_px - py) / (y_max_px - y_min_px) * (y_max_val - y_min_val)
        return x, y

    plot_mask = np.zeros((height, width), dtype=np.uint8)
    plot_mask[y_min_px:y_max_px, x_min_px:x_max_px] = 255

    prod_target_path = production_image_path if production_image_path else image_path
    df_prod = _extract_red_circles(prod_target_path, plot_mask, pixel_to_data)
    df_model = _extract_black_dashed_line(hsv, plot_mask, pixel_to_data)

    return df_prod, df_model


def _calculate_variance_analysis(
    df_actual: pd.DataFrame, df_model: pd.DataFrame, steady_state_start_years: float = _STEADY_STATE_START_YEARS
) -> pd.DataFrame:
    post_ramp_mask = df_actual['Time_Years'] > steady_state_start_years
    n_before = len(df_actual[post_ramp_mask])

    is_steady = _get_steady_state_mask(df_actual, steady_state_start_years)
    df_steady_state = df_actual[is_steady].copy()

    _log.info(f'Continuous operation filter: dropped {n_before - len(df_steady_state)} transient/dip points.')

    model_interpolator = interp1d(
        df_model['Time_Years'],
        df_model['Temperature_C'],
        kind='linear',
        fill_value='extrapolate',
    )

    df_steady_state['Model_Temperature_C'] = model_interpolator(df_steady_state['Time_Years'])
    df_steady_state['Error_C'] = df_steady_state['Temperature_C'] - df_steady_state['Model_Temperature_C']

    return df_steady_state.reset_index(drop=True)


def _extract_red_circles(
    img_path: Path | str,
    plot_mask: np.ndarray,
    pixel_to_data,
) -> pd.DataFrame:
    img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f'Could not load image at {img_path}')

    if len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        _, mask_alpha = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        hsv = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV)
    else:
        mask_alpha = np.ones(img.shape[:2], dtype=np.uint8) * 255
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 20, 20])
    upper_red1 = np.array([20, 255, 255])
    lower_red2 = np.array([160, 20, 20])
    upper_red2 = np.array([180, 255, 255])

    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_red = cv2.bitwise_and(mask_red, mask_alpha)
    mask_red = cv2.bitwise_and(mask_red, plot_mask)

    dist_transform = cv2.distanceTransform(mask_red, cv2.DIST_L2, 5)

    local_max = maximum_filter(dist_transform, size=3) == dist_transform
    peak_mask = local_max & (dist_transform > 1.0)

    y_coords, x_coords = np.where(peak_mask)
    centers_px = [(int(x), int(y)) for x, y in zip(x_coords, y_coords)]

    if not centers_px:
        _log.warning('No valid pixels found in the production data mask.')
        return pd.DataFrame(columns=['Time_Years', 'Temperature_C'])

    deduped_centers_px = _dedupe_centers(centers_px, min_dist_px=_HOUGH_MIN_DIST_PX)

    _log.info(f'Red-marker detection: Extracted {len(deduped_centers_px)} topological ridge points from edited mask.')

    production_data = [pixel_to_data(cx, cy) for cx, cy in deduped_centers_px]
    df_prod = pd.DataFrame(production_data, columns=['Time_Years', 'Temperature_C'])
    return df_prod.sort_values('Time_Years').reset_index(drop=True)


def _extract_black_dashed_line(hsv: np.ndarray, plot_mask: np.ndarray, pixel_to_data) -> pd.DataFrame:
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    mask_black = cv2.inRange(hsv, lower_black, upper_black)
    mask_black = cv2.bitwise_and(mask_black, plot_mask)

    y_coords, x_coords = np.where(mask_black > 0)
    model_data = [pixel_to_data(px, py) for px, py in zip(x_coords, y_coords)]

    df_model_raw = pd.DataFrame(model_data, columns=['Time_Years', 'Temperature_C'])
    if df_model_raw.empty:
        return df_model_raw

    df_model_raw['Time_Years_Rounded'] = df_model_raw['Time_Years'].round(3)
    df_model = (
        df_model_raw.groupby('Time_Years_Rounded', as_index=False)['Temperature_C']
        .mean()
        .rename(columns={'Time_Years_Rounded': 'Time_Years'})
        .sort_values('Time_Years')
        .reset_index(drop=True)
    )

    rolling_median = (
        df_model['Temperature_C'].rolling(window=_MODEL_ROLLING_WINDOW, center=True, min_periods=3).median()
    )
    rolling_std = df_model['Temperature_C'].rolling(window=_MODEL_ROLLING_WINDOW, center=True, min_periods=3).std()
    rolling_std = rolling_std.fillna(rolling_std.median()).replace(0, rolling_std.median())

    deviations = (df_model['Temperature_C'] - rolling_median).abs()
    inlier_mask = deviations <= _MODEL_OUTLIER_STD_THRESHOLD * rolling_std
    inlier_mask = inlier_mask.fillna(True)

    n_before = len(df_model)
    df_model = df_model[inlier_mask].reset_index(drop=True)
    _log.info(f'Model-curve outlier rejection: {n_before - len(df_model)} of {n_before} points dropped')

    return df_model


def _dedupe_centers(centers_px: list[tuple[int, int]], min_dist_px: float) -> list[tuple[int, int]]:
    if not centers_px:
        return []

    accepted: list[tuple[int, int]] = []
    min_dist_sq = min_dist_px * min_dist_px
    for cx, cy in centers_px:
        duplicate = False
        for ax, ay in accepted:
            if (cx - ax) * (cx - ax) + (cy - ay) * (cy - ay) < min_dist_sq:
                duplicate = True
                break
        if not duplicate:
            accepted.append((cx, cy))
    return accepted


def _get_steady_state_mask(df_prod: pd.DataFrame, steady_state_start_years: float) -> pd.Series:
    """
    Identifies steady-state production points iteratively. Maintains a rolling
    buffer of verified plateau points to mathematically isolate and reject
    the steep walls and floors of transient shut-ins.
    """
    is_steady = pd.Series(False, index=df_prod.index)
    post_ramp_idx = df_prod.index[df_prod['Time_Years'] > steady_state_start_years]

    valid_buffer: list[float] = []

    for idx in post_ramp_idx:
        temp = df_prod.at[idx, 'Temperature_C']

        if temp < _CONTINUOUS_OPERATION_MIN_TEMP_C:
            continue

        if len(valid_buffer) >= _STATISTICAL_MIN_BUFFER:
            history = valid_buffer[-_STATISTICAL_BUFFER_SIZE:]
            mean_temp = float(np.mean(history))
            std_temp = float(np.std(history, ddof=1))

            std_temp = max(std_temp, _STATISTICAL_MIN_STD)

            if abs(temp - mean_temp) > _STATISTICAL_Z_SCORE * std_temp:
                continue

        is_steady.at[idx] = True
        valid_buffer.append(temp)

    return is_steady


def _generate_production_temperature_comparison_graph(
    production_csv_path: Path,
    model_csv_path: Path,
    output_path_stem: Path,
    steady_state_start_years: float = _STEADY_STATE_START_YEARS,
    geophires_data: pd.Series | None = None,
    fervo_modeled_stats_caption: str = '',
    geophires_modeled_stats_caption: str = '',
) -> None:
    df_prod = pd.read_csv(production_csv_path)
    df_model = pd.read_csv(model_csv_path)

    is_thermal_conditioning = df_prod['Time_Years'] <= steady_state_start_years  # noqa: F841
    is_steady_state = _get_steady_state_mask(df_prod, steady_state_start_years)

    df_included = df_prod[
        # is_thermal_conditioning |
        is_steady_state
    ]
    df_excluded = df_prod[
        ~(
            # is_thermal_conditioning |
            is_steady_state
        )
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(
        df_included['Time_Years'],
        df_included['Temperature_C'],
        facecolors='none',
        edgecolors='#d62728',
        s=22,
        linewidths=1.0,
        alpha=0.85,
        label='Measured '
        # f'Flowing '
        'Temperature (Steady State)',
        # f', n={len(df_included)}',
    )

    if not df_excluded.empty:
        ax.scatter(
            df_excluded['Time_Years'],
            df_excluded['Temperature_C'],
            facecolors='none',
            edgecolors='gray',
            s=22,
            linewidths=1.0,
            alpha=0.5,
            label='Measured '
            # f'Flowing '
            'Temperature (Thermal Conditioning ' '& Transient Operations' ')',
            # f', n={len(df_excluded)}',
        )

    ax.plot(
        df_model['Time_Years'],
        df_model['Temperature_C'],
        color='black',
        linestyle='--',
        linewidth=1.5,
        label=f'\nFervo-Modeled Temperature{fervo_modeled_stats_caption}',
    )

    if geophires_data is not None:
        ax.plot(
            geophires_data.index,
            geophires_data.values,
            # color='#1f77b4',
            color='green',
            linestyle='-.',
            # linestyle=(
            #     0,
            #     (1, 3),
            # ),  # loosely dotted - https://matplotlib.org/stable/gallery/lines_bars_and_markers/linestyles.html
            # linewidth=7,
            label=f'GEOPHIRES-Modeled Temperature (Gringarten){geophires_modeled_stats_caption}',
        )

    ax.set_xlabel('Time (Years)', fontsize=12)
    ax.set_ylabel('Flowing Temperature (°C)', fontsize=12)

    title = 'Fervo Project Red: Measured vs. Modeled Flowing Temperature (Regenerated)'
    if geophires_data is not None:
        title = 'Project Red Temperature: Measured vs. Fervo-Modeled vs. GEOPHIRES'
    ax.set_title(title, fontsize=13)

    ax.set_xlim(0.0, 1.75)

    ax.grid(True, linestyle='--', alpha=0.5)

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=1, frameon=False, fontsize=11)

    output_path_stem.parent.mkdir(parents=True, exist_ok=True)

    ax.set_ylim(0.0, 200.0)
    fig.savefig(f'{output_path_stem}-1.png', bbox_inches='tight', **_SAVEFIG_ARGS)

    ax.set_ylim(
        175,
        185,
    )
    fig.savefig(f'{output_path_stem}-2.png', bbox_inches='tight', **_SAVEFIG_ARGS)

    plt.close(fig)


def _generate_long_term_forecast_graph(
    df_prod: pd.DataFrame,
    df_model: pd.DataFrame,
    geophires_data: pd.Series,
    steady_state_start_years: float,
    output_path: Path,
) -> None:
    is_steady_state = _get_steady_state_mask(df_prod, steady_state_start_years)

    df_included = df_prod[is_steady_state]
    df_excluded = df_prod[~is_steady_state]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(
        df_included['Time_Years'],
        df_included['Temperature_C'],
        facecolors='none',
        edgecolors='#d62728',
        s=22,
        linewidths=1.0,
        alpha=0.85,
        label='Measured Temperature (Steady State)',
    )

    if not df_excluded.empty:
        ax.scatter(
            df_excluded['Time_Years'],
            df_excluded['Temperature_C'],
            facecolors='none',
            edgecolors='gray',
            s=22,
            linewidths=1.0,
            alpha=0.5,
            label='Measured Temperature (Thermal Conditioning & Transient Operations)',
        )

    ax.plot(
        df_model['Time_Years'],
        df_model['Temperature_C'],
        color='black',
        linestyle='--',
        linewidth=1.5,
        label='Fervo-Modeled Temperature',
    )

    ax.plot(
        geophires_data.index,
        geophires_data.values,
        color='green',
        linestyle='-.',
        label='GEOPHIRES-Modeled Temperature (Gringarten)',
    )

    ax.set_xlabel('Time (Years)', fontsize=12)
    ax.set_ylabel('Flowing Temperature (°C)', fontsize=12)

    ax.set_title(
        f'Project Red GEOPHIRES Temperature Forecast: {_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS}-Year Horizon',
        fontsize=13,
    )

    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(0.0, 200.0)
    ax.grid(True, linestyle='--', alpha=0.5)

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=1, frameon=False, fontsize=11)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches='tight', **_SAVEFIG_ARGS)
    plt.close(fig)


def _get_file_path(file_name: str) -> Path:
    return Path(__file__).parent / file_name


def get_project_red_input_params_and_result() -> tuple[GeophiresInputParameters, GeophiresXResult]:
    input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
        from_file_path=_get_file_path('../../tests/examples/Fervo_Project_Red-2026.txt'),
        params={'Print Output to Console': 0},
    )
    input_and_result = (
        input_params,
        GeophiresXResult(_get_file_path('../../tests/examples/Fervo_Project_Red-2026.out')),
    )

    return input_and_result


def get_project_red_production_temperature_profile_series(
    fervo_graph_df_model: pd.Series,
) -> tuple[
    pd.Series,
    Any,  # interpolator
]:
    input_and_result = get_project_red_input_params_and_result()
    input_params: GeophiresInputParameters = input_and_result[0]

    project_red_geophires_result_data: list = _get_full_production_temperature_profile(input_and_result)

    time_steps_per_year: int = int(_get_input_parameters_dict(input_params)['Time steps per year'])
    geophires_time_data = [
        float(step) / float(time_steps_per_year) for step, _ in enumerate(project_red_geophires_result_data)
    ]

    geophires_x = geophires_time_data
    geophires_y = [q.magnitude for q in project_red_geophires_result_data]

    # Interpolate the GEOPHIRES curve along the exact timestamps established by the model dashed line extraction
    geophires_interpolator = interp1d(geophires_x, geophires_y, kind='linear', fill_value='extrapolate')
    geophires_interpolated_y = geophires_interpolator(fervo_graph_df_model['Time_Years'])

    geophires_series = pd.Series(data=geophires_interpolated_y, index=fervo_graph_df_model['Time_Years'])

    return geophires_series, geophires_interpolator


def get_long_term_geophires_profile() -> pd.Series:
    long_term_input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
        from_file_path=_get_file_path('../../tests/examples/Fervo_Project_Red-2026.txt'),
        params={'Plant Lifetime': _LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS, 'Print Output to Console': 0},
    )
    long_term_result: GeophiresXResult = GeophiresXClient().get_geophires_result(long_term_input_params)

    long_term_profile = _get_full_production_temperature_profile((long_term_input_params, long_term_result))

    time_steps_per_year: int = int(_get_input_parameters_dict(long_term_input_params)['Time steps per year'])
    geophires_x = [float(step) / float(time_steps_per_year) for step, _ in enumerate(long_term_profile)]
    geophires_y = [q.magnitude for q in long_term_profile]

    return pd.Series(data=geophires_y, index=geophires_x)


def _get_fracture_sensitivity_fracture_counts() -> list[int]:
    base_input_params: GeophiresInputParameters = get_project_red_input_params_and_result()[0]
    base_number_of_fractures = int(_get_input_parameters_dict(base_input_params)[NUMBER_OF_FRACTURES_PARAM_NAME])
    return [
        base_number_of_fractures,
        base_number_of_fractures - 6,
        base_number_of_fractures - 3,
        base_number_of_fractures + 3,
        base_number_of_fractures + 6,
    ]


def _generate_fracture_sensitivity_graph(
    df_prod: pd.DataFrame,
    steady_state_start_years: float,
    sensitivity_graph_path: Path,
    power_graph_path: Path,
    power_csv_path: Path,
    df_variance: pd.DataFrame | None = None,
    show_excluded_measured_temperatures: bool = False,
    calculate_stats: bool = True,
) -> pd.DataFrame:
    _log.info(
        f'Running {_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS}-year fracture sensitivity analysis (including power generation)...'
    )

    # noinspection DuplicatedCode
    is_steady_state = _get_steady_state_mask(df_prod, steady_state_start_years)

    df_included = df_prod[is_steady_state]
    df_excluded = df_prod[~is_steady_state]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(
        df_included['Time_Years'],
        df_included['Temperature_C'],
        facecolors='none',
        edgecolors='#d62728',
        s=22,
        linewidths=1.0,
        alpha=0.85,
        label='Measured Temperature (Steady State)',
    )

    if not df_excluded.empty and show_excluded_measured_temperatures:
        ax.scatter(
            df_excluded['Time_Years'],
            df_excluded['Temperature_C'],
            facecolors='none',
            edgecolors='gray',
            s=22,
            linewidths=1.0,
            alpha=0.5,
            label='Measured Temperature (Thermal Conditioning & Transient Operations)',
        )

    base_input_params: GeophiresInputParameters = get_project_red_input_params_and_result()[0]
    base_number_of_fractures = int(_get_input_parameters_dict(base_input_params)[NUMBER_OF_FRACTURES_PARAM_NAME])

    fracture_counts = _get_fracture_sensitivity_fracture_counts()
    client = GeophiresXClient()

    colors = {
        base_number_of_fractures: 'green',
        fracture_counts[1]: '#1C6CA4',
        fracture_counts[2]: '#1f77b4',
        fracture_counts[3]: '#ff7f0e',
        fracture_counts[4]: '#9467bd',
    }
    line_styles = {
        base_number_of_fractures: '-.',
    }

    if calculate_stats:
        _log.info(
            f'--- FRACTURE SENSITIVITY STATISTICAL ALIGNMENT (Steady-State > {steady_state_start_years} Years) ---'
        )
        y_true = df_included['Temperature_C'].values
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))

    power_data = []

    for frac_count in fracture_counts:
        input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
            from_file_path=base_input_params.as_file_path(),
            params={
                NUMBER_OF_FRACTURES_PARAM_NAME: frac_count,
                'Plant Lifetime': _LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS,
                'Gringarten-Stehfest Precision': 10,  # Speed up build with only minor effect on precision
                'Print Output to Console': 0,
            },
        )
        result: GeophiresXResult = client.get_geophires_result(input_params)

        avg_generation_param: str = 'Average Annual Net Electricity Generation'
        avg_generation_vu: dict[str, Any] = result.result['SURFACE EQUIPMENT SIMULATION RESULTS'][avg_generation_param]
        avg_generation_u = 'GWh'
        avg_generation_v: float = (
            PlainQuantity(avg_generation_vu['value'], avg_generation_vu['unit']).to(avg_generation_u).magnitude
        )

        # noinspection DuplicatedCode
        profile = _get_full_production_temperature_profile((input_params, result))
        time_steps_per_year: int = int(_get_input_parameters_dict(input_params)['Time steps per year'])

        geophires_x = [float(step) / float(time_steps_per_year) for step, _ in enumerate(profile)]
        geophires_y = [q.magnitude for q in profile]

        final_temp_degc = float(geophires_y[-1]) if geophires_y else 0.0
        power_data.append(
            {
                NUMBER_OF_FRACTURES_PARAM_NAME: frac_count,
                f'{avg_generation_param} ({avg_generation_u})': avg_generation_v,
                f'Year {_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS} Flowing Temperature (°C)': final_temp_degc,
            }
        )

        label_prefix = 'GEOPHIRES: ' if frac_count == base_number_of_fractures else ''
        label_suffix = ' (Baseline)' if frac_count == base_number_of_fractures else ''

        if calculate_stats and not df_included.empty:
            geo_interp = interp1d(geophires_x, geophires_y, kind='linear', fill_value='extrapolate')
            y_geo = geo_interp(df_included['Time_Years'])

            if df_variance is not None:
                df_variance[f'GEOPHIRES_Modeled_Temperature_C_{frac_count}_Fractures'] = geo_interp(
                    df_variance['Time_Years']
                )

            ss_res_g = float(np.sum((y_true - y_geo) ** 2))

            calculated_stats = _StatsAlignmentResult(
                rmse_degc=float(np.sqrt(((y_true - y_geo) ** 2).mean())),
                bias_degc=float((y_geo - y_true).mean()),
                r2=1.0 - (ss_res_g / ss_tot) if ss_tot != 0.0 else 0.0,
            )
            if df_variance is not None:
                df_variance.loc[0, f'GEOPHIRES_R2_{frac_count}_Fractures'] = calculated_stats.r2

            _log.info(f'{frac_count} Fractures: {calculated_stats.as_caption}')

            label_suffix += f' (R²={calculated_stats.r2:.4f})'

        ax.plot(
            geophires_x,
            geophires_y,
            color=colors[frac_count],
            linestyle=line_styles.get(frac_count, ':'),
            linewidth=1.5 if frac_count != base_number_of_fractures else 2.0,
            label=f'{label_prefix}{frac_count} Fractures{label_suffix}',
        )

    ax.set_xlabel('Time (Years)', fontsize=12)
    ax.set_ylabel('Flowing Temperature (°C)', fontsize=12)
    ax.set_title('Project Red GEOPHIRES Temperature Forecast: Effective Number of Fractures Sensitivity', fontsize=13)

    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False, fontsize=11)

    sensitivity_graph_path.parent.mkdir(parents=True, exist_ok=True)

    def _savefig(version: int | str) -> None:
        fig.savefig(
            sensitivity_graph_path.with_name(f'{sensitivity_graph_path.stem}-{version}').with_suffix(
                sensitivity_graph_path.suffix
            ),
            bbox_inches='tight',
            **_SAVEFIG_ARGS,
        )

    ax.set_xlim(0.0, _LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS)
    ax.set_ylim(0, 200)
    _savefig(1)

    ax.set_xlim(0.0, _LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS * 0.375)
    ax.set_ylim(160, 190)
    _savefig(2)

    plt.close(fig)

    df_power = pd.DataFrame(power_data)
    df_power = df_power.sort_values(NUMBER_OF_FRACTURES_PARAM_NAME).reset_index(drop=True)
    df_power.to_csv(power_csv_path, index=False)

    fig_pwr, ax_pwr = plt.subplots(figsize=(8, 5))
    x_labels = [str(x) for x in df_power[NUMBER_OF_FRACTURES_PARAM_NAME]]
    y_values = df_power[f'{avg_generation_param} ({avg_generation_u})']

    bars = ax_pwr.bar(x_labels, y_values, color='#1f77b4', alpha=0.8, edgecolor='black')

    baseline_idx = df_power.index[df_power[NUMBER_OF_FRACTURES_PARAM_NAME] == base_number_of_fractures].tolist()[0]
    bars[baseline_idx].set_color('green')
    bars[baseline_idx].set_edgecolor('black')

    ax_pwr.set_xlabel('Effective Number of Fractures', fontsize=12)
    ax_pwr.set_ylabel(f'{avg_generation_param} ({avg_generation_u})', fontsize=12)
    ax_pwr.set_title(
        f'GEOPHIRES: {_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS}-Year Average Power Production by Fracture Count',
        fontsize=13,
    )

    y_max = y_values.max()
    y_min = y_values.min()
    y_padding = (y_max - y_min) * 0.4
    if y_padding == 0:
        y_padding = max(y_max * 0.1, 1.0)
    ax_pwr.set_ylim(max(0.0, y_min - y_padding), y_max + y_padding)

    for bar in bars:
        height = bar.get_height()
        ax_pwr.annotate(
            f'{height:.2f} {avg_generation_u}',
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords='offset points',
            ha='center',
            va='bottom',
            fontsize=11,
        )

    ax_pwr.grid(True, axis='y', linestyle='--', alpha=0.5)

    baseline_patch = mpatches.Patch(color='green', label='Baseline Model')
    sensitivity_patch = mpatches.Patch(color='#1f77b4', alpha=0.8, label='Sensitivity Cases')
    ax_pwr.legend(handles=[baseline_patch, sensitivity_patch], loc='upper left', frameon=False)

    power_graph_path.parent.mkdir(parents=True, exist_ok=True)
    fig_pwr.savefig(power_graph_path, bbox_inches='tight', **_SAVEFIG_ARGS)
    plt.close(fig_pwr)

    return df_power


def generate_fervo_project_red_2026_md(
    input_params: GeophiresInputParameters,
    result: GeophiresXResult,
    fervo_stats_alignment: _StatsAlignmentResult,
    geophires_stats_alignment: _StatsAlignmentResult,
    project_root: Path = _PROJECT_ROOT,
) -> None:
    result_values: dict[str, Any] = {}  # get_result_values(result)

    def _get_input_params_dict_with_nbsp() -> dict[str, Any]:
        input_params_dict: dict[str, Any] = _get_input_parameters_dict(input_params)

        for k, v in input_params_dict.items():
            if isinstance(v, str):
                input_params_dict[k] = v.replace(' ', _NON_BREAKING_SPACE)

        return input_params_dict

    docs_dir = project_root / 'docs'
    template_file = docs_dir / 'Fervo_Project_Red.md.jinja'
    template_mtime = datetime.fromtimestamp(template_file.stat().st_mtime).strftime('%Y-%m-%d')  # noqa: DTZ006
    sim_date = result.result['Simulation Metadata']['Simulation Date']['value']
    last_updated_date = max(sim_date, template_mtime)

    # noinspection PyDictCreation
    template_values = {
        'input_params': _get_input_params_dict_with_nbsp(),
        'input_params_comments': _get_input_parameters_comments_dict(input_params),
        **result_values,
        'nbsp': _NON_BREAKING_SPACE,
        'last_updated_date': last_updated_date,
        'fervo_rmse_degc': f'{fervo_stats_alignment.rmse_degc:.2f}',
        'fervo_r2': f'{fervo_stats_alignment.r2:.4f}',
        'fervo_bias_degc': f'{fervo_stats_alignment.bias_degc:.2f}',
        'geophires_rmse_degc': f'{geophires_stats_alignment.rmse_degc:.2f}',
        'geophires_r2': f'{geophires_stats_alignment.r2:.4f}',
        'geophires_bias_degc': f'{geophires_stats_alignment.bias_degc:.2f}',
        'long_term_forecast_years': _LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS,
        'fracture_sensitivity_range_low': min(_get_fracture_sensitivity_fracture_counts()),
        'fracture_sensitivity_range_high': max(_get_fracture_sensitivity_fracture_counts()),
    }

    # Set up Jinja environment
    env = Environment(loader=FileSystemLoader(docs_dir), autoescape=True)
    template = env.get_template('Fervo_Project_Red.md.jinja')

    # Render template
    _log.info('Rendering template...')
    output = template.render(**template_values)

    # Write output
    output_file = docs_dir / 'Fervo_Project_Red.md'
    output_file.write_text(output, encoding='utf-8')

    _log.info(f'✓ Generated {output_file}')


def generate_fervo_project_red_2026_docs():
    IMAGE_PATH = _get_file_path('../../docs/_images/fervo-project-red-2026_figure-5_measured-flowing-temperature.png')
    PRODUCTION_IMAGE_PATH = _get_file_path(
        '../../docs/_images/fervo_project_red-2026_graph-data-extraction_production-series-edited.png'
    )

    _BUILD_DIR.mkdir(parents=True, exist_ok=True)
    production_csv_path_ = _BUILD_DIR / _PRODUCTION_CSV_FILENAME
    model_csv_path_ = _BUILD_DIR / _MODEL_CSV_FILENAME
    variance_analysis_csv_path = _BUILD_DIR / _VARIANCE_ANALYSIS_CSV_FILENAME
    generated_graph_path_stem = _get_file_path(f'../../docs/_images/{_GENERATED_GRAPH_FILENAME_STEM}')

    _log.info('Extracting data from image...')
    df_actual, df_model_ = extract_plot_data(IMAGE_PATH, PRODUCTION_IMAGE_PATH)

    _log.info(f'Extracted {len(df_actual)} production data points.')
    _log.info(f'Extracted {len(df_model_)} model line data points.')

    df_actual.to_csv(production_csv_path_, index=False)
    df_model_.to_csv(model_csv_path_, index=False)
    _log.info(f'Wrote production data CSV: {production_csv_path_}')
    _log.info(f'Wrote model data CSV:      {model_csv_path_}')

    df_steady_state = _calculate_variance_analysis(df_actual, df_model_)

    # Like-for-like comparison metrics
    y_true = df_steady_state['Temperature_C'].values
    y_fervo = df_steady_state['Model_Temperature_C'].values

    # Calculate R^2 and Bias for Fervo
    rmse_f = float(np.sqrt((df_steady_state['Error_C'] ** 2).mean()))
    bias_f = float((y_fervo - y_true).mean())
    ss_res_f = np.sum((y_true - y_fervo) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2_f = 1 - (ss_res_f / ss_tot) if ss_tot != 0 else 0.0
    fervo_stat_result = _StatsAlignmentResult(rmse_degc=rmse_f, bias_degc=bias_f, r2=r2_f)

    # Calculate metrics for GEOPHIRES (interpolated at the exact same steady-state timestamps)
    geophires_series, geo_interp = get_project_red_production_temperature_profile_series(df_model_)
    # geo_interp = interp1d(geophires_series.index, geophires_series.values, kind='linear', fill_value='extrapolate')
    y_geo = geo_interp(df_steady_state['Time_Years'])

    rmse_g = float(np.sqrt(((y_true - y_geo) ** 2).mean()))
    bias_g = float((y_geo - y_true).mean())
    ss_res_g = np.sum((y_true - y_geo) ** 2)
    r2_g = 1 - (ss_res_g / ss_tot) if ss_tot != 0 else 0.0

    geophires_stat_result = _StatsAlignmentResult(rmse_degc=rmse_g, bias_degc=bias_g, r2=r2_g)

    _log.info(f'--- STATISTICAL ALIGNMENT (Steady-State > {_STEADY_STATE_START_YEARS} Years) ---')
    fervo_modeled_stats_caption = fervo_stat_result.as_caption
    geophires_modeled_stats_caption = geophires_stat_result.as_caption
    _log.info(f'FERVO:      {fervo_modeled_stats_caption}')
    _log.info(f'GEOPHIRES:  {geophires_modeled_stats_caption}')

    is_thermal_conditioning = df_actual['Time_Years'] <= _STEADY_STATE_START_YEARS
    is_steady_state = _get_steady_state_mask(df_actual, _STEADY_STATE_START_YEARS)

    df_variance = pd.DataFrame(
        {
            'Time_Years': df_actual['Time_Years'],
            'Measured_Temperature_C': df_actual['Temperature_C'],
            'Is_Thermal_Conditioning': is_thermal_conditioning,
            'Is_Transient_Operation': ~(is_thermal_conditioning | is_steady_state),
        }
    )

    model_interpolator = interp1d(
        df_model_['Time_Years'], df_model_['Temperature_C'], kind='linear', fill_value='extrapolate'
    )
    df_variance['Fervo_Modeled_Temperature_C'] = model_interpolator(df_variance['Time_Years'])
    df_variance.loc[0, 'Fervo_R2'] = fervo_stat_result.r2

    df_variance['GEOPHIRES_Modeled_Temperature_C'] = geo_interp(df_variance['Time_Years'])
    df_variance.loc[0, 'GEOPHIRES_R2'] = geophires_stat_result.r2

    _tab = '    '

    _generate_production_temperature_comparison_graph(
        production_csv_path_,
        model_csv_path_,
        generated_graph_path_stem,
        geophires_data=geophires_series,
        fervo_modeled_stats_caption=f'\n{_tab}{fervo_modeled_stats_caption}\n',
        geophires_modeled_stats_caption=f'\n{_tab}{geophires_modeled_stats_caption}',
    )

    # 8-year long-term simulation graph
    _log.info(f'Running long-term {_LONG_TERM_FORECAST_PLANT_LIFETIME_YEARS}-year forecast simulation...')
    long_term_series = get_long_term_geophires_profile()
    long_term_graph_path = _get_file_path(f'../../docs/_images/{_GENERATED_GRAPH_FILENAME_STEM}-long-term.png')

    _generate_long_term_forecast_graph(
        df_actual,
        df_model_,
        long_term_series,
        _STEADY_STATE_START_YEARS,
        long_term_graph_path,
    )
    _log.info(f'Wrote long-term graph:     {long_term_graph_path}')

    _df_power_sensitivity = _generate_fracture_sensitivity_graph(
        df_actual,
        _STEADY_STATE_START_YEARS,
        _get_file_path(f'../../docs/_images/{_GENERATED_GRAPH_FILENAME_STEM}-fracture-sensitivity.png'),
        _get_file_path(f'../../docs/_images/{_GENERATED_GRAPH_FILENAME_STEM}-power-sensitivity.png'),
        _BUILD_DIR / 'project_red_2026_power_sensitivity.csv',
        df_variance=df_variance,
    )
    _log.info('Wrote sensitivity graphs and power data')

    df_variance.to_csv(variance_analysis_csv_path, index=False)
    _log.info(f'Wrote variance analysis CSV: {variance_analysis_csv_path}')

    generate_fervo_project_red_2026_md(
        *get_project_red_input_params_and_result(), fervo_stat_result, geophires_stat_result
    )


if __name__ == '__main__':
    generate_fervo_project_red_2026_docs()
