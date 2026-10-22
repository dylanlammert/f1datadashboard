from matplotlib.axes import Axes

BACKGROUND = "#1A1A1A"
CONTEXT_LINE = "#4E4E58"
GRID_LINE = "#2C2C2C"
TEXT = "#ECECEC"
MUTED_TEXT = "#9A9AA6"
ACCENT = "#00D2BE"


def style_axes_dark(ax: Axes) -> None:
    ax.set_facecolor(BACKGROUND)
    ax.title.set_color(TEXT)
    ax.xaxis.label.set_color(MUTED_TEXT)
    ax.yaxis.label.set_color(MUTED_TEXT)
    ax.tick_params(colors=MUTED_TEXT, length=0)
    ax.grid(True, axis="y", color=GRID_LINE, linewidth=0.6)
    ax.grid(False, axis="x")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    legend = ax.get_legend()
    if legend is not None:
        legend.set_frame_on(False)
        for text in legend.get_texts():
            text.set_color(TEXT)
