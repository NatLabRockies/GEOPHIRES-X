"""
Geothermal Resources Management System (GRMS) classification.

GRMS is a project-based classification framework for geothermal resources,
modeled on the SPE Petroleum Resources Management System (SPE-PRMS). SPE and
Project InnerSpace announced the initiative to develop an official GRMS in
March 2026; until that framework publishes, this module implements the
conceptual GRMS proposed in:

    Gardner, S. and Faulder, D. (2024), "Geothermal Reserves Standards: A Study
        of the Applicability of the SPE Petroleum Resources Management System",
        GRC Transactions Vol. 48
    Gardner, S. E. and Chen, C. A. (2026), "Practical application of geothermal
        resources management system based on SPE-PRMS concepts",
        51st Stanford Geothermal Workshop, SGP-TR-230

Structural definitions follow SPE-PRMS v1.01 (revised June 2018), which Gardner
and Chen note is "reasonably applicable to geothermal resources until such time
as an official GRMS document may become available in the industry."

A project carries up to four independent designations:

1. Class            - commercial maturity (PRMS 1.1.0.6)
2. Category         - technical uncertainty, named per class (PRMS 2.2)
3. Sub-class        - project maturity (PRMS 2.1.3.5)
4. Reserves status  - development/production status (PRMS 2.1.3.6), Reserves only
                      (Gardner and Chen Table 3 also applies it to Contingent)

Contingent Resources may additionally carry an economic status (PRMS 2.1.3.7).

Production and Unrecoverable appear on the PRMS classification framework but are
not project classifications, so neither is a ResourceClass member here.
"""

from __future__ import annotations

from geophires_x.OptionList import GeophiresInputEnum


class ResourceClass(GeophiresInputEnum):
    """Commercial maturity: the chance-of-commerciality axis (PRMS Figure 1.1)."""

    PROSPECTIVE_RESOURCES = 1, 'Prospective Resources'
    CONTINGENT_RESOURCES = 2, 'Contingent Resources'
    RESERVES = 3, 'Reserves'

    @staticmethod
    def from_int(int_val: int) -> ResourceClass:
        for member in ResourceClass:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Resource Class integer input value: {int_val}')


