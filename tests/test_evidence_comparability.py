"""Regression tests for evidence comparability (Apple scenarios A–E and general rules).

Every sentence is SYNTHETIC, written to mirror the structure of the Apple claim types
named in the task. None is a real Apple quotation and none is evidence of anything
about Apple. The tests check only that the comparability layer does not treat
different measures as verifying each other.
"""

import unittest

import timeline_analyzer as ta

CLAIM_A = (
    "Apple reports that gross greenhouse gas emissions across Scopes 1, 2, and 3 "
    "decreased by more than 60% compared with its 2015 baseline, excluding offsets."
)
SUPPLIER_AVOIDED = (
    "Our supplier energy-efficiency program avoided 1.2 million metric tons of CO2e in 2023."
)


def _gate(claim, evidence, metadata=None):
    return ta.compare_measurement_compatibility(claim, evidence, metadata or {})


class ScenarioAOverallReductionTests(unittest.TestCase):
    """Supplier avoided emissions must never directly verify an overall gross reduction."""

    def test_supplier_avoided_emissions_do_not_verify_overall_reduction(self):
        status, reason = _gate(CLAIM_A, SUPPLIER_AVOIDED)
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("avoided", reason.lower())

    def test_avoided_emissions_are_labelled_as_a_supplier_program_measure(self):
        # The metric_key vocabulary is unchanged (it is persisted). The distinction is
        # carried by the measure label, which is what the comparability gate uses.
        self.assertIn("avoided_or_supplier_program", ta.measure_labels(SUPPLIER_AVOIDED))
        self.assertNotIn("company_gross_total", ta.measure_labels(SUPPLIER_AVOIDED))


class ScenarioCProductFootprintTests(unittest.TestCase):
    """A product-specific footprint reduction is not verified by company-wide Scope 3 data."""

    PRODUCT_CLAIM = (
        "The Mac mini carbon footprint is reduced by 80% compared with the "
        "business-as-usual scenario."
    )
    COMPANY_SCOPE3 = (
        "Across all Scope 3 categories, emissions decreased by 30% compared with 2015."
    )

    def test_company_wide_scope3_does_not_verify_product_reduction(self):
        status, reason = _gate(self.PRODUCT_CLAIM, self.COMPANY_SCOPE3)
        self.assertEqual(status, "INCOMPATIBLE", reason)

    def test_product_footprint_is_not_classified_as_company_emissions_reduction(self):
        claim_records = ta._measurement_records(self.PRODUCT_CLAIM, [])
        scope3_records = ta._measurement_records(self.COMPANY_SCOPE3, ta._explicit_reporting_years(self.COMPANY_SCOPE3) or [])
        self.assertTrue(claim_records)
        self.assertTrue(scope3_records)
        self.assertNotEqual(
            claim_records[0].get("boundary"),
            scope3_records[0].get("boundary"),
            "product footprint and company-wide Scope 3 must carry different boundaries",
        )


class ScenarioBRareEarthTests(unittest.TestCase):
    """A rare-earth recycling claim is not matched to carbon-footprint figures."""

    CLAIM = "99% of the rare earth elements in the magnets of our products are recycled."
    CARBON = "Total Scope 3 emissions fell 25% compared with 2015."

    def test_rare_earth_claim_has_a_material_identity(self):
        self.assertEqual(ta.material_of(self.CLAIM), "rare_earth_elements")

    def test_carbon_figure_is_not_direct_support_for_rare_earth_claim(self):
        status, reason = _gate(self.CLAIM, self.CARBON)
        self.assertEqual(status, "INCOMPATIBLE", reason)


class ScenarioERecycledMaterialTests(unittest.TestCase):
    """Recycled-material claims require the same material, not generic emissions totals."""

    def test_recycled_aluminum_is_not_recycled_rare_earths(self):
        self.assertNotEqual(
            ta.material_of("We use 100% recycled aluminum in our enclosures."),
            ta.material_of("99% of the rare earth elements in our magnets are recycled."),
        )

    def test_overall_recycled_content_is_not_an_emissions_total(self):
        status, reason = _gate(
            "We increased the use of recycled materials across our products.",
            "Total emissions across our operations were 1.5 million metric tons in 2023.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)

    def test_recycled_aluminum_evidence_does_not_verify_recycled_rare_earths(self):
        status, reason = _gate(
            "99% of the rare earth elements in our magnets are recycled.",
            "100% of the aluminum in our enclosures is recycled.",
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)

    def test_same_material_recycled_content_is_not_blocked(self):
        status, reason = _gate(
            "99% of the rare earth elements in our magnets are recycled.",
            "In 2024, 99% of the rare earth elements in our magnets were recycled material.",
        )
        self.assertNotEqual(status, "INCOMPATIBLE", reason)


class ScenarioDFacilityRenewableTests(unittest.TestCase):
    """Apple's own facilities are distinct from supplier clean-energy programs."""

    CLAIM = "All of our facilities have been powered by renewable electricity since 2018."
    SUPPLIER = "Supplier clean-energy programs supported 4 gigawatts of renewable generation in 2023."

    def test_supplier_clean_energy_is_not_own_facility_coverage(self):
        status, reason = _gate(self.CLAIM, self.SUPPLIER)
        self.assertEqual(status, "INCOMPATIBLE", reason)

    def test_partial_facility_coverage_does_not_support_all_facilities(self):
        status, reason = _gate(
            self.CLAIM,
            "Three of our 40 facilities in Europe are powered by renewable electricity.",
        )
        self.assertNotEqual(status, "COMPATIBLE", reason)
        self.assertIn("coverage", reason.lower())


class GeneralComparabilityTests(unittest.TestCase):
    def test_missing_metadata_is_not_treated_as_compatible(self):
        status, _ = _gate(
            "Scope 1 emissions were 800 t in 2024.",
            "Scope 1 emissions were 790 t in 2024.",
        )
        self.assertNotEqual(status, "COMPATIBLE")

    def test_assurance_excluding_scope_1_and_3_does_not_verify_scope_1_2_3_claim(self):
        status, reason = _gate(
            CLAIM_A,
            "Trinity Consultants performed a limited review of Scope 2 electricity for 2023.",
            {
                "assurance_report": True,
                "covered_fiscal_period": "fiscal year 2023",
                "scope_exclusions": ["Scope 1 and 3 emissions are not subject to our review."],
            },
        )
        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("Scope 1", reason)

    def test_third_party_assurance_does_not_extend_beyond_its_scope(self):
        status, _ = _gate(
            CLAIM_A,
            "Trinity Consultants performed a limited review of Scope 2 electricity for 2023.",
            {
                "assurance_report": True,
                "covered_fiscal_period": "fiscal year 2023",
                "scope_exclusions": ["Scope 1 and 3 emissions are not subject to our review."],
            },
        )
        self.assertNotEqual(status, "COMPATIBLE")

    def test_nested_assurance_metadata_excludes_unreviewed_scope(self):
        claim = (
            "Apple reported that gross Scope 1 emissions were 1,000 metric "
            "tons of CO2e for global operations under the GHG Protocol in "
            "fiscal year 2024."
        )
        status, reason = _gate(
            claim,
            claim,
            {
                "assurance": {
                    "status": "ambiguous",
                    "scopes_excluded": ["Scope 1"],
                    "reporting_period": "2024",
                },
            },
        )

        self.assertEqual(status, "INCOMPATIBLE", reason)
        self.assertIn("Scope 1", reason)


if __name__ == "__main__":
    unittest.main()
