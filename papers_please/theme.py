"""
Cyberpunk-themed flavor text, constants, and world-building for Papers Please bot game.
Set in 2032 America during WWIII.
"""

import random
from typing import Tuple

# ============================================================================
# FACTIONS
# ============================================================================

FACTIONS = [
    "UACC",  # United American Cyber Command (HOME)
    "PRC",   # Pacific Rim Coalition
    "ERN",   # European Resistance Network
    "CIH",   # Collective of Independent Hackers
    "CORP",  # Corporate Syndicate
    "NALL",  # Northern Alliance
    "FSU",   # Free States Underground
]

HOME_FACTION = "UACC"

FACTION_DESCRIPTIONS = {
    "UACC": "United American Cyber Command",
    "PRC": "Pacific Rim Coalition",
    "ERN": "European Resistance Network",
    "CIH": "Collective of Independent Hackers",
    "CORP": "Corporate Syndicate",
    "NALL": "Northern Alliance",
    "FSU": "Free States Underground",
}

# ============================================================================
# DOCUMENT TYPES
# ============================================================================

DOCUMENT_TYPES = {
    "digital_id": "Digital Identity Certificate",
    "bio_badge": "Biometric Authentication Badge",
    "access_token": "Network Access Token",
    "clearance_code": "Contractor Clearance Code",
    "asylum_key": "Asylum Encryption Key",
    "diplomatic_cipher": "Diplomatic Cipher Channel",
    "integrity_report": "System Integrity Report",
}

# Document field structures
DOCUMENT_FIELDS = {
    "digital_id": ["ID#", "HANDLE", "FACTION", "DOB", "SEX", "ISSUING_NODE", "EXP"],
    "bio_badge": ["HANDLE", "HEIGHT", "WEIGHT", "FACTION"],
    "access_token": ["ID#", "HANDLE", "FACTION", "PURPOSE", "DURATION", "HEIGHT", "WEIGHT", "EXP"],
    "clearance_code": ["ID#", "HANDLE", "FACTION", "EXP"],
    "asylum_key": ["ID#", "HANDLE", "FACTION", "DOB", "HEIGHT", "WEIGHT", "EXP"],
    "diplomatic_cipher": ["ID#", "HANDLE", "FACTION", "ACCESS", "EXP"],
    "integrity_report": ["ID#", "HANDLE", "SCANS"],
}

# ============================================================================
# SECURITY CHECKS (REPLACES VACCINES)
# ============================================================================

SECURITY_CHECKS = [
    "rootkit_scan",
    "trojan_check",
    "ransomware_sweep",
    "spyware_audit",
    "zero_day_patch",
]

# ============================================================================
# PURPOSE TYPES
# ============================================================================

PURPOSE_TYPES = ["TRANSIT", "OPERATION"]

# ============================================================================
# NAME POOLS
# ============================================================================

FIRST_NAMES = [
    "Alex", "Jordan", "Casey", "Riley", "Morgan",
    "Sam", "Taylor", "Quinn", "Blake", "Avery",
    "Dakota", "River", "Phoenix", "Skylar", "Sage",
    "Nova", "Cipher", "Hex", "Echo", "Volt",
    "Raze", "Pixel", "Sync", "Logic", "Rebus",
    "Shade", "Storm", "Static", "Oracle", "Vex",
]

LAST_NAMES = [
    "Chen", "Rodriguez", "Patel", "Kim", "Johnson",
    "Volkov", "Mueller", "Okafor", "Sato", "Costa",
    "Zhang", "Reeves", "Cross", "Ward", "Drake",
    "Lynch", "Hart", "Stone", "Price", "Shaw",
    "Crane", "Fox", "Wolf", "Frost", "Knight",
    "Vane", "Blaze", "Storm", "Raven", "Sage",
]

HACKER_HANDLES = [
    "Ghost", "Cipher", "Null", "Wraith", "Phantom",
    "Specter", "Venom", "Cryptid", "Mirage", "Glitch",
    "Reaper", "Shadow", "Nexus", "Void", "Rogue",
    "Oracle", "Sentinel", "Chimera", "Pulse", "Ember",
    "Forge", "Hack", "Breach", "Surge", "Shatter",
    "Whisper", "Static", "Splice", "Daemon", "Rift",
]

# ============================================================================
# ISSUING NODES (LOCATIONS)
# ============================================================================

ISSUING_NODES = [
    "Node-7 East Grid",
    "Sector-12 Hub",
    "Gateway Alpha",
    "Vault-Nine Access",
    "Tower-5 Central",
    "Core Station Beta",
    "Nexus-1 North",
    "Boundary Station Omega",
    "Haven Checkpoint Gamma",
    "Fortress Delta",
]

# ============================================================================
# FLAVOR TEXT & MESSAGES
# ============================================================================

HOME_SUCCESS = "Access granted. Loyalty to UACC noted."

FOREIGN_SUCCESS = "Access granted. You are being monitored."

GAME_INTRO = (
    "You are a Digital Checkpoint Agent stationed at the UACC Network Access Control Point in 2032. "
    "America is at war. Foreign operatives and criminals seek entry. "
    "Your duty is to verify digital credentials and determine who enters our secured networks. "
    "Process entrants carefully. One mistake compromises national security."
)

GAME_OVER = (
    "You have failed in your duties as a Digital Checkpoint Agent. "
    "Your security clearance has been revoked."
)

DIRECTIVE_PREFIX = "SECURITY DIRECTIVE"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def random_name() -> Tuple[str, str]:
    """Return a random (first_name, last_name) tuple."""
    return (random.choice(FIRST_NAMES), random.choice(LAST_NAMES))


def random_handle() -> str:
    """Return a random hacker handle."""
    return random.choice(HACKER_HANDLES)
