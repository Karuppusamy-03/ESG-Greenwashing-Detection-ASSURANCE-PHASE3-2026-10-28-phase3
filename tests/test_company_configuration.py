"""Configuration check: every target company has well-formed official domains.

Reads web_search.py with ast, so it does not import the module (which needs ddgs).
Checks configuration shape only. It does not check that any domain is reachable.
"""

import ast
import pathlib
import re
import unittest

WEB_SEARCH = pathlib.Path(__file__).resolve().parents[1] / "web_search.py"
TARGET_COMPANIES = ("apple", "samsung", "microsoft", "tesla", "infosys")
DOMAIN_SHAPE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _official_domains():
    tree = ast.parse(WEB_SEARCH.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "OFFICIAL_COMPANY_DOMAINS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("OFFICIAL_COMPANY_DOMAINS not found in web_search.py")


class OfficialDomainConfigTests(unittest.TestCase):
    def test_every_target_company_has_an_official_domain(self):
        domains = _official_domains()
        for company in TARGET_COMPANIES:
            with self.subTest(company=company):
                self.assertIn(company, domains)
                self.assertTrue(domains[company], "domain list must not be empty")

    def test_domains_are_bare_hostnames(self):
        for company, hosts in _official_domains().items():
            for host in hosts:
                with self.subTest(company=company, host=host):
                    self.assertRegex(host, DOMAIN_SHAPE)
                    self.assertNotIn("/", host)
                    self.assertFalse(host.startswith("www."))


if __name__ == "__main__":
    unittest.main()
