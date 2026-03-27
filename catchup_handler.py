"""
Catchup Handler for CSEC-472-bot

This module provides functionality to catch newly registered users up on feedback
they missed while unregistered. When a user registers, any failed DM deliveries
due to lack of registration are retrieved and resent.

Usage:
    Import and call after user registration:

    from catchup_handler import CatchupHandler

    handler = CatchupHandler(bot, database)
    await handler.send_catchup_for_user(discord_id, rit_username)
"""

import discord
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CatchupHandler:
    """Handles catchup messages for newly registered users."""

    def __init__(self, bot, database):
        """
        Initialize the catchup handler.

        Args:
            bot: The discord.ext.commands.Bot instance
            database: The Database instance from bot.py
        """
        self.bot = bot
        self.db = database

    async def send_catchup_for_user(self, discord_id: int, rit_username: str) -> dict:
        """
        Send catchup feedback to a newly registered user.

        This function:
        1. Queries for any failed delivery attempts for this user
        2. Retrieves the feedback content from those assignments
        3. Sends a compiled catchup message to the user
        4. Cleans up the delivery_failure records

        Args:
            discord_id: Discord user ID of the newly registered user
            rit_username: RIT username of the newly registered user

        Returns:
            dict with keys:
                - 'success': bool indicating if catchup was sent
                - 'assignments_count': number of assignments they were missing feedback for
                - 'error': error message if something went wrong
        """
        try:
            # Normalize username (lowercase, strip whitespace)
            rit_username = rit_username.strip().lower()

            # Query for failed deliveries for this user due to non-registration
            failed_deliveries = self._get_failed_deliveries_for_user(rit_username)

            if not failed_deliveries:
                logger.info(f"No missed feedback for {rit_username}")
                return {
                    'success': True,
                    'assignments_count': 0,
                    'error': None
                }

            # Fetch user object
            user = self.bot.get_user(discord_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(discord_id)
                except discord.NotFound:
                    return {
                        'success': False,
                        'assignments_count': 0,
                        'error': f"Could not find Discord user {discord_id}"
                    }

            # Build and send catchup message
            catchup_message = self._build_catchup_message(failed_deliveries)

            try:
                await user.send(catchup_message)
                logger.info(f"Sent catchup message to {rit_username} ({discord_id})")
            except discord.Forbidden:
                return {
                    'success': False,
                    'assignments_count': len(failed_deliveries),
                    'error': f"Bot cannot send DMs to {rit_username} (privacy settings)"
                }
            except discord.HTTPException as e:
                return {
                    'success': False,
                    'assignments_count': len(failed_deliveries),
                    'error': f"HTTP error sending DM: {e}"
                }

            # Clean up delivery_failure records for this user
            self._cleanup_delivery_failures(rit_username)

            return {
                'success': True,
                'assignments_count': len(failed_deliveries),
                'error': None
            }

        except Exception as e:
            logger.error(f"Error in send_catchup_for_user: {e}", exc_info=True)
            return {
                'success': False,
                'assignments_count': 0,
                'error': str(e)
            }

    def _get_failed_deliveries_for_user(self, rit_username: str) -> list:
        """
        Query the database for failed delivery attempts for a user.

        Args:
            rit_username: RIT username to search for

        Returns:
            List of dicts with keys: assignment_id, recipient_username, reason, created_at
        """
        # Get failed deliveries where user was marked as unregistered
        query = """
            SELECT assignment_id, recipient_username, reason, created_at
            FROM delivery_failures
            WHERE recipient_username = ?
            AND reason LIKE '%not registered%'
            ORDER BY created_at ASC
        """

        rows = self.db.conn.execute(query, (rit_username,)).fetchall()

        # Convert to list of dicts
        return [
            {
                'assignment_id': row[0],
                'recipient_username': row[1],
                'reason': row[2],
                'created_at': row[3]
            }
            for row in rows
        ]

    def _build_catchup_message(self, failed_deliveries: list) -> str:
        """
        Build a formatted catchup message with all missed feedback.

        Args:
            failed_deliveries: List of failed delivery dicts

        Returns:
            Formatted Discord message string
        """
        message = "**Getting you caught up on your peer's feedback!** 📋\n\n"
        message += f"We have {len(failed_deliveries)} assignment(s) with feedback that were waiting for you to register.\n\n"

        for i, delivery in enumerate(failed_deliveries, 1):
            assignment_id = delivery['assignment_id']
            created_at = delivery['created_at']

            # Fetch assignment details
            assignment = self.db.get_assignment(assignment_id)
            if assignment:
                message += self._format_assignment_feedback(assignment, i)
            else:
                message += f"**Assignment #{i}** (ID: {assignment_id})\n"
                message += f"_Failed to retrieve details, but feedback was submitted on {created_at}_\n\n"

        message += "---\n"
        message += "Thank you for registering! You're all caught up. ✅"

        return message

    def _format_assignment_feedback(self, assignment: tuple, index: int) -> str:
        """
        Format a single assignment's feedback into readable text.

        Args:
            assignment: Tuple from get_assignment()
            index: Sequential number for display

        Returns:
            Formatted assignment feedback string
        """
        # Unpack assignment tuple (based on bot.py schema)
        # Structure: (id, reviewer_discord_id, reviewer_username, home_team, assigned_team,
        #             video_url, wireframe_url, status, assigned_at, submitted_at,
        #             intro_score, background_score, method_score, findings_score, references_score,
        #             intro_comment, background_comment, method_comment, findings_comment, references_comment)

        assignment_id = assignment[0]
        reviewer_username = assignment[2]
        home_team = assignment[3]
        assigned_team = assignment[4]
        intro_score = assignment[10]
        background_score = assignment[11]
        method_score = assignment[12]
        findings_score = assignment[13]
        references_score = assignment[14]
        intro_comment = assignment[15]
        background_comment = assignment[16]
        method_comment = assignment[17]
        findings_comment = assignment[18]
        references_comment = assignment[19]

        formatted = f"**Assignment #{index}** (ID: {assignment_id})\n"
        formatted += f"Reviewer: `{reviewer_username}` from `{home_team}`\n"
        formatted += f"Review Target: `{assigned_team}`\n\n"

        # Add scores and comments
        if intro_score:
            formatted += f"**Introduction**: {intro_score}/5"
            if intro_comment:
                formatted += f" — _{intro_comment}_"
            formatted += "\n"

        if background_score:
            formatted += f"**Background**: {background_score}/5"
            if background_comment:
                formatted += f" — _{background_comment}_"
            formatted += "\n"

        if method_score:
            formatted += f"**Method**: {method_score}/5"
            if method_comment:
                formatted += f" — _{method_comment}_"
            formatted += "\n"

        if findings_score:
            formatted += f"**Findings**: {findings_score}/5"
            if findings_comment:
                formatted += f" — _{findings_comment}_"
            formatted += "\n"

        if references_score:
            formatted += f"**References**: {references_score}/5"
            if references_comment:
                formatted += f" — _{references_comment}_"
            formatted += "\n"

        formatted += "\n"
        return formatted

    def _cleanup_delivery_failures(self, rit_username: str) -> int:
        """
        Remove delivery_failure records for a user (they've been caught up).

        Args:
            rit_username: RIT username to clean up

        Returns:
            Number of records deleted
        """
        query = """
            DELETE FROM delivery_failures
            WHERE recipient_username = ?
            AND reason LIKE '%not registered%'
        """

        cursor = self.db.conn.execute(query, (rit_username,))
        self.db.conn.commit()

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} delivery_failure records for {rit_username}")

        return deleted_count


# Integration instructions for bot.py:
#
# 1. Add this import near the top of bot.py:
#    from catchup_handler import CatchupHandler
#
# 2. In the PeerReviewBot.__init__() method, add:
#    self.catchup_handler = CatchupHandler(self, DB)
#
# 3. In the /register command, after successful registration, add:
#
#    result = await bot.catchup_handler.send_catchup_for_user(
#        interaction.user.id,
#        username
#    )
#
#    if result['assignments_count'] > 0:
#        if result['success']:
#            await interaction.followup.send(
#                f"✅ Sent you {result['assignments_count']} assignment(s) of feedback you missed!"
#            )
#        else:
#            await interaction.followup.send(
#                f"⚠️ Found {result['assignments_count']} assignment(s) with feedback, but had trouble sending: {result['error']}"
#            )
