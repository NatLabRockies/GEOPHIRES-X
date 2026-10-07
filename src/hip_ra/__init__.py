import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

# noinspection PyProtectedMember
from geophires_x_client.common import _get_logger
from hip_ra import HIP_RA


class HipRaInputParameters:

    def __init__(self, file_path_or_params_dict: Any):
        if isinstance(file_path_or_params_dict, dict):
            tmp_file_path = Path(tempfile.gettempdir(), f'hip-ra-params_{uuid.uuid1()}.txt')
            with open(tmp_file_path, 'w') as f:
                f.writelines(
                    [', '.join([str(p) for p in param_item]) + '\n' for param_item in file_path_or_params_dict.items()]
                )
            file_path_or_params_dict = str(tmp_file_path)
        elif not isinstance(file_path_or_params_dict, (str, Path)):
            raise ValueError('Provide either file path (as Path or string) or parameters as dict')

        self._input_file_path = Path(file_path_or_params_dict)
        self._output_file_path = Path(
            tempfile.gettempdir(), f'hip-ra-result_{self._input_file_path.stem}_{uuid.uuid1()!s}.out'
        )

    def as_file_path(self) -> Path:
        return self._input_file_path

    @property
    def output_file_path(self) -> Path:
        return self._output_file_path


class HipRaResult:
    def __init__(self, output_file_path):
        self.output_file_path = output_file_path
        self.result = self._parse_fields()

    def _parse_fields(self):
        with open(self.output_file_path) as f:
            text = f.read()
            pattern = re.compile(r'(.+?):\s+([0-9eE.+-]+)\s*(\S+)*?\n')

            matches = re.findall(pattern, text)

            result = {
                key.strip(): {'value': float(value), 'unit': unit.strip() if unit else None}
                for key, value, unit in matches
            }

            # Second, additive pass for non-numeric field values (such as GRMS
            # classification designations). Numeric fields are already captured
            # above and are not revisited, so existing results are unchanged.
            text_pattern = re.compile(r'^\s{6}(\S[^:\n]*?):\s+(\S[^\n]*?)\s*$', re.MULTILINE)
            for key, value in re.findall(text_pattern, text):
                key = key.strip()

                if re.fullmatch(r'[0-9eE.+-]+(\s+\S+)?', value):
                    # A number, optionally followed by a unit: already captured
                    # by the numeric pass above.
                    continue

                # Anything else is a text value. This overrides the numeric pass,
                # which splits values like '2P' into 2.0 with unit 'P' because it
                # does not require whitespace between value and unit.
                result[key] = {'value': value, 'unit': None}

            return result


class HipRaClient:
    def __init__(self, enable_caching=True, logger_name='root'):
        self._logger = _get_logger(logger_name=logger_name)

    def get_hip_ra_result(self, input_params: HipRaInputParameters) -> HipRaResult:
        stash_cwd = Path.cwd()
        stash_sys_argv = sys.argv

        sys.argv = ['', input_params.as_file_path(), input_params.output_file_path]
        try:
            HIP_RA.main(enable_hip_ra_logging_config=False)
        except Exception as e:
            raise RuntimeError(f'HIP-RA encountered an exception: {e!s}') from e
        except SystemExit:
            raise RuntimeError('HIP-RA exited without giving a reason') from None
        finally:
            # Undo HIP-RA internal global settings changes
            sys.argv = stash_sys_argv
            os.chdir(stash_cwd)

        self._logger.info(f'HIP-RA output file: {input_params.output_file_path}')

        return HipRaResult(input_params.output_file_path)
