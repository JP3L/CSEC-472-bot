# AuthBot — CSEC-472 Peer Review & Cybersecurity Training Platform

A Discord bot for RIT's CSEC-472 (Authentication) course that combines peer review management with an educational cybersecurity game inspired by *Papers, Please*. Students register with their RIT username, complete rubric-based peer reviews, and play a checkpoint-inspection game where every document maps to a real authentication protocol from the syllabus.

**Repository:** [github.com/JP3L/CSEC-472-bot](https://github.com/JP3L/CSEC-472-bot)

---

## Features

**Peer Review System** — Assigns teams for cross-review, collects Likert scores and written feedback through Discord modals, and delivers completed reviews by DM to each team member. Tracks delivery failures and catches up newly registered users on missed feedback.

**Papers Please Game** — A cyberpunk-themed checkpoint inspection game played in Discord DMs. Players review digital credentials, cross-reference documents against a security directive, and decide whether to allow, deny, or detain each entrant. Difficulty scales from level 0 (basic ID checks) through level 8 (OMEGA clearance with multi-document cross-validation, wanted handles, and operator-level requirements).

**CERBERUS AI Tutor** — A three-headed guardian AI (named for the mythological gatekeeper) whose heads represent the three authentication factors: something you know, something you have, and something you are. During gameplay, CERBERUS performs context-aware document analysis — detecting handle mismatches, expired credentials, and policy violations — and explains the underlying protocol (TLS, Kerberos, OAuth, etc.) that each finding relates to. Flagged fields are highlighted with visual markers in the entrant display.

**Concept Review Questions** — Multiple-choice questions interleaved during gameplay covering Kerberos, TLS/PKI, OAuth 2.0, MFA, cryptography, RBAC, password security, and network security. Results are tracked per student and per topic for instructor reporting.

**Daily Instructor Brief** — An automated executive-style report pushed to `#instructors` each weekday with peer review statistics, game leaderboards, concept mastery breakdowns by topic, milestone achievements, and matplotlib-generated charts (accuracy, difficulty progression, topic performance, session activity).

**Course Utilities** — Office hours display with live "available now" detection, upcoming deadline tracking with daily reminders to `#deadlines`, and a dad joke command for `#extracurricular`.

---

## Slash Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/register <rit_username>` | Link Discord account to RIT username. Auto-creates entry for instructors/TAs not on the roster. Sends any missed feedback. | Everyone |
| `/review` | Get next peer review assignment (max 3). Opens score modal then comments modal. | Registered users |
| `/play` | Start Papers Please game session in DMs. Requires registration. | Registered users |
| `/cerberus <topic>` | Ask CERBERUS about a security concept. Add "deep dive" for extended explanations. | Everyone |
| `/quit_game` | End current game session with confirmation. | Active players |
| `/upcoming [days]` | Show upcoming deadlines (1-30 day lookahead, default 7). | Everyone |
| `/office_hours` | Show current availability, next sessions, and full weekly schedule. | Everyone |
| `/dadjoke` | Post a random dad joke to `#extracurricular`. | Everyone |
| `/status` | View personal registration and review progress. | Everyone |
| `/username_help <username> [note]` | Log a username mismatch for instructor review. | Everyone |
| `/send_daily_report_now` | Trigger the daily instructor report immediately. | Instructors |
| `/reload_data` | Reload the Excel workbook from disk. | Instructors |

---

## Papers Please — Game Mechanics

The game is set in 2032 at a UACC (United Allied Cyber Command) checkpoint. Players act as border agents inspecting digital credentials during a fictional cyberwar. Each game mechanic maps directly to CSEC-472 course material:

| Game Element | Course Concept |
|---|---|
| Digital Identity Certificate | TLS/PKI, X.509 certificates |
| Biometric Authentication Badge | Multi-factor authentication (inherence factor) |
| Network Access Token | OAuth 2.0 bearer tokens, Kerberos TGTs |
| Contractor Clearance Code | Authorization, RBAC, least privilege |
| Asylum Encryption Key | Cryptographic key management |
| Diplomatic Cipher Channel | Secure communication protocols (TLS, SSH) |
| Integrity Report | System monitoring, IDS/HIDS |
| Wanted Handle (CRL check) | Certificate Revocation Lists, OCSP |
| Cross-document field mismatch | Clark-Wilson integrity model |
| Faction deny list | Mandatory/role-based access control |

The game tracks 14 milestones across score, streak, difficulty, and knowledge categories. Three strikes end the session, and difficulty increases every 5 correct decisions.

---

## Architecture

```
bot.py                          Main bot: commands, database, scheduled tasks
catchup_handler.py              Send missed feedback to newly registered users

papers_please/
  __init__.py                   Package exports
  models.py                     Document, Entrant, SecurityDirective, GameState, InspectionResult
  engine.py                     Core inspection validation logic
  generator.py                  Procedural directive & entrant generation (scales with difficulty)
  session.py                    PlayerSession, GameDatabase, SessionManager
  assistant.py                  CERBERUS AI tutor with concept map and deep dives
  questions.py                  50+ concept review questions across 10 topics
  views.py                      Discord embeds, buttons, modals, field highlighting
  charts.py                     Matplotlib chart generation (cyberpunk theme)
  theme.py                      Factions, document types, field definitions, flavor text
```

---

## Database Schema

AuthBot uses a single SQLite database (default: `peer_reviews.db`) with tables for both peer review and game tracking.

**Peer review tables:** `users` (discord_id to rit_username mapping), `assignments` (review assignments with rubric scores and comments), `username_help_logs`, `delivery_failures`.

**Game tables:** `game_sessions` (per-session stats including score, accuracy, difficulty, duration, milestones), `game_question_results` (per-question results with topic tracking for mastery analysis).

---

## Setup

### Prerequisites

- Python 3.10+
- A Discord bot token with Message Content intent enabled
- The course roster Excel workbook

### Installation

```bash
git clone https://github.com/JP3L/CSEC-472-bot.git
cd CSEC-472-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Configuration

Edit `.env` with your values:

```env
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=your_guild_id

# Channel names (defaults shown)
INSTRUCTOR_CHANNEL_NAME=instructors
DEADLINES_CHANNEL_NAME=deadlines
GENERAL_CHANNEL_NAME=general

# Files
EXCEL_FILE=Teams-WireFrames.xlsx
DATABASE_FILE=peer_reviews.db

# Scheduling (defaults shown, America/New_York timezone)
DAILY_REPORT_HOUR=18
DAILY_REPORT_MINUTE=0
NUDGE_HOUR=8
NUDGE_MINUTE=0
```

### Workbook Requirements

Place your Excel workbook (default: `Teams-WireFrames.xlsx`) in the project root with two sheets:

- **Username-Team Mappings** — columns: `Group Name`, `Username`, `First Name`, `Last Name`, `Email Address`
- **Assigned Team Links** — columns: `Assigned Team`, `Video Link`, `Wireframe PDF`

### Discord Server Setup

Required channels: `#instructors` (daily reports), `#deadlines` (deadline reminders). Optional: `#extracurricular` (dad jokes), `#general` (nudge messages).

The bot detects instructors by checking for `manage_guild` or `administrator` permissions, or membership in a role named "instructor" or "instructors".

### Running

```bash
python bot.py
```

### Office Hours

The `/office_hours` command ships with Spring 2026 defaults. Override by setting `OFFICE_HOURS_JSON` in `.env`:

```json
[{
  "name": "Jane Doe",
  "role": "Instructor",
  "email": "jd@rit.edu",
  "location": "CYB-1234",
  "zoom": "https://rit.zoom.us/...",
  "hours": [{ "days": [1, 3], "start": "15:30", "end": "16:30" }]
}]
```

Days use Python weekday numbers (Monday=0 through Sunday=6). Times are 24-hour format in `REPORT_TIMEZONE`.

---

## Dependencies

```
discord.py>=2.6,<3
pandas>=2,<3
openpyxl>=3.1,<4
python-dotenv>=1.0,<2
backports.zoneinfo
matplotlib>=3.7,<4
```

---

## License

CSEC-472 course infrastructure, RIT. Built for the Spring 2026 semester.
