import json
import os
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import aiohttp
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
import discord
import pandas as pd
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from catchup_handler import CatchupHandler
from papers_please.session import game_sessions
from papers_please.views import (
    build_intro_embed,
    build_directive_embed,
    build_entrant_embed,
    build_cerberus_embed,
    build_game_over_embed,
    GameActionView,
    QuitConfirmView,
    unpin_bot_messages,
)
from papers_please.assistant import CERBERUS
from papers_please.charts import (
    generate_accuracy_chart,
    generate_topic_performance_chart,
    generate_difficulty_progression_chart,
    generate_session_activity_chart,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID_RAW = os.getenv("DISCORD_GUILD_ID", "").strip()
GUILD_ID = int(GUILD_ID_RAW) if GUILD_ID_RAW else None
INSTRUCTOR_CHANNEL_NAME = os.getenv("INSTRUCTOR_CHANNEL_NAME", "bot-briefs").strip()
DADJOKE_CHANNEL_NAME = os.getenv("DADJOKE_CHANNEL_NAME", "extracurricular").strip()
GENERAL_CHANNEL_NAME = os.getenv("GENERAL_CHANNEL_NAME", "general").strip()
DEADLINES_CHANNEL_NAME = os.getenv("DEADLINES_CHANNEL_NAME", "deadlines").strip()
EXCEL_FILE = os.getenv("EXCEL_FILE", "Teams-WireFrames.xlsx").strip()
DATABASE_FILE = os.getenv("DATABASE_FILE", "peer_reviews.db").strip()
REPORT_TIMEZONE = os.getenv("REPORT_TIMEZONE", "America/New_York").strip()
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "18"))
DAILY_REPORT_MINUTE = int(os.getenv("DAILY_REPORT_MINUTE", "0"))
NUDGE_HOUR = int(os.getenv("NUDGE_HOUR", "8"))
NUDGE_MINUTE = int(os.getenv("NUDGE_MINUTE", "0"))
MAX_REVIEWS_PER_REVIEWER = 3

if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment.")
if not os.path.exists(EXCEL_FILE):
    raise RuntimeError(f"Workbook not found: {EXCEL_FILE}")

GUILD_OBJECT = discord.Object(id=GUILD_ID) if GUILD_ID else None
REPORT_TZ = ZoneInfo(REPORT_TIMEZONE)
REPORT_TIME = time(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE, tzinfo=REPORT_TZ)
RECOMMENDATIONS_TIME = time(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE + 1, tzinfo=REPORT_TZ)
NUDGE_TIME = time(hour=NUDGE_HOUR, minute=NUDGE_MINUTE, tzinfo=REPORT_TZ)

# ---------------------------------------------------------------------------
# Office-hours configuration
# ---------------------------------------------------------------------------
# Loaded from the OFFICE_HOURS_JSON env-var (a JSON string) **or** from a
# default that matches the Spring 2026 syllabus.  Each entry is:
#   { "name", "role", "email", "location", "zoom" (optional),
#     "hours": [ {"days": [0-6 Mon=0], "start": "HH:MM", "end": "HH:MM"} ] }
# Days follow Python's weekday(): Monday=0 … Sunday=6.

_DEFAULT_OFFICE_HOURS: List[dict] = [
    {
        "name": "Justin Pelletier",
        "role": "Instructor",
        "email": "jxpics@rit.edu",
        "location": "CYB-3763",
        "zoom": "https://rit.zoom.us/j/99911135440?from=addon",
        "hours": [
            {"days": [1, 3], "start": "15:30", "end": "16:30"},  # Tu/Th 3:30-4:30 PM
        ],
    },
    {
        "name": "Matthew Wright",
        "role": "Instructor",
        "email": "matthew.wright@rit.edu",
        "location": "CYB-1781",
        "zoom": "https://rit.zoom.us/my/mkwics?pwd=dUVGUFFONTR2aWN3eUlvQlhCTGFZdz09",
        "hours": [
            {"days": [0, 2], "start": "14:00", "end": "15:00"},  # M/W 2:00-3:00 PM
        ],
    },
    {
        "name": "Sid Dongre",
        "role": "TA",
        "email": "sd4767@rit.edu",
        "location": "CYB-2791",
        "zoom": "https://rit.zoom.us/my/sd4767?pwd=NWJTWHZiQWVjSXpzV1dPelJ0bUJmUT09",
        "hours": [
            {"days": [1], "start": "13:00", "end": "15:00"},  # Tu 1:00-3:00 PM
        ],
    },
]

_raw_oh = os.getenv("OFFICE_HOURS_JSON", "").strip()
OFFICE_HOURS_DATA: List[dict] = json.loads(_raw_oh) if _raw_oh else _DEFAULT_OFFICE_HOURS


@dataclass
class _OfficeWindow:
    """One contiguous block of office hours for a staff member."""
    day: int        # Monday=0
    start: time
    end: time


@dataclass
class StaffSchedule:
    name: str
    role: str
    email: str
    location: str
    zoom: Optional[str]
    windows: List[_OfficeWindow] = field(default_factory=list)


def _parse_office_hours(data: List[dict]) -> List[StaffSchedule]:
    """Convert raw JSON/dict list into typed StaffSchedule objects."""
    schedules: List[StaffSchedule] = []
    for entry in data:
        windows: List[_OfficeWindow] = []
        for block in entry.get("hours", []):
            start_h, start_m = (int(x) for x in block["start"].split(":"))
            end_h, end_m = (int(x) for x in block["end"].split(":"))
            for day in block["days"]:
                windows.append(
                    _OfficeWindow(
                        day=day,
                        start=time(start_h, start_m),
                        end=time(end_h, end_m),
                    )
                )
        schedules.append(
            StaffSchedule(
                name=entry["name"],
                role=entry["role"],
                email=entry["email"],
                location=entry["location"],
                zoom=entry.get("zoom"),
                windows=windows,
            )
        )
    return schedules


STAFF_SCHEDULES: List[StaffSchedule] = _parse_office_hours(OFFICE_HOURS_DATA)

_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _is_available_now(staff: StaffSchedule, now: datetime) -> Optional[_OfficeWindow]:
    """Return the matching window if *staff* is holding office hours at *now*, else None."""
    current_day = now.weekday()
    current_time = now.time()
    for w in staff.windows:
        if w.day == current_day and w.start <= current_time < w.end:
            return w
    return None


def _next_window(staff: StaffSchedule, now: datetime) -> Optional[Tuple[datetime, _OfficeWindow]]:
    """Return (start_datetime, window) for the next upcoming office-hours block."""
    if not staff.windows:
        return None
    best: Optional[Tuple[datetime, _OfficeWindow]] = None
    for w in staff.windows:
        # How many days until this window's weekday?
        days_ahead = (w.day - now.weekday()) % 7
        candidate_date = (now + timedelta(days=days_ahead)).date()
        candidate_dt = datetime.combine(candidate_date, w.start, tzinfo=now.tzinfo)
        # If it's today but the window already ended, jump to next week
        if candidate_dt <= now:
            candidate_date = (now + timedelta(days=days_ahead + 7)).date()
            candidate_dt = datetime.combine(candidate_date, w.start, tzinfo=now.tzinfo)
        if best is None or candidate_dt < best[0]:
            best = (candidate_dt, w)
    return best


def build_office_hours_embed(now: datetime) -> discord.Embed:
    """Create a rich embed showing who is available and upcoming sessions."""
    embed = discord.Embed(
        title="Office Hours",
        color=discord.Color.blue(),
        timestamp=now,
    )

    available_now: List[str] = []
    # Each entry is (next_start_datetime, formatted_text) so we can sort by date.
    upcoming_with_dt: List[Tuple[datetime, str]] = []

    for staff in STAFF_SCHEDULES:
        active_window = _is_available_now(staff, now)
        if active_window:
            loc = staff.location
            if staff.zoom:
                loc += f" / [Zoom]({staff.zoom})"
            ends = active_window.end.strftime("%-I:%M %p")
            available_now.append(
                f"**{staff.name}** ({staff.role})\n"
                f"Until {ends} — {loc}\n"
                f"{staff.email}"
            )
        else:
            nxt = _next_window(staff, now)
            if nxt:
                nxt_dt, nxt_w = nxt
                day_label = _DAY_ABBR[nxt_w.day]
                start_str = nxt_w.start.strftime("%-I:%M %p")
                end_str = nxt_w.end.strftime("%-I:%M %p")
                loc = staff.location
                if staff.zoom:
                    loc += f" / [Zoom]({staff.zoom})"
                upcoming_with_dt.append((
                    nxt_dt,
                    f"**{staff.name}** ({staff.role})\n"
                    f"{day_label} {start_str}–{end_str} — {loc}\n"
                    f"{staff.email}",
                ))

    # Sort by soonest session first.
    upcoming_with_dt.sort(key=lambda entry: entry[0])
    upcoming = [text for _dt, text in upcoming_with_dt]

    if available_now:
        embed.add_field(
            name="Available Now",
            value="\n\n".join(available_now),
            inline=False,
        )
    else:
        embed.add_field(
            name="Available Now",
            value="No one is holding office hours right now.",
            inline=False,
        )

    if upcoming:
        embed.add_field(
            name="Coming Up Next",
            value="\n\n".join(upcoming),
            inline=False,
        )

    # Full weekly schedule summary
    schedule_lines: List[str] = []
    for staff in STAFF_SCHEDULES:
        day_ranges: List[str] = []
        for block in sorted(staff.windows, key=lambda w: (w.day, w.start)):
            day_ranges.append(
                f"{_DAY_ABBR[block.day]} {block.start.strftime('%-I:%M')}"
                f"–{block.end.strftime('%-I:%M %p')}"
            )
        schedule_lines.append(f"**{staff.name}** — {', '.join(day_ranges)}")

    embed.add_field(
        name="Full Weekly Schedule",
        value="\n".join(schedule_lines),
        inline=False,
    )

    embed.set_footer(text="All times Eastern (ET)")
    return embed


