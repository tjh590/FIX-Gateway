#  Copyright (c) 2018 Phil Birkelbach
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
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# This is the FIX-Net client library for FIX-Gateway

import queue, threading
import socket
import logging
import time

try:
    import queue
except:
    import Queue as queue

log = logging.getLogger(__name__)


class ResponseError(Exception):
    pass


class SendError(Exception):
    pass


class NotConnectedError(Exception):
    pass


# A convenience class for working with the get_report() response.
class Report:
    def __init__(self, res):
        self.desc = res[1]
        self.dtype = res[2]
        self.min = res[3]
        self.max = res[4]
        self.units = res[5]
        self.tol = res[6]
        self.aux = []
        if res[7]:
            x = res[7].split(",")
            for aux in x:
                self.aux.append(aux)

        def _as_float(value):
            return float(value) if value not in ("", None) else None

        def _as_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        extras = res[8:] if len(res) > 8 else []
        self.last_writer = extras[0] if len(extras) > 0 and extras[0] else None
        self.rate_min = _as_float(extras[1]) if len(extras) > 1 else None
        self.rate_max = _as_float(extras[2]) if len(extras) > 2 else None
        self.rate_avg = _as_float(extras[3]) if len(extras) > 3 else None
        self.rate_stdev = _as_float(extras[4]) if len(extras) > 4 else None
        samples_value = extras[5] if len(extras) > 5 else None
        self.rate_samples = _as_int(samples_value) if samples_value not in ("", None) else 0

    def __str__(self):
        return "{}:{}".format(self.desc, self.units)


# This is the main communication thread of the FIX Gateway client.
class ClientThread(threading.Thread):
    def __init__(self, host, port):
        super(ClientThread, self).__init__()
        self.daemon = True
        self.host = host
        self.port = port
        self.getout = False
        self.timeout = 1.0
        self.s = None
        # This Queue will hold normal data parameter responses
        # self.dataqueue = queue.Queue()
        # This Queue will hold command responses
        self.cmdqueue = queue.Queue()
        self.connectedEvent = threading.Event()
        # Callbeack function for connection events.  Passes True for connected
        # and False for disconnected
        self.connectCallback = None
        self.dataCallback = None

        self.dataqueue = queue.Queue(maxsize=5000)
        self._dispatcher_stop = threading.Event()
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True)
        self.reportCallback = None

    def connectedState(self, connected):
        if connected:
            self.connectedEvent.set()
        else:
            self.connectedEvent.clear()
        if self.connectCallback is not None:
            self.connectCallback(connected)

    def handle_request(self, d):
        if d.startswith("#q"):  # server-pushed report
            if self.reportCallback:
                self.reportCallback(d[2:])  # hand off payload
            return
                
        log.debug("Response - {}".format(d))
        if d[0] == "@":
            self.cmdqueue.put([d[1], d[2:]])
        else:
            x = d.split(";")
            if len(x) != 3 and len(x) != 2:
                log.error("Bad Data Sentence Received")
            if len(x) == 3:
                s = ""
                if x[2][0] == "1": s += "a"
                if x[2][1] == "1": s += "o"
                if x[2][2] == "1": s += "b"
                if x[2][3] == "1": s += "f"
                if x[2][4] == "1": s += "s"
                x[2] = s
            # Defer to dispatcher instead of calling dataCallback inline
            try:
                self.dataqueue.put_nowait(x)
            except queue.Full:
                log.debug("Dropping update due to backpressure")

    def _dispatch_loop(self):
        while not self._dispatcher_stop.is_set():
            try:
                x = self.dataqueue.get(timeout=0.5)
            except queue.Empty:
                continue
            if x is None:
                break
            if self.dataCallback:
                try:
                    self.dataCallback(x)
                except Exception as e:
                    log.error("dataCallback error: %s", e)

    def run(self):
        log.debug("ClientThread - Starting")

        if not self._dispatcher.is_alive():
            self._dispatcher.start()

        while True:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.settimeout(self.timeout)

            try:
                self.s.connect((self.host, self.port))
            except Exception as e:
                log.debug("Failed to connect {0}".format(e))
            else:
                log.debug("Connected to {0}:{1}".format(self.host, self.port))
                self.connectedState(True)

                buff = ""
                while True:
                    try:
                        data = self.s.recv(1024)
                    except socket.timeout:
                        if self.getout:
                            self.connectedState(False)
                            self.s.close()
                            break
                    except Exception as e:
                        log.error("Receive Failure {0}".format(e))
                        break
                    else:
                        if not data:
                            log.error("No Data, Bailing Out")
                            self.connectedState(False)
                            break
                        else:
                            try:
                                dstring = data.decode("utf-8")
                            except UnicodeDecodeError:
                                self.log.debug(
                                    "Bad Message from {0}".format(self.addr[0])
                                )
                            for d in dstring:
                                if d == "\n":
                                    try:
                                        self.handle_request(buff)
                                    except Exception as e:
                                        # TODO: Print file and line number here.  Use traceback module
                                        log.error(
                                            "Error handling request {} - {}".format(
                                                buff, e
                                            )
                                        )
                                    buff = ""
                                else:
                                    buff += d
            if self.getout:
                self.connectedState(False)
                self.s.close()
                log.debug("ClientThread - Exiting")
                break
            else:
                # TODO: Replace with configuration time
                time.sleep(2)
                log.debug(
                    "Attempting to Reconnect to {0}:{1}".format(self.host, self.port)
                )

    def stop(self):
        self.getout = True
        self._dispatcher_stop.set()
        try:
            self.dataqueue.put_nowait(None)
        except Exception:
            pass

    def connectWait(self, timeout=1.0):
        return self.connectedEvent.wait(timeout)

    def isConnected(self):
        return self.connectedEvent.is_set()

    def getResponse(self, c, timeout=1.0):
        # TODO Check for errors and report those as well
        if not self.isConnected():
            raise ResponseError("Not Connected to Server")
        # Honor the caller's timeout budget
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ResponseError("Timeout waiting on data")
            try:
                x = self.cmdqueue.get(timeout=remaining)
            except queue.Empty:
                raise ResponseError("Timeout waiting on data")
            if x[0] == c:
                return x
            
    def send(self, s):
        if not self.isConnected():
            raise NotConnectedError("Not Connected to Server")
        self.s.send(s)


