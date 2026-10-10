"""
Supplementary Fervo_Project_Cape-7 scenario results cited in the case study documentation: the production flow rate
parametric, which is stored as data and regenerated manually because it runs 51 simulations, and single-input
scenarios, which are simulated when the documentation is generated.

Regenerate the flow rate parametric data after changing Fervo_Project_Cape-7 inputs:

    python -m geophires_docs.fervo_project_cape_7_scenarios

FervoProjectCape7TestCase.test_flow_rate_parametric_data_matches_example_result fails when the data is stale.
"""

from __future__ import annotations

import csv
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geophires_docs import _get_fpc7_input_file_path
from geophires_docs import _get_logger
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters

_log = _get_logger(__name__)

FPC7_FLOW_RATE_PARAMETRIC_CSV_PATH: Path = (
    Path(__file__).parent / 'data' / 'Fervo_Project_Cape-7_flow_rate_parametric.csv'
)

_FLOW_RATE_PARAM_NAME = 'Production Flow Rate per Well'


@dataclass(frozen=True)
class FlowRateParametricRow:
    flow_kg_per_s: float
    avg_net_mw: float
    min_net_mw: float
    redrills: int
    lcoe_cents_per_kwh: float
    irr_pct: float
    npv_musd: float

    @staticmethod
    def from_result(flow_kg_per_s: float, result: GeophiresXResult) -> FlowRateParametricRow:
        r = result.result
        surf_equip_sim = r['SURFACE EQUIPMENT SIMULATION RESULTS']
        econ = r['ECONOMIC PARAMETERS']
        return FlowRateParametricRow(
            flow_kg_per_s=flow_kg_per_s,
            avg_net_mw=surf_equip_sim['Average Net Electricity Generation']['value'],
            min_net_mw=surf_equip_sim['Minimum Net Electricity Generation']['value'],
            redrills=int(r['ENGINEERING PARAMETERS']['Number of times redrilling']['value']),
            lcoe_cents_per_kwh=r['SUMMARY OF RESULTS']['Electricity breakeven price']['value'],
            irr_pct=econ['After-tax IRR']['value'],
            npv_musd=econ['Project NPV']['value'],
        )


@dataclass(frozen=True)
class RedrillingStep:
    flow_below_kg_per_s: float
    flow_at_kg_per_s: float
    redrills_below: int
    redrills_at: int


@dataclass(frozen=True)
class FlowRateParametricSummary:
    redrilling_steps: list[RedrillingStep]
    minimum_ppa_feasible_flow_rate_kg_per_s: float
    base_redrills: int
    max_irr_change_above_base_within_band_pct_pts: float


def generate_fpc7_flow_rate_parametric_csv(
    input_params: GeophiresInputParameters | None = None,
    flow_rates_kg_per_s: list[float] | None = None,
    output_path: Path = FPC7_FLOW_RATE_PARAMETRIC_CSV_PATH,
) -> list[FlowRateParametricRow]:
    if input_params is None:
        input_params = ImmutableGeophiresInputParameters(from_file_path=_get_fpc7_input_file_path())

    if flow_rates_kg_per_s is None:
        flow_rates_kg_per_s = [float(it) for it in range(80, 131)]

    client = GeophiresXClient()
    rows = []
    for flow_rate in flow_rates_kg_per_s:
        _log.info(f'Simulating {_FLOW_RATE_PARAM_NAME} = {flow_rate:g} kg/s...')
        result = client.get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=input_params.as_file_path(), params={_FLOW_RATE_PARAM_NAME: flow_rate}
            )
        )
        rows.append(FlowRateParametricRow.from_result(flow_rate, result))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(
            f, fieldnames=[it.name for it in dataclasses.fields(FlowRateParametricRow)], lineterminator='\n'
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: f'{v:g}' if isinstance(v, float) else v for k, v in dataclasses.asdict(row).items()})

    _log.info(f'✓ Wrote {output_path}')
    return rows


