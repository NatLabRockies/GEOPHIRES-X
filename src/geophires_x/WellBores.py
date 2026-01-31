import math
import numpy as np
from pint.facets.plain import PlainQuantity

from .Parameter import floatParameter, intParameter, boolParameter, OutputParameter, ReadParameter, \
    coerce_int_params_to_enum_values, Parameter
from geophires_x.GeoPHIRESUtils import vapor_pressure_water_kPa, quantity, static_pressure_MPa
from geophires_x.GeoPHIRESUtils import density_water_kg_per_m3
from geophires_x.GeoPHIRESUtils import viscosity_water_Pa_sec
from .Units import *
import geophires_x.Model as Model
from .OptionList import ReservoirModel, Configuration, WorkingFluid


# code from Koenraad


def calculate_total_drilling_lengths_m(Configuration, numnonverticalsections: int, nonvertical_length_km: float,
                                       InputDepth_km: float, OutputDepth_km: float, nprod:int, ninj:int,
                                       junction_depth_km: float = 0.0, angle_rad: float = 0.0) -> tuple:
    """
    returns the total length, vertical length, and non-vertical lengths, depending on the configuration
    :param Configuration:  configuration of the well
    :type Configuration: :class:`~geophires
    :param numnonverticalsections: number of non-vertical sections
    :type numnonverticalsections: int
    :param nonvertical_length_km: length of non-vertical sections in km
    :type nonvertical_length_km: float
    :param InputDepth_km: depth of the well in km
    :type InputDepth_km: float
    :param OutputDepth_km: depth of the output end of the well in km, if U shaped, and not horizontal
    :type OutputDepth_km: float
    :param nprod: number of production wells
    :type nprod: int
    :param ninj: number of injection wells
    :param junction_depth_km: depth of the junction in km
    :type junction_depth_km: float
    :param angle_rad: angle of the well in radians, from horizontal
    :type angle_rad: float
    :return: total length, vertical length, lateral, and junction lengths in meters
    :rtype: tuple
    """
    tot_pipe_length_m = vertical_pipe_length_m = lateral_pipe_length_m = tot_to_junction_m = 0.0
    if Configuration is Configuration.ULOOP:
        # Total drilling depth of both wells and laterals in U-loop [m]
        vertical_pipe_length_m = (nprod * InputDepth_km * 1000.0) + (ninj * OutputDepth_km * 1000.0)
        lateral_pipe_length_m = numnonverticalsections * nonvertical_length_km * 1000.0

    elif Configuration is Configuration.COAXIAL:
        # Total drilling depth of well and lateral in co-axial case [m] - is not necessarily only vertical
        vertical_pipe_length_m = (nprod + ninj) * InputDepth_km * 1000.0
        lateral_pipe_length_m = numnonverticalsections * nonvertical_length_km * 1000.0

    elif Configuration is Configuration.VERTICAL:
        # Total drilling depth of well in vertical case [m]
        vertical_pipe_length_m = (nprod + ninj) * InputDepth_km * 1000.0
        lateral_pipe_length_m = 0.0

    elif Configuration is Configuration.L:
        # Total drilling depth of well in L case [m]
        vertical_pipe_length_m = (nprod + ninj) * InputDepth_km * 1000.0
        lateral_pipe_length_m = numnonverticalsections * nonvertical_length_km * 1000.0

    elif Configuration is Configuration.EAVORLOOP:
        # Total drilling length of well in EavorLoop [m]
        vertical_pipe_length_m = (nprod + ninj) * InputDepth_km * 1000.0

        # now calculate the distance from the bottom of the vertical to the junction of the laterals [m]
        O1 = (junction_depth_km - InputDepth_km) * 1000.0  # in meters
        tot_to_junction_m = (O1 / math.sin(angle_rad)) * 2  # there are two of these of each EavorLoop

        # now calculate the distance from the junction of the laterals to the end of the laterals [m]
        O2 = (OutputDepth_km - junction_depth_km) * 1000.0   # in meters
        lateral_pipe_length_m = (O2 / math.sin(angle_rad)) * 2  # there are two of these of each lateral of an EavorLoop
        lateral_pipe_length_m = lateral_pipe_length_m * numnonverticalsections  # there are numnonverticalsections of these
    else:
        raise ValueError(f'Invalid Configuration: {Configuration}')

    tot_pipe_length_m = vertical_pipe_length_m + lateral_pipe_length_m + tot_to_junction_m
    return tot_pipe_length_m, vertical_pipe_length_m, lateral_pipe_length_m, tot_to_junction_m


def InjectionReservoirPressurePredictor(project_lifetime_yr: int, timesteps_per_year: int, initial_pressure_kPa: float,
                                        inflation_rate: float) -> list:
    """
    InjectionReservoirPressurePredictor builds the Injection Reservoir Pressure Array for the project lifetime
     based on the initial (perhaps hydrostatic) pressure and the inflation rate. There is no limit to how high the
        pressure can go.
    :param project_lifetime_yr: The lifetime of the project in years
    :type project_lifetime_yr: int
    :param timesteps_per_year: The number of timesteps per year
    :type timesteps_per_year: int
    :param initial_pressure_kPa: The initial pressure in kPa
    :type initial_pressure_kPa: float
    :param inflation_rate: The inflation rate in %/yr
    :type inflation_rate: float
    :return: pressure: The pressure array as a function of time.
    :rtype: list
    """

    # Initialize the pressure array with the initial hydrostatic pressure
    pressure = [initial_pressure_kPa] * project_lifetime_yr * timesteps_per_year

    # If the overpressure percentage is 0,
    # return the hydrostatic pressure array as a constant value equal to the initial hydrostatic pressure
    if inflation_rate == 0:
        return pressure

    # Calculate the initial pressure
    pressure[0] = initial_pressure_kPa
    pressure_change_per_timestep = inflation_rate / timesteps_per_year
    for current_timestep in range(1, project_lifetime_yr * timesteps_per_year):
        pressure[current_timestep] = initial_pressure_kPa + (pressure_change_per_timestep * current_timestep)
    return pressure


def ReservoirPressurePredictor(project_lifetime_yr: int, timesteps_per_year: int, initial_pressure_kPa: float,
                               overpressure_percentage: float, depletion_rate: float) -> list:
    """
    ReservoirPressurePredictor builds the Reservoir Pressure Array for the project lifetime based on the initial
    (likely hydrostatic) pressure. the overpressure percentage and the depletion rate. Don't let the pressure drop
    below the initial pressure.
    :param project_lifetime_yr: The lifetime of the project in years
    :type project_lifetime_yr: int
    :param timesteps_per_year: The number of timesteps per year
    :type timesteps_per_year: int
    :param initial_pressure_kPa: The hydrostatic pressure in kPa
    :type initial_pressure_kPa: float
    :param overpressure_percentage: The overpressure percentage in %
    :type overpressure_percentage: float
    :param depletion_rate: The depletion rate in %/yr
    :type depletion_rate: float
    :return: hydrostatic_pressure: The hydrostatic pressure array as a function of time.
    :rtype: list
    """

    # Initialize the hydrostatic pressure array with the initial hydrostatic pressure
    pressure = [initial_pressure_kPa] * project_lifetime_yr * timesteps_per_year

    # If the overpressure percentage is 100,
    # return the hydrostatic pressure array as a constant value equal to the initial pressure
    if overpressure_percentage == 100.0:
        return pressure

    # Calculate the initial overpressure
    pressure[0] = initial_pressure_kPa * (overpressure_percentage / 100)
    delta_pressure = (pressure[0] - initial_pressure_kPa)
    depletion_timesteps = int((100.0 / depletion_rate) * timesteps_per_year)
    pressure_change_per_timestep = delta_pressure / depletion_timesteps
    for timestep in range(1, project_lifetime_yr * timesteps_per_year):
        pressure[timestep] = pressure[0] - (pressure_change_per_timestep * timestep)
        if pressure[timestep] < initial_pressure_kPa:
            # If the pressure drops below the hydrostatic pressure, set it to the hydrostatic pressure and break out
            pressure[timestep] = initial_pressure_kPa
            break
    return pressure


def RameyCalc(krock: float, rhorock: float, cprock: float, welldiam: float, tv, utilfactor: float, flowrate: float,
              cpwater: float, Trock: float, Tresoutput: float, averagegradient: float, depth: float) -> float:
    """
    Calculate the temperature drop along the length of a well
    this code is only valid so far for 1 gradient and deviation = 0
    For multiple gradients, use Ramey's model for every layer
    assume outside diameter of casing is 10% larger than inside diameter of production pipe (=prodwelldiam)
    assume borehole thermal resistance is negligible to rock thermal resistance
        :param depth:  depth of the well [m]
        :type: float
        :param averagegradient: average geothermal gradient [C/km]
        :type: float
        :param Tresoutput: reservoir output temperature [C]
        :type: float
        :param Trock: rock temperature [C]
        :type: float
        :param flowrate: flow rate [kg/s]
        :type: float
        :param utilfactor: utilization factor (fraction of time the well is producing) [-]
        :type: float
        :param tv: time vector [years]
        :type: float
        :param welldiam: well diameter [m]
        :type: float
        :param cprock: rock heat capacity [J/kg/C]
        :type: float
        :param rhorock: rock density [kg/m3]
        :type: float
        :param krock: rock thermal conductivity [W/m/C]
        :type: float
        :param cpwater: water heat capacity [J/kg/C]
        :type: float
        :return: temperature drop along the length of the well [C]
        :rtype: float
    """
    alen = len(tv)
    alpharock = krock / (rhorock * cprock)
    framey = np.zeros(alen)
    framey[1:] = -np.log(
        1.1 * (welldiam / 2.0) / np.sqrt(4. * alpharock * tv[1:] * 365.0 * 24.0 * 3600.0 * utilfactor)) - 0.29
    framey[0] = framey[1]  # force the first value to be the same as the second to get away from near surface effects
    rameyA = flowrate * cpwater * framey / 2 / math.pi / krock
    TempDrop = -((Trock - Tresoutput) - averagegradient * (depth - rameyA) + (
        Tresoutput - averagegradient * rameyA - Trock) * np.exp(-depth / rameyA))

    return TempDrop


def WellPressureDrop(model: Model, Taverage: float, wellflowrate: float, welldiam: float,
                     impedancemodelused: bool, depth: float) -> tuple:
    """
    calculate the pressure drop over the length of the well due to friction or impedance for the production well and
    the injection well (if applicable) using the Impedance Model or the friction model (if applicable) and the well
    flow rate and diameter and the average temperature of the fluid in the well (which is the average of the reservoir
    temperature and the injection temperature) and the depth of the well and the impedance of the reservoir (if
    applicable) and the number of production wells and the number of injection wells and the water loss (if applicable)
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param Taverage: average temperature of the fluid in the well [C]
        :type Taverage: float
        :param wellflowrate: flow rate of the fluid in the well [kg/s]
        :type wellflowrate: float
        :param welldiam: diameter of the well [m]
        :type welldiam: float
        :param impedancemodelused: whether or not the impedance model is used (True or False) [-]
        :type impedancemodelused: bool
        :param depth: depth of the well [m]
        :type depth: float
        :return: tuple of DPWell, f3, v, rhowater
        :rtype: tuple
    """
    # start by calculating wellbore fluid conditions [kPa], noting that most temperature drop happens
    # in upper section (because surrounding rock temperature is lowest in upper section)

    rhowater = np.array([
        density_water_kg_per_m3(
            t,
            pressure=model.reserv.hydrostatic_pressure(),
        )
        for t in Taverage
    ])  # replace with correlation based on Tprodaverage

    muwater = np.array([
        viscosity_water_Pa_sec(
            t,
            pressure=model.reserv.hydrostatic_pressure(),
        )
        for t in Taverage
    ])  # replace with correlation based on Tprodaverage

    v = wellflowrate / rhowater / (math.pi / 4. * welldiam ** 2)
    Rewater = 4.0 * wellflowrate / (muwater * math.pi * welldiam)  # laminar or turbulent flow?
    Rewateraverage = np.average(Rewater)
    if Rewateraverage < 2300.0:
        f3 = 64. / Rewater
    else:
        relroughness = 1E-4 / welldiam
        # 6 iterations to converge
        f3 = 1. / np.power(-2 * np.log10(relroughness / 3.7 + 5.74 / np.power(Rewater, 0.9)), 2.)
        f3 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f3))), 2.)
        f3 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f3))), 2.)
        f3 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f3))), 2.)
        f3 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f3))), 2.)
        f3 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f3))), 2.)

    if impedancemodelused:
        # assumed everything stays liquid throughout; /1E3 to convert from Pa to kPa
        DPWell = f3 * (rhowater * v ** 2 / 2.) * (depth / welldiam) / 1E3
    else:
        DPWell = []  # it will be calculated elsewhere

    return DPWell, f3, v, rhowater


def InjectionWellPressureDrop(model: Model, Taverage: float, wellflowrate: float, welldiam: float,
                              impedancemodelused: bool, depth: float, nprod: int, ninj: int, waterloss: float) -> tuple:
    """
    calculate the injection well pressure drop over the length of the well due to friction or impedance
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param Taverage: average temperature of the fluid in the well [C]
        :type Taverage: float
        :param wellflowrate: flow rate of the fluid in the well [kg/s]
        :type wellflowrate: float
        :param welldiam: diameter of the well [m]
        :type welldiam: float
        :param impedancemodelused: whether or not the impedance model is used (True or False) [-]
        :type impedancemodelused: bool
        :param depth: depth of the well [m]
        :type depth: float
        :param nprod: number of production wells [-]
        :type nprod: int
        :param ninj: number of injection wells [-]
        :type ninj: int
        :param waterloss: water loss [-]
        :type waterloss: float
        :return: tuple of DPWell, f1, v, rhowater
        :rtype: tuple
    """
    # start by calculating wellbore fluid conditions [kPa], noting that most temperature drop happens in
    # upper section (because surrounding rock temperature is lowest in upper section)
    rhowater = (density_water_kg_per_m3(Taverage, pressure=model.reserv.hydrostatic_pressure())
                * np.linspace(1, 1, len(model.wellbores.ProducedTemperature.value)))

    # replace with correlation based on Tinjaverage
    muwater = viscosity_water_Pa_sec(Taverage, pressure=model.reserv.hydrostatic_pressure()) * np.linspace(1, 1, len(model.wellbores.ProducedTemperature.value))
    v = nprod / ninj * wellflowrate * (1.0 + waterloss) / rhowater / (math.pi / 4. * welldiam ** 2)
    Rewater = 4. * nprod / ninj * wellflowrate * (1.0 + waterloss) / (
        muwater * math.pi * welldiam)  # laminar or turbulent flow?
    Rewateraverage = np.average(Rewater)
    if Rewateraverage < 2300.:  # laminar flow
        f1 = 64. / Rewater
    else:  # turbulent flow
        relroughness = 1E-4 / welldiam
        # 6 iterations to converge
        f1 = 1. / np.power(-2 * np.log10(relroughness / 3.7 + 5.74 / np.power(Rewater, 0.9)), 2.)
        f1 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f1))), 2.)
        f1 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f1))), 2.)
        f1 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f1))), 2.)
        f1 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f1))), 2.)
        f1 = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewater / np.sqrt(f1))), 2.)

    if impedancemodelused:
        # assumed everything stays liquid throughout, calculate well pressure drop [kPa]; /1E3 to convert from Pa to kPa
        DPWell = f1 * (rhowater * v ** 2 / 2) * (depth / welldiam) / 1E3
    else:
        DPWell = []  # it will be calculated elsewhere

    return DPWell, f1, v, rhowater

def ProdPressureDropsAndPumpingPowerUsingImpedenceModel(f3: float, vprod: float, rhowaterinj: float,
                                                        rhowaterprod: float, rhowaterreservoir: float, depth: float,
                                                        wellflowrate: float, prodwelldiam: float,
                                                        impedance: float, nprod: int, waterloss: float,
                                                        pumpeff: float, tilt: float = 90.0,
                                                        trim_neg_to_zero: bool = True) -> tuple:
    """
    Calculate Pressure Drops and Pumping Power needed for the production well using the Impedance Model
        :param f3: friction factor [-]
        :type f3: float
        :param vprod: velocity of the fluid in the production well [m/s]
        :type vprod: float
        :param rhowaterinj: density of the water in the injection well [kg/m3]
        :type rhowaterinj: float
        :param rhowaterreservoir: density of the water in the reservoir [kg/m3]
        :type rhowaterreservoir: float
        :param rhowaterprod: density of the water in the production well [kg/m3]
        :type rhowaterprod: float
        :param depth: depth of the well [m]
        :type depth: float
        :param wellflowrate: flow rate of the fluid in the well [kg/s]
        :type wellflowrate: float
        :param prodwelldiam: diameter of the well [m]
        :type prodwelldiam: float
        :param impedance: impedance of the reservoir [kg/s/kPa]
        :type impedance: float
        :param nprod: number of production wells [-]
        :type nprod: int
        :param waterloss: water loss [-]
        :type waterloss: float
        :param pumpeff: pump efficiency [-]
        :type pumpeff: float
        :param tilt: tilt of the well from the junction box to the bottom of the laterals [degrees]
        :type tilt: float
        :param trim_neg_to_zero: whether to trim negative values of pumping power to zero
        :type trim_neg_to_zero: bool
        :return: tuple of DPOverall, PumpingPower, DPProdWell, DPReserv, DPBouyancy
        :rtype: tuple
    """
    # production well pressure drops [kPa]
    DPProdWell = f3 * (rhowaterprod * vprod ** 2 / 2.) * (depth / prodwelldiam) / 1E3  # /1E3 to convert from Pa to kPa

    # reservoir pressure drop [kPa]
    DPReserv = impedance * nprod * wellflowrate * 1000. / rhowaterreservoir

    # buoyancy pressure drop [kPa]
    gravity_tilt = 9.81 * np.sin(np.radians(tilt))
    DPBouyancy = (rhowaterprod - rhowaterinj) * depth * gravity_tilt / 1E3  # /1E3 to convert from Pa to kPa

    # overall pressure drop
    DPOverall = DPReserv + DPProdWell + DPBouyancy

    # calculate pumping power [MWe] (approximate)
    PumpingPower = ([0.0] * len(vprod))
    PumpingPower = DPOverall * nprod * wellflowrate * (1 + waterloss) / rhowaterinj / pumpeff / 1E3

    # in GEOPHIRES v1.2, negative pumping power values become zero (b/c we are not generating electricity)
    if trim_neg_to_zero:
        PumpingPower = [0. if x < 0. else x for x in PumpingPower]

    return DPOverall, PumpingPower, DPProdWell, DPReserv, DPBouyancy


