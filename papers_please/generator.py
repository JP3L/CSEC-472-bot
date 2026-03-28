"""
Procedural content generator for the cyberpunk Papers Please Discord game.
Generates security directives and entrants with appropriate difficulty scaling.
"""

import random
from typing import Tuple, Set, Dict, Optional
from datetime import datetime, timedelta

from .models import Document, Entrant, SecurityDirective, InspectionResult
from .engine import inspect_entrant
from . import theme


# ============================================================================
# DIRECTIVE GENERATION
# ============================================================================


def generate_directive(difficulty: int) -> SecurityDirective:
    """
    Generate a security directive with rules that scale by difficulty level.

    Difficulty scaling:
    - Level 0: Basic digital_id requirement
    - Level 1: Add allowed factions + access_token requirement
    - Level 2: Deny a faction + add scan requirement
    - Level 3: Add wanted handle + operator doc requirement
    - Level 4+: Accumulate more rules (stack previous + new ones)

    Args:
        difficulty: 0-based difficulty level

    Returns:
        SecurityDirective with formatted raw_text and structured rules
    """
    directive = SecurityDirective(raw_text="")

    # Start with base rule
    directive_rules = ["All entrants require digital identity certificate."]

    # Level 0: Just the base requirement (digital_id)
    if difficulty < 1:
        pass

    # Level 1+: Add allowed factions and access_token requirement
    if difficulty >= 1:
        # Pick 2-3 allowed factions (always include UACC)
        num_allowed = random.randint(2, 3)
        allowed = [theme.HOME_FACTION]
        other = [f for f in theme.FACTIONS if f != theme.HOME_FACTION]
        allowed.extend(random.sample(other, num_allowed - 1))
        directive.allowed_factions = set(allowed)

        factions_str = ", ".join(allowed)
        directive_rules.append(f"Allow operatives from: {factions_str}.")

        # Require access_token for a random faction (not UACC)
        token_faction = random.choice([f for f in allowed if f != theme.HOME_FACTION])
        directive.required_docs_by_faction[token_faction] = {"access_token"}
        directive_rules.append(f"{token_faction} operatives require access token.")

    # Level 2+: Deny a faction + add scan requirement
    if difficulty >= 2:
        # Pick a faction to deny (from those not in allowed list)
        available_to_deny = [f for f in theme.FACTIONS if f not in directive.allowed_factions]
        if available_to_deny:
            denied = random.choice(available_to_deny)
            directive.denied_factions.add(denied)
            directive_rules.append(f"Deny all operatives from: {denied}.")

        # Add scan requirement for a random faction
        scan_faction = random.choice(list(directive.allowed_factions))
        scan_type = random.choice(theme.SECURITY_CHECKS)
        if scan_faction not in directive.required_scans_by_faction:
            directive.required_scans_by_faction[scan_faction] = set()
        directive.required_scans_by_faction[scan_faction].add(scan_type)
        directive_rules.append(f"{scan_faction} operatives require {scan_type}.")

    # Level 3+: Add wanted handle + operator requirements
    if difficulty >= 3:
        # Add a wanted handle
        wanted = random.choice(theme.HACKER_HANDLES)
        directive.wanted_handle = wanted
        directive_rules.append(f'Wanted by Cyber Division: "{wanted}"')

        # Require clearance_code for operators
        directive.required_docs_for_operators.add("clearance_code")
        directive_rules.append("Operations personnel require contractor clearance.")

    # Level 4+: Keep stacking new rules
    if difficulty >= 4:
        # Add integrity_report requirement for all
        directive.required_scans_for_operators.add(random.choice(theme.SECURITY_CHECKS))
        directive_rules.append("All operations personnel require system integrity report.")

        # Optionally deny another faction
        available_to_deny = [f for f in theme.FACTIONS if f not in directive.allowed_factions]
        if available_to_deny and random.random() < 0.6:
            denied = random.choice(available_to_deny)
            directive.denied_factions.add(denied)
            directive_rules.append(f"Deny all operatives from: {denied}.")

    if difficulty >= 5:
        # Add more scan requirements
        for _ in range(random.randint(1, 2)):
            scan_faction = random.choice(list(directive.allowed_factions))
            scan_type = random.choice(theme.SECURITY_CHECKS)
            if scan_faction not in directive.required_scans_by_faction:
                directive.required_scans_by_faction[scan_faction] = set()
            directive.required_scans_by_faction[scan_faction].add(scan_type)

    # Format raw_text as a military/hacker briefing
    current_date = "2032.11.22"
    header = f"═══ SECURITY DIRECTIVE ═══\n[{current_date} // UACC CYBER COMMAND]\n"
    body = "\n".join(f"> {rule}" for rule in directive_rules)
    footer = "\n═════════════════════════════"

    directive.raw_text = header + body + footer

    return directive


