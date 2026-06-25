"""
Response Diff Engine
Team Alpha — Task 6

Stateless functions that compare two ScanResponse objects and produce
a DiffResult describing anomalies, leaked fields, and body similarity.
"""

import json
import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from models import DiffResult, ScanResponse


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _body_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Return a 0.0–1.0 similarity ratio between two response bodies."""
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _flatten_json(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """
    Recursively flatten a JSON object into dot-notation key → value pairs.
    Example: {"user": {"id": 1}} → {"user.id": 1}
    """
    result: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            result.update(_flatten_json(v, full_key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            full_key = f"{prefix}[{i}]"
            result.update(_flatten_json(v, full_key))
    else:
        result[prefix] = obj
    return result


def _extract_ids(obj: Any) -> Set[str]:
    """
    Extract plausible ID values (UUIDs, numeric IDs) from a JSON structure.
    Used to detect cross-tenant / cross-user ID leakage.
    """
    ids: Set[str] = set()
    flat = _flatten_json(obj) if obj else {}
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
    )
    int_id_pattern = re.compile(r"^\d{1,12}$")

    for key, val in flat.items():
        if val is None:
            continue
        val_str = str(val)
        if uuid_pattern.match(val_str):
            ids.add(val_str.lower())
        elif int_id_pattern.match(val_str) and any(
            k in key.lower() for k in ("id", "user", "owner", "account", "tenant")
        ):
            ids.add(val_str)
    return ids


def _field_diff(
    body_a: Optional[Any], body_b: Optional[Any]
) -> Tuple[List[str], List[str], List[str], Dict[str, Any]]:
    """
    Compare two parsed JSON bodies.
    Returns (leaked_fields, added_fields, removed_fields, value_changes).

    leaked_fields  = keys present in BOTH bodies (potential data shared)
    added_fields   = keys only in B (extra data B got that A didn't)
    removed_fields = keys only in A (data A had that B lacks)
    value_changes  = keys present in both but with different values
    """
    if body_a is None and body_b is None:
        return [], [], [], {}

    flat_a = _flatten_json(body_a) if body_a else {}
    flat_b = _flatten_json(body_b) if body_b else {}

    keys_a = set(flat_a.keys())
    keys_b = set(flat_b.keys())

    common      = keys_a & keys_b
    added        = list(keys_b - keys_a)
    removed      = list(keys_a - keys_b)
    leaked       = list(common)

    value_changes: Dict[str, Any] = {}
    for k in common:
        if flat_a[k] != flat_b[k]:
            value_changes[k] = {"a": flat_a[k], "b": flat_b[k]}

    return leaked, added, removed, value_changes


# ─── Main diff function ───────────────────────────────────────────────────────

def compare_responses(
    response_a: ScanResponse,
    response_b: ScanResponse,
    similarity_threshold: float = 0.65,
) -> DiffResult:
    """
    Compare two ScanResponse objects from different users/roles to the same
    endpoint and produce a DiffResult.

    Args:
        response_a:             Reference response (owner / higher privilege).
        response_b:             Challenger response (other user / lower privilege).
        similarity_threshold:   Body similarity above this triggers anomaly flag.

    Returns:
        DiffResult with all fields populated.
    """
    status_delta = response_b.status_code - response_a.status_code

    body_sim = _body_similarity(response_a.body, response_b.body)

    leaked_fields, added_fields, removed_fields, value_changes = _field_diff(
        response_a.body_json, response_b.body_json
    )

    # Cross-tenant: IDs from A showing up in B's body.
    # Only flag if the two responses belong to different tenants or different users,
    # AND the shared IDs are not simply the same resource being accessed legitimately.
    ids_a = _extract_ids(response_a.body_json)
    ids_b = _extract_ids(response_b.body_json)
    different_tenant = (
        response_a.tenant_id
        and response_b.tenant_id
        and response_a.tenant_id != response_b.tenant_id
    )
    different_user = response_a.user_id != response_b.user_id
    foreign_ids = (
        list(ids_a & ids_b)
        if (ids_a and ids_b and (different_tenant or different_user))
        else []
    )

    # Determine if this is an anomaly
    is_anomaly = False
    anomaly_reason = ""

    same_user = (response_a.user_id == response_b.user_id)
    same_tenant = (
        response_a.tenant_id is not None
        and response_a.tenant_id == response_b.tenant_id
    )

    if (
        not same_user
        and response_a.status_code == 200
        and response_b.status_code == 200
        and body_sim >= similarity_threshold
    ):
        is_anomaly = True
        anomaly_reason = (
            f"Both users received HTTP 200 with body similarity {body_sim:.0%}. "
            f"User A ({response_a.user_id}/{response_a.role}) and "
            f"User B ({response_b.user_id}/{response_b.role}) appear to receive the same data."
        )

    elif foreign_ids and not same_user and (
        response_a.status_code == 200 or response_b.status_code == 200
    ):
        is_anomaly = True
        anomaly_reason = (
            f"IDs belonging to User A ({response_a.user_id}) found in User B's response body: "
            + ", ".join(foreign_ids[:5])
        )

    elif (
        not same_user
        and response_a.status_code in (403, 401)
        and response_b.status_code == 200
    ):
        is_anomaly = True
        anomaly_reason = (
            f"User A received {response_a.status_code} but User B "
            f"({response_b.role}) received 200 on the same endpoint."
        )

    return DiffResult(
        endpoint=response_a.endpoint,
        method=response_a.method,
        response_a=response_a,
        response_b=response_b,
        status_delta=status_delta,
        body_similarity=round(body_sim, 4),
        leaked_fields=leaked_fields,
        added_fields=added_fields,
        removed_fields=removed_fields,
        value_changes=value_changes,
        is_anomaly=is_anomaly,
        anomaly_reason=anomaly_reason,
        foreign_ids_found=foreign_ids,
    )


def detect_data_leak(diff: DiffResult) -> bool:
    """
    Quick boolean check: did meaningful data leak across the authorization
    boundary? Uses body similarity + shared field count + foreign IDs.
    """
    high_similarity = diff.body_similarity >= 0.65
    many_shared_fields = len(diff.leaked_fields) >= 3
    foreign_ids_present = bool(diff.foreign_ids_found)

    return any([high_similarity, many_shared_fields, foreign_ids_present])


def batch_compare(
    pairs: List[Tuple[ScanResponse, ScanResponse]],
    similarity_threshold: float = 0.65,
) -> List[DiffResult]:
    """
    Compare a list of (response_a, response_b) pairs.
    Returns only results where is_anomaly is True.
    """
    results = []
    for a, b in pairs:
        diff = compare_responses(a, b, similarity_threshold)
        if diff.is_anomaly:
            results.append(diff)
    return results
