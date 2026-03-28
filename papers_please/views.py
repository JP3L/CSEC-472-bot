"""
Discord UI components for the Papers Please game.
Rich embeds, interactive buttons, concept review questions, and DM-based gameplay.
Features CERBERUS — the three-headed guardian AI tutor.
"""

import random
import discord
from discord import ui
from typing import Optional, List

from . import theme
from .models import Entrant, SecurityDirective, InspectionResult, GameState
from .session import PlayerSession, game_sessions
from .assistant import CERBERUS
from .questions import select_question, shuffle_options, ConceptQuestion


# ============================================================================
# HELPERS
# ============================================================================

async def unpin_bot_messages(channel: discord.DMChannel, bot_id: int) -> None:
    """Unpin all messages in a DM channel that were sent by the bot."""
    try:
        pins = await channel.pins()
        for msg in pins:
            if msg.author.id == bot_id:
                try:
                    await msg.unpin()
                except discord.HTTPException:
                    pass
    except discord.HTTPException:
        pass


# ============================================================================
# VISUAL CONSTANTS
# ============================================================================

COLOR_CERBERUS = 0x9B59B6    # Deep purple — CERBERUS responses
COLOR_DIRECTIVE = 0xFF4500    # Orange-red — security directives
COLOR_ENTRANT = 0x00BFFF      # Cyan — entrant documents
COLOR_CORRECT = 0x00FF66      # Neon green — correct answer
COLOR_INCORRECT = 0xFF3333    # Red — wrong answer
COLOR_GAME_OVER = 0x8B0000    # Dark red — game over
COLOR_QUESTION = 0xFFD700     # Gold — concept review questions
COLOR_MILESTONE = 0xF1C40F    # Yellow — milestone unlocked
COLOR_INTRO = 0x2ECC71        # Emerald — game intro


# ============================================================================
# PROGRESS BAR GENERATOR
# ============================================================================

def _progress_bar(current: int, maximum: int, length: int = 10, filled: str = "█", empty: str = "░") -> str:
    """Generate a visual progress bar."""
    if maximum == 0:
        return empty * length
    ratio = min(current / maximum, 1.0)
    filled_len = int(ratio * length)
    return filled * filled_len + empty * (length - filled_len)


def _strikes_display(strikes: int, max_strikes: int) -> str:
    """Generate a visual strikes display with shield emojis."""
    intact = max_strikes - strikes
    return "🛡️" * intact + "💥" * strikes


# ============================================================================
# EMBED BUILDERS
# ============================================================================


def build_directive_embed(directive: SecurityDirective, difficulty: int) -> discord.Embed:
    """Build a visually rich embed for the Security Directive."""
    # Difficulty label
    diff_labels = {
        0: "ROUTINE", 1: "GUARDED", 2: "ELEVATED",
        3: "HIGH", 4: "SEVERE", 5: "CRITICAL",
        6: "MAXIMUM", 7: "ABSOLUTE", 8: "OMEGA",
    }
    diff_label = diff_labels.get(difficulty, "UNKNOWN")
    diff_bar = _progress_bar(difficulty, 8)

    embed = discord.Embed(
        title=f"⚡ SECURITY DIRECTIVE — {diff_label} [{diff_bar}]",
        description=directive.raw_text,
        color=COLOR_DIRECTIVE,
    )

    # Add structured rule summary for quick reference
    rules_summary = []
    if directive.denied_factions:
        rules_summary.append(f"🚫 **Denied:** {', '.join(directive.denied_factions)}")
    if directive.allowed_factions:
        rules_summary.append(f"✅ **Allowed:** {', '.join(directive.allowed_factions)}")
    if directive.wanted_handle:
        rules_summary.append(f"🔴 **WANTED:** `{directive.wanted_handle}`")
    for faction, docs in directive.required_docs_by_faction.items():
        rules_summary.append(f"📄 **{faction}** requires: {', '.join(docs)}")
    for faction, scans in directive.required_scans_by_faction.items():
        rules_summary.append(f"🔍 **{faction}** scans: {', '.join(scans)}")
    if directive.required_docs_for_operators:
        rules_summary.append(f"⚡ **Operators** require: {', '.join(directive.required_docs_for_operators)}")

    if rules_summary:
        embed.add_field(
            name="📋 Quick Reference",
            value="\n".join(rules_summary),
            inline=False,
        )

    embed.set_footer(text=f"UACC Cyber Division • Threat Level: {diff_label} • Pin this for reference ↗️")
    return embed


