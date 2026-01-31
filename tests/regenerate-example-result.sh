#!/bin/zsh

set -e

STASH_PWD=$(pwd)
trap 'cd "$STASH_PWD"' EXIT

cd "$(dirname "$0")"

# Use this script to regenerate example results in cases where changes in GEOPHIRES
# calculations alter the example test output. Example:
# ./tests/regenerate-example-result.sh SUTRAExample1
# See https://github.com/NREL/GEOPHIRES-X/issues/107

# Note: make sure your virtualenv is activated and you have run pip install -e . before running or this script will fail
# or generate incorrect results.

echo "Regenerating example: $1..."

if [[ $1 == "Fervo_Project_Cape-6" ]]
then
    echo "Syncing Fervo_Project_Cape-6.txt from Fervo_Project_Cape-5.txt..."

    sed -e 's/Construction Years,.*/Construction Years, 3/' \
        -e 's/Construction CAPEX Schedule,.*/Construction CAPEX Schedule, 0.075,0.525,0.4/' \
        -e '/^# Construction CAPEX Schedule/d' \
        -e '/^# ATB advanced scenario/d' \
        -e '/^# DOE scenario (alternative)/d' \
        -e '/^# DOE-ATB hybrid scenario)/d' \
        -e 's/^Bond Financing Start Year.*/Bond Financing Start Year, -1/' \
        -e 's/^Number of Production Wells,.*/Number of Production Wells, 12/' \
        -e 's/^Production Flow Rate per Well.*/Production Flow Rate per Well, 100/' \
        -e 's/500 MWe/100 MWe/' \
        -e 's/Phase II/Phase I/' \
        -e 's/\/Fervo_Project_Cape-5.html/\/Fervo_Project_Cape-5.html#Fervo_Project_Cape-6-section/' \
        examples/Fervo_Project_Cape-5.txt > examples/Fervo_Project_Cape-6.txt
fi

if [[ $1 == "example5b" ]]
then
    python regenerate_example_input_reservoir_output_profile.py example5b src/geophires_x/Examples/ReservoirOutput.txt
fi

python -mgeophires_x examples/$1.txt examples/$1.out
rm examples/$1.json

if [[ $1 == "example1_addons" ]]
then
    echo "Updating example1_addons CSV..."
    python regenerate_example_result_csv.py example1_addons
fi

if [[ $1 == "example_SAM-single-owner-PPA-5" ]]
then
    echo "Regenerating example_SAM-single-owner-PPA-5 cash flow CSV..."
    python regenerate_example_result_csv.py example_SAM-single-owner-PPA-5 --output-path examples --csv-type cash-flow
fi

if [[ $1 == "Fervo_Project_Cape-5" ]]
then
    python ../src/geophires_docs/generate_fervo_project_cape_5_docs.py

    ./regenerate-example-result.sh Fervo_Project_Cape-6

    if [ ! -f regenerate-example-result.env ] && [ -f regenerate-example-result.env.template ]; then
        echo "Creating regenerate-example-result.env from template..."
        cp regenerate-example-result.env.template regenerate-example-result.env
    fi

    source regenerate-example-result.env
    if [ -n "$GEOPHIRES_FPC5_SENSITIVITY_ANALYSIS_PROJECT_ROOT" ]; then
        echo "Updating sensitivity analysis..."
        STASH_PWD_2=$(pwd)
        cd $GEOPHIRES_FPC5_SENSITIVITY_ANALYSIS_PROJECT_ROOT
        source venv/bin/activate
        python -m fpc_sensitivity_analysis.generate_geophires_fpc5_sensitivity_analysis
        deactivate
        cd $STASH_PWD_2
    fi
fi

if [[ $1 == "example5" ]]
then
    ./regenerate-example-result.sh example5b
fi

echo "Regenerated example $1."
