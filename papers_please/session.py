"""
Game session manager for the Papers Please Discord game.
Tracks active player sessions, handles difficulty escalation, manages game flow,
and persists game statistics to SQLite for instructor reporting.
"""

import sqlite3
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, field
from datetime import datetime

from .models import Entrant, SecurityDirective, GameState, InspectionResult
from .generator import generate_directive, generate_entrant


# ============================================================================
# DIFFICULTY SETTINGS
# ============================================================================

ENTRANTS_PER_DIFFICULTY = 5  # Escalate difficulty every N correct answers
MAX_DIFFICULTY = 8

# Milestones: (threshold_type, threshold_value, milestone_name, emoji)
MILESTONES = [
    ("score", 5, "First Five", "🔰"),
    ("score", 10, "Double Digits", "⭐"),
    ("score", 25, "Quarter Century", "🌟"),
    ("score", 50, "Half Century", "💫"),
    ("score", 100, "Centurion", "🏆"),
    ("streak", 5, "Hot Streak", "🔥"),
    ("streak", 10, "Unstoppable", "⚡"),
    ("streak", 20, "Legendary Run", "👑"),
    ("difficulty", 3, "Cleared Level 3", "🛡️"),
    ("difficulty", 5, "Cleared Level 5", "⚔️"),
    ("difficulty", 8, "Max Security", "🏅"),
    ("questions_correct", 5, "Scholar", "📚"),
    ("questions_correct", 15, "Professor", "🎓"),
    ("questions_correct", 25, "Mastermind", "🧠"),
]


# ============================================================================
# PLAYER SESSION
# ============================================================================

