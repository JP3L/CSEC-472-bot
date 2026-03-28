"""
Core validation engine for the cyberpunk Papers Please game.
Inspects entrants against security directives and determines inspection outcomes.

This is a Python port of the TypeScript inspector logic, adapted for the cyberpunk theme.
"""

from typing import Dict, Set, Optional
from datetime import datetime

from .models import Entrant, Document, SecurityDirective, InspectionResult
from . import theme


# ============================================================================
# MODULE CONSTANTS
# ============================================================================

CURRENT_DATE = "2032.11.22"


# ============================================================================
# MAIN INSPECTION FUNCTION
# ============================================================================


def inspect_entrant(entrant: Entrant, directive: SecurityDirective) -> InspectionResult:
    """
    Inspect an entrant against a security directive and determine the outcome.

    Checks are performed in priority order:
    1. Detainment checks (highest priority)
    2. Denial checks (if detainment passes)
    3. Approval (if all checks pass)

    Args:
        entrant: The person seeking access.
        directive: The current security directive with requirements and restrictions.

    Returns:
        InspectionResult with decision (allow/deny/detain), reason, and correctness.
    """

    # ========================================================================
    # DETAINMENT CHECKS (Highest Priority)
    # ========================================================================

    # 1. Wanted handle match
    if directive.wanted_handle:
        entrant_handle = _get_entrant_handle(entrant)
        if entrant_handle and entrant_handle == directive.wanted_handle:
            return InspectionResult(
                "detain",
                "Wanted by UACC Cyber Division",
                entrant.true_faction == theme.HOME_FACTION
            )

    # 2. ID# mismatch
    if not _check_consistency(entrant, "ID#"):
        id_values = _get_field_across_docs(entrant, "ID#")
        if len(id_values) > 1:
            return InspectionResult(
                "detain",
                "Document ID mismatch detected",
                False
            )

    # 3. Handle mismatch
    if not _check_consistency(entrant, "HANDLE"):
        handle_values = _get_field_across_docs(entrant, "HANDLE")
        if len(handle_values) > 1:
            return InspectionResult(
                "detain",
                "Handle inconsistency across documents",
                False
            )

    # 4. Faction mismatch
    if not _check_consistency(entrant, "FACTION"):
        faction_values = _get_field_across_docs(entrant, "FACTION")
        if len(faction_values) > 1:
            return InspectionResult(
                "detain",
                "Faction discrepancy detected",
                False
            )

    # 5. DOB mismatch
    if not _check_consistency(entrant, "DOB"):
        dob_values = _get_field_across_docs(entrant, "DOB")
        if len(dob_values) > 1:
            return InspectionResult(
                "detain",
                "Date of birth mismatch",
                False
            )

    # 6. Height mismatch
    if not _check_consistency(entrant, "HEIGHT"):
        height_values = _get_field_across_docs(entrant, "HEIGHT")
        if len(height_values) > 1:
            return InspectionResult(
                "detain",
                "Biometric height mismatch",
                False
            )

    # 7. Weight mismatch
    if not _check_consistency(entrant, "WEIGHT"):
        weight_values = _get_field_across_docs(entrant, "WEIGHT")
        if len(weight_values) > 1:
            return InspectionResult(
                "detain",
                "Biometric weight mismatch",
                False
            )

    # ========================================================================
    # DENIAL CHECKS (Checked if detainment clears)
    # ========================================================================

    # Get entrant's faction for denial checks
    entrant_faction = _get_entrant_faction(entrant)
    if not entrant_faction:
        return InspectionResult(
            "deny",
            "No faction data available",
            False
        )

    # 1. No digital_id (missing primary identity certificate)
    digital_ids = entrant.get_documents_by_type("digital_id")
    if not digital_ids:
        return InspectionResult(
            "deny",
            "Missing digital identity certificate",
            entrant_faction != theme.HOME_FACTION
        )

    # 2. Faction banned
    if directive.is_faction_denied(entrant_faction):
        return InspectionResult(
            "deny",
            f"Faction {entrant_faction} access denied by directive",
            entrant_faction != theme.HOME_FACTION
        )

    # 3. Faction not allowed (if allowed_factions is restricted)
    if directive.allowed_factions and entrant_faction not in directive.allowed_factions:
        if entrant_faction != theme.HOME_FACTION:
            return InspectionResult(
                "deny",
                f"Faction {entrant_faction} not authorized for access",
                True
            )

    # 4. Missing required documents
    required_docs = directive.get_required_docs(entrant_faction, _is_operator(entrant))
    for doc_type in required_docs:
        docs = entrant.get_documents_by_type(doc_type)
        if not docs:
            doc_name = theme.DOCUMENT_TYPES.get(doc_type, doc_type)
            return InspectionResult(
                "deny",
                f"Missing required {doc_name}",
                entrant_faction != theme.HOME_FACTION
            )

    # 5. Expired documents
    for doc in entrant.documents:
        if _is_expired(doc, CURRENT_DATE):
            doc_name = theme.DOCUMENT_TYPES.get(doc.doc_type, doc.doc_type)
            return InspectionResult(
                "deny",
                f"Expired {doc_name}",
                entrant_faction != theme.HOME_FACTION
            )

    # 6. Missing required scans
    required_scans = directive.get_required_scans(entrant_faction, _is_operator(entrant))
    if required_scans:
        integrity_reports = entrant.get_documents_by_type("integrity_report")
        if not integrity_reports:
            # Missing the integrity report that would list scans
            first_scan = next(iter(required_scans))
            return InspectionResult(
                "deny",
                f"Missing required {first_scan} clearance",
                entrant_faction != theme.HOME_FACTION
            )

        # Check if the integrity report lists all required scans
        report = integrity_reports[0]
        scans_field = report.fields.get("SCANS", "")
        scans_list = set(scans_field.split(",")) if scans_field else set()
        scans_list = {s.strip() for s in scans_list}  # Clean whitespace

        missing_scans = required_scans - scans_list
        if missing_scans:
            first_missing = next(iter(missing_scans))
            return InspectionResult(
                "deny",
                f"Missing required {first_missing} clearance",
                entrant_faction != theme.HOME_FACTION
            )

    # 7. Operator without required docs
    if _is_operator(entrant):
        operator_docs = directive.required_docs_for_operators
        for doc_type in operator_docs:
            docs = entrant.get_documents_by_type(doc_type)
            if not docs:
                doc_name = theme.DOCUMENT_TYPES.get(doc_type, doc_type)
                return InspectionResult(
                    "deny",
                    f"Missing required {doc_name} for operations personnel",
                    entrant_faction != theme.HOME_FACTION
                )

    # ========================================================================
    # SUCCESS (All checks passed)
    # ========================================================================

    if entrant_faction == theme.HOME_FACTION:
        return InspectionResult(
            "allow",
            theme.HOME_SUCCESS,
            True
        )
    else:
        return InspectionResult(
            "allow",
            theme.FOREIGN_SUCCESS,
            True
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _get_field_across_docs(entrant: Entrant, field_name: str) -> Set[str]:
    """
    Collect all unique values for a field across all documents.

    Args:
        entrant: The entrant to search.
        field_name: The field name to look for (e.g., "ID#", "HANDLE").

    Returns:
        Set of unique values found for that field across all documents.
    """
    values = set()
    for doc in entrant.documents:
        if field_name in doc.fields:
            values.add(doc.fields[field_name])
    return values


def _check_consistency(entrant: Entrant, field_name: str) -> bool:
    """
    Check if all documents with a given field agree on the value.

    Args:
        entrant: The entrant to check.
        field_name: The field name to check (e.g., "ID#", "DOB").

    Returns:
        True if all documents agree (or field is not present in any doc).
        False if documents have conflicting values for this field.
    """
    values = _get_field_across_docs(entrant, field_name)
    # If 0 or 1 unique values, they're consistent
    return len(values) <= 1


def _get_entrant_faction(entrant: Entrant) -> Optional[str]:
    """
    Get the entrant's faction, preferring digital_id, then any document.

    Args:
        entrant: The entrant to check.

    Returns:
        The faction string, or None if not found.
    """
    # Prefer faction from digital_id
    digital_ids = entrant.get_documents_by_type("digital_id")
    if digital_ids and digital_ids[0].faction:
        return digital_ids[0].faction

    # Fallback to any document's faction
    return entrant.primary_faction


def _get_entrant_handle(entrant: Entrant) -> Optional[str]:
    """
    Get the entrant's handle, preferring digital_id, then any document.

    Args:
        entrant: The entrant to check.

    Returns:
        The handle string, or None if not found.
    """
    return entrant.primary_handle


def _is_expired(doc: Document, reference_date: str = CURRENT_DATE) -> bool:
    """
    Check if a document is expired based on a reference date.

    Args:
        doc: The document to check.
        reference_date: The date to check against (format: "YYYY.MM.DD").
                       Defaults to CURRENT_DATE.

    Returns:
        True if the document has an EXP field and is expired relative to reference_date.
        False if no EXP field or document is not expired.
    """
    if "EXP" not in doc.fields:
        return False

    try:
        # Parse reference date (format: "YYYY.MM.DD")
        ref_parts = reference_date.split(".")
        ref_date = datetime(int(ref_parts[0]), int(ref_parts[1]), int(ref_parts[2]))

        # Parse expiration date (format: "YYYY.MM.DD" or "YYYY-MM-DD")
        exp_str = doc.fields["EXP"]
        if "." in exp_str:
            exp_parts = exp_str.split(".")
            exp_date = datetime(int(exp_parts[0]), int(exp_parts[1]), int(exp_parts[2]))
        else:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")

        # Document is expired if reference date is after expiration date
        return ref_date > exp_date
    except (ValueError, IndexError, KeyError):
        # If we can't parse the dates, assume not expired to avoid false positives
        return False


def _is_operator(entrant: Entrant) -> bool:
    """
    Check if the entrant is an operator (has PURPOSE=OPERATION in access_token).

    Args:
        entrant: The entrant to check.

    Returns:
        True if any access_token has PURPOSE=OPERATION, False otherwise.
    """
    access_tokens = entrant.get_documents_by_type("access_token")
    for token in access_tokens:
        if token.fields.get("PURPOSE") == "OPERATION":
            return True
    return False
