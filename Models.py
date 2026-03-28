"""
Data models for the cyberpunk Papers Please game.
Includes documents, entrants, security directives, and game state.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from datetime import datetime

from . import theme


# ============================================================================
# DOCUMENT MODEL
# ============================================================================

@dataclass
class Document:
    """Represents a digital document/credential."""
    doc_type: str
    fields: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate that doc_type is recognized."""
        if self.doc_type not in theme.DOCUMENT_TYPES:
            raise ValueError(f"Unknown document type: {self.doc_type}")

    def __str__(self) -> str:
        """Format document as readable text (similar to Papers Please display)."""
        doc_name = theme.DOCUMENT_TYPES[self.doc_type]
        lines = [f"--- {doc_name} ---"]

        # Display fields in defined order
        if self.doc_type in theme.DOCUMENT_FIELDS:
            for field_name in theme.DOCUMENT_FIELDS[self.doc_type]:
                if field_name in self.fields:
                    lines.append(f"{field_name}: {self.fields[field_name]}")

        return "\n".join(lines)

    @property
    def is_expired(self) -> bool:
        """Check if document has an EXP field and is expired."""
        if "EXP" not in self.fields:
            return False
        try:
            exp_date = datetime.strptime(self.fields["EXP"], "%Y-%m-%d")
            return datetime.now() > exp_date
        except (ValueError, KeyError):
            return False

    @property
    def faction(self) -> Optional[str]:
        """Get faction from this document, if present."""
        return self.fields.get("FACTION")

    @property
    def handle(self) -> Optional[str]:
        """Get handle from this document, if present."""
        return self.fields.get("HANDLE")


# ============================================================================
# ENTRANT MODEL
# ============================================================================

@dataclass
class Entrant:
    """Represents a person seeking access."""
    documents: List[Document] = field(default_factory=list)
    true_faction: str = field(default="UACC")

    def __post_init__(self):
        """Validate faction is recognized."""
        if self.true_faction not in theme.FACTIONS:
            raise ValueError(f"Unknown faction: {self.true_faction}")

    def get_documents_by_type(self, doc_type: str) -> List[Document]:
        """Get all documents of a specific type."""
        return [doc for doc in self.documents if doc.doc_type == doc_type]

    def get_all_handles(self) -> Set[str]:
        """Get all unique handles across all documents."""
        handles = set()
        for doc in self.documents:
            if doc.handle:
                handles.add(doc.handle)
        return handles

    def get_all_factions(self) -> Set[str]:
        """Get all unique factions claimed across all documents."""
        factions = set()
        for doc in self.documents:
            if doc.faction:
                factions.add(doc.faction)
        return factions

    @property
    def primary_handle(self) -> Optional[str]:
        """Return the handle from the primary document (usually digital_id)."""
        digital_ids = self.get_documents_by_type("digital_id")
        if digital_ids:
            return digital_ids[0].handle
        # Fallback to any handle from any document
        for doc in self.documents:
            if doc.handle:
                return doc.handle
        return None

    @property
    def primary_faction(self) -> Optional[str]:
        """Return the faction from the primary document (usually digital_id)."""
        digital_ids = self.get_documents_by_type("digital_id")
        if digital_ids:
            return digital_ids[0].faction
        # Fallback to any faction from any document
        for doc in self.documents:
            if doc.faction:
                return doc.faction
        return None


# ============================================================================
# SECURITY DIRECTIVE MODEL
# ============================================================================

@dataclass
class SecurityDirective:
    """Represents a security directive (replaces Bulletin from original game)."""
    raw_text: str
    denied_factions: Set[str] = field(default_factory=set)
    required_docs_by_faction: Dict[str, Set[str]] = field(default_factory=dict)
    required_docs_for_operators: Set[str] = field(default_factory=set)
    required_scans_by_faction: Dict[str, Set[str]] = field(default_factory=dict)
    required_scans_for_operators: Set[str] = field(default_factory=set)
    wanted_handle: Optional[str] = None
    allowed_factions: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Post-initialization validation."""
        # Convert to sets if needed
        if isinstance(self.denied_factions, list):
            self.denied_factions = set(self.denied_factions)
        if isinstance(self.wanted_handle, str):
            self.wanted_handle = self.wanted_handle

    def __str__(self) -> str:
        """Format directive for display."""
        lines = [f"=== {theme.DIRECTIVE_PREFIX} ==="]
        lines.append(self.raw_text)
        return "\n".join(lines)

    def is_faction_denied(self, faction: str) -> bool:
        """Check if a faction is denied entry."""
        return faction in self.denied_factions

    def is_faction_allowed(self, faction: str) -> bool:
        """Check if a faction is explicitly allowed."""
        if self.allowed_factions:
            return faction in self.allowed_factions
        # If no explicit allow list, allow by default (unless denied)
        return not self.is_faction_denied(faction)

    def get_required_docs(self, faction: str, is_operator: bool = False) -> Set[str]:
        """Get required documents for a given faction."""
        docs = set()

        # Add faction-specific requirements
        if faction in self.required_docs_by_faction:
            docs.update(self.required_docs_by_faction[faction])

        # Add operator requirements if applicable
        if is_operator:
            docs.update(self.required_docs_for_operators)

        return docs

    def get_required_scans(self, faction: str, is_operator: bool = False) -> Set[str]:
        """Get required security scans for a given faction."""
        scans = set()

        # Add faction-specific requirements
        if faction in self.required_scans_by_faction:
            scans.update(self.required_scans_by_faction[faction])

        # Add operator requirements if applicable
        if is_operator:
            scans.update(self.required_scans_for_operators)

        return scans


# ============================================================================
# GAME STATE MODEL
# ============================================================================

@dataclass
class GameState:
    """Tracks the overall game state and score."""
    score: int = 0
    strikes: int = 0
    max_strikes: int = 3
    entrants_processed: int = 0
    current_directive: Optional[SecurityDirective] = None
    difficulty_level: int = 1
    is_game_over: bool = False

    def record_decision(self, correct: bool) -> None:
        """
        Record the result of an inspection decision.

        Args:
            correct: True if the decision was correct, False if incorrect.
        """
        if correct:
            self.score += 1
        else:
            self.strikes += 1

        self.entrants_processed += 1

        # Check if game is over
        if self.strikes >= self.max_strikes:
            self.is_game_over = True

    def reset(self) -> None:
        """Reset game state to initial values."""
        self.score = 0
        self.strikes = 0
        self.entrants_processed = 0
        self.is_game_over = False


# ============================================================================
# INSPECTION RESULT MODEL
# ============================================================================

@dataclass
class InspectionResult:
    """Represents the result of inspecting an entrant."""
    decision: str  # "allow", "deny", or "detain"
    reason: str
    is_correct: bool

    def __post_init__(self):
        """Validate decision type."""
        valid_decisions = {"allow", "deny", "detain"}
        if self.decision not in valid_decisions:
            raise ValueError(f"Invalid decision: {self.decision}. Must be one of {valid_decisions}")

    def __str__(self) -> str:
        """Format result for display."""
        decision_display = self.decision.upper()
        return f"[{decision_display}] {self.reason}"
