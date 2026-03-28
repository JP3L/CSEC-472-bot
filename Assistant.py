"""
DAEMON — Digital Authentication Expert & Mentoring Operations Network.
An AI tutor embedded in the Papers Please game that teaches CSEC-472 concepts
by mapping real-world authentication and security principles to in-game mechanics.
"""

import random
from typing import Optional, Dict, List
from .models import Entrant, SecurityDirective, InspectionResult


# ============================================================================
# CONCEPT MAPPINGS: Game Mechanic → CSEC-472 Syllabus Topic
# ============================================================================

CONCEPT_MAP: Dict[str, Dict] = {
    "digital_id": {
        "syllabus_topic": "TLS / PKI Certificates",
        "real_world": "X.509 Digital Certificates",
        "explanation": (
            "Digital Identity Certificates in 2032 function like X.509 certificates "
            "in TLS/PKI. Each certificate has an issuing node (Certificate Authority), "
            "an expiration date, and binds an identity (handle) to a faction (organization). "
            "Just as a browser validates a server's certificate chain, you must verify "
            "the certificate hasn't expired and was issued by a recognized node."
        ),
        "tip": "Check the EXP date and ISSUING_NODE. An expired cert is like an expired TLS certificate — always deny.",
    },
    "access_token": {
        "syllabus_topic": "OAuth 2.0 / Kerberos Tickets",
        "real_world": "OAuth Access Tokens & Kerberos TGTs",
        "explanation": (
            "Network Access Tokens mirror OAuth 2.0 access tokens and Kerberos ticket-granting "
            "tickets. They encode PURPOSE (scope), DURATION (token lifetime), and the bearer's "
            "identity. In Kerberos, a TGT proves you authenticated to the KDC; here, the token "
            "proves the bearer authenticated to their faction's authority."
        ),
        "tip": "Verify the token's PURPOSE matches what's allowed. An OPERATION token is like an OAuth scope granting write access — more scrutiny required.",
    },
    "bio_badge": {
        "syllabus_topic": "Multi-Factor Authentication (MFA)",
        "real_world": "Biometric Authentication Factor",
        "explanation": (
            "The Biometric Authentication Badge represents 'something you are' — the biometric "
            "factor in MFA. Combined with the Digital ID ('something you have') and handle "
            "('something you know'), these three factors form a complete MFA chain. "
            "Mismatched biometrics (HEIGHT, WEIGHT) across documents indicate a stolen identity."
        ),
        "tip": "Cross-reference HEIGHT and WEIGHT across all documents. Mismatches signal identity fraud — like a biometric factor failing verification.",
    },
    "faction_access": {
        "syllabus_topic": "Role-Based Access Control (RBAC)",
        "real_world": "RBAC Policies & Group Membership",
        "explanation": (
            "Security Directives define which factions (roles/groups) may access the network. "
            "This mirrors RBAC: users are assigned roles (factions), and access policies "
            "determine which roles are permitted. A denied faction is like a group removed "
            "from an ACL. UACC members always pass — they have implicit admin privileges."
        ),
        "tip": "Check the directive's allowed and denied factions. Think of it as checking group membership against an access control list.",
    },
    "document_consistency": {
        "syllabus_topic": "Identity Verification & Integrity",
        "real_world": "Biba Integrity Model / Clark-Wilson",
        "explanation": (
            "Cross-document consistency checks mirror the Biba Integrity Model's concern "
            "with data integrity. If an ID# on one document doesn't match another, the "
            "integrity of the identity claim is compromised. Clark-Wilson's well-formed "
            "transactions require all data to be internally consistent before processing."
        ),
        "tip": "Compare ID#, HANDLE, FACTION, DOB, HEIGHT, and WEIGHT across ALL documents. Any mismatch = DETAIN (integrity violation).",
    },
    "clearance_code": {
        "syllabus_topic": "Bell-LaPadula / Security Clearances",
        "real_world": "Mandatory Access Control (MAC)",
        "explanation": (
            "Contractor Clearance Codes implement a form of Mandatory Access Control (MAC) "
            "similar to Bell-LaPadula. Contractors need explicit clearance beyond their "
            "faction membership — 'no read up, no write down' becomes 'no access without "
            "proper clearance level.' The system enforces security labels independent of "
            "the subject's wishes."
        ),
        "tip": "Contractors without clearance codes are like users without proper security labels — deny regardless of other valid documents.",
    },
    "integrity_report": {
        "syllabus_topic": "System Security Scanning",
        "real_world": "Vulnerability Assessment & Compliance",
        "explanation": (
            "System Integrity Reports list completed security scans (rootkit, trojan, "
            "ransomware, spyware, zero-day). This maps to real-world compliance requirements "
            "where systems must pass vulnerability assessments before network access. "
            "Think of NIST frameworks requiring specific security controls."
        ),
        "tip": "Match required SCANS in the directive against the integrity report's scan list. Missing scans = deny, like failing a compliance audit.",
    },
    "expiration": {
        "syllabus_topic": "Certificate Lifecycle / Key Management",
        "real_world": "Certificate Revocation & Expiry",
        "explanation": (
            "Document expiration mirrors certificate lifecycle management. In TLS, expired "
            "certificates must be rejected — browsers show warnings for expired certs. "
            "Similarly, expired digital credentials indicate the bearer's authorization "
            "has lapsed. Key management requires regular rotation and revocation."
        ),
        "tip": "The current date is 2032.11.22. Any document with EXP before this date is expired — always deny, just like rejecting an expired TLS cert.",
    },
    "wanted_handle": {
        "syllabus_topic": "Certificate Revocation Lists (CRL)",
        "real_world": "CRL / OCSP Revocation Checking",
        "explanation": (
            "A wanted handle in the Security Directive is analogous to a Certificate "
            "Revocation List (CRL) or OCSP response. Even if all documents are valid, "
            "a revoked identity must be detained — just as a valid-looking certificate "
            "on a CRL must be rejected. Always check the 'revocation list' first."
        ),
        "tip": "Check the wanted handle BEFORE anything else. If the entrant's handle matches — DETAIN immediately, like finding a cert on a CRL.",
    },
    "diplomatic_cipher": {
        "syllabus_topic": "Cryptographic Key Exchange",
        "real_world": "Diffie-Hellman / Key Agreement Protocols",
        "explanation": (
            "Diplomatic Cipher Channels represent secure key exchange between factions. "
            "In the real world, this maps to key agreement protocols like Diffie-Hellman, "
            "where two parties establish a shared secret. The ACCESS field determines "
            "what level of encrypted communication is authorized."
        ),
        "tip": "Diplomatic cipher holders have pre-negotiated secure channels. Verify their ACCESS level matches directive requirements.",
    },
    "asylum_key": {
        "syllabus_topic": "Asymmetric Cryptography / Digital Signatures",
        "real_world": "Public Key Cryptography for Identity",
        "explanation": (
            "Asylum Encryption Keys use asymmetric cryptography concepts. The key holder "
            "proves their identity through a unique cryptographic token — similar to how "
            "digital signatures prove authorship using private keys. The asylum process "
            "requires verifying the key's validity and the holder's biometric data."
        ),
        "tip": "Asylum keys require extra verification — check ALL fields including biometrics. Think of it as verifying both a digital signature AND the signer's identity.",
    },
}

