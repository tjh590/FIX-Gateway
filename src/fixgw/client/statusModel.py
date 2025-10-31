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
from PyQt6.QtWidgets import QScrollArea, QLabel, QPlainTextEdit
import json
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

class StatusView(QScrollArea):
    def __init__(self, parent=None):
        super(StatusView, self).__init__(parent)
        self.setWidgetResizable(True)
        # Use a QPlainTextEdit for efficient large text updates
        self.textBox = QPlainTextEdit(self)
        self.textBox.setReadOnly(True)
        self.setWidget(self.textBox)
        self.connected = False
        self._perf = _PerfMonitor(self, tick_ms=100)

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

        self._w.got.connect(self._apply_status_json)
        self._w.err.connect(lambda e: None)  # optional logging

    def _apply_status_json(self, s):
        # Pretty-print JSON into the Status tab
        try:
            d = json.loads(s, object_pairs_hook=OrderedDict)
            # Inject client-side performance metrics into Performance subtree when present
            try:
                client_perf = self._perf.get_metrics()
                if isinstance(d.get("Performance"), dict):
                    d["Performance"]["Client (GUI)"] = client_perf
                else:
                    d["Client Performance"] = client_perf
            except Exception:
                pass
            pretty_json = json.dumps(d, indent=2)
            self.textBox.setPlainText(pretty_json)
        except Exception:
            # Fallback: show raw string if JSON parse fails
            self.textBox.setPlainText(str(s))

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
                self.textBox.setPlainText("")
                print("statusModel.update()", e)
                return
            d = json.loads(res, object_pairs_hook=OrderedDict)
            s = json.dumps(d, indent=2)
            # for key in connection.db.get_item_list():
            #     s += "{} = {}\n".format(key, connection.db.get_value(key))
            self.textBox.setPlainText(s)

    #def showEvent(self, QShowEvent):
    #    self.timer.start()

    #def hideEvent(self, QHideEvent):
    #    self.timer.stop()

    def shutdown(self):
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
