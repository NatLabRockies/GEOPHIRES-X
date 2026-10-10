from __future__ import annotations

import io
import logging
import os
import re
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from geophires_x.Parameter import OutputParameter
from geophires_x.Parameter import ParameterEntry
from geophires_x.Parameter import floatParameter
from geophires_x.Parameter import intParameter
from geophires_x.Units import EnthalpyUnit
from geophires_x.Units import HeatUnit
from geophires_x.Units import PercentUnit
from geophires_x.Units import PowerUnit
from geophires_x.Units import TemperatureUnit
from geophires_x.Units import Units
from geophires_x.Units import VolumeUnit
from hip_ra import HipRaClient
from hip_ra import HipRaInputParameters
from hip_ra import HipRaResult
from hip_ra.HIP_RA import HIP_RA
from hip_ra_x import HipRaXClient
from hip_ra_x import HipRaXResult
from hip_ra_x.hip_ra_x import HIP_RA_X
from tests.base_test_case import BaseTestCase


# noinspection PyTypeChecker
class HipRaXTestCase(BaseTestCase):
    def test_hip_ra_x_examples(self):
        example_files = self._list_test_files_dir(test_files_dir='./examples')
        assert len(example_files) > 0  # test integrity check - no files means something is misconfigured

        client = HipRaXClient()

        def get_output_file_for_example(example_file: Path):
            return self._get_test_file_path(Path(example_file).with_suffix('.out'))

        for example_file_path in example_files:
            if (
                example_file_path.startswith(('HIP-RA-X_example', 'Fervo_Project_Cape-HIIP'))
                and '.out' not in example_file_path
            ):
                with self.subTest(msg=example_file_path):
                    input_file_path = self._get_test_file_path(Path('./examples', example_file_path))
                    result = client.get_hip_ra_result(HipRaInputParameters(input_file_path))

                    assert result is not None
                    expected_result_output_file_path = get_output_file_for_example(input_file_path)

                    expected_result = HipRaResult(expected_result_output_file_path)
                    self.assertDictEqual(expected_result.result, result.result)

                    # TODO
                    # self.assertFileContentsEqual(expected_result_output_file_path, result.output_file_path)

                    x_result = client.get_hip_ra_x_result(HipRaInputParameters(input_file_path))
                    expected_x_result = HipRaXResult.from_hip_ra_result(expected_result)
                    self.assertDictEqual(expected_x_result.result, x_result.result)

    def test_print_output_to_console(self):
        def get_stdout_from_running(print_output_to_console: bool | int) -> str:
            params = {
                'Reservoir Temperature': 250.0,
                'Rejection Temperature': 60.0,
                'Reservoir Porosity': 10.0,
                'Reservoir Area': 55.0,
                'Reservoir Thickness': 0.25,
                'Reservoir Life Cycle': 25,
                'Print Output to Console': print_output_to_console,
            }

            f = io.StringIO()
            with redirect_stdout(f):
                result: HipRaResult = HipRaXClient().get_hip_ra_result(HipRaInputParameters(params))

            self.assertIsNotNone(result)
            return f.getvalue()

        self.assertIn('***HIP CASE REPORT***', get_stdout_from_running(True))
        self.assertNotIn('***HIP CASE REPORT***', get_stdout_from_running(False))
        self.assertIn('***HIP CASE REPORT***', get_stdout_from_running(1))
        self.assertNotIn('***HIP CASE REPORT***', get_stdout_from_running(0))

    def test_result_parsing_1(self):
        result = HipRaResult(self._get_test_file_path('hip-result_example-1.out'))
        self.assertIsNotNone(result.result)
        self.assertDictEqual(
            result.result,
            {
                'Reservoir Temperature': {'value': 250.0, 'unit': 'degC'},
                'Reservoir Volume': {'value': 13.75, 'unit': 'km**3'},
                'Stored Heat': {'value': 7420000000000000.0, 'unit': 'kJ'},
                'Fluid Produced': {'value': 1100000000000.0, 'unit': 'kilogram'},
                'Enthalpy': {'value': 181.43, 'unit': 'kJ/kg'},
                'Wellhead Heat': {'value': 827000000000000.0, 'unit': 'kJ'},
                'Recovery Factor': {'value': 11.15, 'unit': '%'},
                'Available Heat': {'value': 14700000000000.0, 'unit': 'kJ'},
                'Producible Heat': {'value': 5860000000000.0, 'unit': 'kJ'},
                'Producible Electricity': {'value': 185.85, 'unit': 'MW'},
            },
        )

    def test_result_parsing_2(self):
        result = HipRaResult(self._get_test_file_path('hip-result_example-2.out'))
        self.assertIsNotNone(result.result)
        self.assertDictEqual(
            result.result,
            {
                'Reservoir Temperature': {'value': 250.00, 'unit': 'degC'},
                'Reservoir Volume (reservoir)': {'value': 13.75, 'unit': 'km**3'},
                'Reservoir Volume (rock)': {'value': 12.38, 'unit': 'km**3'},
                'Reservoir Volume (fluid)': {'value': 0.69, 'unit': 'km**3'},
                'Stored Heat (reservoir)': {'value': 5.52e15, 'unit': 'kJ'},
                'Stored Heat (rock)': {'value': 5.01e15, 'unit': 'kJ'},
                'Stored Heat (fluid)': {'value': 5.09e14, 'unit': 'kJ'},
                'Mass of Reservoir (total)': {'value': 3.21e13, 'unit': 'kilogram'},
                'Mass of Reservoir (rock)': {'value': 3.16e13, 'unit': 'kilogram'},
                'Mass of Reservoir (fluid)': {'value': 5.49e11, 'unit': 'kilogram'},
                'Enthalpy (reservoir)': {'value': 49.31, 'unit': 'kJ/kg'},
                'Enthalpy (rock)': {'value': -333.72, 'unit': 'kJ/kg'},
                'Enthalpy (fluid)': {'value': 383.04, 'unit': 'kJ/kg'},
                'Wellhead Heat (reservoir)': {'value': 5.52e15, 'unit': 'kJ'},
                'Wellhead Heat (rock)': {'value': 5.01e15, 'unit': 'kJ'},
                'Wellhead Heat (fluid)': {'value': 5.09e14, 'unit': 'kJ'},
                'Recovery Factor (reservoir)': {'value': -49.39, 'unit': '%'},
                'Recovery Factor (rock)': {'value': -55.51, 'unit': '%'},
                'Recovery Factor (fluid)': {'value': 10.91, 'unit': '%'},
                'Available Heat (reservoir)': {'value': -6.81e15, 'unit': 'kJ'},
                'Available Heat (rock)': {'value': -6.95e15, 'unit': 'kJ'},
                'Available Heat (fluid)': {'value': 1.39e14, 'unit': 'kJ'},
                'Producible Heat (reservoir)': {'value': -2.72e15, 'unit': 'kJ'},
                'Producible Heat (rock)': {'value': -2.78e15, 'unit': 'kJ'},
                'Producible Heat (fluid)': {'value': 5.55e13, 'unit': 'kJ'},
                'Producible Heat/Unit Area (reservoir)': {'value': -4.95e13, 'unit': 'KJ/km**2'},
                'Producible Heat/Unit Area (rock)': {'value': -5.05e13, 'unit': 'KJ/km**2'},
                'Producible Heat/Unit Area (fluid)': {'value': 1.01e12, 'unit': 'KJ/km**2'},
                'Producible Electricity (reservoir)': {'value': -86399.37, 'unit': 'MW'},
                'Producible Electricity (rock)': {'value': -88159.67, 'unit': 'MW'},
                'Producible Electricity (fluid)': {'value': 1760.30, 'unit': 'MW'},
                'Producible Electricity/Unit Area (reservoir)': {'value': -1570.90, 'unit': 'MW/km**2'},
                'Producible Electricity/Unit Area (rock)': {'value': -1602.90, 'unit': 'MW/km**2'},
                'Producible Electricity/Unit Area (fluid)': {'value': 32.01, 'unit': 'MW/km**2'},
            },
        )

    def test_result_parsing_3(self):
        result = HipRaResult(self._get_test_file_path('hip-result_test-result-parsing-3.out'))
        self.assertIsNone(result.result['Recoverable Fluid Factor']['unit'])
        self.assertEqual(result.result['Recoverable Fluid Factor']['value'], 0.50)
        self.assertEqual(result.result['Producible Heat/Unit Area (reservoir)']['value'], 1.37e13)
        self.assertEqual(result.result['Producible Heat/Unit Area (reservoir)']['unit'], 'kJ/km**2')

    def test_calculate_reservoir_volume(self):
        """Calculates the volume of the reservoir"""

        hip_ra = self._new_hip_ra_test_instance()
        hip_ra.Calculate()
        assert hip_ra.reservoir_volume.value == hip_ra.reservoir_area.value * hip_ra.reservoir_thickness.value

    @unittest.skip(reason='FIXME: Race condition if tests are run in parallel')
    def test_standard_outputs(self):
        """Prints the standard outputs to the output file"""

        hip_ra = self._new_hip_ra_test_instance()
        hip_ra.PrintOutputs()

        # Assert that the output file is created
        # ruff: noqa: PTH110
        assert os.path.exists('HIP.out')

        # Assert that the output file is not empty
        # ruff: noqa: PTH202
        assert os.path.getsize('HIP.out') > 0

        # Clean up the output file
        # ruff: noqa: PTH107
        os.remove('HIP.out')

    def test_converts_units_back(self):
        """Converts Units back to PreferredUnits, if required"""

        hip_ra = self._new_hip_ra_test_instance()
        hip_ra.PrintOutputs()

        # Assert that the units of all parameters in ParameterDict are converted back to PreferredUnits
        for key in hip_ra.ParameterDict:
            param = hip_ra.ParameterDict[key]
            assert param.CurrentUnits == param.PreferredUnits

    def test_updates_output_parameter_units(self):
        hip_ra = self._new_hip_ra_test_instance()
        hip_ra.PrintOutputs()
        # Assert that the units of all parameters in OutputParameterDict are updated to the user-specified units
        for key in hip_ra.OutputParameterDict:
            param: OutputParameter = hip_ra.OutputParameterDict[key]
            assert param.CurrentUnits == param.PreferredUnits

    @unittest.skip(reason='FIXME: Race condition if tests are run in parallel')
    def test_raises_permission_error(self):
        """Raises a PermissionError if there is no permission to write to the output file"""

        hip_ra = self._new_hip_ra_test_instance()
        # Create a read-only file
        Path.chmod('HIP.out', 0o444)
        with self.assertRaises(PermissionError):
            hip_ra.PrintOutputs()
        # Restore file permissions
        Path.chmod('HIP.out', 0o644)

    def test_handles_converting_output_units(self):
        """Handles converting output units for all classes of units (TEMPERATURE, DENSITY, etc.)"""

        hip_ra: HIP_RA = self._new_hip_ra_test_instance()
        hip_ra.PrintOutputs()
        # Assert that the units of all parameters in OutputParameterDict are converted to the user-specified units
        for key in hip_ra.OutputParameterDict:
            param = hip_ra.OutputParameterDict[key]
            assert param.CurrentUnits == param.PreferredUnits

    def test_handles_rendering_float_parameters_in_scientific_notation(self):
        """
        Assert that the float parameters in scientific notation are rendered correctly in the output file
        """
        client = HipRaClient()
        result: HipRaResult = client.get_hip_ra_result(
            HipRaInputParameters(self._get_test_file_path('./examples/HIP-RA-X_example1.txt'))
        )
        with open(result.output_file_path) as f:
            content = f.read()
            assert len(re.compile(r'[0-9]e\+[0-9]+\s').findall(content)) > 0

    def test_read_all_parameters_no_effect_with_no_input_file(self):
        def read_params(hip_ra):
            hip_ra.read_parameters()

        hip_ra: HIP_RA = self._new_hip_ra_test_instance(pre_re_stash_runner=read_params)

        # Assert that all the parameters have been read in and updated
        assert hip_ra.reservoir_temperature.value == 150.0
        assert hip_ra.rejection_temperature.value == 25.0
        assert hip_ra.reservoir_porosity.value == 18.0
        assert hip_ra.reservoir_area.value == 81.0
        assert hip_ra.reservoir_thickness.value == 0.286

    def test_update_changed_parameters(self):
        """updates any of these parameter values that have been changed by the user"""

        def set_and_read_input_params(hip_ra):
            # Set some input parameters to be changed by the user
            hip_ra.InputParameters = {
                param.Name: param
                for param in [
                    ParameterEntry(Name='Reservoir Temperature', sValue='200'),
                    ParameterEntry(Name='Reservoir Porosity', sValue='25.0'),
                ]
            }

            hip_ra.read_parameters()

        hip_ra: HIP_RA = self._new_hip_ra_test_instance(pre_re_stash_runner=set_and_read_input_params)

        # Assert that the changed parameters have been updated
        assert hip_ra.reservoir_temperature.value == 200.0
        assert hip_ra.reservoir_porosity.value == 25.0

    def test_handle_special_cases(self):
        def set_and_read_input_params(hip_ra):
            # Set some input parameters to trigger special cases
            hip_ra.InputParameters = {
                param.Name: param
                for param in [
                    ParameterEntry(Name='Reservoir Porosity', sValue='30.0'),
                    ParameterEntry(Name='Rejection Temperature', sValue='50.0'),
                    ParameterEntry(Name='Density Of Water', sValue='-1'),
                    ParameterEntry(Name='Heat Capacity Of Water', sValue='-1'),
                    ParameterEntry(Name='Recoverable Heat', sValue='-1'),
                ]
            }

            hip_ra.read_parameters()

        hip_ra = self._new_hip_ra_test_instance(pre_re_stash_runner=set_and_read_input_params)

        assert hip_ra.rejection_temperature.value == 50
        assert hip_ra.fluid_density.value == -1
        assert hip_ra.fluid_heat_capacity.value == -1
        assert hip_ra.fluid_recoverable_heat.value == -1

    def test_set_current_units_preferred_units_match(self):
        """sets the CurrentUnits of a parameter to its PreferredUnits if they match"""

        def set_and_read_input_params(hip_ra):
            # Set some input parameters with matching PreferredUnits
            hip_ra.InputParameters = {
                param.Name: param
                for param in [
                    ParameterEntry(Name='Reservoir Temperature', sValue='150.0'),
                    ParameterEntry(Name='Formation Porosity', sValue='18.0'),
                ]
            }

            hip_ra.read_parameters()

        hip_ra = self._new_hip_ra_test_instance(pre_re_stash_runner=set_and_read_input_params)

        # Assert that the CurrentUnits have been set to PreferredUnits
        assert hip_ra.reservoir_temperature.CurrentUnits == TemperatureUnit.CELSIUS
        assert hip_ra.reservoir_porosity.CurrentUnits == PercentUnit.PERCENT

    def test_set_current_units_preferred_units_do_not_match(self):
        """sets the CurrentUnits of a parameter to the units provided by the user if they don't match"""

        def set_and_read_input_params(hip_ra: HIP_RA):
            # Set some input parameters with non-matching PreferredUnits
            hip_ra.InputParameters = {
                param.Name: param
                for param in [
                    # TODO Pint conversion would treat 'F' as farad, hence 'degF' here. However, it is possible to
                    #  configure Pint to treat 'F' as Fahrenheit instead, which should be done since users could make
                    #  this mistake.
                    ParameterEntry(Name='Reservoir Temperature', sValue='150.0 degF'),
                    ParameterEntry(Name='Formation Porosity', sValue='18.0 %'),
                ]
            }

            hip_ra.read_parameters()

        hip_ra: HIP_RA = self._new_hip_ra_test_instance(pre_re_stash_runner=set_and_read_input_params)

        # Assert that the CurrentUnits have been set to the units provided by the user
        assert hip_ra.reservoir_temperature.CurrentUnits == TemperatureUnit.FAHRENHEIT
        assert hip_ra.reservoir_porosity.CurrentUnits == PercentUnit.PERCENT

    def test_convert_units_of_output_parameters(self):
        """The class converts units of the output parameters if specified in the input file."""

        hip_ra: HIP_RA = self._new_hip_ra_test_instance()
        hip_ra.OutputParameterDict['Reservoir Volume (reservoir)'].PreferredUnits = VolumeUnit.METERS3
        hip_ra.OutputParameterDict['Stored Heat (reservoir)'].PreferredUnits = HeatUnit.J

        hip_ra.OutputParameterDict['Specific Enthalpy (reservoir)'].PreferredUnits = EnthalpyUnit.KJPERKG

        hip_ra.OutputParameterDict['Wellhead Heat (reservoir)'].PreferredUnits = HeatUnit.J
        hip_ra.OutputParameterDict['Recovery Factor (reservoir)'].PreferredUnits = PercentUnit.PERCENT
        hip_ra.OutputParameterDict['Available Heat (reservoir)'].PreferredUnits = HeatUnit.J
        hip_ra.OutputParameterDict['Producible Heat (reservoir)'].PreferredUnits = HeatUnit.J
        hip_ra.OutputParameterDict['Producible Electricity (reservoir)'].PreferredUnits = PowerUnit.W

        hip_ra.PrintOutputs()

        assert hip_ra.OutputParameterDict['Reservoir Volume (reservoir)'].CurrentUnits == VolumeUnit.KILOMETERS3
        assert hip_ra.OutputParameterDict['Stored Heat (reservoir)'].CurrentUnits == HeatUnit.KJ

        assert hip_ra.OutputParameterDict['Specific Enthalpy (reservoir)'].CurrentUnits == EnthalpyUnit.KJPERKG
        assert hip_ra.OutputParameterDict['Recovery Factor (reservoir)'].CurrentUnits == PercentUnit.PERCENT
        assert hip_ra.OutputParameterDict['Available Heat (reservoir)'].CurrentUnits == HeatUnit.KJ
        assert hip_ra.OutputParameterDict['Producible Heat (reservoir)'].CurrentUnits == HeatUnit.KJ
        assert hip_ra.OutputParameterDict['Producible Electricity (reservoir)'].CurrentUnits == PowerUnit.MW

    def test_initialization_with_default_parameters(self):
        hip_ra: HIP_RA_X = self._new_hip_ra_test_instance()

        assert isinstance(hip_ra.reservoir_temperature, floatParameter)
        assert isinstance(hip_ra.rejection_temperature, floatParameter)
        assert isinstance(hip_ra.reservoir_porosity, floatParameter)
        assert isinstance(hip_ra.reservoir_area, floatParameter)
        assert isinstance(hip_ra.reservoir_thickness, floatParameter)
        assert isinstance(hip_ra.rock_heat_capacity, floatParameter)
        assert isinstance(hip_ra.fluid_heat_capacity, floatParameter)
        assert isinstance(hip_ra.rock_heat_capacity, floatParameter)
        assert isinstance(hip_ra.fluid_density, floatParameter)
        assert isinstance(hip_ra.rock_density, floatParameter)
        assert isinstance(hip_ra.fluid_recoverable_heat, floatParameter)

        # TODO should these be initialized?
        # assert isinstance(hip_ra.rejection_temperature_k, floatParameter)
        # assert isinstance(hip_ra.rejection_entropy, floatParameter)
        # assert isinstance(hip_ra.rejection_enthalpy, floatParameter)

        assert isinstance(hip_ra.reservoir_life_cycle, intParameter)

        assert isinstance(hip_ra.volume_recoverable_fluid, OutputParameter)
        assert isinstance(hip_ra.volume_rock, OutputParameter)
        assert isinstance(hip_ra.reservoir_volume, OutputParameter)
        assert isinstance(hip_ra.reservoir_stored_heat, OutputParameter)
        assert isinstance(hip_ra.reservoir_mass, OutputParameter)
        assert isinstance(hip_ra.reservoir_enthalpy, OutputParameter)
        assert isinstance(hip_ra.wellhead_heat, OutputParameter)
        assert isinstance(hip_ra.reservoir_recovery_factor, OutputParameter)
        assert isinstance(hip_ra.reservoir_available_heat, OutputParameter)
        assert isinstance(hip_ra.reservoir_producible_heat, OutputParameter)
        assert isinstance(hip_ra.reservoir_producible_electricity, OutputParameter)

        assert hip_ra.reservoir_thickness.value == 0.286

        assert hip_ra.reservoir_temperature.Name == 'Reservoir Temperature'
        assert hip_ra.reservoir_temperature.value == 150.0
        assert hip_ra.reservoir_temperature.Min == 50
        assert hip_ra.reservoir_temperature.Max == 1000
        assert hip_ra.reservoir_temperature.UnitType == Units.TEMPERATURE
        assert hip_ra.reservoir_temperature.PreferredUnits == TemperatureUnit.CELSIUS
        assert hip_ra.reservoir_temperature.CurrentUnits == TemperatureUnit.CELSIUS
        assert hip_ra.reservoir_temperature.Required is True
        assert hip_ra.reservoir_temperature.ErrMessage == 'assume default reservoir temperature (150 degC)'
        assert hip_ra.reservoir_temperature.ToolTipText == 'Reservoir Temperature'

        assert hip_ra.rejection_temperature.value == 25.0
        assert hip_ra.reservoir_porosity.value == 18.0
        assert hip_ra.reservoir_area.value == 81.0
        assert hip_ra.reservoir_thickness.value == 0.286
        assert hip_ra.reservoir_life_cycle.value == 30
        assert hip_ra.rock_heat_capacity.value == 2840000000000.0
        assert hip_ra.fluid_heat_capacity.value == -1.0
        assert hip_ra.fluid_density.value == -1.0
        assert hip_ra.rock_density.value == 2550000000000.0
        assert hip_ra.rock_recoverable_heat.value == -1.0
        assert hip_ra.rejection_temperature.value == 25.0

        # FIXME TODO determine if these are applicable
        # assert hip_ra.WaterContent.value == 18.0
        # assert hip_ra.RockContent.value == 82.0
        # assert hip_ra.rejection_entropy.value == 0.367
        # assert hip_ra.rejection_enthalpy.value == 104.8

    @unittest.skip(reason='FIXME: Race condition if tests are run in parallel')
    def test_logger_initialization(self):
        hip_ra = self._new_hip_ra_test_instance(enable_hip_ra_logging_config=True)
        assert hip_ra.logger.name == 'root'
        assert hip_ra.logger.level == logging.INFO
        assert hip_ra.logger.isEnabledFor(logging.INFO) is True

    def test_handling_input_file_not_found(self):
        client = HipRaClient()

        with self.assertRaises(RuntimeError) as rex:
            client.get_hip_ra_result(
                HipRaInputParameters(
                    file_path_or_params_dict=Path(tempfile.gettempdir(), f'a-non-existent-file_{uuid.uuid1()!s}.txt')
                )
            )

        self.assertIn('Unable to read input file', str(rex.exception))
        self.assertIn('.txt not found', str(rex.exception))

    def test_hip_ra_input_parameters_init(self):
        input_from_params: HipRaInputParameters = HipRaInputParameters(
            {
                'Reservoir Temperature': 250.0,
                'Rejection Temperature': 60.0,
                'Reservoir Porosity': 10.0,
                'Reservoir Area': 55.0,
                'Reservoir Thickness': 0.25,
                'Reservoir Life Cycle': 25,
            }
        )

        with open(input_from_params.as_file_path()) as f:
            input_file_contents = f.read()
            self.assertEqual(
                'Reservoir Temperature, 250.0\n'
                'Rejection Temperature, 60.0\n'
                'Reservoir Porosity, 10.0\n'
                'Reservoir Area, 55.0\n'
                'Reservoir Thickness, 0.25\n'
                'Reservoir Life Cycle, 25\n',
                input_file_contents,
            )

        with self.assertRaises(ValueError):
            HipRaInputParameters(1)

    def test_area_acre(self):
        result: HipRaResult = HipRaXClient().get_hip_ra_x_result(
            HipRaInputParameters(self._get_test_file_path('hip-ra-x-area-acres.txt'))
        )

        self.assertEqual('km**2', result.result['SUMMARY OF INPUTS']['Reservoir Area']['unit'])
        self.assertAlmostEqual(444.9, result.result['SUMMARY OF INPUTS']['Reservoir Area']['value'], places=1)

    @staticmethod
    def _new_hip_ra_test_instance(enable_hip_ra_logging_config=False, pre_re_stash_runner=None) -> HIP_RA_X:
        stash_cwd = Path.cwd()
        stash_sys_argv = sys.argv

        sys.argv = ['']

        try:
            hip_ra: HIP_RA_X = HIP_RA_X(enable_hip_ra_logging_config=enable_hip_ra_logging_config)
            if pre_re_stash_runner is not None:
                pre_re_stash_runner(hip_ra)
            return hip_ra
        finally:
            sys.argv = stash_sys_argv
            os.chdir(stash_cwd)
