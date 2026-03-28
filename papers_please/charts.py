"""
Chart generation for the Papers Please instructor report.
Generates cyberpunk-themed matplotlib charts as Discord file attachments.
"""

import io
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import discord

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ============================================================================
# THEME CONSTANTS
# ============================================================================

CYBER_BG = "#0d0221"
CYBER_PANEL = "#1a0a2e"
CYBER_CYAN = "#00FFFF"
CYBER_MAGENTA = "#FF00FF"
CYBER_ORANGE = "#FF6600"
CYBER_GREEN = "#00FF66"
CYBER_RED = "#FF3333"
CYBER_YELLOW = "#FFD700"
CYBER_TEXT = "#E0E0FF"
CYBER_GRID = "#2a1a4e"


def _apply_cyber_theme(fig, ax):
    """Apply cyberpunk theme to a matplotlib figure and axes."""
    fig.patch.set_facecolor(CYBER_BG)
    ax.set_facecolor(CYBER_PANEL)
    ax.tick_params(colors=CYBER_TEXT, labelsize=9)
    ax.xaxis.label.set_color(CYBER_TEXT)
    ax.yaxis.label.set_color(CYBER_TEXT)
    ax.title.set_color(CYBER_CYAN)
    ax.title.set_fontsize(13)
    ax.title.set_fontweight("bold")
    for spine in ax.spines.values():
        spine.set_color(CYBER_GRID)
    ax.grid(True, color=CYBER_GRID, alpha=0.3, linestyle="--")


def _fig_to_discord_file(fig, filename: str) -> discord.File:
    """Convert matplotlib figure to a discord.File."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return discord.File(buf, filename=filename)


# ============================================================================
# CHART GENERATORS
# ============================================================================


def generate_accuracy_chart(
    player_data: List[Dict],
) -> Optional[discord.File]:
    """
    Generate a horizontal bar chart of player accuracy rates.

    Args:
        player_data: List of dicts with keys: 'label', 'accuracy', 'total_entrants'

    Returns:
        discord.File with the chart image, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB or not player_data:
        return None

    # Sort by accuracy descending
    sorted_data = sorted(player_data, key=lambda x: x["accuracy"], reverse=True)
    labels = [d["label"] for d in sorted_data]
    accuracies = [d["accuracy"] for d in sorted_data]

    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.5 + 1)))
    _apply_cyber_theme(fig, ax)

    colors = []
    for acc in accuracies:
        if acc >= 80:
            colors.append(CYBER_GREEN)
        elif acc >= 60:
            colors.append(CYBER_CYAN)
        elif acc >= 40:
            colors.append(CYBER_ORANGE)
        else:
            colors.append(CYBER_RED)

    bars = ax.barh(labels, accuracies, color=colors, edgecolor=CYBER_CYAN, linewidth=0.5, height=0.6)
    ax.set_xlabel("Accuracy %")
    ax.set_title("AGENT ACCURACY RATINGS")
    ax.set_xlim(0, 105)
    ax.invert_yaxis()

    # Add percentage labels on bars
    for bar, acc in zip(bars, accuracies):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{acc:.0f}%", va="center", color=CYBER_TEXT, fontsize=9)

    return _fig_to_discord_file(fig, "accuracy_chart.png")


def generate_topic_performance_chart(
    topic_data: Dict[str, Dict],
) -> Optional[discord.File]:
    """
    Generate a grouped bar chart showing correct vs incorrect answers by topic.

    Args:
        topic_data: Dict of topic -> {'correct': int, 'total': int}

    Returns:
        discord.File with the chart image, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB or not topic_data:
        return None

    topics = list(topic_data.keys())
    correct = [topic_data[t]["correct"] for t in topics]
    incorrect = [topic_data[t]["total"] - topic_data[t]["correct"] for t in topics]

    fig, ax = plt.subplots(figsize=(10, 5))
    _apply_cyber_theme(fig, ax)

    x = range(len(topics))
    width = 0.35
    ax.bar([i - width/2 for i in x], correct, width, label="Correct",
           color=CYBER_GREEN, edgecolor=CYBER_CYAN, linewidth=0.5)
    ax.bar([i + width/2 for i in x], incorrect, width, label="Incorrect",
           color=CYBER_RED, edgecolor=CYBER_CYAN, linewidth=0.5)

    ax.set_xticks(list(x))
    ax.set_xticklabels(topics, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Responses")
    ax.set_title("CONCEPT MASTERY BY TOPIC")
    ax.legend(facecolor=CYBER_PANEL, edgecolor=CYBER_GRID, labelcolor=CYBER_TEXT)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    return _fig_to_discord_file(fig, "topic_performance.png")


def generate_difficulty_progression_chart(
    player_data: List[Dict],
) -> Optional[discord.File]:
    """
    Generate a chart showing max difficulty reached by each player.

    Args:
        player_data: List of dicts with keys: 'label', 'max_difficulty', 'sessions'

    Returns:
        discord.File with the chart image, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB or not player_data:
        return None

    sorted_data = sorted(player_data, key=lambda x: x["max_difficulty"], reverse=True)
    labels = [d["label"] for d in sorted_data]
    difficulties = [d["max_difficulty"] for d in sorted_data]

    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.5 + 1)))
    _apply_cyber_theme(fig, ax)

    colors = [CYBER_MAGENTA if d >= 5 else CYBER_CYAN if d >= 3 else CYBER_ORANGE for d in difficulties]
    bars = ax.barh(labels, difficulties, color=colors, edgecolor=CYBER_MAGENTA, linewidth=0.5, height=0.6)
    ax.set_xlabel("Max Difficulty Reached")
    ax.set_title("DIFFICULTY PROGRESSION")
    ax.set_xlim(0, 9)
    ax.invert_yaxis()

    for bar, diff in zip(bars, difficulties):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                f"Lv {diff}", va="center", color=CYBER_TEXT, fontsize=9)

    return _fig_to_discord_file(fig, "difficulty_chart.png")


def generate_session_activity_chart(
    daily_counts: Dict[str, int],
) -> Optional[discord.File]:
    """
    Generate a line chart showing game sessions over time.

    Args:
        daily_counts: Dict of date_str -> session_count

    Returns:
        discord.File with the chart image, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB or not daily_counts:
        return None

    dates = list(daily_counts.keys())
    counts = list(daily_counts.values())

    fig, ax = plt.subplots(figsize=(10, 4))
    _apply_cyber_theme(fig, ax)

    ax.plot(dates, counts, color=CYBER_CYAN, linewidth=2, marker="o",
            markersize=6, markerfacecolor=CYBER_MAGENTA, markeredgecolor=CYBER_CYAN)
    ax.fill_between(dates, counts, alpha=0.15, color=CYBER_CYAN)

    ax.set_ylabel("Sessions")
    ax.set_title("CHECKPOINT ACTIVITY TIMELINE")
    ax.tick_params(axis="x", rotation=35)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    return _fig_to_discord_file(fig, "activity_chart.png")
