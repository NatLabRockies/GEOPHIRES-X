import argparse
import os

RESERVOIR_OUTPUT_PROFILE_PARAM_NAME = 'Reservoir Output Profile'
RESERVOIR_OUTPUT_PROFILE_TIME_STEP_PARAM_NAME = 'Reservoir Output Profile Time Step'
RESERVOIR_MODEL_PARAM_NAME = 'Reservoir Model'


def _get_file_path(file_name: str) -> str:
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), str(file_name))


def _is_numeric(value: str) -> bool:
    """Check if a string value can be converted to a float."""
    try:
        float(value)
        return True
    except ValueError:
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Regenerate a CSV result file from a GEOPHIRES-X example .out file.')
    parser.add_argument(
        'example_id',
        type=str,
        nargs='?',  # Makes the argument optional
        default='example5b',
        help='The base name of the example file',
    )
    parser.add_argument(
        'reservoir_output_source_file',
        type=str,
        nargs='?',  # Makes the argument optional
        default='src/geophires_x/Examples/ReservoirOutput.txt',
        help='Path to reservoir source file relative to project root',
    )
    args = parser.parse_args()

    reservoir_output_source_file = args.reservoir_output_source_file
    example_file_name = f'{args.example_id}.txt'
    print(f'Syncing {example_file_name} {RESERVOIR_OUTPUT_PROFILE_PARAM_NAME} from {reservoir_output_source_file}...')

    # 1. Read ReservoirOutput.txt and extract time and temperature values
    reservoir_output_path = _get_file_path(f'../{reservoir_output_source_file}')
    times = []
    temperatures = []
    with open(reservoir_output_path) as f:
        for line in f:
            line = line.strip()
            if line:
                # Each line has format: "time , temperature"
                parts = line.split(',')
                if len(parts) >= 2:
                    time_val = parts[0].strip()
                    temp = parts[1].strip()
                    # Skip header rows by checking if the values are numeric
                    if _is_numeric(time_val) and _is_numeric(temp):
                        times.append(float(time_val))
                        temperatures.append(temp)

    # Calculate time step from the input data
    if len(times) >= 2:
        time_step = times[1] - times[0]
    else:
        time_step = 1.0  # Default fallback

    # 2. Update example file with the new Reservoir Output Profile and Time Step
    example_path = _get_file_path(f'examples/{example_file_name}')
    reservoir_output_profile_value = ','.join(temperatures)
    reservoir_output_profile_line = f'{RESERVOIR_OUTPUT_PROFILE_PARAM_NAME}, {reservoir_output_profile_value}\n'
    reservoir_output_time_step_line = f'{RESERVOIR_OUTPUT_PROFILE_TIME_STEP_PARAM_NAME}, {time_step}\n'

    with open(example_path) as f:
        lines = f.readlines()

    # Check if parameters already exist in the file
    profile_exists = any(line.startswith(f'{RESERVOIR_OUTPUT_PROFILE_PARAM_NAME},') for line in lines)
    time_step_exists = any(line.startswith(f'{RESERVOIR_OUTPUT_PROFILE_TIME_STEP_PARAM_NAME},') for line in lines)

    with open(example_path, 'w') as f:
        for line in lines:
            if line.startswith(f'{RESERVOIR_OUTPUT_PROFILE_PARAM_NAME},'):
                # Replace the existing line with updated temperature profile
                f.write(reservoir_output_profile_line)
            elif line.startswith(f'{RESERVOIR_OUTPUT_PROFILE_TIME_STEP_PARAM_NAME},'):
                # Replace the existing time step line
                f.write(reservoir_output_time_step_line)
            elif not profile_exists and line.startswith(f'{RESERVOIR_MODEL_PARAM_NAME},'):
                # Write the Reservoir Model line first
                f.write(line)
                # Insert the Reservoir Output Profile line after Reservoir Model
                f.write(reservoir_output_profile_line)
                # Also insert the time step line
                f.write(reservoir_output_time_step_line)
            else:
                f.write(line)

        # If time step line didn't exist and wasn't added after Reservoir Model, we need to add it
        # This handles the case where profile_exists=True but time_step_exists=False

    # Re-read and add time step if it still doesn't exist
    if profile_exists and not time_step_exists:
        with open(example_path) as f:
            lines = f.readlines()

        with open(example_path, 'w') as f:
            for line in lines:
                f.write(line)
                if line.startswith(f'{RESERVOIR_OUTPUT_PROFILE_PARAM_NAME},'):
                    # Insert time step right after the profile
                    f.write(reservoir_output_time_step_line)

    print(
        f'Updated {example_file_name} {RESERVOIR_OUTPUT_PROFILE_PARAM_NAME} '
        f'with {len(temperatures)} temperature values (time step: {time_step} yr) from {reservoir_output_source_file}'
    )
