from __future__ import annotations

import json
import sys
import numpy as np
from scipy.interpolate import interp1d

from .Parameter import strParameter, listParameter, floatParameter
from .Units import Units, TimeUnit, TemperatureUnit
import geophires_x.Model as Model
from .Reservoir import Reservoir


class UPPReservoir(Reservoir):
    """
    This class models the User Provided Profile Reservoir.
    """

    def __init__(self, model: Model):
        """
        The __init__ function is called automatically when a class is instantiated.
        It initializes the attributes of an object, and sets default values for certain arguments that can be overridden
        by user input.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')
        super().__init__(model)  # initialize the parent parameters and variables
        sclass = str(__class__).replace("<class \'", "")
        self.MyClass = sclass.replace("\'>", "")

        self.filenamereservoiroutput = self.ParameterDict[self.filenamereservoiroutput.Name] = strParameter(
            "Reservoir Output File Name",
            value='ReservoirOutput.txt',
            UnitType=Units.NONE,
            ErrMessage="assume default reservoir output file name (ReservoirOutput.txt)",
            ToolTipText="File name of reservoir output in case reservoir model 5 is selected",
        )

        reservoir_output_profile_param_name = 'Reservoir Output Profile'
        reservoir_output_profile_time_step_param_name = 'Reservoir Output Profile Time Step'

        self.reservoir_output_data = self.ParameterDict[self.reservoir_output_data.Name] = listParameter(
            reservoir_output_profile_param_name,
            DefaultValue=[],
            Min=0,
            Max=model.reserv.Tmax.Max,
            UnitType=Units.TEMPERATURE,
            CurrentUnits=TemperatureUnit.CELSIUS,
            PreferredUnits=TemperatureUnit.CELSIUS,
            ToolTipText=f'Temperature profile data as a comma-separated list of values in Celsius. '
            f'Example: 200,195,190,185 for a 4-point temperature decline profile. '
            f'Values are interpolated over the time range determined by the number of profile data points '
            f'and {reservoir_output_profile_time_step_param_name}. '
            f'If the profile is shorter than the plant lifetime, the temperature trend is extrapolated '
            f'based on the last ~20% of the data, with the injection temperature used as a minimum. ',
        )

        self.reservoir_output_time_step = self.ParameterDict[self.reservoir_output_time_step.Name] = floatParameter(
            reservoir_output_profile_time_step_param_name,
            DefaultValue=1.0,
            Min=0.01,
            Max=100.0,
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ToolTipText=f'Time interval between temperature values in the {reservoir_output_profile_param_name}. '
            f'For example, if set to 0.25, the profile values represent temperatures at '
            f'0, 0.25, 0.5, 0.75, 1.0 years, etc.',
        )

        model.logger.info(f'Complete {__class__!s}: {sys._getframe().f_code.co_name}')

    def __str__(self):
        return "UPPReservoir"

    def read_parameters(self, model: Model) -> None:
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')
        super().read_parameters(model)  # read the parameters for the parent.

        # Validate mutual exclusivity: user should provide either file or inline data, not both
        if self.reservoir_output_data.Provided and self.filenamereservoiroutput.Provided:
            # If both are provided, prefer inline data and log a warning
            msg = (
                "Both 'Reservoir Output Profile' and 'Reservoir Output File Name' were provided. "
                "Using 'Reservoir Output Profile' data."
            )
            print(f"Warning: {msg}")
            model.logger.warning(msg)

        model.logger.info(f'Complete {str(__class__)}: {sys._getframe().f_code.co_name}')

    def Calculate(self, model: Model):
        """
        The Calculate function calculates the values of the parameters that are calculated from other parameters.
        This includes the parameters that are calculated and then published using the Printouts function.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')
        super().Calculate(model)  # run calculations for the parent.

        model.reserv.Tresoutput.value[0] = model.reserv.Trock.value

        # Use the actual size of the Tresoutput array (set by parent Calculate)
        num_timesteps = len(model.reserv.Tresoutput.value)

        reservoir_temperatures: list[float] = self._get_reservoir_output_temperatures(model, num_timesteps)

        if len(reservoir_temperatures) != num_timesteps:
            # Shouldn't happen, but we'll log a warning if it does.
            model.logger.warning(
                f'Unexpected number of reservoir temperatures: '
                f'({len(reservoir_temperatures)}) found (expected {num_timesteps}).'
            )

        for i in range(num_timesteps):
            model.reserv.Tresoutput.value[i] = reservoir_temperatures[i]

        model.logger.info(f'Complete {str(__class__)}: {sys._getframe().f_code.co_name}')

    def _get_reservoir_output_temperatures(self, model: Model, num_timesteps: int):
        if self.reservoir_output_data.Provided and len(self.reservoir_output_data.value) > 0:
            input_times, reservoir_output_data = self._get_reservoir_output_data_from_profile_parameter(model)
        else:
            input_times, reservoir_output_data = self._get_reservoir_output_data_from_text_file(model)

        # Create target time points for the simulation
        plant_lifetime = model.surfaceplant.plant_lifetime.value
        target_time_points = np.linspace(0, plant_lifetime, num_timesteps)

        # Determine interpolation/extrapolation strategy based on input data coverage
        input_max_time = input_times[-1]

        if input_max_time >= plant_lifetime:
            # Input data covers the full simulation period - just interpolate
            interpolator = interp1d(
                input_times,
                reservoir_output_data,
                kind='linear',
                bounds_error=False,
                fill_value=(reservoir_output_data[0], reservoir_output_data[-1]),
            )
            interpolated_temps = interpolator(target_time_points)
        else:
            # Input data is shorter than plant lifetime - need to extrapolate
            msg = (
                f'Reservoir output profile data ends at year {input_max_time:.2f}, '
                f'but plant lifetime is {plant_lifetime} years. '
                f'Extrapolating temperature trend for remaining years.'
            )
            model.logger.warning(msg)
            print(f'Warning: {msg}')

            interpolated_temps = self._interpolate_and_extrapolate(
                input_times, reservoir_output_data, target_time_points, model
            )

        ret = [float(it) for it in interpolated_temps]

        return ret

    # noinspection PyMethodMayBeStatic
    def _interpolate_and_extrapolate(
        self,
        input_times: np.ndarray,
        input_temps: list[float],
        target_times: np.ndarray,
        model: Model,
    ) -> np.ndarray:
        """
        Interpolate within the input data range and extrapolate beyond it using the trend
        from the last portion of the data.
        """
        input_max_time = input_times[-1]
        result = np.zeros(len(target_times))

        # Interpolate for times within the input data range
        interpolator = interp1d(
            input_times, input_temps, kind='linear', bounds_error=False, fill_value=(input_temps[0], input_temps[-1])
        )

        first_extrapolated_index: int | None = None

        for i, t in enumerate(target_times):
            if t <= input_max_time:
                result[i] = interpolator(t)
            else:
                # Extrapolate using linear trend from the last ~20% of input data (or at least last 2 points)
                trend_start_idx = max(0, int(len(input_times) * 0.8))
                if trend_start_idx >= len(input_times) - 1:
                    trend_start_idx = max(0, len(input_times) - 2)

                trend_times = input_times[trend_start_idx:]
                trend_temps = input_temps[trend_start_idx:]

                # Calculate linear trend (slope) from the trend portion
                if len(trend_times) >= 2:
                    slope = (trend_temps[-1] - trend_temps[0]) / (trend_times[-1] - trend_times[0])
                else:
                    slope = 0.0

                # Extrapolate from the last known point
                time_beyond = t - input_max_time
                extrapolated_temp = input_temps[-1] + slope * time_beyond

                # Don't let temperature go below injection temperature
                min_temp = model.wellbores.Tinj.value
                result[i] = max(extrapolated_temp, min_temp)

                if first_extrapolated_index is None:
                    first_extrapolated_index = i

        if first_extrapolated_index is not None:
            model.logger.info(
                f'Reservoir temperature extrapolation result from trend in last ~20% of input data, starting '
                f'at time step {first_extrapolated_index}: '
                f'{json.dumps([round(it,2) for it in list(result[first_extrapolated_index:])])}.'
            )

        return result

    def _get_reservoir_output_data_from_profile_parameter(self, model: Model) -> tuple[np.ndarray, list[float]]:
        """
        Load reservoir temperature profile from inline data.
        Returns tuple of (time_points, temperatures).
        """
        temp_data = self.reservoir_output_data.value

        if len(temp_data) < 2:
            msg = (
                "Error: 'Reservoir Output Profile' must contain at least 2 temperature values "
                f"for interpolation. Got {len(temp_data)} value(s)."
            )
            model.logger.critical(msg)
            raise RuntimeError(msg)

        # Generate time points based on the time step parameter
        time_step = self.reservoir_output_time_step.value
        time_points = np.array([i * time_step for i in range(len(temp_data))])

        return time_points, [float(it) for it in temp_data]

    # noinspection PyMethodMayBeStatic
    def _get_reservoir_output_data_from_text_file(self, model: Model) -> tuple[np.ndarray, list[float]]:
        """
        Load reservoir temperature profile from file.
        Returns tuple of (time_points, temperatures).
        """
        try:
            with open(model.reserv.filenamereservoiroutput.value, encoding='UTF-8') as f:
                content_prod_temp = f.readlines()
        except Exception:
            msg = (
                f'Error: GEOPHIRES could not read reservoir output file '
                f'({model.reserv.filenamereservoiroutput.value}) and will abort simulation.'
            )
            model.logger.critical(msg)
            raise RuntimeError(msg)

        times: list[float] = []
        temps: list[float] = []

        for line in content_prod_temp:
            line = line.strip()
            if line:
                parts = line.split(',')
                if len(parts) >= 2:
                    try:
                        time_val = float(parts[0].strip())
                        temp_val = float(parts[1].strip())
                        times.append(time_val)
                        temps.append(temp_val)
                    except ValueError:
                        # Skip lines that can't be parsed (e.g., headers)
                        continue

        if len(times) < 2:
            msg = (
                f"Error: Reservoir output file ({model.reserv.filenamereservoiroutput.value}) "
                f"must contain at least 2 valid data points. Found {len(times)}."
            )
            model.logger.critical(msg)
            raise RuntimeError(msg)

        return np.array(times), temps
