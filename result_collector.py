"""
Result Collector — Integration Layer
Team Alpha — Task 6

Subscribes to scan results from the async executor (Task 5),
buffers response pairs per endpoint, runs the diff engine,
classifies issues, and flushes to the report generator.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from diff_engine import batch_compare, compare_responses
from issue_classifier import classify_all, classify_diff
from models import DiffResult, Issue, ScanResponse
from report_generator import build_report, save_report

logger = logging.getLogger(__name__)


# ─── Collector class ──────────────────────────────────────────────────────────

class ScanResultCollector:
    """
    Collects ScanResponse objects emitted by the async scan executor,
    pairs them by endpoint+method, diffs them, and builds a final report.

    Usage:
        collector = ScanResultCollector(target_url="https://api.example.com")

        # Called by the async executor for each response received:
        collector.on_result(response)

        # After all scanning is done:
        report = collector.flush()
        paths  = collector.save(report, output_dir="./reports")
    """

    def __init__(
        self,
        target_url: str,
        scan_name: str = "API Security Scan",
        similarity_threshold: float = 0.65,
        reference_role: str = "admin",
        on_issue_found: Optional[Callable[[Issue], None]] = None,
    ):
        """
        Args:
            target_url:           Base URL of the target API.
            scan_name:            Human-readable name for this scan run.
            similarity_threshold: Body similarity threshold for BOLA detection.
            reference_role:       Role treated as the "owner" in each pair (User A).
            on_issue_found:       Optional callback fired immediately when an issue
                                  is classified (for live streaming to a UI/log).
        """
        self.target_url           = target_url
        self.scan_name            = scan_name
        self.similarity_threshold = similarity_threshold
        self.reference_role       = reference_role
        self.on_issue_found       = on_issue_found

        # endpoint_key → list of responses received
        self._buffer: Dict[str, List[ScanResponse]] = defaultdict(list)

        self._diffs:  List[DiffResult] = []
        self._issues: List[Issue]      = []
        self._request_count: int       = 0
        self._scan_start: datetime     = datetime.utcnow()

    # ─── Ingest ───────────────────────────────────────────────────────────────

    def on_result(self, response: ScanResponse) -> None:
        """
        Ingest a single ScanResponse from the async executor.
        Call this for every HTTP response captured during the scan.
        """
        key = f"{response.method}::{response.endpoint}"
        self._buffer[key].append(response)
        self._request_count += 1
        logger.debug("Buffered response: %s [%s] user=%s", key, response.status_code, response.user_id)

    def on_results_batch(self, responses: List[ScanResponse]) -> None:
        """Ingest multiple responses at once."""
        for r in responses:
            self.on_result(r)

    # ─── Process ──────────────────────────────────────────────────────────────

    def _build_pairs(
        self, responses: List[ScanResponse]
    ) -> List[Tuple[ScanResponse, ScanResponse]]:
        """
        From a list of responses for one endpoint, build (reference, challenger) pairs.

        Strategy:
          - Reference (User A) = response from reference_role (e.g. admin / owner).
          - Challenger (User B) = every other response.
          - If no reference role found, use the first response as reference.
        """
        refs = [r for r in responses if (r.role or "").lower() == self.reference_role.lower()]
        others = [r for r in responses if r not in refs]

        if not refs:
            if len(responses) < 2:
                return []
            refs = [responses[0]]
            others = responses[1:]

        pairs = []
        for ref in refs:
            for other in others:
                if ref.user_id != other.user_id or ref.role != other.role:
                    pairs.append((ref, other))
        return pairs

    def process_buffered(self) -> List[Issue]:
        """
        Process all buffered responses:
          1. Build response pairs per endpoint.
          2. Run diff engine on each pair.
          3. Classify anomalies into issues.
          4. Fire on_issue_found callback if set.

        Returns the full list of discovered Issues.
        """
        all_issues: List[Issue] = []

        for endpoint_key, responses in self._buffer.items():
            if len(responses) < 2:
                logger.debug("Skipping %s — only 1 response buffered", endpoint_key)
                continue

            pairs = self._build_pairs(responses)
            if not pairs:
                continue

            for ref, challenger in pairs:
                diff = compare_responses(ref, challenger, self.similarity_threshold)
                self._diffs.append(diff)

                if diff.is_anomaly:
                    issues = classify_diff(diff)
                    for issue in issues:
                        logger.info(
                            "Issue found: [%s] %s on %s",
                            issue.severity.value,
                            issue.issue_type.value,
                            issue.endpoint,
                        )
                        all_issues.append(issue)
                        if self.on_issue_found:
                            try:
                                self.on_issue_found(issue)
                            except Exception as e:
                                logger.warning("on_issue_found callback failed: %s", e)

        self._issues = all_issues
        return all_issues

    # ─── Report ───────────────────────────────────────────────────────────────

    def flush(self) -> "ScanReport":  # type: ignore[name-defined]  # noqa: F821
        """
        Process all buffered results and build a ScanReport.
        Call this once after all scan results have been ingested.
        """
        from report_generator import ScanReport  # local import to avoid circular

        if not self._issues:
            self.process_buffered()

        scan_end = datetime.utcnow()

        return build_report(
            issues=self._issues,
            target_url=self.target_url,
            scan_name=self.scan_name,
            total_endpoints=len(self._buffer),
            total_requests=self._request_count,
            scan_start=self._scan_start,
            scan_end=scan_end,
            metadata={
                "similarity_threshold": self.similarity_threshold,
                "reference_role":       self.reference_role,
                "total_diffs":          len(self._diffs),
                "anomaly_diffs":        sum(1 for d in self._diffs if d.is_anomaly),
            },
        )

    def save(self, report, output_dir: str = "./reports") -> Dict[str, str]:
        """Save the report to disk in all formats. Returns dict of format→path."""
        paths = save_report(report, output_dir=output_dir)
        for fmt, path in paths.items():
            logger.info("Report saved [%s]: %s", fmt.upper(), path)
        return paths

    # ─── Stats ────────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return {
            "endpoints_buffered": len(self._buffer),
            "total_requests":     self._request_count,
            "diffs_run":          len(self._diffs),
            "anomalies_detected": sum(1 for d in self._diffs if d.is_anomaly),
            "issues_found":       len(self._issues),
        }

    def reset(self) -> None:
        """Clear all buffered state (allows reuse for a new scan)."""
        self._buffer.clear()
        self._diffs.clear()
        self._issues.clear()
        self._request_count = 0
        self._scan_start = datetime.utcnow()