class UncertaintyCategory(GeophiresInputEnum):
    """
    Incremental technical uncertainty categories (PRMS 2.2.2). Naming is
    class-specific. Note that PRMS 2.2.2.4 defines no incremental terms for
    Prospective Resources, which are reported only as cumulative scenarios.
    The leading digit encodes the owning class.
    """

    # Contingent Resources
    C1 = 21, 'C1'
    C2 = 22, 'C2'
    C3 = 23, 'C3'

    # Reserves
    PROVED = 31, 'Proved (P1)'
    PROBABLE = 32, 'Probable (P2)'
    POSSIBLE = 33, 'Possible (P3)'

    @property
    def resource_class(self) -> ResourceClass:
        return ResourceClass.from_int(self.int_value // 10)

    @staticmethod
    def from_int(int_val: int) -> UncertaintyCategory:
        for member in UncertaintyCategory:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Uncertainty Category integer input value: {int_val}')


class CumulativeCategory(GeophiresInputEnum):
    """
    Cumulative quantities derived from the low/best/high estimate scenarios
    (PRMS 2.2.2.2-2.2.2.4). These correspond to P90/P50/P10 when probabilistic
    methods are used (PRMS 2.2.1.2).
    """

    # Prospective Resources
    U1 = 11, '1U'
    U2 = 12, '2U'
    U3 = 13, '3U'

    # Contingent Resources
    C1_CUMULATIVE = 21, '1C'
    C2_CUMULATIVE = 22, '2C'
    C3_CUMULATIVE = 23, '3C'

    # Reserves
    P1_CUMULATIVE = 31, '1P'
    P2_CUMULATIVE = 32, '2P'
    P3_CUMULATIVE = 33, '3P'

    @property
    def resource_class(self) -> ResourceClass:
        return ResourceClass.from_int(self.int_value // 10)

    @property
    def estimate_scenario(self) -> str:
        """Low / best / high estimate this cumulative quantity derives from."""
        return {1: 'Low Estimate', 2: 'Best Estimate', 3: 'High Estimate'}[self.int_value % 10]

    @staticmethod
    def from_int(int_val: int) -> CumulativeCategory:
        for member in CumulativeCategory:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Cumulative Category integer input value: {int_val}')


class ProjectMaturitySubClass(GeophiresInputEnum):
    """Project maturity sub-classes (PRMS 2.1.3.5, Figure 2.1)."""

    # Prospective Resources
    PLAY = 11, 'Play'
    LEAD = 12, 'Lead'
    PROSPECT = 13, 'Prospect'

    # Contingent Resources
    DEVELOPMENT_NOT_VIABLE = 21, 'Development Not Viable'
    DEVELOPMENT_UNCLARIFIED = 22, 'Development Unclarified'
    DEVELOPMENT_ON_HOLD = 23, 'Development On Hold'
    DEVELOPMENT_PENDING = 24, 'Development Pending'

    # Reserves
    JUSTIFIED_FOR_DEVELOPMENT = 31, 'Justified for Development'
    APPROVED_FOR_DEVELOPMENT = 32, 'Approved for Development'
    ON_PRODUCTION = 33, 'On Production'

    @property
    def resource_class(self) -> ResourceClass:
        return ResourceClass.from_int(self.int_value // 10)

    @staticmethod
    def from_int(int_val: int) -> ProjectMaturitySubClass:
        for member in ProjectMaturitySubClass:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Project Maturity Sub-Class integer input value: {int_val}')


class ReservesStatus(GeophiresInputEnum):
    """
    Development and production status (PRMS 2.1.3.6). Defined for Reserves;
    Gardner and Chen (2026) Table 3 also report it for Contingent Resources.
    """

    DEVELOPED_PRODUCING = 1, 'Developed Producing'
    DEVELOPED_NON_PRODUCING_SHUT_IN = 2, 'Developed Non-Producing: Shut-In'
    DEVELOPED_NON_PRODUCING_BEHIND_PIPE = 3, 'Developed Non-Producing: Behind Pipe'
    UNDEVELOPED = 4, 'Undeveloped'

    @property
    def is_developed(self) -> bool:
        return self is not ReservesStatus.UNDEVELOPED

    @staticmethod
    def from_int(int_val: int) -> ReservesStatus:
        for member in ReservesStatus:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Reserves Status integer input value: {int_val}')


class EconomicStatus(GeophiresInputEnum):
    """
    Economic status for Contingent Resources (PRMS 2.1.3.7). Projects classified
    as Reserves are commercial by definition.
    """

    ECONOMICALLY_VIABLE = 1, 'Economically Viable'
    ECONOMICALLY_NOT_VIABLE = 2, 'Economically Not Viable'
    UNDETERMINED = 3, 'Undetermined'

    @staticmethod
    def from_int(int_val: int) -> EconomicStatus:
        for member in EconomicStatus:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Economic Status integer input value: {int_val}')


class EstimateScenario(GeophiresInputEnum):
    """
    The low, best or high estimate a deterministic evaluation represents
    (PRMS 2.2.1.4). Combined with the resource class this gives the cumulative
    category: a best estimate of Reserves is 2P, a low estimate of Contingent
    Resources is 1C, and so on.
    """

    LOW = 1, 'Low Estimate'
    BEST = 2, 'Best Estimate'
    HIGH = 3, 'High Estimate'

    @staticmethod
    def from_int(int_val: int) -> EstimateScenario:
        for member in EstimateScenario:
            if member.int_value == int_val:
                return member
        raise ValueError(f'Unknown Estimate Scenario integer input value: {int_val}')


def cumulative_category_for(resource_class: ResourceClass, estimate_scenario: EstimateScenario) -> CumulativeCategory:
    """
    The cumulative category a given class and estimate scenario denote
    (PRMS 2.2.2.2-2.2.2.4).
    """

    return CumulativeCategory.from_int(resource_class.int_value * 10 + estimate_scenario.int_value)


def resolve(enum_cls, raw: str):
    """
    Resolve a user-provided designation given either as its name ('Reserves')
    or as its integer code ('3'). Matching on names ignores case and
    surrounding whitespace.

    :raises ValueError: if the value matches no member of enum_cls
    """

    value = str(raw).strip()
    if not value:
        raise ValueError(f'No value provided for {enum_cls.__name__}')

    try:
        return enum_cls.from_int(int(value))
    except ValueError:
        pass

    folded = value.casefold()
    for member in enum_cls:
        if folded in (member.value.casefold(), member.name.casefold()):
            return member

    options = ', '.join(m.value for m in enum_cls)
    raise ValueError(f'Unknown {enum_cls.__name__} value: {raw!r}. Valid values are: {options}.')


def validate_classification(
    resource_class: ResourceClass,
    uncertainty_category: UncertaintyCategory | None = None,
    cumulative_category: CumulativeCategory | None = None,
    sub_class: ProjectMaturitySubClass | None = None,
    reserves_status: ReservesStatus | None = None,
    economic_status: EconomicStatus | None = None,
) -> None:
    """
    Raise ValueError if designations are mutually inconsistent.

    PRMS 2.2.0.4 forbids "split classification": a single project's quantities
    cannot span more than one class.
    """

    rc = resource_class.value

    if uncertainty_category is not None:
        if resource_class == ResourceClass.PROSPECTIVE_RESOURCES:
            raise ValueError(
                f'PRMS 2.2.2.4 defines no incremental uncertainty categories for {rc}; '
                f'use cumulative categories (1U/2U/3U) instead.'
            )
        if uncertainty_category.resource_class != resource_class:
            raise ValueError(
                f'{uncertainty_category.value} is not a valid uncertainty category for {rc}; '
                f'it belongs to {uncertainty_category.resource_class.value}.'
            )

    if cumulative_category is not None and cumulative_category.resource_class != resource_class:
        raise ValueError(
            f'{cumulative_category.value} is not a valid cumulative category for {rc}; '
            f'it belongs to {cumulative_category.resource_class.value}.'
        )

    if sub_class is not None and sub_class.resource_class != resource_class:
        raise ValueError(
            f'{sub_class.value} is not a valid project maturity sub-class for {rc}; '
            f'it belongs to {sub_class.resource_class.value}.'
        )

    if reserves_status is not None:
        # Note that sub-class describes the project while status describes
        # quantities within it, so a project On Production may legitimately hold
        # undeveloped quantities (PRMS 2.1.3.6.5; Gardner and Chen 2026 Project A
        # reports developed producing, developed shut-in and undeveloped reserves
        # for a single producing asset). No cross-check between the two is valid.
        #
        # PRMS 2.1.3.6 defines development/production status for Reserves only.
        # Gardner and Chen (2026) report Contingent Resources as "of course,
        # undeveloped", so only that status is accepted outside Reserves.
        if resource_class != ResourceClass.RESERVES and reserves_status.is_developed:
            raise ValueError(
                f'PRMS 2.1.3.6 defines development status for '
                f'{ResourceClass.RESERVES.value} only; {rc} are undeveloped. '
                f'{reserves_status.value} is not valid here.'
            )
    if economic_status is not None and resource_class != ResourceClass.CONTINGENT_RESOURCES:
        raise ValueError(
            f'Economic status is defined for {ResourceClass.CONTINGENT_RESOURCES.value} '
            f'(PRMS 2.1.3.7); {rc} projects are commercial by definition.'
        )