def decodeDataString(d):
    if "!" in d:  # This is an error
        x = d.split("!")
        return int(x[1])
    x = d.split(";")
    id = x[0]
    v = x[1]
    if len(x) == 3:
        f = ""  # Quality Flags
        if x[2][0] == "1":
            f += "a"
        if x[2][1] == "1":
            f += "o"
        if x[2][2] == "1":
            f += "b"
        if x[2][3] == "1":
            f += "f"
        if x[2][4] == "1":
            f += "s"
        return (id, v, f)
    else:
        return (id, v)


class Client:
    def __init__(self, host, port, timeout=1.0):
        self.cthread = ClientThread(host, port)
        self.cthread.timeout = timeout
        self.cthread.daemon = True
        self.lock = threading.Lock()

    def subscribeReport(self, key, interval_ms=1000):
        with self.lock:
            self.cthread.send(f"@Q{key};{interval_ms}\n".encode())
            # Do not block; server may not ack @Q. Best-effort short wait only.
            try:
                self.cthread.getResponse("Q", timeout=0.05)
            except Exception:
                pass

    def unsubscribeReport(self, key):
        with self.lock:
            self.cthread.send(f"@UQ{key}\n".encode())
            # Do not block; best-effort short wait only.
            try:
                self.cthread.getResponse("U", timeout=0.05)
            except Exception:
                pass
            
    def connect(self):
        self.cthread.start()
        return self.cthread.connectWait()

    def disconnect(self):
        self.cthread.stop()
        # TODO: Block unit disconnected.

    def isConnected(self):
        return self.cthread.isConnected()

    def setDataCallback(self, func):
        self.cthread.dataCallback = func

    def clearDataCallback(self):
        self.cthread.dataCallback = None

    def setConnectCallback(self, func):
        self.cthread.connectCallback = func

    def clearConnectCallback(self):
        self.cthread.connectCallback = None

    def getList(self):
        # Request list and read fragments until the server indicates end.
        with self.lock:
            self.cthread.send("@l\n".encode())
            total = []
            while True:
                try:
                    res = self.cthread.getResponse("l", timeout=self.cthread.timeout)
                except ResponseError:
                    # No more fragments (or server slow) -> stop gracefully
                    break
                parts = res[1].split(";")
                # parts[2] is a comma-separated chunk; blank or short means done
                if len(parts) < 3 or not parts[2]:
                    break
                total.extend([k for k in parts[2].split(",") if k])
            return total
        
    def getReport(self, id):
        with self.lock:
            self.cthread.send("@q{}\n".format(id).encode())
            res = self.cthread.getResponse("q")
            if "!" in res[1]:
                e = res[1].split("!")
                if e[1] == "001":
                    raise ResponseError("Key Not Found {}".format(e[0]))
                else:
                    raise ResponseError("Response Error {} for {}".format(e[1], e[0]))
            # print("rpt:{0}".format(res[1]))
            a = res[1].split(";")
            return a

    def read(self, id):
        with self.lock:
            self.cthread.send("@r{}\n".format(id).encode())
            res = self.cthread.getResponse("r")
            return decodeDataString(res[1])

    def write(self, id, value, flags=""):
        with self.lock:
            a = "1" if "a" in flags else "0"
            b = "1" if "b" in flags else "0"
            f = "1" if "f" in flags else "0"
            s = "1" if "s" in flags else "0"
            sendStr = "{0};{1};{2}{3}{4}{5}\n".format(id, value, a, b, f, s)
            self.cthread.send(sendStr.encode())

    def subscribe(self, id):
        with self.lock:
            self.cthread.send("@s{}\n".format(id).encode())
            res = self.cthread.getResponse("s")

    def unsubscribe(self, id):
        with self.lock:
            self.cthread.send("@u{}\n".format(id).encode())
            res = self.cthread.getResponse("u")

    def flag(self, id, flag, setting):
        with self.lock:
            if setting:
                s = "1"
            else:
                s = "0"
            self.cthread.send("@f{};{};{}\n".format(id, flag.lower(), s).encode())
            res = self.cthread.getResponse("f")
            if "!" in res[1]:
                e = res[1].split("!")
                if e[1] == "001":
                    raise ResponseError("Key Not Found {}".format(e[0]))
                elif e[1] == "002":
                    raise ResponseError("Unknown Flag {}".format(flag))
                else:
                    raise ResponseError("Response Error {} for {}".format(e[1], e[0]))

    def writeValue(self, id, value):
        with self.lock:
            self.cthread.send("@w{};{}\n".format(id, value).encode())
            res = self.cthread.getResponse("w")
            return res[1]

    def getStatus(self):
        with self.lock:
            self.cthread.send("@xstatus\n".encode())
            res = self.cthread.getResponse("x")
        return res[1][7:]

    def stop(self):
        with self.lock:
            self.cthread.send("@xkill\n".encode())
            res = self.cthread.getResponse("x")
