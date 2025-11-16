#  Copyright (c) 2016 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
#  USA.import plugin

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, QSortFilterProxyModel
from PyQt6.QtWidgets import (
    QTableView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QWidget,
    QVBoxLayout,
    QLineEdit,
)
from PyQt6.QtGui import QPainter, QColor

from . import connection
from .dbItemDialog import ItemDialog


_COLS = [
    "Value",
    "Annun",
    "Old",
    "Bad",
    "Fail",
    "SFail",
    "Writer",
    "Rate Avg (Hz)",
    "Rate Min (Hz)",
    "Rate Max (Hz)",
    "Rate SDev (Hz)",
    "Samples",
    "Description",
]


class _DataModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._keys = connection.db.get_item_list()
        self._keys.sort()
        self._items = [connection.db.get_item(k) for k in self._keys]
        self._dirty_rows = set()
        self._align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        # Connect item signals to mark rows dirty; coalesce via external timer
        for row, it in enumerate(self._items):
            it.valueChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.annunciateChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.oldChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.badChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.failChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.secFailChanged.connect(lambda _v, r=row: self._mark_dirty(r))
            it.statsChanged.connect(lambda _s, r=row: self._mark_dirty(r))

    def _mark_dirty(self, row):
        self._dirty_rows.add(row)

    # External caller flushes changes periodically
    def flush(self):
        if not self._dirty_rows:
            return
        rows = sorted(self._dirty_rows)
        self._dirty_rows.clear()
        # Emit minimal number of dataChanged signals by coalescing contiguous rows
        start = rows[0]
        prev = start
        for r in rows[1:]:
            if r != prev + 1:
                top = self.index(start, 0)
                bottom = self.index(prev, len(_COLS) - 1)
                self.dataChanged.emit(top, bottom, [])
                start = r
            prev = r
        top = self.index(start, 0)
        bottom = self.index(prev, len(_COLS) - 1)
        self.dataChanged.emit(top, bottom, [])

    # Qt model API
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(_COLS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _COLS[section]
        else:
            return self._keys[section] if 0 <= section < len(self._keys) else None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        it = self._items[row]

        # Alignment for numeric columns
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (7, 8, 9, 10, 11):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        try:
            if col == 0:
                v = it.value
                return "" if v is None else str(v)
            elif col == 1:
                return "I" if it.annunciate else "0"
            elif col == 2:
                return "I" if it.old else "0"
            elif col == 3:
                return "I" if it.bad else "0"
            elif col == 4:
                return "I" if it.fail else "0"
            elif col == 5:
                return "I" if it.secFail else "0"
            elif col == 6:
                return it.last_writer or ""
            elif col == 7:
                return "" if it.rate_avg is None else f"{it.rate_avg:.2f}"
            elif col == 8:
                return "" if it.rate_min is None else f"{it.rate_min:.2f}"
            elif col == 9:
                return "" if it.rate_max is None else f"{it.rate_max:.2f}"
            elif col == 10:
                return "" if it.rate_stdev is None else f"{it.rate_stdev:.2f}"
            elif col == 11:
                return "" if it.rate_samples is None else str(it.rate_samples)
            elif col == 12:
                return it.description
        except Exception:
            return None

    # Helpers for filtering
    def key_at(self, row: int) -> str:
        try:
            return self._keys[row]
        except Exception:
            return ""

    def writer_at(self, row: int) -> str:
        try:
            return self._items[row].last_writer or ""
        except Exception:
            return ""


class _DataFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def setFilterText(self, text: str):
        text = text or ""
        if text == self._text:
            return
        self._text = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent):
        if not self._text:
            return True
        model = self.sourceModel()
        if not isinstance(model, _DataModel):
            return True
        t = self._text
        if t in model.key_at(source_row):
            return True
        if t in model.writer_at(source_row):
            return True
        return False


