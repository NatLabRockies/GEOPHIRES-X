from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from pint.facets.plain import PlainQuantity

from geophires_x.ParameterUtils import COMMENT_PARAMETER_NAME_PREFIX
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult

_NON_BREAKING_SPACE = '\xa0'


def _get_file_path(file_name) -> Path:
    return Path(os.path.join(os.path.abspath(os.path.dirname(__file__)), file_name))


def _get_project_root() -> Path:
    return _get_file_path('../..')


def _get_fpc7_input_file_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        project_root = _get_project_root()
    return project_root / 'tests/examples/Fervo_Project_Cape-7.txt'


def _get_fpc7_result_file_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        project_root = _get_project_root()
    return project_root / 'tests/examples/Fervo_Project_Cape-7.out'


_PROJECT_ROOT: Path = _get_project_root()
_FPC7_INPUT_FILE_PATH: Path = _get_fpc7_input_file_path()
_FPC7_RESULT_FILE_PATH: Path = _get_fpc7_result_file_path()

_FPC7_PPA_MINIMUM_NET_GENERATION_MW: float = 500.0

# Gross capacity of each Gen 2 ORC unit announced for Cape Station Phase II (Turboden, 2025; Jacobs, 2025).
_FPC7_ORC_UNIT_GROSS_CAPACITY_MW: float = 60.0


def _get_fpc7_orc_unit_count(max_total_generation_mw: float) -> int:
    """
    :return: Number of Gen 2 ORC units required for nameplate capacity to cover the maximum total (gross) generation.
    """
    return math.ceil(max_total_generation_mw / _FPC7_ORC_UNIT_GROSS_CAPACITY_MW)


def _get_logger(_name_: str) -> Any:
    # TODO consolidate _get_logger methods into a commonly accessible utility

    # sh = logging.StreamHandler(sys.stdout)
    # sh.setLevel(logging.INFO)
    # sh.setFormatter(logging.Formatter(fmt='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    #
    # ret = logging.getLogger(__name__)
    # ret.addHandler(sh)
    # return ret

    # noinspection PyMethodMayBeStatic
    class _PrintLogger:
        def info(self, msg):
            print(f'[INFO] {msg}')

        def error(self, msg):
            print(f'[ERROR] {msg}')

    return _PrintLogger()


def _get_input_parameters_dict(  # TODO consolidate with FervoProjectCape7TestCase._get_input_parameters
    _params: GeophiresInputParameters, include_parameter_comments: bool = False, include_line_comments: bool = False
) -> dict[str, Any]:
    comment_idx = 0
    ret: dict[str, Any] = {}
    for line in _params.as_text().split('\n'):
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


def _get_input_parameters_comments_dict(_params: GeophiresInputParameters) -> dict[str, str]:
    ret: dict[str, str] = {}

    with open(_get_file_path('../geophires_x_schema_generator/geophires-request.json'), encoding='utf-8') as f:
        request_schema = json.loads(f.read())

    input_params_with_comments: dict[str, Any] = _get_input_parameters_dict(_params, include_parameter_comments=True)
    for k, v in input_params_with_comments.items():
        comment: str = ''

        if v is not None and isinstance(v, str) and ',' in v:
            ARRAY_TYPE_COMMENT_DELINEATOR = ', --'  # TODO use regex to treat space after comma as optional
            if (
                k in request_schema['properties']
                and request_schema['properties'][k]['type'] == 'array'
                and ARRAY_TYPE_COMMENT_DELINEATOR in v
            ):
                comment = v.split(ARRAY_TYPE_COMMENT_DELINEATOR, maxsplit=1)[1]
            else:
                comment = v.split(',', maxsplit=1)[1]
                # Strip ' --' and optional whitespace from the start of the comment
                comment = re.sub(r'^\s*--\s*', '', comment)

            comment = comment.strip()

        ret[k] = comment

    return ret


def _get_full_profile(
    input_and_result: tuple[GeophiresInputParameters, GeophiresXResult], profile_key: str
) -> list[PlainQuantity]:
    """
    :return: List of data points with length Time steps per year * Plant lifetime
    """

    input_params: GeophiresInputParameters = input_and_result[0]
    result = GeophiresXClient().get_geophires_result(input_params)

    with open(result.json_output_file_path, encoding='utf-8') as f:
        full_result_obj = json.load(f)

    net_gen_obj = full_result_obj[profile_key]
    net_gen_obj_unit = net_gen_obj['CurrentUnits'].replace('CELSIUS', 'degC')
    profile = [PlainQuantity(it, net_gen_obj_unit) for it in net_gen_obj['value']]
    return profile


def _get_full_production_temperature_profile(
    input_and_result: tuple[GeophiresInputParameters, GeophiresXResult],
) -> list[PlainQuantity]:
    return _get_full_profile(input_and_result, 'Produced Temperature')