# ============================================================================
# CONTEXTUAL HINTS: Generated based on game state
# ============================================================================

GENERAL_TIPS = [
    "Remember MFA: Digital ID = something you have, Handle = something you know, Bio Badge = something you are.",
    "Think RBAC: the Security Directive defines which faction-roles can access the network.",
    "Integrity first: cross-reference ALL fields across documents before making a decision. Biba would be proud.",
    "Expired documents are like expired TLS certificates — NEVER accept them, no matter how valid everything else looks.",
    "The wanted handle check is your CRL lookup — always do it first, before any other validation.",
    "OPERATION purpose on an access token = elevated privileges. Apply principle of least privilege — extra docs required.",
    "When in doubt, think about the CIA triad: is the Confidentiality, Integrity, or Availability of the network at risk?",
    "Bell-LaPadula says 'no read up': if someone lacks clearance, they can't access higher-level resources.",
    "OAuth scopes limit what a token can do. Similarly, an access token's PURPOSE limits the bearer's allowed actions.",
    "Kerberos tickets expire for a reason — token replay attacks are real. Always check expiration dates.",
]

# ============================================================================
# MISTAKE EXPLANATIONS: Map common errors to learning opportunities
# ============================================================================

MISTAKE_EXPLANATIONS = {
    "missed_wanted": (
        "You missed a wanted handle! In real-world terms, you failed to check the "
        "Certificate Revocation List (CRL). Always check if an identity has been revoked "
        "BEFORE validating other credentials. OCSP stapling and CRL checks are the first "
        "line of defense."
    ),
    "missed_mismatch": (
        "You missed a document mismatch! This is an integrity violation — like the Biba "
        "model warns, compromised data integrity means the identity claim is untrustworthy. "
        "Always cross-reference ID#, HANDLE, FACTION, DOB, HEIGHT, and WEIGHT across ALL documents."
    ),
    "missed_expiry": (
        "You accepted an expired document! Think of this like accepting an expired TLS "
        "certificate — a browser would warn you, and you should too. Certificate lifecycle "
        "management requires rejecting expired credentials regardless of other validity."
    ),
    "missed_faction_deny": (
        "You allowed a denied faction through! The Security Directive is your access "
        "control policy (like an ACL). If a faction is denied, no individual from that "
        "group can pass — that's how RBAC works. Group policy overrides individual credentials."
    ),
    "missed_missing_doc": (
        "You allowed entry without a required document! In MFA terms, you accepted "
        "single-factor authentication when multi-factor was required. Each required document "
        "adds a verification factor. Missing any one breaks the authentication chain."
    ),
    "missed_scan": (
        "You allowed entry without required security scans! This is like granting network "
        "access to a system that hasn't passed its compliance audit. NIST and ISO 27001 "
        "require verified security controls before access is granted."
    ),
    "false_detain": (
        "You detained someone whose documents were consistent! Be careful not to see "
        "discrepancies where none exist. False positives in security systems (like IDS) "
        "waste resources and erode trust. Verify carefully before escalating."
    ),
    "false_deny": (
        "You denied someone who should have been allowed! This is a false rejection — "
        "like a firewall rule that's too restrictive, blocking legitimate traffic. "
        "Balance security with availability — the 'A' in CIA."
    ),
}


