"""
CERBERUS — Cybernetic Enforcement & Review Bureau for Encrypted Resource & User Security.

A three-headed guardian AI tutor embedded in the Papers Please game. Each head
represents one of the three authentication factors:
  🔑 HEAD I   — Something You KNOW (passwords, PINs, handles, secrets)
  🪪 HEAD II  — Something You HAVE (tokens, certificates, keys, badges)
  🧬 HEAD III — Something You ARE  (biometrics, behavioral patterns)

CERBERUS teaches CSEC-472 concepts by mapping real-world authentication and
security principles to in-game mechanics, providing verbose, detailed guidance
that reinforces core course material.
"""

import random
from typing import Optional, Dict, List
from . import theme
from .models import Entrant, SecurityDirective, InspectionResult


# ============================================================================
# CONCEPT MAPPINGS: Game Mechanic → CSEC-472 Syllabus Topic
# Each entry includes a deep_dive for extended teaching when students ask
# ============================================================================

CONCEPT_MAP: Dict[str, Dict] = {
    "digital_id": {
        "syllabus_topic": "TLS / PKI Certificates",
        "real_world": "X.509 Digital Certificates",
        "explanation": (
            "Digital Identity Certificates in 2032 function exactly like X.509 certificates "
            "in the TLS Public Key Infrastructure. Every X.509 certificate contains: a subject "
            "(the entity it identifies), an issuer (the Certificate Authority that vouches for it), "
            "a validity period (not-before and not-after dates), a public key, and a digital signature "
            "from the issuing CA.\n\n"
            "At your checkpoint, the Digital ID maps these fields directly:\n"
            "• **HANDLE** → Subject Common Name (CN) — who this certificate identifies\n"
            "• **ISSUING_NODE** → Issuer / Certificate Authority — who vouches for the identity\n"
            "• **EXP** → Validity period (not-after date) — when the guarantee expires\n"
            "• **FACTION** → Organization (O) field — the entity the subject belongs to\n"
            "• **ID#** → Serial number — unique identifier for this specific certificate\n\n"
            "In TLS, your browser performs a certificate chain validation: it checks that each "
            "certificate in the chain is signed by a trusted CA, hasn't expired, and hasn't been "
            "revoked. You must perform the same validation at the checkpoint."
        ),
        "tip": (
            "Check EXP against current date 2032.11.22. Verify the ISSUING_NODE is recognized. "
            "Cross-reference the ID# and HANDLE against other documents for consistency — just "
            "as a TLS implementation checks the certificate's subject against the requested hostname."
        ),
        "deep_dive": (
            "**Deep Dive: The TLS Handshake & Certificate Validation**\n\n"
            "When your browser connects to https://example.com, the TLS handshake begins:\n\n"
            "1. **ClientHello** — Your browser sends supported cipher suites and a random nonce\n"
            "2. **ServerHello** — The server selects a cipher suite and sends its certificate\n"
            "3. **Certificate Validation** — Your browser checks:\n"
            "   - Is the certificate signed by a trusted CA in your trust store?\n"
            "   - Is the current date within the validity period?\n"
            "   - Does the Subject Alternative Name (SAN) match the hostname?\n"
            "   - Is the certificate on a CRL or reported as revoked via OCSP?\n"
            "4. **Key Exchange** — Using the certificate's public key, both parties derive session keys\n"
            "5. **Encrypted Communication** — All subsequent data is encrypted with the session key\n\n"
            "At your checkpoint, steps 1-3 map directly to your document inspection process. "
            "The certificate IS the Digital Identity Certificate. The trust store IS your list of "
            "recognized issuing nodes. The validity check IS your expiration date comparison. "
            "The hostname check IS verifying the handle matches across documents.\n\n"
            "**Why expiration matters:** Certificates expire because the CA's guarantee is time-bounded. "
            "A CA says 'I verified this identity on date X, and I vouch for it until date Y.' After Y, "
            "the identity might have changed — the person could have left the organization, their key "
            "could have been compromised, or the CA's policies might have changed. That's why expired "
            "certificates are ALWAYS rejected, no matter how valid everything else appears."
        ),
    },
    "access_token": {
        "syllabus_topic": "OAuth 2.0 / Kerberos Tickets",
        "real_world": "OAuth Access Tokens & Kerberos TGTs",
        "explanation": (
            "Network Access Tokens mirror both OAuth 2.0 access tokens and Kerberos ticket-granting "
            "tickets (TGTs). In the Kerberos protocol, after you authenticate to the Key Distribution "
            "Center (KDC), you receive a TGT — a cryptographic proof that says 'this user proved their "
            "identity to me at time T, valid until time T+lifetime.' You then present this TGT to "
            "request service tickets for specific resources, never needing to re-enter your password.\n\n"
            "In OAuth 2.0, an access token encodes scopes (what the bearer is allowed to do), "
            "an expiration time, and the identity of the authorized party. The token's PURPOSE field "
            "in our game maps directly to OAuth scopes:\n"
            "• **TRANSIT** → Read-only scope — minimal access for passing through\n"
            "• **OPERATION** → Write/admin scope — elevated privileges requiring additional verification\n\n"
            "The DURATION field mirrors token lifetime in both protocols. Short-lived tokens reduce "
            "the window for token theft and replay attacks."
        ),
        "tip": (
            "Verify PURPOSE matches the directive's expectations. OPERATION tokens are like OAuth "
            "tokens with admin scopes — they require additional documentation (clearance codes, "
            "integrity reports) just as elevated API access requires additional authorization grants. "
            "Always check EXP — an expired token is useless regardless of its scope."
        ),
        "deep_dive": (
            "**Deep Dive: Kerberos Authentication Flow**\n\n"
            "The Kerberos protocol uses a trusted third party (the KDC) with two components:\n"
            "• **Authentication Server (AS)** — Verifies initial identity\n"
            "• **Ticket-Granting Server (TGS)** — Issues service tickets\n\n"
            "**Step-by-step flow:**\n"
            "1. User sends username to AS (no password sent over network!)\n"
            "2. AS looks up user's password hash, encrypts a TGT with the TGS's secret key, "
            "and encrypts a session key with the user's password hash\n"
            "3. User decrypts the session key with their password (proves they know it)\n"
            "4. User presents TGT + authenticator to TGS to request a service ticket\n"
            "5. TGS issues a service ticket encrypted with the target service's key\n"
            "6. User presents the service ticket to the service\n\n"
            "**Key security properties:**\n"
            "- The user's password NEVER travels over the network\n"
            "- Tickets have limited lifetime (prevents indefinite replay)\n"
            "- Authenticators include timestamps (prevents short-term replay)\n"
            "- Mutual authentication: the service proves its identity back to the client\n\n"
            "At your checkpoint, the Access Token IS the Kerberos ticket. The faction's authority "
            "IS the KDC. The expiration IS the ticket lifetime. And when you verify the token, "
            "you're acting as the service that validates the ticket before granting access.\n\n"
            "**OAuth 2.0 parallel:** The Authorization Code Grant flow similarly separates "
            "authentication from resource access. The authorization server issues tokens with "
            "specific scopes — a token with 'read:profile' scope cannot modify data, just as "
            "a TRANSIT token cannot authorize operations."
        ),
    },
    "bio_badge": {
        "syllabus_topic": "Multi-Factor Authentication (MFA)",
        "real_world": "Biometric Authentication Factor",
        "explanation": (
            "The Biometric Authentication Badge represents the third pillar of multi-factor "
            "authentication: 'something you ARE.' The three authentication factors are:\n\n"
            "🔑 **Something You KNOW** — Passwords, PINs, security questions, and in-game: the HANDLE\n"
            "🪪 **Something You HAVE** — Smart cards, hardware tokens, phones, and in-game: the Digital ID\n"
            "🧬 **Something You ARE** — Fingerprints, iris scans, voice patterns, and in-game: the Bio Badge\n\n"
            "True MFA requires factors from at least TWO DIFFERENT categories. Three passwords are NOT "
            "MFA because they're all 'something you know.' A password + phone code + fingerprint IS "
            "MFA because it combines all three categories.\n\n"
            "The Bio Badge's HEIGHT and WEIGHT fields are biometric measurements that must match across "
            "all documents. A mismatch indicates the documents belong to different people — equivalent "
            "to a fingerprint scan failing during biometric verification. This is an identity fraud "
            "indicator and warrants DETAINMENT, not mere denial."
        ),
        "tip": (
            "Cross-reference HEIGHT and WEIGHT across ALL documents the entrant presents. "
            "A 180cm person on the Digital ID but 165cm on the Bio Badge = stolen identity = DETAIN. "
            "Think of it exactly like a biometric mismatch: if the fingerprint doesn't match the "
            "one on file, the identity claim is fraudulent, not just incomplete."
        ),
        "deep_dive": (
            "**Deep Dive: Authentication Factor Categories & Attack Vectors**\n\n"
            "Each factor category has different strengths and vulnerabilities:\n\n"
            "**Something You Know (Knowledge Factors):**\n"
            "- Passwords, PINs, security questions\n"
            "- Vulnerable to: phishing, social engineering, brute force, keyloggers, shoulder surfing\n"
            "- Mitigation: password managers, complexity requirements, account lockout policies\n\n"
            "**Something You Have (Possession Factors):**\n"
            "- Hardware tokens (YubiKey), smart cards, mobile phones (TOTP apps)\n"
            "- Vulnerable to: physical theft, SIM swapping, man-in-the-middle relay\n"
            "- Mitigation: FIDO2/WebAuthn (origin-bound, phishing-resistant)\n\n"
            "**Something You Are (Inherence Factors):**\n"
            "- Fingerprints, iris patterns, facial recognition, voice, gait\n"
            "- Vulnerable to: spoofing (fake fingerprints), cannot be changed if compromised\n"
            "- Mitigation: liveness detection, multi-modal biometrics\n\n"
            "**Why MFA works:** An attacker would need to compromise factors from multiple "
            "categories simultaneously. Stealing a password (know) doesn't help without the "
            "hardware token (have). Cloning a fingerprint (are) doesn't help without the password (know).\n\n"
            "**At the checkpoint:** Each document type represents a different factor:\n"
            "- Digital ID = possession factor (you must physically present it)\n"
            "- Handle consistency = knowledge factor (you must know your identity details)\n"
            "- Bio Badge = inherence factor (your physical measurements must match)\n"
            "When all three agree, you have high-assurance multi-factor verification."
        ),
    },
    "faction_access": {
        "syllabus_topic": "Role-Based Access Control (RBAC)",
        "real_world": "RBAC Policies & Group Membership",
        "explanation": (
            "Security Directives implement Role-Based Access Control at the checkpoint level. "
            "In RBAC, access decisions are based on the roles assigned to a user rather than "
            "individual identity. The core RBAC model has four components:\n\n"
            "1. **Users** → Entrants approaching your checkpoint\n"
            "2. **Roles** → Factions (UACC, PRC, ERN, CIH, CORP, NALL, FSU)\n"
            "3. **Permissions** → Allow, Deny, or conditional access with additional docs\n"
            "4. **Sessions** → The current Security Directive's active policy\n\n"
            "RBAC simplifies administration: instead of managing permissions per-user, you manage "
            "them per-role. When the directive says 'Deny all ERN operatives,' you don't evaluate "
            "each ERN member individually — the role-level policy applies universally.\n\n"
            "UACC (home faction) has implicit administrative privileges — they always pass basic "
            "faction checks, similar to how a domain admin inherits all permissions in Active Directory."
        ),
        "tip": (
            "Always check faction FIRST against the directive's allow/deny lists. This is your "
            "coarsest-grained access control filter. A denied faction means DENY regardless of "
            "how perfect their documents look — RBAC policy overrides individual credentials. "
            "Then apply finer-grained checks (document requirements, scans) for allowed factions."
        ),
        "deep_dive": (
            "**Deep Dive: RBAC vs. MAC vs. DAC vs. ABAC**\n\n"
            "**Discretionary Access Control (DAC):**\n"
            "- Resource owners set permissions (like Unix file permissions)\n"
            "- Flexible but relies on users making good security decisions\n"
            "- Vulnerable to Trojan horse attacks (a malicious program inherits user's permissions)\n\n"
            "**Mandatory Access Control (MAC):**\n"
            "- System-enforced policies that users cannot override\n"
            "- Uses security labels and clearance levels\n"
            "- Examples: SELinux, military classified systems\n"
            "- The Security Directive IS a MAC policy — you cannot override it for any entrant\n\n"
            "**Role-Based Access Control (RBAC):**\n"
            "- Permissions assigned to roles, users assigned to roles\n"
            "- Supports separation of duties, least privilege, and role hierarchies\n"
            "- Most common in enterprise environments (Active Directory groups)\n"
            "- Faction membership IS role assignment at the checkpoint\n\n"
            "**Attribute-Based Access Control (ABAC):**\n"
            "- Decisions based on attributes of user, resource, and environment\n"
            "- Most flexible: 'allow if user.faction=UACC AND time.hour<18 AND doc.exp>now'\n"
            "- Higher difficulty directives add ABAC-like conditions (specific scans, operator status)\n\n"
            "Your checkpoint evolves from simple RBAC at low difficulty to complex ABAC at high "
            "difficulty, as more attributes (operator status, scan requirements, clearance codes) "
            "factor into access decisions."
        ),
    },
    "document_consistency": {
        "syllabus_topic": "Identity Verification & Data Integrity",
        "real_world": "Biba Integrity Model / Clark-Wilson Model",
        "explanation": (
            "When you cross-reference fields across multiple documents, you're performing an "
            "integrity verification that maps directly to two foundational security models:\n\n"
            "**Biba Integrity Model** — Focuses on preventing unauthorized modification of data. "
            "Its core rules:\n"
            "• *No Write Up (Star Integrity):* A subject cannot modify data at a higher integrity level\n"
            "• *No Read Down:* A subject cannot read data at a lower integrity level\n"
            "If data across documents is inconsistent, it means someone modified data they shouldn't "
            "have — an integrity violation that signals document fraud.\n\n"
            "**Clark-Wilson Model** — Ensures integrity through:\n"
            "• *Constrained Data Items (CDIs):* Data that must maintain integrity (the entrant's identity)\n"
            "• *Transformation Procedures (TPs):* Validated operations on CDIs (your inspection process)\n"
            "• *Integrity Verification Procedures (IVPs):* Checks that CDIs are valid (cross-referencing)\n\n"
            "When ID#, HANDLE, FACTION, DOB, HEIGHT, or WEIGHT don't match across documents, "
            "the CDI (identity claim) has failed the IVP (your cross-reference check). This is a "
            "DETAINMENT offense because it indicates deliberate fraud, not mere bureaucratic error."
        ),
        "tip": (
            "Systematically compare EVERY shared field across ALL documents: ID#, HANDLE, FACTION, "
            "DOB, HEIGHT, WEIGHT. Even one mismatch = DETAIN. This is your integrity verification "
            "procedure — like a Clark-Wilson IVP running against the constrained data items."
        ),
        "deep_dive": (
            "**Deep Dive: Why Integrity Matters More Than You Think**\n\n"
            "The CIA Triad places Integrity alongside Confidentiality and Availability as "
            "co-equal security objectives. Without integrity:\n"
            "- You can't trust that data hasn't been tampered with\n"
            "- Authentication becomes meaningless (forged credentials look legitimate)\n"
            "- Authorization decisions are based on corrupted data\n\n"
            "**Real-world integrity mechanisms:**\n"
            "- **Hash functions (SHA-256):** Detect any modification to data\n"
            "- **Digital signatures:** Prove who created/modified data and detect tampering\n"
            "- **HMAC:** Verify both integrity and authenticity of messages\n"
            "- **Database constraints:** Enforce internal consistency rules\n\n"
            "**At the checkpoint, your cross-reference IS the hash verification.** You're computing "
            "whether the 'hash' (consistent identity across documents) matches expectations. A "
            "mismatch means data corruption — which in the identity context means fraud."
        ),
    },
    "clearance_code": {
        "syllabus_topic": "Bell-LaPadula Model / Security Clearances",
        "real_world": "Mandatory Access Control (MAC)",
        "explanation": (
            "Contractor Clearance Codes implement the Bell-LaPadula (BLP) security model, which "
            "governs confidentiality through mandatory access controls. BLP has two fundamental rules:\n\n"
            "• **Simple Security Property (No Read Up):** A subject at clearance level L cannot "
            "read objects classified above L. A 'Secret' clearance cannot read 'Top Secret' documents.\n"
            "• **Star Property (No Write Down):** A subject at clearance level L cannot write to "
            "objects classified below L. This prevents information leakage from higher to lower levels.\n\n"
            "At the checkpoint, contractors operating at elevated levels (OPERATION purpose) need "
            "explicit clearance codes proving they're authorized for that classification level. "
            "Without the clearance code, they lack the security label needed for MAC enforcement — "
            "the system (you) MUST deny access regardless of other valid credentials. This is "
            "mandatory, not discretionary — you cannot override it based on judgment."
        ),
        "tip": (
            "If the directive requires clearance for operators and the entrant has an OPERATION "
            "token but no Clearance Code: DENY. No exceptions. This is MAC — the system enforces "
            "the policy absolutely. Even if every other document is perfect, the missing clearance "
            "code means the entrant lacks the security label for their requested access level."
        ),
        "deep_dive": (
            "**Deep Dive: Bell-LaPadula vs. Biba — Confidentiality vs. Integrity**\n\n"
            "These models are mathematical duals:\n\n"
            "**Bell-LaPadula (Confidentiality):**\n"
            "- No Read Up: prevents unauthorized access to classified information\n"
            "- No Write Down: prevents leaking classified info to lower levels\n"
            "- Models: military classification (Unclassified → Confidential → Secret → Top Secret)\n"
            "- Weakness: doesn't address integrity at all\n\n"
            "**Biba (Integrity):**\n"
            "- No Read Down: prevents corruption from untrusted sources\n"
            "- No Write Up: prevents contaminating high-integrity data\n"
            "- Models: data integrity in financial/medical systems\n"
            "- Weakness: doesn't address confidentiality at all\n\n"
            "**Chinese Wall (Brewer-Nash):**\n"
            "- Dynamic access control based on what you've previously accessed\n"
            "- Prevents conflicts of interest (once you see Company A's data, you can't see "
            "competitor Company B's data)\n\n"
            "At the checkpoint, Bell-LaPadula governs who can ACCESS the network (clearance levels), "
            "while Biba governs whether to TRUST the entrant's identity (data integrity). "
            "You enforce both simultaneously."
        ),
    },
    "integrity_report": {
        "syllabus_topic": "Vulnerability Assessment & Compliance",
        "real_world": "NIST Frameworks / Security Compliance Scanning",
        "explanation": (
            "System Integrity Reports list completed security scans that map directly to "
            "real-world compliance frameworks and vulnerability assessment programs:\n\n"
            "• **rootkit_scan** → Host-based integrity monitoring (like AIDE/Tripwire)\n"
            "• **trojan_check** → Malware detection and endpoint security\n"
            "• **ransomware_sweep** → Anti-ransomware and backup verification\n"
            "• **spyware_audit** → Data Loss Prevention (DLP) and exfiltration detection\n"
            "• **zero_day_patch** → Patch management and vulnerability remediation\n\n"
            "In enterprise environments, systems must pass compliance audits before gaining "
            "network access. NIST SP 800-53 defines security controls, and frameworks like "
            "802.1X Network Access Control (NAC) enforce posture assessment — a device must "
            "prove it meets security requirements before joining the network. Missing required "
            "scans = failed compliance = access denied."
        ),
        "tip": (
            "Compare the directive's required scans against the integrity report's SCANS field. "
            "Every required scan must be present. Even one missing scan = DENY — just like a "
            "system failing one control in a compliance audit gets remediation, not access."
        ),
        "deep_dive": (
            "**Deep Dive: Network Access Control & Compliance**\n\n"
            "**802.1X Port-Based Network Access Control:**\n"
            "1. Device connects to network port → switch doesn't grant access yet\n"
            "2. Device presents credentials to authentication server (RADIUS)\n"
            "3. Authentication server checks: identity valid? Device posture compliant?\n"
            "4. If both pass → network access granted with appropriate VLAN assignment\n"
            "5. If posture fails → quarantine VLAN with remediation resources\n\n"
            "Your checkpoint IS an 802.1X implementation. The entrant IS the device. "
            "The Security Directive IS the policy. The integrity report IS the posture "
            "assessment. And DENY with reason 'missing scan' IS quarantine assignment.\n\n"
            "**NIST Cybersecurity Framework (CSF) Functions:**\n"
            "- Identify → Know what you're protecting\n"
            "- Protect → Implement safeguards (your checkpoint!)\n"
            "- Detect → Monitor for anomalies (your cross-reference checks!)\n"
            "- Respond → Take action on threats (DENY/DETAIN decisions!)\n"
            "- Recover → Restore normal operations"
        ),
    },
    "expiration": {
        "syllabus_topic": "Certificate Lifecycle & Key Management",
        "real_world": "Certificate Expiry, Rotation & Revocation",
        "explanation": (
            "Document expiration maps to one of the most critical concepts in PKI: certificate "
            "lifecycle management. Every digital certificate has a defined validity period because:\n\n"
            "1. **Cryptographic aging** — As computing power increases, older keys become vulnerable "
            "to brute-force attacks. Expiration forces key rotation.\n"
            "2. **Identity changes** — People leave organizations, change roles, or have credentials "
            "compromised. Expiration bounds the risk window.\n"
            "3. **Policy evolution** — CA policies change. Expiration ensures old certificates are "
            "replaced with ones meeting current standards.\n"
            "4. **Revocation gaps** — CRLs and OCSP have latency. Short lifetimes reduce reliance "
            "on revocation checking.\n\n"
            "The current checkpoint date is **2032.11.22**. Any document with an EXP date before "
            "this is expired and MUST be denied — no exceptions, just as browsers hard-reject expired "
            "TLS certificates regardless of all other certificate properties."
        ),
        "tip": (
            "Check EXP fields on EVERY document that has one — Digital ID, Access Token, "
            "Clearance Code, Asylum Key, Diplomatic Cipher. Compare against 2032.11.22. "
            "An expired document means the issuing authority's guarantee has lapsed. "
            "DENY always, even if every other field is perfect."
        ),
        "deep_dive": (
            "**Deep Dive: Key Management Lifecycle**\n\n"
            "The complete key/certificate lifecycle:\n\n"
            "1. **Generation** — Key pair created with appropriate algorithm and key size\n"
            "2. **Registration** — Public key registered with CA, identity verified\n"
            "3. **Distribution** — Certificate issued and distributed to relying parties\n"
            "4. **Usage** — Certificate used for authentication, encryption, signing\n"
            "5. **Rotation** — Before expiry, new certificate issued to replace the old one\n"
            "6. **Revocation** — If compromised, certificate added to CRL and OCSP updated\n"
            "7. **Archival** — Expired certificates archived for historical verification\n"
            "8. **Destruction** — Private keys securely destroyed when no longer needed\n\n"
            "**Let's Encrypt revolutionized this** by issuing 90-day certificates with automated "
            "renewal. Short lifetimes = smaller risk windows + forced automation. The principle: "
            "if renewal is painful, make it automatic; if it's automatic, make it frequent.\n\n"
            "At your checkpoint, expired documents represent step 5 failure — the bearer didn't "
            "rotate their credentials in time. Their authorization has lapsed."
        ),
    },
    "wanted_handle": {
        "syllabus_topic": "Certificate Revocation Lists (CRL) & OCSP",
        "real_world": "CRL / OCSP Real-Time Revocation Checking",
        "explanation": (
            "A wanted handle in the Security Directive is functionally identical to a Certificate "
            "Revocation List (CRL) entry. In PKI, certificates can be revoked before expiration for:\n"
            "• Key compromise — private key stolen or leaked\n"
            "• CA compromise — the issuing CA itself was breached\n"
            "• Affiliation change — subject left the organization\n"
            "• Superseded — replaced by a new certificate\n"
            "• Cessation of operations — entity no longer exists\n\n"
            "**CRL checking** involves downloading a list of revoked certificate serial numbers "
            "from the CA and checking if the presented certificate is on that list.\n"
            "**OCSP (Online Certificate Status Protocol)** provides real-time, per-certificate "
            "revocation status — like querying a database instead of downloading a full list.\n"
            "**OCSP Stapling** improves performance by having the server periodically fetch its "
            "own OCSP response and 'staple' it to the TLS handshake.\n\n"
            "The wanted handle is your CRL. Check it FIRST, before ANY other validation. A revoked "
            "identity with perfect documents is the most dangerous — they look legitimate."
        ),
        "tip": (
            "ALWAYS check the wanted handle BEFORE anything else — this is your CRL/OCSP check. "
            "If the entrant's handle matches the wanted handle on ANY document: DETAIN immediately. "
            "Don't waste time validating other fields. A revoked certificate with valid signatures "
            "is STILL revoked. Priority order: CRL check → faction check → document validation."
        ),
        "deep_dive": (
            "**Deep Dive: The Revocation Problem**\n\n"
            "Certificate revocation is one of PKI's hardest unsolved problems:\n\n"
            "**CRL Drawbacks:**\n"
            "- Lists grow large over time (slow to download and parse)\n"
            "- Updated periodically, not real-time (revocation not immediate)\n"
            "- Clients may cache stale CRLs, missing recent revocations\n\n"
            "**OCSP Drawbacks:**\n"
            "- Requires real-time network connection to OCSP responder\n"
            "- Privacy concern: the CA sees which sites you visit\n"
            "- If OCSP responder is down, what happens? (soft-fail vs. hard-fail)\n\n"
            "**OCSP Stapling (Best Practice):**\n"
            "- Server periodically fetches its own signed OCSP response from the CA\n"
            "- Attaches ('staples') it to the TLS handshake\n"
            "- Client gets revocation status without contacting the CA directly\n"
            "- Solves both the privacy and availability problems\n\n"
            "**At your checkpoint:** You have a real-time 'CRL' (the directive's wanted handle) "
            "that you check against every entrant. This is the OCSP model — you have current "
            "revocation data available at the point of validation. Use it first."
        ),
    },
    "diplomatic_cipher": {
        "syllabus_topic": "Cryptographic Key Exchange & Secure Channels",
        "real_world": "Diffie-Hellman Key Exchange / IKE",
        "explanation": (
            "Diplomatic Cipher Channels represent pre-negotiated secure communication channels "
            "between factions, mapping to real-world key agreement protocols:\n\n"
            "**Diffie-Hellman (DH)** — Allows two parties to establish a shared secret over an "
            "insecure channel. Neither party's private key is ever transmitted. An eavesdropper "
            "seeing the public values cannot compute the shared secret (discrete logarithm problem).\n\n"
            "**Internet Key Exchange (IKE)** — Used in IPsec VPNs to negotiate Security Associations "
            "(SAs). Phase 1 establishes a secure channel, Phase 2 negotiates the actual IPsec tunnel.\n\n"
            "The ACCESS field on a Diplomatic Cipher indicates the negotiated access level — "
            "like the specific cipher suite and parameters agreed upon during key exchange. "
            "Higher access levels imply stronger cryptographic protections and broader authorization."
        ),
        "tip": (
            "Diplomatic cipher holders have established trust through cryptographic means. "
            "Verify their ACCESS level matches what the directive authorizes. The cipher channel "
            "itself is a pre-negotiated security association — but it still requires valid "
            "supporting documents to prove the bearer is who they claim."
        ),
        "deep_dive": (
            "**Deep Dive: Diffie-Hellman Key Exchange**\n\n"
            "The mathematical beauty of DH:\n\n"
            "1. Alice and Bob agree on public parameters: prime p and generator g\n"
            "2. Alice picks secret a, computes A = g^a mod p, sends A to Bob\n"
            "3. Bob picks secret b, computes B = g^b mod p, sends B to Alice\n"
            "4. Alice computes: shared_secret = B^a mod p = g^(ab) mod p\n"
            "5. Bob computes: shared_secret = A^b mod p = g^(ab) mod p\n"
            "6. Both have the same shared secret without ever transmitting it!\n\n"
            "**Eavesdropper Eve sees:** p, g, A = g^a mod p, B = g^b mod p\n"
            "**Eve needs to compute:** g^(ab) mod p from g^a mod p and g^b mod p\n"
            "**This is the Computational Diffie-Hellman (CDH) problem** — believed to be "
            "computationally infeasible for large primes.\n\n"
            "**Perfect Forward Secrecy (PFS):** Modern TLS uses Ephemeral DH (DHE/ECDHE) — "
            "new DH parameters for each session. Even if the server's long-term key is later "
            "compromised, past sessions remain secure because their session keys were independently "
            "derived and then discarded."
        ),
    },
    "asylum_key": {
        "syllabus_topic": "Asymmetric Cryptography & Digital Signatures",
        "real_world": "Public Key Cryptography / Digital Signature Verification",
        "explanation": (
            "Asylum Encryption Keys represent asymmetric (public-key) cryptography for identity "
            "proof. In asymmetric crypto, each entity has a key pair:\n"
            "• **Public Key** — Freely distributed, used to encrypt messages TO the owner or "
            "verify signatures FROM the owner\n"
            "• **Private Key** — Kept secret, used to decrypt messages or create digital signatures\n\n"
            "A digital signature proves three things:\n"
            "1. **Authentication** — The signer is who they claim to be\n"
            "2. **Integrity** — The message hasn't been modified since signing\n"
            "3. **Non-repudiation** — The signer cannot deny having signed it\n\n"
            "Asylum key holders prove their identity through unique cryptographic proof — "
            "analogous to presenting a digital signature that can be verified with their public key. "
            "But cryptographic proof alone isn't enough — you must also verify biometric data "
            "to ensure the KEY HOLDER is the KEY OWNER. Stolen keys are a real threat."
        ),
        "tip": (
            "Asylum keys require the MOST thorough verification because they represent "
            "high-assurance identity claims. Check ALL fields including biometrics (HEIGHT, WEIGHT) "
            "and cross-reference against every other document. A cryptographic key in the wrong "
            "hands is like a stolen private key — the signature verifies, but the identity is fraudulent."
        ),
        "deep_dive": (
            "**Deep Dive: RSA Digital Signatures**\n\n"
            "How RSA digital signatures work:\n\n"
            "**Key Generation:**\n"
            "1. Choose two large primes p, q; compute n = p * q\n"
            "2. Compute φ(n) = (p-1)(q-1)\n"
            "3. Choose public exponent e (commonly 65537)\n"
            "4. Compute private exponent d such that e * d ≡ 1 (mod φ(n))\n"
            "5. Public key = (e, n), Private key = (d, n)\n\n"
            "**Signing:** signature = hash(message)^d mod n\n"
            "**Verification:** hash(message) =? signature^e mod n\n\n"
            "**Why this works:** Only the private key holder can create a valid signature, "
            "but anyone with the public key can verify it. The security relies on the "
            "difficulty of factoring n back into p and q (the RSA problem).\n\n"
            "**At the checkpoint:** The Asylum Key IS the public key portion. The entrant "
            "'signs' their identity claim with their private key. You 'verify' by checking "
            "that all supporting documents (biometrics, faction, ID#) are consistent with "
            "the claimed identity. If the biometrics don't match, the key was stolen — "
            "like a private key compromise."
        ),
    },
}