def InjPressureDropsAndPumpingPowerUsingImpedenceModel(f1: float, vinj: float, rhowaterinj: float, depth: float,
                                                       wellflowrate: float, injwelldiam: float, ninj: int,
                                                       waterloss: float, pumpeff: float, DPOverall) -> tuple:
    """
    Calculate Injection well Pressure Drops and Pumping Power needed for the injection well using the Impedance Model
        :param f1: friction factor [-]
        :type f1: float
        :param vinj: velocity of the fluid in the injection well [m/s]
        :type vinj: float
        :param rhowaterinj: density of the water in the injection well [kg/m3]
        :type rhowaterinj: float
        :param depth: depth of the well [m]
        :type depth: float
        :param wellflowrate: flow rate of the fluid in the well [kg/s]
        :type wellflowrate: float
        :param injwelldiam: diameter of the well [m]
        :type injwelldiam: float
        :param ninj: number of injection wells [-]
        :type ninj: int
        :param waterloss: water loss [-]
        :type waterloss: float
        :param pumpeff: pump efficiency [-]
        :type pumpeff: float
        :param DPOverall: overall pressure drop [kPa]
        :type DPOverall: float
        :return: tuple of newDPOverall, PumpingPower, DPInjWell [kPa]
        :rtype: tuple
    """
    # Calculate Pressure Drops and Pumping Power needed for the injection well using the Impedance Model
    # injection well pressure drops [kPa]
    DPInjWell = f1 * (rhowaterinj * vinj ** 2 / 2) * (depth / injwelldiam) / 1E3  # /1E3 to convert from Pa to kPa

    # overall pressure drop
    newDPOverall = DPOverall + DPInjWell

    # calculate pumping power [MWe] (approximate)
    PumpingPower = newDPOverall * ninj * wellflowrate * (1 + waterloss) / rhowaterinj / pumpeff / 1E3

    # in GEOPHIRES v1.2, negative pumping power values become zero (b/c we are not generating electricity)
    PumpingPower = [0. if x < 0. else x for x in PumpingPower]

    return newDPOverall, PumpingPower, DPInjWell

def get_hydrostatic_pressure_kPa(
        Trock_degC: float,
        Tsurf_degC: float,
        depth_m: float,
        gradient_C_per_km: float,
        lithostatic_pressure: PlainQuantity) -> float:
    """
    Correlation cited as being from Xie, Bloomfield, and Shook in
    https://workingincaes.inl.gov/SiteAssets/CAES%20Files/FORGE/inl_ext-16-38751%20GETEM%20User%20Manual%20Final.pdf
    """
    CP = 4.64E-7
    CT = 9E-4 / (30.796 * Trock_degC ** (-0.552))
    return 0 + 1. / CP * (math.exp(
        density_water_kg_per_m3(Tsurf_degC, pressure=lithostatic_pressure) * 9.81 * CP / 1000 * (
            depth_m - CT / 2 * gradient_C_per_km * depth_m ** 2)) - 1)


def ProdPressureDropAndPumpingPowerUsingIndexes(
        model: Model,
        productionwellpumping: bool,
        usebuiltinppwellheadcorrelation: bool,
        Trock_degC: float,
        depth_m: float,
        ppwellhead_kPa: float,
        PI_kg_per_sec_per_bar: float,
        wellflowrate_kg_per_sec: float,
        f3: float,
        vprod_m: float,
        prodwelldiam_m: float,
        nprod: int,
        pumpeff: float,
        rhowaterprod_kg_per_m3: float) -> tuple:
    """
    Calculate Pressure Drops and Pumping Power needed for the production well using indexes
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param productionwellpumping: whether or not the production well is pumping (True or False) [-]
        :type productionwellpumping: bool
        :param usebuiltinppwellheadcorrelation: whether or not to use the built-in wellhead pressure correlation (True or False) [-]
        :type usebuiltinppwellheadcorrelation: bool
        :param Trock_degC: rock temperature [C]
        :type Trock_degC: float
        :param depth_m: depth of the well [m]
        :type depth_m: float
        :param ppwellhead_kPa: production wellhead pressure [kPa]
        :type ppwellhead_kPa: float
        :param PI_kg_per_sec_per_bar: productivity index [kg/s/bar]
        :type PI_kg_per_sec_per_bar: float
        :param wellflowrate_kg_per_sec: flow rate of the fluid in the well [kg/s]
        :type wellflowrate_kg_per_sec: float
        :param f3: friction factor [-]
        :type f3: float
        :param vprod_m: velocity of the fluid in the production well [m/s]
        :type vprod_m: float
        :param prodwelldiam_m: diameter of the well [m]
        :type prodwelldiam_m: float
        :param nprod: number of production wells [-]
        :type nprod: int
        :param pumpeff: pump efficiency [-]
        :type pumpeff: float
        :param rhowaterprod_kg_per_m3: density of the water in the production well [kg/m3]
        :type rhowaterprod_kg_per_m3: float
        :return: tuple of PumpingPower, PumpingPowerProd, DPProdWell, Pprodwellhead [kPa]
        :rtype: tuple
    """
    # initialize PumpingPower value in case it doesn't get set.
    PumpingPower = PumpingPowerProd = DPProdWell = Pprodwellhead = ([0.0] * len(vprod_m))

    # reservoir hydrostatic pressure
    Phydrostaticcalc_kPa = model.wellbores.production_reservoir_pressure.quantity().to('kPa').magnitude

    if productionwellpumping:
        # Excess pressure covers non-condensable gas pressure and net positive suction head for the pump
        Pexcess_kPa = 344.7  # = 50 psi

        # Minimum production pump inlet pressure and minimum wellhead pressure
        if Trock_degC < 373.9:
            Pminimum_kPa = vapor_pressure_water_kPa(Trock_degC) + Pexcess_kPa
        else:
            # Above the critical water temperature, vapor no longer occurs and vapor pressure can no longer be
            # calculated. A "dummy" vapor pressure can be assumed as the fluid phase no longer impacts the pump depth.
            Pminimum_kPa = 100 # 1 bar = 100 kPa

        if usebuiltinppwellheadcorrelation:
            Pprodwellhead = Pminimum_kPa  # production wellhead pressure [kPa]
        else:
            Pprodwellhead = ppwellhead_kPa
            if Pprodwellhead < Pminimum_kPa:
                msg = (f'Provided production wellhead pressure ({Pprodwellhead:.3f} kPa) '
                       f'under minimum pressure ({Pminimum_kPa:.3f} kPa). '
                       f'GEOPHIRES will assume minimum wellhead pressure.')

                Pprodwellhead = Pminimum_kPa

                print(f'Warning: {msg}')
                model.logger.warning(msg)

        PI_kPa = PI_kg_per_sec_per_bar / 100.0  # convert PI from kg/s/bar to kg/s/kPa

        # calculate pumping depth
        pumpdepth_m = depth_m + (Pminimum_kPa - Phydrostaticcalc_kPa + wellflowrate_kg_per_sec / PI_kPa) / (
            f3 * (rhowaterprod_kg_per_m3 * vprod_m ** 2 / 2.) * (
            1 / prodwelldiam_m) / 1E3 + rhowaterprod_kg_per_m3 * 9.81 / 1E3)
        pumpdepthfinal_m = np.max(pumpdepth_m)
        if pumpdepthfinal_m < 0.0:
            pumpdepthfinal_m = 0.0
            msg = (f'GEOPHIRES calculates negative production well pumping depth. ({pumpdepthfinal_m:.2f}m). '
                   f'No production well pumps will be assumed')
            print(f'Warning: {msg}')
            model.logger.warning(msg)
        elif pumpdepthfinal_m > 600.0:
            msg = (f'GEOPHIRES calculates production pump depth to be deeper than 600m ({pumpdepthfinal_m:.2f}m). '
                   f'Verify reservoir pressure, production well flow rate and production well dimensions')
            model.logger.warning(msg)

        # calculate production well pumping pressure [kPa]
        DPProdWell = Pprodwellhead - (
            Phydrostaticcalc_kPa - wellflowrate_kg_per_sec / PI_kPa - rhowaterprod_kg_per_m3 * 9.81 * depth_m / 1E3 - f3 *
            (rhowaterprod_kg_per_m3 * vprod_m ** 2 / 2.) * (depth_m / prodwelldiam_m) / 1E3)
        # [MWe] total pumping power for production wells
        PumpingPowerProd = DPProdWell * nprod * wellflowrate_kg_per_sec / rhowaterprod_kg_per_m3 / pumpeff / 1E3
        PumpingPowerProd = np.array([0. if x < 0. else x for x in PumpingPowerProd])

    # total pumping power
    if productionwellpumping:
        PumpingPower = PumpingPowerProd

    # negative pumping power values become zero (b/c we are not generating electricity)
    PumpingPower = [max(x, 0.) for x in PumpingPower]

    return PumpingPower, PumpingPowerProd, DPProdWell, Pprodwellhead


