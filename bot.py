import os
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, List, Optional
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

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID_RAW = os.getenv("DISCORD_GUILD_ID", "").strip()
GUILD_ID = int(GUILD_ID_RAW) if GUILD_ID_RAW else None
INSTRUCTOR_CHANNEL_NAME = os.getenv("INSTRUCTOR_CHANNEL_NAME", "instructors").strip()
EXCEL_FILE = os.getenv("EXCEL_FILE", "Teams-WireFrames.xlsx").strip()
DATABASE_FILE = os.getenv("DATABASE_FILE", "peer_reviews.db").strip()
REPORT_TIMEZONE = os.getenv("REPORT_TIMEZONE", "America/New_York").strip()
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "18"))
DAILY_REPORT_MINUTE = int(os.getenv("DAILY_REPORT_MINUTE", "0"))
MAX_REVIEWS_PER_REVIEWER = 3

if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing from environment.")
if not os.path.exists(EXCEL_FILE):
    raise RuntimeError(f"Workbook not found: {EXCEL_FILE}")

GUILD_OBJECT = discord.Object(id=GUILD_ID) if GUILD_ID else None
REPORT_TZ = ZoneInfo(REPORT_TIMEZONE)
REPORT_TIME = time(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE, tzinfo=REPORT_TZ)


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

        await interaction.response.send_message(message, ephemeral=True)


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
        if not daily_instructor_report.is_running():
            daily_instructor_report.start()


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


async def deliver_feedback(assignment_id: int) -> tuple[list[str], list[str]]:
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
    reviewer_rows = DB.reviewer_completion_rows()
    team_rows = DB.team_received_rows()
    username_help_rows = DB.recent_username_help_rows()
    delivery_failure_rows = DB.recent_delivery_failure_rows()

    lines = []
    lines.append("**Daily Peer Review Summary**")
    lines.append(f"Generated: {datetime.now(REPORT_TZ).strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append("")

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
    lines.append("**Username disputes / insistence logs (last 24h)**")
    if username_help_rows:
        for row in username_help_rows:
            note = row["note"] or "(no note)"
            lines.append(
                f"- discord_id `{row['discord_id']}` claimed `{row['claimed_username']}` at {row['created_at']} — {note}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("**DM delivery failures (last 24h)**")
    if delivery_failure_rows:
        for row in delivery_failure_rows:
            lines.append(
                f"- assignment `{row['assignment_id']}`, recipient `{row['recipient_username']}` at {row['created_at']} — {row['reason']}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines[:1900])


@tasks.loop(time=REPORT_TIME)
async def daily_instructor_report():
    channel = await get_instructor_channel()
    if channel is None:
        print(f"Instructor channel '{INSTRUCTOR_CHANNEL_NAME}' not found.")
        return

    await channel.send(build_daily_report_text())


@bot.tree.command(name="register", description="Register your Discord account to your RIT username.")
@app_commands.describe(rit_username="Your RIT username, e.g. abc1234")
async def register(interaction: discord.Interaction, rit_username: str):
    username = norm_username(rit_username)

    if username not in DATA.members_by_username:
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
    catchup_result = await interaction.client.catchup_handler.send_catchup_for_user(
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

    await channel.send(build_daily_report_text())
    await interaction.response.send_message("Instructor report sent.", ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
