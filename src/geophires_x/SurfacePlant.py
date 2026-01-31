import numpy as np

from .EconomicsUtils import CONSTRUCTION_CAPEX_SCHEDULE_PARAMETER_NAME
from .GeoPHIRESUtils import quantity
from .NumpyUtils import np_trapz
from .OptionList import EndUseOptions, PlantType
from .Parameter import floatParameter, intParameter, OutputParameter, ReadParameter, \
    coerce_int_params_to_enum_values
from .SurfacePlantUtils import MAX_CONSTRUCTION_YEARS
from .Units import *
import geophires_x.Model as Model


class SurfacePlant:
    @staticmethod
    def integrate_time_series_slice(
        series: np.ndarray,
        _i: int,
        time_steps_per_year: int,
        utilization_factor: float
    ) -> np.float64:
        slice_start_index = _i * time_steps_per_year
        slice_end_index = ((_i + 1) * time_steps_per_year) + 1
        _slice = list(series[slice_start_index:slice_end_index])

        # Note that len(_slice) - 1 may be less than time_steps_per_year for the last slice.

        if len(_slice) == 1:
            extrapolated_future_datapoint = _slice[0]
            if slice_start_index - 1 > 0:
                delta = series[slice_start_index] - series[slice_start_index - 1]
                extrapolated_future_datapoint = _slice[0] + delta
            _slice.append(extrapolated_future_datapoint)

        dx_steps = len(_slice) - 1

        integral = np_trapz(
            _slice,
            dx=1. / dx_steps * 365. * 24.
        )

        return integral * 1000. * utilization_factor

    def remaining_reservoir_heat_content(self, InitialReservoirHeatContent: np.ndarray, HeatkWhExtracted:  np.ndarray) -> np.ndarray:
        """
        Calculate reservoir heat content
        :param InitialReservoirHeatContent: Initial reservoir heat content [PJ]
        :param HeatkWhExtracted: Heat extracted from reservoir [kWh]
        :return: Remaining reservoir heat content [PJ]

        """
        # calculate reservoir heat content
        return InitialReservoirHeatContent - np.add.accumulate(HeatkWhExtracted) * 3600 * 1E3 / 1E15

    def power_plant_entering_temperature(self, enduse_option: EndUseOptions, timevector: np.ndarray,
                                         T_chp_bottom: float, ProducedTemperature: np.ndarray) -> np.ndarray:
        """
        Calculate power plant entering temperature based on end-use option and power plant type (see docs for details)
        :param enduse_option: end-use option
        :param timevector: time vector
        :param T_chp_bottom: power plant entering temperature used in CHP bottoming cycle
        :param ProducedTemperature: produced temperature
        :return: power plant entering temperature

        """
        if enduse_option in [EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT]:
            TenteringPP = np.full(len(timevector), T_chp_bottom)
        else:
            TenteringPP = ProducedTemperature
        return TenteringPP

    def availability_water(self, T0: float, T1: float, T2: float) -> float:
        """
        Availability water: copied from GEOPHIRES v1.0 Fortran Code
        :param T0: T0
        :param T1: T1
        :param T2: T2
        :return: Availability water [MJ/kg]
        """
        A = 4.041650
        B = -1.204E-2
        C = 1.60500E-5

        T0 = T0 + 273.15
        T1 = T1 + 273.15
        T2 = T2 + 273.15
        availability = ((A - B * T0) * (T1 - T2) + (B - C * T0) / 2.0 * (T1 ** 2 - T2 ** 2) + C / 3.0 * (
                T1 ** 3 - T2 ** 3) - A * T0 * np.log(T1 / T2)) * 2.2046 / 947.83  # MJ/kg

        return availability

    def reinjection_temperature(self, model: Model, ambient_temperature: float, TenteringPP: np.ndarray, Tinj: float,
                                C01: float, C11: float, C21: float, D01: float, D11: float, D21: float,
                                C02: float, C12: float, C22: float, D02: float, D12: float, D22: float) -> tuple:
        """
        Calculate reinjection temperature based on ambient temperature, power plant entering temperature and injection temperature.
        (see docs for details)
        :param model: The container class of the application, giving access to everything else, including the logger
        :param ambient_temperature: ambient temperature
        :param TenteringPP: power plant entering temperature
        :param Tinj: injection temperature
        :param C01: C01
        :param C11: C11
        :param C21: C21
        :param D02: D02
        :param D12: D12
        :param D22: D22
        :return: injection temperature, reinjection temperature, and etau
        """
        if ambient_temperature < 15.:
            Tfraction = (ambient_temperature - 5.) / 10.
        else:
            Tfraction = (ambient_temperature - 15.) / 10.
        etaull = C21*TenteringPP**2 + C11*TenteringPP + C01
        etauul = D21*TenteringPP**2 + D11*TenteringPP + D01
        etau = (1.-Tfraction)*etaull + Tfraction*etauul

        reinjtll = C22*TenteringPP**2 + C12*TenteringPP + C02
        reinjtul = D22*TenteringPP**2 + D12*TenteringPP + D02
        ReinjTemp = (1.-Tfraction)*reinjtll + Tfraction*reinjtul

        # check if reinjectemp (model calculated) < Tinj (user provided)
        if np.min(ReinjTemp) < Tinj:
            user_injection_temp = Tinj
            Tinj = np.min(ReinjTemp)
            msg = (f'Model-calculated reinjection temperature ({Tinj:2f}) is lower than input reinjection temperature '
                   f'({user_injection_temp}); input reinjection temperature will be ignored.')
            model.logger.warning(msg)

        return Tinj, ReinjTemp, etau

    def electricity_heat_production(self, enduse_option: EndUseOptions, availability: np.ndarray, etau: np.ndarray, nprod: int,
                                    prodwellflowrate: float, cpwater: float, ProducedTemperature: np.ndarray, Tinj: float,
                                    ReinjTemp: float, T_chp_bottom: float, enduse_efficiency_factor: float, chp_fraction: float) -> tuple:
        """
        Calculate electricity/heat production based on end-use option (see docs for details)
        :param enduse_option: end-use option
        :param availability: geofluid availability
        :param etau: etau
        :param nprod: number of production wells
        :param prodwellflowrate: production well flow rate
        :param cpwater: specific heat capacity of water
        :param ProducedTemperature: produced temperature
        :param Tinj: injection temperature
        :param ReinjTemp: reinjection temperature
        :param T_chp_bottom: power plant entering temperature used in CHP bottoming cycle
        :param enduse_efficiency_factor: end-use efficiency factor
        :param chp_fraction: fraction of produced geofluid flow rate going to direct-use heat application in CHP parallel cycle
        :return: electricity produced, heat extracted, heat produced, and heat extracted towards electricity
        """
        HeatProduced = np.empty(0)
        HeatExtractedTowardsElectricity = np.empty(0)
        # calculate electricity/heat - first, calculate the total amount of heat extracted from geofluid [MWth] (same for all)
        HeatExtracted = nprod * prodwellflowrate * cpwater * (ProducedTemperature - Tinj) / 1E6

        # next do the electricity produced - the same for all, except enduse=5, where it is recalculated
        ElectricityProduced = availability * etau * nprod * prodwellflowrate
        if ElectricityProduced.max() < 0:
            # TODO: make message more informative (possibly by hinting that maximum temperature may be too high)
            raise RuntimeError('Electricity production calculated as negative.')

        if enduse_option == EndUseOptions.ELECTRICITY:
            # pure electricity
            HeatExtractedTowardsElectricity = HeatExtracted

        elif enduse_option in [EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT]:
            # enduse_option = 3: cogen topping cycle
            # Useful heat for direct-use application [MWth]
            HeatProduced = enduse_efficiency_factor * nprod * prodwellflowrate * cpwater * (ReinjTemp - Tinj) / 1E6
            HeatExtractedTowardsElectricity = nprod * prodwellflowrate * cpwater * (ProducedTemperature - ReinjTemp) / 1E6

        elif enduse_option in [EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY]:
            # enduse_option = 4: cogen bottoming cycle
            # Useful heat for direct-use application [MWth]
            HeatProduced = enduse_efficiency_factor * nprod * prodwellflowrate * cpwater * (ProducedTemperature - T_chp_bottom) / 1E6
            HeatExtractedTowardsElectricity = nprod * prodwellflowrate * cpwater * (T_chp_bottom - Tinj) / 1E6

        elif enduse_option in [EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT]:
            # enduse_option = 5: cogen split of mass flow rate
            # electricity part [MWe]
            ElectricityProduced = availability * etau * nprod * prodwellflowrate * (1. - chp_fraction)
            # useful heat part for direct-use application [MWth]
            HeatProduced = enduse_efficiency_factor * chp_fraction * nprod * prodwellflowrate * cpwater * (ProducedTemperature - Tinj) / 1E6
            HeatExtractedTowardsElectricity = (1. - chp_fraction) * nprod * prodwellflowrate * cpwater * (ProducedTemperature - Tinj) / 1E6

        return ElectricityProduced, HeatExtracted, HeatProduced, HeatExtractedTowardsElectricity

    def annual_electricity_pumping_power(self, plant_lifetime: int,enduse_option: EndUseOptions, HeatExtracted: np.ndarray,
                                         time_steps_per_year: int, utilization_factor: float, PumpingPower: np.ndarray,
                                         ElectricityProduced: np.ndarray, NetElectricityProduced: np.ndarray, HeatProduced: np.ndarray) -> tuple:
        """
        Calculate annual electricity/heat production
        :param plant_lifetime: plant lifetime
        :param enduse_option: end-use option
        :param HeatExtracted: heat extracted
        :param time_steps_per_year: time steps per year
        :param utilization_factor: utilization factor
        :param PumpingPower: pumping power
        :param ElectricityProduced: electricity produced
        :param NetElectricityProduced: net electricity produced
        :param HeatProduced: heat produced

        """
        # Calculate annual electricity/heat production
        # all end-use options have "heat extracted from reservoir" and pumping kWs
        HeatkWhExtracted = np.zeros(plant_lifetime)
        PumpingkWh = np.zeros(plant_lifetime)
        TotalkWhProduced = np.zeros(plant_lifetime)
        NetkWhProduced = np.zeros(plant_lifetime)
        HeatkWhProduced = np.zeros(plant_lifetime)

        def _integrate_slice(series: np.ndarray, _i: int) -> np.float64:
            return SurfacePlant.integrate_time_series_slice(series, _i, time_steps_per_year, utilization_factor)

        for i in range(0, plant_lifetime):
            HeatkWhExtracted[i] = _integrate_slice(HeatExtracted, i)
            PumpingkWh[i] = _integrate_slice(PumpingPower, i)


        if enduse_option in [EndUseOptions.ELECTRICITY, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                        EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
            # all these end-use options have an electricity generation component
            TotalkWhProduced = np.zeros(plant_lifetime)
            NetkWhProduced = np.zeros(plant_lifetime)
            for i in range(0, plant_lifetime):
                TotalkWhProduced[i] = _integrate_slice(ElectricityProduced, i)
                NetkWhProduced[i] = _integrate_slice(NetElectricityProduced, i)

        if enduse_option is not EndUseOptions.ELECTRICITY:
            # all those end-use options have a direct-use component
            HeatkWhProduced = np.zeros(plant_lifetime)
            for i in range(0, plant_lifetime):
                HeatkWhProduced[i] = _integrate_slice(HeatProduced, i)

        return HeatkWhExtracted, PumpingkWh, TotalkWhProduced, NetkWhProduced, HeatkWhProduced

    def __init__(self, model: Model):
        """
        The __init__ function is called automatically when a class is instantiated.
        It initializes the attributes of an object, and sets default values for certain arguments that can be overridden
         by user input.
        The __init__ function is used to set up all the parameters in the Surfaceplant.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')

        self.Tinj = 0.0

        # Set up all the Parameters that will be predefined by this class using the different types of parameter classes.
        # Setting up includes giving it a name, a default value, The Unit Type (length, volume, temperature, etc.) and
        # Unit Name of that value, sets it as required (or not), sets allowable range, the error message if that range
        # is exceeded, the ToolTip Text, and the name of teh class that created it.
        # This includes setting up temporary variables that will be available to all the class but noy read in by user,
        # or used for Output
        # This also includes all Parameters that are calculated and then published using the Printouts function.

        # These dictionaries contain a list of all the parameters set in this object, stored as "Parameter" and
        # "OutputParameter" Objects.  This will allow us later to access them in a user interface and get that list,
        # along with unit type, preferred units, etc.
        self.ParameterDict = {}
        self.OutputParameterDict = {}

        self.enduse_option = self.ParameterDict[self.enduse_option.Name] = intParameter(
            "End-Use Option",
            DefaultValue=EndUseOptions.ELECTRICITY.int_value,
            AllowableRange=[1, 2, 31, 32, 41, 42, 51, 52],
            ValuesEnum=EndUseOptions,
            UnitType=Units.NONE,
            ErrMessage="assume default end-use option (1: electricity only)",
            ToolTipText="Select the end-use application of the geofluid heat: " +
                        '; '.join([f'{it.int_value}: {it.value}' for it in EndUseOptions])
        )
        self.plant_type = self.ParameterDict[self.plant_type.Name] = intParameter(
            "Power Plant Type",
            DefaultValue=PlantType.SUB_CRITICAL_ORC.int_value,
            AllowableRange=[1, 2, 3, 4, 5, 6, 7, 8, 9],
            ValuesEnum=PlantType,
            UnitType=Units.NONE,
            ErrMessage="assume default power plant type (1: subcritical ORC)",
            ToolTipText="Specify the type of physical plant. " +
                        '; '.join([f'{it.int_value}: {it.value}' for it in PlantType])
        )
        self.pump_efficiency = self.ParameterDict[self.pump_efficiency.Name] = floatParameter(
            "Circulation Pump Efficiency",
            DefaultValue=0.75,
            Min=0.1,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.TENTH,
            Required=True,
            ErrMessage="assume default circulation pump efficiency (0.75)",
            ToolTipText="Specify the overall efficiency of the injection and production well pumps"
        )
        self.utilization_factor = self.ParameterDict[self.utilization_factor.Name] = floatParameter(
            "Utilization Factor",
            DefaultValue=0.9,
            Min=0.1,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Required=True,
            ErrMessage="assume default utilization factor (0.9)",
            ToolTipText="Ratio of the time the plant is running in normal production in a 1-year time period. "
                        "Synonymous with capacity factor."
        )
        self.enduse_efficiency_factor = self.ParameterDict[self.enduse_efficiency_factor.Name] = floatParameter(
            "End-Use Efficiency Factor",
            DefaultValue=0.9,
            Min=0.1,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default end-use efficiency factor (0.9)",
            ToolTipText="Constant thermal efficiency of the direct-use application"
        )
        self.chp_fraction = self.ParameterDict[self.chp_fraction.Name] = floatParameter(
            "CHP Fraction",
            DefaultValue=0.5,
            Min=0.0001,
            Max=0.9999,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default CHP fraction (0.5)",
            ToolTipText="Fraction of produced geofluid flow rate going to direct-use heat application in" +
            " CHP parallel cycle"
        )
        self.T_chp_bottom = self.ParameterDict[self.T_chp_bottom.Name] = floatParameter(
            "CHP Bottoming Entering Temperature",
            DefaultValue=150.0,
            Min=0,
            Max=400,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            ErrMessage="assume default CHP bottom temperature (150 deg.C)",
            ToolTipText="Power plant entering geofluid temperature used in CHP bottoming cycle"
        )
        self.ambient_temperature = self.ParameterDict[self.ambient_temperature.Name] = floatParameter(
            "Ambient Temperature",
            DefaultValue=15.0,
            Min=-50,
            Max=50,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            ErrMessage="assume default ambient temperature (15 deg.C)",
            ToolTipText="Ambient (or dead-state) temperature used for calculating power plant utilization efficiency"
        )
        self.plant_lifetime = self.ParameterDict[self.plant_lifetime.Name] = intParameter(
            "Plant Lifetime",
            DefaultValue=30,
            AllowableRange=list(range(1, 101, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            Required=True,
            ErrMessage="assume default plant lifetime (30 years)",
            ToolTipText="System lifetime"
        )
        self.piping_length = self.ParameterDict[self.piping_length.Name] = floatParameter(
            "Surface Piping Length",
            DefaultValue=0.0,
            Min=0,
            Max=100,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.KILOMETERS,
            CurrentUnits=LengthUnit.KILOMETERS,
            ErrMessage="assume default piping length (0km)"
        )
        self.plant_outlet_pressure = self.ParameterDict[self.plant_outlet_pressure.Name] = floatParameter(
            "Plant Outlet Pressure",
            DefaultValue=100.0,
            Min=0.01,
            Max=15000.0,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL,
            ErrMessage="assume default plant outlet pressure (100 kPa)",
            ToolTipText="Constant plant outlet pressure equal to injection well pump(s) suction pressure"
        )
        self.electricity_cost_to_buy = self.ParameterDict[self.electricity_cost_to_buy.Name] = floatParameter(
            "Electricity Rate",
            DefaultValue=0.07,
            Min=0.0,
            Max=1.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume default electricity rate ($0.07/kWh)",
            ToolTipText="Price of electricity to calculate pumping costs in direct-use heat only mode or revenue" +
            " from electricity sales in CHP mode."
        )
        self.heat_price = self.ParameterDict[self.heat_price.Name] = floatParameter(
            "Heat Rate",
            DefaultValue=0.02,
            Min=0.0,
            Max=1.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume default heat rate ($0.02/kWh)",
            ToolTipText="Price of heat to calculate revenue from heat sales in CHP mode."
        )

        default_construction_years = 1
        self.construction_years = self.ParameterDict[self.construction_years.Name] = intParameter(
            "Construction Years",
            DefaultValue=default_construction_years,
            AllowableRange=list(range(1, MAX_CONSTRUCTION_YEARS + 1, 1)),
            UnitType=Units.NONE,
            ErrMessage=f'assume default number of years in construction ({default_construction_years})',
            ToolTipText=f'Number of years spent in construction (assumes whole years, no fractions). '
                        f'By default, capital costs are spread evenly over construction years e.g. if total capital '
                        f'costs are $500M and there are 2 construction years, '
                        f'then $250M will be spent in both the first and second construction years. '
                        f'For SAM Economic Models, provide {CONSTRUCTION_CAPEX_SCHEDULE_PARAMETER_NAME} to use a '
                        f'custom spread instead.'
        )

        self.cp_fluid = self.ParameterDict[self.cp_fluid.Name] = floatParameter(
            "Working Fluid Heat Capacity",
            UnitType=Units.HEAT_CAPACITY,
            PreferredUnits=HeatCapacityUnit.JPERKGPERK,
            CurrentUnits=HeatCapacityUnit.JPERKGPERK,
            DefaultValue=4200.0,
            Min=0.0,
            Max=10_000.0,
            ErrMessage="assume default working fluid heat capacity (4200)",
            ToolTipText="Heat capacity of the working fluid"
        )
        self.rho_fluid = self.ParameterDict[self.rho_fluid.Name] = floatParameter(
            "Working Fluid Density",
            UnitType=Units.DENSITY,
            PreferredUnits=DensityUnit.KGPERMETERS3,
            CurrentUnits=DensityUnit.KGPERMETERS3,
            DefaultValue=1000.0,
            Min=0.0,
            Max=10_000.0,
            ErrMessage="assume default working fluid density (1000)",
            ToolTipText="Density of the working fluid"
        )
        self.k_fluid = self.ParameterDict[self.k_fluid.Name] = floatParameter(
            "Working Fluid Thermal Conductivity",
            UnitType=Units.THERMAL_CONDUCTIVITY,
            PreferredUnits=ThermalConductivityUnit.WPERMPERK,
            CurrentUnits=ThermalConductivityUnit.WPERMPERK,
            DefaultValue=0.68,
            Min=0.0,
            Max=10.0,
            ErrMessage="assume default working fluid thermal conductivity (0.68)",
            ToolTipText="Thermal conductivity of the working fluid"
        )
        self.mu_fluid = self.ParameterDict[self.mu_fluid.Name] = floatParameter(
            "Working Fluid Dynamic Viscosity",
            UnitType=Units.DYNAMIC_VISCOSITY,
            PreferredUnits=Dynamic_ViscosityUnit.PASCALSEC,
            CurrentUnits=Dynamic_ViscosityUnit.PASCALSEC,
            DefaultValue=600*10**-6,
            Min=0.0,
            Max=1,
            ErrMessage="assume default fluid dynamic density (600*10**-6)",
            ToolTipText="Dynamic viscosity of the working fluid"
        )

        # local variable initialization
        self.setinjectionpressurefixed = False
        sclass = str(__class__).replace("<class \'", "")
        self.MyClass = sclass.replace("\'>", "")
        self.MyPath = os.path.abspath(__file__)

        # Results - used by other objects or printed in output downstream

        self.enduse_option_output = self.OutputParameterDict[self.enduse_option_output.Name] = OutputParameter(
            Name=self.enduse_option.Name,
            UnitType=Units.NONE,
            ToolTipText='Five different end-use options are available in GEOPHIRES: '
                        '1: Electricity: All produced geothermal fluid is used to generate electricity with either an '
                        'ORC or flash power plant; '
                        '2: Direct-use heat: All produced geothermal fluid is used to provide heating for a given '
                        'application, e.g., a district-heating system or industrial process; '
                        '3: Cogeneration or combined heat and power (CHP): Both heat and electricity are produced. '
                        'Three different cogeneration configurations are available: '
                        '(1): Cogeneration topping cycle: A power plant is followed by a direct-use heat application '
                        'in series. Heat at high temperatures from the geothermal fluid is first converted into '
                        'electricity. Any remaining heat in the geothermal fluid after leaving the power plant is '
                        'supplied to a low-temperature direct-use heat application; '
                        '(2): Cogeneration bottoming cycle: A direct-use heat application is followed by a power plant '
                        'in series. In this less common configuration, the geothermal fluid first serves a '
                        'high-temperature direct-use heat application. Any remaining heat in the geothermal fluid '
                        'after leaving the direct-use heat process (at a user-specified temperature) is used to '
                        'generate electricity. The heat-to-power conversion typically occurs with an ORC plant '
                        'operating at low conversion efficiencies; '
                        '(3): Cogeneration parallel cycle: A power plant operates in parallel with a direct-use heat '
                        'application. The produced geothermal fluid is split into two streams, providing heat at the '
                        'same temperature to a power plant and direct-use heat application. The user specifies the '
                        'fluid flow fraction going to each process.',
            # TODO this tooltip text (ported from the theoretical basis) is probably better suited to being semantically
            #  associated with the End-Use Option input parameter rather than the corresponding OutputParameter here.
            #  However, the input parameter tooltip text is generated from an enumeration of EndUseOptions enum values
            #  which doesn't cleanly map to the information contained here because each of the CHP configurations has
            #  two EndUseOptions for whether heat or electricity sales are considered as extra income. This mapping
            #  incongruency could possibly eventually be addressed by an additional layer of metadata/indirection for
            #  adding pointers from input parameters to more complete documentation entries/sections. In the meantime,
            #  this output parameter tooltip is a logical-enough place to store the information, where it is reasonably
            #  user-accessible in the UI and parameters reference.
            json_parameter_type='string'
        )
        self.usebuiltinoutletplantcorrelation = self.OutputParameterDict[self.usebuiltinoutletplantcorrelation.Name] = OutputParameter(
            Name="usebuiltinoutletplantcorrelation",
            UnitType=Units.NONE
        )
        self.TenteringPP = self.OutputParameterDict[self.TenteringPP.Name] = OutputParameter(
            Name="TenteringPP",
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS
        )
        self.HeatkWhExtracted = self.OutputParameterDict[self.HeatkWhExtracted.Name] = OutputParameter(
            Name="annual heat production",
            UnitType=Units.ENERGYFREQUENCY,
            PreferredUnits=EnergyFrequencyUnit.GWPERYEAR,
            CurrentUnits=EnergyFrequencyUnit.GWPERYEAR
        )
        self.PumpingkWh = self.OutputParameterDict[self.PumpingkWh.Name] = OutputParameter(
            Name="annual electricity production",
            UnitType=Units.ENERGYFREQUENCY,
            PreferredUnits=EnergyFrequencyUnit.KWPERYEAR,
            CurrentUnits=EnergyFrequencyUnit.KWPERYEAR
        )
        self.ElectricityProduced = self.OutputParameterDict[self.ElectricityProduced.Name] = OutputParameter(
            Name="Total Electricity Production",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
            # TODO tooltip text - should reference that this is gross production
        )
        self.NetElectricityProduced = self.OutputParameterDict[self.NetElectricityProduced.Name] = OutputParameter(
            Name="Net Electricity Production",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.TotalkWhProduced = self.OutputParameterDict[self.TotalkWhProduced.Name] = OutputParameter(
            Name="Total Electricity Generation",
            UnitType=Units.ENERGY,
            PreferredUnits=EnergyUnit.KWH,
            CurrentUnits=EnergyUnit.KWH
        )
        self.NetkWhProduced = self.OutputParameterDict[self.NetkWhProduced.Name] = OutputParameter(
            Name="Net Electricity Generation",
            UnitType=Units.ENERGY,
            PreferredUnits=EnergyUnit.KWH,
            CurrentUnits=EnergyUnit.KWH
        )
        self.FirstLawEfficiency = self.OutputParameterDict[self.FirstLawEfficiency.Name] = OutputParameter(
            Name="First Law Efficiency",
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,  # FIXME default values are actually in tenths, not percent.
            ToolTipText='Net electricity produced divided by heat extracted towards electricity'
        )
        self.heat_to_power_conversion_efficiency = self.OutputParameterDict[self.heat_to_power_conversion_efficiency.Name] = OutputParameter(
            Name='Heat to Power Conversion Efficiency',
            value=None,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText='First law efficiency average over project lifetime'
        )
        self.HeatExtracted = self.OutputParameterDict[self.HeatExtracted.Name] = OutputParameter(
            Name="Heat Extracted",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.HeatProduced = self.OutputParameterDict[self.HeatProduced.Name] = OutputParameter(
            Name="Heat Produced in MW",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.HeatkWhProduced = self.OutputParameterDict[self.HeatkWhProduced.Name] = OutputParameter(
            Name="Heat Produced in kWh",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.KW,
            CurrentUnits=PowerUnit.KW
        )
        self.Availability = self.OutputParameterDict[self.Availability.Name] = OutputParameter(
            Name="Geofluid Availability",
            UnitType=Units.AVAILABILITY,
            PreferredUnits=AvailabilityUnit.MWPERKGPERSEC,
            CurrentUnits=AvailabilityUnit.MWPERKGPERSEC
        )
        self.RemainingReservoirHeatContent = self.OutputParameterDict[self.RemainingReservoirHeatContent.Name] = OutputParameter(
            Name="Remaining Reservoir Heat Content",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )

        model.logger.info(f'Complete {self.__class__.__name__}: {__name__}')

    def __str__(self):
        return 'SurfacePlant'

    def read_parameters(self, model:Model) -> None:
        """
        The read_parameters function reads in the parameters from a dictionary and stores them in the parameters.
        It also handles special cases that need to be handled after a value has been read in and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not), and if you do
        :param model: The container class of the application, giving access to everything else, including the logger
        :return: None
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')

        # Deal with all the parameter values that the user has provided.  They should really only provide values that
        # they want to change from the default values, but they can provide a value that is already set because it is a
        # default value set in __init__.  It will ignore those.
        # This also deals with all the special cases that need to be taken care of after a value has been
        # read in and checked.
        # If you choose to subclass this master class, you can also choose to override this method (or not),
        # and if you do, do it before or after you call you own version of this method.
        # If you do, you can also choose to call this method from you class, which can effectively modify all
        # these superclass parameters in your class.

        if len(model.InputParameters) > 0:
            # loop through all the parameters that the user wishes to set, looking for parameters that match this object
            for item in self.ParameterDict.items():
                ParameterToModify = item[1]
                key = ParameterToModify.Name.strip()
                if key in model.InputParameters:
                    ParameterReadIn = model.InputParameters[key]

                    # this should handle all the non-special cases
                    ReadParameter(ParameterReadIn, ParameterToModify, model)

                    # handle special cases
                    if ParameterToModify.Name == 'End-Use Option':
                        end_use_option = EndUseOptions.from_input_string(ParameterReadIn.sValue)
                        ParameterToModify.value = end_use_option
                        if end_use_option == EndUseOptions.HEAT:
                            self.plant_type.value = PlantType.INDUSTRIAL
                    elif ParameterToModify.Name == 'Power Plant Type':
                        ParameterToModify.value = PlantType.from_input_string(ParameterReadIn.sValue)
                        if self.enduse_option.value == EndUseOptions.ELECTRICITY:
                            # simple single- or double-flash power plant assumes no production well pumping
                            if ParameterToModify.value in [PlantType.SINGLE_FLASH, PlantType.DOUBLE_FLASH]:
                                model.wellbores.impedancemodelallowed.value = False
                                model.wellbores.productionwellpumping.value = False
                                self.setinjectionpressurefixed = True
                        elif self.enduse_option.value in \
                            [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY]:
                            # co-generation topping cycle with single- or double-flash power plant assumes no production well pumping
                            if ParameterToModify.value in [PlantType.SINGLE_FLASH, PlantType.DOUBLE_FLASH]:
                                model.wellbores.impedancemodelallowed.value = False
                                model.wellbores.productionwellpumping.value = False
                                self.setinjectionpressurefixed = True
                        elif self.enduse_option.value in \
                            [EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY]:
                            # co-generation bottoming cycle with single- or double-flash power plant assumes
                            # production well pumping
                            if ParameterToModify.value in [PlantType.SINGLE_FLASH, PlantType.DOUBLE_FLASH]:
                                model.wellbores.impedancemodelallowed.value = False
                                self.setinjectionpressurefixed = True
                        elif self.enduse_option.value in \
                            [EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
                            # co-generation parallel cycle with single- or double-flash power plant assumes
                            # production well pumping
                            if ParameterToModify.value in [PlantType.SINGLE_FLASH, PlantType.DOUBLE_FLASH]:
                                model.wellbores.impedancemodelallowed.value = False
                                self.setinjectionpressurefixed = True
                        if model.wellbores.impedancemodelused.value and \
                            ParameterToModify.value in [PlantType.SINGLE_FLASH, PlantType.DOUBLE_FLASH]:
                            msg = ('Flash plant is being used with impedance model. When reservoir impedance '
                                   'is specified, no flashing is allowed in production wells or at surface.')
                            print(f'Warning: {msg}')
                            model.logger.warning(msg)
                    elif ParameterToModify.Name == 'Plant Outlet Pressure':
                        if ParameterToModify.value < self.plant_outlet_pressure.Min or ParameterToModify.value > self.plant_outlet_pressure.Max:
                                if self.setinjectionpressurefixed:
                                    ParameterToModify.value = 100
                                    msg = (f'Provided plant outlet pressure outside of range defined valid range. GEOPHIRES will '
                                           f'assume default plant outlet pressure ({ParameterToModify.value} kPa)')
                                    print(f'Warning: {msg}')
                                    model.logger.warning(msg)
                                else:
                                    self.usebuiltinoutletplantcorrelation.value = True
                                    msg = ('Provided plant outlet pressure outside of defined valid range. '
                                           'GEOPHIRES will calculate plant outlet pressure based on production '
                                           'wellhead pressure and surface equipment pressure drop of 10 psi')
                                    print(f'Warning: {msg}')
                                    model.logger.warning(msg)
            if "Plant Outlet Pressure" not in model.InputParameters:
                if self.setinjectionpressurefixed:
                    self.usebuiltinoutletplantcorrelation.value = False
                    self.plant_outlet_pressure.value = 100
                    msg = (f'No valid plant outlet pressure provided. '
                           f'GEOPHIRES will assume default plant outlet pressure ({self.plant_outlet_pressure.value} kPa)')
                    model.logger.warning(msg)
                else:
                    self.usebuiltinoutletplantcorrelation.value = True
                    msg = (f'No valid plant outlet pressure provided. GEOPHIRES will calculate plant outlet pressure '
                           f'based on production wellhead pressure and surface equipment pressure drop of 10 psi')
                    model.logger.warning(msg)
        else:
            model.logger.info('No parameters read because no content provided')

        coerce_int_params_to_enum_values(self.ParameterDict)

        model.logger.info(f'Complete {self.__class__.__name__}: {__name__}')

    def Calculate(self, model: Model) -> None:
        """
        The Calculate function is where all the calculations are done.
        This function can be called multiple times, and will only recalculate what has changed each time it is called.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: Nothing, but it does make calculations and set values in the model
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')

        # All calculations are handled in subclasses of this class, so this function is empty.

        # Subclasses should call _calculate_derived_outputs at the end of their Calculate methods.
        self._calculate_derived_outputs(model)

        model.logger.info(f'Complete {self.__class__.__name__}: {__name__}')

    def _calculate_derived_outputs(self, model: Model) -> None:
        """
        Subclasses should call _calculate_derived_outputs at the end of their Calculate methods to populate output
        values that are derived from subclass-calculated outputs.
        """

        if self.FirstLawEfficiency is not None:
            fle_unit = PercentUnit.TENTH  # See FIXME on self.FirstLawEfficiency re: CurrentUnit being incorrect.
            avg_efficiency = quantity(np.average(model.surfaceplant.FirstLawEfficiency.value), fle_unit).to(
                convertible_unit(self.heat_to_power_conversion_efficiency.CurrentUnits)).magnitude
            if avg_efficiency > 0:  # 0 is presumed to mean N/A
                self.heat_to_power_conversion_efficiency.value = avg_efficiency

        self.enduse_option_output.value = self.enduse_option.value.value
