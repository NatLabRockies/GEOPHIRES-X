from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from geophires_x_client import GeophiresInputParameters


def _get_file_path(file_name) -> Path:
    return Path(os.path.join(os.path.abspath(os.path.dirname(__file__)), file_name))


def _get_project_root() -> Path:
    return _get_file_path('../..')


def _get_fpc5_input_file_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        project_root = _get_project_root()
    return project_root / 'tests/examples/Fervo_Project_Cape-5.txt'


def _get_fpc5_result_file_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        project_root = _get_project_root()
    return project_root / 'tests/examples/Fervo_Project_Cape-5.out'


_PROJECT_ROOT: Path = _get_project_root()
_FPC5_INPUT_FILE_PATH: Path = _get_fpc5_input_file_path()
_FPC5_RESULT_FILE_PATH: Path = _get_fpc5_result_file_path()


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


def _get_input_parameters_dict(  # TODO consolidate with FervoProjectCape5TestCase._get_input_parameters
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
            ret[f'_COMMENT-{comment_idx}'] = line.strip()
            comment_idx += 1

        # TODO preserve newlines

    return ret
