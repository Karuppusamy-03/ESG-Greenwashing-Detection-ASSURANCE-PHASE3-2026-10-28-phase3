"""Cross-company regression tests for the comparability gate.

ALL sentences are SYNTHETIC. They mirror realistic claim structures for Samsung,
Microsoft, Tesla and Infosys. None is a quotation from any company, and none is
evidence about a real company. The purpose is to check that the same general rules
give the correct verdict AND reason for every company, not only for Apple.

Each assertion checks the verdict and a key phrase of the reason.
"""

import unittest

import timeline_analyzer as ta


def _gate(claim, evidence, metadata=None):
    return ta.compare_measurement_compatibility(claim, evidence, metadata or {})


class MeasureMismatchAcrossCompaniesTests(unittest.TestCase):
    def test_samsung_gross_total_vs_supplier_avoided_emissions(self):
        status, reason = _gate(
            "Samsung reports that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 baseline.",
            "Our supplier energy-efficiency program avoided 900,000 metric tons of CO2e in 2023.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("different measures", reason)

    def test_microsoft_product_footprint_vs_company_scope3(self):
        status, reason = _gate(
            "The Surface Laptop carbon footprint is reduced by 60% compared with the business-as-usual scenario.",
            "Across all Scope 3 categories, Microsoft emissions decreased by 25% compared with 2020.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("product_footprint", reason)

    def test_tesla_recycled_cobalt_vs_scope3_total(self):
        status, reason = _gate(
            "99% of the cobalt in our battery cells is recycled.",
            "Total Scope 3 emissions fell 18% compared with 2021.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("material content", reason)

    def test_tesla_recycled_materials_vs_emissions_total(self):
        status, reason = _gate(
            "We increased the use of recycled materials across our vehicles.",
            "Total emissions across our operations were 2.1 million metric tons in 2023.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("material content", reason)

    def test_microsoft_own_datacenters_vs_supplier_clean_energy(self):
        status, reason = _gate(
            "All of our datacenters have been powered by renewable electricity since 2025.",
            "Supplier clean-energy programs contracted 3 gigawatts of renewable generation in 2024.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("facility_coverage", reason)

    def test_infosys_own_campuses_vs_supplier_clean_energy(self):
        status, reason = _gate(
            "All of our campuses are powered by renewable electricity since 2020.",
            "Supplier clean-energy programs supported 1 gigawatt of renewable generation in 2023.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("different measures", reason)


class CoverageAndAssuranceTests(unittest.TestCase):
    def test_infosys_all_facilities_vs_partial_subset(self):
        status, reason = _gate(
            "All of our facilities have been powered by renewable electricity since 2020.",
            "Four of our 30 facilities in India are powered by renewable electricity.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("subset of facilities", reason)

    def test_tesla_assurance_excluding_scope_1_and_3_cannot_verify_full_claim(self):
        status, reason = _gate(
            "Tesla reports that gross Scope 1, 2, and 3 emissions decreased by 30% compared with 2021.",
            "Deloitte performed a limited review of Scope 2 electricity for 2023.",
            {
                "assurance_report": True,
                "covered_fiscal_period": "fiscal year 2023",
                "scope_exclusions": ["Scope 1 and 3 emissions are not subject to our review."],
            },
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("explicitly excludes", reason)


class TargetVersusAchievedTests(unittest.TestCase):
    def test_microsoft_target_is_not_compared_as_an_achieved_result(self):
        status, reason = _gate(
            "Microsoft targets 100% renewable electricity by 2030 for global operations under the GHG Protocol.",
            "Microsoft reported that renewable electricity supplied 60% of its global operations in 2024 under the GHG Protocol.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("Performance modalities differ", reason)


class CompatiblePassTests(unittest.TestCase):
    """Genuinely comparable pairs must pass. The gate must not reject everything."""

    def test_samsung_same_metric_baseline_boundary_method_and_period_is_compatible(self):
        status, reason = _gate(
            "Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 baseline "
            "for global operations under the GHG Protocol in fiscal year 2023.",
            "Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with the 2019 baseline "
            "for global operations under the GHG Protocol in fiscal year 2023 in its sustainability report.",
        )
        self.assertEqual(status, "COMPATIBLE", reason)

    def test_tesla_same_metric_baseline_boundary_method_and_period_is_compatible(self):
        status, reason = _gate(
            "Tesla reported that gross Scope 1 and 2 emissions decreased by 25% compared with its 2020 baseline "
            "for global operations under the GHG Protocol in fiscal year 2023.",
            "Tesla reported that gross Scope 1 and 2 emissions decreased by 25% compared with the 2020 baseline "
            "for global operations under the GHG Protocol in fiscal year 2023 in its impact report.",
        )
        self.assertEqual(status, "COMPATIBLE", reason)


class SameCompanyMismatchTests(unittest.TestCase):
    """Same company and metric, but a different baseline or scope must not pass."""

    CLAIM = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 baseline "
             "for global operations under the GHG Protocol in fiscal year 2023.")
    EVIDENCE = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with the 2019 baseline "
                "for global operations under the GHG Protocol in fiscal year 2023 in its sustainability report.")

    def test_different_baseline_year_is_incompatible(self):
        status, reason = _gate(self.CLAIM, self.EVIDENCE.replace("2019", "2015"))
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("baseline years differ", reason)

    def test_different_scope_is_incompatible(self):
        status, reason = _gate(self.CLAIM, self.EVIDENCE.replace("Scope 1 and 2", "Scope 3"))
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("measurement scopes or boundaries differ", reason)


class ExtractionQualityTests(unittest.TestCase):
    """Noisy or concatenated extraction is never promoted to support."""

    def test_table_fragment_is_inconclusive_not_compatible(self):
        status, reason = _gate(
            "Infosys reported that gross Scope 1 emissions decreased by 15% compared with 2019.",
            "Scope 1 . . . . 1,234 . . 2023 . . ..... page 14 of 62 Table 3 continued",
        )
        self.assertEqual(status, "INCONCLUSIVE", reason)
        self.assertIn("not extracted", reason)

    def test_concatenated_heading_is_inconclusive_not_compatible(self):
        status, reason = _gate(
            "Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 baseline.",
            "SustainabilityReportEnvironmentalPerformanceClimateChangeGHGEmissionsOverview2023",
        )
        self.assertEqual(status, "INCONCLUSIVE", reason)
        self.assertIn("not extracted", reason)


if __name__ == "__main__":
    unittest.main()
