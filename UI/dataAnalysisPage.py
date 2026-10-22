from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGraphicsProxyWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal, QPointF, QSize
from PySide6.QtGui import QPainter, QMouseEvent, QResizeEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from graphs.placement_over_time import placement_figure_for_session
from graphs.graph_factory import Metric, GenericGraphFactory
from Services.dbhandler import DBhandler
from ViewModels.sessionSelectorVM import SessionSelectorVM
from UI.Theme import theme


class SearchableGraphDropdown(QComboBox):
    """Searchable dropdown for the graphs"""

    def __init__(self, graphs: list[str], parent=None):
        super().__init__(parent)
        self.setEditable(True)
        # ? Supposedly, this will stop the user from inserting their own text into it (while still searching)? It's a good check to have regardless.
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItems(graphs)
        # ? Sets the current index "out of bounds" so the default search box is empty
        self.setCurrentIndex(-1)
        # ? self.lineEdit() can return None, so this check is necessary to prevent a crash.
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("Add Graph")
        self.setFixedSize(220, 36)

        # ? Autocompleter search implementation
        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # ? Makes it all pretty :3
        self.setStyleSheet(
            f"""
            QComboBox {{
                background-color: #21212e;
                color: {theme.primaryText};
                border-radius: 8px;
                padding: 0px 12px;
                font-weight: bold;
            }}
            QComboBox QAbstractItemView {{
                background-color: #16161f;
                color: {theme.primaryText};
                selection-background-color: {theme.info};
            }}
            """
        )