# ============================================================================
# DAEMON CLASS
# ============================================================================

class DAEMON:
    """
    Digital Authentication Expert & Mentoring Operations Network.

    An in-game AI tutor that helps students learn CSEC-472 concepts by
    providing contextual hints, explaining mistakes, and mapping game
    mechanics to real-world authentication and security principles.
    """

    NAME = "DAEMON"
    FULL_NAME = "Digital Authentication Expert & Mentoring Operations Network"
    AVATAR_EMOJI = "🔮"

    GREETING = (
        "```ansi\n"
        "\033[0;35m╔══════════════════════════════════════════════════════════════╗\n"
        "║  DAEMON v3.2.1 — Digital Authentication Expert               ║\n"
        "║  & Mentoring Operations Network                              ║\n"
        "║  UACC Cyber Division • Training Module Active                ║\n"
        "╚══════════════════════════════════════════════════════════════╝\033[0m\n"
        "```\n"
        "Online and monitoring. I'm your embedded security advisor.\n"
        "Ask me about any authentication concept, document type, or security principle.\n"
        "I'll map it to your CSEC-472 coursework so you can make better checkpoint decisions."
    )

    @staticmethod
    def get_concept_help(topic: str) -> Optional[str]:
        """
        Look up a game concept and return its CSEC-472 mapping.

        Args:
            topic: A keyword to search for (e.g., "token", "mfa", "kerberos", "expired")

        Returns:
            Formatted help text, or None if no match found.
        """
        topic_lower = topic.lower().strip()

        # Direct concept map lookup
        for key, info in CONCEPT_MAP.items():
            searchable = (
                key + " " +
                info["syllabus_topic"] + " " +
                info["real_world"] + " " +
                info["explanation"]
            ).lower()
            if topic_lower in searchable:
                return (
                    f"**{DAEMON.AVATAR_EMOJI} DAEMON — {info['syllabus_topic']}**\n\n"
                    f"**Real-World Parallel:** {info['real_world']}\n\n"
                    f"{info['explanation']}\n\n"
                    f"**Agent Tip:** {info['tip']}"
                )

        return None

    @staticmethod
    def get_inspection_hint(entrant: Entrant, directive: SecurityDirective) -> str:
        """
        Provide a contextual hint based on the current entrant and directive.
        Does NOT reveal the answer — just points the student toward what to check.

        Args:
            entrant: The current entrant to inspect.
            directive: The active security directive.

        Returns:
            A hint string that guides without giving away the answer.
        """
        hints = []

        # Hint about wanted handle if directive has one
        if directive.wanted_handle:
            hints.append(
                "🔍 **CRL Check:** The directive has a wanted handle listed. "
                "Remember — checking the revocation list is always step one. "
                "Compare it against the entrant's handle across all documents."
            )

        # Hint about faction restrictions
        if directive.denied_factions:
            hints.append(
                "🛡️ **RBAC Policy:** Some factions are denied by the current directive. "
                "Check the entrant's faction against the access control list before "
                "validating individual documents."
            )

        # Hint about document count
        doc_types = {d.doc_type for d in entrant.documents}
        if len(entrant.documents) > 2:
            hints.append(
                "📋 **Integrity Check:** This entrant has multiple documents. "
                "Cross-reference shared fields (ID#, HANDLE, FACTION, DOB, HEIGHT, WEIGHT) "
                "for consistency — the Biba model demands data integrity."
            )

        # Hint about operator status
        for doc in entrant.documents:
            if doc.doc_type == "access_token" and doc.fields.get("PURPOSE") == "OPERATION":
                hints.append(
                    "⚡ **Elevated Privileges:** This entrant has an OPERATION token. "
                    "Like elevated OAuth scopes, operators require additional documentation. "
                    "Check for operator-specific requirements in the directive."
                )
                break

        # Hint about expiration
        has_exp = any("EXP" in d.fields for d in entrant.documents)
        if has_exp:
            hints.append(
                "⏰ **Certificate Lifecycle:** Some documents have expiration dates. "
                "Remember: the current date is 2032.11.22. Expired certs = denied, always."
            )

        if not hints:
            hints.append(random.choice(GENERAL_TIPS))

        # Return 1-2 hints max to avoid overwhelming
        selected = random.sample(hints, min(2, len(hints)))
        return "\n\n".join(selected)

    @staticmethod
    def explain_mistake(result: InspectionResult, player_decision: str) -> str:
        """
        After a wrong answer, explain what the student missed using CSEC-472 concepts.

        Args:
            result: The correct inspection result.
            player_decision: What the player chose ("allow", "deny", "detain").

        Returns:
            Educational explanation of the mistake.
        """
        reason_lower = result.reason.lower()

        # Map the correct answer's reason to an explanation category
        if "wanted" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_wanted"]
        elif "mismatch" in reason_lower or "inconsistency" in reason_lower or "discrepancy" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_mismatch"]
        elif "expired" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_expiry"]
        elif "denied" in reason_lower or "denied by directive" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_faction_deny"]
        elif "missing" in reason_lower and "scan" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_scan"]
        elif "missing" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_missing_doc"]
        elif result.decision == "allow" and player_decision == "detain":
            explanation = MISTAKE_EXPLANATIONS["false_detain"]
        elif result.decision == "allow" and player_decision == "deny":
            explanation = MISTAKE_EXPLANATIONS["false_deny"]
        else:
            explanation = (
                f"The correct decision was **{result.decision.upper()}**: {result.reason}. "
                "Review the Security Directive carefully and cross-check all document fields."
            )

        return (
            f"**{DAEMON.AVATAR_EMOJI} DAEMON — Post-Action Analysis**\n\n"
            f"**Correct Decision:** {result.decision.upper()}\n"
            f"**Reason:** {result.reason}\n\n"
            f"{explanation}"
        )

    @staticmethod
    def get_random_tip() -> str:
        """Return a random general tip."""
        tip = random.choice(GENERAL_TIPS)
        return f"**{DAEMON.AVATAR_EMOJI} DAEMON Tip:** {tip}"

    @staticmethod
    def get_topic_list() -> str:
        """Return a formatted list of all topics DAEMON can help with."""
        lines = [
            f"**{DAEMON.AVATAR_EMOJI} DAEMON — Available Topics**\n",
            "Ask me about any of these to learn how they connect to your CSEC-472 coursework:\n",
        ]
        for key, info in CONCEPT_MAP.items():
            lines.append(f"• **{info['syllabus_topic']}** — `{key}`")

        lines.append(
            "\nUsage: Type a keyword like `kerberos`, `mfa`, `expired`, `rbac`, "
            "`tls`, `integrity`, or any security concept."
        )
        return "\n".join(lines)