# ---------------------------------------------------------------------------
# Course schedule / deadline configuration
# ---------------------------------------------------------------------------
# Loaded from COURSE_SCHEDULE_JSON env-var **or** from a default that matches
# the Spring 2026 syllabus.  Each entry is:
#   { "date": "YYYY-MM-DD", "label": "short description", "category": "..." }
# Categories help colour-code the embed: assignment, exam, project, quiz, peer_eval

_DEFAULT_COURSE_SCHEDULE: List[dict] = [
    # Week 1
    {"date": "2026-01-21", "label": "Topic Area selection", "category": "project"},
    # Week 2
    {"date": "2026-01-28", "label": "Source Summary 1 (SS1)", "category": "project"},
    {"date": "2026-02-04", "label": "Assignment 1", "category": "assignment"},
    # Week 3
    {"date": "2026-02-04", "label": "Source Summary 2 (SS2)", "category": "project"},
    # Week 4
    {"date": "2026-02-11", "label": "Source Summary 3 (SS3)", "category": "project"},
    {"date": "2026-02-18", "label": "Assignment 2", "category": "assignment"},
    # Week 5
    {"date": "2026-02-18", "label": "Source Summary 4 (SS4)", "category": "project"},
    # Week 6
    {"date": "2026-02-25", "label": "Wireframe & Video", "category": "project"},
    # Week 7  (Peer Eval 1)
    {"date": "2026-02-27", "label": "Peer Evaluation 1", "category": "peer_eval"},
    # Week 8
    {"date": "2026-03-03", "label": "Exam 1", "category": "exam"},
    {"date": "2026-03-18", "label": "Source Summary 5 (SS5)", "category": "project"},
    # Week 9 — Spring Break (no deadlines)
    # Week 10
    {"date": "2026-03-25", "label": "Source Summary 6 (SS6)", "category": "project"},
    {"date": "2026-04-01", "label": "Assignment 3", "category": "assignment"},
    # Week 11
    {"date": "2026-04-01", "label": "Source Summary 7 (SS7)", "category": "project"},
    # Week 12
    {"date": "2026-04-08", "label": "Source Summary 8 (SS8)", "category": "project"},
    {"date": "2026-04-15", "label": "Assignment 4", "category": "assignment"},
    # Week 13
    {"date": "2026-04-17", "label": "Draft Paper & Video", "category": "project"},
    # Week 14
    {"date": "2026-04-21", "label": "Exam 2", "category": "exam"},
    # Week 15
    {"date": "2026-05-04", "label": "Final Report & Video", "category": "project"},
    {"date": "2026-05-05", "label": "Peer Evaluation 2", "category": "peer_eval"},
    # Week 16
    {"date": "2026-05-15", "label": "Poster Presentations (TBD)", "category": "project"},
]

_raw_cs = os.getenv("COURSE_SCHEDULE_JSON", "").strip()
COURSE_SCHEDULE_DATA: List[dict] = json.loads(_raw_cs) if _raw_cs else _DEFAULT_COURSE_SCHEDULE


@dataclass
class Deadline:
    date: datetime
    label: str
    category: str


def _parse_course_schedule(data: List[dict]) -> List[Deadline]:
    """Convert raw JSON/dict list into sorted Deadline objects."""
    deadlines: List[Deadline] = []
    for entry in data:
        dt = datetime.strptime(entry["date"], "%Y-%m-%d").replace(tzinfo=REPORT_TZ)
        deadlines.append(Deadline(date=dt, label=entry["label"], category=entry.get("category", "other")))
    deadlines.sort(key=lambda d: d.date)
    return deadlines


COURSE_DEADLINES: List[Deadline] = _parse_course_schedule(COURSE_SCHEDULE_DATA)

# Emoji prefix by category for embed readability
_CATEGORY_EMOJI = {
    "assignment": "\U0001f4dd",   # memo
    "exam": "\U0001f4d6",         # open book
    "project": "\U0001f4cb",      # clipboard
    "quiz": "\u2753",             # question mark
    "peer_eval": "\U0001f465",    # busts in silhouette
}


