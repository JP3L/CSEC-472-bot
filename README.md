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

## Workbook requirements
Place `Teams-WireFrames.xlsx` in the project root.

Expected sheet names:
- `Username-Team Mappings`
- `Assigned Team Links`

Expected columns:
- Tab 1: `Group Name`, `Username`, `First Name`, `Last Name`, `Email Address`
- Tab 2: `Assigned Team`, `Video Link`, `Wireframe PDF`

## Local setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
python bot.py