# ============================================================================
# ENTRANT GENERATION
# ============================================================================


def generate_entrant(directive: SecurityDirective, difficulty: int) -> Tuple[Entrant, InspectionResult]:
    """
    Generate a random entrant and compute the correct inspection result.

    Distribution:
    - ~50% valid entrants (should be ALLOWED)
    - ~35% denial flaws (should be DENIED)
    - ~15% detainment flaws (should be DETAINED)

    Args:
        directive: The current security directive
        difficulty: Difficulty level (affects flaw complexity)

    Returns:
        Tuple of (generated Entrant, correct InspectionResult from engine)
    """
    # Determine entrant type
    roll = random.random()

    if roll < 0.50:
        # Generate VALID entrant
        entrant = _generate_valid_entrant(directive)
    elif roll < 0.85:
        # Generate entrant with DENIAL flaw
        entrant = _generate_valid_entrant(directive)
        _introduce_flaw(entrant, directive, difficulty, flaw_type="denial")
    else:
        # Generate entrant with DETAINMENT flaw
        entrant = _generate_valid_entrant(directive)
        _introduce_flaw(entrant, directive, difficulty, flaw_type="detainment")

    # Compute correct result using the engine
    result = inspect_entrant(entrant, directive)

    return entrant, result


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _random_id() -> str:
    """Generate a random ID in format: XX00A-AA0AA (alphanumeric)."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    id_part1 = "".join(random.choices(chars, k=5))
    id_part2 = "".join(random.choices(chars, k=5))
    return f"{id_part1}-{id_part2}"


def _random_dob() -> str:
    """Generate random DOB in YYYY.MM.DD format, aged 18-57 (born 1975-2010)."""
    year = random.randint(1975, 2010)
    month = random.randint(1, 12)
    # Days depend on month
    if month in [1, 3, 5, 7, 8, 10, 12]:
        day = random.randint(1, 31)
    elif month in [4, 6, 9, 11]:
        day = random.randint(1, 30)
    else:  # February
        day = random.randint(1, 28)
    return f"{year}.{month:02d}.{day:02d}"


def _random_expiry(valid: bool) -> str:
    """
    Generate random expiration date.

    Args:
        valid: If True, future date (2033-2035). If False, past date (2030-2032, before 2032.11.22).

    Returns:
        Date string in YYYY.MM.DD format
    """
    if valid:
        # Future dates: 2033-2035
        year = random.randint(2033, 2035)
        month = random.randint(1, 12)
        if month in [1, 3, 5, 7, 8, 10, 12]:
            day = random.randint(1, 31)
        elif month in [4, 6, 9, 11]:
            day = random.randint(1, 30)
        else:
            day = random.randint(1, 28)
    else:
        # Past dates: 2030 to early 2032 (before 2032.11.22)
        year = random.randint(2030, 2032)
        if year == 2032:
            # Before November 22
            month = random.randint(1, 10)  # Jan-Oct
        else:
            month = random.randint(1, 12)

        if month in [1, 3, 5, 7, 8, 10, 12]:
            day = random.randint(1, 31)
        elif month in [4, 6, 9, 11]:
            day = random.randint(1, 30)
        else:
            day = random.randint(1, 28)

    return f"{year}.{month:02d}.{day:02d}"


def _random_height() -> str:
    """Generate random height in cm (150-200cm)."""
    cm = random.randint(150, 200)
    return f"{cm}cm"


def _random_weight() -> str:
    """Generate random weight in kg (50-120kg)."""
    kg = random.randint(50, 120)
    return f"{kg}kg"


def _random_sex() -> str:
    """Return M or F."""
    return random.choice(["M", "F"])


def _build_document(doc_type: str, fields_dict: Dict[str, str]) -> Document:
    """
    Build a Document with proper fields.

    Args:
        doc_type: Document type (e.g., "digital_id", "access_token")
        fields_dict: Dictionary of field names to values

    Returns:
        Document instance
    """
    doc = Document(doc_type=doc_type, fields=fields_dict)
    return doc


def _generate_valid_entrant(directive: SecurityDirective) -> Entrant:
    """
    Generate a fully valid entrant that passes all current directive requirements.

    Args:
        directive: The security directive defining requirements

    Returns:
        Valid Entrant with all required documents
    """
    # Pick a faction from allowed factions
    if directive.allowed_factions:
        faction = random.choice(list(directive.allowed_factions))
    else:
        # If no restrictions, pick any non-denied faction
        available = [f for f in theme.FACTIONS if f not in directive.denied_factions]
        faction = random.choice(available) if available else theme.HOME_FACTION

    # Generate consistent personal data
    first_name, last_name = theme.random_name()
    handle = theme.random_handle()
    dob = _random_dob()
    height = _random_height()
    weight = _random_weight()
    sex = _random_sex()
    id_num = _random_id()
    issuing_node = random.choice(theme.ISSUING_NODES)

    entrant = Entrant(true_faction=faction)

    # Always include digital_id (base requirement)
    digital_id = _build_document("digital_id", {
        "ID#": id_num,
        "HANDLE": handle,
        "FACTION": faction,
        "DOB": dob,
        "SEX": sex,
        "ISSUING_NODE": issuing_node,
        "EXP": _random_expiry(valid=True),
    })
    entrant.documents.append(digital_id)

    # Add bio_badge (always useful)
    bio_badge = _build_document("bio_badge", {
        "HANDLE": handle,
        "HEIGHT": height,
        "WEIGHT": weight,
        "FACTION": faction,
    })
    entrant.documents.append(bio_badge)

    # Check if faction requires access_token
    if faction in directive.required_docs_by_faction:
        for doc_type in directive.required_docs_by_faction[faction]:
            if doc_type == "access_token":
                purpose = random.choice(theme.PURPOSE_TYPES)
                duration = f"{random.randint(1, 12)}mo"
                access_token = _build_document("access_token", {
                    "ID#": id_num,
                    "HANDLE": handle,
                    "FACTION": faction,
                    "PURPOSE": purpose,
                    "DURATION": duration,
                    "HEIGHT": height,
                    "WEIGHT": weight,
                    "EXP": _random_expiry(valid=True),
                })
                entrant.documents.append(access_token)

    # Check if faction requires scans
    if faction in directive.required_scans_by_faction:
        scans = list(directive.required_scans_by_faction[faction])
        scans_str = ", ".join(scans)
        integrity_report = _build_document("integrity_report", {
            "ID#": id_num,
            "HANDLE": handle,
            "SCANS": scans_str,
        })
        entrant.documents.append(integrity_report)

    # Check if this is an operator (PURPOSE=OPERATION in access_token)
    is_operator = any(
        doc.doc_type == "access_token" and doc.fields.get("PURPOSE") == "OPERATION"
        for doc in entrant.documents
    )

    # Add operator-required documents
    if is_operator:
        for doc_type in directive.required_docs_for_operators:
            if doc_type == "clearance_code":
                clearance_code = _build_document("clearance_code", {
                    "ID#": id_num,
                    "HANDLE": handle,
                    "FACTION": faction,
                    "EXP": _random_expiry(valid=True),
                })
                entrant.documents.append(clearance_code)

    # Add operator-required scans
    if is_operator and directive.required_scans_for_operators:
        # Update integrity_report with operator scans
        integrity_reports = entrant.get_documents_by_type("integrity_report")
        if integrity_reports:
            scans_str = integrity_reports[0].fields.get("SCANS", "")
            existing_scans = set(s.strip() for s in scans_str.split(",")) if scans_str else set()
            existing_scans.update(directive.required_scans_for_operators)
            integrity_reports[0].fields["SCANS"] = ", ".join(sorted(existing_scans))
        else:
            scans_str = ", ".join(sorted(directive.required_scans_for_operators))
            integrity_report = _build_document("integrity_report", {
                "ID#": id_num,
                "HANDLE": handle,
                "SCANS": scans_str,
            })
            entrant.documents.append(integrity_report)

    return entrant


def _introduce_flaw(
    entrant: Entrant,
    directive: SecurityDirective,
    difficulty: int,
    flaw_type: str = "denial"
) -> None:
    """
    Mutate an entrant to introduce a specific flaw.

    Args:
        entrant: The entrant to modify in-place
        directive: The current directive (for requirements context)
        difficulty: Difficulty level (affects flaw complexity)
        flaw_type: "denial" or "detainment"
    """
    if flaw_type == "denial":
        # Denial flaws: missing doc, expired doc, banned faction, wrong faction
        flaw_options = ["missing_doc", "expired_doc", "banned_faction"]
        if difficulty >= 2:
            flaw_options.append("faction_mismatch")

        chosen_flaw = random.choice(flaw_options)

        if chosen_flaw == "missing_doc":
            # Remove a required document
            required_docs = directive.get_required_docs(entrant.true_faction, _is_operator(entrant))
            if required_docs:
                doc_type_to_remove = random.choice(list(required_docs))
                entrant.documents = [d for d in entrant.documents if d.doc_type != doc_type_to_remove]

        elif chosen_flaw == "expired_doc":
            # Expire a random document with EXP field
            expirable_docs = [d for d in entrant.documents if "EXP" in d.fields]
            if expirable_docs:
                doc = random.choice(expirable_docs)
                doc.fields["EXP"] = _random_expiry(valid=False)

        elif chosen_flaw == "banned_faction":
            # Change faction to a banned one
            if directive.denied_factions:
                new_faction = random.choice(list(directive.denied_factions))
                entrant.true_faction = new_faction
                # Update all documents to this faction
                for doc in entrant.documents:
                    if "FACTION" in doc.fields:
                        doc.fields["FACTION"] = new_faction

        elif chosen_flaw == "faction_mismatch":
            # Mismatch faction between two documents
            if len(entrant.documents) >= 2:
                doc1, doc2 = random.sample(entrant.documents, 2)
                if "FACTION" in doc1.fields and "FACTION" in doc2.fields:
                    # Change doc2's faction to something different
                    available = [f for f in theme.FACTIONS if f != doc1.fields["FACTION"]]
                    if available:
                        doc2.fields["FACTION"] = random.choice(available)

    elif flaw_type == "detainment":
        # Detainment flaws: handle mismatch, ID mismatch, DOB mismatch, wanted handle
        flaw_options = ["handle_mismatch", "id_mismatch", "dob_mismatch"]
        if directive.wanted_handle:
            flaw_options.append("wanted_handle")

        chosen_flaw = random.choice(flaw_options)

        if chosen_flaw == "handle_mismatch":
            # Mismatch handle between documents
            docs_with_handle = [d for d in entrant.documents if "HANDLE" in d.fields]
            if len(docs_with_handle) >= 2:
                doc_to_change = random.choice(docs_with_handle)
                doc_to_change.fields["HANDLE"] = theme.random_handle()

        elif chosen_flaw == "id_mismatch":
            # Mismatch ID# between documents
            docs_with_id = [d for d in entrant.documents if "ID#" in d.fields]
            if len(docs_with_id) >= 2:
                doc_to_change = random.choice(docs_with_id)
                doc_to_change.fields["ID#"] = _random_id()

        elif chosen_flaw == "dob_mismatch":
            # Mismatch DOB between documents
            docs_with_dob = [d for d in entrant.documents if "DOB" in d.fields]
            if len(docs_with_dob) >= 2:
                doc_to_change = random.choice(docs_with_dob)
                doc_to_change.fields["DOB"] = _random_dob()

        elif chosen_flaw == "wanted_handle":
            # Change handle to wanted handle
            for doc in entrant.documents:
                if "HANDLE" in doc.fields:
                    doc.fields["HANDLE"] = directive.wanted_handle


def _is_operator(entrant: Entrant) -> bool:
    """Check if entrant has PURPOSE=OPERATION in access_token."""
    access_tokens = entrant.get_documents_by_type("access_token")
    for token in access_tokens:
        if token.fields.get("PURPOSE") == "OPERATION":
            return True
    return False