def build_entrant_embed(
    entrant: Entrant,
    entrant_number: int,
    session: PlayerSession,
    flagged_fields: set = None,
) -> discord.Embed:
    """Build a visually rich embed for an entrant's documents.

    Args:
        flagged_fields: Optional set of (doc_type, field_name) tuples.
            If provided, those fields are highlighted with ❌ markers
            to indicate CERBERUS-detected issues.
    """
    if flagged_fields is None:
        flagged_fields = set()

    # Approach flavor text
    approach_texts = [
        "A figure materializes at your terminal, data streams flickering...",
        "Proximity alert. An operative approaches the checkpoint barrier...",
        "Neural link detected. Credentials incoming on secure channel...",
        "Checkpoint scanner active. Subject presents digital documents...",
        "Access request detected. Biometric handshake initiated...",
        "Terminal alert: new subject in the verification queue...",
    ]

    # If flagged, change the title/color to indicate CERBERUS scan results
    if flagged_fields:
        embed = discord.Embed(
            title=f"🔍 ENTRANT #{entrant_number} — CERBERUS SCAN RESULTS",
            description="Fields marked with ❌ have issues detected by CERBERUS.",
            color=0xE74C3C,  # Red for flagged
        )
    else:
        embed = discord.Embed(
            title=f"👤 ENTRANT #{entrant_number} — INSPECTION REQUIRED",
            description=random.choice(approach_texts),
            color=COLOR_ENTRANT,
        )

    # Document display with visual formatting
    doc_emojis = {
        "digital_id": "🪪", "bio_badge": "🧬", "access_token": "🔑",
        "clearance_code": "🔐", "asylum_key": "🗝️",
        "diplomatic_cipher": "📡", "integrity_report": "📊",
    }

    for doc in entrant.documents:
        doc_name = theme.DOCUMENT_TYPES.get(doc.doc_type, doc.doc_type)
        emoji = doc_emojis.get(doc.doc_type, "📄")
        field_lines = []
        if doc.doc_type in theme.DOCUMENT_FIELDS:
            for field_name in theme.DOCUMENT_FIELDS[doc.doc_type]:
                if field_name in doc.fields:
                    val = doc.fields[field_name]
                    is_flagged = (doc.doc_type, field_name) in flagged_fields
                    if is_flagged:
                        field_lines.append(f"❌ `{field_name:14s}` │ **{val}**")
                    elif flagged_fields:
                        # Only show ✅ when CERBERUS scan is active
                        field_lines.append(f"✅ `{field_name:14s}` │ {val}")
                    else:
                        # Default: clean display, no markers
                        field_lines.append(f"`{field_name:14s}` │ {val}")
        value_text = "\n".join(field_lines) if field_lines else "*[No data]*"
        embed.add_field(name=f"{emoji} {doc_name}", value=value_text, inline=False)

    # Status bar footer
    gs = session.game_state
    shields = _strikes_display(gs.strikes, gs.max_strikes)
    acc_bar = _progress_bar(gs.score, max(gs.entrants_processed, 1), length=8)

    embed.set_footer(
        text=(
            f"Score: {gs.score}/{gs.entrants_processed} [{acc_bar}] • "
            f"Shields: {shields} • "
            f"Lv{session.difficulty} • "
            f"🔥{session.correct_streak}"
        )
    )
    return embed


