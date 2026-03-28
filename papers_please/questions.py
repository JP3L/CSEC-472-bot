"""
CSEC-472 concept review questions for the Papers Please game.
Questions are woven into gameplay to reinforce authentication and security concepts.
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict


@dataclass
class ConceptQuestion:
    """A multiple-choice concept review question."""
    id: str                     # Unique ID like "kerberos_01"
    topic: str                  # Syllabus topic
    difficulty: int             # 0-3 (0=basic, 3=advanced)
    question: str               # The question text
    options: List[str]          # 4 options (first is always the correct answer internally)
    explanation: str            # Teaching explanation shown after answering
    game_context: str           # How this concept connects to the game mechanic


# ============================================================================
# QUESTION BANK
# ============================================================================

QUESTION_BANK: List[ConceptQuestion] = [
    # ── KERBEROS ──────────────────────────────────────────────────
    ConceptQuestion(
        id="kerberos_01",
        topic="Kerberos",
        difficulty=0,
        question="In Kerberos, what does the KDC issue to a user after initial authentication?",
        options=[
            "A Ticket-Granting Ticket (TGT)",
            "A digital certificate",
            "An OAuth access token",
            "A session cookie",
        ],
        explanation="The KDC's Authentication Server issues a TGT after verifying credentials. The TGT is then used to request service tickets without re-authenticating — similar to how access tokens in the game prove prior authentication to a faction's authority.",
        game_context="Access Tokens in the game work like Kerberos tickets — they prove the bearer authenticated to their faction's KDC.",
    ),
    ConceptQuestion(
        id="kerberos_02",
        topic="Kerberos",
        difficulty=1,
        question="What prevents replay attacks in the Kerberos protocol?",
        options=[
            "Timestamps and ticket expiration",
            "Password complexity requirements",
            "IP address whitelisting",
            "Biometric verification",
        ],
        explanation="Kerberos uses timestamps (authenticators) and ticket expiration to prevent replay attacks. If a ticket is expired, it's rejected — just like how you must reject expired documents at the checkpoint.",
        game_context="When you check document EXP dates at the checkpoint, you're performing the same time-validity check that Kerberos does with ticket lifetimes.",
    ),
    ConceptQuestion(
        id="kerberos_03",
        topic="Kerberos",
        difficulty=2,
        question="In Kerberos, mutual authentication means:",
        options=[
            "Both the client and server verify each other's identity",
            "Two users authenticate to the same server",
            "The password is checked twice for accuracy",
            "Both a password and token are required",
        ],
        explanation="Mutual authentication ensures both parties verify each other, preventing man-in-the-middle attacks. The server proves it can decrypt the service ticket, confirming it's the real service.",
        game_context="At the checkpoint, mutual trust matters — you verify the entrant's documents, and the UACC credential on your terminal proves you're an authorized agent.",
    ),

    # ── TLS / PKI ─────────────────────────────────────────────────
    ConceptQuestion(
        id="tls_01",
        topic="TLS / PKI",
        difficulty=0,
        question="What is the primary purpose of a Certificate Authority (CA) in PKI?",
        options=[
            "To verify identities and issue digital certificates",
            "To encrypt all network traffic",
            "To store user passwords securely",
            "To manage firewall rules",
        ],
        explanation="CAs are trusted third parties that verify identities and issue digital certificates binding public keys to entities. This chain of trust is foundational to TLS security.",
        game_context="Issuing Nodes in the game function as CAs — they vouch for the identity on each Digital Identity Certificate you inspect.",
    ),
    ConceptQuestion(
        id="tls_02",
        topic="TLS / PKI",
        difficulty=1,
        question="What happens when a TLS certificate expires?",
        options=[
            "The browser rejects the connection and shows a warning",
            "The certificate automatically renews",
            "The connection proceeds but unencrypted",
            "The CA revokes all related certificates",
        ],
        explanation="Expired certificates are rejected because the CA can no longer vouch for the identity. Browsers show security warnings, and the connection is typically blocked.",
        game_context="This is exactly why you DENY entrants with expired documents — an expired cert means the authority's guarantee has lapsed.",
    ),
    ConceptQuestion(
        id="tls_03",
        topic="TLS / PKI",
        difficulty=2,
        question="A Certificate Revocation List (CRL) is used to:",
        options=[
            "List certificates that have been invalidated before their expiration date",
            "Track which certificates will expire soon",
            "Store backup copies of all issued certificates",
            "Record the order in which certificates were created",
        ],
        explanation="CRLs list certificates revoked before expiry — due to compromise, key theft, or policy changes. OCSP provides real-time revocation status as an alternative to CRLs.",
        game_context="The wanted handle in your Security Directive is essentially a CRL entry — even if all documents look valid, a revoked identity must be DETAINED.",
    ),

    # ── OAuth 2.0 ─────────────────────────────────────────────────
    ConceptQuestion(
        id="oauth_01",
        topic="OAuth 2.0",
        difficulty=0,
        question="In OAuth 2.0, what defines what actions an access token can perform?",
        options=[
            "Scopes",
            "The token's encryption algorithm",
            "The user's password strength",
            "The server's IP address",
        ],
        explanation="Scopes limit what an access token can do — like 'read:email' or 'write:files'. This enforces the principle of least privilege by granting only the permissions needed.",
        game_context="The PURPOSE field on Access Tokens (TRANSIT vs OPERATION) works like OAuth scopes — OPERATION grants elevated privileges that require additional verification.",
    ),
    ConceptQuestion(
        id="oauth_02",
        topic="OAuth 2.0",
        difficulty=1,
        question="Why do OAuth access tokens have limited lifetimes?",
        options=[
            "To reduce the window of opportunity if a token is stolen",
            "To force users to create stronger passwords",
            "To reduce server storage requirements",
            "To comply with international law",
        ],
        explanation="Short-lived tokens limit damage from theft. Refresh tokens can obtain new access tokens without re-authentication, balancing security with usability.",
        game_context="Token DURATION and EXP fields in the game reflect this principle — expired tokens must be rejected because their authorization window has closed.",
    ),
    ConceptQuestion(
        id="oauth_03",
        topic="OAuth 2.0",
        difficulty=2,
        question="The OAuth 2.0 Authorization Code Grant is preferred for web applications because:",
        options=[
            "The access token is never exposed to the user's browser",
            "It requires the fewest network requests",
            "It doesn't need a client secret",
            "It works without HTTPS",
        ],
        explanation="The authorization code is exchanged server-side for an access token, keeping the token out of the browser's URL/history. This prevents token leakage through browser-based attacks.",
        game_context="Secure token handling matters at checkpoints too — an access token's validity depends on the secure chain from its issuing authority to the bearer.",
    ),

    # ── PASSWORDS & HASHING ───────────────────────────────────────
    ConceptQuestion(
        id="password_01",
        topic="Passwords & Hashing",
        difficulty=0,
        question="What is the purpose of a salt in password hashing?",
        options=[
            "To ensure identical passwords produce different hashes",
            "To encrypt the password for transmission",
            "To make the password longer",
            "To verify the user's identity",
        ],
        explanation="A salt is random data added before hashing, ensuring that even identical passwords produce unique hashes. This defeats precomputed attacks like rainbow tables.",
        game_context="Each entrant's unique ID# functions like a salt — it makes their identity distinguishable even if other fields match another person's.",
    ),
    ConceptQuestion(
        id="password_02",
        topic="Passwords & Hashing",
        difficulty=1,
        question="Why is bcrypt preferred over MD5 for password hashing?",
        options=[
            "bcrypt is intentionally slow, making brute-force attacks costly",
            "bcrypt produces shorter hashes that are easier to store",
            "MD5 cannot hash passwords longer than 8 characters",
            "bcrypt doesn't require a salt",
        ],
        explanation="bcrypt includes a configurable work factor that makes hashing deliberately slow. This dramatically increases the cost of brute-force and dictionary attacks compared to fast hashes like MD5.",
        game_context="Thorough verification takes time — just as bcrypt trades speed for security, you trade speed for accuracy at the checkpoint.",
    ),

    # ── MFA ────────────────────────────────────────────────────────
    ConceptQuestion(
        id="mfa_01",
        topic="Multi-Factor Authentication",
        difficulty=0,
        question="Which combination represents true multi-factor authentication?",
        options=[
            "A password (know) + a phone code (have) + a fingerprint (are)",
            "Three different passwords",
            "A password + a security question + a PIN",
            "An email code + an SMS code + a voice code",
        ],
        explanation="True MFA requires factors from different categories: something you know, something you have, and something you are. Three passwords are all the same factor type.",
        game_context="In the game: Digital ID = something you have, Handle = something you know, Bio Badge = something you are. All three together form complete MFA.",
    ),
    ConceptQuestion(
        id="mfa_02",
        topic="Multi-Factor Authentication",
        difficulty=1,
        question="TOTP (Time-based One-Time Password) codes change every 30 seconds because:",
        options=[
            "A short validity window limits the time an intercepted code can be reused",
            "The server can only store 30 seconds of data",
            "Users forget codes after 30 seconds",
            "Network latency requires frequent refreshes",
        ],
        explanation="TOTP's short window minimizes replay attack viability. Even if intercepted, the code expires quickly. Both client and server compute the same code from a shared secret and current time.",
        game_context="Document expiration in the game serves the same purpose — time-limited credentials reduce the window for fraudulent use.",
    ),
    ConceptQuestion(
        id="mfa_03",
        topic="Multi-Factor Authentication",
        difficulty=2,
        question="FIDO2/WebAuthn improves on traditional MFA because:",
        options=[
            "It uses public-key cryptography and is resistant to phishing",
            "It requires three passwords instead of one",
            "It stores biometrics on a central server",
            "It only works on government-approved devices",
        ],
        explanation="FIDO2 uses asymmetric cryptography with origin-bound credentials, making phishing impossible — the private key never leaves the authenticator, and credentials are bound to the exact website domain.",
        game_context="Asylum Encryption Keys in the game use similar asymmetric principles — the key holder proves identity through a unique cryptographic token.",
    ),

    # ── ACCESS CONTROL ────────────────────────────────────────────
    ConceptQuestion(
        id="access_01",
        topic="Access Control",
        difficulty=0,
        question="In Role-Based Access Control (RBAC), access decisions are based on:",
        options=[
            "The user's assigned role within the organization",
            "The time of day the request is made",
            "The physical location of the user",
            "The user's password complexity",
        ],
        explanation="RBAC assigns permissions to roles, then assigns users to roles. This simplifies management — change a role's permissions and all members are updated automatically.",
        game_context="Faction-based access rules in the Security Directive are pure RBAC — each faction (role) has defined permissions, and entrants inherit those permissions from their faction membership.",
    ),
    ConceptQuestion(
        id="access_02",
        topic="Access Control",
        difficulty=1,
        question="The principle of least privilege states that:",
        options=[
            "Users should only have the minimum access needed for their task",
            "All users should have equal access levels",
            "Administrators should have access to everything at all times",
            "Privileges should be granted based on seniority",
        ],
        explanation="Least privilege minimizes the attack surface by restricting each user to only the resources they need. If compromised, the damage is limited to their minimal access scope.",
        game_context="TRANSIT vs OPERATION token purposes embody this — TRANSIT grants minimal network traversal, while OPERATION requires additional documentation because it implies elevated access.",
    ),
    ConceptQuestion(
        id="access_03",
        topic="Access Control",
        difficulty=2,
        question="Mandatory Access Control (MAC) differs from Discretionary Access Control (DAC) because:",
        options=[
            "In MAC, access policies are enforced by the system and cannot be overridden by users",
            "MAC allows users to share files freely while DAC restricts sharing",
            "MAC only works on classified government systems",
            "DAC requires administrator approval for every access request",
        ],
        explanation="In MAC, the system enforces access policies based on security labels — users cannot change permissions. In DAC, resource owners can grant/revoke access at their discretion.",
        game_context="Your Security Directive is a MAC policy — you can't override it for individual entrants, even if their documents look valid. The system's rules are absolute.",
    ),

    # ── SECURITY MODELS ───────────────────────────────────────────
    ConceptQuestion(
        id="model_01",
        topic="Security Models",
        difficulty=1,
        question="The Bell-LaPadula model's 'no read up' rule means:",
        options=[
            "A subject cannot read data at a higher security classification",
            "Users cannot read their own previous messages",
            "Files cannot be read more than once",
            "Lower-level users cannot view the org chart",
        ],
        explanation="Bell-LaPadula enforces confidentiality through 'no read up, no write down' — preventing information flow from higher to lower classification levels. This protects state secrets.",
        game_context="Clearance codes in the game implement this — contractors without proper clearance level cannot access higher-level resources, regardless of other valid credentials.",
    ),
    ConceptQuestion(
        id="model_02",
        topic="Security Models",
        difficulty=1,
        question="The Biba integrity model is primarily concerned with:",
        options=[
            "Preventing unauthorized modification of data",
            "Keeping data confidential",
            "Ensuring system availability",
            "Managing user passwords",
        ],
        explanation="Biba focuses on integrity: 'no write up, no read down' — a subject cannot modify higher-integrity data or read lower-integrity data, preventing corruption of trusted data.",
        game_context="Cross-document consistency checking IS a Biba integrity check — if data doesn't match across documents, the integrity of the identity claim is compromised.",
    ),
    ConceptQuestion(
        id="model_03",
        topic="Security Models",
        difficulty=2,
        question="Clark-Wilson's well-formed transactions require:",
        options=[
            "All data modifications must go through validated transformation procedures",
            "Transactions must be completed within 30 seconds",
            "All users must have the same access level",
            "Data must be encrypted before every transaction",
        ],
        explanation="Clark-Wilson ensures integrity through constrained data items (CDIs), transformation procedures (TPs), and integrity verification procedures (IVPs). All changes must follow approved procedures.",
        game_context="Your checkpoint process IS a Clark-Wilson transformation procedure — entrants (CDIs) must pass through your validated inspection (TP) before state changes (access granted/denied).",
    ),

    # ── CRYPTOGRAPHY ──────────────────────────────────────────────
    ConceptQuestion(
        id="crypto_01",
        topic="Cryptography",
        difficulty=0,
        question="The key difference between symmetric and asymmetric encryption is:",
        options=[
            "Symmetric uses one shared key; asymmetric uses a public/private key pair",
            "Symmetric is newer and more secure",
            "Asymmetric can only encrypt, not decrypt",
            "Symmetric encryption doesn't require any keys",
        ],
        explanation="Symmetric encryption (AES, ChaCha20) uses one key for both encrypt/decrypt. Asymmetric (RSA, ECC) uses a key pair — public to encrypt, private to decrypt — solving the key distribution problem.",
        game_context="Diplomatic Cipher Channels represent pre-shared symmetric keys between factions, while Asylum Encryption Keys use asymmetric principles for identity proof.",
    ),
    ConceptQuestion(
        id="crypto_02",
        topic="Cryptography",
        difficulty=1,
        question="A digital signature verifies:",
        options=[
            "The sender's identity and that the message hasn't been altered",
            "That the message was encrypted",
            "The recipient's identity",
            "That the message was sent at a specific time",
        ],
        explanation="Digital signatures use the sender's private key to create a signature that anyone can verify with the public key. This provides authentication (who sent it) and integrity (not modified).",
        game_context="Each document's issuing node signature is like a digital signature — it proves the document came from an authorized authority and hasn't been tampered with.",
    ),
    ConceptQuestion(
        id="crypto_03",
        topic="Cryptography",
        difficulty=2,
        question="Diffie-Hellman key exchange allows two parties to:",
        options=[
            "Establish a shared secret over an insecure channel",
            "Send encrypted messages without any keys",
            "Verify each other's identity",
            "Store passwords securely",
        ],
        explanation="DH enables two parties to derive a shared secret using public values — an eavesdropper seeing the exchange cannot compute the shared key. This is the foundation of perfect forward secrecy in TLS.",
        game_context="Diplomatic Cipher Channels between factions represent these pre-negotiated key agreements — secure communication channels established through cryptographic key exchange.",
    ),

    # ── IDENTITY & AUTHENTICATION ─────────────────────────────────
    ConceptQuestion(
        id="identity_01",
        topic="Identity & Authentication",
        difficulty=0,
        question="Single Sign-On (SSO) benefits users by:",
        options=[
            "Allowing one login to access multiple services",
            "Requiring a different password for each service",
            "Eliminating the need for passwords entirely",
            "Encrypting all network traffic automatically",
        ],
        explanation="SSO lets users authenticate once and access multiple applications without re-entering credentials. This improves usability while centralizing authentication control.",
        game_context="A valid UACC Digital ID functions like an SSO token — it grants access across multiple checkpoints without re-verification at each one.",
    ),
    ConceptQuestion(
        id="identity_02",
        topic="Identity & Authentication",
        difficulty=1,
        question="SAML (Security Assertion Markup Language) is primarily used for:",
        options=[
            "Exchanging authentication and authorization data between parties",
            "Encrypting database records",
            "Managing firewall configurations",
            "Compressing network packets",
        ],
        explanation="SAML enables SSO by exchanging XML-based security assertions between an identity provider (IdP) and service providers (SPs). The IdP authenticates the user and asserts their identity to SPs.",
        game_context="When an entrant presents documents from their faction's authority, it's like a SAML assertion — the faction (IdP) asserts the entrant's identity to you (the SP).",
    ),

    # ── NETWORK SECURITY ──────────────────────────────────────────
    ConceptQuestion(
        id="network_01",
        topic="Network Security",
        difficulty=0,
        question="A firewall's primary function is to:",
        options=[
            "Filter network traffic based on predefined rules",
            "Speed up internet connections",
            "Store backup copies of data",
            "Generate encryption keys",
        ],
        explanation="Firewalls examine network traffic against rules (allow/deny by IP, port, protocol) to control what enters and leaves a network. They're the first line of perimeter defense.",
        game_context="YOU are the human firewall — the Security Directive is your ruleset, and you allow/deny/detain traffic (entrants) based on those rules.",
    ),
    ConceptQuestion(
        id="network_02",
        topic="Network Security",
        difficulty=1,
        question="Zero Trust Architecture is based on the principle of:",
        options=[
            "Never trust, always verify — regardless of network location",
            "Trusting all internal network traffic",
            "Using a single strong password for everything",
            "Blocking all external connections",
        ],
        explanation="Zero Trust eliminates implicit trust based on network location. Every request is authenticated, authorized, and encrypted — whether from inside or outside the network perimeter.",
        game_context="Your checkpoint embodies Zero Trust — even UACC members must present valid credentials. No one gets automatic access based on claimed faction alone.",
    ),
]


# ============================================================================
# QUESTION SELECTION AND TRACKING
# ============================================================================


def get_questions_for_difficulty(difficulty: int) -> List[ConceptQuestion]:
    """Get questions appropriate for the current game difficulty."""
    # Map game difficulty (0-8) to question difficulty (0-3)
    if difficulty <= 1:
        max_q_diff = 0
    elif difficulty <= 3:
        max_q_diff = 1
    elif difficulty <= 5:
        max_q_diff = 2
    else:
        max_q_diff = 3

    return [q for q in QUESTION_BANK if q.difficulty <= max_q_diff]


def select_question(
    difficulty: int,
    seen_ids: Set[str],
) -> Optional[ConceptQuestion]:
    """
    Select a question the player hasn't seen yet, appropriate for their difficulty.

    Args:
        difficulty: Current game difficulty level (0-8)
        seen_ids: Set of question IDs already seen by this player

    Returns:
        A ConceptQuestion, or None if all questions have been seen.
    """
    eligible = get_questions_for_difficulty(difficulty)
    unseen = [q for q in eligible if q.id not in seen_ids]

    if not unseen:
        # All eligible questions seen — open up to all questions
        unseen = [q for q in QUESTION_BANK if q.id not in seen_ids]

    if not unseen:
        return None  # Player has seen every question

    return random.choice(unseen)


def shuffle_options(question: ConceptQuestion) -> tuple:
    """
    Shuffle the options and return (shuffled_options, correct_index).
    The first option in the original list is always the correct answer.

    Returns:
        Tuple of (shuffled_options: List[str], correct_index: int)
    """
    correct = question.options[0]
    shuffled = question.options.copy()
    random.shuffle(shuffled)
    correct_index = shuffled.index(correct)
    return shuffled, correct_index
