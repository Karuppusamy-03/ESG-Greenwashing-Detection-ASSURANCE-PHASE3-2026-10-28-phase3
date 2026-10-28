import json
import math
from pathlib import Path

from claim_extractor import extract_claims_and_evidence
from timeline_analyzer import compare_measurement_compatibility
from extraction_quality import MALFORMED, assess_statement_quality
from source_dedupe import group_candidates
from report_extractor import extract_text

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_REPORT = PROJECT_DIR / "data" / "sample_esg_report.txt"

# These are initial retrieval thresholds, not truth or risk thresholds.
STRONG_MATCH_THRESHOLD = 0.55
POTENTIAL_MATCH_THRESHOLD = 0.35
MAX_MATCHES_PER_CLAIM = 3


def load_latest_statements(company_name=None):
    files = sorted(
        OUTPUT_DIR.glob("*_statements.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            "No *_statements.json file found in output. "
            "Run online_claim_extractor.py first."
        )

    def _matches_company(path):
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return False

        if not isinstance(data, dict):
            return False

        if company_name is None:
            return True

        target = str(company_name).strip()
        if not target:
            return True

        stored_company = str(data.get("company") or "").strip()
        searched_name = str(data.get("search_name") or "").strip()
        return (
            stored_company.casefold() == target.casefold()
            or searched_name.casefold() == target.casefold()
        )

    candidates = [path for path in files if _matches_company(path)]
    if company_name and str(company_name).strip() and not candidates:
        raise FileNotFoundError(
            f"No statement collection found for company "
            f"{str(company_name).strip()!r}."
        )
    path = candidates[0] if candidates else files[0]

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    print("Statement file:", path.name)
    print("Company:", data.get("company", "Unknown"))

    return data


def load_sample_claims():
    if not SAMPLE_REPORT.exists():
        raise FileNotFoundError(
            f"Sample ESG report not found: {SAMPLE_REPORT}"
        )

    report_text = extract_text(SAMPLE_REPORT)
    claims, _ = extract_claims_and_evidence(report_text)
    return claims


def classify_similarity(score):
    if score >= STRONG_MATCH_THRESHOLD:
        return "potentially_relevant"
    elif score >= POTENTIAL_MATCH_THRESHOLD:
        return "weak_match"
    else:
        return "no_sufficiently_relevant_match"


def _dedupe_evidence_items(items):
    seen = set()
    unique = []
    for item in items:
        if not isinstance(item, dict):
            continue
        statement = item.get("statement")
        if not isinstance(statement, str):
            continue
        text = " ".join(statement.split()).strip()
        if not text:
            continue
        source_url = str(item.get("source_url") or item.get("final_url") or "").strip()
        key = (source_url.casefold(), text.casefold()) if source_url else text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def match_online_evidence(claims, statements, model, cos_sim=None):
    if cos_sim is None:
        from sentence_transformers import util
        cos_sim = util.cos_sim

    evidence_items = _dedupe_evidence_items([
        item for item in statements
        if isinstance(item.get("statement"), str)
        and item["statement"].strip()
        and item.get("source_role") in {
            "external_source",
            "external_regulatory_evidence",
            "configured_environmental_source",
            "independent_third_party_source",
        }
        and isinstance(item.get("source_url"), str)
        and item["source_url"].strip()
    ])

    if not claims or not evidence_items:
        return []

    claim_embeddings = model.encode(
        claims,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    evidence_texts = [
        item["statement"].strip()
        for item in evidence_items
    ]

    evidence_embeddings = model.encode(
        evidence_texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    similarity_matrix = cos_sim(
        claim_embeddings,
        evidence_embeddings,
    )

    results = []

    evidence_items = group_candidates([dict(item) for item in evidence_items])

    for claim_index, claim in enumerate(claims):
        scores = similarity_matrix[claim_index].tolist()

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        matches = []

        for index in ranked_indices:
            score = float(scores[index])

            # A NaN or infinite score is a missing measurement, not evidence of
            # relevance. NaN compares False to every threshold, so without this
            # guard it would pass the filter and become a match.
            if not math.isfinite(score):
                continue

            if score < POTENTIAL_MATCH_THRESHOLD:
                continue

            item = evidence_items[index]

            # claims arrive as plain strings from the pipeline; accept a dict too.
            if isinstance(claim, dict):
                claim_text = claim.get("claim") or claim.get("statement", "")
            else:
                claim_text = str(claim)
            quality_status, quality_reasons = assess_statement_quality(item["statement"])
            if quality_status == MALFORMED:
                # Malformed extraction is not reliable text. It is kept for review but is
                # never presented as support, however similar it is.
                comparability_status = "INCONCLUSIVE"
                comparability_reason = (
                    "Extraction quality is malformed (" + "; ".join(quality_reasons) + "); "
                    "the text is not reliable enough to assess."
                )
            else:
                comparability_status, comparability_reason = compare_measurement_compatibility(
                    claim_text, item["statement"], item,
                )
            label = classify_similarity(score)
            if quality_status == MALFORMED:
                label = "low_quality_extraction"
            if comparability_status == "INCOMPATIBLE":
                # Keep the candidate and its source for review, but never present it as
                # relevant support. Similarity alone does not establish comparability.
                label = "incompatible_candidate"

            matches.append({
                "matched_evidence": item["statement"],
                "similarity": round(score, 4),
                "match_label": label,
                "comparability_status": comparability_status,
                "comparability_reason": comparability_reason,
                "quality_status": quality_status,
                "quality_reasons": quality_reasons,
                "content_fingerprint": item.get("content_fingerprint"),
                "canonical_url": item.get("canonical_url"),
                "duplicate_group_id": item.get("duplicate_group_id"),
                "is_duplicate_of": item.get("is_duplicate_of"),
                "duplicate_method": item.get("duplicate_method"),
                "source_relation": item.get("source_relation"),
                "potentially_related_to": item.get("potentially_related_to"),
                "source_title": item.get("source_title", ""),
                "source_url": item.get("source_url", ""),
                "original_source_url": item.get(
                    "original_source_url",
                    item.get("source_url", ""),
                ),
                "publisher": item.get("publisher", ""),
                "source_domain": item.get("source_domain", ""),
                "source_role": item.get("source_role", "unknown"),
                "entity_context": item.get("entity_context"),
                "publication_date": item.get("publication_date"),
                "source_type": item.get("source_type", ""),
                "assurance_report": item.get("assurance_report", False),
                "assurance_scope": item.get("assurance_scope", ""),
                "assurance": item.get("assurance"),
                "covered_fiscal_period": item.get(
                    "covered_fiscal_period",
                    "",
                ),
                "scope_exclusions": item.get("scope_exclusions", []),
                "original_text": item.get("original_text", ""),
                "attribution_basis": item.get("attribution_basis", ""),
                "interpretation": (
                    "Textual similarity only. Check the source, date, "
                    "context, and claim details before deciding whether "
                    "this evidence supports or contradicts the claim."
                ),
            })

            if len(matches) >= MAX_MATCHES_PER_CLAIM:
                break

        supporting = [
            match for match in matches
            if match["match_label"] == "potentially_relevant"
            and match["comparability_status"] in {"COMPATIBLE", "NOT_QUANTITATIVE"}
            and match.get("quality_status") != MALFORMED
            and match.get("is_duplicate_of") is None
        ]
        independent_support_count = len({
            match.get("duplicate_group_id") for match in supporting
        })
        if not matches:
            status = "no_sufficiently_relevant_match"
        elif all(match["match_label"] == "incompatible_candidate" for match in matches):
            status = "candidates_found_but_incompatible"
        elif all(match["match_label"] == "low_quality_extraction" for match in matches):
            status = "candidates_found_low_quality_extraction"
        elif any(
            match.get("comparability_status") == "INCONCLUSIVE"
            for match in matches
        ) and independent_support_count == 0:
            status = "candidates_found_but_inconclusive"
        elif independent_support_count > 0:
            status = "potentially_relevant_evidence_found"
        else:
            status = "only_weak_matches_found"

        results.append({
            "claim": claim,
            "evidence_status": status,
            "matches_found": len(matches),
            "independent_support_count": independent_support_count,
            # Distinct documents whose independence is NOT established (similar content,
            # no same-document or provenance signal). Not counted as confirmed independent.
            "potentially_related_count": sum(
                1 for match in matches
                if match.get("source_relation") == "potentially_related"
            ),
            "matches": matches,
        })

    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("IMPROVED ONLINE ESG EVIDENCE MATCHING")
    print("=" * 65)

    data = load_latest_statements()
    claims = load_sample_claims()
    statements = data.get("statements", [])

    print("Sample claims:", len(claims))
    print("Online candidate statements:", len(statements))

    if not claims:
        print("No sample claims found. Check sample_esg_report.txt.")
        return

    if not statements:
        print("No online statements found.")
        return

    print("\nLoading Sentence Transformer model...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    results = match_online_evidence(
        claims,
        statements,
        model
    )

    output_data = {
        "company": data.get("company", ""),
        "collection_file": data.get("collection_file", ""),
        "claim_source": "data/sample_esg_report.txt",
        "test_type": (
            "Sample claims matched with online statements; "
            "these are not necessarily claims made by the searched company."
        ),
        "thresholds": {
            "potential_match": POTENTIAL_MATCH_THRESHOLD,
            "strong_match": STRONG_MATCH_THRESHOLD
        },
        "result_count": len(results),
        "results": results
    }

    output_path = OUTPUT_DIR / "online_evidence_matches.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            output_data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\n" + "=" * 65)
    print("MATCHING RESULTS")
    print("=" * 65)

    for number, result in enumerate(results, start=1):
        print(f"\nClaim {number}: {result['claim']}")
        print("Evidence status:", result["evidence_status"])
        print("Matches found:", result["matches_found"])

        for match_number, match in enumerate(
            result["matches"], start=1
        ):
            print(f"\n  Match {match_number}")
            print("  Similarity:", match["similarity"])
            print("  Label:", match["match_label"])
            print("  Source role:", match["source_role"])
            print("  Source title:", match["source_title"])
            print("  Evidence:", match["matched_evidence"][:350])
            print("  URL:", match["source_url"])

        if not result["matches"]:
            print("  No sufficiently relevant statement was found.")

    print("\nResults saved to:", output_path)
    print("\nImproved evidence matching completed.")
    print(
        "Reminder: similarity does not establish truth, contradiction, "
        "or greenwashing."
    )


if __name__ == "__main__":
    main()