def InjPressureDropAndPumpingPowerUsingIndexes(
        model: Model,
        productionwellpumping: bool,
        usebuiltinppwellheadcorrelation: bool,
        usebuiltinoutletplantcorrelation: bool,
        Trock_degC: float,
        depth_m: float,
        ppwellhead: float,
        II: float,
        wellflowrate: float,
        f1: float,
        vinj: float,
        injwelldiam: float,
        nprod: int,
        ninj: int,
        waterloss: float,
        pumpeff: float,
        rhowaterinj: float,
        Pplantoutlet: float) -> tuple:
    """
     Calculate PressureDrops and Pumping Power needed for the injection well using indexes
        :param depth_m: depth of the well [m]
        :type depth_m: float
        :param wellflowrate: flow rate of the fluid in the well [kg/s]
        :type wellflowrate: float
        :param pumpeff: pump efficiency [-]
        :type pumpeff: float
        :param nprod: number of production wells [-]
        :type nprod: int
        :param ppwellhead: production wellhead pressure [kPa]
        :type ppwellhead: float
        :param Trock_degC: rock temperature [C]
        :type Trock_degC: float
        :param usebuiltinppwellheadcorrelation: whether to use the built-in wellhead pressure correlation (True or False) [-]
        :type usebuiltinppwellheadcorrelation: bool
        :param productionwellpumping: whether the production well is pumping (True or False) [-]
        :type productionwellpumping: bool
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param Pplantoutlet: plant outlet pressure [kPa]
        :type Pplantoutlet: float
        :param rhowaterinj: density of the water in the injection well [kg/m3]
        :type rhowaterinj: float
        :param waterloss: water loss [-]
        :type waterloss: float
        :param ninj: number of injection wells [-]
        :type ninj: int
        :param injwelldiam: diameter of the well [m]
        :type injwelldiam: float
        :param vinj: velocity of the fluid in the injection well [m/s]
        :type vinj: float
        :param f1: friction factor [-]
        :type f1: float
        :param usebuiltinoutletplantcorrelation: whether or not to use the built-in outlet plant pressure correlation (True or False) [-]
        :type usebuiltinoutletplantcorrelation: bool
        :param II: injectivity index [kg/s/bar]
        :type II: float
        :return: tuple of PumpingPowerInj, DPInjWell, plant_outlet_pressure, Pprodwellhead [kPa]
        :rtype: tuple
    """
    PumpingPowerInj = DPInjWell = Pprodwellhead = [0.0]  # initialize value in case it doesn't get set.

    # reservoir hydrostatic pressure
    Phydrostaticcalc_kPa = model.wellbores.injection_reservoir_pressure.value

    if productionwellpumping:
        # Excess pressure covers non-condensable gas pressure and net positive suction head for the pump
        Pexcess_kPa = 344.7  # = 50 psi

        # Minimum production pump inlet pressure and minimum wellhead pressure
        if Trock_degC < 373.9:
            Pminimum_kPa = vapor_pressure_water_kPa(Trock_degC) + Pexcess_kPa
        else:
            # Above the critical water temperature, vapor no longer occurs and vapor pressure can no longer be
            # calculated. A "dummy" vapor pressure can be assumed as the fluid phase no longer impacts the pump depth.
            Pminimum_kPa = 100  # setting artificially to 1 bar = 100 kPa
        if usebuiltinppwellheadcorrelation:
            Pprodwellhead = Pminimum_kPa  # production wellhead pressure [kPa]
        else:
            Pprodwellhead = ppwellhead
            if Pprodwellhead < Pminimum_kPa:
                Pprodwellhead = Pminimum_kPa
                msg = (f'Provided production wellhead pressure ({Pprodwellhead:.2f} kPa) under minimum pressure '
                       f'({Pminimum_kPa:.2f} kPa). '
                       f'GEOPHIRES will assume minimum wellhead pressure.')
                print(f'Warning: {msg}')
                model.logger.warning(msg)

    IIkPa = II / 100.0  # convert II from kg/s/bar to kg/s/kPa

    # necessary injection wellhead pressure [kPa]
    Pinjwellhead = [0] * len(Phydrostaticcalc_kPa)
    for i in range(len(Phydrostaticcalc_kPa)):
        Pinjwellhead[i] = (Phydrostaticcalc_kPa[i] +
                        wellflowrate * (1 + waterloss) * nprod / ninj / IIkPa -
                        rhowaterinj[i] * 9.81 * depth_m / 1E3 + f1[i] *
                        (rhowaterinj[i] * vinj[i] ** 2 / 2) * (depth_m / injwelldiam) / 1E3)

    # plant outlet pressure [kPa]
    if usebuiltinoutletplantcorrelation:
        DPSurfaceplant = 68.95  # [kPa] assumes 10 psi pressure drop in surface equipment
        Pplantoutlet = Pprodwellhead - DPSurfaceplant

    # injection pump pressure [kPa]
    DPInjWell = [0.0] * len(Phydrostaticcalc_kPa)
    for i in range(len(DPInjWell)):
        DPInjWell[i] = Pinjwellhead[i] - Pplantoutlet

    # [MWe] total pumping power for injection wells
    PumpingPowerInj = [0.0] * len(DPInjWell)
    for i in range(len(DPInjWell)):
        PumpingPowerInj[i] = DPInjWell[i] * nprod * wellflowrate * (1 + waterloss) / rhowaterinj[i] / pumpeff / 1E3
    PumpingPowerInj = np.array([0. if x < 0. else x for x in PumpingPowerInj])

    return PumpingPowerInj, DPInjWell, Pplantoutlet, Pprodwellhead