def build_result_embed(
    is_correct: bool,
    result: InspectionResult,
    player_decision: str,
    session: PlayerSession,
    difficulty_increased: bool,
    new_milestones: List[tuple] = None,
) -> discord.Embed:
    """Build a result embed after a player's decision."""
    if is_correct:
        # Correct decision — celebratory
        streak = session.correct_streak
        streak_text = ""
        if streak >= 10:
            streak_text = f" • 🔥 **{streak}x COMBO!**"
        elif streak >= 5:
            streak_text = f" • 🔥 {streak}x streak"

        embed = discord.Embed(
            title=f"✅ CORRECT — {result.decision.upper()}",
            description=(
                f"**Reason:** {result.reason}{streak_text}\n\n"
                f"Score: **{session.game_state.score}** / {session.game_state.entrants_processed}"
            ),
            color=COLOR_CORRECT,
        )

        if difficulty_increased:
            embed.add_field(
                name="⚡ THREAT LEVEL INCREASED",
                value=(
                    f"Advancing to **Level {session.difficulty}**. "
                    "New Security Directive incoming. Read it carefully — the rules have changed."
                ),
                inline=False,
            )
    else:
        # Incorrect — informative
        embed = discord.Embed(
            title=f"❌ INCORRECT — Strike #{session.game_state.strikes}",
            description=(
                f"**Your Call:** {player_decision.upper()}\n"
                f"**Correct:** {result.decision.upper()}\n"
                f"**Reason:** {result.reason}"
            ),
            color=COLOR_INCORRECT,
        )
        gs = session.game_state
        shields = _strikes_display(gs.strikes, gs.max_strikes)
        embed.add_field(name="Remaining Shields", value=shields, inline=False)

    # Milestones
    if new_milestones:
        milestone_text = "\n".join(f"{emoji} **{name}** unlocked!" for name, emoji in new_milestones)
        embed.add_field(name="🏆 Milestone Achieved!", value=milestone_text, inline=False)

    return embed


def build_game_over_embed(session: PlayerSession) -> discord.Embed:
    """Build the game-over embed with final stats and rating."""
    embed = discord.Embed(
        title="💀 CLEARANCE REVOKED — GAME OVER",
        description=session.get_game_over_summary(),
        color=COLOR_GAME_OVER,
    )
    embed.set_footer(text="Use /play to start a new session • Use /cerberus <topic> to study")
    return embed


def build_intro_embed() -> discord.Embed:
    """Build the game introduction embed with visual flair."""
    embed = discord.Embed(
        title="🌐 UACC DIGITAL CHECKPOINT — STATION ACTIVE",
        description=theme.GAME_INTRO,
        color=COLOR_INTRO,
    )
    embed.add_field(
        name="🎮 How to Play",
        value=(
            "Entrants present digital credentials for inspection.\n"
            "Review their documents against the **Security Directive**.\n"
            "Choose your decision:\n\n"
            "✅ **ALLOW** — Valid credentials, grant network access\n"
            "🚫 **DENY** — Missing/expired docs, restricted faction, failed compliance\n"
            "🔒 **DETAIN** — Document fraud (mismatched fields) or wanted suspect\n\n"
            "Three strikes and your clearance is revoked."
        ),
        inline=False,
    )
    embed.add_field(
        name="🐕‍🦺 CERBERUS Guardian",
        value=(
            "Your three-headed security advisor is online.\n"
            "🔑 **Head I** — Knowledge factor analysis\n"
            "🪪 **Head II** — Possession factor verification\n"
            "🧬 **Head III** — Inherence factor validation\n\n"
            "Use **Ask CERBERUS** for hints or `/cerberus <topic>` for deep dives."
        ),
        inline=False,
    )
    embed.add_field(
        name="📚 Concept Reviews",
        value=(
            "Every 3 entrants, you'll face a CSEC-472 concept question.\n"
            "Answer correctly to boost your score. CERBERUS provides explanations "
            "for every question — right or wrong."
        ),
        inline=False,
    )
    embed.set_footer(text="UACC Cyber Division • Authentication Training Module v4.0")
    return embed


def build_cerberus_embed(response_text: str) -> discord.Embed:
    """Build an embed for CERBERUS responses."""
    embed = discord.Embed(
        title=f"{CERBERUS.AVATAR_EMOJI} CERBERUS",
        description=response_text,
        color=COLOR_CERBERUS,
    )
    embed.set_footer(text="Cybernetic Enforcement & Review Bureau for Encrypted Resource & User Security")
    return embed


def build_milestone_embed(name: str, emoji: str, session: PlayerSession) -> discord.Embed:
    """Build a milestone achievement embed."""
    embed = discord.Embed(
        title=f"{emoji} MILESTONE UNLOCKED — {name}",
        description=(
            f"Agent, you've earned the **{name}** achievement!\n\n"
            f"Current Stats: {session.game_state.score} correct | "
            f"Level {session.difficulty} | "
            f"🔥{session.best_streak} best streak"
        ),
        color=COLOR_MILESTONE,
    )
    return embed