class DragHeader(QWidget):
    """Top object of the graphs, allows movement and resizing"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background-color: #3a3a3a; color: white;")
        # ? Cursor shape that tells the user they can move this object in any direction
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        # ? Sets the title of the graph in the top left. Currently looks a little janky, but it's not egregious.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.addWidget(QLabel(title))
        layout.addStretch()

        # ? Close button in the top right
        self.close_btn = QPushButton("x")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self.close_btn)

        self._press_global = None
        self._press_item_pos = None

    def mousePressEvent(self, event: QMouseEvent):
        """Controls what happens when the mouse clicks"""
        proxy = self._proxy()
        # ? Filters to only have an effect when the LMB is pressed
        if event.button() == Qt.MouseButton.LeftButton and proxy:
            self._press_global = event.globalPosition()
            self._press_item_pos = proxy.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Controls what happens when the mouse is moved around"""
        proxy = self._proxy()
        # ? Filters to only allow movement when the mouse is pressed
        if self._press_global is not None and proxy:
            # ? Gets the change of position before and during the movement event
            delta = event.globalPosition() - self._press_global
            # ? Safeguard to handle if the proxy doesn't have a position
            if self._press_item_pos is not None:
                # ? Updates the position with the change in x and y coordinates
                proxy.setPos(self._press_item_pos + QPointF(delta.x(), delta.y()))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Releases the global press event when the mouse is released"""
        # ? `event` still must be passed since an event is being used, but `event` isn't being accessed in this code.
        self._press_global = None

    def _proxy(self) -> QGraphicsProxyWidget | None:
        """Helper function that returns the current widget"""
        return self.window().graphicsProxyWidget()


class ResizeGrip(QWidget):
    """Allows resizing the graphs"""

    # ? Since MatPlotLib handles resizing, we don't need to deal with the proxy objects at all, just update the size of the window.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setStyleSheet("background-color: #555;")
        self._press_global = None
        self._press_size = None

    def mousePressEvent(self, event):
        """Controls what happens when the mouse clicks"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition()
            self._press_size = self.window().size()
            event.accept()

    def mouseMoveEvent(self, event):
        """Controls what happens when the mouse is moved around"""
        if self._press_global is not None:
            delta = event.globalPosition() - self._press_global
            panel = self.window()
            if self._press_size is not None:
                new_w = max(
                    panel.minimumWidth(), self._press_size.width() + int(delta.x())
                )
                new_h = max(
                    panel.minimumHeight(), self._press_size.height() + int(delta.y())
                )
                panel.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Releases the global press event when the mouse is released"""
        # ? `event` still must be passed since an event is being used, but `event` isn't being accessed in this code.
        self._press_global = None


class GraphPanel(QFrame):
    """Embeds the header and resize handle into each graph"""

    close_requested = Signal()

    def __init__(self, title: str, canvas: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("graphPanel")
        self.setStyleSheet("#graphPanel { background-color: #1e1e1e; }")
        self.setMinimumSize(300, 200)

        self.header = DragHeader(title)
        self.header.close_btn.clicked.connect(self.close_requested)

        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas.setMinimumSize(1, 1)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(ResizeGrip())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(canvas, 1)
        layout.addLayout(grip_row)


class GraphCanvasView(QGraphicsView):
    """Displays the view of the graph canvas"""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setStyleSheet("background-color: #16161f; border: none;")
        self._overlay = None
        self.on_graph_pressed = None

    def set_overlay(self, widget: QWidget):
        self._overlay = widget
        self._position_overlay()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._position_overlay()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        while item is not None and not isinstance(item, QGraphicsProxyWidget):
            item = item.parentItem()
        if item is not None and self.on_graph_pressed is not None:
            self.on_graph_pressed(item)
        super().mousePressEvent(event)

    def _position_overlay(self):
        if self._overlay is None:
            return
        margin = 16
        # ? This is necessary to exclude the scroll bars that appear on screen.
        vp = self.viewport().geometry()
        self._overlay.move(
            vp.right() - self._overlay.width() - margin + 1, vp.top() + margin
        )
        self._overlay.raise_()


class GraphCanvasContainer(QWidget):
    """The container that holds all the graphs"""

    def __init__(self, session_selector: SessionSelectorVM, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dbhandler = DBhandler()

        self.current_session_id = session_selector.currentSessionID
        session_selector.currentSessionIDChanged.connect(self._onSessionChanged)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.view = GraphCanvasView(self.scene)
        self.view.on_graph_pressed = self._bring_to_front
        layout.addWidget(self.view)

        self.active_graphs: dict[str, QGraphicsProxyWidget] = {}
        self._z_counter = 0

        # ! Graphs can be put in here following this format IFF they're implemented with FigureCanvasQTAgg in mind (like the Placement over Time graph is)
        self.graph_factories = {
            "Placement over Time": lambda: FigureCanvasQTAgg(
                placement_figure_for_session(self.current_session_id)
            )
        }

        # ? This handles populating generic graphs into the graphs list.
        self.generic = GenericGraphFactory(self.dbhandler)
        for metric in Metric:
            self.graph_factories[f"Generic: {metric.spec.label}"] = lambda m=metric: (
                FigureCanvasQTAgg(self.generic.build(m, self.current_session_id))
            )

        self.dropdown = SearchableGraphDropdown(list(self.graph_factories), self.view)
        self.view.set_overlay(self.dropdown)
        self.dropdown.textActivated.connect(self._on_graph_selected)

    def add_graph(
        self,
        graph_id: str,
        canvas: QWidget,
        x: float,
        y: float,
        size: QSize = QSize(800, 500),
    ):
        if graph_id in self.active_graphs:
            return

        panel = GraphPanel(graph_id, canvas)
        panel.resize(size)
        panel.close_requested.connect(lambda gid=graph_id: self.remove_graph(gid))

        proxy = QGraphicsProxyWidget()
        proxy.setWidget(panel)
        proxy.setPos(x, y)
        self.scene.addItem(proxy)
        self.active_graphs[graph_id] = proxy
        self._bring_to_front(proxy)

    def remove_graph(self, graph_id: str):
        proxy = self.active_graphs.pop(graph_id, None)
        if proxy:
            self.scene.removeItem(proxy)
            proxy.deleteLater()

    def _bring_to_front(self, proxy):
        # ? Prevents the z-value from incrementing too high.
        if self._z_counter > 0 and proxy.zValue() == self._z_counter:
            return
        self._z_counter += 1
        proxy.setZValue(self._z_counter)

    def _on_graph_selected(self, name: str):
        factory = self.graph_factories.get(name)
        if factory is not None and name not in self.active_graphs:
            # ? These numbers *should* put it near the top left of wherever the user is looking at currently
            spot = self.view.mapToScene(40, 70)
            # ? This will cascade them if the user clicks a bunch of graphs on at once
            offset = 30 * len(self.active_graphs)
            self.add_graph(name, factory(), spot.x() + offset, spot.y() + offset)

        self.dropdown.setCurrentIndex(-1)
        self.dropdown.clearEditText()

    def _onSessionChanged(self, session_id: int) -> None:
        self.current_session_id = session_id
