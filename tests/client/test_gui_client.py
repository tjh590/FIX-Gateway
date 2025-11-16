import json
import time
from collections import OrderedDict

import pytest
from PyQt6.QtCore import QModelIndex

import fixgw.database as database
from fixgw.client import gui as client_gui
from fixgw.client import connection
import fixgw.netfix.QtDb as QtDb


class LocalClient:
    """Minimal in-process client that mirrors the netfix.Client API
    used by fixgw.netfix.db.Database, but operates on fixgw.database.
    """

    def __init__(self):
        self._connect_cb = None
        self._data_cb = None
        self._connected = True
        self._client_name = "LocalTest"
        # Minimal thread-like object expected by netfix.db for reportCallback
        class _CT:
            def __init__(self):
                self.reportCallback = None
                self.host = "local"
                self.port = 0
        self.cthread = _CT()

    # Connection API
    def connect(self):
        if self._connect_cb:
            try:
                self._connect_cb(True)
            except Exception:
                pass
        return True

    def disconnect(self):
        if self._connect_cb:
            try:
                self._connect_cb(False)
            except Exception:
                pass

    def isConnected(self):
        return True

    def setConnectCallback(self, func):
        self._connect_cb = func

    def clearConnectCallback(self):
        self._connect_cb = None

    def setDataCallback(self, func):
        self._data_cb = func

    def clearDataCallback(self):
        self._data_cb = None

    # Data plane API
    def getList(self):
        return database.listkeys()

    def getReport(self, key):
        item = database.get_raw_item(key)
        aux_csv = ",".join(item.get_aux_list())
        stats = database.get_rate_stats(key)
        last_writer = stats.get("last_writer") if stats else database.get_last_writer(key)
        rate_min = stats.get("min") if stats else None
        rate_max = stats.get("max") if stats else None
        rate_avg = stats.get("avg") if stats else None
        rate_stdev = stats.get("stdev") if stats else None
        rate_samples = stats.get("samples") if stats else 0
        extras = [
            last_writer or "",
            f"{rate_min:.6f}" if isinstance(rate_min, (int, float)) else "",
            f"{rate_max:.6f}" if isinstance(rate_max, (int, float)) else "",
            f"{rate_avg:.6f}" if isinstance(rate_avg, (int, float)) else "",
            f"{rate_stdev:.6f}" if isinstance(rate_stdev, (int, float)) else "",
            str(int(rate_samples or 0)),
        ]
        return [
            key,
            item.description or "",
            item.typestring,
            str(item.min),
            str(item.max),
            item.units or "",
            str(item.tol),
            aux_csv,
            *extras,
        ]

    def read(self, key):
        if "." in key:
            ident, aux = key.split(".", 1)
            val = database.read(key)
            return (key, val, "")
        val, ann, old, bad, fail, sec = database.read(key)
        flags = ("1" if ann else "0") + ("1" if old else "0") + ("1" if bad else "0") + ("1" if fail else "0") + ("1" if sec else "0")
        return (key, val, flags)

    def writeValue(self, key, value):
        database.write(key, value, source=self._client_name)
        # echo back id;value;flags (all zeros here)
        return f"{key};{value};00000"

    def flag(self, key, flag, setting):
        # Map to database raw item flags
        try:
            it = database.get_raw_item(key)
            if flag == "a":
                it._annunciate = bool(setting)
            elif flag == "o":
                it._old = bool(setting)
            elif flag == "b":
                it._bad = bool(setting)
            elif flag == "f":
                it._fail = bool(setting)
            elif flag == "s":
                it._secfail = bool(setting)
        except Exception:
            pass
        return f"@f{key}"

    def subscribe(self, *args, **kwargs):
        return None

    def unsubscribe(self, *args, **kwargs):
        return None

    def subscribeReport(self, *args, **kwargs):
        return None

    def unsubscribeReport(self, *args, **kwargs):
        return None

    # Status API used by StatusView
    def getStatus(self):
        d = OrderedDict()
        d["Plugin: demo"] = OrderedDict({"Item Count": len(database.listkeys())})
        return json.dumps(d)

    # Optional name used by GUI
    def setName(self, name: str):
        self._client_name = str(name)