# ============================================================================
# CONCEPT QUESTION VIEW
# ============================================================================

class ConceptQuestionView(ui.View):
    """Interactive view for concept review questions between entrants."""

    def __init__(self, session: PlayerSession, question: ConceptQuestion,
                 shuffled_options: List[str], correct_index: int):
        super().__init__(timeout=120)
        self.session = session
        self.question = question
        self.correct_index = correct_index
        self.answered = False

        # Add option buttons dynamically
        labels = ["A", "B", "C", "D"]
        styles = [
            discord.ButtonStyle.primary, discord.ButtonStyle.primary,
            discord.ButtonStyle.primary, discord.ButtonStyle.primary,
        ]
        for i, (label, opt) in enumerate(zip(labels, shuffled_options)):
            button = ui.Button(
                label=f"{label}: {opt[:70]}",
                style=styles[i],
                custom_id=f"q_option_{i}",
                row=i,
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

    def _make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if self.answered:
                await interaction.response.send_message("Already answered!", ephemeral=True)
                return

            self.answered = True
            for item in self.children:
                item.disabled = True

            is_correct = index == self.correct_index
            self.session.record_question_result(self.question.topic, is_correct)

            # Save to DB
            if game_sessions.db:
                try:
                    game_sessions.db.save_question_result(
                        self.session.user_id, self.session.rit_username, None,
                        self.question.id, self.question.topic, is_correct,
                    )
                except Exception:
                    pass

            if is_correct:
                embed = discord.Embed(
                    title="✅ Correct!",
                    description=(
                        f"**{self.question.explanation}**\n\n"
                        f"🎮 **Game Connection:** {self.question.game_context}"
                    ),
                    color=COLOR_CORRECT,
                )
            else:
                correct_option = self.question.options[0]
                embed = discord.Embed(
                    title=f"❌ Incorrect — The answer was: {correct_option}",
                    description=(
                        f"**{self.question.explanation}**\n\n"
                        f"🎮 **Game Connection:** {self.question.game_context}"
                    ),
                    color=COLOR_INCORRECT,
                )

            embed.set_footer(text=f"Topic: {self.question.topic} • Difficulty: {'⭐' * (self.question.difficulty + 1)}")
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=embed)

            # Check milestones from question
            new_milestones = self.session.check_milestones()
            for name, emoji in new_milestones:
                m_embed = build_milestone_embed(name, emoji, self.session)
                await interaction.followup.send(embed=m_embed)

            # Continue to next entrant
            self.session.generate_next_round()
            entrant_embed = build_entrant_embed(
                self.session.current_entrant,
                self.session.total_entrants_seen,
                self.session,
            )
            new_view = GameActionView(self.session)
            await interaction.followup.send(embed=entrant_embed, view=new_view)
            self.stop()

        return callback


def build_question_embed(question: ConceptQuestion, shuffled_options: List[str]) -> discord.Embed:
    """Build an embed for a concept review question."""
    embed = discord.Embed(
        title=f"📚 CONCEPT REVIEW — {question.topic}",
        description=(
            "```\n"
            f"  {question.question}\n"
            "```"
        ),
        color=COLOR_QUESTION,
    )
    labels = ["A", "B", "C", "D"]
    options_text = "\n".join(f"**{l}.** {o}" for l, o in zip(labels, shuffled_options))
    embed.add_field(name="Choose your answer:", value=options_text, inline=False)
    embed.set_footer(text=f"Topic: {question.topic} • Difficulty: {'⭐' * (question.difficulty + 1)}")
    return embed


# ============================================================================
# GAME ACTION VIEW (ALLOW / DENY / DETAIN / Ask CERBERUS / Score)
# ============================================================================

