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
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

#  This module contains all of the functions that interact with the server
#  for the GUI client.

import fixgw.netfix.QtDb
import fixgw.netfix as netfix

client = None
db = None
status_client = None


class RoutedClient:
    """
    Proxy that routes status/report RPCs to a separate connection while
    keeping subscriptions and pushed data on the main connection.
    """

    def __init__(self, main_client: netfix.Client, status_client: netfix.Client):
        self._main = main_client
        self._status = status_client
        # Preserve the main thread object so db.py can attach reportCallback
        self.cthread = main_client.cthread

    # Connection state and callbacks are managed on the main client
    def connect(self):
        return self._main.connect()

    def disconnect(self):
        return self._main.disconnect()

    def isConnected(self):
        return self._main.isConnected()

    def setConnectCallback(self, func):
        return self._main.setConnectCallback(func)

    def clearConnectCallback(self):
        return self._main.clearConnectCallback()

    def setDataCallback(self, func):
        return self._main.setDataCallback(func)

    def clearDataCallback(self):
        return self._main.clearDataCallback()

    # Data plane operations stay on the main client
    def getList(self):
        return self._main.getList()

    def read(self, *args, **kwargs):
        return self._main.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        return self._main.write(*args, **kwargs)

    def writeValue(self, *args, **kwargs):
        return self._main.writeValue(*args, **kwargs)

    def flag(self, *args, **kwargs):
        return self._main.flag(*args, **kwargs)

    def subscribe(self, *args, **kwargs):
        return self._main.subscribe(*args, **kwargs)

    def unsubscribe(self, *args, **kwargs):
        return self._main.unsubscribe(*args, **kwargs)

    def subscribeReport(self, *args, **kwargs):
        return self._main.subscribeReport(*args, **kwargs)

    def unsubscribeReport(self, *args, **kwargs):
        return self._main.unsubscribeReport(*args, **kwargs)

    # Status/Report RPCs are routed to the dedicated status client
    def getStatus(self):
        return self._status.getStatus()

    def getReport(self, *args, **kwargs):
        return self._status.getReport(*args, **kwargs)

    # Fallback for any unexpected attribute/method
    def __getattr__(self, name):
        return getattr(self._main, name)


def initialize(c):
    global client
    global db
    global status_client
    client = c
    # Dedicated status_client: no subscriptions or pushes; used only for @xstatus/@q
    try:
        host = getattr(client, "cthread").host
        port = getattr(client, "cthread").port
        status_client = netfix.Client(host, port)
        status_client.connect()
    except Exception:
        # If we fail to create a separate status client, fall back to main client
        status_client = client
    # Use a routed client so db operations use main for subs and status_client for reports
    routed = RoutedClient(client, status_client)
    db = fixgw.netfix.QtDb.Database(routed)

def shutdown():
    """Cleanly stop background DB activity and clients."""
    global client, db, status_client
    try:
        # Stop db polling thread if present (netfix.db.Database.UpdateThread)
        ndb = getattr(fixgw.netfix.QtDb, 'fixgw', None)
    except Exception:
        ndb = None
    try:
        # Access underlying netfix.db via QtDb.Database internals
        # This code assumes QtDb.Database holds netfix.db.Database in _Database__db
        if db is not None:
            try:
                underlying = getattr(db, '_Database__db', None)
                if underlying is not None and hasattr(underlying, 'timer'):
                    underlying.timer.stop()
            except Exception:
                pass
    except Exception:
        pass
    # Disconnect clients
    try:
        if status_client is not None and status_client is not client:
            status_client.disconnect()
    except Exception:
        pass
    try:
        if client is not None:
            client.disconnect()
    except Exception:
        pass