@pytest.fixture
def local_client(database):
    # Ensure DB initialized by the database fixture
    c = LocalClient()
    c.connect()
    return c


@pytest.fixture
def main_window(qtbot, monkeypatch, local_client):
    # Patch connection.initialize to use our LocalClient and direct QtDb
    def fake_initialize(c):
        connection.client = c
        connection.status_client = c
        connection.db = QtDb.Database(c)

    monkeypatch.setattr(connection, "initialize", fake_initialize)

    # Also set client references as if invoked through CLI
    connection.initialize(local_client)
    w = client_gui.MainWindow(client_name="TestClient")
    qtbot.addWidget(w)
    return w


@pytest.fixture
def seed_ias(database):
    # Write a known value before the GUI and client DB are initialized
    database.write("IAS", 123.45, source="unittest")
    return True


def _find_tree_item_text(view, text: str) -> list[QModelIndex]:
    # Returns a list of indexes whose display text matches exactly
    model = view.model()
    matches = []

    def recurse(parent_idx: QModelIndex):
        rows = model.rowCount(parent_idx)
        for r in range(rows):
            idx = model.index(r, 0, parent_idx)
            if model.data(idx) == text:
                matches.append(idx)
            recurse(idx)

    recurse(QModelIndex())
    return matches


def test_status_tab_tree_shows_item_count(qtbot, main_window):
    # Let the polling timer run at least once
    qtbot.waitUntil(lambda: main_window.statusview._tree.model().rowCount() > 0, timeout=3000)
    # Expand all to make search simpler
    main_window.statusview._tree.expandAll()
    idxs = _find_tree_item_text(main_window.statusview._tree, "Item Count")
    assert idxs, "Expected 'Item Count' node in Status tree"
    # Verify its value matches DB
    model = main_window.statusview._tree.model()
    for idx in idxs:
        val_idx = model.index(idx.row(), 1, idx.parent())
        val = model.data(val_idx)
        assert str(val).isdigit()
        assert int(val) == len(database.listkeys())
        break


def test_data_tab_table_displays_values(qtbot, seed_ias, main_window):
    # Switch to Data tab
    try:
        tw = main_window.tabWidget
        for i in range(tw.count()):
            if tw.tabText(i).lower() == "data":
                tw.setCurrentIndex(i)
                break
    except Exception:
        pass

    # Allow model to build and flush
    qtbot.wait(200)
    table = main_window.dataview.table
    # Find 'IAS' row in the source model
    model = table._model  # _DataModel
    row = None
    for r in range(model.rowCount()):
        if model.key_at(r) == "IAS":
            row = r
            break
    assert row is not None, "IAS row not found"
    # Map to proxy and read Value (col 0) and Description (col 12)
    src_val_idx = model.index(row, 0)
    src_desc_idx = model.index(row, 12)
    prox_val_idx = table._proxy.mapFromSource(src_val_idx)
    prox_desc_idx = table._proxy.mapFromSource(src_desc_idx)
    assert table.model().data(prox_val_idx) in ("123.45", "123.5", "123.450000")
    assert "Airspeed" in str(table.model().data(prox_desc_idx))


def test_item_details_dialog_updates_value(qtbot, main_window):
    # Open item dialog for IAS and change value
    from fixgw.client.dbItemDialog import ItemDialog

    dlg = ItemDialog(main_window)
    dlg.setKey("IAS")
    qtbot.addWidget(dlg)
    # Locate the main value editor control and set a new value
    editor = getattr(dlg, "_valueControl", None)
    assert editor is not None
    # Change the value via editor APIs to trigger signal bindings
    target = 150.0
    if hasattr(editor, "setValue"):
        editor.setValue(target)
    elif hasattr(editor, "setText"):
        editor.setText(str(target))
    # Allow signal processing
    qtbot.wait(50)
    # Verify the database value was updated
    val = database.read("IAS")[0]
    assert pytest.approx(val, rel=0.0, abs=1e-6) == target
    # Close the dialog
    dlg.close()
