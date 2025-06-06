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
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# This is the CAN-FIX plugin. CAN-FIX is a CANBus based protocol for
# aircraft data.

# This file controls mapping CAN-FIX parameter ids to FIX database keys

import fixgw.database as database
import canfix
import fixgw.quorum as quorum
from fixgw import cfg
import os


class Mapping(object):
    def __init__(self, mapfile, log=None):
        self.meta_replacements_in = {}
        self.meta_replacements_out = {}

        # This is a list of function closures
        self.input_mapping = [None] * 1280
        self.input_nodespecific = [None] * 1536
        self.output_mapping = {}
        self.log = log
        self.sendcount = 0
        self.senderrorcount = 0
        self.recvignorecount = 0
        self.recvinvalidcount = 0
        self.ignore_fixid_missing = False

        # Open and parse the YAML mapping file passed to us
        if not os.path.exists(mapfile):
            raise ValueError(f"Unable to open mapfile: '{mapfile}'")
        maps, meta = cfg.from_yaml(mapfile, metadata=True)

        if "ignore_fixid_missing" in maps:
            if isinstance(maps["ignore_fixid_missing"], bool):
                self.ignore_fixid_missing = maps["ignore_fixid_missing"]
            else:
                raise ValueError(
                    cfg.message(
                        "ignore_fixid_missing must be true or false",
                        meta,
                        "ignore_fixid_missing",
                        True,
                    )
                )

        if not maps.get("meta replacements", False):
            raise ValueError(
                f"The mapfile '{mapfile}' must provide a valid 'meta replacements' section"
            )
        # dictionaries used for converting meta data strings from db to canfix and back
        self.meta_replacements_in = maps["meta replacements"]
        self.meta_replacements_out = {
            v: k for k, v in self.meta_replacements_in.items()
        }

        # We really just assign all the outputs to a dictionary for the main
        # plugin code to use to assign callbacks.
        for each in maps["outputs"]:
            fixids = []
            switch = False
            if each["canid"] > 0x307 and each["canid"] < 0x310:
                switch = True
                for fid in each["fixid"].split(","):
                    fixids.append(fid.strip())
            else:
                fixids.append(each["fixid"])
            for ea in fixids:
                output = {
                    "canid": each["canid"],
                    "index": each["index"],
                    "owner": each.get("owner", False),
                    "require_leader": each.get("require_leader", True),
                    "on_change": each.get("on_change", True),
                    "exclude": False,
                    "lastValue": None,
                    "lastFlags": None,
                    "lastOld": None,
                    "switch": switch,
                    "fixids": fixids,
                }
                self.output_mapping[ea] = output

        # each input mapping item := [CANID, Index, FIX DB ID, Priority]
        for index, each in enumerate(maps["inputs"]):
            self.validate_mapping_inputs(each, meta["inputs"], index)
            # Parameters start at 0x100 so we subtract that offset to index the array
            ix = each["canid"] - 0x100
            if self.input_mapping[ix] is None:
                self.input_mapping[ix] = [None] * 256
            self.input_mapping[ix][each["index"]] = self.getInputFunction(each["fixid"])
            self.input_nodespecific[each["canid"]] = each.get("nodespecific", False)
        # each input mapping item := [CANID, Index, FIX DB ID, Priority]
        for each in maps["encoders"]:
            # p = canfix.protocol.parameters[each["canid"]]
            # Parameters start at 0x100 so we subtract that offset to index the array
            ix = each["canid"] - 0x100
            if self.input_mapping[ix] is None:
                self.input_mapping[ix] = [None] * 256
            self.input_mapping[ix][each["index"]] = self.getEncoderFunction(
                each["fixid"], each.get("sum", False)
            )
            self.input_nodespecific[each["canid"]] = each.get("nodespecific", False)
        for each in maps["switches"]:
            ix = each["canid"] - 0x100
            if self.input_mapping[ix] is None:
                self.input_mapping[ix] = [None] * 256
            self.input_mapping[ix][each["index"]] = self.getSwitchFunction(
                each["fixid"], each.get("toggle", None)
            )
            self.input_nodespecific[each["canid"]] = each.get("nodespecific", False)

    # The idea here is that we create arrays and dictionaries for each type of
    # mapping.  These contain closure functions that know how to put the data in
    # the right place.  The functions are determined ahead of time for
    # performance reasons which is why we are using closures.

    # This is a closure that holds the information we need to transfer data
    # from the CAN-FIX port to the FIXGW Database
    def getInputFunction(self, dbKey):
        try:
            dbItem = database.get_raw_item(dbKey)
        except KeyError:
            # Need to improve this, maybe the user made a typo, they might not ever know.
            # Currently the code has been updated to allow this because we want to
            # keep the default config as simple as possible
            # If you change database variable to one engine, then all the fixids for
            # engine two are not created
            # We have all the fixids defined for both engines and currently
            # lack a simple mechanism to turn them on or off
            return None

        # The output exclusion keeps us from constantly sending updates on the
        # CAN Bus when the change that we recieved was from the CAN Bus.
        # Basically when the input function is called we'll first exclude
        # the output then make the change.  The output callback will be
        # called but will do nothing but reset the exclusion flag.
        if dbKey in self.output_mapping:
            output_exclude = True
        else:
            output_exclude = False

        def InputFunc(cfpar):
            if output_exclude:
                self.output_mapping[dbItem.key]["exclude"] = True
                self.output_mapping[dbItem.key]["lastValue"] = cfpar.value
            if cfpar.meta:
                try:
                    # Check to see if we have a replacement string in the dictionary
                    if cfpar.meta in self.meta_replacements_in:
                        m = self.meta_replacements_in[cfpar.meta]
                    else:  # Just use the one we were sent
                        m = cfpar.meta
                    dbItem.set_aux_value(m, cfpar.value)
                except:
                    self.recvinvalidcount += 1
                    self.log.warning(
                        "Problem setting Aux Value for {0}".format(dbItem.key)
                    )
            else:
                if (
                    cfpar.value is not None
                    and cfpar.annunciate is not None
                    and cfpar.quality is not None
                    and cfpar.failure is not None
                ):
                    dbItem.value = (
                        cfpar.value,
                        cfpar.annunciate,
                        cfpar.quality,
                        cfpar.failure,
                    )
                else:
                    self.recvinvalidcount += 1

        return InputFunc

    # Returns a closure that should be used as the callback for database item
    # changes that should be written to the CAN Bus
    def getOutputFunction(self, bus, dbKey, node):
        def outputCallback(key, value, udata):
            m = self.output_mapping[dbKey]
            self.log.debug(f"Output {dbKey}: {value[0]}")
            if m["require_leader"] and not quorum.leader:
                self.log.debug(
                    f"LEADER({quorum.leader}) blocked Output {dbKey}: {value[0]}"
                )
                return

            # If the exclude flag is set we just recieved the value
            # from the bus so we don't turn around and write it back out
            if m["exclude"]:
                self.log.debug(f"Resend protection blocked Output {dbKey}: {value[0]}")
                m["exclude"] = False
                return
            if m["switch"]:
                # This is a switch output
                # merge value of all switches
                val = bytearray([0x0] * 5)
                # Loop always runs
                for b, valByte in enumerate(val):  # pragma: no cover # fmt: skip
                    # Each byte of val
                    for bt in range(8):
                        # Each bit in the byte
                        if b + bt + 1 > len(m["fixids"]):
                            break
                        else:
                            if database.get_raw_item(m["fixids"][b + bt]).value[0]:
                                val[b] = val[b] | (1 << bt)
                                # Do not need to set 0 since that is default
                    if b + bt + 1 > len(m["fixids"]):
                        break
                # Not setting the flags for the buttons because it is not
                # possible to set them for each individual button
                value = (val, 0, 0, 0, 0, 0)
            if m["owner"]:
                # If we are the owner we send a regular parameter update
                # We do not send unless the flags or value have changed
                # unless on_change==False
                r = False
                if (
                    "lastOld" in m
                    and m["lastOld"] != value[2]
                    and m["lastFlags"] == (value[1], value[3], value[4])
                    and value[0] == m["lastValue"]
                ):
                    # The only thing that changed was old, we do not care about that
                    r = True

                if (
                    "lastValue" in m
                    and m["on_change"]
                    and value[0] == m["lastValue"]
                    and m["lastFlags"] == (value[1], value[3], value[4])
                ):
                    # Nothing we care about changed and we only send changes
                    r = True

                # When comparing the flags, we only care about the flags
                # that we can use in canfix

                m["lastValue"] = value[0]
                m["lastFlags"] = (value[1], value[3], value[4])
                m["lastOld"] = value[2]

                if r:
                    return
                p = canfix.Parameter()
                p.identifier = m["canid"]
                p.value = value[0]
                p.index = index = m["index"]  # noqa: F841
                p.annunciate = value[1]
                # 2 is old
                p.quality = value[3]
                p.failure = value[4]
                # 5 is secondary fail
                p.node = node
                try:
                    bus.send(p.msg)
                except Exception as e:
                    self.senderrorcount += 1
                    self.log.error("CAN send failure:" + str(e))
                    # This does not seem to always flush the buffer
                    # a full tx queue seems to be the most common error
                    # when the bus is disrupted
                    bus.flush_tx_buffer()
                self.sendcount += 1
                self.log.debug(f"Output {dbKey}: Sent")
            else:
                # If we are not the owner we don't worry about the flags or
                # sending values that have not changed unless
                # on_change==False
                self.log.debug(f"Output {dbKey}: sending NodeSpecific")
                if "lastValue" in m and value[0] == m["lastValue"] and m["on_change"]:
                    self.log.debug(f"Output {dbKey}: not sending, not change")
                    return

                m["lastValue"] = value[0]
                m["lastFlags"] = (value[1], value[3], value[4])
                m["lastOld"] = value[2]
                # Workaround for bug in python-canfix
                # https://github.com/birkelbach/python-canfix/pull/14
                p = canfix.ParameterSet()
                p.parameter = m["canid"]
                if p.multiplier is None:
                    p.multiplier = 1.0
                p.value = value[0]
                # End workaround
                # p = canfix.ParameterSet(parameter=m["canid"], value=value[0])
                p.sendNode = node
                try:
                    bus.send(p.msg)
                    self.log.debug(f"Output {dbKey}: sent value: '{value[0]}'")
                except Exception as e:
                    self.senderrorcount += 1
                    self.log.debug(f"Output {dbKey}: Send Failed {p.msg}")
                    self.log.error("CAN send failure:" + str(e))
                    # This does not seem to always flush the buffer
                    # a full tx queue seems to be the most common error
                    # when the bus is disrupted
                    bus.flush_tx_buffer()
                else:
                    self.sendcount += 1
                    self.log.debug(f"Output {dbKey}: Sent {p.msg}")

        return outputCallback

    # Returns a closure that should be used as the callback for database item
    # changes to the quorum voting fixid that should be written to the CAN Bus
    def getQuorumOutputFunction(self, bus, dbKey, node):
        def outputCallback(key, value, udata):
            p = canfix.NodeStatus()
            p.sendNode = node
            p.parameter = 0x09
            p.value = value[0]
            try:
                bus.send(p.msg)
            except Exception as e:
                self.senderrorcount += 1
                self.log.debug(f"Output {dbKey}: Send Failed {p.msg}")
                self.log.error("CAN send failure:" + str(e))
                # This does not seem to always flush the buffer
                # a full tx queue seems to be the most common error
                # when the bus is disrupted
                bus.flush_tx_buffer()
            else:
                self.sendcount += 1

        return outputCallback

    # This is a closure that holds the information we need to transfer data
    # from the CAN-FIX port to the FIXGW Database
    def getEncoderFunction(self, dbKeys, add):
        # the dbKeys parameter should be three fix ids separated by commas
        # the first two are the encoder ids for each of the encoders that
        # are contained in the fix message and the third is the button.
        buttons = list()
        encoders = list()
        try:
            ids = dbKeys.split(",")
            skip = 1
            # allow 1 or more encoders
            encoders.append(database.get_raw_item(ids[0].strip()))
            if len(ids) > 1:
                encoders.append(database.get_raw_item(ids[1].strip()))
                skip += 1
            # Allow 0 to 8 buttons too
            if len(ids) > 2 and len(ids) < 11:
                for bc, btn in enumerate(ids[2:]):
                    buttons.append(database.get_raw_item(ids[bc + skip].strip()))

        except KeyError:
            return None

        def InputFunc(cfpar):
            for ec, e in enumerate(encoders):
                if add:
                    encoders[ec].value = encoders[ec].value[0] + cfpar.value[ec]
                else:
                    encoders[ec].value = cfpar.value[ec]
            for bc, b in enumerate(buttons):
                b.value = cfpar.value[2][bc]

        return InputFunc

    def getSwitchFunction(self, dbKeys, toggle):
        try:
            switches = []
            ids = dbKeys.split(",")
            for each in ids:
                switches.append(database.get_raw_item(each.strip()))
            toggles = dict()
            if toggle:
                ids = toggle.split(",")
                for each in ids:
                    toggles[each.strip()] = True

        except KeyError:
            return None

        def InputFunc(cfpar):
            x = cfpar.value
            bit = 0
            byte = 0
            for each in switches:
                if each.key in self.output_mapping:
                    output_exclude = True
                    self.output_mapping[each.key]["exclude"] = True
                else:
                    output_exclude = False

                if toggles.get(each.key, False):
                    if x[byte][bit]:
                        if output_exclude:
                            self.output_mapping[each.key]["lastValue"] = not each.value[
                                0
                            ]
                        # toggle only when we receive True
                        each.value = not each.value[0]
                else:
                    if output_exclude:
                        self.output_mapping[each.key]["lastValue"] = x[byte][bit]

                    each.value = x[byte][bit]
                bit += 1
                if bit >= 8:
                    bit = 0
                    byte += 1

        return InputFunc

    def inputMap(self, par):
        """Retrieve the function that should be called for a given parameter"""
        ix = par.identifier - 0x100
        im = self.input_mapping[ix]  # This should always exist
        if im is None:
            return None
        if par.meta:
            for func in im:
                if func is not None:
                    func(par)
                # else:
                # log.error("Yo you gotta be kidding")
        else:
            func = im[par.index]
            if func is not None:
                func(par)

    def valid_canid(self, canid, detailed=False):
        if canid < 256:
            return (False, "canid must be >= to 256 (0x100)") if detailed else False
        if canid > 2015:
            return (False, "canid must be <= to 2015 (0x7df)") if detailed else False
        if canid in range(1536, 1759):
            return (
                (False, "canid must not be between 1536 (0x600) and 1759 (0x6DF)")
                if detailed
                else False
            )
        return (True, None) if detailed else True

    def valid_index(self, index, detailed=False):
        if index >= 0 and index < 256:
            return (True, None) if detailed else True
        else:
            return (
                (False, "Index should be less than 256 and greater than or equall to 0")
                if detailed
                else False
            )

    def valid_fixid(self, fixid):
        return fixid in database.listkeys()

    def validate_mapping_inputs(self, data, meta, index):
        if not isinstance(data, dict):
            raise ValueError(cfg.message("Inputs should be dictionaries", meta, index))
        for k in ["canid", "index", "fixid"]:
            if k not in data:
                raise ValueError(cfg.message(f"Key '{k}' is missing", meta, index))
        if not self.valid_canid(data["canid"]):
            raise ValueError(
                cfg.message(
                    self.valid_canid(data["canid"], True)[1], meta[index], "canid", True
                )
            )
        if data["fixid"] not in database.listkeys() and not self.ignore_fixid_missing:
            raise ValueError(
                cfg.message(
                    f"fixid '{data['fixid']}' is not a valid fixid",
                    meta[index],
                    "fixid",
                    True,
                )
            )
        if not self.valid_index(data["index"]):
            raise ValueError(
                cfg.message(
                    self.valid_index(data["index"], True)[1], meta[index], "index", True
                )
            )
        if not isinstance(data.get("nodespecific", False), bool):
            raise ValueError(
                cfg.message(
                    "nodespecific should be true or false without quotes",
                    meta[index],
                    "nodespecific",
                    True,
                )
            )
