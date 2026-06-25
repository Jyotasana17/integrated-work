"""
Unit Tests — Task 6: Response Diff Engine + Integration & Reporting
Team Alpha

Run with:  pytest tests/test_diff_engine.py -v
"""

import json
from datetime import datetime

import pytest

from diff_engine import (
    _body_similarity,
    _extract_ids,
    _field_diff,
    batch_compare,
    compare_responses,
    detect_data_leak,
)
from issue_classifier import classify_diff, classify_all
from result_collector import ScanResultCollector
from models import IssueType, ScanResponse, SeverityLevel
from report_generator import (
    build_report,
    generate_json,
    generate_html,
    generate_markdown,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_response(
    endpoint="/api/users/42",
    method="GET",
    status_code=200,
    body=None,
    body_json=None,
    user_id="user_001",
    role="user",
    tenant_id="tenant_A",
    token="valid.jwt.token",
    url=None,
):
    return ScanResponse(
        endpoint=endpoint,
        method=method,
        url=url or f"https://api.example.com{endpoint}",
        status_code=status_code,
        body=body or json.dumps(body_json) if body_json else '{"id": 42, "name": "Alice"}',
        body_json=body_json or {"id": 42, "name": "Alice"},
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
        token=token,
        request_headers={"Authorization": f"Bearer {token}"},
    )


# ─── diff_engine tests ────────────────────────────────────────────────────────

class TestBodySimilarity:
    def test_identical_strings(self):
        assert _body_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        ratio = _body_similarity("abc", "xyz")
        assert ratio < 0.5

    def test_both_none(self):
        assert _body_similarity(None, None) == 1.0

    def test_one_none(self):
        assert _body_similarity("abc", None) == 0.0


class TestFieldDiff:
    def test_identical_bodies(self):
        body = {"id": 1, "name": "Alice", "email": "a@b.com"}
        leaked, added, removed, changes = _field_diff(body, body)
        assert set(leaked) == {"id", "name", "email"}
        assert added == []
        assert removed == []
        assert changes == {}

    def test_extra_field_in_b(self):
        a = {"id": 1, "name": "Alice"}
        b = {"id": 1, "name": "Alice", "secret_token": "abc123"}
        leaked, added, removed, changes = _field_diff(a, b)
        assert "secret_token" in added

    def test_value_change(self):
        a = {"id": 1, "role": "user"}
        b = {"id": 1, "role": "admin"}
        leaked, added, removed, changes = _field_diff(a, b)
        assert "role" in changes
        assert changes["role"]["a"] == "user"
        assert changes["role"]["b"] == "admin"


class TestExtractIds:
    def test_extracts_numeric_user_id(self):
        body = {"user_id": "12345", "name": "Bob"}
        ids = _extract_ids(body)
        assert "12345" in ids

    def test_extracts_uuid(self):
        body = {"id": "550e8400-e29b-41d4-a716-446655440000"}
        ids = _extract_ids(body)
        assert "550e8400-e29b-41d4-a716-446655440000" in ids

    def test_no_ids_in_plain_text(self):
        body = {"message": "hello world", "status": "ok"}
        ids = _extract_ids(body)
        assert len(ids) == 0


class TestCompareResponses:
    def test_same_user_no_anomaly(self):
        """Identical responses from the same user → no anomaly."""
        a = make_response(user_id="user_001", role="user")
        b = make_response(user_id="user_001", role="user")
        diff = compare_responses(a, b)
        assert diff.is_anomaly is False

    def test_bola_detection(self):
        """Different users, same data, both 200 → BOLA anomaly."""
        payload = {"id": 42, "name": "Alice", "email": "alice@example.com", "ssn": "123-45-6789"}
        a = make_response(
            user_id="user_001", role="user",
            body_json=payload, body=json.dumps(payload),
        )
        b = make_response(
            user_id="user_002", role="user",
            body_json=payload, body=json.dumps(payload),
        )
        diff = compare_responses(a, b)
        assert diff.is_anomaly is True
        assert diff.body_similarity >= 0.9

    def test_bfla_detection(self):
        """User A got 403, User B got 200 → BFLA anomaly."""
        a = make_response(status_code=403, user_id="admin_001", role="admin")
        b = make_response(status_code=200, user_id="user_002", role="user")
        diff = compare_responses(a, b)
        assert diff.is_anomaly is True
        assert "403" in diff.anomaly_reason or "User B" in diff.anomaly_reason

    def test_tenant_leak_detection(self):
        """IDs from Tenant A appear in Tenant B response → anomaly."""
        tenant_a_id = "550e8400-e29b-41d4-a716-446655440000"
        body_a = {"user_id": tenant_a_id, "name": "Alice"}
        body_b = {"user_id": "other-id", "related_user": tenant_a_id}  # leaked!
        a = make_response(user_id="user_001", tenant_id="tenant_A", body_json=body_a, body=json.dumps(body_a))
        b = make_response(user_id="user_002", tenant_id="tenant_B", body_json=body_b, body=json.dumps(body_b))
        diff = compare_responses(a, b)
        assert diff.is_anomaly is True
        assert tenant_a_id.lower() in [i.lower() for i in diff.foreign_ids_found]

    def test_no_anomaly_403_403(self):
        """Both get 403 — no issue."""
        a = make_response(status_code=403, user_id="user_001")
        b = make_response(status_code=403, user_id="user_002")
        diff = compare_responses(a, b)
        assert diff.is_anomaly is False

    def test_detect_data_leak_high_similarity(self):
        payload = {"id": 1, "name": "Bob", "email": "b@b.com", "phone": "555-1234", "role": "admin"}
        a = make_response(user_id="user_001", body_json=payload, body=json.dumps(payload))
        b = make_response(user_id="user_002", body_json=payload, body=json.dumps(payload))
        diff = compare_responses(a, b)
        assert detect_data_leak(diff) is True

    def test_batch_compare_filters_non_anomalies(self):
        safe_a = make_response(user_id="user_001")
        safe_b = make_response(user_id="user_001")

        vuln_payload = {"id": 99, "name": "Eve", "email": "e@e.com", "secret": "xyz"}
        vuln_a = make_response(user_id="user_001", body_json=vuln_payload, body=json.dumps(vuln_payload))
        vuln_b = make_response(user_id="user_002", body_json=vuln_payload, body=json.dumps(vuln_payload))

        results = batch_compare([(safe_a, safe_b), (vuln_a, vuln_b)])
        assert len(results) == 1
        assert results[0].is_anomaly is True


# ─── issue_classifier tests ───────────────────────────────────────────────────

class TestIssueClassifier:
    def test_bola_classified(self):
        payload = {"id": 42, "name": "Alice", "email": "a@b.com"}
        a = make_response(user_id="user_001", role="user", body_json=payload, body=json.dumps(payload))
        b = make_response(user_id="user_002", role="user", body_json=payload, body=json.dumps(payload))
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        types = [i.issue_type for i in issues]
        assert IssueType.BOLA in types

    def test_bfla_classified(self):
        a = make_response(status_code=403, user_id="admin_001", role="admin")
        b = make_response(status_code=200, user_id="user_002", role="user")
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        types = [i.issue_type for i in issues]
        assert IssueType.BFLA in types

    def test_tenant_leak_classified(self):
        tid = "550e8400-e29b-41d4-a716-446655440001"
        ba = {"user_id": tid, "data": "secret"}
        bb = {"user_id": "other", "ref": tid}
        a = make_response(user_id="u1", tenant_id="T1", body_json=ba, body=json.dumps(ba))
        b = make_response(user_id="u2", tenant_id="T2", body_json=bb, body=json.dumps(bb))
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        types = [i.issue_type for i in issues]
        assert IssueType.TENANT_LEAK in types

    def test_jwt_bypass_classified(self):
        a = make_response(user_id="admin", role="admin", status_code=200)
        b = make_response(
            user_id="attacker", role="guest", status_code=200,
            token="eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.payload.fake"
        )
        # Force anomaly for JWT bypass test
        diff = compare_responses(a, b)
        diff.is_anomaly = True
        issues = classify_diff(diff)
        types = [i.issue_type for i in issues]
        assert IssueType.JWT_BYPASS in types

    def test_no_issues_on_clean_diff(self):
        a = make_response(user_id="user_001")
        b = make_response(user_id="user_001")
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        assert issues == []

    def test_bola_critical_with_pii(self):
        payload = {"id": 1, "email": "a@b.com", "ssn": "123-45", "name": "Alice"}
        a = make_response(user_id="u1", body_json=payload, body=json.dumps(payload))
        b = make_response(user_id="u2", body_json=payload, body=json.dumps(payload))
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        bola_issues = [i for i in issues if i.issue_type == IssueType.BOLA]
        assert any(i.severity == SeverityLevel.CRITICAL for i in bola_issues)


# ─── report_generator tests ──────────────────────────────────────────────────

class TestReportGenerator:
    def _make_issue(self):
        payload = {"id": 42, "email": "x@y.com", "name": "Bob"}
        a = make_response(user_id="user_001", body_json=payload, body=json.dumps(payload))
        b = make_response(user_id="user_002", body_json=payload, body=json.dumps(payload))
        diff = compare_responses(a, b)
        issues = classify_diff(diff)
        return issues

    def test_build_report(self):
        issues = self._make_issue()
        report = build_report(issues, target_url="https://api.example.com", total_endpoints=5, total_requests=50)
        assert report.summary.total_issues == len(issues)
        assert report.target_url == "https://api.example.com"

    def test_generate_json_valid(self):
        issues = self._make_issue()
        report = build_report(issues, target_url="https://api.example.com")
        output = generate_json(report)
        data = json.loads(output)
        assert "issues" in data
        assert "summary" in data
        assert data["summary"]["total_issues"] == len(issues)

    def test_generate_markdown_contains_title(self):
        issues = self._make_issue()
        report = build_report(issues, target_url="https://api.example.com", scan_name="Test Scan")
        md = generate_markdown(report)
        assert "# Test Scan" in md
        assert "BOLA" in md

    def test_generate_html_contains_structure(self):
        issues = self._make_issue()
        report = build_report(issues, target_url="https://api.example.com")
        html = generate_html(report)
        assert "<!DOCTYPE html>" in html
        assert "BOLA" in html
        assert "summary-grid" in html

    def test_empty_report(self):
        report = build_report([], target_url="https://api.example.com")
        assert report.summary.total_issues == 0
        md = generate_markdown(report)
        assert "No issues found" in md


# ─── result_collector tests ───────────────────────────────────────────────────

class TestScanResultCollector:
    def test_basic_collection_and_flush(self):
        payload = {"id": 1, "email": "a@b.com"}
        collector = ScanResultCollector(target_url="https://api.example.com")

        collector.on_result(make_response(user_id="user_001", role="admin", body_json=payload, body=json.dumps(payload)))
        collector.on_result(make_response(user_id="user_002", role="user",  body_json=payload, body=json.dumps(payload)))

        report = collector.flush()
        assert report.summary.total_requests == 2
        assert report.summary.total_endpoints == 1

    def test_on_issue_callback_fires(self):
        fired = []
        payload = {"id": 99, "email": "c@d.com", "ssn": "000"}
        collector = ScanResultCollector(
            target_url="https://api.example.com",
            on_issue_found=lambda issue: fired.append(issue),
        )

        collector.on_result(make_response(user_id="user_001", role="admin", body_json=payload, body=json.dumps(payload)))
        collector.on_result(make_response(user_id="user_002", role="user",  body_json=payload, body=json.dumps(payload)))
        collector.process_buffered()

        assert len(fired) > 0

    def test_stats_updated_after_flush(self):
        collector = ScanResultCollector(target_url="https://api.example.com")
        for i in range(4):
            collector.on_result(make_response(user_id=f"user_{i:03d}", role="user"))
        collector.flush()
        stats = collector.stats
        assert stats["total_requests"] == 4

    def test_reset_clears_state(self):
        collector = ScanResultCollector(target_url="https://api.example.com")
        collector.on_result(make_response())
        collector.reset()
        assert collector.stats["total_requests"] == 0
        assert collector.stats["endpoints_buffered"] == 0
