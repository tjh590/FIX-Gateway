#  Copyright (c) 2019 Phil Birkelbach
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

#  This is the gui client.  It gives us a graphical interface into the
#  inner workings of the gateway.

import sys

from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtCore import QByteArray
import os, json

from . import connection
from .ui.main_ui import Ui_MainWindow

from . import table
from . import statusModel

# from . import simulate


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, client_name: str | None = None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        # self.client = client
        self._client_name = client_name
        self.statusview = statusModel.StatusView(client_name=self._client_name)
        self.layoutStatus.addWidget(self.statusview)
        # Data tab: quick filter + table
        self.dataview = table.DataPanel()
        self.layoutData.addWidget(self.dataview)
        
        # Remove the unused "Simulate" tab
        idx = self.tabWidget.indexOf(self.tabSimulate)
        if idx != -1:
            self.tabWidget.removeTab(idx)
       
        self.tabWidget.currentChanged.connect(self._on_tab)

        # Restore window geometry if available
        try:
            g = self._load_window_state().get("geometry")
            if g:
                self.restoreGeometry(QByteArray.fromHex(g.encode("ascii")))
        except Exception:
            pass

        self.show()

    def closeEvent(self, event):
        # Save window geometry
        try:
            state = self._load_window_state()
            state["geometry"] = bytes(self.saveGeometry().toHex()).decode("ascii")
            self._save_window_state(state)
        except Exception:
            pass
        # Attempt to disconnect the dedicated status client cleanly
        try:
            from . import connection
            # Stop background DB polling first
            try:
                if hasattr(connection, 'shutdown'):
                    connection.shutdown()
            except Exception:
                pass
            if connection.status_client is not None and connection.status_client is not connection.client:
                connection.status_client.disconnect()
        except Exception:
            pass
        # Stop background timers/threads in StatusView
        try:
            if hasattr(self, "statusview") and hasattr(self.statusview, "shutdown"):
                self.statusview.shutdown()
        except Exception:
            pass
        return super().closeEvent(event)

    def _on_tab(self, idx):
        # 0 == Status tab in current UI
        try:
            self.statusview._timer.setActive(idx == 0)  # if you wrap start/stop
        except AttributeError:
            if idx == 0:
                self.statusview._timer.start()
            else:
                self.statusview._timer.stop()
        # 1 == Data tab in current UI
        try:
            self.dataview.setActive(idx == 1)
        except Exception:
            pass

    # --- Window state persistence ---
    def _persist_dir(self) -> str:
        # Always use ~/.config/fixgwclient
        path = os.path.join(os.path.expanduser("~"), ".config", "fixgwclient")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return path

    def _state_file(self) -> str:
        name = self._client_name or "noname"
        safe = "".join(ch if (ch.isalnum() or ch in ("-", "_", ".")) else "_" for ch in str(name))
        return os.path.join(self._persist_dir(), f"window_state_{safe}.json")

    def _load_window_state(self) -> dict:
        fn = self._state_file()
        try:
            if not os.path.isfile(fn):
                return {}
            with open(fn, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_window_state(self, state: dict):
        try:
            fn = self._state_file()
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

def main(client, name=None):
    connection.initialize(client)
    app = QApplication(sys.argv)
    app.setApplicationName("FIX Gateway Client")
    # If a name is provided, name the status (Info) connection as well
    try:
        if name and getattr(connection, 'status_client', None):
            # Only name the Info connection if it's a separate socket
            if connection.status_client is not client:
                connection.status_client.setName(f"{name}.Info")
    except Exception:
        pass

    window = MainWindow(client_name=name)
    x = app.exec()
    return x
