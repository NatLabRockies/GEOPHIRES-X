"""
 contains code from Wanju Yuan based on: "Closed-Loop Geothermal Energy Recovery from Deep High Enthalpy Systems"
 ref: Yuan, Wanju, et al. "Closed-loop geothermal energy recovery from deep high enthalpy systems."
 Renewable Energy 177 (2021): 976-991.
 and CLGScode from Koenraad
 ref Beckers, Koenraad, et al. Tabulated Database of Closed-Loop Geothermal Systems Performance for Cloud-Based
 Technical and Economic Modeling of Heat Production and Electricity Generation. No. NREL/CP-5700-84979.
 National Renewable Energy Lab.(NREL), Golden, CO (United States), 2023.
"""
import sys
import os
import math
import numpy as np
from pint.facets.plain import PlainQuantity

import geophires_x.Model as Model
from .Parameter import floatParameter, intParameter, boolParameter, OutputParameter
from geophires_x.GeoPHIRESUtils import density_water_kg_per_m3
from geophires_x.GeoPHIRESUtils import heat_capacity_water_J_per_kg_per_K
from .Units import *
from .OptionList import WorkingFluid, Configuration

import h5py
import scipy
from scipy.interpolate import interpn, interp1d
from scipy import signal
import itertools as itern

from .WellBores import WellBores, RameyCalc, ProdPressureDropAndPumpingPowerUsingIndexes, WellPressureDrop, \
    ProdPressureDropsAndPumpingPowerUsingImpedenceModel

from geophires_x.GeoPHIRESUtils import viscosity_water_Pa_sec

esp2 = 10.0e-10


class data:
    _cache = {}

    @staticmethod
    def _get_cache_key(fname, case, fluid):
        return f'{fname}/{case},{fluid}'

    @staticmethod
    def get(fname, case, fluid):
        cache_key = data._get_cache_key(fname, case, fluid)
        if cache_key in data._cache:
            return data._cache[cache_key]
        else:
            d = data(fname, case, fluid)
            data._cache[cache_key] = d
            return d

    def __init__(self, fname, case, fluid):
        """
        Initialize the data structures for a given case and fluid
        :param fname: h5 file name
        :param case: case name
        :param fluid: fluid name
        :return: None
        """
        self.fluid = fluid
        self.case = case

        with h5py.File(fname, 'r') as file:
            fixed_loc = "/" + case + "/fixed_params/"
            input_loc = "/" + case + "/" + fluid + "/input/"
            output_loc = "/" + case + "/" + fluid + "/output/"

            # independent vars
            self.mdot = file[input_loc + "mdot"][:]  # i0
            self.L2 = file[input_loc + "L2"][:]  # i1
            self.L1 = file[input_loc + "L1"][:]  # i2
            self.grad = file[input_loc + "grad"][:]  # i3
            self.D = file[input_loc + "D"][:]  # i4
            self.Tinj = file[input_loc + "T_i"][:]  # i5
            self.k = file[input_loc + "k_rock"][:]  # i6
            self.time = file[input_loc + "time"][:]  # i7
            self.ivars = (self.mdot, self.L2, self.L1, self.grad, self.D, self.Tinj, self.k, self.time)

            # fixed vars
            self.Pinj = file[fixed_loc + "Pinj"][()]
            self.Tamb = file[fixed_loc + "Tamb"][()]

            # dim = Mdot x L2 x L1 x grad x D x Tinj x k
            self.Wt = file[output_loc + "Wt"][:]  # int mdot * dh dt
            self.We = file[output_loc + "We"][:]  # int mdot * (dh - Too * ds) dt

            self.GWhr = 1e6 * 3_600_000.0

            self.kWe_avg = self.We * self.GWhr / (1000. * self.time[-1] * 86400. * 365.)
            self.kWt_avg = self.Wt * self.GWhr / (1000. * self.time[-1] * 86400. * 365.)

            # dim = Mdot x L2 x L1 x grad x D x Tinj x k x time
            self.shape = (
                len(self.mdot),
                len(self.L2),
                len(self.L1),
                len(self.grad),
                len(self.D),
                len(self.Tinj),
                len(self.k),
                len(self.time))
            self.Tout = self.__uncompress(file, output_loc, "Tout")
            self.Pout = self.__uncompress(file, output_loc, "Pout")

        self.CP_fluid = "CO2"
        if fluid == "H2O":
            self.CP_fluid = "H2O"

    def __uncompress(self, file, output_loc, state):
        U = file[output_loc + state + "/" + "U"][:]
        sigma = file[output_loc + state + "/" + "sigma"][:]
        Vt = file[output_loc + state + "/" + "Vt"][:]
        M_k = np.dot(U, np.dot(np.diag(sigma), Vt))

        shape = self.shape
        valid_runs = np.argwhere(np.isfinite(self.We.flatten()))[:, 0]
        M_k_full = np.full((shape[-1], np.prod(shape[:-1])), np.nan)
        M_k_full[:, valid_runs] = M_k
        return np.reshape(M_k_full.T, shape)

    def interp_outlet_states(self, point):
        """
        Interpolate the outlet states for a given point
        param: point: tuple of (mdot, L2, L1, grad, D, Tinj, k)
        :return: Tout, Pout
        """
        points = list(itern.product(
            (point[0],),
            (point[1],),
            (point[2],),
            (point[3],),
            (point[4],),
            (point[5],),
            (point[6],),
            self.time))
        try:
            Tout = interpn(self.ivars, self.Tout, points)
            Pout = interpn(self.ivars, self.Pout, points)

        except BaseException as ex:
            print(str(ex))
            msg = 'Error: AGSWellBores: interp_outlet_states failed.'
            print(msg)
            raise RuntimeError(msg) from ex
        return Tout, Pout

    def interp_kWe_avg(self, point):
        """
        Interpolate the average heat extraction rate for a given point
        :param point: tuple of (mdot, L2, L1, grad, D, Tinj, k)
        :return: kWe_avg
        """
        ivars = self.ivars[:-1]
        return self.GWhr * interpn(ivars, self.We, point) / (1000. * self.time[-1] * 86400. * 365.)

    def interp_kWt_avg(self, point):
        """
        Interpolate the average heat extraction rate for a given point
        :param point: tuple of (mdot, L2, L1, grad, D, Tinj, k)
        :return: kWt_avg
        """
        ivars = self.ivars[:-1]
        return self.GWhr * interpn(ivars, self.Wt, point) / (1000. * self.time[-1] * 86400. * 365.)