class WellBores:
    def __init__(self, model: Model):
        """
        The __init__ function is the constructor for a class.  It is called whenever an instance of the class is created.
        The __init__ function can take arguments, but self is always the first one. Self refers to the instance of the
         object that has already been created, and it's used to access variables that belong to that object.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: Nothing, and is used to initialize the class
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')
        self.rhowaterprod = self.rhowaterinj = 0.0

        # Set up all the Parameters that will be predefined by this class using the different types of parameter classes.
        # Setting up includes giving it a name, a default value, The Unit Type (length, volume, temperature, etc.)
        # and Unit Name of that value, sets it as required (or not), sets allowable range, the error message
        # if that range is exceeded, the ToolTip Text, and the name of teh class that created it.
        # This includes setting up temporary variables that will be available to all the class but noy read in by user,
        # or used for Output
        # This also includes all Parameters that are calculated and then published using the Printouts function.
        # If you choose to subclass this master class, you can do so before or after you create your own parameters.
        # If you do, you can also choose to call this method from you class, which will effectively add and set all
        # these parameters to your class.

        # These dictionaries contain a list of all the parameters set in this object, stored as "Parameter" and
        # OutputParameter Objects.  This will allow us later to access them in a user interface and get that list,
        # along with unit type, preferred units, etc.
        self.ParameterDict = {}
        self.OutputParameterDict = {}

        max_doublets = 200
        # noinspection SpellCheckingInspection
        self.nprod = self.ParameterDict[self.nprod.Name] = intParameter(
            "Number of Production Wells",
            DefaultValue=2,
            AllowableRange=list(range(1, max_doublets+1, 1)),
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default number of production wells (2)",
            ToolTipText="Number of (identical) production wells"
        )
        # noinspection SpellCheckingInspection
        self.ninj = self.ParameterDict[self.ninj.Name] = intParameter(
            "Number of Injection Wells",
            DefaultValue=2,
            AllowableRange=list(range(0, max_doublets+1, 1)),
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default number of injection wells (2)",
            ToolTipText="Number of (identical) injection wells"
        )
        self.doublets_count = self.ParameterDict[self.doublets_count.Name] = intParameter(
            "Number of Doublets",
            DefaultValue=2,
            AllowableRange=list(range(0, max_doublets+1, 1)),
            UnitType=Units.NONE,
            ToolTipText="Pass this parameter to set the Number of Production Wells and Number of Injection Wells to "
                        "same value."
        )
        # noinspection SpellCheckingInspection
        self.ninj_per_production_well = self.ParameterDict[self.ninj_per_production_well.Name] = floatParameter(
            "Number of Injection Wells per Production Well",
            DefaultValue=1,
            Min=0,
            Max=max_doublets-1,
            UnitType=Units.NONE,
            Required=False,
            ToolTipText="Number of (identical) injection wells per production well. "
                        "For example, provide 0.666 to specify a 3:2 production:injection well ratio. "
                        "The number of injection wells will be rounded up to the nearest integer."
        )

        # noinspection SpellCheckingInspection
        self.prodwelldiam = self.ParameterDict[self.prodwelldiam.Name] = floatParameter(
            "Production Well Diameter",
            DefaultValue=8.0,
            Min=1.,
            Max=30.,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.INCHES,
            CurrentUnits=LengthUnit.INCHES,
            Required=True,
            ErrMessage="assume default production well diameter (8 inch)",
            ToolTipText='Inner diameter of production wellbore (assumed constant along the wellbore) to calculate '
                        'frictional pressure drop and wellbore heat transmission with Rameys model'
        )
        # noinspection SpellCheckingInspection
        self.injwelldiam = self.ParameterDict[self.injwelldiam.Name] = floatParameter(
            "Injection Well Diameter",
            DefaultValue=8.0,
            Min=1.,
            Max=30.,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.INCHES,
            CurrentUnits=LengthUnit.INCHES,
            Required=True,
            ErrMessage="assume default injection well diameter (8 inch)",
            ToolTipText='Inner diameter of injection wellbore (assumed constant along the wellbore) to calculate '
                        'frictional pressure drop and wellbore heat transmission with Rameys model'
        )
        self.rameyoptionprod = self.ParameterDict[self.rameyoptionprod.Name] = boolParameter(
            "Ramey Production Wellbore Model",
            DefaultValue=True,
            UnitType=Units.NONE,
            Required=True,
            ErrMessage="assume default production wellbore model (Ramey model active)",
            ToolTipText="Select whether to use Rameys model to estimate the geofluid temperature drop in the "
                        "production wells"
        )
        self.tempdropprod = self.ParameterDict[self.tempdropprod.Name] = floatParameter(
            "Production Wellbore Temperature Drop",
            DefaultValue=5.0,
            Min=-5.,
            Max=50.,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            ErrMessage="assume default production wellbore temperature drop (5 deg.C)",
            ToolTipText="Specify constant production well geofluid temperature drop in case Rameys model is disabled."
        )
        self.tempgaininj = self.ParameterDict[self.tempgaininj.Name] = floatParameter(
            "Injection Wellbore Temperature Gain",
            DefaultValue=0.0,
            Min=-5.,
            Max=50.,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            ErrMessage="assume default injection wellbore temperature gain (0 deg.C)",
            ToolTipText="Specify constant injection well geofluid temperature gain."
        )
        self.prodwellflowrate = self.ParameterDict[self.prodwellflowrate.Name] = floatParameter(
            "Production Flow Rate per Well",
            DefaultValue=50.0,
            Min=1.,
            Max=500.,
            UnitType=Units.FLOWRATE,
            PreferredUnits=FlowRateUnit.KGPERSEC,
            CurrentUnits=FlowRateUnit.KGPERSEC,
            ErrMessage="assume default flow rate per production well (50 kg/s)",
            ToolTipText="Geofluid flow rate per production well."
        )
        self.impedance = self.ParameterDict[self.impedance.Name] = floatParameter(
            "Reservoir Impedance",

            # Note default/input value units are converted as a special case in read_parameters; see
            # https://github.com/NREL/GEOPHIRES-X/blob/d51eb8d1dc8b21c7a79c4d35f296d740347658e0/src/geophires_x/WellBores.py#L1280-L1282
            DefaultValue=1000.0,

            Min=1E-4,
            Max=1E4,
            UnitType=Units.IMPEDANCE,
            PreferredUnits=ImpedanceUnit.GPASPERM3,
            CurrentUnits=ImpedanceUnit.GPASPERM3,
            ErrMessage="assume default reservoir impedance (0.1 GPa*s/m^3)",
            ToolTipText='Reservoir resistance to flow per well-pair. '
                        'For EGS-type reservoirs when the injection well is in hydraulic communication with the '
                        'production well, this parameter specifies the overall pressure drop in the reservoir between '
                        'injection well and production well (see docs)'
        )

        well_separation_default_value_m = 1000
        well_separation_default_unit = LengthUnit.INCHES
        well_separation_preferred_unit = LengthUnit.METERS
        well_separation_unit_mismatch_note = (f'. (Note that the default unit is '
                                              f'{well_separation_default_unit.name.lower()}.)'
                                              if well_separation_default_unit != well_separation_preferred_unit else '')
        # noinspection SpellCheckingInspection
        self.wellsep = self.ParameterDict[self.wellsep.Name] = floatParameter(
            "Well Separation",
            DefaultValue=int(quantity(well_separation_default_value_m, 'm')
                             .to(well_separation_default_unit.value).magnitude),
            Min=10.,
            Max=int(quantity(10000, 'm').to(well_separation_default_unit.value).magnitude),
            UnitType=Units.LENGTH,
            PreferredUnits=well_separation_preferred_unit,
            CurrentUnits=well_separation_default_unit,
            ErrMessage=f'assume default well separation ({well_separation_default_value_m} m)',
            ToolTipText=f'Well separation for built-in TOUGH2 doublet reservoir model'
                        f'{well_separation_unit_mismatch_note}'
        )

        self.Tinj = self.ParameterDict[self.Tinj.Name] = floatParameter(
            "Injection Temperature",
            DefaultValue=70.0,
            Min=0.,
            Max=200.,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            Required=True,
            ErrMessage="assume default injection temperature (70 deg.C)",
            ToolTipText="Constant geofluid injection temperature at injection wellhead."
        )
        self.Phydrostatic = self.ParameterDict[self.Phydrostatic.Name] = floatParameter(
            "Reservoir Hydrostatic Pressure",
            DefaultValue=29430, # Calculated from example1
            Min=1E2,
            Max=1E5,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL,
            ErrMessage="calculate reservoir hydrostatic pressure using built-in correlation",
            ToolTipText="Reservoir hydrostatic far-field pressure.  Default value is calculated with built-in modified "
                        "Xie-Bloomfield-Shook equation (DOE, 2016)."
        )
        self.ppwellhead = self.ParameterDict[self.ppwellhead.Name] = floatParameter(
            "Production Wellhead Pressure",
            DefaultValue=101.3200 + 344.7,
            Min=0.0,
            Max=1E4,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL,
            ErrMessage="using Water vapor pressure (101.3200; at 100 C) + 344.7 kPa (50 psi).",
            ToolTipText="Constant production wellhead pressure; Required if specifying productivity index"
        )
        self.II = self.ParameterDict[self.II.Name] = floatParameter(
            "Injectivity Index",
            DefaultValue=10.0,
            Min=1E-2,
            Max=1E4,
            UnitType=Units.INJECTIVITY_INDEX,
            PreferredUnits=InjectivityIndexUnit.KGPERSECPERBAR,
            CurrentUnits=InjectivityIndexUnit.KGPERSECPERBAR,
            ErrMessage="assume default injectivity index (10 kg/s/bar)",
            ToolTipText="Injectivity index defined as ratio of injection well flow rate over injection well outflow "
                        "pressure drop (flowing bottom hole pressure - hydrostatic reservoir pressure)."
        )
        self.PI = self.ParameterDict[self.PI.Name] = floatParameter(
            "Productivity Index",
            DefaultValue=10.0,
            Min=1E-2,
            Max=1E4,
            UnitType=Units.PRODUCTIVITY_INDEX,
            PreferredUnits=ProductivityIndexUnit.KGPERSECPERBAR,
            CurrentUnits=ProductivityIndexUnit.KGPERSECPERBAR,
            ErrMessage="assume default productivity index (10 kg/s/bar)",
            ToolTipText="Productivity index defined as ratio of production well flow rate over production well inflow "
                        "pressure drop (see docs)"
        )
        self.maxdrawdown = self.ParameterDict[self.maxdrawdown.Name] = floatParameter(
            "Maximum Drawdown",
            DefaultValue=1.0,
            Min=0.0,
            Max=1.000001,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default maximum drawdown (1)",
            ToolTipText="Maximum allowable thermal drawdown before redrilling of all wells into new reservoir "
                        "(most applicable to EGS-type reservoirs with heat farming strategies). E.g. a value of 0.2 "
                        "means that all wells are redrilled after the production temperature (at the wellhead) has "
                        "dropped by 20% of its initial temperature"
        )
        self.IsAGS = self.ParameterDict[self.IsAGS.Name] = boolParameter(
            "Is AGS",
            DefaultValue=False,
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default is not AGS",
            ToolTipText="Set to true if the model is for an Advanced Geothermal System (AGS)"
        )
        self.overpressure_percentage = self.ParameterDict[self.overpressure_percentage.Name] = floatParameter(
            "Overpressure Percentage",
            DefaultValue=100.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            Required=False,
            ErrMessage="assume there is no overpressure",
            ToolTipText="enter the amount of pressure over the hydrostatic pressure in the reservoir (100%=hydrostatic)"
        )
        self.overpressure_depletion_rate = self.ParameterDict[self.overpressure_depletion_rate.Name] = floatParameter(
            "Overpressure Depletion Rate",
            DefaultValue=0.0,
            UnitType=Units.DECAY_RATE,
            PreferredUnits=Decay_RateUnit.PERCENTPERYEAR,
            CurrentUnits=Decay_RateUnit.PERCENTPERYEAR,
            Required=False,
            ErrMessage="assume there is no overpressure",
            ToolTipText="enter the amount of pressure over the hydrostatic pressure in the reservoir (100%=hydrostatic)"
        )
        self.injection_reservoir_temperature = self.ParameterDict[self.injection_reservoir_temperature.Name] = floatParameter(
            "Injection Reservoir Temperature",
            DefaultValue=100.0,
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS,
            Required=False,
            ErrMessage="assume there is not an injection reservoir, so there is no injection reservoir temperature",
            ToolTipText="enter the temperature of the injection reservoir (100 C)"
        )
        self.injection_reservoir_depth = self.ParameterDict[self.injection_reservoir_depth.Name] = floatParameter(
            "Injection Reservoir Depth",
            DefaultValue=1000.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS,
            Required=False,
            ErrMessage="assume there is not an injection reservoir, so there is no injection reservoir depth",
            ToolTipText="enter the depth of the injection reservoir (1000 m)"
        )
        self.injection_reservoir_initial_pressure = self.ParameterDict[self.injection_reservoir_initial_pressure.Name] = floatParameter(
            "Injection Reservoir Initial Pressure",
            DefaultValue=0.0,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL,
            Required=False,
            ErrMessage="assume there is not an injection reservoir, so there is no injection reservoir initial "
                       "pressure",
            ToolTipText="enter the depth of the injection reservoir initial pressure (use lithostatic pressure)"
        )
        self.injection_reservoir_inflation_rate = self.ParameterDict[self.injection_reservoir_inflation_rate.Name] = floatParameter(
            "Injection Reservoir Inflation Rate",
            DefaultValue=1000.0,
            UnitType=Units.INFLATION_RATE,
            CurrentUnits=Inflation_RateUnit.KPASCALPERYEAR,
            Required=False,
            ErrMessage="assume there is not an injection reservoir, so there is no injection reservoir inflation rate",
            ToolTipText="enter the rate at which the pressure increases per year in the injection reservoir "
                        "(1000 kPa/yr)"
        )
        # This is a alias for "Well Geometry Configuration" - putting it here for backwards compatibility
        self.Configuration = self.ParameterDict[self.Configuration.Name] = intParameter(
            "Closed-loop Configuration",
            DefaultValue=Configuration.VERTICAL.int_value,
            AllowableRange=[1, 2, 3, 4, 5],
            ValuesEnum=Configuration,
            UnitType=Units.NONE,
            Required=True,
            ErrMessage="assume simple vertical well (3)",
            ToolTipText = '; '.join([f'{it.int_value}: {it.value}' for it in Configuration])
        )
        # This is a alias for "Closed-loop Configuration" - putting it here for backwards compatibility
        self.Configuration = self.ParameterDict[self.Configuration.Name] = intParameter(
            "Well Geometry Configuration",
            DefaultValue=Configuration.VERTICAL.int_value,
            AllowableRange=[1, 2, 3, 4, 5],
            ValuesEnum=Configuration,
            UnitType=Units.NONE,
            Required=True,
            ErrMessage="assume simple vertical well (3)",
            ToolTipText='; '.join([f'{it.int_value}: {it.value}' for it in Configuration])
        )

        self.WaterThermalConductivity = self.ParameterDict[self.WaterThermalConductivity.Name] = floatParameter(
            "Water Thermal Conductivity",
            DefaultValue=0.6,
            Min=0.0,
            Max=100.0,
            UnitType=Units.THERMAL_CONDUCTIVITY,
            PreferredUnits=ThermalConductivityUnit.WPERMPERK,
            CurrentUnits=ThermalConductivityUnit.WPERMPERK,
            ErrMessage="assume default for water thermal conductivity (0.6 W/m/K)",
            ToolTipText="Water Thermal Conductivity"
        )

        self.Fluid = self.ParameterDict[self.Fluid.Name] = intParameter(
            "Heat Transfer Fluid",
            DefaultValue=WorkingFluid.WATER.int_value,
            AllowableRange=[1, 2],
            ValuesEnum=WorkingFluid,
            UnitType=Units.NONE,
            Required=True,
            ErrMessage="assume default Heat transfer fluid is water (1)",
            ToolTipText='; '.join([f'{it.int_value}: {it.value}' for it in WorkingFluid])
        )

        # Input data for subsurface condition
        self.Nonvertical_length = self.ParameterDict[self.Nonvertical_length.Name] = floatParameter(
            "Nonvertical Length per Multilateral Section",
            DefaultValue=1000.0,
            Min=50.0,
            Max=20000.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS,
            Required=True,
            ErrMessage="assume default Nonvertical Length per Multilateral Section (1000 m)"
        )

        self.nonverticalwellborediameter = self.ParameterDict[self.nonverticalwellborediameter.Name] = floatParameter(
            "Nonvertical Wellbore Diameter",
            DefaultValue=0.156,
            Min=0.01,
            Max=100.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS,
            ErrMessage="assume default for Non-vertical Wellbore Diameter (0.156 m)",
            ToolTipText="Non-vertical Wellbore Diameter"
        )

        max_allowed_total_wells = max(self.nprod.AllowableRange) + max(self.ninj.AllowableRange)
        max_allowed_laterals_per_well_when_max_wells = 3
        """Arbitrary upper limit, could be increased in future if needed"""

        # noinspection SpellCheckingInspection
        self.numnonverticalsections = self.ParameterDict[self.numnonverticalsections.Name] = intParameter(
            "Number of Multilateral Sections",
            DefaultValue=0,
            AllowableRange=list(range(0, max_allowed_total_wells * max_allowed_laterals_per_well_when_max_wells, 1)),
            UnitType=Units.NONE,
            ErrMessage="assume default for Number of Nonvertical Wellbore Sections (0)",
            ToolTipText='Number of Nonvertical Wellbore Sections, aka laterals or horizontals. '
                        'Note that this is the total number of sections for the entire project and not the number of '
                        'sections per well. For example, a project with 2 injectors and 2 producers with 3 laterals '
                        'per well should set Number of Multilateral Sections = 2 * 2 * 3 = 12.'
        )

        self.NonverticalsCased = self.ParameterDict[self.NonverticalsCased.Name] = boolParameter(
            "Multilaterals Cased",
            DefaultValue=False,
            Required=False,
            Provided=False,
            Valid=True,
            ErrMessage="assume default value (False)",
            ToolTipText="If set to True, casing & cementing are assumed to comprise 50% of drilling costs "
                        "(doubling cost compared to uncased)."
        )

        # local variable initiation
        self.Pinjwellhead = 0.0
        self.usebuiltinhydrostaticpressurecorrelation = True
        self.usebuiltinppwellheadcorrelation = True
        self.Pminimum = 0.0
        sclass = self.__class__.__name__
        self.MyClass = sclass
        self.MyPath = __file__

        # Results - used by other objects or printed in output downstream

        self.injection_well_casing_inner_diameter = self.OutputParameterDict[self.injection_well_casing_inner_diameter.Name] = OutputParameter(
            Name='Injection well casing ID',
            UnitType=self.injwelldiam.UnitType,
            PreferredUnits=self.injwelldiam.PreferredUnits,
            CurrentUnits=self.injwelldiam.CurrentUnits,
            ToolTipText=self.injwelldiam.ToolTipText,
        )
        self.production_well_casing_inner_diameter = self.OutputParameterDict[self.production_well_casing_inner_diameter.Name] = OutputParameter(
            Name='Production well casing ID',
            UnitType=self.prodwelldiam.UnitType,
            PreferredUnits=self.prodwelldiam.PreferredUnits,
            CurrentUnits=self.prodwelldiam.CurrentUnits,
            ToolTipText=self.prodwelldiam.ToolTipText,
        )
        self.production_reservoir_pressure = self.OutputParameterDict[self.production_reservoir_pressure.Name] = OutputParameter(
            Name="Calculated Reservoir Pressure",
            value=self.Phydrostatic.value,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.average_production_reservoir_pressure = self.OutputParameterDict[self.average_production_reservoir_pressure.Name] = OutputParameter(
            Name="Average Reservoir Pressure",
            display_name='Average reservoir pressure',
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.injection_reservoir_pressure = self.OutputParameterDict[self.injection_reservoir_pressure.Name] = OutputParameter(
            Name="Calculated Injection Reservoir Pressure",
            value=-1,
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.redrill = self.OutputParameterDict[self.redrill.Name] = OutputParameter(
            Name="redrill",
            # TODO pivot Name to more user-friendly display name in all contexts if feasible (such as output parameters
            #  documentation, where Name is prepended to ToolTipText, resulting in the documentation entry beginning
            #  clumsily and confusingly with "redrill. The total number of redrilling events [...]")
            display_name='Number of times redrilling',
            UnitType=Units.NONE,
            ToolTipText="The total number of redrilling events triggered when production temperature drops below "
                        "the 'Maximum Drawdown' threshold. In the reservoir simulation, this resets the thermal "
                        "decline curve by repeating the initial production temperature profile. Economically, each "
                        "event incurs the full cost of drilling and stimulating the wellfield. "
                        "The cost of all redrilling events is summed and amortized over the project lifetime as an "
                        "operational expense. "
                        # "This accounts for the heavy capital expenditure (e.g., sidetracking and stimulating "
                        # "laterals into fresh rock) required to access undepleted reservoir volume and sustain "
                        # "target power output."
        )
        self.PumpingPowerProd = self.OutputParameterDict[self.PumpingPowerProd.Name] = OutputParameter(
            Name="PumpingPowerProd",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.PumpingPowerInj = self.OutputParameterDict[self.PumpingPowerInj.Name] = OutputParameter(
            Name="PumpingPowerInj",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.pumpdepth = self.OutputParameterDict[self.pumpdepth.Name] = OutputParameter(
            Name="pumpdepth",
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS
        )
        self.impedancemodelallowed = self.OutputParameterDict[self.impedancemodelallowed.Name] = OutputParameter(
            Name="impedancemodelallowed",
            UnitType=Units.NONE
        )
        self.productionwellpumping = self.OutputParameterDict[self.productionwellpumping.Name] = OutputParameter(
            Name="productionwellpumping",
            value=True,
            UnitType=Units.NONE
        )
        self.impedancemodelused = self.OutputParameterDict[self.impedancemodelused.Name] = OutputParameter(
            Name="impedancemodelused",
            UnitType=Units.NONE
        )
        self.ProdTempDrop = self.OutputParameterDict[self.ProdTempDrop.Name] = OutputParameter(
            Name="Production Well Temperature Drop",
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS
        )
        self.DPOverall = self.OutputParameterDict[self.DPOverall.Name] = OutputParameter(
            Name="Total Pressure Drop",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.DPInjWell = self.OutputParameterDict[self.DPInjWell.Name] = OutputParameter(
            Name="Injection Well Pressure Drop",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.DPReserv = self.OutputParameterDict[self.DPReserv.Name] = OutputParameter(
            Name="Reservoir Pressure Drop",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.DPProdWell = self.OutputParameterDict[self.DPProdWell.Name] = OutputParameter(
            Name="Production Well Pump Pressure Drop",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.DPBouyancy = self.OutputParameterDict[self.DPBouyancy.Name] = OutputParameter(
            Name="Bouyancy Pressure Drop",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.ProducedTemperature = self.OutputParameterDict[self.ProducedTemperature.Name] = OutputParameter(
            Name="Produced Temperature",
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS
        )
        self.PumpingPower = self.OutputParameterDict[self.PumpingPower.Name] = OutputParameter(
            Name="Pumping Power",
            UnitType=Units.POWER,
            PreferredUnits=PowerUnit.MW,
            CurrentUnits=PowerUnit.MW
        )
        self.Pprodwellhead = self.OutputParameterDict[self.Pprodwellhead.Name] = OutputParameter(
            Name="Production wellhead pressure",
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.NonverticalProducedTemperature = self.OutputParameterDict[self.NonverticalProducedTemperature.Name] = OutputParameter(
            Name="Nonvertical Produced Temperature",
            value=[0.0],
            UnitType=Units.TEMPERATURE,
            PreferredUnits=TemperatureUnit.CELSIUS,
            CurrentUnits=TemperatureUnit.CELSIUS
        )
        self.NonverticalPressureDrop = self.OutputParameterDict[self.NonverticalPressureDrop.Name] = OutputParameter(
            Name="Nonvertical Pressure Drop",
            value=[0.0],
            UnitType=Units.PRESSURE,
            PreferredUnits=PressureUnit.KPASCAL,
            CurrentUnits=PressureUnit.KPASCAL
        )
        self.total_drilled_length = self.OutputParameterDict[self.total_drilled_length.Name] = OutputParameter(
            Name="Total length of all drilling",
            value=-1.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.KILOMETERS,
            CurrentUnits=LengthUnit.KILOMETERS
        )
        self.tot_vert_m = self.OutputParameterDict[self.tot_vert_m.Name] = OutputParameter(
            Name="Total length of vertical drilling",
            value=-1.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS
        )
        self.tot_to_junction_m = self.OutputParameterDict[self.tot_to_junction_m.Name] = OutputParameter(
            Name="Total length from lateral junction to base of vertical drilling",
            value=-1.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS
        )
        self.tot_lateral_m = self.OutputParameterDict[self.tot_lateral_m.Name] = OutputParameter(
            Name="Total length of lateral drilling",
            value=-1.0,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.METERS,
            CurrentUnits=LengthUnit.METERS
        )

    def __str__(self):
        return "WellBores"

    def read_parameters(self, model: Model) -> None:
        """
        The read_parameters function reads in the parameters from a dictionary and stores them in the parameters.
        It also handles special cases that need to be handled after a value has been read in and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not).
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')

        # Deal with all the parameter values that the user has provided. They should really only provide values that
        # they want to change from the default values, but they can provide a value that is already set because it is a
        # default value set in __init__. It will ignore those.
        # This also deals with all the special cases that need to be taken care of after a value has been
        # read in and checked.
        # If you choose to subclass this master class, you can also choose to override this method (or not),
        # and if you do, do it before or after you call you own version of this method. If you do, you can also choose
        # to call this method from you class, which can modify all these superclass parameters in your class.


        if len(model.InputParameters) > 0:

            # See https://github.com/NREL/GEOPHIRES-X/issues/278?title=Total+Nonvertical+Length+is+actually+per+section
            deprecated_nonvertical_length_param_name = 'Total Nonvertical Length'
            if deprecated_nonvertical_length_param_name in model.InputParameters:
                model.logger.warning(
                    f'"{deprecated_nonvertical_length_param_name}" parameter name is deprecated, '
                    f'use "{self.Nonvertical_length.Name}" instead')

                if self.Nonvertical_length.Name not in model.InputParameters:
                    model.InputParameters[self.Nonvertical_length.Name] = model.InputParameters[
                        deprecated_nonvertical_length_param_name]
                else:
                    model.logger.warning(
                        f'Ignoring value of "{deprecated_nonvertical_length_param_name}" '
                        f'because it is set by "{self.Nonvertical_length.Name}" instead')

                del model.InputParameters[deprecated_nonvertical_length_param_name]

            # loop through all the parameters that the user wishes to set, looking for parameters that match this object
            for item in self.ParameterDict.items():
                ParameterToModify = item[1]
                key = ParameterToModify.Name.strip()
                if key in model.InputParameters:
                    ParameterReadIn = model.InputParameters[key]
                    ReadParameter(ParameterReadIn, ParameterToModify, model)  # this should handle all non-special cases

                    # handle special cases
                    if ParameterToModify.Name == "Heat Transfer Fluid":
                        self.Fluid.value = WorkingFluid.from_input_string(ParameterReadIn.sValue)

                    # IsAGS is false by default - if it equals 1, then it is true
                    if ParameterToModify.Name == "Ramey Production Wellbore Model":
                        if ParameterReadIn.sValue == '0':
                            ParameterToModify.value = False
                    # Ramey Production Wellbore Model is true by default - if it equals 0, then it is false
                    elif ParameterToModify.Name == "Is AGS":
                        if ParameterReadIn.sValue == '1':
                            ParameterToModify.value = True
                    # impedance: impedance per well pair (input as GPa*s/m^3 and converted to KPa/kg/s
                    # (assuming 1000 for density; density will be corrected for later))
                    elif ParameterToModify.Name == "Reservoir Impedance":
                        # shift it by a constant to make the units right, per line 619 of GEOPHIRES 2:
                        # https://github.com/NREL/GEOPHIRES-v2/blob/08485b98ae02aeb7a5acd972f906b2ea81ae2647/GEOPHIRESv2.py#L610-L619
                        self.impedance.value = self.impedance.value * (1E6 / 1E3)
                        self.impedancemodelused.value = True
                        if self.impedance.Provided is False:
                            self.impedancemodelused.value = False
                    elif ParameterToModify.Name == "Reservoir Hydrostatic Pressure":
                        if ParameterToModify.value == -1:
                            self.usebuiltinhydrostaticpressurecorrelation = True
                        else:
                            self.usebuiltinhydrostaticpressurecorrelation = False
                    elif ParameterToModify.Name == "Production Wellhead Pressure":
                        if ParameterToModify.value == -1.0:
                            self.usebuiltinppwellheadcorrelation = True
                        else:
                            self.usebuiltinppwellheadcorrelation = False
                    elif (ParameterToModify.Name == "Closed-loop Configuration" or
                          ParameterToModify.Name == "Well Geometry Configuration"):  # These two are alias of each other
                        self.Configuration.value = Configuration.from_input_string(ParameterReadIn.sValue)
        else:
            model.logger.info("No parameters read because no content provided")

        coerce_int_params_to_enum_values(self.ParameterDict)

        self._set_well_counts_from_parameters(model)

        model.logger.info(f"read parameters complete {self.__class__.__name__}: {__name__}")

    def _set_well_counts_from_parameters(self, model: Model):
        mutually_exclusive_well_count_params = [self.doublets_count, self.ninj_per_production_well]
        provided_well_count_params = [it for it in mutually_exclusive_well_count_params if it.Provided]
        if len(provided_well_count_params) > 1:
            raise ValueError(f'Only one of [{", ".join([it.Name for it in mutually_exclusive_well_count_params])}] '
                             f'may be provided.')

        def _raise_incompatible_param_error(incompatible_param: intParameter, with_param: intParameter):
            msg = f'{incompatible_param.Name} may not be provided when {with_param.Name} is provided.'
            model.logger.error(msg)
            raise ValueError(msg)

        if self.doublets_count.Provided:
            for num_wells_param in [self.ninj, self.nprod]:
                if num_wells_param.Provided:
                    _raise_incompatible_param_error(num_wells_param, self.doublets_count)

            self.ninj.value = self.doublets_count.value
            self.nprod.value = self.doublets_count.value

        if self.ninj_per_production_well.Provided:
            if self.ninj.Provided:
                _raise_incompatible_param_error(self.ninj, self.ninj_per_production_well)

            self.ninj.value = int(math.ceil(self.nprod.value * self.ninj_per_production_well.value))

    def Calculate(self, model: Model) -> None:
        """
        The Calculate function is where all the calculations are done.
        This function can be called multiple times, and will only recalculate what has changed each time it is called.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: Nothing, but it does make calculations and set values in the model
        """
        model.logger.info(f'Init {self.__class__.__name__}: {__name__}')

        # This is where all the calculations are made using all the values that have been set.
        # If you subclass this class, you can choose to run these calculations before (or after) your calculations,
        # but that assumes you have set all the values that are required for these calculations
        # If you choose to subclass this master class, you can also choose to override this method (or not),
        # and if you do, do it before or after you call you own version of this method.  If you do, you can also
        # choose to call this method from you class, which can effectively run the calculations of the superclass,
        # making all the values available to your methods. but you had better have set all the parameters!

        # calculate the reservoir pressure as a function of time
        if self.usebuiltinhydrostaticpressurecorrelation:
            self.production_reservoir_pressure.value = get_hydrostatic_pressure_kPa(model.reserv.Trock.value, model.reserv.Tsurf.value,
                                                                                model.reserv.depth.quantity().to('m').magnitude,
                                                                                model.reserv.averagegradient.value,
                                                                                model.reserv.hydrostatic_pressure())
        else:
            self.production_reservoir_pressure.value = self.Phydrostatic.quantity().to(self.production_reservoir_pressure.CurrentUnits).magnitude

        self.production_reservoir_pressure.value = ReservoirPressurePredictor(model.surfaceplant.plant_lifetime.value,
                                                                              model.economics.timestepsperyear.value,
                                                                              self.production_reservoir_pressure.value,
                                                                              self.overpressure_percentage.value,
                                                                              self.overpressure_depletion_rate.value)
        self.average_production_reservoir_pressure.value = np.average(self.production_reservoir_pressure.value)

        if self.overpressure_percentage.Provided:
            # if we are doing an overpressure calculation, it is possible that the user has chosen to
            # split the reservoir into two parts - the deeper, overpressured Production Reservoir,
            # and a shallower, lower pressure Injection Reservoir.
            # If so, calculate the injection reservoir pressure as a function of time if overpressure is provided.
            # If the injection reservoir temperature or pressure are not provided, calculate a default for them.
            if self.injection_reservoir_depth.Provided or self.injection_reservoir_inflation_rate.Provided:
                # this means they must be doing a split reservoir -
                # now deal give default values to whatever values they didn't set
                if not self.injection_reservoir_temperature.Provided:
                    self.injection_reservoir_temperature.value = model.reserv.Trock.value
                if not self.injection_reservoir_depth.Provided:
                    self.injection_reservoir_depth.value = model.reserv.depth.value
                if not self.injection_reservoir_temperature.Provided:
                    self.injection_reservoir_temperature.value = (model.reserv.averagegradient.value * self.injection_reservoir_depth.value) + model.reserv.Tsurf.value

                injection_reservoir_static_pressure = quantity(static_pressure_MPa(
                    model.reserv.rhorock.value, self.injection_reservoir_depth.quantity().to('m').magnitude), 'MPa')

                if self.injection_reservoir_pressure.value < 0: # they didn't provide a pressure so assume hydrostatic.
                    self.injection_reservoir_pressure.value = get_hydrostatic_pressure_kPa(self.injection_reservoir_temperature.value,
                                                                                        model.reserv.Tsurf.value,
                                                                                        self.injection_reservoir_depth.value,
                                                                                        model.reserv.averagegradient.value * 1000.0,
                                                                                        injection_reservoir_static_pressure)
            self.injection_reservoir_initial_pressure.value = self.injection_reservoir_pressure.value = get_hydrostatic_pressure_kPa(self.injection_reservoir_temperature.value,
                                                                                   model.reserv.Tsurf.value,
                                                                                   self.injection_reservoir_depth.value,
                                                                                   model.reserv.averagegradient.value,
                                                                                   injection_reservoir_static_pressure)

