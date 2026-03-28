"""
Discord UI components for the Papers Please game.
Embeds, buttons, and views for DM-based gameplay.
"""

import discord
from discord import ui
from typing import Optional

from . import theme
from .models import Entrant, SecurityDirective, InspectionResult, GameState
from .session import PlayerSession, game_sessions
from .assistant import DAEMON


# ============================================================================
# EMBED BUILDERS
# ============================================================================


def build_directive_embed(directive: SecurityDirective, difficulty: int) -> discord.Embed:
    """Build an embed displaying the current Security Directive."""
    embed = discord.Embed(
        title=f"⚡ SECURITY DIRECTIVE — Level {difficulty}",
        description=directive.raw_text,
        color=0xFF4500,
    )
    embed.set_footer(text="UACC Cyber Division • Directive in effect until further notice")
    return embed


def build_entrant_embed(
    entrant: Entrant,
    entrant_number: int,
    session: PlayerSession,
) -> discord.Embed:
    """Build an embed displaying an entrant's documents for inspection."""
    embed = discord.Embed(
        title=f"👤 ENTRANT #{entrant_number}",
        description=(
            "A figure approaches your checkpoint terminal. "
            "Review the following digital credentials and make your decision."
        ),
        color=0x00BFFF,
    )

    for doc in entrant.documents:
        doc_name = theme.DOCUMENT_TYPES.get(doc.doc_type, doc.doc_type)
        field_lines = []
        if doc.doc_type in theme.DOCUMENT_FIELDS:
            for field_name in theme.DOCUMENT_FIELDS[doc.doc_type]:
                if field_name in doc.fields:
                    field_lines.append(f"`{field_name}:` {doc.fields[field_name]}")
        value_text = "\n".join(field_lines) if field_lines else "*No data*"
        embed.add_field(name=f"📄 {doc_name}", value=value_text, inline=False)

    # Score bar in footer
    gs = session.game_state
    strikes_display = "🔴" * gs.strikes + "⚫" * (gs.max_strikes - gs.strikes)
    embed.set_footer(
        text=(
            f"Score: {gs.score}/{gs.entrants_processed} • "
            f"Strikes: {strikes_display} • "
            f"Difficulty: Lv{session.difficulty} • "
            f"Streak: {session.correct_streak}"
        )
    )
    return embed


def build_result_embed(
    is_correct: bool,
    result: InspectionResult,
    player_decision: str,
    session: PlayerSession,
    difficulty_increased: bool,
) -> discord.Embed:
    """Build an embed showing the result of the player's decision."""
    if is_correct:
        embed = discord.Embed(
            title="✅ CORRECT",
            description=f"**Decision:** {result.decision.upper()}\n**Reason:** {result.reason}",
            color=0x00FF00,
        )
        if difficulty_increased:
            embed.add_field(
                name="⚡ DIFFICULTY INCREASED",
                value=f"Advancing to Level {session.difficulty}. New Security Directive incoming.",
                inline=False,
            )
    else:
        embed = discord.Embed(
            title="❌ INCORRECT",
            description=(
                f"**Your Decision:** {player_decision.upper()}\n"
                f"**Correct Decision:** {result.decision.upper()}\n"
                f"**Reason:** {result.reason}"
            ),
            color=0xFF0000,
        )
        gs = session.game_state
        embed.add_field(
            name="Strike",
            value=f"{'🔴' * gs.strikes}{'⚫' * (gs.max_strikes - gs.strikes)}",
            inline=False,
        )

    return embed


def build_game_over_embed(session: PlayerSession) -> discord.Embed:
    """Build the game-over embed with final stats."""
    embed = discord.Embed(
        title="💀 GAME OVER — CLEARANCE REVOKED",
        description=session.get_game_over_summary(),
        color=0x8B0000,
    )
    embed.set_footer(text="Type /play to start a new session.")
    return embed


