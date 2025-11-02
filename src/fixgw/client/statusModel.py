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

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, QModelIndex, Qt, QSortFilterProxyModel
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeView,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
import json
import os
from collections import OrderedDict
import threading
import time
import gc
try:
    import psutil  # optional on client side
except Exception:
    psutil = None

import fixgw.status as status
import fixgw.netfix as netfix
from . import connection

# TODO get the dictionary and convert to a tree view instead of just text

class _TreeFilterProxyModel(QSortFilterProxyModel):
    """Filter that matches substring in either Key or Value column.

    Ensures that if a child matches, its ancestors are also accepted so the tree shows the path.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ""
        try:
            # Case-insensitive contains
            self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        except Exception:
            pass

    def setFilterText(self, text: str):
        self._pattern = (text or "").strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._pattern:
            return True
        m = self.sourceModel()
        idx_key = m.index(source_row, 0, source_parent)
        idx_val = m.index(source_row, 1, source_parent)
        key_txt = str(m.data(idx_key) or "")
        val_txt = str(m.data(idx_val) or "")
        hay = f"{key_txt} {val_txt}".lower()
        if self._pattern.lower() in hay:
            return True
        # If any child matches, accept this row
        rows = m.rowCount(idx_key)
        for r in range(rows):
            if self.filterAcceptsRow(r, idx_key):
                return True
        return False

class _StatusWorker(QObject):
    got = pyqtSignal(str)
    err = pyqtSignal(str)
    def __init__(self, client):
        super().__init__()
        self.client = client
        self._in_flight = False
        self._last_sent = None
    def poll(self):
        if self._in_flight:
            return
        self._in_flight = True
        try:
            s = self.client.getStatus()  # same API, runs off the UI thread now
            # Emit only if changed to reduce UI churn
            if s != self._last_sent:
                self._last_sent = s
                self.got.emit(s)
        except Exception as e:
            self.err.emit(str(e))
        finally:
            self._in_flight = False


class _PerfMonitor(QObject):
    """Collect lightweight client-side performance metrics.

    - Python process CPU/memory (if psutil available)
    - Python thread count
    - GC generation counters
    - Qt event-loop tick jitter using a periodic QTimer
    """

    def __init__(self, parent=None, tick_ms=100):
        super().__init__(parent)
        self._tick_ms = max(10, int(tick_ms))
        self._last_tick = None
        self._last_tick_ms = None
        self._jitters = []  # store recent jitter samples (ms)
        self._jitters_maxlen = 50
        self._dts = []  # store recent dt samples (ms)
        self._dts_maxlen = 50
        self._missed_ticks = 0
        self._timer = QTimer(self)
        self._timer.setInterval(self._tick_ms)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        self._proc = psutil.Process() if psutil is not None else None

    def _on_tick(self):
        now = time.perf_counter()
        if self._last_tick is None:
            self._last_tick = now
            self._last_tick_ms = 0.0
            return
        dt_ms = (now - self._last_tick) * 1000.0
        self._last_tick = now
        self._last_tick_ms = dt_ms
        # Jitter: how much later than target
        jitter = max(0.0, dt_ms - float(self._tick_ms))
        self._jitters.append(jitter)
        if len(self._jitters) > self._jitters_maxlen:
            self._jitters.pop(0)
        # Track dt history and missed ticks (>= 2x target interval)
        self._dts.append(dt_ms)
        if len(self._dts) > self._dts_maxlen:
            self._dts.pop(0)
        if dt_ms >= (2.0 * self._tick_ms):
            self._missed_ticks += 1

    def _fmt(self, x, nd=2):
        if x is None:
            return None
        return round(float(x), nd)

    def get_metrics(self):
        d = OrderedDict()
        # Python/Process
        if self._proc is not None:
            try:
                d["CPU Percent"] = self._fmt(self._proc.cpu_percent(interval=0.0))
                d["Memory Percent"] = self._fmt(self._proc.memory_percent())
                d["RSS MB"] = self._fmt(self._proc.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                pass
        d["Threads"] = threading.active_count()
        try:
            d["GC Gen Counts"] = list(gc.get_count())
        except Exception:
            d["GC Gen Counts"] = None
        # Qt tick metrics
        if self._last_tick_ms is not None:
            d["Qt Tick Target ms"] = self._tick_ms
            d["Qt Last Tick ms"] = self._fmt(self._last_tick_ms, 2)
            if self._jitters:
                avg = sum(self._jitters) / len(self._jitters)
                mx = max(self._jitters)
            else:
                avg = 0.0
                mx = 0.0
            d["Qt Jitter Avg ms"] = self._fmt(avg, 2)
            d["Qt Jitter Max ms"] = self._fmt(mx, 2)
            if self._dts:
                avg_dt = sum(self._dts) / len(self._dts)
                ticks_per_sec = 1000.0 / max(1e-6, avg_dt)
                d["Qt Ticks/sec (avg)"] = self._fmt(ticks_per_sec, 2)
            d["Qt Missed Ticks (>=2x)"] = int(self._missed_ticks)
        return d

class StatusView(QWidget):
    def __init__(self, parent=None, client_name: str | None = None):
        super(StatusView, self).__init__(parent)
        # Layout with controls + tree view
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(6)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        self._btn_expand = QPushButton("Expand All", self)
        self._btn_collapse = QPushButton("Collapse All", self)
        self._btn_expand.clicked.connect(self._expand_all_and_save)
        self._btn_collapse.clicked.connect(self._collapse_all_and_save)
        controls.addWidget(self._btn_expand)
        controls.addWidget(self._btn_collapse)
        controls.addStretch(1)
        # Quick filter box
        try:
            from PyQt6.QtWidgets import QLineEdit, QLabel
            self._filter_row = QHBoxLayout()
            self._filter_row.setContentsMargins(0, 0, 0, 0)
            self._filter_row.setSpacing(6)
            self._filter_label = QLabel("Filter:", self)
            self._filter_edit = QLineEdit(self)
            self._filter_edit.setPlaceholderText("Search keys and values…")
            self._filter_row.addWidget(self._filter_label)
            self._filter_row.addWidget(self._filter_edit, 1)
            self._root_layout.addLayout(self._filter_row)
        except Exception:
            self._filter_edit = None

        self._tree = QTreeView(self)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setHeaderHidden(False)
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["Key", "Value"])
        # Proxy for filtering
        try:
            from PyQt6.QtCore import QSortFilterProxyModel
            self._proxy = _TreeFilterProxyModel(self)
            self._proxy.setSourceModel(self._model)
            self._tree.setModel(self._proxy)
        except Exception:
            self._proxy = None
            self._tree.setModel(self._model)

        self._root_layout.addLayout(controls)
        self._root_layout.addWidget(self._tree)
        self.connected = False
        self._perf = _PerfMonitor(self, tick_ms=100)
        # Client identity for persistence (None -> 'noname')
        self._client_name = client_name or "noname"
        self._expanded_paths = set()
        self._expanded_paths_unfiltered = set()
        self._pending_column_widths = []
        # Load any persisted state early; it will be applied after the first model build
        try:
            st = self._load_persisted_state()
            if st and st.get("paths"):
                self._expanded_paths = st.get("paths", set())
            self._pending_column_widths = st.get("columns", []) if st else []
        except Exception:
            self._pending_column_widths = []

        # Track user expand/collapse interactions to persist across updates
        try:
            self._tree.expanded.connect(self._on_expanded)
            self._tree.collapsed.connect(self._on_collapsed)
        except Exception:
            pass

        # Apply persisted column widths if present
        try:
            if isinstance(self._pending_column_widths, list):
                if len(self._pending_column_widths) >= 1:
                    self._tree.setColumnWidth(0, int(self._pending_column_widths[0]))
                if len(self._pending_column_widths) >= 2:
                    self._tree.setColumnWidth(1, int(self._pending_column_widths[1]))
        except Exception:
            pass

        # Wire filter behavior
        try:
            if self._filter_edit is not None and self._proxy is not None:
                self._filter_edit.textChanged.connect(self._on_filter_changed)
        except Exception:
            pass
        #self.timer = QTimer()
        #self.timer.setInterval(1000)
        #self.timer.timeout.connect(self.update)
        #self.update()

        # Use the dedicated status_client that does no subscriptions/pushes
        self._w = _StatusWorker(connection.status_client or connection.client)
        self._t = QThread(self)
        self._w.moveToThread(self._t)
        self._t.start()

        # Drive the worker from a GUI-thread timer using a queued connection
        self._timer = QTimer(self)
        self._timer.setInterval(1500)  # slightly slower to reduce churn
        self._timer.setSingleShot(False)
        # Because _w lives in a different thread, this becomes a queued connection
        self._timer.timeout.connect(self._w.poll)
        self._timer.start()

        # Connect worker signals
        self._w.got.connect(self._apply_status_json)
        self._w.err.connect(lambda e: None)  # optional logging

    def _apply_status_json(self, s):
        # Parse JSON and populate the tree model
        try:
            d = json.loads(s, object_pairs_hook=OrderedDict)
            # Inject client-side performance metrics
            try:
                client_perf = self._perf.get_metrics()
                if isinstance(d.get("Performance"), dict):
                    d["Performance"]["Client (GUI)"] = client_perf
                else:
                    d["Client Performance"] = client_perf
            except Exception:
                pass

            # Also inject local client connection names so they're visible even
            # if the server doesn't support naming yet.
            try:
                local_names = OrderedDict()
                from . import connection as _conn
                name_data = getattr(_conn.client, "_client_name", None)
                if name_data:
                    local_names["Data"] = name_data
                sc = getattr(_conn, "status_client", None)
                if sc is not None and sc is not _conn.client:
                    name_info = getattr(sc, "_client_name", None)
                    if name_info:
                        local_names["Info"] = name_info
                if local_names:
                    if "Client" not in d or not isinstance(d.get("Client"), dict):
                        d["Client"] = OrderedDict()
                    d["Client"]["Connection Names"] = local_names
            except Exception:
                pass
            # Preserve current expansion paths across rebuild
            restore_paths = set(self._expanded_paths) if self._expanded_paths is not None else set()
            self._populate_tree(d)
            # Restore expansion state
            if restore_paths:
                self._restore_expanded_paths(restore_paths)
        except Exception:
            # If JSON parse fails, show a single root with raw text
            self._populate_tree({"raw": str(s)})

    def _populate_tree(self, data):
        # Rebuild the model from a nested dict/list tree
        model = QStandardItemModel(self)
        model.setHorizontalHeaderLabels(["Key", "Value"])

        def add_node(parent, key, value):
            # If this looks like a per-connection entry and it has a Name field,
            # annotate the display label with the name.
            display_key = str(key)
            # Rewrite top-level 'Connection: X' to 'Plugin: X' when there are no
            # TCP connection details in that plugin's status. We detect this by
            # absence of common connection fields at that node.
            try:
                is_top_level = parent is root
                if is_top_level and display_key.startswith("Connection: ") and isinstance(value, dict):
                    has_conn_fields = (
                        ("Current Connections" in value)
                        or any(str(k).startswith("Connection ") for k in value.keys())
                    )
                    if not has_conn_fields:
                        display_key = display_key.replace("Connection:", "Plugin:", 1)
            except Exception:
                pass
            if isinstance(value, dict):
                try:
                    nm = value.get("Name")
                    cli = value.get("Client")
                    ip_port = None
                    if isinstance(cli, (list, tuple)) and len(cli) >= 2:
                        ip_port = f"{cli[0]}:{cli[1]}"
                    elif isinstance(cli, str):
                        # If server encoded as string already
                        ip_port = cli
                    if display_key.startswith("Connection "):
                        if nm and ip_port:
                            display_key = f"{display_key} ({nm} @ {ip_port})"
                        elif nm:
                            display_key = f"{display_key} ({nm})"
                        elif ip_port:
                            display_key = f"{display_key} ({ip_port})"
                except Exception:
                    pass
            key_item = QStandardItem(display_key)
            # Store a stable token (original key) to ensure exact restore
            try:
                key_item.setData(str(key), int(Qt.ItemDataRole.UserRole))
            except Exception:
                pass
            val_item = QStandardItem("")
            # Leaf node
            if not isinstance(value, (dict, list)):
                val_item.setText(str(value))
                key_item.setEditable(False)
                val_item.setEditable(False)
                parent.appendRow([key_item, val_item])
                return
            # Container node
            key_item.setEditable(False)
            val_item.setEditable(False)
            parent.appendRow([key_item, val_item])
            container = key_item
            if isinstance(value, dict):
                for k, v in value.items():
                    add_node(container, k, v)
            elif isinstance(value, list):
                for idx, v in enumerate(value):
                    add_node(container, f"[{idx}]", v)

        # Top-level: if dict, add each item; else add as a single root value
        root = model.invisibleRootItem()
        if isinstance(data, dict):
            for k, v in data.items():
                add_node(root, k, v)
        else:
            add_node(root, "root", data)

        self._model = model
        if self._proxy is not None:
            self._proxy.setSourceModel(self._model)
            self._tree.setModel(self._proxy)
        else:
            self._tree.setModel(self._model)

    # --- Expansion state persistence helpers ---
    def _index_to_path(self, index: QModelIndex):
        try:
            idx = index.sibling(index.row(), 0)
        except Exception:
            idx = index
        path = []
        # Use the view's model (proxy-aware) when reading keys
        m = self._tree.model() if hasattr(self._tree, "model") else self._model
        while idx.isValid():
            try:
                key = m.data(idx, int(Qt.ItemDataRole.UserRole))
                if key is None:
                    key = m.data(idx)
            except Exception:
                key = None
            path.append(str(key))
            idx = idx.parent()
        return tuple(reversed(path))

    def _get_expanded_paths(self):
        paths = set()
        # Work on the view's model (proxy-aware)
        vm = self._tree.model() if hasattr(self._tree, "model") else self._model
        m = vm

        def visit(parent_idx: QModelIndex, parent_path: tuple):
            rows = m.rowCount(parent_idx)
            for r in range(rows):
                idx = m.index(r, 0, parent_idx)
                key = m.data(idx, int(Qt.ItemDataRole.UserRole))
                if key is None:
                    key = m.data(idx)
                this_path = parent_path + (str(key),)
                if self._tree.isExpanded(idx):
                    paths.add(this_path)
                visit(idx, this_path)

        visit(QModelIndex(), tuple())
        return paths

    def _restore_expanded_paths(self, paths: set):
        # Work on the view's model (proxy-aware)
        vm = self._tree.model() if hasattr(self._tree, "model") else self._model
        m = vm

        def visit(parent_idx: QModelIndex, parent_path: tuple):
            rows = m.rowCount(parent_idx)
            for r in range(rows):
                idx = m.index(r, 0, parent_idx)
                key = m.data(idx, int(Qt.ItemDataRole.UserRole))
                if key is None:
                    key = m.data(idx)
                this_path = parent_path + (str(key),)
                if this_path in paths:
                    try:
                        self._tree.expand(idx)
                    except Exception:
                        pass
                visit(idx, this_path)

        visit(QModelIndex(), tuple())
        # Save back the final expanded set (in case some paths were missing)
        try:
            self._expanded_paths = self._get_expanded_paths()
        except Exception:
            pass

    def _on_expanded(self, index: QModelIndex):
        try:
            p = self._index_to_path(index)
            self._expanded_paths.add(p)
        except Exception:
            pass

    def _on_collapsed(self, index: QModelIndex):
        try:
            p = self._index_to_path(index)
            if p in self._expanded_paths:
                self._expanded_paths.discard(p)
        except Exception:
            pass

    def _expand_all_and_save(self):
        try:
            self._tree.expandAll()
            self._expanded_paths = self._get_expanded_paths()
        except Exception:
            pass

    def _collapse_all_and_save(self):
        try:
            self._tree.collapseAll()
            self._expanded_paths.clear()
        except Exception:
            pass

    # --- Filter handlers ---
    def _on_filter_changed(self, text: str):
        try:
            if self._proxy is None:
                return
            t = (text or "").strip()
            if t:
                # Save unfiltered expansion once when entering filtered state
                if not self._expanded_paths_unfiltered:
                    self._expanded_paths_unfiltered = set(self._expanded_paths)
                self._proxy.setFilterText(t)
                self._tree.expandAll()
            else:
                self._proxy.setFilterText("")
                # Restore previous expansion state
                if self._expanded_paths_unfiltered:
                    self._restore_expanded_paths(self._expanded_paths_unfiltered)
                self._expanded_paths_unfiltered.clear()
        except Exception:
            pass

    # def __init__(self, parent=None):
    #     super(StatusView, self).__init__(parent)
    #     self.setWidgetResizable(True)
    #     self.textBox = QLabel(self)
    #     self.setWidget(self.textBox)
    #     self.connected = False

    #     self.timer = QTimer()
    #     self.timer.setInterval(1000)
    #     self.timer.timeout.connect(self.update)
    #     self.update()

    # Deprecated legacy text update method removed; tree view is updated by _StatusWorker

    #def showEvent(self, QShowEvent):
    #    self.timer.start()

    #def hideEvent(self, QHideEvent):
    #    self.timer.stop()

    def shutdown(self):
        # Persist expansion state and column widths before shutting down
        try:
            self._save_persisted_state()
        except Exception:
            pass
        # Stop timers first
        try:
            if hasattr(self, "_timer"):
                self._timer.stop()
        except Exception:
            pass
        # Stop perf monitor timer if present
        try:
            if hasattr(self, "_perf") and hasattr(self._perf, "_timer"):
                self._perf._timer.stop()
        except Exception:
            pass
        # Cleanly stop worker thread
        try:
            if hasattr(self, "_t") and self._t is not None:
                self._t.quit()
                self._t.wait(2000)
        except Exception:
            pass

    # --- Persistence helpers ---
    def _persist_dir(self) -> str:
        # Always use ~/.config/fixgwclient
        path = os.path.join(os.path.expanduser("~"), ".config", "fixgwclient")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return path

    def _persist_file(self) -> str:
        name = self._client_name or "noname"
        safe = "".join(ch if (ch.isalnum() or ch in ("-", "_", ".")) else "_" for ch in str(name))
        return os.path.join(self._persist_dir(), f"status_state_{safe}.json")

    def _load_persisted_state(self) -> dict:
        fn = self._persist_file()
        try:
            if not os.path.isfile(fn):
                # Backward-compat: try old filename if present
                old_fn = os.path.join(self._persist_dir(), os.path.basename(fn).replace("status_state_", "status_expansion_"))
                if os.path.isfile(old_fn):
                    fn = old_fn
                else:
                    return {}
            with open(fn, "r", encoding="utf-8") as f:
                payload = json.load(f)
            paths = payload.get("paths", [])
            s = set()
            for p in paths:
                try:
                    s.add(tuple(str(x) for x in p))
                except Exception:
                    continue
            columns = payload.get("columns", [])
            return {"paths": s, "columns": columns}
        except Exception:
            return {}

    def _save_persisted_state(self):
        # Prefer unfiltered expansion snapshot if present
        paths_set = self._expanded_paths_unfiltered if self._expanded_paths_unfiltered else self._expanded_paths
        try:
            columns = [
                int(self._tree.columnWidth(0)),
                int(self._tree.columnWidth(1)),
            ]
        except Exception:
            columns = []
        try:
            payload = {
                "version": 2,
                "paths": [list(p) for p in sorted(paths_set)],
                "columns": columns,
            }
            fn = self._persist_file()
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass
