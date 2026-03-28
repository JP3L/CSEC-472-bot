# RIT Peer Review Discord Bot

## What it does
- Registers Discord users to RIT usernames
- Looks up each user’s home team from `Teams-WireFrames.xlsx`
- Assigns a different team to review, avoiding repeats
- Limits each reviewer to 3 completed reviews
- Presents the review in two steps:
  - 5 Likert scores
  - 5 written comments
- Sends each completed named review by DM to every registered member of the reviewed team
- Sends a daily summary to `#instructors`
- Shows real-time office-hours availability via `/office_hours`

## Workbook requirements
Place `Teams-WireFrames.xlsx` in the project root.

Expected sheet names:
- `Username-Team Mappings`
- `Assigned Team Links`

Expected columns:
- Tab 1: `Group Name`, `Username`, `First Name`, `Last Name`, `Email Address`
- Tab 2: `Assigned Team`, `Video Link`, `Wireframe PDF`

## Office hours

The `/office_hours` command ships with defaults matching the Spring 2026 syllabus.
To override, set `OFFICE_HOURS_JSON` in `.env` to a JSON array — each element is:

```json
{
  "name": "Jane Doe",
  "role": "Instructor",
  "email": "jd@rit.edu",
  "location": "CYB-1234",
  "zoom": "https://rit.zoom.us/...",
  "hours": [
    { "days": [1, 3], "start": "15:30", "end": "16:30" }
  ]
}
```

`days` uses Python weekday numbers: Monday=0 through Sunday=6.
Times are in 24-hour format and interpreted in `REPORT_TIMEZONE`.

## Local setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
python bot.py
