import argparse
import csv
import os
from io import StringIO
from pathlib import Path
from typing import Any

from geophires_x_client import GeophiresXResult


def _get_file_path(file_name: str) -> str:
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), str(file_name))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Regenerate a CSV result file from a GEOPHIRES example .out file.')
    parser.add_argument(
        'example_name',
        type=str,
        nargs='?',  # Makes the argument optional
        default='example1_addons',
        help='The base name of the example file (e.g., "example1_addons"). Defaults to "example1_addons".',
    )
    parser.add_argument(
        '--output-path',
        type=str,
        default=None,
        help='Optional CSV output path relative to tests/ directory.',
    )
    parser.add_argument(
        '--csv-type',
        type=str,
        default='result',
        help='Optional CSV type: "result" (default) or "cash-flow".',
    )
    args = parser.parse_args()

    example_name = args.example_name
    example_relative_path = f'{"examples/" if example_name.startswith("example") else ""}{example_name}.out'

    output_path = _get_file_path(Path(args.output_path, f'{example_name}.csv'))
    with open(output_path, 'w', encoding='utf-8') as csvfile:
        geophires_result: GeophiresXResult = GeophiresXResult(_get_file_path(example_relative_path))
        if args.csv_type == 'result':
            csv_content = geophires_result.as_csv()
        elif args.csv_type == 'cash-flow':
            # TODO port to GeophiresXResult convenience method
            sam_cash_flow_profile: list[list[Any]] = geophires_result.result['SAM CASH FLOW PROFILE']
            f = StringIO()
            w = csv.writer(f)
            for row in sam_cash_flow_profile:
                w.writerow(row)

            csv_content = f.getvalue()

        else:
            raise NotImplementedError

        csvfile.write(csv_content)
