
"""Pre-race AI finishing position predictions versus actual results."""

from matplotlib.figure import Figure
from ML.race_outcome import predict_race
from graphs.themes import BACKGROUND, GRID_LINE, TEXT, MUTED_TEXT, ACCENT



def _placeholder(message):
    fig = Figure(figsize=(10, 5), facecolor=BACKGROUND)
    ax = fig.add_subplot(111, facecolor=BACKGROUND)
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center",
        color=TEXT, fontsize=12,
        wrap=True, transform=ax.transAxes,
    )
    ax.axis("off")
    return fig, None


def build_ai_race_insights_figure(session_id: int, db_path=None):
    """Return a figure and predictions for a completed race."""

    if not session_id:
        return _placeholder("Select a race on Home to view AI predictions.")

    try:
        if db_path is None:
            predictions = predict_race(session_id)
        else:
            predictions = predict_race(session_id, db_path=db_path)
    except ValueError as error:
        return _placeholder(str(error))

    predictions = predictions.sort_values("predicted_position").copy()

    if predictions.empty:
        raise ValueError("No race predictions available.")

    count = len(predictions)
    fig = Figure(
        figsize=(11, max(7, 1.5 + count * 0.43)),
        facecolor=BACKGROUND,
    )
    ax = fig.add_subplot(111, facecolor=BACKGROUND)

    y = list(range(count))
    predicted = predictions["predicted_position"].astype(float).to_numpy()
    actual = predictions["finish_position"].astype(float).to_numpy()

    for i in range(count):
        ax.plot(
            [predicted[i], actual[i]],
            [i, i],
            color=GRID_LINE,
            linewidth=3,
            zorder=1,
        )

    ax.scatter(
        predicted, y,
        color=ACCENT,
        s=75,
        label="AI Predicted",
        zorder=3,
    )
    ax.scatter(
        actual, y,
        color="#F59E0B",
        s=75,
        marker="D",
        label="Actual Finish",
        zorder=3,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(predictions["driver_code"])
    ax.invert_yaxis()

    ax.set_xlim(0, count + 1)
    ax.set_xticks(range(1, count + 1, 2))
    ax.set_xlabel("Finishing Position", color=TEXT)
    ax.set_title(
        "AI Pre-Race Predictions vs Actual Results",
        color=TEXT,
        pad=16,
    )

    ax.tick_params(colors=MUTED_TEXT)
    ax.grid(axis="x", color=GRID_LINE, alpha=0.7)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_visible(False)

    mean_error = abs(predicted - actual).mean()
    ax.text(
        0.02, 0.01,
        f"Mean position error: {mean_error:.2f}",
        transform=ax.transAxes,
        color=TEXT,
        fontsize=10,
    )

    handles, labels = ax.get_legend_handles_labels()
    legend = fig.legend(
        handles, labels,
        loc="upper right",
        bbox_to_anchor=(0.98, 0.93),
        ncol=2,
        frameon=False,
    )
    for label in legend.get_texts():
        label.set_color(TEXT)

    fig.subplots_adjust(
        left=0.14,
        right=0.97,
        top=0.83,
        bottom=0.13,
    )
    return fig, predictions
