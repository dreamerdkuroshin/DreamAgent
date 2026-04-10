"""Analyze failures to identify improvement opportunities."""

from typing import Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FailureAnalysis:
    """Analysis of a failure."""
    failure_type: str
    root_cause: str
    severity: int
    recommendations: List[str]


class FailureAnalyzer:
    """Analyze agent and system failures."""

    def __init__(self):
        """Initialize failure analyzer."""
        self.failures: List[Dict[str, Any]] = []
        self.analysis_cache: Dict[str, FailureAnalysis] = {}

    def record_failure(self, failure_data: Dict[str, Any]) -> None:
        """Record a failure occurrence.
        
        Args:
            failure_data: Data about the failure
        """
        self.failures.append(failure_data)

    def analyze_failure(self, failure_id: str) -> FailureAnalysis:
        """Analyze a specific failure.
        
        Args:
            failure_id: ID of the failure to analyze
            
        Returns:
            Failure analysis results
        """
        # Search for failure data
        failure_data = next((f for f in self.failures if f.get("id") == failure_id), None)
        if not failure_data:
            logger.warning(f"Failure with ID {failure_id} not found.")
            return FailureAnalysis("unknown", "ID not found", 1, [])

        error_msg = failure_data.get("error", "").lower()
        
        # Classify failure
        ftype = "runtime"
        if "timeout" in error_msg or "deadline" in error_msg:
            ftype = "timeout"
        elif any(x in error_msg for x in ["auth", "permission", "401", "403", "token"]):
            ftype = "auth"
        elif any(x in error_msg for x in ["import", "module not found", "no module named"]):
            ftype = "import"
        elif any(x in error_msg for x in ["syntax", "indentation"]):
            ftype = "syntax"
        
        # Determine base severity
        severity = 2
        if ftype == "auth": severity = 4
        elif ftype == "timeout": severity = 3
        elif ftype == "syntax": severity = 2
        elif ftype == "import": severity = 4
        
        # Frequency-bump severity
        count = sum(1 for f in self.failures if f.get("type", "").lower() == ftype or
                    (f.get("error", "").lower() and ftype in f.get("error", "").lower()))
        if count > 5: severity = min(5, severity + 2)
        elif count > 2: severity = min(5, severity + 1)

        # Generate recommendations
        recs = []
        if ftype == "timeout":
            recs = ["Increase timeout limits", "Optimize request payload", "Check network latency"]
        elif ftype == "auth":
            recs = ["Refresh OAuth token", "Verify API key permissions", "Re-authenticate user"]
        elif ftype == "import":
            recs = ["Install missing dependencies", "Check PYTHONPATH", "Verify virtual environment"]
        elif ftype == "syntax":
            recs = ["Review code for syntax errors", "Run a linter before execution"]
        else:
            recs = ["Check stack trace for logical errors", "Add more verbose logging"]

        analysis = FailureAnalysis(
            failure_type=ftype,
            root_cause=failure_data.get("cause", "Unknown logical error"),
            severity=severity,
            recommendations=recs
        )
        
        self.analysis_cache[failure_id] = analysis
        return analysis

    def get_improvement_recommendations(self) -> List[str]:
        """Get recommendations for system improvement."""
        if not self.failures:
            return ["No failures recorded. System is stable."]

        # Aggregate and deduplicate recommendations
        all_recs = []
        type_counts = {}
        
        for f in self.failures:
            # Reclassify to ensure consistency or use cached
            fid = f.get("id")
            if not fid:
                continue
                
            if fid not in self.analysis_cache:
                self.analyze_failure(str(fid))
            
            if fid in self.analysis_cache:
                analysis = self.analysis_cache[fid]
                ftype = analysis.failure_type
                type_counts[ftype] = type_counts.get(ftype, 0) + 1
                all_recs.extend(analysis.recommendations)

        if not type_counts:
            return ["Insufficient data for recommendations."]

        # Sort types by frequency
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        
        unique_recs = list(dict.fromkeys(all_recs))
        summary = [f"Most common failure type: {sorted_types[0][0]}"]
        summary.extend(unique_recs)
        
        return summary

