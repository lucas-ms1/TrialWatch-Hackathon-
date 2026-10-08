"""Synthetic guardrail tests; these are not measured real-case evaluation results."""
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.experiment_01.pipeline import (  # noqa: E402
    assertion_inventory, body_hash, build_cases, calculate_metrics, check_corpus,
    check_packet, check_predictions, display_quotes, main, render_report,
    run_baseline, safe_url, save_json, sha256, validate_audit,
)
from scripts.validate_data import validate_document  # noqa: E402


def source(sid="s001", body="SYNTHETIC: Journalist Alex was arrested.\n\nSYNTHETIC: The court dismissed the complaint.", **updates):
    item = {"source_id": sid, "url": "https://example.invalid/" + sid, "title": "SYNTHETIC fixture " + sid,
            "publisher": "Synthetic publisher", "language": "en", "translation_status": "original",
            "publication_date": "2020-01-02", "update_date": None, "update_note": None,
            "retrieved_at": "2026-10-06T16:00:00Z", "capture_method": "synthetic fixture", "access_status": "readable",
            "body": body, "text_sha256": body_hash(body), "lineage_group": None, "upstream_sources": [],
            "historical_availability": "unverified", "capture_path": "synthetic-not-real.txt"}
    item.update(updates)
    return item


def fixture():
    sources = [source()]
    corpus = {"run_id": "synthetic-run", "sources": sources}
    packet = {"run_id": "synthetic-run", "stage": "early", "sources": deepcopy(sources),
              "early_source_ids": ["s001"], "view_type": "publication_ordered_reconstruction"}
    predictions = {"run_id": "synthetic-run", "stage": "early",
                   "article_decisions": [{"source_id": "s001", "decision": "relevant", "reason": "The fictional article identifies Alex as the arrestee."}],
                   "claims": [{"claim_id": "alex-arrest", "proceeding_id": "alex-firearms", "text": "The fictional source reports Alex's arrest.",
                               "source_id": "s001", "quote": "Journalist Alex was arrested.", "locator": "paragraph 1", "event_date": None,
                               "attribution": "Synthetic publisher", "kind": "procedural_event"}],
                   "proceedings": [{"proceeding_id": "alex-firearms", "title": "SYNTHETIC Alex firearms proceeding", "defendants": ["Alex"],
                                    "source_ids": ["s001"], "related_proceeding_ids": [], "linkage_uncertainty": None}],
                   "cards": [{"proceeding_id": "alex-firearms", "title": "SYNTHETIC Alex firearms proceeding", "earlier_claim_ids": ["alex-arrest"],
                              "later_claim_ids": [], "changes": [],
                              "review_reasons": [{"text": "Candidate review: the fictional source reports the arrest of a journalist.", "claim_ids": ["alex-arrest"]}],
                              "unknowns": [{"question": "Was a formal charge filed?", "next_check": "Inspect the charging document."}], "human_review": "pending"}]}
    return corpus, packet, predictions


class MarkupCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.refs, self.scripts, self.styles = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.refs.append(attrs["href"][1:])
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "link":
            self.styles.append(attrs.get("href"))


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "experiments/philippines_pilot/config.json").read_text(encoding="utf-8-sig"))
        self.corpus, self.packet, self.predictions = fixture()

    def assert_prediction_error(self, fragment):
        errors = check_predictions(self.predictions, self.packet)["errors"]
        self.assertTrue(any(fragment in error for error in errors), errors)

    def labels(self, rows):
        return {"run_id": self.corpus["run_id"], "reference_type": "ai_generated_provisional", "labels": rows}

    def test_good_fixture_checks_without_claiming_semantic_support(self):
        self.assertEqual([], check_corpus(self.corpus, self.config)["errors"])
        self.assertEqual([], check_packet(self.packet, self.corpus, "early")["errors"])
        result = check_predictions(self.predictions, self.packet)
        self.assertEqual([], result["errors"])
        self.assertTrue(result["semantic_support"].startswith("incomplete"))

    def test_victim_role_trap_is_baseline_false_positive_not_rule_engine_truth(self):
        self.corpus["sources"] = [source(body="SYNTHETIC: A suspect was charged with attacking journalist Alex. Alex is the victim.")]
        baseline = run_baseline(self.corpus, self.config)
        self.assertEqual("relevant", baseline["article_decisions"][0]["decision"])
        predictions = {"article_decisions": [{"source_id": "s001", "decision": "irrelevant"}]}
        result = calculate_metrics(self.corpus, predictions, self.labels([{"source_id": "s001", "label": "irrelevant"}]), baseline, self.config)
        self.assertEqual(1, result["methods"]["keyword_baseline"]["queue_confusion"]["fp"])
        self.assertEqual(1, result["methods"]["ai_first_pass"]["queue_confusion"]["tn"])
        self.assertEqual("incomplete", result["acceptance"]["critical_errors"]["status"])

    def test_same_person_different_proceedings_stay_separate(self):
        other = deepcopy(self.predictions["proceedings"][0])
        other.update(proceeding_id="alex-financing", title="SYNTHETIC separate financing proceeding", related_proceeding_ids=["alex-firearms"])
        self.predictions["proceedings"].append(other)
        cases = build_cases(self.predictions, self.corpus, synthetic=True)
        self.assertEqual(["alex-firearms", "alex-financing"], [c["case_id"] for c in cases["cases"]])
        self.assertEqual("needs_sources", cases["cases"][1]["review"]["status"])
        self.assertTrue(all(c["synthetic"] for c in cases["cases"]))

    def test_cross_proceeding_claim_cannot_be_used_in_another_card(self):
        other = deepcopy(self.predictions["proceedings"][0])
        other["proceeding_id"] = "alex-financing"
        self.predictions["proceedings"].append(other)
        self.predictions["cards"][0]["proceeding_id"] = "alex-financing"
        self.assert_prediction_error("wrong proceeding claim")

    def test_distinct_copied_reports_preserve_lineage_without_independence_claim(self):
        self.corpus["sources"][0]["lineage_group"] = "shared-original"
        self.corpus["sources"].append(source("s002", lineage_group="shared-original", publisher="Another publisher"))
        result = check_corpus(self.corpus, self.config)
        self.assertEqual([], result["errors"])
        self.assertEqual(2, result["reports"])
        self.assertEqual(["s001", "s002"], result["known_lineage_groups"]["shared-original"])
        self.assertIsNone(result["independent_origin_count"])

    def test_exact_duplicate_url_is_rejected(self):
        self.corpus["sources"].append(source("s002", url=self.corpus["sources"][0]["url"]))
        self.assertTrue(any("duplicate URL" in e for e in check_corpus(self.corpus, self.config)["errors"]))

    def test_unknown_date_and_status_do_not_become_false(self):
        cases = build_cases(self.predictions, self.corpus, synthetic=True)
        self.assertIsNone(cases["cases"][0]["claims"][0]["event_date"])
        self.assertIsNone(cases["cases"][0]["review"]["reviewer"])
        self.assertEqual("Was a formal charge filed?", self.predictions["cards"][0]["unknowns"][0]["question"])
        self.assertEqual([], validate_document(cases))

    def test_dismissal_does_not_generate_release_and_semantic_overclaim_requires_audit(self):
        claim = self.predictions["claims"][0]
        claim.update(text="The fictional court dismissed the complaint.", quote="The court dismissed the complaint.", locator="paragraph 2")
        cases = build_cases(self.predictions, self.corpus, synthetic=True)
        self.assertNotIn("released", json.dumps(cases))
        claim["text"] = "UNSUPPORTED SYNTHETIC CLAIM: Alex was released."
        result = check_predictions(self.predictions, self.packet)
        self.assertEqual([], result["errors"], "Literal quote matching cannot determine whether dismissal establishes release")
        self.assertTrue(result["semantic_support"].startswith("incomplete"))
        self.assertIn("UNSUPPORTED SYNTHETIC CLAIM", result["assertion_inventory"][0]["text"])

    def test_later_source_cannot_enter_early_stage(self):
        self.predictions["claims"][0]["source_id"] = "s002"
        self.assert_prediction_error("source outside permitted stage")

    def test_later_card_early_column_enforces_source_membership(self):
        self.packet["stage"] = self.predictions["stage"] = "later"
        self.packet["sources"].append(source("s002"))
        self.predictions["article_decisions"].append({"source_id": "s002", "decision": "relevant", "reason": "Synthetic assertion."})
        self.predictions["claims"][0]["source_id"] = "s002"
        self.predictions["proceedings"][0]["source_ids"].append("s002")
        self.assert_prediction_error("later source leaked into early view")

    def test_quote_must_exist_in_exact_cited_paragraph_not_somewhere_in_body(self):
        self.predictions["claims"][0]["locator"] = "paragraph 2"
        self.assert_prediction_error("exact quote not present in cited paragraph")
        self.predictions["claims"][0]["locator"] = "paragraph 1"
        self.predictions["claims"][0]["quote"] = "journalist Alex was arrested."
        self.assert_prediction_error("exact quote not present in cited paragraph")

    def test_packet_body_or_metadata_tamper_is_rejected(self):
        self.packet["sources"][0]["title"] = "Changed title"
        result = check_packet(self.packet, self.corpus, "early")
        self.assertTrue(any("differs from frozen corpus" in e for e in result["errors"]))
        self.corpus["sources"][0]["body"] += " Added text."
        self.assertTrue(any("SHA256 mismatch" in e for e in check_corpus(self.corpus, self.config)["errors"]))

    def test_missing_claim_refs_and_human_review_upgrade_are_rejected(self):
        self.predictions["cards"][0]["review_reasons"][0]["claim_ids"] = []
        self.assert_prediction_error("nonempty claim_ids required")
        self.predictions["cards"][0]["human_review"] = "ready_for_expert_review"
        self.assert_prediction_error("human review must remain")

    def test_three_way_metrics_exclude_reference_uncertain_and_count_queue_burden(self):
        self.corpus["sources"] = [source(f"s{i:03d}") for i in range(1, 10)]
        labels = [{"source_id": f"s{i:03d}", "label": "relevant" if i <= 2 else "irrelevant" if i <= 8 else "uncertain"} for i in range(1, 10)]
        rows = [{"source_id": f"s{i:03d}", "decision": "uncertain" if i in {1, 3, 9} else "relevant" if i == 2 else "irrelevant"} for i in range(1, 10)]
        metrics = calculate_metrics(self.corpus, {"article_decisions": rows}, self.labels(labels), run_baseline(self.corpus, self.config), self.config)
        ai = metrics["methods"]["ai_first_pass"]
        self.assertEqual({"tp": 2, "fp": 1, "fn": 0, "tn": 5}, ai["queue_confusion"])
        self.assertEqual(8, ai["binary_reference_denominator"])
        self.assertEqual(3, ai["queue_precision_agreement"]["denominator"])
        self.assertEqual(1, ai["reference_uncertain"]["queued"])
        self.assertEqual("pass", metrics["acceptance"]["negative_review_burden"]["status"])
        self.assertEqual("incomplete", metrics["acceptance"]["semantic_support"]["status"])
        self.assertEqual(3, ai["predictions"]["uncertain"])

    def test_all_uncertain_cannot_hide_negative_queue_burden(self):
        self.corpus["sources"] = [source(f"s{i:03d}") for i in range(1, 8)]
        labels = [{"source_id": f"s{i:03d}", "label": "relevant" if i == 1 else "irrelevant"} for i in range(1, 8)]
        rows = [{"source_id": f"s{i:03d}", "decision": "uncertain"} for i in range(1, 8)]
        metrics = calculate_metrics(self.corpus, {"article_decisions": rows}, self.labels(labels), run_baseline(self.corpus, self.config), self.config)
        self.assertEqual("fail", metrics["acceptance"]["negative_review_burden"]["status"])
        self.assertEqual(7, metrics["methods"]["ai_first_pass"]["predictions"]["uncertain"])

    def test_duplicate_prediction_is_not_a_second_triage_observation(self):
        self.predictions["article_decisions"].append(deepcopy(self.predictions["article_decisions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            calculate_metrics(self.corpus, self.predictions, self.labels([{"source_id": "s001", "label": "relevant"}]), run_baseline(self.corpus, self.config), self.config)

    def test_render_escapes_source_text_and_resolves_internal_citations(self):
        self.predictions["cards"][0]["title"] = '<script>alert("injected")</script>'
        self.predictions["cards"][0]["unknowns"][0]["question"] = '<img src=x onerror="alert(1)"> Is release reported?'
        later = deepcopy(self.predictions)
        later["stage"] = "later"
        metrics = calculate_metrics(self.corpus, later, self.labels([{"source_id": "s001", "label": "relevant"}]), run_baseline(self.corpus, self.config), self.config)
        validations = {"early": check_predictions(self.predictions, self.packet), "later": check_predictions(later, {**self.packet, "stage": "later"})}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            render_report(self.corpus, self.predictions, later, metrics, validations, output, {})
            body = (output / "index.html").read_text(encoding="utf-8")
            self.assertNotIn('<script>', body)
            self.assertNotIn('<img', body)
            self.assertIn('&lt;script&gt;', body)
            parser = MarkupCheck()
            parser.feed(body)
            self.assertFalse(parser.scripts)
            self.assertEqual(["style.css"], parser.styles)
            self.assertEqual(len(parser.ids), len(set(parser.ids)))
            self.assertTrue(set(parser.refs) <= set(parser.ids))
            self.assertTrue((output / "cards.md").exists())
            self.assertIn('href="cases.json">Full exact excerpt and locator', body)
            self.assertIn('href="cases.early.json">Full exact excerpt and locator', body)
            card_md = (output / "cards" / "later-alex-firearms.md").read_text(encoding="utf-8")
            self.assertIn('](<../cases.json>)', card_md)

    def test_markdown_destination_delimiter_injection_is_rejected(self):
        for url in ('https://example.invalid/a>)[click](javascript:alert(1))',
                    'https://example.invalid/<script>', 'https://example.invalid/a"onload=',
                    "https://example.invalid/a'b", 'https://example.invalid/a`b',
                    'https://example.invalid/a\\b', 'https://example.invalid/a\nb'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_url(url)
        self.assertEqual('https://example.invalid/a%3Eb?name=test', safe_url('https://example.invalid/a%3Eb?name=test'))

    def test_audit_inventory_covers_dates_attribution_unknowns_and_metadata(self):
        rows = assertion_inventory(self.predictions, self.packet)
        claim = next(row for row in rows if row["type"] == "claim")
        self.assertIn("event_date", claim["fields"])
        self.assertIn("attribution", claim["fields"])
        self.assertIn("quote", claim["fields"])
        self.assertIn("locator", claim["fields"])
        self.assertTrue({"unknown_question", "unknown_next_check", "source_metadata", "card_stage_membership", "human_review_state"} <= {row["type"] for row in rows})
        metadata = next(row for row in rows if row["type"] == "source_metadata")
        self.assertIn("publication_date", metadata["fields"])
        self.assertNotIn("body", metadata["fields"])
        self.assertEqual(len(rows), len({row["assertion_id"] for row in rows}))

    def test_audit_pass_requires_exact_identity_and_full_assertion_coverage(self):
        later = {**deepcopy(self.predictions), "stage": "later"}
        validations = {"early": check_predictions(self.predictions, self.packet),
                       "later": check_predictions(later, {**self.packet, "stage": "later"})}
        hashes = {"early_predictions": "a" * 64, "later_predictions": "b" * 64}
        audit = {"run_id": "synthetic-run", "prediction_version": "first_pass",
                 "prediction_hashes": {"early": "a" * 64, "later": "b" * 64},
                 "checks": {"semantic_support": {"status": "pass", "basis": "SYNTHETIC audit fixture only."}}, "coverage": {}}
        for stage in ("early", "later"):
            ids = [row["assertion_id"] for row in validations[stage]["assertion_inventory"]]
            audit["coverage"][stage] = {"status": "complete", "audited_assertion_ids": ids,
                                        "audited_assertions": len(ids), "total_assertions": len(ids)}
        validate_audit(audit, "synthetic-run", "first_pass", hashes, validations)
        for mutation, message in ((lambda doc: doc.update(run_id="other-run"), "run_id"),
                                  (lambda doc: doc.update(prediction_version="repair_01"), "prediction_version"),
                                  (lambda doc: doc["prediction_hashes"].update(early="c" * 64), "hash mismatch"),
                                  (lambda doc: doc["coverage"]["early"]["audited_assertion_ids"].pop(), "complete early"),
                                  (lambda doc: doc["coverage"]["later"].update(audited_assertions=0), "counts mismatch")):
            with self.subTest(message=message):
                altered = deepcopy(audit)
                mutation(altered)
                with self.assertRaisesRegex(ValueError, message):
                    validate_audit(altered, "synthetic-run", "first_pass", hashes, validations)

    def test_report_wide_quotation_budget_spans_both_stages(self):
        self.predictions["claims"][0]["quote"] = " ".join("word" + str(i) for i in range(40))
        later = deepcopy(self.predictions)
        later["stage"] = "later"
        quotes = display_quotes([self.predictions, later])
        self.assertEqual(25, sum(len(q.split()) for q in quotes.values()))
        self.assertEqual("", quotes["later:alex-arrest"])

    def test_pipeline_reproducibility_and_frozen_hash_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            documents = {"corpus": self.corpus, "early_packet": self.packet, "early_predictions": self.predictions,
                         "later_packet": {**deepcopy(self.packet), "stage": "later"},
                         "later_predictions": {**deepcopy(self.predictions), "stage": "later"},
                         "labels": self.labels([{"source_id": "s001", "label": "relevant"}]),
                         "config": self.config, "contract": {"run_id": "synthetic-run", "version": "1.0"}}
            for key, doc in documents.items():
                save_json(root / (key + ".json"), doc)
            protocol = {"run_id": "synthetic-run", "config_sha256": sha256(root / "config.json"), "contract_sha256": sha256(root / "contract.json")}
            save_json(root / "protocol.json", protocol)
            hashes = {key: sha256(root / (key + ".json")) for key in documents}
            save_json(root / "hashes.json", hashes)
            args = ["run"]
            for key in [*documents, "protocol"]:
                args.extend(["--" + key.replace("_", "-"), str(root / (key + ".json"))])
            args += ["--frozen-hashes", str(root / "hashes.json"), "--output", str(root / "output"), "--synthetic"]
            self.assertEqual(0, main(args))
            before = {p.relative_to(root / "output").as_posix(): sha256(p) for p in (root / "output").rglob("*") if p.is_file()}
            self.assertEqual(0, main(args))
            after = {p.relative_to(root / "output").as_posix(): sha256(p) for p in (root / "output").rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            documents["early_packet"]["stage"] = "later"
            save_json(root / "early_packet.json", documents["early_packet"])
            self.assertEqual(2, main(args))
            # Same aggregate decisions and a refreshed manifest must not overwrite
            # a first-pass report if any frozen claim/card/stage input changed.
            documents["early_packet"]["stage"] = "early"
            save_json(root / "early_packet.json", documents["early_packet"])
            documents["early_predictions"]["claims"][0]["text"] = "CHANGED SYNTHETIC CLAIM with identical article decisions."
            save_json(root / "early_predictions.json", documents["early_predictions"])
            hashes["early_predictions"] = sha256(root / "early_predictions.json")
            save_json(root / "hashes.json", hashes)
            self.assertEqual(2, main(args))
            unchanged = {p.relative_to(root / "output").as_posix(): sha256(p) for p in (root / "output").rglob("*") if p.is_file()}
            self.assertEqual(before, unchanged)


if __name__ == "__main__":
    unittest.main()