#            if not self.injection_reservoir_initial_pressure.Provided:
            self.injection_reservoir_pressure.value = InjectionReservoirPressurePredictor(model.surfaceplant.plant_lifetime.value,
                                                                                 model.economics.timestepsperyear.value,
                                                                                 self.injection_reservoir_initial_pressure.value,
                                                                                    self.injection_reservoir_inflation_rate.value)
        else:
            # assume it is the same as the production reservoir pressure if not
            self.injection_reservoir_pressure.value = self.production_reservoir_pressure.value
            self.injection_reservoir_temperature.value = model.reserv.Trock.value
            self.injection_reservoir_depth.value = model.reserv.depth.value

        # special case: production and injection well diameters are input as inches and call calculations
        # assume meters! Check and change if needed, assuming anything > 2 must be talking about inches
        # TODO: heuristic calculation
        if self.injwelldiam.value > 2.0:
            self.injwelldiam.value = self.injwelldiam.value * 0.0254
            self.injwelldiam.CurrentUnits = LengthUnit.METERS
        if self.prodwelldiam.value > 2.0:
            self.prodwelldiam.value = self.prodwelldiam.value * 0.0254
            self.prodwelldiam.CurrentUnits = LengthUnit.METERS

        # calculate wellbore temperature drop
        self.ProdTempDrop.value = self.tempdropprod.value  # if not Ramey, hard code a user-supplied temperature drop.
        if self.rameyoptionprod.value:
            if hasattr(model.reserv, 'InputDepth'):
                d = model.reserv.InputDepth.value
            else:
                d = model.reserv.depth.value
            self.ProdTempDrop.value = RameyCalc(model.reserv.krock.value,
                                                model.reserv.rhorock.value,
                                                model.reserv.cprock.value,
                                                self.prodwelldiam.value, model.reserv.timevector.value,
                                                model.surfaceplant.utilization_factor.value,
                                                self.prodwellflowrate.value,
                                                model.reserv.cpwater.value, model.reserv.Trock.value,
                                                model.reserv.Tresoutput.value, model.reserv.averagegradient.value,
                                                d)

        self.ProducedTemperature.value = model.reserv.Tresoutput.value - self.ProdTempDrop.value

        self.calculate_redrilling(model)

        # calculate pressure drops and pumping power
        self.DPProdWell.value, f3, vprod, self.rhowaterprod = WellPressureDrop(
            model, model.reserv.Tresoutput.value - self.ProdTempDrop.value / 4.0, self.prodwellflowrate.value,
            self.prodwelldiam.value, self.impedancemodelused.value, model.reserv.depth.value)
        self.DPInjWell.value, f1, vinj, self.rhowaterinj = InjectionWellPressureDrop(
            model, self.Tinj.value, self.prodwellflowrate.value, self.injwelldiam.value, self.impedancemodelused.value,
            model.reserv.depth.value, self.nprod.value, self.ninj.value, model.reserv.waterloss.value)

        if self.impedancemodelused.value:
            # assumed everything stays liquid throughout, based on TARB in Geophires v1.2
            self.DPOverall.value, self.PumpingPower.value, self.DPProdWell.value, self.DPReserv.value, self.DPBouyancy.value = \
                ProdPressureDropsAndPumpingPowerUsingImpedenceModel(f3, vprod, self.rhowaterinj, self.rhowaterprod,
                                                                    model.reserv.rhowater.value,
                                                                    model.reserv.depth.value,
                                                                    self.prodwellflowrate.value,
                                                                    self.prodwelldiam.value,
                                                                    self.impedance.value, self.nprod.value,
                                                                    model.reserv.waterloss.value,
                                                                    model.surfaceplant.pump_efficiency.value)
            self.DPOverall.value, self.PumpingPower.value, self.DPInjWell.value = \
                InjPressureDropsAndPumpingPowerUsingImpedenceModel(f1, vinj, self.rhowaterinj, model.reserv.depth.value,
                                                                   self.prodwellflowrate.value, self.injwelldiam.value,
                                                                   self.ninj.value, model.reserv.waterloss.value,
                                                                   model.surfaceplant.pump_efficiency.value,
                                                                   self.DPOverall.value)

        else:
            # PI and II are used
            self.PumpingPower.value, self.PumpingPowerProd.value, self.DPProdWell.value, self.Pprodwellhead.value = \
                ProdPressureDropAndPumpingPowerUsingIndexes(model,
                                                            self.productionwellpumping.value,
                                                            self.usebuiltinppwellheadcorrelation,
                                                            model.reserv.Trock.value,
                                                            model.reserv.depth.value,
                                                            self.ppwellhead.value,
                                                            self.PI.value, self.prodwellflowrate.value, f3, vprod,
                                                            self.prodwelldiam.value, self.nprod.value,
                                                            model.surfaceplant.pump_efficiency.value, self.rhowaterprod)
            self.PumpingPowerInj.value, self.DPInjWell.value, model.surfaceplant.plant_outlet_pressure.value, self.Pprodwellhead.value = \
                InjPressureDropAndPumpingPowerUsingIndexes(model,
                                                           self.productionwellpumping.value,
                                                           self.usebuiltinppwellheadcorrelation,
                                                           model.surfaceplant.usebuiltinoutletplantcorrelation.value,
                                                           self.injection_reservoir_temperature.value,
                                                           self.injection_reservoir_depth.value,
                                                           self.ppwellhead.value, self.II.value,
                                                           self.prodwellflowrate.value, f1, vinj,
                                                           self.injwelldiam.value, self.nprod.value,
                                                           self.ninj.value, model.reserv.waterloss.value,
                                                           model.surfaceplant.pump_efficiency.value, self.rhowaterinj,
                                                           model.surfaceplant.plant_outlet_pressure.value)
            # total pumping power
            if self.productionwellpumping.value:
                self.PumpingPower.value = self.PumpingPowerInj.value + self.PumpingPowerProd.value
            else:
                self.PumpingPower.value = self.PumpingPowerInj.value

            # negative pumping power values become zero (b/c we are not generating electricity)
            self.PumpingPower.value = [0. if x < 0. else x for x in self.PumpingPower.value]

        self._sync_output_params_from_input_params()

        model.logger.info(f'complete {self.__class__.__name__}: {__name__}')

    def calculate_redrilling(self, model: Model) -> None:
        # Redrilling applies to the built-in analytical reservoir models and user-provided profile.
        if model.reserv.resoption.value in \
            [ReservoirModel.MULTIPLE_PARALLEL_FRACTURES, ReservoirModel.LINEAR_HEAT_SWEEP,
             ReservoirModel.SINGLE_FRACTURE, ReservoirModel.ANNUAL_PERCENTAGE, ReservoirModel.USER_PROVIDED_PROFILE]:
            index_first_max_drawdown = np.argmax(
                self.ProducedTemperature.value < (1 - model.wellbores.maxdrawdown.value) *
                self.ProducedTemperature.value[0])

            if index_first_max_drawdown > 0:  # redrilling necessary
                self.redrill.value = int(np.floor(len(self.ProducedTemperature.value) / index_first_max_drawdown))
                ProducedTemperatureRepeated = np.tile(self.ProducedTemperature.value[0:index_first_max_drawdown],
                                                      self.redrill.value + 1)
                self.ProducedTemperature.value = ProducedTemperatureRepeated[0:len(self.ProducedTemperature.value)]
                TResOutputRepeated = np.tile(model.reserv.Tresoutput.value[0:index_first_max_drawdown],
                                             self.redrill.value + 1)
                model.reserv.Tresoutput.value = TResOutputRepeated[0:len(self.ProducedTemperature.value)]

    def _sync_output_params_from_input_params(self) -> None:
        """
        Handles setting output parameters whose values are based on 1:1 corresponding input parameters.
        """

        def _set_output_param_from_input_param(input_param: Parameter, output_param: OutputParameter) -> None:
            output_param.value = input_param.quantity().to(output_param.CurrentUnits).magnitude

        # Injection/production well casing ID have same value as inputs but exist as separate output parameters due to
        # having a different display name.
        _set_output_param_from_input_param(self.injwelldiam, self.injection_well_casing_inner_diameter)
        _set_output_param_from_input_param(self.prodwelldiam, self.production_well_casing_inner_diameter)