def build_intro_embed() -> discord.Embed:
    """Build the game introduction embed."""
    embed = discord.Embed(
        title="🌐 UACC DIGITAL CHECKPOINT — STATION ACTIVE",
        description=theme.GAME_INTRO,
        color=0x9B59B6,
    )
    embed.add_field(
        name="How to Play",
        value=(
            "Entrants will present their digital credentials.\n"
            "Review their documents against the **Security Directive**.\n"
            "Choose **ALLOW**, **DENY**, or **DETAIN**.\n\n"
            "• **ALLOW** — Credentials are valid, grant network access\n"
            "• **DENY** — Missing/expired docs or restricted faction\n"
            "• **DETAIN** — Document fraud detected (mismatched fields) or wanted suspect\n\n"
            "3 strikes and your clearance is revoked."
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{DAEMON.AVATAR_EMOJI} DAEMON Assistant",
        value=(
            "Your embedded AI security advisor is online.\n"
            "Use the **Ask DAEMON** button for contextual hints, or "
            "use `/daemon <topic>` to learn about authentication concepts.\n"
            "DAEMON maps game mechanics to your **CSEC-472** coursework."
        ),
        inline=False,
    )
    embed.set_footer(text="UACC Cyber Division • Authentication Training Module v3.2")
    return embed


def build_daemon_help_embed(response_text: str) -> discord.Embed:
    """Build an embed for DAEMON's help response."""
    embed = discord.Embed(
        title=f"{DAEMON.AVATAR_EMOJI} DAEMON",
        description=response_text,
        color=0x9B59B6,
    )
    embed.set_footer(text="Digital Authentication Expert & Mentoring Operations Network")
    return embed


# ============================================================================
# GAME ACTION VIEW (Buttons for ALLOW / DENY / DETAIN / Ask DAEMON)
# ============================================================================


class GameActionView(ui.View):
    """Buttons presented with each entrant for the player to make a decision."""

    def __init__(self, session: PlayerSession):
        super().__init__(timeout=300)  # 5-minute timeout per entrant
        self.session = session
        self.decision_made = False

    async def _handle_decision(
        self, interaction: discord.Interaction, decision: str
    ) -> None:
        """Common handler for all three decision buttons."""
        if self.decision_made:
            await interaction.response.send_message(
                "You already made a decision for this entrant.", ephemeral=True
            )
            return

        self.decision_made = True
        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.defer()

        is_correct, result, difficulty_increased = self.session.process_decision(decision)

        # Send result embed
        result_embed = build_result_embed(
            is_correct, result, decision, self.session, difficulty_increased
        )
        await interaction.followup.send(embed=result_embed)

        # If wrong, send DAEMON explanation
        if not is_correct:
            explanation = DAEMON.explain_mistake(result, decision)
            daemon_embed = build_daemon_help_embed(explanation)
            await interaction.followup.send(embed=daemon_embed)

        # Check game over
        if self.session.game_state.is_game_over:
            game_over_embed = build_game_over_embed(self.session)
            await interaction.followup.send(embed=game_over_embed)
            game_sessions.end_session(self.session.user_id)
            self.stop()
            return

        # Send new directive if difficulty increased
        if difficulty_increased:
            directive_embed = build_directive_embed(
                self.session.current_directive, self.session.difficulty
            )
            await interaction.followup.send(embed=directive_embed)

        # Generate and send next entrant
        self.session.generate_next_round()
        entrant_embed = build_entrant_embed(
            self.session.current_entrant,
            self.session.total_entrants_seen,
            self.session,
        )
        new_view = GameActionView(self.session)
        await interaction.followup.send(embed=entrant_embed, view=new_view)
        self.stop()

    @ui.button(label="ALLOW", style=discord.ButtonStyle.green, emoji="✅")
    async def allow_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "allow")

    @ui.button(label="DENY", style=discord.ButtonStyle.red, emoji="🚫")
    async def deny_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "deny")

    @ui.button(label="DETAIN", style=discord.ButtonStyle.danger, emoji="🔒")
    async def detain_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "detain")

    @ui.button(label="Ask DAEMON", style=discord.ButtonStyle.secondary, emoji="🔮")
    async def daemon_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.current_entrant is None or self.session.current_directive is None:
            await interaction.response.send_message(
                "No active entrant to analyze.", ephemeral=True
            )
            return

        self.session.daemon_hints_used += 1
        hint = DAEMON.get_inspection_hint(
            self.session.current_entrant, self.session.current_directive
        )
        embed = build_daemon_help_embed(hint)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Score", style=discord.ButtonStyle.secondary, emoji="📊")
    async def score_button(self, interaction: discord.Interaction, button: ui.Button):
        summary = self.session.get_score_summary()
        embed = discord.Embed(
            title="📊 Session Stats",
            description=summary,
            color=0x00BFFF,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self) -> None:
        """Handle view timeout — end the session."""
        session = self.session
        if session and game_sessions.has_active_session(session.user_id):
            game_sessions.end_session(session.user_id)


# ============================================================================
# CONFIRM QUIT VIEW
# ============================================================================


class QuitConfirmView(ui.View):
    """Confirmation view when a player wants to quit."""

    def __init__(self, session: PlayerSession):
        super().__init__(timeout=30)
        self.session = session

    @ui.button(label="Quit Game", style=discord.ButtonStyle.danger)
    async def confirm_quit(self, interaction: discord.Interaction, button: ui.Button):
        summary = self.session.get_game_over_summary()
        game_sessions.end_session(self.session.user_id)
        embed = discord.Embed(
            title="📴 SESSION TERMINATED",
            description=summary,
            color=0x808080,
        )
        await interaction.response.send_message(embed=embed)
        self.stop()

    @ui.button(label="Keep Playing", style=discord.ButtonStyle.green)
    async def cancel_quit(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Returning to checkpoint duty.", ephemeral=True)
        self.stop()
