from __future__ import annotations

import logging
import logging.config
import os
import sys
import traceback
from pathlib import Path
from typing import Callable
from typing import ClassVar

import pint
from rich.console import Console
from rich.table import Table

from geophires_x.GeoPHIRESUtils import RecoverableHeat
from geophires_x.GeoPHIRESUtils import UtilEff_func
from geophires_x.GeoPHIRESUtils import celsius_to_kelvin
from geophires_x.GeoPHIRESUtils import density_water_kg_per_m3
from geophires_x.GeoPHIRESUtils import enthalpy_water_kJ_per_kg
from geophires_x.GeoPHIRESUtils import entropy_water_kJ_per_kg_per_K
from geophires_x.GeoPHIRESUtils import heat_capacity_water_J_per_kg_per_K
from geophires_x.GeoPHIRESUtils import read_input_file
from geophires_x.GeoPHIRESUtils import static_pressure_MPa
from geophires_x.Parameter import ConvertOutputUnits
from geophires_x.Parameter import ConvertUnitsBack
from geophires_x.Parameter import LookupUnits
from geophires_x.Parameter import OutputParameter
from geophires_x.Parameter import Parameter
from geophires_x.Parameter import ParameterEntry
from geophires_x.Parameter import ReadParameter
from geophires_x.Parameter import boolParameter
from geophires_x.Parameter import floatParameter
from geophires_x.Parameter import intParameter
from geophires_x.Parameter import strParameter
from geophires_x.Units import AreaUnit
from geophires_x.Units import DensityUnit
from geophires_x.Units import EnthalpyUnit
from geophires_x.Units import HeatCapacityUnit
from geophires_x.Units import HeatPerUnitAreaUnit
from geophires_x.Units import HeatPerUnitVolumeUnit
from geophires_x.Units import HeatUnit
from geophires_x.Units import LengthUnit
from geophires_x.Units import MassUnit
from geophires_x.Units import PercentUnit
from geophires_x.Units import PowerPerUnitAreaUnit
from geophires_x.Units import PowerPerUnitVolumeUnit
from geophires_x.Units import PowerUnit
from geophires_x.Units import PressureUnit
from geophires_x.Units import TemperatureUnit
from geophires_x.Units import TimeUnit
from geophires_x.Units import Units
from geophires_x.Units import VolumeUnit
from hip_ra_x.grms import EconomicStatus
from hip_ra_x.grms import EstimateScenario
from hip_ra_x.grms import ProjectMaturitySubClass
from hip_ra_x.grms import ReservesStatus
from hip_ra_x.grms import ResourceClass
from hip_ra_x.grms import cumulative_category_for
from hip_ra_x.grms import resolve
from hip_ra_x.grms import validate_classification

"""
Heat in Place calculation: Muffler, P., and Raffaele Cataldi.
"Methods for regional assessment of geothermal resources."
Geothermics 7.2-4 (1978): 53-89.
and: Garg, S.K. and J. Combs. 2011.  A Reexamination of the USGS Volumetric "Heat in Place" Method.
Stanford University, 36th Workshop on Geothermal Reservoir Engineering; SGP-TR-191, 5 pp.
"""


def UpgradeSymbologyOfUnits(unit: str) -> str:
    """
    UpgradeSymbologyOfUnits is a function that takes a string that represents a unit and replaces the **2 and **3
    with the appropriate unicode characters for superscript 2 and 3, and replaces "deg" with the unicode character
    for degrees.
    :param unit: a string that represents a unit
    :return: a string that represents a unit with the appropriate unicode characters for superscript 2 and 3, and
    replaces "deg" with the unicode character for degrees.
    """
    unit = unit.replace('**2', '\u00b2').replace('**3', '\u00b3').replace('deg', '\u00b0')
    return unit