def load_fpc7_flow_rate_parametric(path: Path = FPC7_FLOW_RATE_PARAMETRIC_CSV_PATH) -> list[FlowRateParametricRow]:
    with open(path, encoding='utf-8', newline='') as f:
        rows = [
            FlowRateParametricRow(
                flow_kg_per_s=float(it['flow_kg_per_s']),
                avg_net_mw=float(it['avg_net_mw']),
                min_net_mw=float(it['min_net_mw']),
                redrills=int(it['redrills']),
                lcoe_cents_per_kwh=float(it['lcoe_cents_per_kwh']),
                irr_pct=float(it['irr_pct']),
                npv_musd=float(it['npv_musd']),
            )
            for it in csv.DictReader(f)
        ]

    return sorted(rows, key=lambda it: it.flow_kg_per_s)


def get_fpc7_flow_rate_parametric_row(rows: list[FlowRateParametricRow], flow_kg_per_s: float) -> FlowRateParametricRow:
    matching_rows = [it for it in rows if it.flow_kg_per_s == flow_kg_per_s]
    if len(matching_rows) != 1:
        raise ValueError(f'Expected exactly one flow rate parametric row for {flow_kg_per_s:g} kg/s.')

    return matching_rows[0]


def get_fpc7_flow_rate_parametric_summary(
    rows: list[FlowRateParametricRow],
    base_flow_rate_kg_per_s: float,
    ppa_minimum_net_generation_mw: float,
) -> FlowRateParametricSummary:
    """
    :raises ValueError: if the parametric results no longer support the flow rate discussion in the case study
        documentation, which assumes that minimum net generation meets the PPA minimum above a single threshold flow
        rate and that no flow rate with fewer redrilling events than the base case meets it.
    """
    base_row = get_fpc7_flow_rate_parametric_row(rows, base_flow_rate_kg_per_s)

    redrilling_steps = [
        RedrillingStep(
            flow_below_kg_per_s=below.flow_kg_per_s,
            flow_at_kg_per_s=at.flow_kg_per_s,
            redrills_below=below.redrills,
            redrills_at=at.redrills,
        )
        for below, at in zip(rows, rows[1:])
        if below.redrills != at.redrills
    ]

    feasible = [it.min_net_mw >= ppa_minimum_net_generation_mw for it in rows]
    if not any(feasible):
        raise ValueError(f'No flow rate meets the PPA minimum net generation ({ppa_minimum_net_generation_mw:g} MW).')

    first_feasible_idx = feasible.index(True)
    if not all(feasible[first_feasible_idx:]):
        raise ValueError(
            'Minimum net generation does not meet the PPA minimum at every flow rate above the lowest one that does; '
            'update the flow rate discussion in the case study documentation.'
        )

    if any(it.redrills < base_row.redrills and it.min_net_mw >= ppa_minimum_net_generation_mw for it in rows):
        raise ValueError(
            'A flow rate with fewer redrilling events than the base case meets the PPA minimum net generation; '
            'update the flow rate discussion in the case study documentation.'
        )

    band_rows_above_base = [
        it for it in rows if it.flow_kg_per_s >= base_flow_rate_kg_per_s and it.redrills == base_row.redrills
    ]

    return FlowRateParametricSummary(
        redrilling_steps=redrilling_steps,
        minimum_ppa_feasible_flow_rate_kg_per_s=rows[first_feasible_idx].flow_kg_per_s,
        base_redrills=base_row.redrills,
        max_irr_change_above_base_within_band_pct_pts=max(
            abs(it.irr_pct - base_row.irr_pct) for it in band_rows_above_base
        ),
    )


def get_scenario_results(
    input_params: GeophiresInputParameters,
    scenario_params_by_name: dict[str, dict[str, Any]],
) -> dict[str, GeophiresXResult]:
    """
    :return: Result of each scenario, by scenario name, where each scenario overrides the given base case input
        parameters.
    """
    client = GeophiresXClient()
    results = {}
    for scenario_name, scenario_params in scenario_params_by_name.items():
        _log.info(f'Simulating scenario: {scenario_name}...')
        results[scenario_name] = client.get_geophires_result(
            ImmutableGeophiresInputParameters(from_file_path=input_params.as_file_path(), params=scenario_params)
        )

    return results


if __name__ == '__main__':
    generate_fpc7_flow_rate_parametric_csv()
