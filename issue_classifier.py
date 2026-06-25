"""
Issue Classifier
Team Alpha — Task 6

Takes a DiffResult and applies rule-based detection to classify
security issues: BOLA, BFLA, Tenant Leak, JWT Bypass, Privilege Escalation.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from models import (
    DiffResult,
    Issue,
    IssueType,
    ReproductionSteps,
    ScanResponse,
    SeverityLevel,
)


# ─── CWE / OWASP mappings ────────────────────────────────────────────────────

ISSUE_META = {
    IssueType.BOLA: {
        "cwe":   "CWE-285",
        "owasp": "OWASP API1:2023 — Broken Object Level Authorization",
        "recommendation": (
            "Validate that the authenticated user owns or has explicit permission "
            "to access the requested object. Use indirect object references or "
            "enforce ownership checks server-side on every request."
        ),
    },
    IssueType.BFLA: {
        "cwe":   "CWE-862",
        "owasp": "OWASP API5:2023 — Broken Function Level Authorization",
        "recommendation": (
            "Implement role-based access control (RBAC) checks at the function/action "
            "level. Do not rely solely on UI hiding of admin features. Enforce "
            "permissions in the business logic layer on every API call."
        ),
    },
    IssueType.TENANT_LEAK: {
        "cwe":   "CWE-284",
        "owasp": "OWASP API1:2023 — Broken Object Level Authorization (Multi-tenant)",
        "recommendation": (
            "Ensure every database query and response is scoped by tenant_id. "
            "Never derive tenant context from user-supplied input alone. "
            "Add automated tests that assert cross-tenant queries return 0 results."
        ),
    },
    IssueType.JWT_BYPASS: {
        "cwe":   "CWE-287",
        "owasp": "OWASP API2:2023 — Broken Authentication",
        "recommendation": (
            "Always verify JWT signature with a strong secret or asymmetric key. "
            "Reject tokens with alg=none. Use a well-maintained JWT library and "
            "pin the expected algorithm. Rotate secrets regularly."
        ),
    },
    IssueType.PRIV_ESCALATION: {
        "cwe":   "CWE-269",
        "owasp": "OWASP API5:2023 — Broken Function Level Authorization",
        "recommendation": (
            "Enforce the principle of least privilege. Each role should only be "
            "granted the minimum permissions required. Re-validate role on every "
            "sensitive action, not just at login."
        ),
    },
    IssueType.INFO_DISCLOSURE: {
        "cwe":   "CWE-200",
        "owasp": "OWASP API3:2023 — Broken Object Property Level Authorization",
        "recommendation": (
            "Apply field-level filtering based on the caller's role before "
            "serializing responses. Use allowlist-based serializers rather than "
            "returning full model objects."
        ),
    },
}


# ─── Severity rules ──────────────────────────────────────────────────────────

def _score_bola(diff: DiffResult) -> SeverityLevel:
    """BOLA severity depends on how much data leaked and what type."""
    pii_keywords = {"email", "phone", "ssn", "password", "address", "dob", "credit", "token"}
    has_pii = any(
        any(p in f.lower() for p in pii_keywords)
        for f in diff.leaked_fields
    )
    if has_pii or diff.body_similarity >= 0.9:
        return SeverityLevel.CRITICAL
    if diff.body_similarity >= 0.7 or len(diff.leaked_fields) >= 5:
        return SeverityLevel.HIGH
    return SeverityLevel.MEDIUM


def _score_bfla(diff: DiffResult) -> SeverityLevel:
    """BFLA severity depends on what the function does."""
    method = diff.method.upper()
    destructive = method in ("DELETE", "PUT", "PATCH")
    admin_hints = any(
        k in diff.endpoint.lower()
        for k in ("admin", "manage", "config", "setting", "role", "permission", "internal")
    )
    if destructive and admin_hints:
        return SeverityLevel.CRITICAL
    if destructive or admin_hints:
        return SeverityLevel.HIGH
    return SeverityLevel.MEDIUM


def _build_curl(response: ScanResponse) -> str:
    """Generate a curl reproduction command from a ScanResponse."""
    headers = " ".join(
        f"-H '{k}: {v}'" for k, v in response.request_headers.items()
    )
    body_flag = f"-d '{response.request_body}'" if response.request_body else ""
    return f"curl -X {response.method} {headers} {body_flag} '{response.url}'"


def _build_repro(diff: DiffResult, description: str) -> ReproductionSteps:
    a = diff.response_a
    b = diff.response_b
    return ReproductionSteps(
        description=description,
        request_method=diff.method,
        request_url=b.url,
        request_headers=b.request_headers,
        request_body=b.request_body,
        user_a_token=a.token,
        user_b_token=b.token,
        expected_status=403,
        actual_status=b.status_code,
        curl_command=_build_curl(b),
    )


# ─── Individual classifiers ───────────────────────────────────────────────────

def _check_bola(diff: DiffResult) -> Optional[Issue]:
    """
    BOLA: User B accessed an object owned by User A and got similar/identical data.
    Trigger: both 200, high body similarity, different user_ids.
    """
    a, b = diff.response_a, diff.response_b
    if (
        a.status_code == 200
        and b.status_code == 200
        and diff.body_similarity >= 0.65
        and a.user_id != b.user_id
    ):
        severity = _score_bola(diff)
        meta = ISSUE_META[IssueType.BOLA]
        return Issue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.BOLA,
            severity=severity,
            title=f"BOLA — {diff.method} {diff.endpoint}",
            description=(
                f"User '{b.user_id}' (role: {b.role}) received data belonging to "
                f"User '{a.user_id}' with {diff.body_similarity:.0%} body similarity. "
                f"{len(diff.leaked_fields)} fields were present in both responses."
            ),
            endpoint=diff.endpoint,
            method=diff.method,
            diff=diff,
            repro=_build_repro(diff, "Send request as User B using User B's token to User A's resource URL."),
            recommendation=meta["recommendation"],
            cwe=meta["cwe"],
            owasp=meta["owasp"],
        )
    return None


def _check_bfla(diff: DiffResult) -> Optional[Issue]:
    """
    BFLA: Lower-privilege user successfully called a function that should be restricted.
    Trigger: User A got 403/401, User B (lower role) got 200.
    """
    a, b = diff.response_a, diff.response_b
    if a.status_code in (403, 401) and b.status_code == 200:
        severity = _score_bfla(diff)
        meta = ISSUE_META[IssueType.BFLA]
        return Issue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.BFLA,
            severity=severity,
            title=f"BFLA — {diff.method} {diff.endpoint}",
            description=(
                f"User '{a.user_id}' (role: {a.role}) received HTTP {a.status_code} "
                f"but User '{b.user_id}' (role: {b.role}) received HTTP 200 on the same endpoint. "
                f"Function-level authorization appears missing."
            ),
            endpoint=diff.endpoint,
            method=diff.method,
            diff=diff,
            repro=_build_repro(diff, "Send request as lower-privilege User B. Observe 200 where 403 expected."),
            recommendation=meta["recommendation"],
            cwe=meta["cwe"],
            owasp=meta["owasp"],
        )
    return None


def _check_tenant_leak(diff: DiffResult) -> Optional[Issue]:
    """
    Tenant Leak: IDs or objects from Tenant A appear in Tenant B's response.
    Trigger: foreign IDs from response_a found inside response_b body.
    """
    if not diff.foreign_ids_found:
        return None

    a, b = diff.response_a, diff.response_b
    if a.tenant_id and b.tenant_id and a.tenant_id == b.tenant_id:
        return None  # Same tenant — not a cross-tenant issue

    meta = ISSUE_META[IssueType.TENANT_LEAK]
    return Issue(
        issue_id=str(uuid.uuid4()),
        issue_type=IssueType.TENANT_LEAK,
        severity=SeverityLevel.CRITICAL,
        title=f"Tenant Data Leak — {diff.method} {diff.endpoint}",
        description=(
            f"IDs belonging to Tenant '{a.tenant_id}' (User '{a.user_id}') were found "
            f"in the response of Tenant '{b.tenant_id}' (User '{b.user_id}'). "
            f"Leaked IDs: {', '.join(diff.foreign_ids_found[:5])}."
        ),
        endpoint=diff.endpoint,
        method=diff.method,
        diff=diff,
        repro=_build_repro(diff, "Authenticate as Tenant B, call the endpoint, observe Tenant A's object IDs in response."),
        recommendation=meta["recommendation"],
        cwe=meta["cwe"],
        owasp=meta["owasp"],
    )


def _check_jwt_bypass(diff: DiffResult) -> Optional[Issue]:
    """
    JWT Bypass: A tampered/invalid token still returned 200.
    Trigger: response_b token contains a known tamper marker AND status is 200.
    """
    b = diff.response_b
    tamper_markers = ("alg=none", "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0", "__tampered__")
    token = b.token or ""

    if b.status_code == 200 and any(m in token for m in tamper_markers):
        meta = ISSUE_META[IssueType.JWT_BYPASS]
        return Issue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.JWT_BYPASS,
            severity=SeverityLevel.CRITICAL,
            title=f"JWT Bypass — {diff.method} {diff.endpoint}",
            description=(
                f"A tampered JWT token was accepted by {diff.endpoint}. "
                f"The server returned HTTP {b.status_code} instead of 401/403. "
                f"This may indicate the signature is not being verified."
            ),
            endpoint=diff.endpoint,
            method=diff.method,
            diff=diff,
            repro=_build_repro(diff, "Send request with tampered JWT (alg=none or modified payload). Observe 200 response."),
            recommendation=meta["recommendation"],
            cwe=meta["cwe"],
            owasp=meta["owasp"],
        )
    return None


def _check_privilege_escalation(diff: DiffResult) -> Optional[Issue]:
    """
    Privilege Escalation: User B with a lower role accessed a higher-role resource.
    Trigger: roles differ, both 200, endpoint has role/admin indicators.
    """
    a, b = diff.response_a, diff.response_b
    role_hierarchy = {"admin": 3, "manager": 2, "user": 1, "guest": 0}

    role_a_rank = role_hierarchy.get((a.role or "").lower(), 1)
    role_b_rank = role_hierarchy.get((b.role or "").lower(), 1)

    if (
        a.status_code == 200
        and b.status_code == 200
        and role_b_rank < role_a_rank
        and diff.body_similarity >= 0.5
    ):
        meta = ISSUE_META[IssueType.PRIV_ESCALATION]
        return Issue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.PRIV_ESCALATION,
            severity=SeverityLevel.HIGH,
            title=f"Privilege Escalation — {diff.method} {diff.endpoint}",
            description=(
                f"User '{b.user_id}' with role '{b.role}' accessed a resource "
                f"that should require role '{a.role}'. "
                f"Response body similarity: {diff.body_similarity:.0%}."
            ),
            endpoint=diff.endpoint,
            method=diff.method,
            diff=diff,
            repro=_build_repro(diff, "Authenticate as lower-privilege user and call the higher-privilege endpoint."),
            recommendation=meta["recommendation"],
            cwe=meta["cwe"],
            owasp=meta["owasp"],
        )
    return None


def _check_info_disclosure(diff: DiffResult) -> Optional[Issue]:
    """
    Info Disclosure: Extra fields returned to unauthorized user (not full BOLA).
    Trigger: added_fields in B's response that shouldn't be there.
    """
    sensitive_hints = {"token", "secret", "key", "hash", "internal", "debug", "password", "private"}
    sensitive_fields = [
        f for f in diff.added_fields
        if any(h in f.lower() for h in sensitive_hints)
    ]

    if sensitive_fields:
        meta = ISSUE_META[IssueType.INFO_DISCLOSURE]
        return Issue(
            issue_id=str(uuid.uuid4()),
            issue_type=IssueType.INFO_DISCLOSURE,
            severity=SeverityLevel.MEDIUM,
            title=f"Info Disclosure — {diff.method} {diff.endpoint}",
            description=(
                f"User '{diff.response_b.user_id}' received sensitive fields not "
                f"present in the reference response: {', '.join(sensitive_fields)}."
            ),
            endpoint=diff.endpoint,
            method=diff.method,
            diff=diff,
            repro=_build_repro(diff, "Send request as User B and inspect response body for extra sensitive fields."),
            recommendation=meta["recommendation"],
            cwe=meta["cwe"],
            owasp=meta["owasp"],
        )
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def classify_diff(diff: DiffResult) -> List[Issue]:
    """
    Run all classifiers against a DiffResult.
    Returns a (possibly empty) list of Issues found.
    """
    if not diff.is_anomaly:
        return []

    checkers = [
        _check_jwt_bypass,
        _check_tenant_leak,
        _check_bola,
        _check_bfla,
        _check_privilege_escalation,
        _check_info_disclosure,
    ]

    issues = []
    for checker in checkers:
        result = checker(diff)
        if result:
            issues.append(result)

    return issues


def classify_all(diffs: List[DiffResult]) -> List[Issue]:
    """Run classify_diff across a list of DiffResults."""
    all_issues: List[Issue] = []
    for diff in diffs:
        all_issues.extend(classify_diff(diff))
    return all_issues