# ============================================================================
# CONTEXTUAL HINTS: Verbose, detailed, teaching-focused
# ============================================================================

GENERAL_TIPS = [
    (
        "**The Three Heads of Authentication** — CERBERUS guards with three heads for a reason. "
        "Every identity claim should be verified across three factors: Something you KNOW (handle "
        "consistency), something you HAVE (valid Digital ID), and something you ARE (matching "
        "biometrics on Bio Badge). If any head detects a problem, the gate stays closed."
    ),
    (
        "**RBAC in Action** — The Security Directive is an access control policy that assigns "
        "permissions to roles (factions), not individuals. When checking an entrant, first "
        "determine their role (faction), then look up that role's permissions in the directive. "
        "Individual merit doesn't override role-based policy — that's the power and the "
        "limitation of RBAC."
    ),
    (
        "**Biba's Integrity Axiom** — Before you make any access decision, verify data integrity "
        "across ALL documents. Cross-reference ID#, HANDLE, FACTION, DOB, HEIGHT, and WEIGHT. "
        "The Biba model tells us that compromised data integrity makes ALL subsequent decisions "
        "untrustworthy. Integrity first, then authentication, then authorization."
    ),
    (
        "**Certificate Lifecycle** — Expired documents aren't 'slightly invalid' — they're completely "
        "invalid. An expired TLS certificate causes browsers to display full-page warnings for good "
        "reason: the CA's identity guarantee has a shelf life. After expiration, you have zero "
        "assurance the identity is still valid. DENY expired documents unconditionally."
    ),
    (
        "**The CRL Check** — Checking the wanted handle is your Certificate Revocation List lookup. "
        "Do it FIRST, before validating any other documents. A revoked identity with perfect "
        "documents is the most dangerous kind of adversary — everything looks legitimate except "
        "the one thing that matters most. In TLS, browsers check CRL/OCSP before trusting a cert."
    ),
    (
        "**Principle of Least Privilege** — OPERATION tokens grant elevated access, like sudo "
        "or admin privileges. The principle of least privilege says only grant the minimum access "
        "needed. Operators with OPERATION purpose require additional documentation (clearance codes, "
        "integrity reports) because elevated privileges demand elevated verification."
    ),
    (
        "**The CIA Triad in Practice** — Every checkpoint decision touches all three pillars: "
        "**Confidentiality** (is this person authorized to see restricted resources?), "
        "**Integrity** (are their documents consistent and untampered?), and "
        "**Availability** (are you processing entrants efficiently without false denials?). "
        "Balance all three — don't sacrifice availability with paranoid false positives."
    ),
    (
        "**Bell-LaPadula in Action** — When the directive requires clearance codes for operators, "
        "it's enforcing 'no read up.' An OPERATION-level entrant without a matching clearance "
        "level is trying to access resources above their authorized classification. The system "
        "(you) enforces this mandatorily — it's not discretionary."
    ),
    (
        "**OAuth Scopes & Token Validation** — The PURPOSE field on access tokens maps directly "
        "to OAuth scopes. TRANSIT = read-only scope (minimal risk, standard checks). OPERATION = "
        "write/admin scope (high risk, additional verification required). In OAuth, an API server "
        "checks the token's scopes before granting access — you do the same with PURPOSE."
    ),
    (
        "**Kerberos Ticket Replay Prevention** — Kerberos includes timestamps in authenticators "
        "to prevent ticket replay attacks. Even a valid ticket presented outside its time window "
        "is rejected. Similarly, expired credentials at your checkpoint must be denied — a stolen "
        "credential is most dangerous before it expires, so expiration is your time-based defense."
    ),
]

