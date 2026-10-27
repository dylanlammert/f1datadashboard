from dataclasses import dataclass
from PySide6.QtGui import QFontDatabase, QFont
from pathlib import Path

# find the path based off of clues
fontPath = Path(__file__).parent / "fonts" / "Noto_Sans" / "NotoSansVariableFont.ttf"

@dataclass
class Fonts:
    fontFamily = "Sans Serif"
    h1: int = 24
    h2: int = 18
    text: int = 12

    def qfont(self, size: int | None = None) -> QFont:
        """_build a QFont on load_
        """
        return QFont(self.family, size or self.text)


@dataclass
class DayTheme:
    # UI colors
    background: str = "#16161f"
    primaryText: str = "#ffffff"
    secondaryText: str = "#a0a0b0"
    tertiaryText: str = "#000000"
    # information colors
    success: str = "#00ff59"
    warning: str = "#fff200"
    danger: str = "#e33d3d"
    info: str = "#3e85d1"
    safety: str = "#ff9334"



theme = DayTheme()
fontStyles = Fonts()

def loadFonts() -> None:
    "_build the font after QApplication loads within main_"
    fontID = QFontDatabase.addApplicationFont(str(fontPath))
    if fontID == -1:
        print("NotoSans could not be loaded, default to sys font")
    else:
        families = QFontDatabase.applicationFontFamilies(fontID)
        if families:
            fontStyles.family = families[0]
