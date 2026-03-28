"""
Game session manager for the Papers Please Discord game.
Tracks active player sessions, handles difficulty escalation, and manages game flow.
"""

import asyncio
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .models import Entrant, SecurityDirective, GameState, InspectionResult
from .generator import generate_directive, generate_entrant


# ============================================================================
# DIFFICULTY SETTINGS
# ============================================================================

ENTRANTS_PER_DIFFICULTY = 5  # Escalate difficulty every N correct answers
MAX_DIFFICULTY = 8


# ============================================================================
# PLAYER SESSION
# ============================================================================

@dataclass
class PlayerSession:
    """Tracks an individual player's game session."""
    user_id: int
    game_state: GameState = field(default_factory=GameState)
    current_directive: Optional[SecurityDirective] = None
    current_entrant: Optional[Entrant] = None
    current_result: Optional[InspectionResult] = None
    difficulty: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_action: datetime = field(default_factory=datetime.utcnow)
    daemon_hints_used: int = 0
    total_entrants_seen: int = 0
    correct_streak: int = 0
    best_streak: int = 0

    @property
    def is_active(self) -> bool:
        """Check if the session is still active (not game over)."""
        return not self.game_state.is_game_over

    def advance_difficulty(self) -> bool:
        """
        Check if difficulty should increase based on correct answers.
        Returns True if difficulty was increased.
        """
        if (self.game_state.score > 0 and
            self.game_state.score % ENTRANTS_PER_DIFFICULTY == 0 and
            self.difficulty < MAX_DIFFICULTY):
            self.difficulty += 1
            self.current_directive = None  # Force new directive generation
            return True
        return False

    def generate_next_round(self) -> None:
        """Generate a new directive (if needed) and a new entrant."""
        if self.current_directive is None:
            self.current_directive = generate_directive(self.difficulty)

        self.current_entrant, self.current_result = generate_entrant(self.current_directive, self.difficulty)
        self.total_entrants_seen += 1
        self.last_action = datetime.utcnow()

    def process_decision(self, player_decision: str) -> tuple:
        """
        Process the player's decision and return (is_correct, result).

        Args:
            player_decision: "allow", "deny", or "detain"

        Returns:
            Tuple of (is_correct: bool, correct_result: InspectionResult, difficulty_increased: bool)
        """
        if self.current_result is None:
            raise ValueError("No active entrant to judge")

        correct_decision = self.current_result.decision
        is_correct = player_decision == correct_decision

        self.game_state.record_decision(is_correct)

        if is_correct:
            self.correct_streak += 1
            self.best_streak = max(self.best_streak, self.correct_streak)
        else:
            self.correct_streak = 0

        difficulty_increased = False
        if is_correct:
            difficulty_increased = self.advance_difficulty()

        self.last_action = datetime.utcnow()
        result = self.current_result

        # Clear current entrant so next round can generate
        self.current_entrant = None
        self.current_result = None

        return (is_correct, result, difficulty_increased)

    def get_score_summary(self) -> str:
        """Return a formatted score summary."""
        gs = self.game_state
        elapsed = datetime.utcnow() - self.started_at
        minutes = int(elapsed.total_seconds() // 60)

        accuracy = (gs.score / gs.entrants_processed * 100) if gs.entrants_processed > 0 else 0

        lines = [
            f"**Score:** {gs.score} / {gs.entrants_processed}",
            f"**Accuracy:** {accuracy:.0f}%",
            f"**Strikes:** {'🔴' * gs.strikes}{'⚫' * (gs.max_strikes - gs.strikes)}",
            f"**Difficulty:** Level {self.difficulty}",
            f"**Current Streak:** {self.correct_streak}",
            f"**Best Streak:** {self.best_streak}",
            f"**DAEMON Hints Used:** {self.daemon_hints_used}",
            f"**Session Time:** {minutes} min",
        ]
        return "\n".join(lines)

    def get_game_over_summary(self) -> str:
        """Return the final game-over summary."""
        gs = self.game_state
        elapsed = datetime.utcnow() - self.started_at
        minutes = int(elapsed.total_seconds() // 60)
        accuracy = (gs.score / gs.entrants_processed * 100) if gs.entrants_processed > 0 else 0

        # Rating based on performance
        if accuracy >= 90 and self.difficulty >= 5:
            rating = "LEGENDARY — Master Checkpoint Agent"
        elif accuracy >= 80 and self.difficulty >= 4:
            rating = "ELITE — Senior Security Analyst"
        elif accuracy >= 70 and self.difficulty >= 3:
            rating = "PROFICIENT — Certified Agent"
        elif accuracy >= 60:
            rating = "ADEQUATE — Probationary Agent"
        else:
            rating = "TERMINATED — Security Clearance Revoked"

        return (
            f"```ansi\n"
            f"\033[0;31m╔══════════════════════════════════════════════════════════════╗\n"
            f"║                    GAME OVER — DEBRIEF                       ║\n"
            f"╚══════════════════════════════════════════════════════════════╝\033[0m\n"
            f"```\n"
            f"**Final Score:** {gs.score} / {gs.entrants_processed}\n"
            f"**Accuracy:** {accuracy:.0f}%\n"
            f"**Max Difficulty Reached:** Level {self.difficulty}\n"
            f"**Best Streak:** {self.best_streak}\n"
            f"**DAEMON Hints Used:** {self.daemon_hints_used}\n"
            f"**Session Duration:** {minutes} minutes\n\n"
            f"**Rating:** {rating}"
        )


# ============================================================================
# SESSION MANAGER (Singleton-ish)
# ============================================================================

class SessionManager:
    """Manages all active game sessions across Discord users."""

    def __init__(self):
        self._sessions: Dict[int, PlayerSession] = {}

    def get_session(self, user_id: int) -> Optional[PlayerSession]:
        """Get an active session for a user, if one exists."""
        session = self._sessions.get(user_id)
        if session and session.is_active:
            return session
        return None

    def create_session(self, user_id: int) -> PlayerSession:
        """Create a new game session for a user (overwrites any existing session)."""
        session = PlayerSession(user_id=user_id)
        self._sessions[user_id] = session
        return session

    def end_session(self, user_id: int) -> Optional[PlayerSession]:
        """End and remove a session, returning it for final summary."""
        return self._sessions.pop(user_id, None)

    def has_active_session(self, user_id: int) -> bool:
        """Check if a user has an active game session."""
        session = self._sessions.get(user_id)
        return session is not None and session.is_active

    @property
    def active_count(self) -> int:
        """Number of currently active sessions."""
        return sum(1 for s in self._sessions.values() if s.is_active)


# Module-level singleton
game_sessions = SessionManager()