def pointsource(self, yy, zz, yt, zt, ye, ze, alpha, sp, t):
    """
    point source/sink solution functions
    :param yy: y coordinate of the point source/sink (m) (yy = 0) for coaxial wellbore and (yy = 0.078) for U-loop wellbore (m)
    :type yy: float
    :param zz: z coordinate of the point source/sink (m) (zz = 0) for coaxial wellbore and (zz = 0.078) for U-loop wellbore (m)
    :type zz: float
    :param yt: y coordinate of the point source/sink (m) (yt = 0) for coaxial wellbore and (yt = 0.078) for U-loop wellbore (m)
    :type yt: float
    :param zt: z coordinate of the point source/sink (m) (zt = 0) for coaxial wellbore and (zt = 0.078) for U-loop wellbore (m)
    :type zt: float
    :param ye: y coordinate of the point source/sink (m) (ye = 0) for coaxial wellbore and (ye = 0.078) for U-loop wellbore (m)
    :type ye: float
    :param ze: z coordinate of the point source/sink (m) (ze = 0) for coaxial wellbore and (ze = 0.078) for U-loop wellbore (m)
    :type ze: float
    :param alpha: thermal diffusivity (m2/s)
    :type alpha: float
    :param sp: Laplace variable (1/s)
    :type sp: float
    :param t: time (s)
    :type t: float
    :return: z
    :rtype: float
    """
    rhorock_cprock_4 = self.rhorock * self.cprock * 4.0
    theta_yt_minus_yy = thetaY(yt - yy, ye, alpha, t)
    theta_yt_plus_yy = thetaY(yt + yy, ye, alpha, t)
    theta_zt_minus_zz = thetaZ(zt - zz, ze, alpha, t)
    theta_zt_plus_zz = thetaZ(zt + zz, ze, alpha, t)

    z = (1.0 / rhorock_cprock_4) * (theta_yt_minus_yy + theta_yt_plus_yy) * (
        theta_zt_minus_zz + theta_zt_plus_zz) * math.exp(-sp * t)

    return z



def chebeve_pointsource(self, yy, zz, yt, zt, ye, ze, alpha, sp) -> float:
    """
    Chebyshev approximation for numerical Laplace transformation integration from 1e-8 to 1e30
    :param yy: y coordinate of the point source/sink (m) (yy = 0) for coaxial wellbore and (yy = 0.078) for U-loop wellbore (m)
    :type yy: float
    :param zz: z coordinate of the point source/sink (m) (zz = 0) for coaxial wellbore and (zz = 0.078) for U-loop wellbore (m)
    :type zz: float
    :param yt: y coordinate of the point source/sink (m) (yt = 0) for coaxial wellbore and (yt = 0.078) for U-loop wellbore (m)
    :type yt: float
    :param zt: z coordinate of the point source/sink (m) (zt = 0) for coaxial wellbore and (zt = 0.078) for U-loop wellbore (m)
    :type zt: float
    :param ye: y coordinate of the point source/sink (m) (ye = 0) for coaxial wellbore and (ye = 0.078) for U-loop wellbore (m)
    :type ye: float
    :param ze: z coordinate of the point source/sink (m) (ze = 0) for coaxial wellbore and (ze = 0.078) for U-loop wellbore (m)
    :type ze: float
    :param alpha: thermal diffusivity (m2/s)
    :type alpha: float
    :param sp: Laplace variable (1/s)
    :type sp: float
    :return: ???? (need to check)
    :rtype: float
    """
    m = 32
    t_1 = 1.0e-8
    n = int(math.log10(1.0e4 / 1.0e-8) + 1)
    # t_2 = t_1 * 10 ** n
    a = t_1
    temp = 0.0
    for i in range(1, n + 1):
        b = a * 10.0
        temp = temp + Chebyshev(self, a, b, m, yy, zz, yt, zt, ye, ze, alpha, sp, pointsource)
        a = b
    return temp + (1 / sp * (math.exp(-sp * 1.0e5) - math.exp(-sp * 1.0e30))) / (ye * ze) / self.rhorock / self.cprock



def laplace_solution(cls:WellBores, sp, pressure:PlainQuantity) -> float:
    """
    Duhamel convolution method for closed-loop system
    :param sp: Laplace variable (1/s)
    :type sp: float
    :return: Toutletl
    :rtype: float
    :param pressure: Lithostatic pressure, per https://github.com/NREL/GEOPHIRES-X/issues/113#issuecomment-1941951134
    """

    Toutletl = 0.0
    ss = 1.0 / sp / chebeve_pointsource(cls, cls.y_well, cls.z_well, cls.y_well, cls.z_well - 0.078,
                                        cls.y_boundary, cls.z_boundary, cls.alpha_rock, sp)

    Toutletl = (cls.Tini - cls.Tinj.value) / sp * np.exp(
        -sp * ss / cls.q_circulation / 24.0 / density_water_kg_per_m3(
            cls.Tini, pressure=pressure) / heat_capacity_water_J_per_kg_per_K(
            cls.Tini, pressure=pressure) * cls.Nonvertical_length.value - sp / cls.velocity * cls.Nonvertical_length.value)
    return Toutletl