@dataclass
class PlayerSession:
    """Tracks an individual player's game session."""
    user_id: int
    rit_username: str = ""
    game_state: GameState = field(default_factory=GameState)
    current_directive: Optional[SecurityDirective] = None
    current_entrant: Optional[Entrant] = None
    current_result: Optional[InspectionResult] = None
    difficulty: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_action: datetime = field(default_factory=datetime.utcnow)
    cerberus_hints_used: int = 0
    total_entrants_seen: int = 0
    correct_streak: int = 0
    best_streak: int = 0
    # Concept question tracking
    questions_asked: int = 0
    questions_correct: int = 0
    questions_seen_ids: Set[str] = field(default_factory=set)
    question_topic_results: Dict[str, Dict] = field(default_factory=dict)
    # Milestone tracking
    milestones_earned: List[str] = field(default_factory=list)
    # Pinned directive message ID (for unpinning later)
    pinned_directive_msg_id: Optional[int] = None

    @property
    def is_active(self) -> bool:
        """Check if the session is still active (not game over)."""
        return not self.game_state.is_game_over

    @property
    def elapsed_minutes(self) -> int:
        """Total minutes elapsed since session start."""
        return int((datetime.utcnow() - self.started_at).total_seconds() // 60)

    @property
    def accuracy(self) -> float:
        gs = self.game_state
        return (gs.score / gs.entrants_processed * 100) if gs.entrants_processed > 0 else 0.0

    def check_milestones(self) -> List[tuple]:
        """Check for newly earned milestones. Returns list of (name, emoji) tuples."""
        newly_earned = []
        for m_type, threshold, name, emoji in MILESTONES:
            if name in self.milestones_earned:
                continue
            earned = False
            if m_type == "score" and self.game_state.score >= threshold:
                earned = True
            elif m_type == "streak" and self.correct_streak >= threshold:
                earned = True
            elif m_type == "difficulty" and self.difficulty >= threshold:
                earned = True
            elif m_type == "questions_correct" and self.questions_correct >= threshold:
                earned = True
            if earned:
                self.milestones_earned.append(name)
                newly_earned.append((name, emoji))
        return newly_earned

    def advance_difficulty(self) -> bool:
        """Check if difficulty should increase. Returns True if increased."""
        if (self.game_state.score > 0 and
            self.game_state.score % ENTRANTS_PER_DIFFICULTY == 0 and
            self.difficulty < MAX_DIFFICULTY):
            self.difficulty += 1
            self.current_directive = None
            return True
        return False

    def generate_next_round(self) -> None:
        """Generate a new directive (if needed) and a new entrant."""
        if self.current_directive is None:
            self.current_directive = generate_directive(self.difficulty)
        self.current_entrant, self.current_result = generate_entrant(
            self.current_directive, self.difficulty
        )
        self.total_entrants_seen += 1
        self.last_action = datetime.utcnow()

    def process_decision(self, player_decision: str) -> tuple:
        """
        Process the player's decision.

        Returns:
            (is_correct, correct_result, difficulty_increased, new_milestones)
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

        new_milestones = self.check_milestones()
        self.last_action = datetime.utcnow()
        result = self.current_result

        self.current_entrant = None
        self.current_result = None
        return (is_correct, result, difficulty_increased, new_milestones)

    def record_question_result(self, topic: str, correct: bool) -> None:
        """Record the result of a concept review question."""
        self.questions_asked += 1
        if correct:
            self.questions_correct += 1
        if topic not in self.question_topic_results:
            self.question_topic_results[topic] = {"correct": 0, "total": 0}
        self.question_topic_results[topic]["total"] += 1
        if correct:
            self.question_topic_results[topic]["correct"] += 1

    def should_ask_question(self) -> bool:
        """Determine if it's time for a concept review question (every 3 entrants)."""
        return (
            self.total_entrants_seen > 0
            and self.total_entrants_seen % 3 == 0
            and not self.game_state.is_game_over
        )

    def get_score_summary(self) -> str:
        """Return a formatted score summary."""
        gs = self.game_state
        q_acc = (
            f"{self.questions_correct}/{self.questions_asked}"
            if self.questions_asked > 0 else "—"
        )
        lines = [
            f"**Score:** {gs.score} / {gs.entrants_processed}",
            f"**Accuracy:** {self.accuracy:.0f}%",
            f"**Strikes:** {'🔴' * gs.strikes}{'⚫' * (gs.max_strikes - gs.strikes)}",
            f"**Difficulty:** Level {self.difficulty}",
            f"**Current Streak:** {self.correct_streak}",
            f"**Best Streak:** {self.best_streak}",
            f"**CERBERUS Hints:** {self.cerberus_hints_used}",
            f"**Concept Questions:** {q_acc}",
            f"**Milestones:** {len(self.milestones_earned)}",
            f"**Session Time:** {self.elapsed_minutes} min",
        ]
        return "\n".join(lines)

    def get_game_over_summary(self) -> str:
        """Return the final game-over summary."""
        gs = self.game_state
        q_acc = (
            f"{self.questions_correct}/{self.questions_asked}"
            if self.questions_asked > 0 else "N/A"
        )

        if self.accuracy >= 90 and self.difficulty >= 5:
            rating = "⚜️ LEGENDARY — Master Checkpoint Agent"
        elif self.accuracy >= 80 and self.difficulty >= 4:
            rating = "🏆 ELITE — Senior Security Analyst"
        elif self.accuracy >= 70 and self.difficulty >= 3:
            rating = "🛡️ PROFICIENT — Certified Agent"
        elif self.accuracy >= 60:
            rating = "📋 ADEQUATE — Probationary Agent"
        else:
            rating = "💀 TERMINATED — Security Clearance Revoked"

        milestone_str = ", ".join(
            f"{e} {n}" for n, e in [
                (m, next((em for _, _, nm, em in MILESTONES if nm == m), ""))
                for m in self.milestones_earned
            ]
        ) or "None"

        return (
            f"```ansi\n"
            f"\033[0;31m╔══════════════════════════════════════════════════════════════╗\n"
            f"║                    GAME OVER — DEBRIEF                       ║\n"
            f"╚══════════════════════════════════════════════════════════════╝\033[0m\n"
            f"```\n"
            f"**Final Score:** {gs.score} / {gs.entrants_processed}\n"
            f"**Accuracy:** {self.accuracy:.0f}%\n"
            f"**Max Difficulty:** Level {self.difficulty}\n"
            f"**Best Streak:** {self.best_streak}\n"
            f"**CERBERUS Hints:** {self.cerberus_hints_used}\n"
            f"**Concept Questions:** {q_acc}\n"
            f"**Milestones:** {milestone_str}\n"
            f"**Session Duration:** {self.elapsed_minutes} min\n\n"
            f"**Rating:** {rating}"
        )


# ============================================================================
# GAME DATABASE — Persists session results for instructor reporting
# ============================================================================

class GameDatabase:
    """SQLite persistence for game sessions and concept question performance."""

    def __init__(self, conn: sqlite3.Connection):
        """Use the bot's existing DB connection."""
        self.conn = conn
        self.init_game_schema()

    def init_game_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                rit_username TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                score INTEGER NOT NULL,
                entrants_processed INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                max_difficulty INTEGER NOT NULL,
                best_streak INTEGER NOT NULL,
                cerberus_hints INTEGER NOT NULL,
                questions_asked INTEGER NOT NULL,
                questions_correct INTEGER NOT NULL,
                milestones TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_question_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                rit_username TEXT NOT NULL,
                session_id INTEGER,
                question_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES game_sessions(id)
            )
        """)
        self.conn.commit()

    def save_session(self, session: PlayerSession) -> int:
        """Save a completed game session. Returns the new session row ID."""
        gs = session.game_state
        elapsed = (datetime.utcnow() - session.started_at).total_seconds()
        milestones_str = ",".join(session.milestones_earned)
        cur = self.conn.execute(
            """
            INSERT INTO game_sessions
            (discord_id, rit_username, started_at, ended_at, score, entrants_processed,
             accuracy, max_difficulty, best_streak, cerberus_hints,
             questions_asked, questions_correct, milestones, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(session.user_id),
                session.rit_username,
                session.started_at.isoformat(),
                datetime.utcnow().isoformat(),
                gs.score,
                gs.entrants_processed,
                round(session.accuracy, 1),
                session.difficulty,
                session.best_streak,
                session.cerberus_hints_used,
                session.questions_asked,
                session.questions_correct,
                milestones_str,
                int(elapsed),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def save_question_result(
        self, discord_id: int, rit_username: str, session_id: Optional[int],
        question_id: str, topic: str, correct: bool
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO game_question_results
            (discord_id, rit_username, session_id, question_id, topic, correct, answered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(discord_id), rit_username, session_id,
                question_id, topic, 1 if correct else 0,
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    # ── Reporting queries ────────────────────────────────────────

    def get_player_stats(self) -> List[sqlite3.Row]:
        """Aggregate stats per player for instructor report."""
        return self.conn.execute("""
            SELECT
                rit_username,
                discord_id,
                COUNT(*) as total_sessions,
                SUM(duration_seconds) as total_play_seconds,
                MAX(score) as best_score,
                MAX(max_difficulty) as max_difficulty_reached,
                MAX(best_streak) as overall_best_streak,
                ROUND(AVG(accuracy), 1) as avg_accuracy,
                SUM(questions_asked) as total_questions,
                SUM(questions_correct) as total_q_correct,
                MAX(milestones) as latest_milestones
            FROM game_sessions
            GROUP BY rit_username
            ORDER BY MAX(score) DESC
        """).fetchall()

    def get_topic_performance(self) -> Dict[str, Dict]:
        """Aggregate concept question performance by topic."""
        rows = self.conn.execute("""
            SELECT topic, SUM(correct) as correct, COUNT(*) as total
            FROM game_question_results
            GROUP BY topic
            ORDER BY topic
        """).fetchall()
        return {row["topic"]: {"correct": row["correct"], "total": row["total"]} for row in rows}

    def get_daily_session_counts(self, days: int = 14) -> Dict[str, int]:
        """Session counts per day for the last N days."""
        rows = self.conn.execute("""
            SELECT DATE(started_at) as day, COUNT(*) as cnt
            FROM game_sessions
            WHERE started_at >= DATE('now', ?)
            GROUP BY DATE(started_at)
            ORDER BY day
        """, (f"-{days} days",)).fetchall()
        return {row["day"]: row["cnt"] for row in rows}

    def get_player_milestones(self) -> List[sqlite3.Row]:
        """All milestones earned, grouped by player."""
        return self.conn.execute("""
            SELECT rit_username, discord_id, milestones,
                   MAX(max_difficulty) as max_diff,
                   MAX(score) as top_score
            FROM game_sessions
            WHERE milestones != ''
            GROUP BY rit_username
            ORDER BY top_score DESC
        """).fetchall()


# ============================================================================
# SESSION MANAGER
# ============================================================================

class SessionManager:
    """Manages all active game sessions across Discord users."""

    def __init__(self):
        self._sessions: Dict[int, PlayerSession] = {}
        self.db: Optional[GameDatabase] = None

    def init_db(self, conn: sqlite3.Connection) -> None:
        """Initialize game database using the bot's existing connection."""
        self.db = GameDatabase(conn)

    def get_session(self, user_id: int) -> Optional[PlayerSession]:
        session = self._sessions.get(user_id)
        if session and session.is_active:
            return session
        return None

    def create_session(self, user_id: int, rit_username: str = "") -> PlayerSession:
        session = PlayerSession(user_id=user_id, rit_username=rit_username)
        self._sessions[user_id] = session
        return session

    def end_session(self, user_id: int) -> Optional[PlayerSession]:
        """End a session, save to DB, and return it for final summary."""
        session = self._sessions.pop(user_id, None)
        if session and self.db:
            try:
                self.db.save_session(session)
            except Exception as exc:
                print(f"[GameDB] Error saving session for {user_id}: {exc}")
        return session

    def has_active_session(self, user_id: int) -> bool:
        session = self._sessions.get(user_id)
        return session is not None and session.is_active

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.is_active)


# Module-level singleton
game_sessions = SessionManager()