class HIP_RA_X:
    """
    HIP_RA_X is the container class of the HIP-RA-X application, giving access to everything else, including the logger
    """

    _ureg = pint.get_application_registry()

    _SUMMARY_OF_RESULTS_OUTPUT_CATEGORY: ClassVar[str] = 'SUMMARY OF RESULTS'
    _GRMS_CLASSIFICATION_OUTPUT_CATEGORY: ClassVar[str] = 'GRMS CLASSIFICATION'
    _SUMMARY_OF_INPUTS_OUTPUT_CATEGORY: ClassVar[str] = 'SUMMARY OF INPUTS'

    def __init__(self, enable_hip_ra_logging_config=True):
        # get logging started
        self.logger = logging.getLogger('root')

        if enable_hip_ra_logging_config:
            logging.config.fileConfig(Path(os.path.dirname(os.path.abspath(__file__)), 'logging.conf'))
            self.logger.setLevel(logging.INFO)

        self.logger.info(f'Init {__class__.__name__!s}: {__name__}')

        # Initiate the elements of the Model
        # Set up all the Parameters that will be predefined by this class using the different types of parameter
        # classes.  Setting up includes giving it a name, a default value, The Unit Type (length, volume,
        # temperature, etc.) and Unit Name of that value, sets it as required (or not), sets allowable range,
        # the error message if that range is exceeded, the ToolTip Text, and the name of teh class that created it.
        # This includes setting up temporary variables that will be available to all the class but noy read in by user,
        # or used for Output
        # This also includes all Parameters that are calculated and then published using the Printouts function.

        # These dictionaries contain a list of all the parameters set in this object, stored as "Parameter" and
        # "OutputParameter" Objects.  This will allow us later to access them in a user interface and get that list,
        # along with unit type, preferred units, etc.
        self.ParameterDict: dict[str, Parameter] = {}
        self.OutputParameterDict: dict[str, OutputParameter] = {}
        self.InputParameters: dict[str, ParameterEntry] = {}  # input parameters the user wants to change

        def parameter_dict_entry(param: Parameter) -> Parameter:
            self.ParameterDict[param.Name] = param
            return param

        # inputs
        self.reservoir_temperature: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Temperature',
                DefaultValue=150.0,
                Min=50,
                Max=1000,
                UnitType=Units.TEMPERATURE,
                PreferredUnits=TemperatureUnit.CELSIUS,
                CurrentUnits=TemperatureUnit.CELSIUS,
                Required=True,
                ErrMessage='assume default reservoir temperature (150 degC)',
                ToolTipText='Reservoir Temperature',
            )
        )
        self.rejection_temperature: Parameter = parameter_dict_entry(
            floatParameter(
                'Rejection Temperature',
                DefaultValue=25.0,
                Min=0.1,
                Max=200,
                UnitType=Units.TEMPERATURE,
                PreferredUnits=TemperatureUnit.CELSIUS,
                CurrentUnits=TemperatureUnit.CELSIUS,
                Required=True,
                ErrMessage='assume default rejection temperature (25 degC)',
                ToolTipText='Rejection Temperature',
            )
        )
        self.reservoir_porosity: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Porosity',
                DefaultValue=18.0,
                Min=0.0,
                Max=100.0,
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.PERCENT,
                CurrentUnits=PercentUnit.PERCENT,
                Required=True,
                ErrMessage='assume default reservoir porosity (18%)',
                ToolTipText='Reservoir Porosity',
            )
        )
        self.reservoir_area: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Area',
                DefaultValue=81.0,
                Min=0.0,
                Max=10000.0,
                UnitType=Units.AREA,
                PreferredUnits=AreaUnit.KILOMETERS2,
                CurrentUnits=AreaUnit.KILOMETERS2,
                Required=True,
                ErrMessage='assume default reservoir area (81 km2)',
                ToolTipText='Reservoir Area',
            )
        )
        self.reservoir_thickness: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Thickness',
                DefaultValue=0.286,
                Min=0.0,
                Max=10000.0,
                UnitType=Units.LENGTH,
                PreferredUnits=LengthUnit.KILOMETERS,
                CurrentUnits=LengthUnit.KILOMETERS,
                Required=True,
                ErrMessage='assume default reservoir thickness (0.286 km2)',
                ToolTipText='Reservoir Thickness',
            )
        )
        self.reservoir_life_cycle: Parameter = parameter_dict_entry(
            intParameter(
                'Reservoir Life Cycle',
                DefaultValue=30,
                UnitType=Units.TIME,
                PreferredUnits=TimeUnit.YEAR,
                CurrentUnits=TimeUnit.YEAR,
                AllowableRange=list(range(1, 101, 1)),
                Required=True,
                ErrMessage='assume default Reservoir Life Cycle (25 years)',
                ToolTipText='Reservoir Life Cycle',
            )
        )

        # user-changeable semi-constants
        self.rock_heat_capacity: Parameter = parameter_dict_entry(
            floatParameter(
                'Rock Heat Capacity',
                DefaultValue=2.84e12,
                Min=0.0,
                Max=1e14,
                UnitType=Units.HEAT_CAPACITY,
                PreferredUnits=HeatCapacityUnit.KJPERKM3C,
                CurrentUnits=HeatCapacityUnit.KJPERKM3C,
                Required=True,
                ErrMessage='assume default Rock Heat Capacity (2.84E+12 kJ/km3C)',
                ToolTipText='Rock Heat Capacity',
            )
        )
        self.fluid_heat_capacity: Parameter = parameter_dict_entry(
            floatParameter(
                'Fluid Specific Heat Capacity',
                DefaultValue=-1.0,
                Min=3.0,
                Max=10.0,
                UnitType=Units.HEAT_CAPACITY,
                PreferredUnits=HeatCapacityUnit.kJPERKGC,
                CurrentUnits=HeatCapacityUnit.kJPERKGC,
                Required=True,
                ErrMessage='calculate a value based on the water temperature',
                ToolTipText='Specific Heat Capacity Of Water',
            )
        )
        self.fluid_density: Parameter = parameter_dict_entry(
            floatParameter(
                'Density Of Reservoir Fluid',
                DefaultValue=-1.0,
                Min=1.000e11,
                Max=1.000e13,
                UnitType=Units.DENSITY,
                PreferredUnits=DensityUnit.KGPERKILOMETERS3,
                CurrentUnits=DensityUnit.KGPERKILOMETERS3,
                Required=True,
                ErrMessage='calculate a value based on the water temperature',
                ToolTipText='Density Of Water',
            )
        )
        self.rock_density: Parameter = parameter_dict_entry(
            floatParameter(
                'Density Of Reservoir Rock',
                DefaultValue=2.55e12,
                Min=1.000e11,
                Max=1.000e13,
                UnitType=Units.DENSITY,
                PreferredUnits=DensityUnit.KGPERKILOMETERS3,
                CurrentUnits=DensityUnit.KGPERKILOMETERS3,
                Required=True,
                ErrMessage='assume default Density Of Rock (2.55E+12 kg/km3)',
                ToolTipText='Density Of Rock',
            )
        )
        self.rock_recoverable_heat: Parameter = parameter_dict_entry(
            floatParameter(
                'Rock Recoverable Heat',
                DefaultValue=-1.0,
                Min=0.0,
                Max=1.000,
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.TENTH,
                CurrentUnits=PercentUnit.TENTH,
                Required=False,
                ErrMessage='assume 0.66 for high-T reservoirs (>150C), 0.43 for low-T reservoirs '
                '(>90, Garg and Combs (2011)',
                ToolTipText='percent of heat that is recoverable from the rock in the reservoir 0.66 for high-T reservoirs, '
                '0.43 for low-T reservoirs (Garg and Combs (2011)',
            )
        )
        self.fluid_recoverable_heat: Parameter = parameter_dict_entry(
            floatParameter(
                'Fluid Recoverable Heat',
                DefaultValue=-1.0,
                Min=0.00,
                Max=1.000,
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.TENTH,
                CurrentUnits=PercentUnit.TENTH,
                Required=False,
                ErrMessage='assume 0.66 for high-T reservoirs (>150C), 0.43 for low-T reservoirs '
                '(>90, Garg and Combs (2011)',
                ToolTipText='percent of heat that is recoverable from the fluid in the reservoir 0.66 for high-T reservoirs, '
                '0.43 for low-T reservoirs (Garg and Combs (2011)',
            )
        )
        self.recoverable_fluid_factor: Parameter = parameter_dict_entry(
            floatParameter(
                'Recoverable Fluid Factor',
                DefaultValue=0.5,
                Min=0.00,
                Max=1.000,
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.TENTH,
                CurrentUnits=PercentUnit.TENTH,
                Required=False,
                ErrMessage='assume 0.5 (50%) of fluid from the reservoir is recoverable',
                ToolTipText='percent of fluid that is recoverable from the reservoir (0.5 = 50%)',
            )
        )
        self.reservoir_depth: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Depth',
                DefaultValue=-1.0,
                Min=0.001,
                Max=15.0,
                UnitType=Units.LENGTH,
                PreferredUnits=LengthUnit.KILOMETERS,
                CurrentUnits=LengthUnit.KILOMETERS,
                Required=False,
                Provided=False,
                ErrMessage='calculate based on an assumed gradient of 30 C/km and the reservoir temperature',
                ToolTipText='depth to top of reservoir (km). Calculated based on an assumed gradient '
                'and the reservoir temperature if no value given',
            )
        )
        self.reservoir_pressure: Parameter = parameter_dict_entry(
            floatParameter(
                'Reservoir Pressure',
                DefaultValue=-1.0,
                Min=0.00,
                Max=10000.000,
                UnitType=Units.PRESSURE,
                PreferredUnits=PressureUnit.MPASCAL,
                CurrentUnits=PressureUnit.MPASCAL,
                Required=False,
                Provided=False,
                ErrMessage='calculate assuming hydrostatic pressure and the reservoir depth & water density',
                ToolTipText='pressure of the of reservoir (in MPa). Calculated assuming hydrostatic pressure and '
                'reservoir depth & water density if no value given',
            )
        )
        self.recoverable_rock_heat: Parameter = parameter_dict_entry(
            floatParameter(
                'Recoverable Heat from Rock',
                DefaultValue=0.75,
                Min=0.00,
                Max=1.000,
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.TENTH,
                CurrentUnits=PercentUnit.TENTH,
                Required=False,
                ErrMessage='assume 0.75 (75%) of fluid from the reservoir is recoverable',
                ToolTipText='percent of heat that is recoverable from the rock (0.75 = 75%)',
            )
        )
        self.html_output_file: Parameter = parameter_dict_entry(
            strParameter(
                'HTML Output File',
                DefaultValue='HIP.html',
                Required=False,
                Provided=False,
                ErrMessage='assume no HTML output',
                ToolTipText='Provide a HTML output name if you want to have HTML output (no output if not provided)',
            )
        )

        self.print_output_to_console = parameter_dict_entry(
            boolParameter(
                'Print Output to Console',
                DefaultValue=True,
                UnitType=Units.NONE,
                ToolTipText='Provide False if you do not want to print output to the console',
            )
        )

        # GRMS classification designations. All optional; declaring none leaves
        # the case report unchanged. Each accepts a name or an integer code.
        self.grms_resource_class = parameter_dict_entry(
            strParameter(
                'GRMS Resource Class',
                DefaultValue='',
                Required=False,
                Provided=False,
                ErrMessage='assume no GRMS classification',
                ToolTipText='GRMS commercial maturity: Prospective Resources, Contingent Resources '
                'or Reserves. Required for any other GRMS designation to be reported.',
            )
        )
        self.grms_estimate_scenario = parameter_dict_entry(
            strParameter(
                'GRMS Estimate Scenario',
                DefaultValue='',
                Required=False,
                Provided=False,
                ErrMessage='assume no GRMS estimate scenario',
                ToolTipText='Which estimate this evaluation represents: Low Estimate, Best Estimate '
                'or High Estimate. Combined with GRMS Resource Class this gives the cumulative '
                'category (for example Best Estimate of Reserves is 2P).',
            )
        )
        self.grms_project_maturity_sub_class = parameter_dict_entry(
            strParameter(
                'GRMS Project Maturity Sub-Class',
                DefaultValue='',
                Required=False,
                Provided=False,
                ErrMessage='assume no GRMS project maturity sub-class',
                ToolTipText='GRMS project maturity sub-class, such as On Production, Development '
                'Pending or Prospect. Must belong to the declared GRMS Resource Class.',
            )
        )
        self.grms_reserves_status = parameter_dict_entry(
            strParameter(
                'GRMS Reserves Status',
                DefaultValue='',
                Required=False,
                Provided=False,
                ErrMessage='assume no GRMS reserves status',
                ToolTipText='Development and production status, such as Developed Producing or '
                'Undeveloped. Resources other than Reserves are undeveloped.',
            )
        )
        self.grms_economic_status = parameter_dict_entry(
            strParameter(
                'GRMS Economic Status',
                DefaultValue='',
                Required=False,
                Provided=False,
                ErrMessage='assume no GRMS economic status',
                ToolTipText='Economic status of Contingent Resources: Economically Viable, '
                'Economically Not Viable or Undetermined.',
            )
        )

        # Output parameters
        self.reservoir_volume = self.OutputParameterDict[self.reservoir_volume.Name] = OutputParameter(
            Name='Reservoir Volume (reservoir)',
            UnitType=Units.VOLUME,
            PreferredUnits=VolumeUnit.KILOMETERS3,
            CurrentUnits=VolumeUnit.KILOMETERS3,
        )
        self.volume_rock = self.OutputParameterDict[self.volume_rock.Name] = OutputParameter(
            Name='Reservoir Volume (rock)',
            UnitType=Units.VOLUME,
            PreferredUnits=VolumeUnit.KILOMETERS3,
            CurrentUnits=VolumeUnit.KILOMETERS3,
        )
        self.volume_recoverable_fluid = self.OutputParameterDict[self.volume_recoverable_fluid.Name] = OutputParameter(
            Name='Recoverable Volume (recoverable fluid)',
            UnitType=Units.VOLUME,
            PreferredUnits=VolumeUnit.KILOMETERS3,
            CurrentUnits=VolumeUnit.KILOMETERS3,
        )
        self.reservoir_stored_heat = self.OutputParameterDict[self.reservoir_stored_heat.Name] = OutputParameter(
            Name='Stored Heat (reservoir)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.stored_heat_rock = self.OutputParameterDict[self.stored_heat_rock.Name] = OutputParameter(
            Name='Stored Heat (rock)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.stored_heat_fluid = self.OutputParameterDict[self.stored_heat_fluid.Name] = OutputParameter(
            Name='Stored Heat (fluid)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.reservoir_mass = self.OutputParameterDict[self.reservoir_mass.Name] = OutputParameter(
            Name='Mass of Reservoir (total)',
            UnitType=Units.MASS,
            PreferredUnits=MassUnit.KILOGRAM,
            CurrentUnits=MassUnit.KILOGRAM,
        )
        self.mass_rock = self.OutputParameterDict[self.mass_rock.Name] = OutputParameter(
            Name='Mass of Reservoir (rock)',
            UnitType=Units.MASS,
            PreferredUnits=MassUnit.KILOGRAM,
            CurrentUnits=MassUnit.KILOGRAM,
        )
        self.mass_recoverable_fluid = self.OutputParameterDict[self.mass_recoverable_fluid.Name] = OutputParameter(
            Name='Mass of Reservoir (fluid)',
            UnitType=Units.MASS,
            PreferredUnits=MassUnit.KILOGRAM,
            CurrentUnits=MassUnit.KILOGRAM,
        )
        self.reservoir_enthalpy = self.OutputParameterDict[self.reservoir_enthalpy.Name] = OutputParameter(
            Name='Specific Enthalpy (reservoir)',
            UnitType=Units.ENTHALPY,
            PreferredUnits=EnthalpyUnit.KJPERKG,
            CurrentUnits=EnthalpyUnit.KJPERKG,
        )
        self.enthalpy_rock = self.OutputParameterDict[self.enthalpy_rock.Name] = OutputParameter(
            Name='Specific Enthalpy (rock)',
            UnitType=Units.ENTHALPY,
            PreferredUnits=EnthalpyUnit.KJPERKG,
            CurrentUnits=EnthalpyUnit.KJPERKG,
        )
        self.enthalpy_fluid = self.OutputParameterDict[self.enthalpy_fluid.Name] = OutputParameter(
            Name='Specific Enthalpy (fluid)',
            UnitType=Units.ENTHALPY,
            PreferredUnits=EnthalpyUnit.KJPERKG,
            CurrentUnits=EnthalpyUnit.KJPERKG,
        )
        self.wellhead_heat = self.OutputParameterDict[self.wellhead_heat.Name] = OutputParameter(
            Name='Wellhead Heat (reservoir)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.wellhead_heat_recovery_rock = self.OutputParameterDict[self.wellhead_heat_recovery_rock.Name] = (
            OutputParameter(
                Name='Wellhead Heat (rock)',
                UnitType=Units.HEAT,
                PreferredUnits=HeatUnit.KJ,
                CurrentUnits=HeatUnit.KJ,
            )
        )
        self.wellhead_heat_recovery_fluid = self.OutputParameterDict[self.wellhead_heat_recovery_fluid.Name] = (
            OutputParameter(
                Name='Wellhead Heat (fluid)',
                UnitType=Units.HEAT,
                PreferredUnits=HeatUnit.KJ,
                CurrentUnits=HeatUnit.KJ,
            )
        )
        self.reservoir_recovery_factor = self.OutputParameterDict[self.reservoir_recovery_factor.Name] = (
            OutputParameter(
                Name='Recovery Factor (reservoir)',
                UnitType=Units.PERCENT,
                PreferredUnits=PercentUnit.PERCENT,
                CurrentUnits=PercentUnit.PERCENT,
            )
        )
        self.recovery_factor_rock = self.OutputParameterDict[self.recovery_factor_rock.Name] = OutputParameter(
            Name='Recovery Factor (rock)',
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
        )
        self.recovery_factor_fluid = self.OutputParameterDict[self.recovery_factor_fluid.Name] = OutputParameter(
            Name='Recovery Factor (fluid)',
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
        )
        self.reservoir_available_heat = self.OutputParameterDict[self.reservoir_available_heat.Name] = OutputParameter(
            Name='Available Heat (reservoir)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.available_heat_rock = self.OutputParameterDict[self.available_heat_rock.Name] = OutputParameter(
            Name='Available Heat (rock)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.available_heat_fluid = self.OutputParameterDict[self.available_heat_fluid.Name] = OutputParameter(
            Name='Available Heat (fluid)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.reservoir_producible_heat = self.OutputParameterDict[self.reservoir_producible_heat.Name] = (
            OutputParameter(
                Name='Producible Heat (reservoir)',
                UnitType=Units.HEAT,
                PreferredUnits=HeatUnit.KJ,
                CurrentUnits=HeatUnit.KJ,
            )
        )
        self.producible_heat_rock = self.OutputParameterDict[self.producible_heat_rock.Name] = OutputParameter(
            Name='Producible Heat (rock)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.producible_heat_fluid = self.OutputParameterDict[self.producible_heat_fluid.Name] = OutputParameter(
            Name='Producible Heat (fluid)',
            UnitType=Units.HEAT,
            PreferredUnits=HeatUnit.KJ,
            CurrentUnits=HeatUnit.KJ,
        )
        self.reservoir_producible_electricity = self.OutputParameterDict[self.reservoir_producible_electricity.Name] = (
            OutputParameter(
                Name='Producible Electricity (reservoir)',
                UnitType=Units.POWER,
                PreferredUnits=PowerUnit.MW,
                CurrentUnits=PowerUnit.MW,
            )
        )
        self.producible_electricity_rock = self.OutputParameterDict[self.producible_electricity_rock.Name] = (
            OutputParameter(
                Name='Producible Electricity (rock)',
                UnitType=Units.POWER,
                PreferredUnits=PowerUnit.MW,
                CurrentUnits=PowerUnit.MW,
            )
        )
        self.producible_electricity_fluid = self.OutputParameterDict[self.producible_electricity_fluid.Name] = (
            OutputParameter(
                Name='Producible Electricity (fluid)',
                UnitType=Units.POWER,
                PreferredUnits=PowerUnit.MW,
                CurrentUnits=PowerUnit.MW,
            )
        )
        self.producible_heat_per_unit_area = self.OutputParameterDict[self.producible_heat_per_unit_area.Name] = (
            OutputParameter(
                Name='Producible Heat/Unit Area (reservoir)',
                UnitType=Units.HEATPERUNITAREA,
                PreferredUnits=HeatPerUnitAreaUnit.KJPERSQKM,
                CurrentUnits=HeatPerUnitAreaUnit.KJPERSQKM,
            )
        )
        self.heat_per_unit_area_rock = self.OutputParameterDict[self.heat_per_unit_area_rock.Name] = OutputParameter(
            Name='Producible Heat/Unit Area (rock)',
            UnitType=Units.HEATPERUNITAREA,
            PreferredUnits=HeatPerUnitAreaUnit.KJPERSQKM,
            CurrentUnits=HeatPerUnitAreaUnit.KJPERSQKM,
        )
        self.heat_per_unit_area_fluid = self.OutputParameterDict[self.heat_per_unit_area_fluid.Name] = OutputParameter(
            Name='Producible Heat/Unit Area (fluid)',
            UnitType=Units.HEATPERUNITAREA,
            PreferredUnits=HeatPerUnitAreaUnit.KJPERSQKM,
            CurrentUnits=HeatPerUnitAreaUnit.KJPERSQKM,
        )
        self.heat_per_unit_volume_reservoir = self.OutputParameterDict[self.heat_per_unit_volume_reservoir.Name] = (
            OutputParameter(
                Name='Producible Heat/Unit Volume (reservoir)',
                UnitType=Units.HEATPERUNITVOLUME,
                PreferredUnits=HeatPerUnitVolumeUnit.KJPERCUBICKM,
                CurrentUnits=HeatPerUnitVolumeUnit.KJPERCUBICKM,
            )
        )
        self.producible_electricity_per_unit_area = self.OutputParameterDict[
            self.producible_electricity_per_unit_area.Name
        ] = OutputParameter(
            Name='Producible Electricity/Unit Area (reservoir)',
            UnitType=Units.POWERPERUNITAREA,
            PreferredUnits=PowerPerUnitAreaUnit.MWPERSQKM,
            CurrentUnits=PowerPerUnitAreaUnit.MWPERSQKM,
        )
        self.electricity_per_unit_area_rock = self.OutputParameterDict[self.electricity_per_unit_area_rock.Name] = (
            OutputParameter(
                Name='Producible Electricity/Unit Area (rock)',
                UnitType=Units.POWERPERUNITAREA,
                PreferredUnits=PowerPerUnitAreaUnit.MWPERSQKM,
                CurrentUnits=PowerPerUnitAreaUnit.MWPERSQKM,
            )
        )
        self.electricity_per_unit_area_fluid = self.OutputParameterDict[self.electricity_per_unit_area_fluid.Name] = (
            OutputParameter(
                Name='Producible Electricity/Unit Area (fluid)',
                UnitType=Units.POWERPERUNITAREA,
                PreferredUnits=PowerPerUnitAreaUnit.MWPERSQKM,
                CurrentUnits=PowerPerUnitAreaUnit.MWPERSQKM,
            )
        )
        self.electricity_per_unit_volume_reservoir = self.OutputParameterDict[
            self.electricity_per_unit_volume_reservoir.Name
        ] = OutputParameter(
            Name='Producible Electricity/Unit Volume (reservoir)',
            UnitType=Units.POWERPERUNITVOLUME,
            PreferredUnits=PowerPerUnitVolumeUnit.MWPERCUBICKM,
            CurrentUnits=PowerPerUnitVolumeUnit.MWPERCUBICKM,
        )

        self.logger.info(f'Complete {__class__.__name__!s}: {__name__}')

    def read_parameters(self, suppress_input_sys_argv_warnings=False) -> None:
        """
        The read_parameters function reads in the parameters from a dictionary created by reading the user-provided file
        and updates the parameter values for this object.

        The function reads in all the parameters that relate to this object, including those that are inherited
        from other objects. It then updates any of these parameter values that have been changed by the user.
        It also handles any special cases.
        """
        self.logger.info(f'Init {__class__.__name__!s}: {__name__}')

        read_input_file(
            self.InputParameters, logger=self.logger, suppress_input_sys_argv_warnings=suppress_input_sys_argv_warnings
        )

        if len(self.InputParameters) > 0:
            for item in self.ParameterDict.items():
                ParameterToModify = item[1]
                key = ParameterToModify.Name.strip()
                if key in self.InputParameters:
                    ParameterReadIn = self.InputParameters[key]

                    # this should handle all the non-special cases
                    ReadParameter(ParameterReadIn, ParameterToModify, self)
        else:
            self.logger.info('No parameters read because no content provided')

        # loop through all the parameters that the user wishes to set, looking for parameters that contain
        # the prefix "Units:" - that means we want to set a special case for converting this output parameter
        # to new units
        for key in self.InputParameters.keys():
            if key.startswith('Units:'):
                self.OutputParameterDict[key.replace('Units:', '')].CurrentUnits = LookupUnits(
                    self.InputParameters[key].sValue
                )[0]

        self._grms_classification = self._resolve_grms_classification()

        self.logger.info(f'complete {__class__.__name__!s}: {__name__}')

    def _resolve_grms_classification(self) -> dict[str, str]:
        """
        Resolve and validate the GRMS designations the user declared.

        :return: display names keyed by report field name; empty if the user
            declared no GRMS Resource Class.
        :raises ValueError: if a designation is unrecognized or the declared
            designations are mutually inconsistent.
        """

        if not self.grms_resource_class.Provided or not str(self.grms_resource_class.value).strip():
            return {}

        resource_class = resolve(ResourceClass, self.grms_resource_class.value)

        def _declared(param, enum_cls):
            if not param.Provided or not str(param.value).strip():
                return None
            return resolve(enum_cls, param.value)

        estimate_scenario = _declared(self.grms_estimate_scenario, EstimateScenario)
        sub_class = _declared(self.grms_project_maturity_sub_class, ProjectMaturitySubClass)
        reserves_status = _declared(self.grms_reserves_status, ReservesStatus)
        economic_status = _declared(self.grms_economic_status, EconomicStatus)

        validate_classification(
            resource_class,
            sub_class=sub_class,
            reserves_status=reserves_status,
            economic_status=economic_status,
        )

        classification = {'Resource Class': resource_class.value}

        if estimate_scenario is not None:
            cumulative = cumulative_category_for(resource_class, estimate_scenario)
            classification['Estimate Scenario'] = estimate_scenario.value
            classification['Cumulative Category'] = cumulative.value

        if sub_class is not None:
            classification['Project Maturity Sub-Class'] = sub_class.value

        if reserves_status is not None:
            classification['Reserves Status'] = reserves_status.value

        if economic_status is not None:
            classification['Economic Status'] = economic_status.value

        return classification

    def Calculate(self):
        self.logger.info(f'Init {__class__!s}: {__class__.__name__!s}: {__name__}')

        try:
            # Calculate the volume of rock and fluid in the reservoir.
            self.reservoir_volume.value = self.reservoir_area.value * self.reservoir_thickness.value
            self.volume_rock.value = self.reservoir_volume.value * (1.0 - (self.reservoir_porosity.value / 100.0))

            # Note that we can't recover all the fluid from the reservoir, so we multiply by the recoverable fluid factor
            self.volume_recoverable_fluid.value = (
                self.reservoir_volume.value
                * (self.reservoir_porosity.value / 100.0)
                * self.recoverable_fluid_factor.value
            )

            if not self.reservoir_depth.Provided:
                self.logger.info(
                    f'Deriving value of {self.reservoir_depth.Name} because provided value '
                    f'({self.reservoir_depth.value}) was not provided)'
                )
                # assume ambient Temperature of 15 C and 30C/km
                self.reservoir_depth.value = (self.reservoir_temperature.value - 15.0) / 30.0

            if not self.reservoir_pressure.Provided:
                self.logger.info(
                    f'Deriving value of {self.reservoir_pressure.Name} because provided value '
                    f'({self.reservoir_pressure.value}) was not provided)'
                )
                # Assumes a water density of 1.0 g/cm3, which is high, since the water density decreases with depth
                self.reservoir_pressure.value = static_pressure_MPa(1000.0, self.reservoir_depth.value * 1000.0)

            if self.fluid_density.value < self.fluid_density.Min:
                self.logger.info(
                    f'Deriving value of {self.fluid_density.Name} because provided value '
                    f'({self.fluid_density.value}) was less than min ({self.fluid_density.Min})'
                )

                density_h20_kg_per_m3 = density_water_kg_per_m3(
                    self.reservoir_temperature.value,
                    pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa'),
                )
                self.fluid_density.value = density_h20_kg_per_m3 * 1_000_000_000.0  # converted to kg/km3

            self.mass_rock.value = self.volume_rock.value * self.rock_density.value
            self.mass_recoverable_fluid.value = self.volume_recoverable_fluid.value * self.fluid_density.value
            self.reservoir_mass.value = self.mass_rock.value + self.mass_recoverable_fluid.value

            if self.fluid_heat_capacity.value < self.fluid_heat_capacity.Min:
                self.logger.info(
                    f'Deriving value of {self.fluid_heat_capacity.Name} because provided value '
                    f'({self.fluid_heat_capacity.value}) was less than min ({self.fluid_heat_capacity.Min})'
                )

                # converted to kJ/(kg·K)
                self.fluid_heat_capacity.value = (
                    heat_capacity_water_J_per_kg_per_K(
                        self.reservoir_temperature.value,
                        pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa'),
                    )
                    / 1000.0
                )

            rejection_temperature_k = celsius_to_kelvin(self.rejection_temperature.value)
            reservoir_temperature_k = celsius_to_kelvin(self.reservoir_temperature.value)
            delta_temperature_k = reservoir_temperature_k - rejection_temperature_k
            fluid_net_enthalpy = enthalpy_water_kJ_per_kg(
                self.reservoir_temperature.value, pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa')
            ) - enthalpy_water_kJ_per_kg(
                self.rejection_temperature.value, pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa')
            )
            fluid_net_entropy = entropy_water_kJ_per_kg_per_K(
                self.reservoir_temperature.value, pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa')
            ) - entropy_water_kJ_per_kg_per_K(
                self.rejection_temperature.value, pressure=HIP_RA_X._ureg.Quantity(self.reservoir_pressure.value, 'MPa')
            )

            # fmt: off
            self.enthalpy_rock.value = ((self.rock_heat_capacity.value * delta_temperature_k * self.volume_rock.value) /
                                        self.mass_rock.value)
            # fmt: on

            # result in kJ
            self.stored_heat_rock.value = (
                self.recoverable_rock_heat.value * self.enthalpy_rock.value * self.mass_rock.value
            )
            self.stored_heat_fluid.value = fluid_net_enthalpy * self.mass_recoverable_fluid.value
            self.reservoir_stored_heat.value = self.stored_heat_rock.value + self.stored_heat_fluid.value

            # equation 4 in Garg and Combs(2011)
            amount_fluid_produced_kg = self.reservoir_stored_heat.value / fluid_net_enthalpy
            self.mass_recoverable_fluid.value = amount_fluid_produced_kg

            # equation 7 in Garg and Combs(2011)
            fluid_exergy_kJ_per_kg = (
                fluid_net_enthalpy - celsius_to_kelvin(self.rejection_temperature.value) * fluid_net_entropy
            )
            self.enthalpy_fluid.value = fluid_exergy_kJ_per_kg
            self.reservoir_enthalpy.value = self.enthalpy_rock.value + self.enthalpy_fluid.value

            # (equation 8 in Garg and Combs(2011))
            maximum_lifetime_electricity_kJ = amount_fluid_produced_kg * fluid_exergy_kJ_per_kg
            self.reservoir_available_heat.value = maximum_lifetime_electricity_kJ

            # (with conversion efficiency obtained from the function “RecoverableHeat” [however, note that I find
            # RecoverableHeat a confusing name as it represents the amount of exergy that can be converted to
            # electricity with a power plant not the amount of heat that can be recovered. See figure 2 in this
            # paper: https://geothermal-energy-journal.springeropen.com/articles/10.1186/s40517-019-0119-6
            # which is the basis for the “RecoverableHeat” function. They also call this property
            # utilization_efficiency or 2nd law based efficiency)
            conversion_efficiency = RecoverableHeat(self.reservoir_temperature.value)
            producible_lifetime_electricity_kJ = maximum_lifetime_electricity_kJ * conversion_efficiency
            self.reservoir_producible_heat.value = producible_lifetime_electricity_kJ

            self.reservoir_recovery_factor.value = (
                self.reservoir_producible_heat.value / self.reservoir_stored_heat.value
            )

            maximum_power_kW = maximum_lifetime_electricity_kJ / (self.reservoir_life_cycle.value * 365 * 24 * 3600)

            electricity_with_actual_power_plant_kW = UtilEff_func(self.reservoir_temperature.value) * maximum_power_kW
            producible_power_kW = electricity_with_actual_power_plant_kW
            self.reservoir_producible_electricity.value = (
                HIP_RA_X._ureg.Quantity(producible_power_kW, 'kW').to('MW').magnitude
            )

            self.electricity_per_unit_area_fluid.value = (
                self.producible_electricity_fluid.value / self.reservoir_area.value
            )
            self.producible_electricity_per_unit_area.value = (
                self.reservoir_producible_electricity.value / self.reservoir_area.value
            )
            self.electricity_per_unit_volume_reservoir.value = (
                self.reservoir_producible_electricity.value / self.reservoir_volume.value
            )

            self.producible_heat_per_unit_area.value = self.reservoir_producible_heat.value / self.reservoir_area.value
            self.heat_per_unit_volume_reservoir.value = (
                self.reservoir_producible_heat.value / self.reservoir_volume.value
            )

            self.logger.info(f'Complete {__class__!s}: {__class__.__name__!s}: {__name__}')
        except Exception as e:
            msg = f'Error occurred during calculations: {e!s}'
            self.logger.error(msg)
            traceback.print_exc()

            raise RuntimeError(msg) from e

    def PrintOutputs(self):
        """
        PrintOutputs writes the standard outputs to the output file.
        """
        self.logger.info(f'Init {__class__.__name__!s}: {__name__}')

        # Deal with converting Units back to PreferredUnits, if required.
        # before we write the outputs, we go through all the parameters for all the objects and set the values back
        # to the units that the user entered the data in
        # We do this because the value may be displayed in the output, and we want the user to recognize their value,
        # not some converted value
        for key in self.ParameterDict:
            param = self.ParameterDict[key]
            if not param.UnitsMatch:
                ConvertUnitsBack(param, self)

        # now we need to loop through all the output parameters to update their units to whatever
        # units the user has specified.
        # i.e., they may have specified that all LENGTH results must be in feet, so we need to convert those from
        # whatever LENGTH unit they are to feet.
        # same for all the other classes of units (TEMPERATURE, DENSITY, etc).
        for key in self.OutputParameterDict:
            if not self.OutputParameterDict[key].UnitsMatch:
                ConvertOutputUnits(self.OutputParameterDict[key], self.OutputParameterDict[key].CurrentUnits, self)

        # ---------------------------------------
        # write results to output file and screen
        # ---------------------------------------
        try:
            outputfile = 'HIP.out' if len(sys.argv) <= 2 else sys.argv[2]

            def render_default(p: Parameter) -> str:
                return f'{p.value:10.2f} {p.CurrentUnits.value}'

            def render_scientific(p: Parameter) -> str:
                return f'{p.value:10.2e} {p.CurrentUnits.value}'

            summary_of_inputs = {}
            summary_of_results = {}

            inputs = self._get_output_config_for_summary_of_inputs_category(render_default, render_scientific)
            # If depth and/or pressure are provided, report them as inputs. If not, as outputs
            if not self.reservoir_depth.Provided:
                reservoir_depth_idx = [it[0].Name for it in inputs].index(self.reservoir_depth.Name)
                inputs.pop(reservoir_depth_idx)

            if not self.reservoir_pressure.Provided:
                reservoir_pressure_idx = [it[0].Name for it in inputs].index(self.reservoir_pressure.Name)
                inputs.pop(reservoir_pressure_idx)

            for param, render in inputs:
                summary_of_inputs[param.Name] = render(param)

            case_data_inputs = {self._SUMMARY_OF_INPUTS_OUTPUT_CATEGORY: summary_of_inputs}

            outputs = self._get_output_config_for_summary_of_results_category(render_default, render_scientific)

            # If depth and/or pressure are provided, report them as inputs. If not, as outputs
            if self.reservoir_depth.Provided:
                reservoir_depth_idx = [it[0].Name for it in outputs].index(self.reservoir_depth.Name)
                outputs.pop(reservoir_depth_idx)
            if self.reservoir_pressure.Provided:
                reservoir_pressure_idx = [it[0].Name for it in outputs].index(self.reservoir_pressure.Name)
                outputs.pop(reservoir_pressure_idx)

            for param, render in outputs:
                summary_of_results[param.Name] = render(param)

            case_data_results = {self._SUMMARY_OF_RESULTS_OUTPUT_CATEGORY: summary_of_results}

            grms_classification = getattr(self, '_grms_classification', None) or {}

            with open(outputfile, 'w', encoding='UTF-8') as f:
                nl = '\n'

                f.write(f'                               *********************{nl}')
                f.write(f'                               ***HIP CASE REPORT***{nl}')
                f.write(f'                               *********************{nl}')
                f.write(nl)
                f.write(f'      ***{self._SUMMARY_OF_INPUTS_OUTPUT_CATEGORY}***{nl}')

                for k, v in case_data_inputs[self._SUMMARY_OF_INPUTS_OUTPUT_CATEGORY].items():
                    # align space between value and units to same column
                    kv_spaces = max(1, (24 - (len(v.split(' ')[0]) + len(k)))) * ' '

                    f.write(f'      {k}:{kv_spaces}{v}{nl}')

                f.write(nl)
                f.write(f'      ***{self._SUMMARY_OF_RESULTS_OUTPUT_CATEGORY}***{nl}')
                for k, v in case_data_results[self._SUMMARY_OF_RESULTS_OUTPUT_CATEGORY].items():
                    # align space between value and units to same column
                    kv_spaces = max(1, (24 - (len(v.split(' ')[0]) + len(k)))) * ' '

                    f.write(f'      {k}:{kv_spaces}{v}{nl}')

                if grms_classification:
                    f.write(nl)
                    f.write(f'      ***{self._GRMS_CLASSIFICATION_OUTPUT_CATEGORY}***{nl}')
                    for k, v in grms_classification.items():
                        # Values are text, so align them at a fixed column rather
                        # than by the width of a leading number.
                        kv_spaces = max(1, 30 - len(k)) * ' '
                        f.write(f'      {k}:{kv_spaces}{v}{nl}')

        except FileNotFoundError as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

        except PermissionError as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

        except Exception as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

        if self.html_output_file.Provided:
            # write the outputs to the output file as HTML and the screen as a table
            self.PrintOutputsHTML(case_data_inputs, case_data_results, self.html_output_file.value)
        elif self.print_output_to_console.value:
            # copy the output file to the screen
            with open(outputfile, encoding='UTF-8') as f:
                content = f.readlines()  # store all output in one long list

                # Now write each line to the screen
                for line in content:
                    sys.stdout.write(line)

    def _get_output_config_for_summary_of_inputs_category(
        self, render_default: Callable[[Parameter], str], render_scientific: Callable[[Parameter], str]
    ) -> list[tuple[Parameter, Callable[[Parameter], str]]]:
        return [
            (self.reservoir_temperature, render_default),
            (self.rejection_temperature, render_default),
            (self.reservoir_porosity, render_default),
            (self.reservoir_area, render_default),
            (self.reservoir_thickness, render_default),
            (self.reservoir_life_cycle, render_default),
            (self.rock_heat_capacity, render_scientific),
            (self.fluid_heat_capacity, render_default),
            (self.fluid_density, render_scientific),
            (self.rock_density, render_scientific),
            (self.recoverable_fluid_factor, render_default),
            (self.recoverable_rock_heat, render_default),
            # Note: If depth and/or pressure are provided, they are reported as inputs.
            # If not, they are reported as outputs.
            (self.reservoir_depth, render_default),
            (self.reservoir_pressure, render_default),
        ]

    def _get_output_config_for_summary_of_results_category(
        self, render_default: Callable[[Parameter], str], render_scientific: Callable[[Parameter], str]
    ) -> list[tuple[Parameter, Callable[[Parameter], str]]]:
        return [
            # Note: If depth and/or pressure are provided, they are reported as inputs.
            # If not, they are reported as outputs.
            (self.reservoir_depth, render_default),
            (self.reservoir_pressure, render_default),
            (self.reservoir_volume, render_default),
            (self.volume_rock, render_default),
            (self.volume_recoverable_fluid, render_default),
            (self.reservoir_stored_heat, render_scientific),
            (self.stored_heat_rock, render_scientific),
            (self.stored_heat_fluid, render_scientific),
            (self.mass_rock, render_scientific),
            (self.mass_recoverable_fluid, render_scientific),
            (self.reservoir_enthalpy, render_default),
            (self.enthalpy_rock, render_default),
            (self.enthalpy_fluid, render_default),
            (
                self.reservoir_recovery_factor,
                lambda rg: f'{(100 * rg.value):10.2f} {self.reservoir_recovery_factor.CurrentUnits.value}',
            ),
            (self.reservoir_available_heat, render_scientific),
            (self.reservoir_producible_heat, render_scientific),
            (self.producible_heat_per_unit_area, render_scientific),
            (self.heat_per_unit_volume_reservoir, render_scientific),
            (self.reservoir_producible_electricity, render_default),
            (self.producible_electricity_per_unit_area, render_default),
            (self.electricity_per_unit_volume_reservoir, render_default),
        ]

    def PrintOutputsHTML(self, inputs, outputs, output_filename: str = 'HIP.html'):
        """
        PrintOutputs writes the standard outputs to the output file as HTML. The inputs and outputs are already prepared
        by the calling function so we just pass them in and use them in writing the HTML. They are dictionaries that
        contain the already formatted information for output.
        args:
            inputs: dict of inputs
            outputs: dict of outputs
            output_filename: name of the output file
        """
        self.logger.info(f'Init {__class__.__name__!s}: {__name__}')

        try:
            inputs_table = Table(title='***SUMMARY OF INPUTS***')
            inputs_table.add_column('Parameter Name', no_wrap=True)
            inputs_table.add_column('Value', no_wrap=True, justify='center')
            inputs_table.add_column('Units', no_wrap=True)
            outputs_table = Table(title='***SUMMARY OF RESULTS***')
            outputs_table.add_column('Result Name', no_wrap=True)
            outputs_table.add_column('Value', no_wrap=True, justify='center')
            outputs_table.add_column('Units', no_wrap=True)

            for key, value in inputs['SUMMARY OF INPUTS'].items():
                name: str = key
                val1 = value.strip().split(' ')
                val = val1[0]
                unit = ''
                if len(val1) > 1:
                    unit: str = UpgradeSymbologyOfUnits(str(val1[1]))
                inputs_table.add_row(name, val, unit)

            for key, value in outputs['SUMMARY OF RESULTS'].items():
                name: str = key
                val1 = value.strip().split(' ')
                val = val1[0]
                unit = ''
                if len(val1) > 1:
                    unit: str = UpgradeSymbologyOfUnits(str(val1[1]))

                outputs_table.add_row(name, val, unit)

            console = Console(style='bold white on blue', force_terminal=True, record=True)
            console.print('                  *********************')
            console.print('                  ***HIP CASE REPORT***')
            console.print('                  *********************')
            console.print(' ')
            console.print(inputs_table)
            console.print(' ')
            console.print(outputs_table)
            console.save_html('d:\\temp\\test_table.html')

        except FileNotFoundError as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

        except PermissionError as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

        except Exception as ex:
            traceback_str = traceback.format_exc()
            msg = f'Error: HIP_RA_X Failed to write the output file. Exiting....\n{traceback_str}'
            self.logger.critical(str(ex))
            self.logger.critical(msg)
            raise

    def __str__(self):
        return 'HIP_RA_X'


def main(enable_hip_ra_logging_config=True, suppress_input_sys_argv_warnings=False):
    # set the starting directory to be the directory that this file is in
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # set up logging.
    if enable_hip_ra_logging_config:
        logging.config.fileConfig('logging.conf')
    logger = logging.getLogger('root')

    logger.info('Initializing the HIP-RA-X application')

    # initiate the HIP-RA parameters, setting them to their default values
    model = HIP_RA_X(enable_hip_ra_logging_config=enable_hip_ra_logging_config)

    # read the parameters that apply to the model
    model.read_parameters(suppress_input_sys_argv_warnings=suppress_input_sys_argv_warnings)

    try:
        # Calculate the entire model
        model.Calculate()
    except Exception as e:
        logger.error(f'Error occurred during model calculation: {e!s}')

    try:
        # write the outputs
        model.PrintOutputs()
    except Exception as e:
        logger.error(f'Error occurred during output printing: {e!s}')

    logger.info('HIP-RA-X application execution completed')


if __name__ == '__main__':
    main()