def inverselaplace(cls:WellBores, NL, MM, pressure:PlainQuantity):
    """
    Numerical Laplace transformation algorithm
    :param NL: NL
    :type NL: int
    :param MM: MM
    :type MM: int
    :return: Toutlet
    :rtype: float
    """
    V = np.zeros(50)
    Gi = np.zeros(50)
    H = np.zeros(25)
    DLN2 = 0.6931471805599453
    FI = 0.0
    SN = 0.0
    Az = 0.0
    Z = 0.0

    if NL != MM:
        Gi[1] = 1.0
        NH = NL // 2
        SN = 2.0 * (NH % 2) - 1.0

        for i in range(1, NL + 1):
            Gi[i + 1] = Gi[i] * i

        H[1] = 2.0 / Gi[NH]
        for i in range(1, NH + 1):
            FI = i
            H[i] = math.pow(FI, NH) * Gi[2 * i + 1] / Gi[NH - i + 1] / Gi[i + 1] / Gi[i]

        for i in range(1, NL + 1):
            V[i] = 0.0
            KBG = (i + 1) // 2
            temp = NH if i >= NH else i
            KND = temp
            for k in range(KBG, KND + 1):
                V[i] = V[i] + H[k] / Gi[i - k + 1] / Gi[2 * k - i + 1]
            V[i] = SN * V[i]
            SN = -SN
        MM = NL

    FI = 0.0
    Az = DLN2 / cls.time_operation.value
    Toutlet = 0.0
    for k in range(1, NL + 1):
        Z = Az * k
        Toutletl = laplace_solution(cls, Z, pressure)
        Toutlet += Toutletl * V[k]
    Toutlet = cls.Tini - Az * Toutlet
    return Toutlet


def thetaY(yt, ye, alpha, t):
    coeff = 1.0 / math.sqrt(math.pi * alpha * t)
    y_coeff = yt + 2 * ye

    i = 0
    while True:
        term = abs(coeff * math.exp(-y_coeff * y_coeff / 4.0 / alpha / t))
        if term <= esp2:
            break
        i += 1

    k = -1
    while True:
        term = abs(coeff * math.exp(-y_coeff * y_coeff / 4.0 / alpha / t))
        if term <= esp2:
            break
        k -= 1

    y_values = [coeff * math.exp(-(yt + 2 * j * ye) * (yt + 2 * j * ye) / 4.0 / alpha / t) for j in
                range(i, -1, -1)]
    y1_values = [coeff * math.exp(-(yt + 2 * w * ye) * (yt + 2 * w * ye) / 4.0 / alpha / t) for w in range(k, 0)]
    y = sum(y_values)
    y1 = sum(y1_values)

    return y + y1


def thetaZ(zt, ze, alpha, t):
    coeff = 1.0 / math.sqrt(math.pi * alpha * t)
    z_coeff = zt + 2 * ze

    i = 0
    while True:
        term = abs(coeff * math.exp(-z_coeff * z_coeff / 4.0 / alpha / t))
        if term <= esp2:
            break
        i += 1

    k = -1
    while True:
        term = abs(coeff * math.exp(-z_coeff * z_coeff / 4.0 / alpha / t))
        if term <= esp2:
            break
        k -= 1

    y_values = [coeff * math.exp(-(zt + 2 * j * ze) * (zt + 2 * j * ze) / 4.0 / alpha / t) for j in
                range(i, -1, -1)]
    y1_values = [coeff * math.exp(-(zt + 2 * w * ze) * (zt + 2 * w * ze) / 4.0 / alpha / t) for w in range(k, 0)]
    y = sum(y_values)
    y1 = sum(y1_values)

    return y + y1


def Chebyshev(self, a, b, n, yy, zz, yt, zt, ye, ze, alpha, sp, func):
    """
    Chebyshev approximation for numerical Laplace transformation integration from 1e-8 to 1e30
    :param a: a
    :type a: float
    :param b: b
    :type b: float
    :param n: n
    :type n: int
    :param yy: y coordinate of the point source/sink
    :type yy: float
    :param zz: z coordinate of the point source/sink
    :type zz: float
    :param yt: y coordinate of the point source/sink
    :type yt: float
    :param zt: z coordinate of the point source/sink
    :type zt: float
    :param ye: y coordinate of the point source/sink
    :type ye: float
    :param ze: z coordinate of the point source/sink
    :type ze: float
    :param alpha: thermal diffusivity (m2/s)
    :type alpha: float
    :param sp: Laplace variable (1/s)
    :type sp: float
    :param func: function to be integrated (pointsource)
    :type func: function
    :return: y * d - dd + 0.5 * cint[0]
    :rtype: float
    """
    bma = 0.5 * (b - a)
    bpa = 0.5 * (b + a)
    cos_vals = [math.cos(math.pi * (k + 0.5) / n) for k in range(n)]
    f = []
    for cos_val in cos_vals:
        result = func(self, yy, zz, yt, zt, ye, ze, alpha, sp, cos_val * bma + bpa)
        f.append(result)
    # f = [func(yy, zz, yt, zt, ye, ze, alpha, sp, cos_val * bma + bpa) for cos_val in cos_vals]
    fac = 2.0 / n
    pi_div_n = math.pi / n
    # c = [fac * np.sum([f[k] * math.cos(math.pi * j * (k + 0.5) / n)
    #             for k in range(n)]) for j in range(n)]
    # optimized:
    fac_times_f = [fac * f_k for f_k in f]
    cos_vals = np.cos(np.pi * np.arange(n) * (np.arange(n)[:, np.newaxis] + 0.5) / n)
    c = fac_times_f @ cos_vals
    con = 0.25 * (b - a)
    fac2 = 1.0
    cint = np.zeros(513)
    summ = 0.0
    for j in range(1, n - 1):
        cint[j] = con * (c[j - 1] - c[j + 1]) / j
        summ += fac2 * cint[j]
        fac2 = -fac2
        cint[n - 1] = con * c[n - 2] / (n - 1)
        summ += fac2 * cint[n - 1]
        cint[0] = 2.0 * summ
    d = 0.0
    dd = 0.0
    y = (2.0 * b - a - b) * (1.0 / (b - a))
    y2 = 2.0 * y
    for j in range(n - 1, 0, -1):
        sv = d
        d = y2 * d - dd + cint[j]
        dd = sv
    return y * d - dd + 0.5 * cint[0]  # Last step is different


