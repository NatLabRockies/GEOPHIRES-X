from __future__ import annotations

from typing import Any

from geophires_docs import _FPC7_INPUT_FILE_PATH
from geophires_docs import _FPC7_RESULT_FILE_PATH
from geophires_docs import _PROJECT_ROOT
from geophires_docs import generate_fervo_project_cape_7_md
from geophires_docs.generate_fervo_project_cape_7_graphs import generate_fervo_project_cape_7_graphs
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters

_SINGH_ET_AL_BASE_SIMULATION_PARAMETERS: dict[str, Any] = {
    'Number of Production Wells': 4,
    'Number of Injection Wells per Production Well': '1.2, -- The Singh et al. scenario has 4 producers and 6 injectors. '
    'We model one fewer injector here to account for the combined injection rate being lower for '
    'the higher bench separation cases.',
    'Maximum Drawdown': '1, -- Redrilling not modeled in Singh et al. scenario. '
    '(The equivalent GEOPHIRES simulation allows drawdown to reach up to 100% without triggering redrilling)',
    'Plant Lifetime': 15,
    'Reservoir Depth': '2.68, -- Approximate average depth between the upper and lower benches of the Phase I design '
    'simulated by Singh et al. The case study base case is deeper, corresponding to the Fervo 3.0 well design.',
    'Nonvertical Length per Multilateral Section': '5000 feet, -- Phase I lateral length (BLM, 2024). '
    'The case study base case uses the longer lateral of the Fervo 3.0 well design.',
    'Number of Fractures per Stimulated Well': '150, -- 12 stages for the 5,000 ft Phase I lateral at the case study '
    'stage length, clusters per stage, and stimulation success rate. '
    'The case study base case scales the stage count to the longer 3.0 design lateral.',
}


# fmt:off
def get_singh_et_al_base_simulation_result(base_input_params: GeophiresInputParameters) \
        -> tuple[GeophiresInputParameters,GeophiresXResult]:
    singh_et_al_base_simulation_input_params = ImmutableGeophiresInputParameters(
        from_file_path=base_input_params.as_file_path(),
        params={
            **_SINGH_ET_AL_BASE_SIMULATION_PARAMETERS,
            # Ensure debt tenor does not exceed plant lifetime
            'Debt Tenor': _SINGH_ET_AL_BASE_SIMULATION_PARAMETERS['Plant Lifetime']
        },
    )
    # fmt:on

    singh_et_al_base_simulation_result = GeophiresXClient().get_geophires_result(
        singh_et_al_base_simulation_input_params
    )

    return singh_et_al_base_simulation_input_params, singh_et_al_base_simulation_result


def generate_fervo_project_cape_7_docs():
    input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
        from_file_path=_FPC7_INPUT_FILE_PATH
    )
    result = GeophiresXResult(_FPC7_RESULT_FILE_PATH)

    singh_et_al_base_simulation: tuple[GeophiresInputParameters,GeophiresXResult] = get_singh_et_al_base_simulation_result(input_params)

    generate_fervo_project_cape_7_graphs(
        (input_params, result),
        singh_et_al_base_simulation,
        _PROJECT_ROOT / 'docs/_images'
    )

    generate_fervo_project_cape_7_md.generate_fervo_project_cape_7_md(
        input_params,
        result,
        _SINGH_ET_AL_BASE_SIMULATION_PARAMETERS
    )


if __name__ == '__main__':
    generate_fervo_project_cape_7_docs()