def get_upcoming_deadlines(now: datetime, lookahead_days: int = 7) -> List[Deadline]:
    """Return deadlines from *today* through *lookahead_days* in the future."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today + timedelta(days=lookahead_days + 1)  # inclusive of the last day
    return [d for d in COURSE_DEADLINES if today <= d.date < cutoff]


def build_upcoming_embed(now: datetime, lookahead_days: int = 7) -> discord.Embed:
    """Create a rich embed showing upcoming deadlines."""
    upcoming = get_upcoming_deadlines(now, lookahead_days)

    embed = discord.Embed(
        title="Upcoming Deadlines",
        color=discord.Color.orange(),
        timestamp=now,
    )

    if not upcoming:
        embed.description = f"Nothing due in the next {lookahead_days} days."
        embed.set_footer(text="Use /upcoming to check anytime")
        return embed

    lines: List[str] = []
    for d in upcoming:
        emoji = _CATEGORY_EMOJI.get(d.category, "\U0001f4cc")  # default: pushpin
        day_diff = (d.date.date() - now.date()).days
        if day_diff == 0:
            when = "**TODAY**"
        elif day_diff == 1:
            when = "tomorrow"
        else:
            when = d.date.strftime("%a %b %-d")
        lines.append(f"{emoji} {when} — {d.label}")

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Showing next {lookahead_days} days • Use /upcoming to check anytime")
    return embed


def build_deadline_reminder_text(now: datetime) -> Optional[str]:
    """Build a plain-text message for the daily #deadlines post.
    Returns None if nothing is due in the next 7 days."""
    upcoming = get_upcoming_deadlines(now, lookahead_days=7)
    if not upcoming:
        return None

    lines: List[str] = []
    lines.append("**Upcoming Deadlines (next 7 days)**")
    lines.append("")

    for d in upcoming:
        emoji = _CATEGORY_EMOJI.get(d.category, "\U0001f4cc")
        day_diff = (d.date.date() - now.date()).days
        if day_diff == 0:
            when = "**TODAY**"
        elif day_diff == 1:
            when = "**Tomorrow**"
        else:
            when = d.date.strftime("%A, %b %-d")
        lines.append(f"{emoji} {when} — {d.label}")

    return "\n".join(lines)


def utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def norm_username(value: str) -> str:
    return str(value).strip().lower()


def norm_team(value: str) -> str:
    return str(value).strip().upper().replace(" ", "")


@dataclass
class MemberRecord:
    username: str
    team: str
    first_name: str
    last_name: str
    email: str


@dataclass
class TeamAsset:
    team: str
    video_url: str
    wireframe_url: str


# ============================================================================
# DATABASE CLASS - DEFINED FIRST (before instantiation and WorkbookData)
# ============================================================================

class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                discord_id TEXT PRIMARY KEY,
                rit_username TEXT UNIQUE NOT NULL,
                registered_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewer_discord_id TEXT NOT NULL,
                reviewer_username TEXT NOT NULL,
                home_team TEXT NOT NULL,
                assigned_team TEXT NOT NULL,
                video_url TEXT NOT NULL,
                wireframe_url TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('assigned', 'submitted')),
                assigned_at TEXT NOT NULL,
                submitted_at TEXT,
                intro_score INTEGER,
                background_score INTEGER,
                method_score INTEGER,
                findings_score INTEGER,
                references_score INTEGER,
                intro_comment TEXT,
                background_comment TEXT,
                method_comment TEXT,
                findings_comment TEXT,
                references_comment TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_reviewer_team
            ON assignments (reviewer_discord_id, assigned_team)
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS username_help_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                claimed_username TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                recipient_username TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self.conn.commit()

    def upsert_user(self, discord_id: int, rit_username: str) -> None:
        self.conn.execute(
            """
            INSERT INTO users (discord_id, rit_username, registered_at)
            VALUES (?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                rit_username=excluded.rit_username
            """,
            (str(discord_id), norm_username(rit_username), utcnow_iso()),
        )
        self.conn.commit()

    def get_rit_username_for_discord(self, discord_id: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT rit_username FROM users WHERE discord_id = ?",
            (str(discord_id),),
        ).fetchone()
        return row["rit_username"] if row else None

    def get_discord_id_for_username(self, rit_username: str) -> Optional[int]:
        row = self.conn.execute(
            "SELECT discord_id FROM users WHERE rit_username = ?",
            (norm_username(rit_username),),
        ).fetchone()
        return int(row["discord_id"]) if row else None

    def count_submitted_reviews(self, discord_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM assignments
            WHERE reviewer_discord_id = ? AND status = 'submitted'
            """,
            (str(discord_id),),
        ).fetchone()
        return int(row["count"])

    def get_open_assignment(self, discord_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM assignments
            WHERE reviewer_discord_id = ? AND status = 'assigned'
            ORDER BY assigned_at DESC
            LIMIT 1
            """,
            (str(discord_id),),
        ).fetchone()

    def get_assignment(self, assignment_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM assignments WHERE id = ?",
            (assignment_id,),
        ).fetchone()

    def get_reviewed_or_assigned_teams(self, discord_id: int) -> List[str]:
        rows = self.conn.execute(
            """
            SELECT assigned_team
            FROM assignments
            WHERE reviewer_discord_id = ?
            """,
            (str(discord_id),),
        ).fetchall()
        return [row["assigned_team"] for row in rows]

    def count_received_reviews(self, team: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM assignments
            WHERE assigned_team = ? AND status = 'submitted'
            """,
            (team,),
        ).fetchone()
        return int(row["count"])

    def create_assignment(
        self,
        reviewer_discord_id: int,
        reviewer_username: str,
        home_team: str,
        assigned_team: str,
        video_url: str,
        wireframe_url: str,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO assignments (
                reviewer_discord_id, reviewer_username, home_team,
                assigned_team, video_url, wireframe_url, status, assigned_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
            """,
            (
                str(reviewer_discord_id),
                reviewer_username,
                home_team,
                assigned_team,
                video_url,
                wireframe_url,
                utcnow_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_scores(
        self,
        assignment_id: int,
        intro: int,
        background: int,
        method: int,
        findings: int,
        references: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE assignments
            SET intro_score = ?, background_score = ?, method_score = ?,
                findings_score = ?, references_score = ?
            WHERE id = ?
            """,
            (intro, background, method, findings, references, assignment_id),
        )
        self.conn.commit()

    def submit_comments(
        self,
        assignment_id: int,
        intro_comment: str,
        background_comment: str,
        method_comment: str,
        findings_comment: str,
        references_comment: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE assignments
            SET intro_comment = ?, background_comment = ?, method_comment = ?,
                findings_comment = ?, references_comment = ?,
                status = 'submitted',
                submitted_at = ?
            WHERE id = ?
            """,
            (
                intro_comment,
                background_comment,
                method_comment,
                findings_comment,
                references_comment,
                utcnow_iso(),
                assignment_id,
            ),
        )
        self.conn.commit()

    def log_username_help(self, discord_id: int, claimed_username: str, note: str) -> None:
        self.conn.execute(
            """
            INSERT INTO username_help_logs (discord_id, claimed_username, note, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(discord_id), norm_username(claimed_username), note.strip(), utcnow_iso()),
        )
        self.conn.commit()

    def log_delivery_failure(self, assignment_id: int, recipient_username: str, reason: str) -> None:
        self.conn.execute(
            """
            INSERT INTO delivery_failures (assignment_id, recipient_username, reason, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (assignment_id, norm_username(recipient_username), reason[:500], utcnow_iso()),
        )
        self.conn.commit()

    def reviewer_completion_rows(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT reviewer_username, COUNT(*) AS review_count
            FROM assignments
            WHERE status = 'submitted'
            GROUP BY reviewer_username
            ORDER BY review_count DESC, reviewer_username ASC
            """
        ).fetchall()

    def team_received_rows(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT assigned_team, COUNT(*) AS review_count
            FROM assignments
            WHERE status = 'submitted'
            GROUP BY assigned_team
            ORDER BY assigned_team ASC
            """
        ).fetchall()

    def recent_username_help_rows(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT discord_id, claimed_username, note, created_at
            FROM username_help_logs
            WHERE datetime(replace(created_at, 'Z', '')) >= datetime('now', '-1 day')
            ORDER BY created_at DESC
            """
        ).fetchall()

    def recent_delivery_failure_rows(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT assignment_id, recipient_username, reason, created_at
            FROM delivery_failures
            WHERE datetime(replace(created_at, 'Z', '')) >= datetime('now', '-1 day')
            ORDER BY created_at DESC
            """
        ).fetchall()

    def unregistered_usernames_with_pending_reviews(self) -> List[sqlite3.Row]:
        """Return usernames that have delivery failures because they haven't
        registered yet, along with how many reviews are waiting for them.
        Only includes usernames that are still NOT in the users table."""
        return self.conn.execute(
            """
            SELECT df.recipient_username,
                   COUNT(DISTINCT df.assignment_id) AS pending_review_count
            FROM delivery_failures df
            LEFT JOIN users u
                ON df.recipient_username = u.rit_username
            WHERE u.rit_username IS NULL
              AND df.reason LIKE '%not registered%'
            GROUP BY df.recipient_username
            ORDER BY df.recipient_username ASC
            """
        ).fetchall()


# ============================================================================
# INSTANTIATE DATABASE AND WORKBOOK DATA (after Database class is defined)
# ============================================================================

DB = Database(DATABASE_FILE)


class WorkbookData:
    def __init__(self, path: str):
        self.path = path
        self.members_by_username: Dict[str, MemberRecord] = {}
        self.members_by_team: Dict[str, List[MemberRecord]] = {}
        self.assets_by_team: Dict[str, TeamAsset] = {}
        self.all_teams: List[str] = []
        self.load()
        self.catchup_handler = CatchupHandler(self, DB)

    def load(self) -> None:
        mappings_df = pd.read_excel(self.path, sheet_name="Username-Team Mappings").fillna("")
        links_df = pd.read_excel(self.path, sheet_name="Assigned Team Links").fillna("")

        members_by_username: Dict[str, MemberRecord] = {}
        members_by_team: Dict[str, List[MemberRecord]] = {}
        assets_by_team: Dict[str, TeamAsset] = {}

        for _, row in mappings_df.iterrows():
            username = norm_username(row["Username"])
            team = norm_team(row["Group Name"])
            member = MemberRecord(
                username=username,
                team=team,
                first_name=str(row["First Name"]).strip(),
                last_name=str(row["Last Name"]).strip(),
                email=str(row["Email Address"]).strip(),
            )
            members_by_username[username] = member
            members_by_team.setdefault(team, []).append(member)

        for _, row in links_df.iterrows():
            team = norm_team(row["Assigned Team"])
            asset = TeamAsset(
                team=team,
                video_url=str(row["Video Link"]).strip(),
                wireframe_url=str(row["Wireframe PDF"]).strip(),
            )
            assets_by_team[team] = asset

        missing_assets = sorted(set(members_by_team.keys()) - set(assets_by_team.keys()))
        if missing_assets:
            raise RuntimeError(
                f"Workbook mismatch: these teams exist in tab 1 but not tab 2: {', '.join(missing_assets)}"
            )

        self.members_by_username = members_by_username
        self.members_by_team = members_by_team
        self.assets_by_team = assets_by_team
        self.all_teams = sorted(assets_by_team.keys())


DATA = WorkbookData(EXCEL_FILE)


def parse_likert(value: str) -> int:
    cleaned = str(value).strip()
    if cleaned not in {"1", "2", "3", "4", "5"}:
        raise ValueError("Likert values must be integers 1-5.")
    return int(cleaned)


def format_assignment_message(row: sqlite3.Row) -> str:
    return (
        f"**Assigned team:** {row['assigned_team']}\n"
        f"**Video:** {row['video_url']}\n"
        f"**Wireframe PDF:** {row['wireframe_url']}\n\n"
        "Please review the video and associated wireframe PDF, then click **Start Review**.\n\n"
        "**Likert scale:** 1 = missing, 5 = solid argumentation & references."
    )


def format_feedback_dm(row: sqlite3.Row) -> str:
    return (
        f"**Peer Review for {row['assigned_team']}**\n"
        f"Reviewer: `{row['reviewer_username']}`\n"
        f"Reviewer home team: `{row['home_team']}`\n"
        f"Submitted: {row['submitted_at']}\n\n"
        f"**1a. Introduction effectiveness:** {row['intro_score']}/5\n"
        f"**1b. Introduction improvement:**\n{row['intro_comment']}\n\n"
        f"**2a. Background effectiveness:** {row['background_score']}/5\n"
        f"**2b. Background improvement:**\n{row['background_comment']}\n\n"
        f"**3a. Method effectiveness:** {row['method_score']}/5\n"
        f"**3b. Method improvement:**\n{row['method_comment']}\n\n"
        f"**4a. Findings effectiveness:** {row['findings_score']}/5\n"
        f"**4b. Findings improvement:**\n{row['findings_comment']}\n\n"
        f"**5a. References effectiveness:** {row['references_score']}/5\n"
        f"**5b. References improvement:**\n{row['references_comment']}"
    )


class CommentsLaunchView(discord.ui.View):
    def __init__(self, reviewer_discord_id: int, assignment_id: int):
        super().__init__(timeout=1800)
        self.reviewer_discord_id = reviewer_discord_id
        self.assignment_id = assignment_id

    @discord.ui.button(label="Continue to Comments", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.reviewer_discord_id:
            await interaction.response.send_message(
                "This review belongs to someone else.",
                ephemeral=True,
            )
            return

        row = DB.get_assignment(self.assignment_id)
        if row is None or row["status"] != "assigned":
            await interaction.response.send_message(
                "This assignment is no longer open.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(CommentsModal(self.reviewer_discord_id, self.assignment_id))


class ScoreModal(discord.ui.Modal, title="Peer Review Scores"):
    intro_score = discord.ui.TextInput(
        label="1a. Introduction effectiveness (1-5)",
        placeholder="1 = missing, 5 = solid argumentation & references",
        max_length=1,
    )
    background_score = discord.ui.TextInput(
        label="2a. Background effectiveness (1-5)",
        placeholder="1-5",
        max_length=1,
    )
    method_score = discord.ui.TextInput(
        label="3a. Method effectiveness (1-5)",
        placeholder="1-5",
        max_length=1,
    )
    findings_score = discord.ui.TextInput(
        label="4a. Findings effectiveness (1-5)",
        placeholder="1-5",
        max_length=1,
    )
    references_score = discord.ui.TextInput(
        label="5a. References effectiveness (1-5)",
        placeholder="1-5",
        max_length=1,
    )

    def __init__(self, reviewer_discord_id: int, assignment_id: int):
        super().__init__(timeout=1800)
        self.reviewer_discord_id = reviewer_discord_id
        self.assignment_id = assignment_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.reviewer_discord_id:
            await interaction.response.send_message("This review belongs to someone else.", ephemeral=True)
            return

        row = DB.get_assignment(self.assignment_id)
        if row is None or row["status"] != "assigned":
            await interaction.response.send_message("This assignment is no longer open.", ephemeral=True)
            return

        try:
            intro = parse_likert(self.intro_score.value)
            background = parse_likert(self.background_score.value)
            method = parse_likert(self.method_score.value)
            findings = parse_likert(self.findings_score.value)
            references = parse_likert(self.references_score.value)
        except ValueError:
            await interaction.response.send_message(
                "All five score fields must be integers from 1 to 5.",
                ephemeral=True,
            )
            return

        DB.save_scores(self.assignment_id, intro, background, method, findings, references)

        await interaction.response.send_message(
            "Scores saved. Now add your written feedback.",
            view=CommentsLaunchView(self.reviewer_discord_id, self.assignment_id),
            ephemeral=True,
        )


class CommentsModal(discord.ui.Modal, title="Peer Review Comments"):
    intro_comment = discord.ui.TextInput(
        label="1b. Improve the Introduction",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    background_comment = discord.ui.TextInput(
        label="2b. Improve the Background",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    method_comment = discord.ui.TextInput(
        label="3b. Improve the Method",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    findings_comment = discord.ui.TextInput(
        label="4b. Improve the Findings",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    references_comment = discord.ui.TextInput(
        label="5b. Improve the References",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    def __init__(self, reviewer_discord_id: int, assignment_id: int):
        super().__init__(timeout=1800)
        self.reviewer_discord_id = reviewer_discord_id
        self.assignment_id = assignment_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.reviewer_discord_id:
            await interaction.response.send_message("This review belongs to someone else.", ephemeral=True)
            return

        row = DB.get_assignment(self.assignment_id)
        if row is None or row["status"] != "assigned":
            await interaction.response.send_message("This assignment is no longer open.", ephemeral=True)
            return

        if row["intro_score"] is None:
            await interaction.response.send_message(
                "Please submit the score form first.",
                ephemeral=True,
            )
            return

        # Defer immediately — deliver_feedback() sends DMs to every registered
        # team member, which can easily exceed Discord's 3-second interaction
        # deadline and cause a "404 Unknown interaction" error.
        await interaction.response.defer(ephemeral=True)

        DB.submit_comments(
            self.assignment_id,
            self.intro_comment.value.strip(),
            self.background_comment.value.strip(),
            self.method_comment.value.strip(),
            self.findings_comment.value.strip(),
            self.references_comment.value.strip(),
        )

        delivered, failed = await deliver_feedback(self.assignment_id)

        message = f"Review submitted. Delivered to {len(delivered)} team member(s)."
        if failed:
            message += "\n\nSome deliveries failed:\n- " + "\n- ".join(failed[:10])

        await interaction.followup.send(message, ephemeral=True)


class StartReviewView(discord.ui.View):
    def __init__(self, reviewer_discord_id: int, assignment_id: int):
        super().__init__(timeout=1800)
        self.reviewer_discord_id = reviewer_discord_id
        self.assignment_id = assignment_id

    @discord.ui.button(label="Start Review", style=discord.ButtonStyle.primary)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.reviewer_discord_id:
            await interaction.response.send_message(
                "This assignment belongs to someone else.",
                ephemeral=True,
            )
            return

        row = DB.get_assignment(self.assignment_id)
        if row is None or row["status"] != "assigned":
            await interaction.response.send_message(
                "This assignment is no longer open.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(ScoreModal(self.reviewer_discord_id, self.assignment_id))


class PeerReviewBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read @mention message text
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        if GUILD_OBJECT:
            self.tree.copy_global_to(guild=GUILD_OBJECT)
            await self.tree.sync(guild=GUILD_OBJECT)
            print(f"Slash commands synced to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Global slash commands synced")

    async def on_ready(self):
        print(f"Logged in as {self.user} ({self.user.id})")
        # Initialize game DB using the existing peer-review DB connection
        game_sessions.init_db(DB.conn)
        print("Papers Please game database initialized.")
        if not daily_instructor_report.is_running():
            daily_instructor_report.start()
        if not weekly_game_report.is_running():
            weekly_game_report.start()
        if not daily_recommendations_summary.is_running():
            daily_recommendations_summary.start()
        if not daily_unregistered_nudge.is_running():
            daily_unregistered_nudge.start()
        if not daily_deadline_reminder.is_running():
            daily_deadline_reminder.start()


bot = PeerReviewBot()


def is_instructor(member: discord.Member) -> bool:
    if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
        return True
    role_names = {role.name.lower() for role in member.roles}
    return "instructor" in role_names or "instructors" in role_names


async def get_instructor_channel() -> Optional[discord.TextChannel]:
    if GUILD_ID is None:
        return None

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except discord.DiscordException:
            return None

    for channel in guild.text_channels:
        if channel.name == INSTRUCTOR_CHANNEL_NAME:
            return channel
    return None


async def get_general_channel() -> Optional[discord.TextChannel]:
    if GUILD_ID is None:
        return None

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except discord.DiscordException:
            return None

    for channel in guild.text_channels:
        if channel.name == GENERAL_CHANNEL_NAME:
            return channel
    return None


async def get_deadlines_channel() -> Optional[discord.TextChannel]:
    if GUILD_ID is None:
        return None

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except discord.DiscordException:
            return None

    for channel in guild.text_channels:
        if channel.name == DEADLINES_CHANNEL_NAME:
            return channel
    return None


def choose_team_for_reviewer(discord_id: int, home_team: str) -> Optional[str]:
    already_seen = set(DB.get_reviewed_or_assigned_teams(discord_id))
    eligible = [
        team for team in DATA.all_teams
        if team != home_team and team not in already_seen
    ]
    if not eligible:
        return None

    counts = {team: DB.count_received_reviews(team) for team in eligible}
    min_count = min(counts.values())
    least_reviewed = [team for team, count in counts.items() if count == min_count]
    return random.choice(least_reviewed)


async def deliver_feedback(assignment_id: int) -> Tuple[List[str], List[str]]:
    row = DB.get_assignment(assignment_id)
    if row is None:
        return [], ["Assignment not found."]

    message = format_feedback_dm(row)
    delivered: List[str] = []
    failed: List[str] = []

    recipients = DATA.members_by_team.get(row["assigned_team"], [])
    for member in recipients:
        discord_id = DB.get_discord_id_for_username(member.username)
        if discord_id is None:
            reason = "recipient has not registered with the bot yet"
            DB.log_delivery_failure(assignment_id, member.username, reason)
            failed.append(f"{member.username}: {reason}")
            continue

        try:
            user = bot.get_user(discord_id) or await bot.fetch_user(discord_id)
            await user.send(message)
            delivered.append(member.username)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            DB.log_delivery_failure(assignment_id, member.username, reason)
            failed.append(f"{member.username}: DM failed")

    return delivered, failed


def build_daily_report_text() -> str:
    """Build the peer review section of the daily report."""
    reviewer_rows = DB.reviewer_completion_rows()
    team_rows = DB.team_received_rows()
    username_help_rows = DB.recent_username_help_rows()
    delivery_failure_rows = DB.recent_delivery_failure_rows()

    lines = []
    lines.append("**Reviews completed per user**")
    if reviewer_rows:
        for row in reviewer_rows:
            lines.append(f"- `{row['reviewer_username']}`: {row['review_count']}")
    else:
        lines.append("- None yet")

    lines.append("")
    lines.append("**Reviews received per team**")
    if team_rows:
        for row in team_rows:
            lines.append(f"- `{row['assigned_team']}`: {row['review_count']}")
    else:
        lines.append("- None yet")

    lines.append("")
    lines.append("**Username disputes (last 24h)**")
    if username_help_rows:
        for row in username_help_rows:
            note = row["note"] or "(no note)"
            lines.append(
                f"- `{row['discord_id']}` → `{row['claimed_username']}` — {note}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("**DM delivery failures (last 24h)**")
    if delivery_failure_rows:
        for row in delivery_failure_rows:
            lines.append(
                f"- assignment `{row['assignment_id']}` → `{row['recipient_username']}` — {row['reason']}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines[:1800])


def build_game_report_embed() -> discord.Embed:
    """Build the game performance section as a rich embed."""
    if not game_sessions.db:
        return None

    player_stats = game_sessions.db.get_player_stats()
    if not player_stats:
        return None

    embed = discord.Embed(
        title="🎮 Papers Please — Agent Performance Brief",
        description=f"Game activity as of {datetime.now(REPORT_TZ).strftime('%Y-%m-%d %H:%M %Z')}",
        color=0x9B59B6,
    )

    # Top performers summary
    top_lines = []
    for i, row in enumerate(player_stats[:10]):
        rit = row["rit_username"]
        play_min = row["total_play_seconds"] // 60 if row["total_play_seconds"] else 0
        top_lines.append(
            f"**{i+1}.** `{rit}` — "
            f"Best: {row['best_score']} | "
            f"Acc: {row['avg_accuracy']}% | "
            f"MaxLv: {row['max_difficulty_reached']} | "
            f"Sessions: {row['total_sessions']} | "
            f"Time: {play_min}m"
        )
    if top_lines:
        embed.add_field(
            name="🏆 Leaderboard (by Best Score)",
            value="\n".join(top_lines),
            inline=False,
        )

    # Concept mastery overview
    topic_data = game_sessions.db.get_topic_performance()
    if topic_data:
        mastery_lines = []
        for topic, stats in topic_data.items():
            pct = round(stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            mastery_lines.append(f"`{topic[:20]:20s}` [{bar}] {pct}% ({stats['correct']}/{stats['total']})")
        embed.add_field(
            name="📚 Concept Mastery by Topic",
            value="\n".join(mastery_lines[:12]),
            inline=False,
        )

    # Milestone summary
    milestone_rows = game_sessions.db.get_player_milestones()
    if milestone_rows:
        m_lines = []
        for row in milestone_rows[:8]:
            milestones = row["milestones"].split(",") if row["milestones"] else []
            m_lines.append(f"`{row['rit_username']}`: {', '.join(milestones[:5])}")
        embed.add_field(
            name="🎖️ Milestones Earned",
            value="\n".join(m_lines),
            inline=False,
        )

    embed.set_footer(text="Papers Please • CSEC-472 Authentication Training Module")
    return embed


async def build_game_report_charts() -> List[discord.File]:
    """Generate chart images for the game report."""
    charts = []
    if not game_sessions.db:
        return charts

    # Accuracy chart
    player_stats = game_sessions.db.get_player_stats()
    if player_stats:
        accuracy_data = [
            {"label": f"{r['rit_username']}", "accuracy": r["avg_accuracy"] or 0, "total_entrants": r["best_score"]}
            for r in player_stats[:15]
        ]
        chart = generate_accuracy_chart(accuracy_data)
        if chart:
            charts.append(chart)

        # Difficulty progression
        diff_data = [
            {"label": f"{r['rit_username']}", "max_difficulty": r["max_difficulty_reached"] or 0, "sessions": r["total_sessions"]}
            for r in player_stats[:15]
        ]
        chart2 = generate_difficulty_progression_chart(diff_data)
        if chart2:
            charts.append(chart2)

    # Topic performance
    topic_data = game_sessions.db.get_topic_performance()
    if topic_data:
        chart3 = generate_topic_performance_chart(topic_data)
        if chart3:
            charts.append(chart3)

    # Activity timeline
    daily_counts = game_sessions.db.get_daily_session_counts()
    if daily_counts:
        chart4 = generate_session_activity_chart(daily_counts)
        if chart4:
            charts.append(chart4)

    return charts


@tasks.loop(time=REPORT_TIME)
async def daily_instructor_report():
    # Skip weekends (Saturday=5, Sunday=6).
    if datetime.now(REPORT_TZ).weekday() >= 5:
        return

    channel = await get_instructor_channel()
    if channel is None:
        print(f"Instructor channel '{INSTRUCTOR_CHANNEL_NAME}' not found.")
        return

    # Header embed
    header_embed = discord.Embed(
        title="📋 CSEC-472 Daily Brief",
        description=f"Generated: {datetime.now(REPORT_TZ).strftime('%A, %B %d %Y • %H:%M %Z')}",
        color=0x2ECC71,
    )
    header_embed.set_footer(text="AuthBot • CSEC-472 Peer Review System")
    await channel.send(embed=header_embed)

    # Peer review section
    review_text = build_daily_report_text()
    review_embed = discord.Embed(
        title="📝 Peer Review Summary",
        description=review_text,
        color=0x3498DB,
    )
    await channel.send(embed=review_embed)


@tasks.loop(time=REPORT_TIME)
async def weekly_game_report():
    """Send the Papers Please game performance brief every Friday."""
    # Only fire on Fridays (weekday 4)
    if datetime.now(REPORT_TZ).weekday() != 4:
        return

    channel = await get_instructor_channel()
    if channel is None:
        print(f"Instructor channel '{INSTRUCTOR_CHANNEL_NAME}' not found.")
        return

    # Header embed
    header_embed = discord.Embed(
        title="🎮 CSEC-472 Weekly Agent Performance Brief",
        description=f"Generated: {datetime.now(REPORT_TZ).strftime('%A, %B %d %Y • %H:%M %Z')}",
        color=0x9B59B6,
    )
    header_embed.set_footer(text="AuthBot • Papers Please Game Analytics")
    await channel.send(embed=header_embed)

    # Game performance section
    game_embed = build_game_report_embed()
    if game_embed:
        await channel.send(embed=game_embed)

    # Charts
    try:
        charts = await build_game_report_charts()
        for chart_file in charts:
            await channel.send(file=chart_file)
    except Exception as exc:
        print(f"[Report] Chart generation error: {exc}")


# ---------------------------------------------------------------------------
# @Mention handler — recommendation detection & smart replies
# ---------------------------------------------------------------------------

import re as _re

# In-memory store for today's confirmed recommendations; flushed after daily summary.
_pending_recommendations: List[dict] = []

# Tracks recommendation proposals awaiting user confirmation in DMs.
# Key: bot DM message ID → value: draft recommendation dict
_unconfirmed_recommendations: Dict[int, dict] = {}

# Keywords / phrases that signal a feature recommendation
_RECOMMENDATION_SIGNALS = [
    "should", "could you", "can you", "would be nice", "it would be",
    "add a", "add an", "feature", "idea", "suggestion", "suggest",
    "recommend", "request", "please make", "you should", "how about",
    "what if", "wish", "need a", "needs a", "improve", "upgrade",
    "update", "change", "fix", "implement", "build", "create",
    "let us", "let me", "allow us", "allow me", "enable",
]

# Keywords that signal a question or task request (not a recommendation)
_QUESTION_SIGNALS = [
    "what", "when", "where", "who", "how", "why", "is there", "are there",
    "do you", "does", "tell me", "explain", "help", "show me", "?",
]

_TASK_SIGNALS = [
    "remind", "check", "look at", "look into", "find", "search",
    "send", "post", "run", "start", "stop", "reset", "clear",
    "list", "count", "give me", "get me", "pull up",
]

# Canned smart replies for truly casual mentions (greetings, shoutouts, etc.)
_CASUAL_REPLIES = [
    "I'm always listening. Well, when you @ me, at least. 👂",
    "You rang? AuthBot at your service. 🫡",
    "At your service! Fun fact: CERBERUS has three heads, but I still only have one brain cell dedicated to dad jokes.",
    "Acknowledged. If that was meant to be a compliment, I'll take it. If not... I'll still take it. 😎",
    "I'm here! Unlike expired TLS certificates, I'm always valid. Well, until someone restarts me.",
    "Did someone say AuthBot? That's me! I'm like a Kerberos KDC — I'm the trusted third party in this conversation.",
    "Ping received! My response time is better than most OAuth token refresh cycles. ⚡",
    "Reporting for duty! 🛡️ Though if you're trying to social-engineer me, you'll need more than an @mention.",
    "Copy. I may be a bot, but I've got feelings. Well, `if/else` statements. Close enough.",
]

# Intelligent replies keyed to recognized topics/tasks
_COMMAND_HINTS = {
    "review": "Looking for peer reviews? Use `/review` to get your next assignment.",
    "play": "Want to play Papers Please? Use `/play` to start a checkpoint session in your DMs!",
    "game": "Ready for a round? Use `/play` to launch the Papers Please game. CERBERUS will be watching. 🐕‍🦺",
    "office": "Check `/office_hours` to see who's available right now and when the next sessions are.",
    "deadline": "Use `/upcoming` to see what's due in the next few days.",
    "register": "Need to register? Use `/register <your_rit_username>` to link your Discord account.",
    "score": "Your game stats are available during an active session via the 📊 Score button, or instructors can check the weekly report.",
    "cerberus": "Ask CERBERUS about any AUTH concept with `/cerberus <topic>` — try `kerberos`, `tls`, `oauth`, `mfa`, or `deep dive <topic>` for the full breakdown.",
    "joke": "Need a laugh? Try `/dadjoke` to drop one in #extracurricular.",
    "help": "Here's what I can do: `/register`, `/review`, `/play`, `/cerberus`, `/upcoming`, `/office_hours`, `/dadjoke`, and `/status`. What do you need?",
    "quit": "To end your game session, use `/quit_game`. Your stats will be saved.",
    "report": "Instructors can trigger reports with `/send_daily_report_now` or `/send_weekly_report_now`.",
}

# Emojis accepted as confirmation
_CONFIRM_EMOJIS = {"👍", "✅", "🆗", "💯", "🫡", "👌"}
_REJECT_EMOJIS = {"👎", "❌", "🚫"}


def _is_recommendation(text: str) -> bool:
    """Return True if the message text looks like a feature recommendation."""
    lower = text.lower()
    return any(signal in lower for signal in _RECOMMENDATION_SIGNALS)


def _clean_mention_text(text: str) -> str:
    """Strip @mentions and clean up the text."""
    cleaned = _re.sub(r"<@!?\d+>", "", text).strip()
    if len(cleaned) > 300:
        cleaned = cleaned[:297] + "..."
    return cleaned


def _build_intelligent_reply(text: str) -> str:
    """Analyze the mention text and build a context-appropriate reply.

    Priority:
      1. Match a known topic/command → give targeted guidance
      2. Looks like a question → give a helpful answer
      3. Looks like a task request → explain relevant capabilities
      4. Fallback → casual reply
    """
    lower = text.lower()
    cleaned = _re.sub(r"<@!?\d+>", "", lower).strip()

    # 1. Check for known topic keywords → give targeted help
    for keyword, hint in _COMMAND_HINTS.items():
        if keyword in cleaned:
            return hint

    # 2. Looks like a question → give a thoughtful answer
    if any(q in cleaned for q in _QUESTION_SIGNALS):
        return (
            f"Good question! I'm not sure I fully understand what you're asking, "
            f"but here's what I can help with: peer reviews (`/review`), "
            f"the Papers Please game (`/play`), security concepts (`/cerberus <topic>`), "
            f"office hours (`/office_hours`), and deadlines (`/upcoming`). "
            f"Can you be more specific?"
        )

    # 3. Looks like a task request → explain capabilities
    if any(t in cleaned for t in _TASK_SIGNALS):
        return (
            f"I'd love to help! Here are my available commands:\n"
            f"• `/register` — Link your RIT username\n"
            f"• `/review` — Get a peer review assignment\n"
            f"• `/play` — Launch Papers Please\n"
            f"• `/cerberus <topic>` — Deep dive into AUTH concepts\n"
            f"• `/upcoming` — Check deadlines\n"
            f"• `/office_hours` — See availability\n"
            f"Which one fits what you need?"
        )

    # 4. Truly casual mention → fun reply
    return random.choice(_CASUAL_REPLIES)


@bot.event
async def on_message(message: discord.Message):
    """Handle @AuthBot mentions: detect recommendations, handle DM confirmations,
    or reply intelligently."""
    # Ignore messages from self
    if message.author.id == bot.user.id:
        return

    # --- Check if this is a DM reply to an unconfirmed recommendation ---
    if (isinstance(message.channel, discord.DMChannel)
            and message.reference
            and message.reference.message_id in _unconfirmed_recommendations):
        draft = _unconfirmed_recommendations[message.reference.message_id]
        if message.author.id == draft["author_id"]:
            reply_lower = message.content.strip().lower()
            # Check for affirmative replies
            if reply_lower in ("yes", "y", "yep", "yeah", "correct", "confirmed",
                               "confirm", "looks good", "lgtm", "approved", "ok",
                               "okay", "sure", "that's right", "thats right", "right"):
                _pending_recommendations.append(draft)
                del _unconfirmed_recommendations[message.reference.message_id]
                await message.reply(
                    f"✅ **Recommendation confirmed and logged!** "
                    f"It will appear in the next daily summary in `#{INSTRUCTOR_CHANNEL_NAME}`."
                )
            elif reply_lower in ("no", "n", "nope", "wrong", "cancel", "nevermind",
                                 "never mind", "nvm", "discard", "delete", "remove"):
                del _unconfirmed_recommendations[message.reference.message_id]
                await message.reply("🗑️ Recommendation discarded. No worries!")
            else:
                # Treat as a correction — update the summary text
                corrected = _clean_mention_text(message.content)
                draft["text"] = corrected
                bot_reply = await message.reply(
                    f"📝 **Updated recommendation:**\n> {corrected}\n\n"
                    f"Is this correct? Reply **yes** to confirm, "
                    f"or reply with another correction."
                )
                del _unconfirmed_recommendations[message.reference.message_id]
                _unconfirmed_recommendations[bot_reply.id] = draft
        await bot.process_commands(message)
        return

    # --- Only process guild/channel messages that mention the bot ---
    if bot.user not in message.mentions:
        await bot.process_commands(message)
        return

    text = message.content
    author = message.author

    if _is_recommendation(text):
        cleaned = _clean_mention_text(text)

        draft = {
            "author": str(author),
            "author_id": author.id,
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "text": cleaned,
            "timestamp": datetime.now(REPORT_TZ).isoformat(),
        }

        # Acknowledge publicly in channel (brief)
        await message.reply(
            f"💡 Recommendation detected! Check your DMs, {author.display_name} — "
            f"I've sent it there for you to review and confirm."
        )

        # Send the full confirmation flow via DM
        try:
            dm_channel = await author.create_dm()
            bot_dm = await dm_channel.send(
                f"💡 **RECOMMENDATION DETECTED** (from #{draft['channel']}):\n"
                f"> {cleaned}\n\n"
                f"Is this correct? Reply **yes** to confirm, type a correction to revise, "
                f"or reply **cancel** to discard."
            )
            _unconfirmed_recommendations[bot_dm.id] = draft
        except discord.Forbidden:
            # Can't DM user — fall back to storing directly
            _pending_recommendations.append(draft)
            await message.channel.send(
                f"⚠️ I couldn't DM you, {author.display_name}, so I've logged the "
                f"recommendation as-is. It will appear in the next daily summary."
            )
    else:
        # Not a recommendation — analyze and reply intelligently
        reply = _build_intelligent_reply(text)
        await message.reply(reply)

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reaction-based confirmation/rejection of recommendations in DMs."""
    if user.id == bot.user.id:
        return

    msg_id = reaction.message.id
    if msg_id not in _unconfirmed_recommendations:
        return

    draft = _unconfirmed_recommendations[msg_id]
    if user.id != draft["author_id"]:
        return

    emoji = str(reaction.emoji)

    if emoji in _CONFIRM_EMOJIS:
        _pending_recommendations.append(draft)
        del _unconfirmed_recommendations[msg_id]
        await reaction.message.reply(
            f"✅ **Recommendation confirmed and logged!** "
            f"It will appear in the next daily summary in `#{INSTRUCTOR_CHANNEL_NAME}`."
        )
    elif emoji in _REJECT_EMOJIS:
        del _unconfirmed_recommendations[msg_id]
        await reaction.message.reply("🗑️ Recommendation discarded. No worries!")


@tasks.loop(time=RECOMMENDATIONS_TIME)
async def daily_recommendations_summary():
    """Post accumulated recommendations to #bot-briefs at 18:01 daily."""
    # Skip weekends
    if datetime.now(REPORT_TZ).weekday() >= 5:
        return

    channel = await get_instructor_channel()
    if channel is None:
        return

    if not _pending_recommendations:
        # No recommendations today — skip silently
        return

    # Build the summary embed
    embed = discord.Embed(
        title="💡 Daily Recommendations Summary",
        description=(
            f"**{len(_pending_recommendations)}** recommendation(s) received today "
            f"via @AuthBot mentions."
        ),
        color=0xF39C12,  # Amber
    )
    embed.set_footer(
        text=f"Generated: {datetime.now(REPORT_TZ).strftime('%A, %B %d %Y • %H:%M %Z')}"
    )

    for i, rec in enumerate(_pending_recommendations[:25], start=1):  # Cap at 25
        embed.add_field(
            name=f"#{i} — {rec['author']} in #{rec['channel']}",
            value=rec["text"][:1024],  # Discord field value limit
            inline=False,
        )

    await channel.send(embed=embed)

    # Flush the day's recommendations
    _pending_recommendations.clear()


# ---------------------------------------------------------------------------
# Daily unregistered-users nudge  (posts to #general at 08:00 by default)
# ---------------------------------------------------------------------------

def build_unregistered_nudge_text() -> Optional[str]:
    """Build a message listing usernames that have reviews waiting but haven't
    registered yet.  Returns None if everyone is registered."""
    rows = DB.unregistered_usernames_with_pending_reviews()
    if not rows:
        return None

    lines: List[str] = []
    lines.append("**Peer reviews are waiting for you!**")
    lines.append(
        "The following students have feedback ready to be delivered, "
        "but haven't registered with the bot yet. "
        "Use `/register <your_rit_username>` to get caught up!"
    )
    lines.append("")

    for row in rows:
        count = row["pending_review_count"]
        review_word = "review" if count == 1 else "reviews"
        lines.append(f"- `{row['recipient_username']}` — {count} {review_word} waiting")

    return "\n".join(lines)


@tasks.loop(time=NUDGE_TIME)
async def daily_unregistered_nudge():
    # Skip weekends (Saturday=5, Sunday=6).
    if datetime.now(REPORT_TZ).weekday() >= 5:
        return

    channel = await get_general_channel()
    if channel is None:
        print(f"General channel '{GENERAL_CHANNEL_NAME}' not found; skipping unregistered nudge.")
        return

    message = build_unregistered_nudge_text()
    if message is None:
        return  # Everyone is registered — nothing to post.

    await channel.send(message)


# ---------------------------------------------------------------------------
# Daily deadline reminder  (posts to #deadlines at 08:00 by default)
# ---------------------------------------------------------------------------

@tasks.loop(time=NUDGE_TIME)
async def daily_deadline_reminder():
    # Skip weekends (Saturday=5, Sunday=6).
    if datetime.now(REPORT_TZ).weekday() >= 5:
        return

    channel = await get_deadlines_channel()
    if channel is None:
        print(f"Deadlines channel '{DEADLINES_CHANNEL_NAME}' not found; skipping deadline reminder.")
        return

    now = datetime.now(REPORT_TZ)
    message = build_deadline_reminder_text(now)
    if message is None:
        return  # Nothing due in the next 7 days.

    await channel.send(message)


@bot.tree.command(name="register", description="Register your Discord account to your RIT username.")
@app_commands.describe(rit_username="Your RIT username, e.g. abc1234")
async def register(interaction: discord.Interaction, rit_username: str):
    username = norm_username(rit_username)

    if username not in DATA.members_by_username:
        # Check if user is an instructor/TA — auto-create entry for staff
        # In guild context, interaction.user is already a discord.Member
        # Fall back to fetch_member if needed (e.g. DM context)
        staff = False
        if isinstance(interaction.user, discord.Member):
            staff = is_instructor(interaction.user)
        elif GUILD_ID:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                try:
                    member_obj = await guild.fetch_member(interaction.user.id)
                    staff = is_instructor(member_obj)
                except (discord.NotFound, discord.HTTPException):
                    pass

        if staff:
            DB.upsert_user(interaction.user.id, username)
            await interaction.response.send_message(
                f"✅ Registered as **staff**: `{username}` (not on the class roster — entry created automatically for instructor/TA).",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "I could not find that RIT username in the workbook. Please try again carefully. "
            "If you are sure it is correct, use `/username_help` so the instructors can investigate.",
            ephemeral=True,
        )
        return

    DB.upsert_user(interaction.user.id, username)

    member = DATA.members_by_username[username]

    await interaction.response.send_message(
        f"Registered as `{member.username}` on `{member.team}`.",
        ephemeral=True,
    )

    # Send any missed feedback to the newly registered user
    catchup_result = await DATA.catchup_handler.send_catchup_for_user(
            interaction.user.id,
            username
        )

    if catchup_result['assignments_count'] > 0:
        if catchup_result['success']:
            await interaction.followup.send(
                f"✅ Sent you {catchup_result['assignments_count']} assignment(s) of feedback you missed while unregistered!"
            )
        else:
            await interaction.followup.send(
                f"⚠️ Found {catchup_result['assignments_count']} assignment(s) with feedback, but had trouble sending them: {catchup_result['error']}"
            )


@bot.tree.command(name="username_help", description="Log a username mismatch for instructor review.")
@app_commands.describe(
    claimed_username="The username you believe is correct",
    note="Optional note for the instructors"
)
async def username_help(interaction: discord.Interaction, claimed_username: str, note: Optional[str] = ""):
    DB.log_username_help(interaction.user.id, claimed_username, note or "")
    await interaction.response.send_message(
        "Thanks. I logged that for the instructors and it will appear in the daily report.",
        ephemeral=True,
    )


@bot.tree.command(name="review", description="Get your next peer-review assignment.")
async def review(interaction: discord.Interaction):
    reviewer_username = DB.get_rit_username_for_discord(interaction.user.id)
    if reviewer_username is None:
        await interaction.response.send_message(
            "Please register first with `/register`.",
            ephemeral=True,
        )
        return

    submitted_count = DB.count_submitted_reviews(interaction.user.id)
    if submitted_count >= MAX_REVIEWS_PER_REVIEWER:
        await interaction.response.send_message(
            f"You have already completed the maximum of {MAX_REVIEWS_PER_REVIEWER} reviews.",
            ephemeral=True,
        )
        return

    open_assignment = DB.get_open_assignment(interaction.user.id)
    if open_assignment is not None:
        await interaction.response.send_message(
            "You already have an open assignment.\n\n"
            + format_assignment_message(open_assignment),
            view=StartReviewView(interaction.user.id, int(open_assignment["id"])),
            ephemeral=True,
        )
        return

    member = DATA.members_by_username.get(reviewer_username)
    if member is None:
        await interaction.response.send_message(
            "Your registration exists, but your username was not found in the workbook. "
            "Please notify the instructors.",
            ephemeral=True,
        )
        return

    assigned_team = choose_team_for_reviewer(interaction.user.id, member.team)
    if assigned_team is None:
        await interaction.response.send_message(
            "There are no remaining eligible teams for you to review.",
            ephemeral=True,
        )
        return

    asset = DATA.assets_by_team[assigned_team]
    assignment_id = DB.create_assignment(
        reviewer_discord_id=interaction.user.id,
        reviewer_username=reviewer_username,
        home_team=member.team,
        assigned_team=assigned_team,
        video_url=asset.video_url,
        wireframe_url=asset.wireframe_url,
    )

    row = DB.get_assignment(assignment_id)
    assert row is not None

    await interaction.response.send_message(
        "Here is your next assignment.\n\n" + format_assignment_message(row),
        view=StartReviewView(interaction.user.id, assignment_id),
        ephemeral=True,
    )


@bot.tree.command(name="status", description="See your registration and review progress.")
async def status(interaction: discord.Interaction):
    reviewer_username = DB.get_rit_username_for_discord(interaction.user.id)
    if reviewer_username is None:
        await interaction.response.send_message(
            "You are not registered yet. Use `/register` first.",
            ephemeral=True,
        )
        return

    submitted_count = DB.count_submitted_reviews(interaction.user.id)
    open_assignment = DB.get_open_assignment(interaction.user.id)
    member = DATA.members_by_username[reviewer_username]

    message = [
        f"Registered as `{reviewer_username}` on `{member.team}`.",
        f"Completed reviews: **{submitted_count}/{MAX_REVIEWS_PER_REVIEWER}**",
    ]

    if open_assignment:
        message.append("")
        message.append("**Current open assignment**")
        message.append(format_assignment_message(open_assignment))

    await interaction.response.send_message("\n".join(message), ephemeral=True)


@bot.tree.command(name="reload_data", description="Reload the Excel workbook from disk.")
async def reload_data(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_instructor(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    try:
        DATA.load()
        await interaction.response.send_message("Workbook reloaded successfully.", ephemeral=True)
    except Exception as exc:
        await interaction.response.send_message(f"Reload failed: {exc}", ephemeral=True)


@bot.tree.command(name="send_daily_report_now", description="Send the instructor summary immediately.")
async def send_daily_report_now(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_instructor(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    channel = await get_instructor_channel()
    if channel is None:
        await interaction.response.send_message(
            f"I could not find `#{INSTRUCTOR_CHANNEL_NAME}`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Header embed
    header_embed = discord.Embed(
        title="📋 CSEC-472 Daily Brief",
        description=f"Generated: {datetime.now(REPORT_TZ).strftime('%A, %B %d %Y • %H:%M %Z')} *(manual trigger)*",
        color=0x2ECC71,
    )
    header_embed.set_footer(text="AuthBot • CSEC-472 Peer Review System")
    await channel.send(embed=header_embed)

    # Peer review section
    review_text = build_daily_report_text()
    review_embed = discord.Embed(
        title="📝 Peer Review Summary",
        description=review_text,
        color=0x3498DB,
    )
    await channel.send(embed=review_embed)

    await interaction.followup.send("Daily report sent.", ephemeral=True)


@bot.tree.command(name="send_weekly_report_now", description="Send the weekly game performance report immediately.")
async def send_weekly_report_now(interaction: discord.Interaction):
    if not is_instructor(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    channel = await get_instructor_channel()
    if channel is None:
        await interaction.response.send_message(
            f"I could not find `#{INSTRUCTOR_CHANNEL_NAME}`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Header embed
    header_embed = discord.Embed(
        title="🎮 CSEC-472 Weekly Agent Performance Brief",
        description=f"Generated: {datetime.now(REPORT_TZ).strftime('%A, %B %d %Y • %H:%M %Z')} *(manual trigger)*",
        color=0x9B59B6,
    )
    header_embed.set_footer(text="AuthBot • Papers Please Game Analytics")
    await channel.send(embed=header_embed)

    # Game performance section
    game_embed = build_game_report_embed()
    if game_embed:
        await channel.send(embed=game_embed)

    # Charts
    try:
        charts = await build_game_report_charts()
        for chart_file in charts:
            await channel.send(file=chart_file)
    except Exception as exc:
        print(f"[Report] Chart generation error: {exc}")

    await interaction.followup.send("Weekly game report sent.", ephemeral=True)


@bot.tree.command(name="upcoming", description="See upcoming assignment and exam deadlines.")
@app_commands.describe(days="How many days to look ahead (default 7)")
async def upcoming(interaction: discord.Interaction, days: Optional[int] = 7):
    lookahead = max(1, min(days or 7, 30))  # clamp between 1 and 30
    now = datetime.now(REPORT_TZ)
    embed = build_upcoming_embed(now, lookahead_days=lookahead)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="office_hours", description="See who has office hours right now and when the next sessions are.")
async def office_hours(interaction: discord.Interaction):
    now = datetime.now(REPORT_TZ)
    embed = build_office_hours_embed(now)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="dadjoke", description="Post a random dad joke to #extracurricular.")
async def dadjoke(interaction: discord.Interaction):
    # Find the extracurricular channel
    if GUILD_ID is None:
        await interaction.response.send_message(
            "Guild ID is not configured.",
            ephemeral=True,
        )
        return

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except discord.DiscordException:
            await interaction.response.send_message(
                "Could not find the server.",
                ephemeral=True,
            )
            return

    target_channel = None
    for channel in guild.text_channels:
        if channel.name == DADJOKE_CHANNEL_NAME:
            target_channel = channel
            break

    if target_channel is None:
        await interaction.response.send_message(
            f"Could not find `#{DADJOKE_CHANNEL_NAME}` channel.",
            ephemeral=True,
        )
        return

    # Fetch a random dad joke from icanhazdadjoke.com
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Accept": "application/json",
                "User-Agent": "AuthBot Discord Bot (https://github.com/JP3L/CSEC-472-bot)",
            }
            async with session.get("https://icanhazdadjoke.com/", headers=headers) as resp:
                if resp.status != 200:
                    await interaction.response.send_message(
                        "Could not fetch a dad joke right now. Try again later.",
                        ephemeral=True,
                    )
                    return
                data = await resp.json()
                joke = data.get("joke", "I ran out of dad jokes... that's no joke.")
    except Exception as exc:
        await interaction.response.send_message(
            f"Error fetching dad joke: {exc}",
            ephemeral=True,
        )
        return

    # Post the joke to the extracurricular channel
    await target_channel.send(f"**Dad Joke of the Moment**\n\n{joke}")

    # Send ephemeral DM note to the user who called the command
    await interaction.response.send_message(
        f"I've pushed a dad joke to #{DADJOKE_CHANNEL_NAME}... everyone (well, maybe only some people) "
        "likes a good dad joke but no one appreciates a channel spammer, so please use this with discretion.",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Papers Please – /play command (DM-based, registration-gated)
# ---------------------------------------------------------------------------


@bot.tree.command(
    name="play",
    description="Start a Papers Please checkpoint game in your DMs",
)
async def play_command(interaction: discord.Interaction):
    """Launch a new Papers Please game session — requires /register first."""
    user = interaction.user

    # ── Registration gate ────────────────────────────────────────
    rit_username = DB.get_rit_username_for_discord(user.id)

    if rit_username is None:
        # Not registered at all — check if they're an instructor/TA
        is_staff = (
            isinstance(user, discord.Member)
            and is_instructor(user)
        )
        if is_staff:
            # Instructors/TAs: prompt for manual registration
            await interaction.response.send_message(
                "You're not registered yet. As an instructor/TA, please use "
                "`/register <your_rit_username>` first. If your username isn't in "
                "the class roster, an entry will be created automatically for staff.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "⚠️ **Registration Required**\n\n"
                "You must `/register` with your RIT username before playing.\n"
                "This links your Discord account to your student record so we can "
                "track your progress for CSEC-472.\n\n"
                "Please double-check your RIT UID (e.g. `abc1234`) and ensure "
                "you're enrolled in this semester's AUTH course.",
                ephemeral=True,
            )
        return

    # Verify the username is in the class Excel (or they're staff)
    norm_name = norm_username(rit_username)
    if norm_name not in DATA.members_by_username:
        # Username registered but not on roster — might be staff
        is_staff = (
            isinstance(user, discord.Member)
            and is_instructor(user)
        )
        if not is_staff:
            await interaction.response.send_message(
                f"⚠️ Your registered username `{rit_username}` is not on the class roster.\n\n"
                "Please verify:\n"
                "1. Your RIT UID is correct (double/triple-check)\n"
                "2. You're enrolled in this semester's CSEC-472 AUTH course\n"
                "3. Use `/register <correct_uid>` to update your registration\n\n"
                "If you believe this is an error, contact your instructor.",
                ephemeral=True,
            )
            return

    # ── Existing session check ───────────────────────────────────
    if game_sessions.has_active_session(user.id):
        await interaction.response.send_message(
            "You already have an active game session! Check your DMs.\n"
            "Use `/quit_game` to end it first.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    # ── Create DM channel ────────────────────────────────────────
    try:
        dm_channel = await user.create_dm()
    except discord.Forbidden:
        await interaction.followup.send(
            "I can't DM you. Please enable DMs from server members "
            "in your Discord privacy settings and try again.",
            ephemeral=True,
        )
        return

    # ── Create session ───────────────────────────────────────────
    session = game_sessions.create_session(user.id, rit_username=rit_username)
    session.generate_next_round()

    # Send intro
    intro_embed = build_intro_embed()
    await dm_channel.send(embed=intro_embed)

    # CERBERUS greeting
    cerberus_embed = build_cerberus_embed(CERBERUS.GREETING)
    await dm_channel.send(embed=cerberus_embed)

    # First directive — pin it
    directive_embed = build_directive_embed(
        session.current_directive, session.difficulty
    )
    directive_msg = await dm_channel.send(embed=directive_embed)
    try:
        await unpin_bot_messages(dm_channel, bot.user.id)
        await directive_msg.pin()
        session.pinned_directive_msg_id = directive_msg.id
    except discord.Forbidden:
        pass

    # First entrant with action buttons
    entrant_embed = build_entrant_embed(
        session.current_entrant,
        session.total_entrants_seen,
        session,
    )
    view = GameActionView(session)
    await dm_channel.send(embed=entrant_embed, view=view)

    await interaction.followup.send(
        "🎮 **Game started!** Check your DMs for your checkpoint assignment.\n"
        f"Playing as `{rit_username}`. Good luck, Agent.",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Papers Please – /cerberus command (query the AI tutor)
# ---------------------------------------------------------------------------


@bot.tree.command(
    name="cerberus",
    description="Ask CERBERUS about an authentication or security concept",
)
@app_commands.describe(
    topic="A keyword or concept (e.g. kerberos, mfa, expired, rbac, tls, oauth, 'deep dive tls')"
)
async def cerberus_command(interaction: discord.Interaction, topic: str):
    """Query the CERBERUS AI tutor for CSEC-472 concept help."""
    if topic.lower().strip() in ("help", "topics", "list"):
        response = CERBERUS.get_topic_list()
    else:
        response = CERBERUS.get_concept_help(topic)

    if response is None:
        response = (
            f"I don't have a specific entry for **{topic}**, but here's a general advisory:\n\n"
            f"{CERBERUS.get_random_tip()}\n\n"
            f"Try `/cerberus topics` to see everything I can help with, or add "
            f"'deep dive' to any topic for extended protocol analysis."
        )

    embed = build_cerberus_embed(response)
    # Split if too long for one embed (Discord 4096 char limit)
    if len(response) > 4000:
        parts = [response[i:i+3900] for i in range(0, len(response), 3900)]
        for i, part in enumerate(parts):
            e = build_cerberus_embed(part)
            if i == 0:
                await interaction.response.send_message(embed=e, ephemeral=True)
            else:
                await interaction.followup.send(embed=e, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Papers Please – /quit_game command
# ---------------------------------------------------------------------------


@bot.tree.command(
    name="quit_game",
    description="End your current Papers Please game session",
)
async def quit_game_command(interaction: discord.Interaction):
    """End the current game session with a final summary."""
    session = game_sessions.get_session(interaction.user.id)
    if session is None:
        await interaction.response.send_message(
            "You don't have an active game session. Use `/play` to start one.",
            ephemeral=True,
        )
        return

    view = QuitConfirmView(session)
    await interaction.response.send_message(
        "Are you sure you want to end your current session?",
        view=view,
        ephemeral=True,
    )


if __name__ == "__main__":
    bot.run(TOKEN)
