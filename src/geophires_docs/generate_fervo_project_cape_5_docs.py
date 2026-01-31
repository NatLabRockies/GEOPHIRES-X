from __future__ import annotations

from typing import Any

from geophires_docs import _FPC5_INPUT_FILE_PATH
from geophires_docs import _FPC5_RESULT_FILE_PATH
from geophires_docs import _PROJECT_ROOT
from geophires_docs import generate_fervo_project_cape_5_md
from geophires_docs.generate_fervo_project_cape_5_graphs import generate_fervo_project_cape_5_graphs
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
}


# fmt:off
def get_singh_et_al_base_simulation_result(base_input_params: GeophiresInputParameters) \
        -> tuple[GeophiresInputParameters,GeophiresXResult]:
    singh_et_al_base_simulation_input_params = ImmutableGeophiresInputParameters(
        from_file_path=base_input_params.as_file_path(),
        params=_SINGH_ET_AL_BASE_SIMULATION_PARAMETERS,
    )
    # fmt:on

    singh_et_al_base_simulation_result = GeophiresXClient().get_geophires_result(
        singh_et_al_base_simulation_input_params
    )

    return singh_et_al_base_simulation_input_params, singh_et_al_base_simulation_result


def generate_fervo_project_cape_5_docs():
    input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
        from_file_path=_FPC5_INPUT_FILE_PATH
    )
    result = GeophiresXResult(_FPC5_RESULT_FILE_PATH)

    singh_et_al_base_simulation: tuple[GeophiresInputParameters,GeophiresXResult] = get_singh_et_al_base_simulation_result(input_params)

    generate_fervo_project_cape_5_graphs(
        (input_params, result),
        singh_et_al_base_simulation,
        _PROJECT_ROOT / 'docs/_images'
    )

    generate_fervo_project_cape_5_md.generate_fervo_project_cape_5_md(
        input_params,
        result,
        _SINGH_ET_AL_BASE_SIMULATION_PARAMETERS
    )


if __name__ == '__main__':
    generate_fervo_project_cape_5_docs()