class AGSWellBores(WellBores):
    """
    AGSWellBores Child class of WellBores; it is the same, but has advanced AGS closed-loop functionality
    """

    def __init__(self, model: Model):
        """
        The __init__ function is the constructor for a class. It is called whenever an instance of the class is created.
        The __init__ function can take arguments, but self is always the first one. Self refers to the instance of the
        object that has already been created, and it's used to access variables that belong to that object.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: Nothing, and is used to initialize the class
        """
        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        # Initialize the superclass first to gain access to those variables
        super().__init__(model)
        sclass = str(__class__).replace("<class \'", "")
        self.MyClass = sclass.replace("\'>", "")
        self.MyPath = os.path.abspath(__file__)
        self.u_H2O = None
        self.timearray = None
        self.u_sCO2 = None
        self.FlowRateVector = 0.0
        self.HorizontalLengthVector = 0.0
        self.DepthVector = 0.0
        self.GradientVector = 0.0
        self.DiameterVector = 0.0
        self.TinVector = 0.0
        self.KrockVector = 0.0
        self.Fluid_name = ""
        self.Pvector = None
        self.Tvector = None
        self.density = None
        self.enthalpy = None
        self.entropy = None
        self.Pvector_ap = None
        self.hvector_ap = None
        self.svector_ap = None
        self.TPh = None
        self.hPs = None
        self.point = None
        self.Tout = None
        self.Pout = None
        self.error = 0
        self.area = 0.0
        self.q_circulation = 0.0
        self.velocity = 0.0
        self.x_boundary = 0.0
        self.y_boundary = 0.0
        self.z_boundary = 2.0e15
        self.y_well = 0.0
        self.z_well = 0.0
        self.al = 0.0
        self.time_max = 0.0
        self.rhorock = 0.0
        self.cprock = 0.0
        self.alpha_rock = 0.0
        self.alpha_fluid = 0.0
        self.InterpolatedTemperatureArray = None
        self.InterpolatedPressureArray = None
        self.krock = 0.0
        self.rhowaterinj = None
        self.rhowaterprod = None

        # Set up the Parameters that will be predefined by this class using the different types of parameter classes.
        # Setting up includes giving it a name, a default value, The Unit Type (length, volume, temperature, etc.) and
        # Unit Name of that value, sets it as required (or not), sets allowable range, the error message if that range
        # is exceeded, the ToolTip Text, and the name of teh class that created it.
        # This includes setting up temporary variables that will be available to all the class but noy read in by user,
        # or used for Output
        # This also includes all Parameters that are calculated and then published using the Printouts function.
        # If you choose to subclass this master class, you can do so before or after you create your own parameters.
        # If you do, you can also choose to call this method from you class, which will effectively add and set all
        # these parameters to your class.
        # NB: inputs we already have ("already have it") need to be set at ReadParameter time so values are set at the
        # last possible time

        # Assume CLGS has 1 lateral by default (Non-CLGS default value is 0)
        self.numnonverticalsections.value = 1
        self.numnonverticalsections.ErrMessage = (f'assume default for Number of Nonvertical Wellbore Sections '
                                                  f'({self.numnonverticalsections.value})')

        self.time_operation = self.ParameterDict[self.time_operation.Name] = floatParameter(
            "Closed Loop Calculation Start Year",
            DefaultValue=0.01,
            Min=0.01,
            Max=100.0,
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default for Closed Loop Calculation Start Year (0.01)",
            ToolTipText="Closed Loop Calculation Start Year"
        )

        # local variable initiation
        # code from Koenraad
        # Filename of h5 database with simulation results [-]
        self.filename = self.MyPath.replace(self.__str__() + ".py", '') + f'CLG Simulator{os.sep}clgs_results_final.h5'
        if self.Fluid.value == WorkingFluid.WATER:
            self.mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py", '') + f'CLG Simulator{os.sep}properties_H2O.mat')
        else:
            self.mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py", '') + f'CLG Simulator{os.sep}properties_CO2v2.mat')
            self.additional_mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py",
                                    '') + f'CLG Simulator{os.sep}additional_properties_CO2v2.mat')

        # results are stored here and in the parent ProducedTemperature array
        self.Tini = 0.0

        model.logger.info(f'complete {__class__!s}: {sys._getframe().f_code.co_name}')

    def __str__(self):
        return 'AGSWellBores'

    def read_parameters(self, model: Model) -> None:
        """
        The read_parameters function reads in the parameters from a dictionary and stores them in the parameters.
        It also handles special cases that need to be handled after a value has been read in and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not), and if you do
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')

        # AGS/CLGS models do not model laterals on a per-vertical-section basis, so the total number of multilateral
        # sections may not be derived from a per-vertical-section value.
        if self.numnonverticalsections_per_vertical_section.Name in model.InputParameters:
            msg = (f'{self.numnonverticalsections_per_vertical_section.Name} is not supported by AGS/CLGS models. '
                   f'Provide {self.numnonverticalsections.Name} instead.')
            model.logger.error(msg)
            raise NotImplementedError(msg)

        super().read_parameters(model)  # read the default parameters
        # if we call super, we don't need to deal with setting the parameters here, just deal with the special cases
        # for the variables in this class because the call to the super.read_parameters will set all the variables,
        # including the ones that are specific to this class

        # handle error checking and special cases:

        if model.reserv.numseg.value > 1:
            msg = ('CLGS model can only handle a single layer gradient segment. '
                   'Number of Segments set to 1, Gradient set to Gradient[0], and Depth set to Reservoir Depth.')
            print(f'Warning: {msg}')
            model.logger.warning(msg)
            model.reserv.numseg.value = 1

        if self.ninj.value > 0:
            msg = ('CLGS model considers the only the production wellbore parameters. '
                   'Anything related to the injection wellbore is ignored.')
            print(f'Warning: {msg}')
            model.logger.warning(msg)

        if self.nprod.value != 1:
            msg = ('CLGS model considers the only a single production wellbore (coaxial or uloop). '
                   'Number of production wellbores set to 1.')
            print(f'Warning: {msg}')
            model.logger.warning(msg)

        # inputs we already have - needs to be set at ReadParameter time so values set at the latest possible time
        self.krock = model.reserv.krock.value  # same units are GEOPHIRES

        model.logger.info(f'complete {str(__class__)}: {sys._getframe().f_code.co_name}')


    def calculatedrillinglengths(self, model) -> tuple:
        """
        returns the total length, vertical length, and horizontal lengths, depending on the configuration
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: total length, vertical length, and horizontal lengths
        :rtype: tuple
        """
        if self.Configuration.value == Configuration.ULOOP:
            # Total drilling depth of both wells and laterals in U-loop [m]
            return ((
                        self.numnonverticalsections.value * self.Nonvertical_length.value) + 2 * model.reserv.InputDepth.value * 1000.0), \
                2 * model.reserv.InputDepth.value * 1000.0, self.numnonverticalsections.value * self.Nonvertical_length.value
        else:
            # Total drilling depth of well and lateral in co-axial case [m]
            return (
                self.Nonvertical_length.value + model.reserv.InputDepth.value * 1000.0), model.reserv.InputDepth.value * 1000.0, \
                self.Nonvertical_length.value

    def initialize(self, model: Model) -> None:
        """
        The initialize function reads values and arrays to be in the format that CLGS model systems expects
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        if self.Fluid.value == WorkingFluid.WATER:
            if self.Configuration.value == Configuration.ULOOP:
                self.u_H2O = data.get(self.filename, Configuration.ULOOP.value, "H2O")
            elif self.Configuration.value == Configuration.COAXIAL:
                self.u_H2O = data.get(self.filename, Configuration.COAXIAL.value, "H2O")
            self.timearray = self.u_H2O.time
            self.FlowRateVector = self.u_H2O.mdot  # length of 26
            self.HorizontalLengthVector = self.u_H2O.L2  # length of 20
            self.DepthVector = self.u_H2O.L1  # length of 9
            self.GradientVector = self.u_H2O.grad  # length of 5
            self.DiameterVector = self.u_H2O.D  # length of 3
            self.TinVector = self.u_H2O.Tinj  # length of 3
            self.KrockVector = self.u_H2O.k  # length of 3
            self.Fluid_name = 'Water'
        elif self.Fluid.value == WorkingFluid.SCO2:
            if self.Configuration.value == Configuration.ULOOP:
                self.u_sCO2 = data.get(self.filename, Configuration.ULOOP.value, "sCO2")
            elif self.Configuration.value == Configuration.COAXIAL:
                self.u_sCO2 = data.get(self.filename, Configuration.COAXIAL.value, "sCO2")
            self.timearray = self.u_sCO2.time
            self.FlowRateVector = self.u_sCO2.mdot  # length of 26
            self.HorizontalLengthVector = self.u_sCO2.L2  # length of 20
            self.DepthVector = self.u_sCO2.L1  # length of 9
            self.GradientVector = self.u_sCO2.grad  # length of 5
            self.DiameterVector = self.u_sCO2.D  # length of 3
            self.TinVector = self.u_sCO2.Tinj  # length of 3
            self.KrockVector = self.u_sCO2.k  # length of 3
            self.Fluid_name = 'CarbonDioxide'

        # load property data
        if self.Fluid.value == WorkingFluid.WATER:
            self.mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py", '') + 'CLG Simulator/properties_H2O.mat')
        else:
            self.mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py", '') + 'CLG Simulator/properties_CO2v2.mat')
            self.additional_mat = scipy.io.loadmat(
                self.MyPath.replace(self.__str__() + ".py", '') + 'CLG Simulator/additional_properties_CO2v2.mat')
        self.Pvector = self.mat['Pvector'][0]
        self.Tvector = self.mat['Tvector'][0]
        self.density = self.mat['density']
        self.enthalpy = self.mat['enthalpy']
        self.entropy = self.mat['entropy']
        if self.Fluid.value == WorkingFluid.SCO2:
            self.Pvector_ap = self.additional_mat['Pvector_ap'][0]
            self.hvector_ap = self.additional_mat['hvector_ap'][0]
            self.svector_ap = self.additional_mat['svector_ap'][0]
            self.TPh = self.additional_mat['TPh']
            self.hPs = self.additional_mat['hPs']

        model.logger.info(f'complete {str(__class__)}: {sys._getframe().f_code.co_name}')

    def getTandP(self, model: Model) -> None:
        """
        The getTandP function reads and prepares Temperature and Pressure values from the CLGS database
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')

        # code from Koenraad
        self.point = (
            self.prodwellflowrate.value, self.Nonvertical_length.value, model.reserv.InputDepth.value * 1000.0,
            model.reserv.gradient.value[0], self.prodwelldiam.value / 39.37, self.Tinj.value + 273.15, self.krock)
        if self.Fluid.value == WorkingFluid.WATER:
            self.Tout, self.Pout = self.u_H2O.interp_outlet_states(self.point)
        elif self.Fluid.value == WorkingFluid.SCO2:
            self.Tout, self.Pout = self.u_sCO2.interp_outlet_states(self.point)

        # Initial time correction (Correct production temperature and pressure at time 0 (the value at
        # time 0 [=initial condition] is not a good representation for the first few months)
        self.Tout[0] = self.Tout[1]
        self.Pout[0] = self.Pout[1]

        model.logger.info(f'complete {str(__class__)}: {sys._getframe().f_code.co_name}')

    def verify(self, model: Model) -> int:
        """
        The verify function checks that all values provided are within the range expected by CLGS modeling system.
         These values in within a smaller range than the value ranges available to GEOPHIRES-X
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: 0 if all OK, 1 if error.
        :rtype: int
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')

        self.error = 0
        errors = []

        def on_invalid_parameter_value(err_msg):
            s = f'Error: CLGS model database imposes additional range restrictions: {err_msg}. Simulation terminated.'
            errors.append(s)
            print(s)
            model.logger.fatal(s)
            self.error = 1

        if self.Nonvertical_length.value < 1000 or self.Nonvertical_length.value > 20000:
            on_invalid_parameter_value('Nonvertical length must be between 1,000 and 20,000 m')

        if self.Tinj.value < 30.0 or self.Tinj.value > 60.0:
            on_invalid_parameter_value('Injection temperature must be between 30 and 60 C')

        if self.krock < 1.5 or self.krock > 4.5:
            on_invalid_parameter_value('Rock thermal conductivity must be between 1.5 and 4.5 W/m/K')

        if model.reserv.gradient.value[0] < 0.03 or model.reserv.gradient.value[0] > 0.07:
            on_invalid_parameter_value(f'{model.reserv.gradient1.Name} must be between '
                                       f'30 and 70 {TemperatureGradientUnit.DEGREESCPERKM.value}')

        model.logger.info(f'complete {str(__class__)}: {sys._getframe().f_code.co_name}')

        return self.error

    # Multilateral code

    def CalculateNonverticalPressureDrop(self, model:Model, time_operation: float, time_max: float, al: float):
        """
        Calculate nonvertical pressure drops - it will vary as the temperature varies
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param time_operation: time of operation in years (0.01)
        :type time_operation: float
        :param time_max: maximum time of operation in years (100) - this is the time of the last year of operation
        :type time_max: float
        :param al: time step in years (0.01) - this is the time step of the simulation (not the time step of the CLGS model)
        :type al: float
        :return: NonverticalPressureDrop, friction - pressure drop and friction factor for the nonvertical section of the wellbore
        :rtype: tuple
        """
        friction = 0.0
        NonverticalPressureDrop = [0.0] * model.surfaceplant.plant_lifetime.value  # initialize the array
        while time_operation <= time_max:
            year = math.trunc(time_operation / al)

            # nonvertical wellbore fluid conditions based on current temperature
            rhowater = density_water_kg_per_m3(
                self.NonverticalProducedTemperature.value[year],
                pressure=model.reserv.hydrostatic_pressure()
            )

            muwater = viscosity_water_Pa_sec(
                self.NonverticalProducedTemperature.value[year],
                pressure=model.reserv.hydrostatic_pressure()
            )
            vhoriz = self.q_circulation / rhowater / (math.pi / 4. * self.nonverticalwellborediameter.value ** 2)

            # assume turbulent flow.
            Rewaterhoriz = 4. * self.q_circulation / (muwater * math.pi * self.nonverticalwellborediameter.value)
            if self.NonverticalsCased:
                relroughness = 1E-4 / self.nonverticalwellborediameter.value
            else:
                # note the higher relative roughness for uncased nonvertical bores
                relroughness = 0.02 / self.nonverticalwellborediameter.value

            # 6 iterations to converge
            friction = 1. / np.power(-2 * np.log10(relroughness / 3.7 + 5.74 / np.power(Rewaterhoriz, 0.9)), 2.)
            friction = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewaterhoriz / np.sqrt(friction))), 2.)
            friction = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewaterhoriz / np.sqrt(friction))), 2.)
            friction = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewaterhoriz / np.sqrt(friction))), 2.)
            friction = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewaterhoriz / np.sqrt(friction))), 2.)
            friction = 1. / np.power((-2 * np.log10(relroughness / 3.7 + 2.51 / Rewaterhoriz / np.sqrt(friction))), 2.)

            # assume everything stays liquid throughout
            # nonvertical section pressure drop [kPa] per lateral section
            # assume no buoyancy effect because laterals are nonvertical, or if they are not,
            # they return to the same place, so there is no buoyancy effect
            NonverticalPressureDrop[year] = friction * (rhowater * vhoriz ** 2 / 2) * (
                self.Nonvertical_length.value / self.nonverticalwellborediameter.value) / 1E3  # /1E3 to convert from Pa to kPa
            time_operation += al

        # interpolation is required because NonverticalPressureDrop is sampled yearly,
        # and needs to be sampled more frequently to match other arrays
        f = interp1d(np.arange(0, len(NonverticalPressureDrop)), NonverticalPressureDrop, fill_value="extrapolate")
        NonverticalPressureDrop = f(np.arange(0, len(self.ProducedTemperature.value), 1))

        return NonverticalPressureDrop, friction

    def Calculate(self, model: Model) -> None:
        """
        The calculate function verifies, initializes, and extracts the values from the AGS model
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        if model.reserv.Trock.value > model.reserv.Tmax.value:
            s = f'{model.reserv.Trock.Name} ({model.reserv.Trock.value}) exceeds ' \
                f'{model.reserv.Tmax.Name} ({model.reserv.Tmax.value})'
            model.logger.critical(s)
            raise ValueError(s)

        self.Tini = model.reserv.Trock.value  # initialize the temperature to be the initial temperature of the reservoir
        if self.Tini > 375.0 or self.numnonverticalsections.value > 1:
            # must be a multilateral setup or too hot for CLGS, so must try to use wanju code.
            if self.Tini > 375.0:
                msg = 'In AGS, but forced to use Wanju code because initial reservoir temperature is too high for CLGS'
                model.logger.warning(msg)
                print(f'Warning: {msg}')

            # handle special cases for the multilateral calc parameters you added
            if self.nonverticalwellborediameter.value > 2.0:
                # correct the units of needed
                self.nonverticalwellborediameter.value = self.nonverticalwellborediameter.value * 0.0254
                self.nonverticalwellborediameter.CurrentUnits = LengthUnit.METERS
            self.area = math.pi * (self.nonverticalwellborediameter.value * 0.5) * (
                self.nonverticalwellborediameter.value * 0.5)
            # need to convert prodwellflowrate in l/sec to m3/hour
            # and then split the flow equally across all the sections
            self.q_circulation = (self.prodwellflowrate.value / 3.6) / self.numnonverticalsections.value
            self.velocity = self.q_circulation / self.area * 24.0
            # Wanju says it ts OK to make these numbers large - "we consider it is an infinite system"
            self.x_boundary = self.y_boundary = self.z_boundary = 2.0e15
            self.y_well = 0.5 * self.y_boundary  # Nonvertical wellbore in the center
            self.z_well = 0.5 * self.z_boundary  # Nonvertical wellbore in the center
            self.al = 365.0 / 4.0 * model.economics.timestepsperyear.value
            self.time_max = model.surfaceplant.plant_lifetime.value * 365.0
            self.rhorock = model.reserv.rhorock.value
            self.cprock = model.reserv.cprock.value
            self.alpha_rock = model.reserv.krock.value / model.reserv.rhorock.value / model.reserv.cprock.value * 24.0 * 3600.0
            # initialize the arrays
            self.NonverticalProducedTemperature.value = [0.0] * model.surfaceplant.plant_lifetime.value
            self.NonverticalPressureDrop.value = [0.0] * model.surfaceplant.plant_lifetime.value

            t = self.time_operation.value
            while self.time_operation.value <= self.time_max:
                # MIR figure out how to calculate year and extract Tini from reserv Tresoutput array
                year = math.trunc(self.time_operation.value / self.al)
                self.NonverticalProducedTemperature.value[year] = inverselaplace(
                    self, 16, 0, model.reserv.lithostatic_pressure())
                # update alpha_fluid value based on next temperature of reservoir

                self.alpha_fluid = self.WaterThermalConductivity.value / density_water_kg_per_m3(
                    self.NonverticalProducedTemperature.value[year],
                    pressure=model.reserv.hydrostatic_pressure()
                ) / heat_capacity_water_J_per_kg_per_K(
                    self.NonverticalProducedTemperature.value[year],
                    pressure=model.reserv.hydrostatic_pressure()
                ) * 24.0 * 3600.0
                self.time_operation.value += self.al

            self.time_operation.value = t  # set it back for use in later loop
            # interpolate the result to a longer array
            self.NonverticalProducedTemperature.value = signal.resample(self.NonverticalProducedTemperature.value,
                                                                        len(model.reserv.Tresoutput.value))

            # Calculate the temperature drop as the fluid makes it way to the surface (or use a constant value)
            # if not Ramey, hard code a user-supplied temperature drop.
            self.ProdTempDrop.value = self.tempdropprod.value
            model.reserv.cpwater.value = heat_capacity_water_J_per_kg_per_K(
                self.NonverticalProducedTemperature.value[0],
                pressure=model.reserv.hydrostatic_pressure()
            )
            if self.rameyoptionprod.value:
                self.ProdTempDrop.value = RameyCalc(model.reserv.krock.value,
                                                    model.reserv.rhorock.value,
                                                    model.reserv.cprock.value,
                                                    self.prodwelldiam.value,
                                                    model.reserv.timevector.value,
                                                    model.surfaceplant.utilization_factor.value,
                                                    self.prodwellflowrate.value,
                                                    model.reserv.cpwater.value,
                                                    model.reserv.Trock.value,
                                                    model.reserv.Tresoutput.value,
                                                    model.reserv.averagegradient.value / 1000.0,
                                                    model.reserv.InputDepth.value)

            self.ProducedTemperature.value = self.NonverticalProducedTemperature.value - self.ProdTempDrop.value

            # Now use the parent's calculation to calculate the upgoing and downgoing pressure drops and pumping power
            self.PumpingPower.value = [0.0] * len(self.ProducedTemperature.value)  # initialize the array
            if self.productionwellpumping.value:
                self.rhowaterinj = density_water_kg_per_m3(
                    model.reserv.Tsurf.value,
                    pressure=model.reserv.hydrostatic_pressure()
                ) * np.linspace(1, 1,
                                len(self.ProducedTemperature.value))

                self.rhowaterprod = density_water_kg_per_m3(
                    model.reserv.Trock.value,
                    pressure=model.reserv.hydrostatic_pressure()
                ) * np.linspace(1, 1, len(self.ProducedTemperature.value))

                self.DPProdWell.value, f3, vprod, self.rhowaterprod = WellPressureDrop(model,
                                                                                       model.reserv.Tresoutput.value - self.ProdTempDrop.value / 4.0,
                                                                                       self.prodwellflowrate.value,
                                                                                       self.prodwelldiam.value,
                                                                                       self.impedancemodelused.value,
                                                                                       model.reserv.InputDepth.value)
                if self.impedancemodelused.value:  # assumed everything stays liquid throughout
                    self.DPOverall.value, UpgoingPumpingPower, self.DPProdWell.value, self.DPReserv.value, self.DPBouyancy.value = \
                        ProdPressureDropsAndPumpingPowerUsingImpedenceModel(
                            f3, vprod,
                            self.rhowaterinj, self.rhowaterprod,
                            self.rhowaterprod, model.reserv.depth.value, self.prodwellflowrate.value,
                            self.prodwelldiam.value, self.impedance.value,
                            self.nprod.value, model.reserv.waterloss.value, model.surfaceplant.pump_efficiency.value)
                    self.DPOverall.value, DowngoingPumpingPower, self.DPProdWell.value, self.DPReserv.value, self.DPBouyancy.value = \
                        ProdPressureDropsAndPumpingPowerUsingImpedenceModel(
                            f3, vprod,
                            self.rhowaterprod, self.rhowaterinj, model.reserv.rhowater.value, model.reserv.depth.value,
                            self.prodwellflowrate.value, self.injwelldiam.value, self.impedance.value,
                            self.nprod.value, model.reserv.waterloss.value, model.surfaceplant.pump_efficiency.value)

                else:  # PI is used for both the verticals
                    UpgoingPumpingPower, self.PumpingPowerProd.value, self.DPProdWell.value, self.Pprodwellhead.value = \
                        ProdPressureDropAndPumpingPowerUsingIndexes(
                            model, self.productionwellpumping.value,
                            self.usebuiltinppwellheadcorrelation,
                            model.reserv.Trock.value, model.reserv.depth.value,
                            self.ppwellhead.value, self.PI.value,
                            self.prodwellflowrate.value, f3, vprod,
                            self.prodwelldiam.value, self.nprod.value, model.surfaceplant.pump_efficiency.value,
                            self.rhowaterprod)

                    DowngoingPumpingPower, ppp2, dppw, ppwh = ProdPressureDropAndPumpingPowerUsingIndexes(
                        model, self.productionwellpumping.value,
                        self.usebuiltinppwellheadcorrelation,
                        model.reserv.Trock.value, model.reserv.InputDepth.value,
                        self.ppwellhead.value, self.PI.value,
                        self.prodwellflowrate.value, f3, vprod,
                        self.injwelldiam.value, self.nprod.value, model.surfaceplant.pump_efficiency.value,
                        self.rhowaterinj)

                # Calculate Nonvertical Pressure Drop
                NonverticalPumpingPower = [0.0] * len(DowngoingPumpingPower)  # initialize the array
                self.NonverticalPressureDrop.value, f3 = self.CalculateNonverticalPressureDrop(
                    model,
                    self.time_operation.value,
                    self.time_max,
                    self.al)

                # calculate nonvertical well pumping power needed[MWe]
                NonverticalPumpingPower = self.NonverticalPressureDrop.value * self.nprod.value * \
                                          self.prodwellflowrate.value / self.rhowaterprod / \
                                          model.surfaceplant.pump_efficiency.value / 1E3  # [MWe] total pumping power for nonvertical section
                NonverticalPumpingPower = np.array(
                    [0. if x < 0. else x for x in NonverticalPumpingPower])  # cannot be negative so set to 0

                # recalculate the pumping power by looking at the difference between the upgoing and downgoing and the nonvertical
                self.PumpingPower.value = DowngoingPumpingPower + NonverticalPumpingPower - UpgoingPumpingPower
                self.PumpingPower.value = [max(x, 0.) for x in self.PumpingPower.value]  # cannot be negative, so set to 0

        else:
            # do the CLGS-style calculation
            err = self.verify(model)
            if err > 0:
                msg = 'Error: GEOPHIRES failed to validate CLGS input value. Exiting...'
                model.logger.fatal(msg)
                print(msg)

                raise RuntimeError(msg)

            self.initialize(model)
            self.getTandP(model)

            # Deep Copy the Arrays
            self.InterpolatedTemperatureArray = self.Tout.copy()
            self.InterpolatedTemperatureArray = self.InterpolatedTemperatureArray - 273.15
            self.InterpolatedPressureArray = self.Pout.copy()
            self.DPOverall.value = self.InterpolatedPressureArray.copy()
            self.ProducedTemperature.value = self.InterpolatedTemperatureArray.copy()

            tot_length, vert_length, horizontal_lengths = self.calculatedrillinglengths(model)

            # in this case, reserv.depth is just the vertical drill depth
            # TODO earlier calculations use reserv.depth before it is recalculated here; this should be refactored to avoid
            #   potential for mix-ups. As of 2024-02-16, calculations correctly account for this on-the-fly change of
            #   reserv.depth - see https://github.com/NREL/GEOPHIRES-X/issues/122#issuecomment-194869313 - but this
            #   implementation is fragile and prone to introducing bugs in future changes. Ideally, parameters should
            #   not be changed once their value has been calculated, and especially not after the first calculated
            #   value has been used as an input for other calculations.
            model.reserv.depth.value = model.reserv.InputDepth.quantity().to(model.reserv.depth.CurrentUnits).magnitude

            # getTandP results must be rejiggered to match wellbores expected output. Once done,
            # the surfaceplant and economics models should just work
            # #overall pressure drop  = previous pressure drop (as calculated from the verticals) + nonvertical section pressure drop
            # interpolation is required because DPOverall is sampled slightly differently, and DPOverall is sampled more frequently
            f = interp1d(np.arange(0, len(self.DPOverall.value)), self.DPOverall.value, fill_value="extrapolate")
            self.DPOverall.value = f(np.arange(0, len(self.DPOverall.value), 1))

            # calculate water values based on initial temperature

            rho_water = density_water_kg_per_m3(
                self.Tout[0],
                pressure = model.reserv.lithostatic_pressure(),
            )


            model.reserv.cpwater.value = heat_capacity_water_J_per_kg_per_K(
                self.Tout[0],
                pressure=model.reserv.hydrostatic_pressure(),
            )  # Need this for surface plant output calculation

            # set pumping power to zero for all times, assuming that the thermosphere wil always
            # make pumping of working fluid unnecessary
            self.PumpingPower.value = [0.0] * (len(self.DPOverall.value))
            self.PumpingPower.value = self.DPOverall.value * self.prodwellflowrate.value / rho_water / model.surfaceplant.pump_efficiency.value / 1E3
            # in GEOPHIRES v1.2, negative pumping power values become zero
            # (b/c we are not generating electricity) = thermosiphon is happening!
            self.PumpingPower.value = [max(x, 0.) for x in self.PumpingPower.value]

        self._sync_output_params_from_input_params()

        model.logger.info(f'complete {str(__class__)}: {sys._getframe().f_code.co_name}')

    def __str__(self):
        return 'AGSWellBores'