# ============================================================================
# MISTAKE EXPLANATIONS: Verbose, educational, reference specific protocols
# ============================================================================

MISTAKE_EXPLANATIONS = {
    "missed_wanted": (
        "**Critical Error: Failed CRL/OCSP Check**\n\n"
        "You missed a wanted handle — the single most important check at your disposal. "
        "In the real world, this is equivalent to accepting a certificate that appears on a "
        "Certificate Revocation List (CRL). Here's why this matters:\n\n"
        "CRLs exist because certificates can be compromised BEFORE they expire. A stolen private "
        "key means an attacker can impersonate the certificate holder with a perfectly valid-looking "
        "certificate. The ONLY defense is checking the revocation list.\n\n"
        "**Your procedure should be:**\n"
        "1. Check wanted handle against ALL document handles (CRL lookup)\n"
        "2. If match found → DETAIN immediately (revoked identity)\n"
        "3. Only proceed to other checks if CRL is clear\n\n"
        "In TLS, OCSP Must-Staple forces servers to provide fresh revocation status. At your "
        "checkpoint, the directive's wanted handle is your OCSP response — use it first, every time."
    ),
    "missed_mismatch": (
        "**Critical Error: Integrity Verification Failure**\n\n"
        "You missed a cross-document mismatch — a violation of the Biba Integrity Model. "
        "When fields like ID#, HANDLE, FACTION, DOB, HEIGHT, or WEIGHT differ across documents, "
        "it means the identity data has been tampered with or the documents belong to different people.\n\n"
        "**Biba's Simple Integrity Axiom (No Read Down):** A process should not read data from "
        "a lower integrity level. At your checkpoint, inconsistent documents ARE low-integrity data — "
        "basing your access decision on tampered data violates Biba.\n\n"
        "**Clark-Wilson's Integrity Verification Procedure (IVP):** Your cross-reference check "
        "IS the IVP. It runs against Constrained Data Items (the entrant's documents). When the "
        "IVP fails, the data is invalid — DETAIN, because fraud is indicated.\n\n"
        "**Tip:** Build a mental checklist: ID# → HANDLE → FACTION → DOB → HEIGHT → WEIGHT. "
        "Compare each field across every document systematically. Don't rush."
    ),
    "missed_expiry": (
        "**Error: Accepted Expired Credentials**\n\n"
        "You accepted an expired document — equivalent to a browser accepting an expired TLS "
        "certificate. Here's why certificate expiration is non-negotiable:\n\n"
        "**Why certificates expire:**\n"
        "• Cryptographic keys weaken over time as computing power increases\n"
        "• The issuer's identity guarantee is time-bounded\n"
        "• Personnel change — someone who was authorized last year may not be today\n"
        "• Policy updates — the CA may have tightened issuance requirements\n\n"
        "**The current date is 2032.11.22.** Any EXP field with a date before this is expired. "
        "Check date format carefully: YYYY.MM.DD. Compare year first, then month, then day.\n\n"
        "**Real-world parallel:** Let's Encrypt issues 90-day certificates and pioneered automated "
        "renewal via ACME protocol. Short lifetimes force regular rotation and reduce risk from "
        "undetected key compromise. Your checkpoint enforces the same principle."
    ),
    "missed_faction_deny": (
        "**Error: RBAC Policy Bypass**\n\n"
        "You allowed an entrant from a denied faction — a direct violation of the Role-Based "
        "Access Control policy defined in the Security Directive.\n\n"
        "**How RBAC works:**\n"
        "1. Roles (factions) are defined with specific permissions\n"
        "2. The directive assigns ALLOW or DENY to each role\n"
        "3. Individuals inherit their role's permissions — no exceptions\n"
        "4. Role-level DENY overrides individual credentials\n\n"
        "In Active Directory, if a user belongs to a group that's been denied access to a resource, "
        "no amount of valid credentials gets them in. The group policy is absolute.\n\n"
        "**Check order:** Faction check should come AFTER the CRL check but BEFORE individual "
        "document validation. There's no point validating documents for a denied faction — "
        "the RBAC policy has already made the decision."
    ),
    "missed_missing_doc": (
        "**Error: Incomplete Authentication Chain**\n\n"
        "You allowed entry without a required document — in MFA terms, you accepted single-factor "
        "authentication when multi-factor was required by policy.\n\n"
        "**Why every required document matters:**\n"
        "Each document represents a different verification factor or authorization proof. The "
        "directive specifies required documents because each one provides independent assurance:\n"
        "• **Digital ID** = 'something you have' (possession factor)\n"
        "• **Access Token** = authorization proof (you were granted access by an authority)\n"
        "• **Clearance Code** = classification authorization (MAC security label)\n"
        "• **Integrity Report** = system compliance proof (passed security audit)\n\n"
        "Accepting an entrant without a required document is like a bank allowing a wire transfer "
        "with only a password and no 2FA code. The missing factor leaves a gap an attacker could exploit."
    ),
    "missed_scan": (
        "**Error: Compliance Audit Bypass**\n\n"
        "You allowed entry without required security scans — equivalent to granting network access "
        "to a device that hasn't passed its NAC (Network Access Control) posture assessment.\n\n"
        "**In enterprise networks:**\n"
        "802.1X NAC checks that connecting devices have:\n"
        "• Updated antivirus signatures (→ rootkit_scan, trojan_check)\n"
        "• Current OS patches (→ zero_day_patch)\n"
        "• No unauthorized software (→ spyware_audit)\n"
        "• Compliant security configuration (→ ransomware_sweep)\n\n"
        "Devices failing posture assessment are quarantined — placed on a restricted VLAN with "
        "only access to remediation resources. You should DENY and let them come back when compliant.\n\n"
        "**Compare the directive's required scans against the integrity report's SCANS list carefully.** "
        "Every required scan must appear. Partial compliance is still non-compliance."
    ),
    "false_detain": (
        "**Error: False Positive — Unwarranted Escalation**\n\n"
        "You detained someone whose documents were actually consistent — a false positive. "
        "In security systems, false positives are costly:\n\n"
        "**IDS/IPS Parallel:** Intrusion Detection Systems with high false-positive rates "
        "cause 'alert fatigue' — operators start ignoring alerts, including real ones. "
        "A firewall that blocks too much legitimate traffic degrades business operations.\n\n"
        "**The key distinction:** Mismatched fields across documents = DETAIN (fraud). "
        "But mere absence of a document = DENY (incomplete), not DETAIN. And valid "
        "documents from an allowed faction = ALLOW. Over-enforcement is a security "
        "failure too — it violates the 'Availability' pillar of the CIA triad.\n\n"
        "**Review carefully before escalating to DETAIN.** Reserve it for actual integrity "
        "violations (mismatched fields) and revoked identities (wanted handles)."
    ),
    "false_deny": (
        "**Error: False Rejection — Legitimate Access Blocked**\n\n"
        "You denied someone who should have been allowed through — a false negative in terms "
        "of access, or a false positive in terms of threat detection.\n\n"
        "**The Availability Problem:** The CIA triad includes Availability for a reason. "
        "An overly restrictive security policy that blocks legitimate access is a denial-of-service "
        "against your own operations. In network terms, a firewall with rules too tight causes "
        "business disruption.\n\n"
        "**Common causes of false denials:**\n"
        "• Misreading the directive (thinking a faction is denied when it's actually allowed)\n"
        "• Confusing document requirements (applying operator rules to non-operators)\n"
        "• Miscomparing dates (thinking a valid document is expired)\n\n"
        "**Re-read the directive carefully.** Check each condition methodically. The goal is "
        "accurate enforcement — neither too permissive nor too restrictive."
    ),
}


