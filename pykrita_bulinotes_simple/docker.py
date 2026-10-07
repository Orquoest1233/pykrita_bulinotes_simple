# -----------------------------------------------------------------------------
# Buli Notes Simple - Docker
# Panel acoplable con lista de notas persistentes por documento.
# -----------------------------------------------------------------------------
import json
import uuid

from krita import DockWidget, Krita
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QComboBox,
    QAbstractItemView, QToolButton, QMessageBox,
    QSizePolicy, QWIDGETSIZE_MAX
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

# ID de la annotation donde se guardan los datos en el .kra
ANNOTATION_ID = "bulinotes_data"

# Roles personalizados para guardar datos extra en cada item
ROLE_ID    = Qt.UserRole       # UUID de la nota (persistencia)
ROLE_COLOR = Qt.UserRole + 1   # Hex del color o None

# Paleta de colores disponibles
COLORS = {
    "Sin color": None,
    "Rojo":      QColor("#96262E"),
    "Naranja":   QColor("#995D3A"),
    "Amarillo":  QColor("#594C25"),
    "Verde":     QColor("#1D665C"),
    "Azul":      QColor("#233F52"),
    "Morado":    QColor("#4A2E73"),
    "Gris":      QColor("#505457"),
}

# Inverso: hex -> nombre, para sincronizar el combo al seleccionar
COLORS_BY_HEX = {
    c.name().lower(): n for n, c in COLORS.items() if c is not None
}

# Alpha del texto cuando la nota está marcada como hecha
DONE_TEXT_ALPHA = 140


def _normalize_hex(hex_str):
    """Normaliza un hex de color a minúsculas sin alfa, o None."""
    if not hex_str:
        return None
    try:
        col = QColor(hex_str)
        if not col.isValid():
            return None
        return col.name().lower()  # name() ya devuelve #rrggbb en minúsculas
    except Exception:
        return None


def _contrast_text_color(bg_color):
    """
    Devuelve negro o blanco según la luminosidad del fondo.
    Fórmula ITU-R BT.601 para luminancia percibida.
    """
    if bg_color is None:
        return None
    r, g, b = bg_color.red(), bg_color.green(), bg_color.blue()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return QColor("#000000") if luminance > 0.5 else QColor("#ffffff")


class BuliNotesDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notas chaild")
        self.current_doc = None
        self._pending_doc = None
        self._loading = False
        self._suppress_color_save = False

        # --- Guardado diferido (debounce) ---
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self._on_save_timeout)

        # =====================================================================
        # UI principal
        # =====================================================================
        self.widget = QWidget()
        self.widget.setMinimumSize(0, 0)  # permite encoger el docker
        self.layout = QVBoxLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. Barra de encabezado (solo el botón de colapsar)
        # ---------------------------------------------------------------------
        self.header_widget = QWidget()
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(5, 2, 5, 2)

        self.btn_collapse = QToolButton()
        self.btn_collapse.setText("▼")
        self.btn_collapse.setCheckable(True)
        self.btn_collapse.setChecked(True)
        self.btn_collapse.setFixedWidth(25)
        self.btn_collapse.setToolTip("Minimizar/Maximizar contenido")

        self.header_layout.addWidget(self.btn_collapse)
        self.header_layout.addStretch(1)
        self.layout.addWidget(self.header_widget)

        # ---------------------------------------------------------------------
        # 2. Contenedor de contenido
        # ---------------------------------------------------------------------
        self.content_widget = QWidget()
        self.content_widget.setMinimumSize(0, 0)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)

        # --- Fila de entrada (VERTICAL para que el docker pueda encogerse) ---
        self.input_layout = QVBoxLayout()
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(3)

        # Línea de texto para nueva nota
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Nueva tarea/nota...")
        self.line_edit.setMinimumWidth(50)
        self.line_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        # Sub-fila: combo de color + botón añadir
        self.input_row = QHBoxLayout()
        self.input_row.setContentsMargins(0, 0, 0, 0)
        self.input_row.setSpacing(3)

        self.combo_color = QComboBox()
        self.combo_color.addItems(COLORS.keys())
        self.combo_color.setToolTip("Color de la nota")
        self.combo_color.setMinimumWidth(60)
        self.combo_color.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_add = QPushButton("Añadir")
        self.btn_add.setMinimumWidth(50)
        self.btn_add.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.input_row.addWidget(self.combo_color, 1)
        self.input_row.addWidget(self.btn_add, 0)

        self.input_layout.addWidget(self.line_edit)
        self.input_layout.addLayout(self.input_row)

        # --- Lista de notas ---
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setWordWrap(True)             # envuelve texto largo
        self.list_widget.setMinimumSize(0, 0)
        self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # --- Botones de acción ---
        self.action_layout = QHBoxLayout()
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(3)

        self.btn_up = QToolButton()
        self.btn_up.setText("↑")
        self.btn_up.setFixedWidth(28)
        self.btn_up.setToolTip("Mover arriba")

        self.btn_down = QToolButton()
        self.btn_down.setText("↓")
        self.btn_down.setFixedWidth(28)
        self.btn_down.setToolTip("Mover abajo")

        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setMinimumWidth(50)
        self.btn_delete.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.btn_clear = QPushButton("Vaciar")
        self.btn_clear.setMinimumWidth(50)
        self.btn_clear.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.action_layout.addWidget(self.btn_up, 0)
        self.action_layout.addWidget(self.btn_down, 0)
        self.action_layout.addStretch(1)
        self.action_layout.addWidget(self.btn_delete, 0)
        self.action_layout.addWidget(self.btn_clear, 0)

        # --- Ensamblado del content_layout con stretch ---
        self.content_layout.addLayout(self.input_layout, 0)
        self.content_layout.addWidget(self.list_widget, 1)   # <-- stretch aquí
        self.content_layout.addLayout(self.action_layout, 0)

        self.layout.addWidget(self.content_widget, 1)
        self.setWidget(self.widget)

        # ---------------------------------------------------------------------
        # Conexiones
        # ---------------------------------------------------------------------
        self.btn_collapse.toggled.connect(self.toggle_content)
        self.btn_add.clicked.connect(self.add_item)
        self.btn_delete.clicked.connect(self.delete_item)
        self.btn_clear.clicked.connect(self.clear_items)
        self.btn_up.clicked.connect(self.move_item_up)
        self.btn_down.clicked.connect(self.move_item_down)
        self.line_edit.returnPressed.connect(self.add_item)

        self.list_widget.itemChanged.connect(self._on_item_changed)
        self.list_widget.model().rowsMoved.connect(lambda *_: self.schedule_save())
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.combo_color.currentIndexChanged.connect(self.update_selected_color)

        # Cargar datos iniciales
        self.current_doc = Krita.instance().activeDocument()
        self.load_data()

    # =========================================================================
    # Persistencia
    # =========================================================================
    def schedule_save(self):
        """Reinicia el temporizador y fija el doc destino del guardado."""
        self._pending_doc = self.current_doc or Krita.instance().activeDocument()
        self.save_timer.start()

    def _on_save_timeout(self):
        """El timer expiró: guardamos contra el doc pendiente."""
        doc = self._pending_doc
        self._pending_doc = None
        self._perform_save(doc)

    def _perform_save(self, doc=None):
        """Serializa la lista de notas y la guarda en la annotation del doc."""
        if doc is None:
            doc = self.current_doc or Krita.instance().activeDocument()

        if not doc:
            return

        data = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)

            color_hex = _normalize_hex(item.data(ROLE_COLOR))

            item_id = item.data(ROLE_ID)
            if not item_id:
                item_id = str(uuid.uuid4())
                item.setData(ROLE_ID, item_id)

            data.append({
                "id":    item_id,
                "text":  item.text(),
                "done":  item.checkState() == Qt.Checked,
                "color": color_hex,
            })

        try:
            json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            doc.setAnnotation(ANNOTATION_ID, "Buli Notes Data", json_bytes)
        except Exception as e:
            print(f"[BuliNotes] Error al guardar notas: {e}")

    def load_data(self):
        """Carga las notas desde la annotation del documento actual."""
        self._loading = True
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        doc = self.current_doc or Krita.instance().activeDocument()
        data = []

        if doc:
            try:
                annotation = doc.annotation(ANNOTATION_ID)
            except Exception as e:
                print(f"[BuliNotes] Error al leer annotation: {e}")
                annotation = None

            if annotation:
                try:
                    data_str = bytes(annotation).decode("utf-8")
                    data = json.loads(data_str)
                    if not isinstance(data, list):
                        data = []
                except Exception as e:
                    print(f"[BuliNotes] Error al parsear notas: {e}")
                    data = []

        for item_data in data:
            if not isinstance(item_data, dict):
                continue

            item = QListWidgetItem()

            # 1. Flags: declara que el item PUEDE tener checkbox y ser editado
            item.setFlags(
                item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable
            )
            item.setText(item_data.get("text", ""))
            item.setData(ROLE_ID, item_data.get("id") or str(uuid.uuid4()))

            # 2. Estado del checkbox: materializa la casilla con su estado
            #    (sin esto, el flag ItemIsUserCheckable no dibuja nada)
            is_done = bool(item_data.get("done"))
            item.setCheckState(Qt.Checked if is_done else Qt.Unchecked)

            # 3. Estilo visual (color de fondo + texto contrastante + tachado)
            self._apply_item_style(item, item_data.get("color"), is_done)

            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)
        self._loading = False

    # =========================================================================
    # Ciclo de vida del docker
    # =========================================================================
    def canvasChanged(self, canvas):
        """Krita llama a esto cuando cambia el documento activo."""
        # Forzar guardado pendiente en el doc al que pertenece
        if self.save_timer.isActive():
            self.save_timer.stop()
            pending = self._pending_doc
            self._pending_doc = None
            self._perform_save(pending)

        new_doc = None
        try:
            if canvas and canvas.view():
                new_doc = canvas.view().document()
        except Exception:
            new_doc = None

        if new_doc is not self.current_doc:
            self.current_doc = new_doc
            self.load_data()

    def closeEvent(self, event):
        """Al cerrar el docker, forzamos guardado pendiente."""
        if self.save_timer.isActive():
            self.save_timer.stop()
            pending = self._pending_doc
            self._pending_doc = None
            self._perform_save(pending)
        super().closeEvent(event)

    # =========================================================================
    # Estilo visual de items (color + tachado) - punto único de verdad
    # =========================================================================
    def _apply_item_style(self, item, color_hex, is_done):
        """
        Aplica fondo, color de texto contrastante y tachado según estado.
        Único punto donde se decide cómo se ve un item.
        NO toca el checkState: eso es responsabilidad del que crea el item.
        """
        color_hex = _normalize_hex(color_hex)
        item.setData(ROLE_COLOR, color_hex)

        # --- Fondo + color de texto contrastante ---
        if color_hex:
            bg = QColor(color_hex)
            item.setBackground(QBrush(bg))
            fg = _contrast_text_color(bg)
            if fg:
                # Atenuar ligeramente el texto si la nota está hecha
                fg.setAlpha(DONE_TEXT_ALPHA if is_done else 255)
                item.setForeground(QBrush(fg))
        else:
            item.setBackground(QBrush())
            item.setForeground(QBrush())  # reset al color del tema

        # --- Tachado según estado ---
        font = item.font()
        font.setStrikeOut(is_done)
        item.setFont(font)

    # =========================================================================
    # UI
    # =========================================================================
    def toggle_content(self, checked):
        """Muestra u oculta el contenido y ajusta el tamaño del docker."""
        self.content_widget.setVisible(checked)
        self.btn_collapse.setText("▼" if checked else "▶")

        if checked:
            self.widget.setMinimumSize(0, 0)
            self.widget.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        else:
            self.widget.setFixedSize(40, 35)

    def get_color_from_combo(self):
        """Devuelve el QColor seleccionado en el combo (o None)."""
        return COLORS[self.combo_color.currentText()]

    def _on_item_changed(self, item):
        """
        Reaplica el estilo del item cuando cambia algo (check, texto...).
        También dispara el guardado diferido.
        """
        if self._loading:
            return
        if self._suppress_color_save:
            return

        # Reaplicar estilo con el estado actual del checkbox
        is_done = item.checkState() == Qt.Checked
        color_hex = item.data(ROLE_COLOR)
        self._apply_item_style(item, color_hex, is_done)

        self.schedule_save()

    def _on_selection_changed(self, current, previous):
        """Sincroniza el combo con el color del item seleccionado."""
        if current is None:
            return
        color_hex = _normalize_hex(current.data(ROLE_COLOR))
        self.combo_color.blockSignals(True)
        if color_hex and color_hex in COLORS_BY_HEX:
            self.combo_color.setCurrentText(COLORS_BY_HEX[color_hex])
        else:
            self.combo_color.setCurrentText("Sin color")
        self.combo_color.blockSignals(False)

    # =========================================================================
    # Acciones sobre items
    # =========================================================================
    def _move_row(self, from_row, to_row):
        """Mueve un item conservando todos sus datos."""
        self.list_widget.blockSignals(True)
        item = self.list_widget.takeItem(from_row)

        item_id = item.data(ROLE_ID)
        color   = item.data(ROLE_COLOR)
        text    = item.text()
        state   = item.checkState()

        new_item = QListWidgetItem()

        # 1. Flags: mismo patrón que en load_data y add_item
        new_item.setFlags(
            new_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable
        )
        new_item.setText(text)
        new_item.setData(ROLE_ID, item_id)

        # 2. Estado del checkbox (imprescindible para que se vea la casilla)
        new_item.setCheckState(state)

        # 3. Estilo visual completo (color + tachado)
        self._apply_item_style(new_item, color, state == Qt.Checked)

        self.list_widget.insertItem(to_row, new_item)
        self.list_widget.setCurrentRow(to_row)
        self.list_widget.blockSignals(False)
        self.schedule_save()

    def move_item_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            self._move_row(row, row - 1)

    def move_item_down(self):
        row = self.list_widget.currentRow()
        if 0 <= row < self.list_widget.count() - 1:
            self._move_row(row, row + 1)

    def add_item(self):
        text = self.line_edit.text().strip()
        if not text:
            return

        color = self.get_color_from_combo()

        item = QListWidgetItem()

        # 1. Flags
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        item.setText(text)
        item.setData(ROLE_ID, str(uuid.uuid4()))

        # 2. Estado del checkbox (nota nueva -> desmarcada)
        item.setCheckState(Qt.Unchecked)

        # 3. Estilo visual (aquí is_done siempre es False)
        color_hex = color.name().lower() if color else None
        self._apply_item_style(item, color_hex, False)

        self.list_widget.blockSignals(True)
        self.list_widget.addItem(item)
        self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)

        self.line_edit.clear()
        self.schedule_save()

    def delete_item(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            row = self.list_widget.row(current_item)
            self.list_widget.takeItem(row)
            self.schedule_save()

    def clear_items(self):
        if self.list_widget.count() == 0:
            return
        reply = QMessageBox.question(
            self.widget,
            "Vaciar notas",
            "¿Seguro que quieres borrar TODAS las notas?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.list_widget.clear()
            self.schedule_save()

    def update_selected_color(self):
        """Aplica el color del combo al item seleccionado."""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        color = self.get_color_from_combo()
        color_hex = color.name().lower() if color else None
        is_done = current_item.checkState() == Qt.Checked

        self._suppress_color_save = True
        self.list_widget.blockSignals(True)
        try:
            # Reaplicar estilo completo preservando el tachado
            self._apply_item_style(current_item, color_hex, is_done)
        finally:
            self.list_widget.blockSignals(False)
            self._suppress_color_save = False

        self.schedule_save()