class BoolIndicatorDelegate(QStyledItemDelegate):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # Prepare default style option and suppress text
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QStyle()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        # Determine state from display text
        text = index.data(Qt.ItemDataRole.DisplayRole)
        active = bool(text == "I")
        r = opt.rect
        size = min(r.height(), r.width(), 12)
        x = r.x() + (r.width() - size) // 2
        y = r.y() + (r.height() - size) // 2
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(150, 150, 150))
        painter.setBrush(self._color if active else QColor(0, 0, 0, 0))
        painter.drawEllipse(x, y, size, size)
        painter.restore()


class DataTable(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = _DataModel(self)
        self._proxy = _DataFilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self.setModel(self._proxy)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(True)
        self.setSortingEnabled(False)
        # QTableView doesn't support setUniformRowHeights (that's for QTreeView).
        # Prefer fixed row height via header and disable word wrap for perf.
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(22)

        # Column sizing: set reasonable defaults
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Auto-size columns to fit header text (plus padding), then allow user adjustment.
        try:
            fm = self.fontMetrics()
            padding = 20  # extra space for sort indicators / readability
            for col, header in enumerate(_COLS):
                w = fm.horizontalAdvance(header) + padding
                # Ensure a reasonable minimum width for value/stat columns
                if col == 0:  # Value column tends to hold numbers
                    w = max(w, 100)
                elif col == 6:  # Writer column may have names
                    w = max(w, 110)
                elif col in (7, 8, 9, 10, 11):  # rate/stat columns
                    w = max(w, 95)
                elif col in (1, 2, 3, 4, 5):  # boolean indicators
                    w = max(w, 55)
                self.setColumnWidth(col, w)
            hh.setStretchLastSection(True)  # Description column stretches to fill
        except Exception:
            # Fallback to previous static sizing on failure
            if len(_COLS) >= 13:
                hh.setStretchLastSection(True)
                self.setColumnWidth(0, 120)
                self.setColumnWidth(6, 120)
                for c in (7, 8, 9, 10, 11):
                    self.setColumnWidth(c, 90)
                for c in (1, 2, 3, 4, 5):
                    self.setColumnWidth(c, 55)
        # Coalesce frequent updates into periodic model flushes
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(50)  # 20 Hz UI update cap
        self._flush_timer.timeout.connect(self._model.flush)
        self._flush_timer.start()

        # Set custom boolean indicator delegates for columns 1..5
        colors = {
            1: QColor(0, 120, 215),   # Annun -> blue
            2: QColor(255, 165, 0),   # Old -> orange
            3: QColor(230, 0, 0),     # Bad -> red
            4: QColor(180, 0, 0),     # Fail -> dark red
            5: QColor(180, 0, 180),   # SFail -> magenta
        }
        for col, color in colors.items():
            self.setItemDelegateForColumn(col, BoolIndicatorDelegate(color, self))

        # Open Item Details on double-click
        self.doubleClicked.connect(self._open_item_for_index)


    def setActive(self, active: bool):
        if active:
            if not self._flush_timer.isActive():
                self._flush_timer.start()
        else:
            if self._flush_timer.isActive():
                self._flush_timer.stop()

    def setFilterText(self, text: str):
        self._proxy.setFilterText(text)

    # UI helpers
    def _open_item_for_index(self, proxy_index: QModelIndex):
        try:
            if not proxy_index or not proxy_index.isValid():
                return
            src_index = self._proxy.mapToSource(proxy_index)
            row = src_index.row()
            key = self._model.key_at(row)
            if not key:
                return
            dlg = ItemDialog(self)
            dlg.setKey(key)
            dlg.exec()
        except Exception:
            # Be resilient; avoid crashing UI on unexpected states
            import traceback
            print("Failed to open Item details:")
            traceback.print_exc()

    # Removed right-click context menu; use double-click to open the dialog


class DataPanel(QWidget):
    """Composite widget: filter box + data table."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = DataTable(self)
        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Filter by item name or writer…")
        self._filter.textChanged.connect(self._table.setFilterText)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._filter)
        lay.addWidget(self._table)

    # pass-through helpers used by gui.py
    def setActive(self, active: bool):
        self._table.setActive(active)

    # expose table for future extensions if needed
    @property
    def table(self) -> 'DataTable':
        return self._table