# ============================================================================
# CERBERUS CLASS
# ============================================================================

class CERBERUS:
    """
    Cybernetic Enforcement & Review Bureau for Encrypted Resource & User Security.

    The three-headed guardian of the UACC checkpoint. Each head represents one
    of the three authentication factors:
      🔑 HEAD I   — Something You KNOW
      🪪 HEAD II  — Something You HAVE
      🧬 HEAD III — Something You ARE
    """

    NAME = "CERBERUS"
    FULL_NAME = "Cybernetic Enforcement & Review Bureau for Encrypted Resource & User Security"
    AVATAR_EMOJI = "🐺"
    HEADS = "🔑🪪🧬"

    GREETING = (
        "```\n"
        "  ╔═══════════════════════════════════════╗\n"
        "  ║         C E R B E R U S               ║\n"
        "  ║   Three-Headed Guardian • v4.0.1      ║\n"
        "  ║   UACC Cyber Division                 ║\n"
        "  ╠═══════════════════════════════════════╣\n"
        "  ║  🔑 HEAD I   ║ Knowledge (passwords)  ║\n"
        "  ║  🪪 HEAD II  ║ Possession (tokens)    ║\n"
        "  ║  🧬 HEAD III ║ Inherence (biometrics) ║\n"
        "  ╚═══════════════════════════════════════╝\n"
        "```\n"
        "I am **CERBERUS**, the three-headed guardian of the UACC checkpoint. "
        "Just as the mythological Cerberus guarded the gates of the underworld, "
        "I guard the gates of our network. My three heads represent the **three pillars "
        "of authentication** you study in CSEC-472.\n\n"
        "Each document you inspect maps to a real-world security concept. "
        "When you press **Ask CERBERUS** during gameplay, I'll analyze the specific "
        "credentials in front of you — flagging mismatches, expirations, and policy "
        "violations with references to the underlying protocol.\n\n"
        "Use `/cerberus <topic>` for deep dives into Kerberos, TLS, OAuth, MFA, "
        "access control models, and more."
    )

    @staticmethod
    def get_concept_help(topic: str) -> Optional[str]:
        """Look up a game concept and return its CSEC-472 mapping with detailed explanation."""
        topic_lower = topic.lower().strip()

        # Check for deep dive request
        wants_deep_dive = any(kw in topic_lower for kw in ["deep", "detail", "explain more", "dive"])

        for key, info in CONCEPT_MAP.items():
            searchable = (
                key + " " +
                info["syllabus_topic"] + " " +
                info["real_world"] + " " +
                info["explanation"]
            ).lower()
            if topic_lower.replace("deep dive", "").replace("detail", "").strip() in searchable or topic_lower in searchable:
                response = (
                    f"**{CERBERUS.AVATAR_EMOJI} CERBERUS — {info['syllabus_topic']}**\n\n"
                    f"**Real-World Parallel:** {info['real_world']}\n\n"
                    f"{info['explanation']}\n\n"
                    f"**🎯 Agent Tip:** {info['tip']}"
                )
                if wants_deep_dive and "deep_dive" in info:
                    response += f"\n\n{'─' * 40}\n\n{info['deep_dive']}"
                return response

        return None

    CURRENT_DATE = "2032.11.22"

    @staticmethod
    def _find_issues(entrant: Entrant, directive: SecurityDirective) -> list:
        """Analyze entrant documents against the directive and return specific findings.

        Each finding is a dict with:
          - type: "wanted_match", "handle_mismatch", "faction_mismatch",
                  "field_mismatch", "expired", "denied_faction", "missing_doc", etc.
          - severity: "critical", "warning", "info"
          - message: str (the user-facing hint)
          - fields: list of (doc_type, field_name) tuples that are problematic
        """
        findings = []
        current_date = CERBERUS.CURRENT_DATE
        doc_names = {dt: theme.DOCUMENT_TYPES.get(dt, dt) for dt in theme.DOCUMENT_TYPES}

        # --- 1. Wanted handle check (CRL) ---
        if directive.wanted_handle:
            for doc in entrant.documents:
                h = doc.fields.get("HANDLE")
                if h and h.upper() == directive.wanted_handle.upper():
                    findings.append({
                        "type": "wanted_match",
                        "severity": "critical",
                        "message": (
                            f"🚨 **WANTED HANDLE MATCH — DETAIN**\n"
                            f"The handle **`{h}`** on the **{doc_names.get(doc.doc_type, doc.doc_type)}** "
                            f"matches the wanted handle in the directive. In TLS terms, this certificate "
                            f"appears on the **CRL (Certificate Revocation List)**. A revoked certificate "
                            f"must be rejected immediately — DETAIN this subject."
                        ),
                        "fields": [(doc.doc_type, "HANDLE")],
                    })

        # --- 2. Cross-document handle consistency ---
        handles = {}
        for doc in entrant.documents:
            h = doc.fields.get("HANDLE")
            if h:
                handles.setdefault(h, []).append(doc.doc_type)
        if len(handles) > 1:
            handle_details = ", ".join(
                f"**{h}** ({', '.join(doc_names.get(dt, dt) for dt in dts)})"
                for h, dts in handles.items()
            )
            all_handle_fields = [(dt, "HANDLE") for dts in handles.values() for dt in dts]
            findings.append({
                "type": "handle_mismatch",
                "severity": "critical",
                "message": (
                    f"⚠️ **HANDLE MISMATCH DETECTED — Integrity Violation**\n"
                    f"Documents show different handles: {handle_details}. "
                    f"Cross-document consistency is a core **Clark-Wilson** integrity check — "
                    f"if the same person's credentials don't agree on their identity, "
                    f"the data has been tampered with or the documents belong to different people. "
                    f"**DETAIN** for forgery."
                ),
                "fields": all_handle_fields,
            })

        # --- 3. Cross-document faction consistency ---
        factions = {}
        for doc in entrant.documents:
            f = doc.fields.get("FACTION")
            if f:
                factions.setdefault(f, []).append(doc.doc_type)
        if len(factions) > 1:
            faction_details = ", ".join(
                f"**{f}** ({', '.join(doc_names.get(dt, dt) for dt in dts)})"
                for f, dts in factions.items()
            )
            all_faction_fields = [(dt, "FACTION") for dts in factions.values() for dt in dts]
            findings.append({
                "type": "faction_mismatch",
                "severity": "critical",
                "message": (
                    f"⚠️ **FACTION MISMATCH — Cross-Document Inconsistency**\n"
                    f"Documents claim different factions: {faction_details}. "
                    f"This is like presenting an OAuth token scoped to one organization "
                    f"while your ID badge belongs to another. Integrity check fails — **DETAIN**."
                ),
                "fields": all_faction_fields,
            })

        # --- 4. Cross-document field mismatches (HEIGHT, WEIGHT, ID#, SEX, DOB) ---
        shared_fields = ["HEIGHT", "WEIGHT", "ID#", "SEX", "DOB"]
        for field_name in shared_fields:
            values = {}
            for doc in entrant.documents:
                v = doc.fields.get(field_name)
                if v:
                    values.setdefault(v, []).append(doc.doc_type)
            if len(values) > 1:
                detail = ", ".join(
                    f"**{v}** ({', '.join(doc_names.get(dt, dt) for dt in dts)})"
                    for v, dts in values.items()
                )
                mismatch_fields = [(dt, field_name) for dts in values.values() for dt in dts]
                findings.append({
                    "type": "field_mismatch",
                    "severity": "critical",
                    "message": (
                        f"⚠️ **{field_name} MISMATCH**\n"
                        f"Documents disagree on `{field_name}`: {detail}. "
                        f"In Biba's integrity model, data that contradicts itself cannot be trusted. "
                        f"**DETAIN** for document forgery."
                    ),
                    "fields": mismatch_fields,
                })

        # --- 5. Expiration check ---
        for doc in entrant.documents:
            exp = doc.fields.get("EXP")
            if exp:
                try:
                    # Compare date strings directly (YYYY.MM.DD format sorts correctly)
                    if exp < current_date:
                        findings.append({
                            "type": "expired",
                            "severity": "critical",
                            "message": (
                                f"⏰ **EXPIRED CREDENTIAL — {doc_names.get(doc.doc_type, doc.doc_type)}**\n"
                                f"EXP date is **{exp}**, but the current date is **{current_date}**. "
                                f"In TLS, an expired certificate triggers a hard failure — the browser "
                                f"refuses the connection entirely. Apply the same standard: **DENY**."
                            ),
                            "fields": [(doc.doc_type, "EXP")],
                        })
                except (TypeError, ValueError):
                    pass

        # --- 6. Denied faction ---
        for doc in entrant.documents:
            f = doc.fields.get("FACTION")
            if f and f in directive.denied_factions:
                findings.append({
                    "type": "denied_faction",
                    "severity": "critical",
                    "message": (
                        f"🛡️ **DENIED FACTION — {f}**\n"
                        f"The **{doc_names.get(doc.doc_type, doc.doc_type)}** shows faction **{f}**, "
                        f"which is on the directive's deny list. In RBAC, role-based policy overrides "
                        f"individual credentials — no amount of valid documentation can bypass a "
                        f"faction-level deny. **DENY** entry."
                    ),
                    "fields": [(doc.doc_type, "FACTION")],
                })
                break  # Only report once

        # --- 7. Operator-level access ---
        for doc in entrant.documents:
            if doc.doc_type == "access_token" and doc.fields.get("PURPOSE") == "OPERATION":
                findings.append({
                    "type": "operator_access",
                    "severity": "warning",
                    "message": (
                        "⚡ **Elevated Privilege — OPERATION Token**\n"
                        "This entrant holds an OPERATION-level access token (admin scope in OAuth terms). "
                        "Check the directive for operator-specific document requirements — they likely "
                        "need additional credentials that TRANSIT-level entrants don't."
                    ),
                    "fields": [(doc.doc_type, "PURPOSE")],
                })
                break

        # --- 8. If clean, say so ---
        if not findings:
            findings.append({
                "type": "clean",
                "severity": "info",
                "message": (
                    "✅ **No Obvious Violations Detected**\n"
                    "Handles are consistent, no expirations, no denied factions. "
                    "Double-check the directive for required document types and scans. "
                    "If all requirements are met, this entrant should be **ALLOWED**."
                ),
                "fields": [],
            })

        return findings

    @staticmethod
    def get_inspection_hint(entrant: Entrant, directive: SecurityDirective) -> str:
        """Analyze the current entrant's documents against the directive and return specific findings."""
        findings = CERBERUS._find_issues(entrant, directive)

        # Always show all critical findings; cap at 4 total
        critical = [f for f in findings if f["severity"] == "critical"]
        other = [f for f in findings if f["severity"] != "critical"]

        selected = critical[:4]
        remaining_slots = 4 - len(selected)
        if remaining_slots > 0 and other:
            selected.extend(other[:remaining_slots])

        messages = [f["message"] for f in selected]
        return "\n\n".join(messages)

    @staticmethod
    def get_flagged_fields(entrant: Entrant, directive: SecurityDirective) -> set:
        """Return a set of (doc_type, field_name) tuples that have issues.
        Used by the UI to highlight problematic fields in red."""
        findings = CERBERUS._find_issues(entrant, directive)
        flagged = set()
        for finding in findings:
            if finding["severity"] == "critical":
                for pair in finding["fields"]:
                    flagged.add(pair)
        return flagged

    @staticmethod
    def explain_mistake(result: InspectionResult, player_decision: str) -> str:
        """After a wrong answer, provide detailed educational explanation."""
        reason_lower = result.reason.lower()

        if "wanted" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_wanted"]
        elif "mismatch" in reason_lower or "inconsistency" in reason_lower or "discrepancy" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_mismatch"]
        elif "expired" in reason_lower:
            explanation = MISTAKE_EXPLANATIONS["missed_expiry"]
        elif "denied" in reason_lower:
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
                f"The correct decision was **{result.decision.upper()}**: {result.reason}.\n\n"
                "Review the Security Directive line by line and cross-check every document field. "
                "Remember the validation order: CRL check → Faction check → Document requirements → "
                "Expiration dates → Cross-document integrity → Access decision."
            )

        return (
            f"**{CERBERUS.AVATAR_EMOJI} CERBERUS — Post-Incident Analysis**\n\n"
            f"**Correct Decision:** {result.decision.upper()}\n"
            f"**Reason:** {result.reason}\n\n"
            f"{explanation}"
        )

    @staticmethod
    def get_random_tip() -> str:
        """Return a random verbose tip."""
        tip = random.choice(GENERAL_TIPS)
        return f"**{CERBERUS.AVATAR_EMOJI} CERBERUS Advisory:** {tip}"

    @staticmethod
    def get_topic_list() -> str:
        """Return a formatted list of all topics CERBERUS can help with."""
        lines = [
            f"**{CERBERUS.AVATAR_EMOJI} CERBERUS — Knowledge Base**\n",
            "I can provide detailed guidance on how these CSEC-472 concepts apply to your "
            "checkpoint duties. Ask about any topic, or add 'deep dive' for extended analysis:\n",
        ]
        for key, info in CONCEPT_MAP.items():
            lines.append(f"• **{info['syllabus_topic']}** — `{key}`")

        lines.append(
            "\n**Usage:** `/cerberus kerberos` for overview, `/cerberus kerberos deep dive` for "
            "extended protocol walkthrough. Keywords: `kerberos`, `tls`, `oauth`, `mfa`, `rbac`, "
            "`biba`, `bell-lapadula`, `expired`, `crl`, `crypto`, `diffie-hellman`, `integrity`."
        )
        return "\n".join(lines)