class GameActionView(ui.View):
    """Buttons presented with each entrant for the player's decision."""

    def __init__(self, session: PlayerSession):
        super().__init__(timeout=300)
        self.session = session
        self.decision_made = False

    async def _handle_decision(
        self, interaction: discord.Interaction, decision: str
    ) -> None:
        if self.decision_made:
            await interaction.response.send_message(
                "Decision already recorded for this entrant.", ephemeral=True
            )
            return

        self.decision_made = True
        for item in self.children:
            item.disabled = True

        await interaction.response.defer()

        is_correct, result, difficulty_increased, new_milestones = (
            self.session.process_decision(decision)
        )

        # Result embed
        result_embed = build_result_embed(
            is_correct, result, decision, self.session,
            difficulty_increased, new_milestones,
        )
        await interaction.followup.send(embed=result_embed)

        # CERBERUS explanation on wrong answer
        if not is_correct:
            explanation = CERBERUS.explain_mistake(result, decision)
            cerberus_embed = build_cerberus_embed(explanation)
            await interaction.followup.send(embed=cerberus_embed)

        # Game over check
        if self.session.game_state.is_game_over:
            game_over_embed = build_game_over_embed(self.session)
            await interaction.followup.send(embed=game_over_embed)
            game_sessions.end_session(self.session.user_id)
            self.stop()
            return

        # New directive on difficulty increase
        if difficulty_increased:
            self.session.generate_next_round()
            directive_embed = build_directive_embed(
                self.session.current_directive, self.session.difficulty,
            )
            directive_msg = await interaction.followup.send(embed=directive_embed)
            # Unpin old directives, then pin the new one
            try:
                await unpin_bot_messages(interaction.channel, interaction.client.user.id)
                await directive_msg.pin()
                self.session.pinned_directive_msg_id = directive_msg.id
            except discord.Forbidden:
                pass

            # Send next entrant
            entrant_embed = build_entrant_embed(
                self.session.current_entrant,
                self.session.total_entrants_seen,
                self.session,
            )
            new_view = GameActionView(self.session)
            await interaction.followup.send(embed=entrant_embed, view=new_view)
            self.stop()
            return

        # Check if it's time for a concept question
        if self.session.should_ask_question():
            question = select_question(
                self.session.difficulty, self.session.questions_seen_ids
            )
            if question:
                self.session.questions_seen_ids.add(question.id)
                shuffled, correct_idx = shuffle_options(question)
                q_embed = build_question_embed(question, shuffled)
                q_view = ConceptQuestionView(
                    self.session, question, shuffled, correct_idx
                )
                await interaction.followup.send(embed=q_embed, view=q_view)
                self.stop()
                return

        # Normal: generate and send next entrant
        self.session.generate_next_round()
        entrant_embed = build_entrant_embed(
            self.session.current_entrant,
            self.session.total_entrants_seen,
            self.session,
        )
        new_view = GameActionView(self.session)
        await interaction.followup.send(embed=entrant_embed, view=new_view)
        self.stop()

    @ui.button(label="ALLOW", style=discord.ButtonStyle.green, emoji="✅", row=0)
    async def allow_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "allow")

    @ui.button(label="DENY", style=discord.ButtonStyle.red, emoji="🚫", row=0)
    async def deny_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "deny")

    @ui.button(label="DETAIN", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def detain_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_decision(interaction, "detain")

    @ui.button(label="Ask CERBERUS", style=discord.ButtonStyle.secondary, emoji="🐕‍🦺", row=1)
    async def cerberus_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.current_entrant is None or self.session.current_directive is None:
            await interaction.response.send_message("No active entrant.", ephemeral=True)
            return
        self.session.cerberus_hints_used += 1

        entrant = self.session.current_entrant
        directive = self.session.current_directive

        # Get contextual analysis
        hint = CERBERUS.get_inspection_hint(entrant, directive)
        flagged = CERBERUS.get_flagged_fields(entrant, directive)

        # Build CERBERUS analysis embed
        cerberus_embed = build_cerberus_embed(hint)

        # Build re-rendered entrant embed with flagged fields highlighted
        embeds = [cerberus_embed]
        if flagged:
            flagged_entrant = build_entrant_embed(
                entrant,
                self.session.game_state.entrants_processed,
                self.session,
                flagged_fields=flagged,
            )
            embeds.append(flagged_entrant)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    @ui.button(label="Score", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def score_button(self, interaction: discord.Interaction, button: ui.Button):
        summary = self.session.get_score_summary()
        embed = discord.Embed(
            title="📊 Agent Performance Dashboard",
            description=summary,
            color=COLOR_ENTRANT,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self) -> None:
        session = self.session
        if session and game_sessions.has_active_session(session.user_id):
            game_sessions.end_session(session.user_id)


# ============================================================================
# CONFIRM QUIT VIEW
# ============================================================================

class QuitConfirmView(ui.View):
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
