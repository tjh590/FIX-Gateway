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

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QScrollArea, QLabel
import json
from collections import OrderedDict

import fixgw.status as status
import fixgw.netfix as netfix
from . import connection

# TODO get the dictionary and convert to a tree view instead of just text

class _StatusWorker(QObject):
    got = pyqtSignal(str)
    err = pyqtSignal(str)
    def __init__(self, client):
        super().__init__()
        self.client = client
        self._in_flight = False
    def poll(self):
        if self._in_flight:
            return
        self._in_flight = True
        try:
            s = self.client.getStatus()  # same API, runs off the UI thread now
            self.got.emit(s)
        except Exception as e:
            self.err.emit(str(e))
        finally:
            self._in_flight = False

class StatusView(QScrollArea):
    def __init__(self, parent=None):
        super(StatusView, self).__init__(parent)
        self.setWidgetResizable(True)
        self.textBox = QLabel(self)
        self.setWidget(self.textBox)
        self.connected = False

        #self.timer = QTimer()
        #self.timer.setInterval(1000)
        #self.timer.timeout.connect(self.update)
        #self.update()

        # Use the dedicated status_client that does no subscriptions/pushes
        self._w = _StatusWorker(connection.status_client or connection.client)
        self._t = QThread(self)
        self._w.moveToThread(self._t)
        self._t.start()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._w.poll)
        self._timer.start()

        self._w.got.connect(self._apply_status_json)
        self._w.err.connect(lambda e: None)  # optional logging

    def _apply_status_json(self, s):
        # Pretty-print JSON into the Status tab
        try:
            d = json.loads(s, object_pairs_hook=OrderedDict)
            pretty_json = json.dumps(d, indent=2)
            self.textBox.setText(pretty_json)
        except Exception:
            # Fallback: show raw string if JSON parse fails
            self.textBox.setText(str(s))

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

    def update(self):
        if not self.connected:
            if connection.client.isConnected():
                self.connected = True
        else:
            self.textBox.clear()
            try:
                res = (connection.status_client or connection.client).getStatus()
            except netfix.NotConnectedError:
                self.connected = False
                return
            except Exception as e:
                self.textBox.setText("")
                print("statusModel.update()", e)
                return
            d = json.loads(res, object_pairs_hook=OrderedDict)
            s = json.dumps(d, indent=2)
            # for key in connection.db.get_item_list():
            #     s += "{} = {}\n".format(key, connection.db.get_value(key))
            self.textBox.setText(s)

    #def showEvent(self, QShowEvent):
    #    self.timer.start()

    #def hideEvent(self, QHideEvent):
    #    self.timer.stop()
