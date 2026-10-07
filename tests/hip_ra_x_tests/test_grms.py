from __future__ import annotations

import unittest

from hip_ra_x.grms import CumulativeCategory
from hip_ra_x.grms import EconomicStatus
from hip_ra_x.grms import ProjectMaturitySubClass
from hip_ra_x.grms import ReservesStatus
from hip_ra_x.grms import ResourceClass
from hip_ra_x.grms import UncertaintyCategory
from hip_ra_x.grms import validate_classification
from tests.base_test_case import BaseTestCase


class GrmsClassificationTestCase(BaseTestCase):
    """
    Classification designations per the conceptual GRMS of Gardner and Faulder
    (2024) and Gardner and Chen (2026), which follow SPE-PRMS v1.01 structure.
    """

    def test_every_designation_resolves_to_its_class(self):
        for category in UncertaintyCategory:
            self.assertIn(category.resource_class, (ResourceClass.CONTINGENT_RESOURCES, ResourceClass.RESERVES))
        for category in CumulativeCategory:
            self.assertIsInstance(category.resource_class, ResourceClass)
        for sub_class in ProjectMaturitySubClass:
            self.assertIsInstance(sub_class.resource_class, ResourceClass)

    def test_from_int_round_trips(self):
        for enum_cls in (
            ResourceClass,
            UncertaintyCategory,
            CumulativeCategory,
            ProjectMaturitySubClass,
            ReservesStatus,
            EconomicStatus,
        ):
            for member in enum_cls:
                self.assertEqual(member, enum_cls.from_int(member.int_value))

            with self.assertRaises(ValueError):
                enum_cls.from_int(-1)

    def test_prospective_resources_have_no_incremental_categories(self):
        """PRMS 2.2.2.4: no incremental terms are defined for Prospective Resources."""

        prospective_cumulative = [
            c for c in CumulativeCategory if c.resource_class is ResourceClass.PROSPECTIVE_RESOURCES
        ]
        self.assertEqual(3, len(prospective_cumulative))

        for category in UncertaintyCategory:
            self.assertIsNot(ResourceClass.PROSPECTIVE_RESOURCES, category.resource_class)

    def test_cumulative_categories_map_to_estimate_scenarios(self):
        self.assertEqual('Low Estimate', CumulativeCategory.P1_CUMULATIVE.estimate_scenario)
        self.assertEqual('Best Estimate', CumulativeCategory.P2_CUMULATIVE.estimate_scenario)
        self.assertEqual('High Estimate', CumulativeCategory.P3_CUMULATIVE.estimate_scenario)
        self.assertEqual('Low Estimate', CumulativeCategory.U1.estimate_scenario)
        self.assertEqual('High Estimate', CumulativeCategory.C3_CUMULATIVE.estimate_scenario)

    def test_project_a_mature_producing_hydrothermal(self):
        """
        Gardner and Chen (2026) Project A: a producing hydrothermal asset
        classified as Reserves, with developed producing, developed shut-in,
        and undeveloped quantities.
        """

        for status in (
            ReservesStatus.DEVELOPED_PRODUCING,
            ReservesStatus.DEVELOPED_NON_PRODUCING_SHUT_IN,
            ReservesStatus.UNDEVELOPED,
        ):
            validate_classification(
                ResourceClass.RESERVES,
                uncertainty_category=UncertaintyCategory.PROVED,
                sub_class=ProjectMaturitySubClass.ON_PRODUCTION,
                reserves_status=status,
            )

    def test_project_b_egs_reserves_and_contingent(self):
        """
        Gardner and Chen (2026) Project B (Table 3): EGS reserves categorized
        1P/2P/3P with non-producing and undeveloped status, plus 1C contingent
        resources sub-classified as development pending and undeveloped.
        """

        for cumulative in (
            CumulativeCategory.P1_CUMULATIVE,
            CumulativeCategory.P2_CUMULATIVE,
            CumulativeCategory.P3_CUMULATIVE,
        ):
            validate_classification(
                ResourceClass.RESERVES,
                cumulative_category=cumulative,
                reserves_status=ReservesStatus.DEVELOPED_NON_PRODUCING_SHUT_IN,
            )

        validate_classification(
            ResourceClass.CONTINGENT_RESOURCES,
            uncertainty_category=UncertaintyCategory.C1,
            cumulative_category=CumulativeCategory.C1_CUMULATIVE,
            sub_class=ProjectMaturitySubClass.DEVELOPMENT_PENDING,
            reserves_status=ReservesStatus.UNDEVELOPED,
        )

    def test_project_b_prime_untested_acreage_is_prospective(self):
        """
        Gardner and Chen (2026) Project B': untested acreage whose exploratory
        nature classifies it as prospective, sub-classed as prospect and
        undeveloped by definition.
        """

        validate_classification(
            ResourceClass.PROSPECTIVE_RESOURCES,
            cumulative_category=CumulativeCategory.U2,
            sub_class=ProjectMaturitySubClass.PROSPECT,
            reserves_status=ReservesStatus.UNDEVELOPED,
        )

    def test_designations_from_another_class_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_classification(ResourceClass.RESERVES, uncertainty_category=UncertaintyCategory.C1)

        with self.assertRaises(ValueError):
            validate_classification(ResourceClass.RESERVES, cumulative_category=CumulativeCategory.C2_CUMULATIVE)

        with self.assertRaises(ValueError):
            validate_classification(ResourceClass.RESERVES, sub_class=ProjectMaturitySubClass.DEVELOPMENT_PENDING)

        with self.assertRaises(ValueError):
            validate_classification(ResourceClass.CONTINGENT_RESOURCES, sub_class=ProjectMaturitySubClass.PROSPECT)

    def test_only_reserves_may_be_developed(self):
        """PRMS 2.1.3.6 defines development status for Reserves."""

        for resource_class in (ResourceClass.PROSPECTIVE_RESOURCES, ResourceClass.CONTINGENT_RESOURCES):
            with self.assertRaises(ValueError):
                validate_classification(resource_class, reserves_status=ReservesStatus.DEVELOPED_PRODUCING)

            validate_classification(resource_class, reserves_status=ReservesStatus.UNDEVELOPED)

    def test_economic_status_applies_only_to_contingent_resources(self):
        """PRMS 2.1.3.7: Reserves are commercial by definition."""

        for status in EconomicStatus:
            validate_classification(ResourceClass.CONTINGENT_RESOURCES, economic_status=status)

        for resource_class in (ResourceClass.PROSPECTIVE_RESOURCES, ResourceClass.RESERVES):
            with self.assertRaises(ValueError):
                validate_classification(resource_class, economic_status=EconomicStatus.UNDETERMINED)


if __name__ == '__main__':
    unittest.main()
