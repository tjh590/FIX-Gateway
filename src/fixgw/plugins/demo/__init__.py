#!/usr/bin/env python

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

#  This is a simple data simulation plugin.  It's mainly for demo purposese
#  It really has no function other than simple testing of displays

# TODO Make the keylist configurable
# TODO add some functions to change the values (noise, cyclic, reduction, etc)

import threading
import time
import math
import os
from collections import OrderedDict
import fixgw.plugin as plugin


class MainThread(threading.Thread):
    def __init__(self, parent):
        super(MainThread, self).__init__()
        self.getout = False  # indicator for when to stop
        self.parent = parent  # parent plugin object
        self.log = parent.log  # simplifies logging
        self.keylist = {
            "ROLL": 0.0,
            "PITCH": 0.0,
            "IAS": 113.0,
            "ALT": 1153.0,
            "VS": 0,
            "TACH1": 2450.0,
            "MAP1": 24.2,
            "FUELP1": 28.5,
            "OILP1": 56.4,
            "OILT1": 95.0,
            "FUELQ1": 11.2,
            "FUELQ2": 19.8,
            "FUELQ3": 10.8,
            "OAT": 32.0,
            "CHT11": 201.0,
            "CHT12": 202.0,
            "CHT13": 199.0,
            "CHT14": 200.0,
            "CHT15": 197.0,
            "CHT16": 196.0,
            "EGT11": 510.0,
            "EGT12": 540.0,
            "EGT13": 544.0,
            "EGT14": 522.0,
            "EGT15": 500.0,
            "EGT16": 550.0,
            "FUELF1": 8.7,
            "VOLT": 13.7,
            "CURRNT": 45.6,
            "TAS": 113,
            "ALAT": 0.0,
            "HEAD": 280.0,
            "LONG": -82.8550,
            "LAT": 40.000200,
            "CDI": 0.0,
            "GSI": 0.0,
            "COURSE": 274.3,
            "COMTXPWR1": 0,
            "COMVSWR1": 0,
            "COMACTTX1": False,
            "COMSTDRXLEVEL1": 0,
            "COMACTRXLEVEL1": 0,
            "COMSQUELCH1": 4.5,
            "COMACTRX1": False,
            "COMSTDRX1": False,
            "COMAUDVOL1": 10,
            "COMRXVOL1": 9,
            "COMINTVOL1": 10,
            "COMACTFREQ1": 121.500,
            "COMSTDFREQ1": 121.500,
        }
        self.script = [
            {"MAVMSG": "Roll/Pitch 0", "ROLL": 0, "PITCH": 0},
            {"MAVMSG": "Roll/Pitch 10", "ROLL": 10, "PITCH": 10},
            {"MAVMSG": "Roll/Pitch 20", "ROLL": 20, "PITCH": 20},
            {"MAVMSG": "Roll/Pitch 10", "ROLL": 10, "PITCH": 10},
            {"MAVMSG": "Roll/Pitch 0", "ROLL": 0, "PITCH": 0},
            {"MAVMSG": "Roll/Pitch 10", "ROLL": -10, "PITCH": -10},
            {"MAVMSG": "Roll/Pitch 20", "ROLL": -20, "PITCH": -20},
            {"MAVMSG": "Roll/Pitch 10", "ROLL": -10, "PITCH": -10},
            {"MAVMSG": "Roll/Pitch 0", "ROLL": 0, "PITCH": 0},
            {"MAVMSG": "PAPI 2 Red", "ALT": 1153},
            {"MAVMSG": "PAPI 1 Red", "ALT": 1200},
            {"MAVMSG": "PAPI 0 Red", "ALT": 1250},
            {"MAVMSG": "PAPI 1 Red", "ALT": 1200},
            {"MAVMSG": "PAPI 2 Red", "ALT": 1153},
            {"MAVMSG": "PAPI 3 Red", "ALT": 1100},
            {"MAVMSG": "PAPI 4 Red", "ALT": 1050},
            {"MAVMSG": "PAPI 3 Red", "ALT": 1100},
            {"MAVMSG": "PAPI 2 Red", "ALT": 1153},
            {"MAVMSG": "HEAD 280", "HEAD": 280.0, "COURSE": 274.3},
            {"MAVMSG": "HEAD 254", "HEAD": 254, "COURSE": 248.3},
            {"MAVMSG": "HEAD 234", "HEAD": 234, "COURSE": 228.3},
            {"MAVMSG": "HEAD 214", "HEAD": 214, "COURSE": 208.3},
            {"MAVMSG": "HEAD 194", "HEAD": 194, "COURSE": 188.3},
            {"MAVMSG": "HEAD 174", "HEAD": 174, "COURSE": 168.3},
            {"MAVMSG": "HEAD 154", "HEAD": 154, "COURSE": 148.3},
            {"MAVMSG": "HEAD 134", "HEAD": 134, "COURSE": 128.3},
            {"MAVMSG": "HEAD 114", "HEAD": 114, "COURSE": 108.3},
            {"MAVMSG": "HEAD 94", "HEAD": 94, "COURSE": 88.3},
            {"MAVMSG": "HEAD 74", "HEAD": 74, "COURSE": 68.3},
            {"MAVMSG": "HEAD 54", "HEAD": 54, "COURSE": 48.3},
            {"MAVMSG": "HEAD 34", "HEAD": 34, "COURSE": 28.3},
            {"MAVMSG": "HEAD 14", "HEAD": 14, "COURSE": 8.3},
            {"MAVMSG": "HEAD 0", "HEAD": 0, "COURSE": 0},
            {"MAVMSG": "HEAD 0", "HEAD": 0, "COURSE": 0},
            {"MAVMSG": "HEAD 14", "HEAD": 14, "COURSE": 8.3},
            {"MAVMSG": "HEAD 34", "HEAD": 34, "COURSE": 28.3},
            {"MAVMSG": "HEAD 54", "HEAD": 54, "COURSE": 48.3},
            {"MAVMSG": "HEAD 74", "HEAD": 74, "COURSE": 68.3},
            {"MAVMSG": "HEAD 94", "HEAD": 94, "COURSE": 88.3},
            {"MAVMSG": "HEAD 114", "HEAD": 114, "COURSE": 108.3},
            {"MAVMSG": "HEAD 134", "HEAD": 134, "COURSE": 128.3},
            {"MAVMSG": "HEAD 154", "HEAD": 154, "COURSE": 148.3},
            {"MAVMSG": "HEAD 174", "HEAD": 174, "COURSE": 168.3},
            {"MAVMSG": "HEAD 194", "HEAD": 194, "COURSE": 188.3},
            {"MAVMSG": "HEAD 214", "HEAD": 214, "COURSE": 208.3},
            {"MAVMSG": "HEAD 234", "HEAD": 234, "COURSE": 228.3},
            {"MAVMSG": "HEAD 254", "HEAD": 254, "COURSE": 248.3},
            {"MAVMSG": "HEAD 280", "HEAD": 280.0, "COURSE": 274.3},
            {
                "MAVMSG": "Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8550,
                "LAT": 40.000200,
                "ALT": 1153,
                "VS": -300,
            },
            {
                "MAVMSG": "Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8650,
                "LAT": 40.000750,
                "ALT": 1020,
                "VS": -300,
            },
            {
                "MAVMSG": "Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8750,
                "LAT": 40.001350,
                "ALT": 880,
                "VS": -300,
            },
            {
                "MAVMSG": "Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8780,
                "LAT": 40.001530,
                "ALT": 860,
                "VS": -300,
            },
            {
                "MAVMSG": "Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8789,
                "LAT": 40.00160,
                "ALT": 830,
                "VS": -300,
            },
            {
                "MAVMSG": "Reverse Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8780,
                "LAT": 40.001530,
                "ALT": 860,
                "VS": 300,
            },
            {
                "MAVMSG": "Reverse Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8750,
                "LAT": 40.001350,
                "ALT": 880,
                "VS": 300,
            },
            {
                "MAVMSG": "Reverse Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8650,
                "LAT": 40.000750,
                "ALT": 1020,
                "VS": 300,
            },
            {
                "MAVMSG": "Reverse Landing",
                "HEAD": 280.0,
                "COURSE": 274.3,
                "LONG": -82.8550,
                "LAT": 40.000200,
                "ALT": 1153,
                "VS": 300,
            },
            {"MAVMSG": "Encoder left 1", "ENC3": "-1"},
            {"MAVMSG": "Encoder right 1", "ENC3": "1"},
            {"MAVMSG": "Encoder right 2", "ENC3": "1"},
            {"MAVMSG": "Encoder right 3", "ENC3": "1", "BTN3": "False"},
            {"MAVMSG": "Encoder Button press", "BTN3": "True"},
            {"MAVMSG": "Encoder left 1", "ENC3": "-1"},
            {"MAVMSG": "Encoder left 2", "ENC3": "-1", "BTN3": "False"},
            {"MAVMSG": "Encoder Button press 1", "BTN3": "True"},
            {"MAVMSG": "Encoder Button press 1", "BTN3": "False"},
            {"MAVMSG": "Encoder Button press 2", "BTN3": "True"},
            {"MAVMSG": "Encoder right 1", "ENC3": "1"},
            {"MAVMSG": "Encoder right 2", "ENC3": "1", "BTN3": "False"},
            {"MAVMSG": "Encoder Button press", "BTN3": "True"},
            {"MAVMSG": "Wait for encoder timeout 1"},
            {"MAVMSG": "Wait for encoder timeout 2"},
            {"MAVMSG": "Wait for encoder timeout 3"},
            {"MAVMSG": "Wait for encoder timeout 4"},
            {"MAVMSG": "Wait for encoder timeout 5"},
            {"MAVMSG": "Wait for encoder timeout 6"},
            {"MAVMSG": "Wait for encoder timeout 7"},
            {"MAVMSG": "Wait for encoder timeout 8"},
            {"MAVMSG": "Wait for encoder timeout 9"},
            {"MAVMSG": "Encoder right 1", "ENC3": "1"},
            {"MAVMSG": "Encoder right 2", "ENC3": "1", "BTN3": "False"},
            {"MAVMSG": "Encoder right 3", "ENC3": "1"},
            {"MAVMSG": "Encoder right 4", "ENC3": "1"},
            {"MAVMSG": "Encoder right 5", "ENC3": "1"},
            {"MAVMSG": "Encoder Button press 1", "BTN3": "True"},
            {"MAVMSG": "Encoder left 1", "ENC3": "-1"},
            {"MAVMSG": "Encoder left 2", "ENC3": "-1"},
            {"MAVMSG": "Encoder left 3", "ENC3": "-1"},
            {"MAVMSG": "Encoder left 4", "ENC3": "-1"},
            {"MAVMSG": "IAS/TAS 113", "IAS": 113, "TAS": 113, "VS": 0},
            {"MAVMSG": "IAS/TAS 123", "IAS": 123, "TAS": 123},
            {"MAVMSG": "IAS/TAS 133", "IAS": 133, "TAS": 133},
            {"MAVMSG": "IAS/TAS 143", "IAS": 143, "TAS": 143},
            {"MAVMSG": "IAS/TAS 133", "IAS": 133, "TAS": 133},
            {"MAVMSG": "IAS/TAS 123", "IAS": 123, "TAS": 123},
            {"MAVMSG": "IAS/TAS 113", "IAS": 113, "TAS": 113},
            {
                "MAVMSG": "COURSE 274.3, VS 100, ALAT -.05",
                "COURSE": 274.3,
                "VS": 100,
                "ALAT": -0.05,
            },
            {
                "MAVMSG": "COURSE 254, VS 500, ALAT -.1",
                "COURSE": 254,
                "VS": 500,
                "ALAT": -0.1,
            },
            {
                "MAVMSG": "COURSE 234, VS 900, ALAT -.2",
                "COURSE": 234,
                "VS": 900,
                "ALAT": -0.2,
            },
            {
                "MAVMSG": "COURSE 214, VS 1200,ALAT -.3",
                "COURSE": 214,
                "VS": 1200,
                "ALAT": -0.3,
            },
            {
                "MAVMSG": "COURSE 194, VS 1500,ALAT 0",
                "COURSE": 194,
                "VS": 1500,
                "ALAT": 0,
            },
            {
                "MAVMSG": "COURSE 214, VS 1200,ALAT .1",
                "COURSE": 214,
                "VS": 1200,
                "ALAT": 0.1,
            },
            {
                "MAVMSG": "COURSE 234, VS 900,ALAT .2",
                "COURSE": 234,
                "VS": 900,
                "ALAT": 0.2,
            },
            {
                "MAVMSG": "COURSE 254, VS 500,ALAT .3",
                "COURSE": 254,
                "VS": 500,
                "ALAT": 0.3,
            },
            {
                "MAVMSG": "COURSE 274.3, VS 0, ALAT 0",
                "COURSE": 274.3,
                "VS": 00,
                "ALAT": 0,
            },
            {
                "MAVMSG": "CHT 100, EGT 500, FUELQ 21,21,42",
                "CHT11": 100,
                "CHT11": 100,
                "CHT12": 100,
                "CHT13": 100,
                "CHT14": 100,
                "CHT15": 100,
                "CHT16": 100,
                "EGT11": 500,
                "EGT12": 500,
                "EGT13": 500,
                "EGT14": 500,
                "EGT15": 500,
                "EGT16": 500,
                "FUELQ1": 21,
                "FUELQ2": 21,
                "FUELQ3": 42,
            },
            {
                "MAVMSG": "CHT 150, EGT 550, FUELQ 18,17,38",
                "CHT11": 150,
                "CHT11": 150,
                "CHT12": 150,
                "CHT13": 150,
                "CHT14": 150,
                "CHT15": 150,
                "CHT16": 150,
                "EGT11": 550,
                "EGT12": 550,
                "EGT13": 550,
                "EGT14": 550,
                "EGT15": 550,
                "EGT16": 550,
                "FUELQ1": 18,
                "FUELQ2": 17,
                "FUELQ3": 38,
            },
            {
                "MAVMSG": "CHT 200, EGT 600, FUELQ 15,15,30",
                "CHT11": 200,
                "CHT11": 200,
                "CHT12": 200,
                "CHT13": 200,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 600,
                "EGT12": 600,
                "EGT13": 600,
                "EGT14": 600,
                "EGT15": 600,
                "EGT16": 600,
                "FUELQ1": 15,
                "FUELQ2": 15,
                "FUELQ3": 30,
            },
            {
                "MAVMSG": "CHT 250, EGT 650, FUELQ 10,11,20",
                "CHT11": 250,
                "CHT11": 250,
                "CHT12": 250,
                "CHT13": 250,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 650,
                "EGT12": 650,
                "EGT13": 650,
                "EGT14": 650,
                "EGT15": 650,
                "EGT16": 650,
                "FUELQ1": 10,
                "FUELQ2": 11,
                "FUELQ3": 20,
            },
            {
                "MAVMSG": "CHT 300, EGT 680, FUELQ 5,6,10",
                "CHT11": 300,
                "CHT11": 300,
                "CHT12": 300,
                "CHT13": 300,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 680,
                "EGT12": 680,
                "EGT13": 680,
                "EGT14": 680,
                "EGT15": 680,
                "EGT16": 680,
                "FUELQ1": 5,
                "FUELQ2": 6,
                "FUELQ3": 10,
            },
            {
                "MAVMSG": "CHT 320, EGT 750, FUELQ 0,0,0,0",
                "CHT11": 320,
                "CHT11": 320,
                "CHT12": 320,
                "CHT13": 320,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 750,
                "EGT12": 750,
                "EGT13": 750,
                "EGT14": 750,
                "EGT15": 750,
                "EGT16": 750,
                "FUELQ1": 0,
                "FUELQ2": 0,
                "FUELQ3": 0,
            },
            {
                "MAVMSG": "CHT 320, EGT 750, FUELQ 0,0,0,0",
                "CHT11": 320,
                "CHT11": 320,
                "CHT12": 320,
                "CHT13": 320,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 750,
                "EGT12": 750,
                "EGT13": 750,
                "EGT14": 750,
                "EGT15": 750,
                "EGT16": 750,
                "FUELQ1": 0,
                "FUELQ2": 0,
                "FUELQ3": 0,
            },
            {
                "MAVMSG": "CHT 300, EGT 680, FUELQ 5,6,10",
                "CHT11": 300,
                "CHT11": 300,
                "CHT12": 300,
                "CHT13": 300,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 680,
                "EGT12": 680,
                "EGT13": 680,
                "EGT14": 680,
                "EGT15": 680,
                "EGT16": 680,
                "FUELQ1": 5,
                "FUELQ2": 6,
                "FUELQ3": 10,
            },
            {
                "MAVMSG": "CHT 250, EGT 650, FUELQ 10,11,20",
                "CHT11": 250,
                "CHT11": 250,
                "CHT12": 250,
                "CHT13": 250,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 650,
                "EGT12": 650,
                "EGT13": 650,
                "EGT14": 650,
                "EGT15": 650,
                "EGT16": 650,
                "FUELQ1": 10,
                "FUELQ2": 11,
                "FUELQ3": 20,
            },
            {
                "MAVMSG": "CHT 200, EGT 600, FUELQ 15,15,30",
                "CHT11": 200,
                "CHT11": 200,
                "CHT12": 200,
                "CHT13": 200,
                "CHT14": 200,
                "CHT15": 200,
                "CHT16": 200,
                "EGT11": 600,
                "EGT12": 600,
                "EGT13": 600,
                "EGT14": 600,
                "EGT15": 600,
                "EGT16": 600,
                "FUELQ1": 15,
                "FUELQ2": 15,
                "FUELQ3": 30,
            },
            {
                "MAVMSG": "CHT 150, EGT 550, FUELQ 18,17,38",
                "CHT11": 150,
                "CHT11": 150,
                "CHT12": 150,
                "CHT13": 150,
                "CHT14": 150,
                "CHT15": 150,
                "CHT16": 150,
                "EGT11": 550,
                "EGT12": 550,
                "EGT13": 550,
                "EGT14": 550,
                "EGT15": 550,
                "EGT16": 550,
                "FUELQ1": 18,
                "FUELQ2": 17,
                "FUELQ3": 38,
            },
            {
                "MAVMSG": "CHT 100, EGT 500, FUELQ 21,21,42",
                "CHT11": 95,
                "CHT12": 90,
                "CHT13": 120,
                "CHT14": 101,
                "CHT15": 105,
                "CHT16": 80,
                "EGT11": 490,
                "EGT12": 510,
                "EGT13": 501,
                "EGT14": 500,
                "EGT15": 515,
                "EGT16": 520,
                "FUELQ1": 5,
                "FUELQ2": 11,
                "FUELQ3": 42,
            },
            {
                "MAVMSG": "TACH 3200, OILP: 0,  OILT 0,  MAP, 0",
                "TACH1": 3200,
                "OILP1": 0,
                "OILT1": 0,
                "MAP1": 0,
            },
            {
                "MAVMSG": "TACH 2800, OILP: 20, OILT 24, MAP, 5",
                "TACH1": 2800,
                "OILP1": 20,
                "OILT1": 24,
                "MAP1": 5,
            },
            {
                "MAVMSG": "TACH 2000, OILP: 40, OILT 44, MAP, 15",
                "TACH1": 2000,
                "OILP1": 40,
                "OILT1": 44,
                "MAP1": 15,
            },
            {
                "MAVMSG": "TACH 1500, OILP: 60, OILT 64, MAP, 20",
                "TACH1": 1500,
                "OILP1": 60,
                "OILT1": 64,
                "MAP1": 20,
            },
            {
                "MAVMSG": "TACH 1000, OILP: 80, OILT 84, MAP, 25",
                "TACH1": 1000,
                "OILP1": 80,
                "OILT1": 84,
                "MAP1": 25,
            },
            {
                "MAVMSG": "TACH 500,  OILP: 90, OILT 100,MAP, 28",
                "TACH1": 500,
                "OILP1": 90,
                "OILT1": 100,
                "MAP1": 28,
            },
            {
                "MAVMSG": "TACH 0, OILP: 100, OILT 122, MAP,  30",
                "TACH1": 3200,
                "OILP1": 100,
                "OILT1": 122,
                "MAP1": 30,
            },
            {
                "MAVMSG": "TACH 0, OILP: 100, OILT 122, MAP,  30",
                "TACH1": 3200,
                "OILP1": 100,
                "OILT1": 122,
                "MAP1": 30,
            },
            {
                "MAVMSG": "TACH 500,  OILP: 90, OILT 100,MAP, 28",
                "TACH1": 500,
                "OILP1": 90,
                "OILT1": 100,
                "MAP1": 28,
            },
            {
                "MAVMSG": "TACH 1000, OILP: 80, OILT 84, MAP, 25",
                "TACH1": 1000,
                "OILP1": 80,
                "OILT1": 84,
                "MAP1": 25,
            },
            {
                "MAVMSG": "TACH 1500, OILP: 60, OILT 64, MAP, 20",
                "TACH1": 1500,
                "OILP1": 60,
                "OILT1": 64,
                "MAP1": 20,
            },
            {
                "MAVMSG": "TACH 2000, OILP: 40, OILT 44, MAP, 15",
                "TACH1": 2000,
                "OILP1": 40,
                "OILT1": 44,
                "MAP1": 15,
            },
            {
                "MAVMSG": "TACH 2800, OILP: 20, OILT 24, MAP, 5",
                "TACH1": 2800,
                "OILP1": 20,
                "OILT1": 24,
                "MAP1": 5,
            },
            {
                "MAVMSG": "TACH 3200, OILP: 0,  OILT 0,  MAP, 0",
                "TACH1": 3200,
                "OILP1": 0,
                "OILT1": 0,
                "MAP1": 0,
            },
            {
                "MAVMSG": "TACH 2450, OILP: 60,  OILT 80,  MAP, 10",
                "TACH1": 2450,
                "OILP1": 60,
                "OILT1": 80,
                "MAP1": 10,
            },
            {"MAVMSG": "RADIO vol", "COMRXVOL1": 0, "COMINTVOL1": 0, "COMAUDVOL1": 0},
            {"MAVMSG": "RADIO vol", "COMRXVOL1": 10, "COMINTVOL1": 9, "COMAUDVOL1": 10},
            {"MAVMSG": "RADIO tx", "COMTXPWR1": 10, "COMVSWR1": 1.5, "COMACTTX1": True},
            {"MAVMSG": "RADIO tx", "COMTXPWR1": 10, "COMVSWR1": 1.5, "COMACTTX1": True},
            {"MAVMSG": "RADIO idle", "COMTXPWR1": 0, "COMVSWR1": 0, "COMACTTX1": False},
            {
                "MAVMSG": "RADIO rx",
                "COMACTRXLEVEL1": 10,
                "COMSQUELCH1": 4.5,
                "COMACTRX1": True,
            },
            {
                "MAVMSG": "RADIO rx",
                "COMACTRXLEVEL1": 10,
                "COMSQUELCH1": 4.5,
                "COMACTRX1": True,
            },
            {
                "MAVMSG": "RADIO rx",
                "COMACTRXLEVEL1": 0,
                "COMSQUELCH1": 4.5,
                "COMACTRX1": False,
            },
            {
                "MAVMSG": "RADIO standby rx",
                "COMSTDRXLEVEL1": 10,
                "COMSQUELCH1": 4.5,
                "COMSTDRX1": True,
            },
            {
                "MAVMSG": "RADIO standby rx",
                "COMSTDRXLEVEL1": 10,
                "COMSQUELCH1": 4.5,
                "COMSTDRX1": True,
            },
            {
                "MAVMSG": "RADIO standby rx",
                "COMSTDRXLEVEL1": 0,
                "COMSQUELCH1": 4.5,
                "COMSTDRX1": False,
            },
            {"MAVMSG": "NO DATA"},
        ]
        # Engine keys we will continuously simulate regardless of script entries
        # Build dynamic list of cylinders by checking database for defined keys (support up to 12)
        self.cylinders = []
        for i in range(1, 13):
            egt_key = f"EGT1{i}"
            cht_key = f"CHT1{i}"
            try:
                # Will raise if key doesn't exist in DB
                self.parent.db_get_item(egt_key)
                self.parent.db_get_item(cht_key)
                self.cylinders.append(i)
            except Exception:
                continue
        # Engine keys (primary metrics + per-cylinder temps)
        self.engine_keys = {
            "TACH1",
            "MAP1",
            "FUELP1",
            "OILP1",
            "OILT1",
            "FUELF1",
        }
        for i in self.cylinders:
            self.engine_keys.add(f"EGT1{i}")
            self.engine_keys.add(f"CHT1{i}")

        # Supports {CONFIG} placeholder like server-level initialization files
        _cfg = getattr(self.parent, "config", {})
        inifile_template = _cfg.get("initialization_file")  # e.g. "{CONFIG}/init_data/engines/forDemo.ini"
        self._initialization_file = None
        if inifile_template:
            cfg_path = _cfg.get("CONFIGPATH", "")  # injected by loader
            try:
                inipath = inifile_template.format(CONFIG=cfg_path)
            except KeyError:
                # If placeholder missing, use raw template
                inipath = inifile_template
            if os.path.isfile(inipath):
                self._initialization_file = inipath
            else:
                self.log.error("Initialization file not found: %s", inipath)
        else:
            self.log.error("Missing required 'initialization_file' element in demo plugin .yaml file")

        # Continuous engine simulation parameters
        self._engine_start = time.time()

        # State for slow-moving temps
        self._oilt = self.keylist.get("OILT1", 90.0)
        self._cht = {}
        self._egt = {}
        for i in self.cylinders:
            self._cht[f"CHT1{i}"] = self.keylist.get(f"CHT1{i}", 200.0)
            self._egt[f"EGT1{i}"] = self.keylist.get(f"EGT1{i}", 650.0)
            
        # Independent phases so cylinders aren't identical
        self._phase = {}
        # Assign phase offsets evenly around a circle for variability
        if self.cylinders:
            for idx, cyl in enumerate(self.cylinders):
                # Spread phases 0..2π
                base_phase = (idx / len(self.cylinders)) * 2.0 * math.pi
                self._phase[f"EGT1{cyl}"] = base_phase
                self._phase[f"CHT1{cyl}"] = base_phase * 0.5  # slower differing phase

        # Initialize the points from keylist
        for each in self.keylist:
            self.parent.db_write(each, self.keylist[each])

        # Configuration for engine simulation and fuel drain
        self._cfg_engine = getattr(self.parent, "config", {}).get("engine_sim", {})
        self._engine_sim_enabled = bool(self._cfg_engine.get("enabled", False))

        self._cfg_fuel = getattr(self.parent, "config", {}).get("fuel_drain", {})
        self._fuel_enabled = bool(self._cfg_fuel.get("enabled", False))

        # Apply overrides from initialization file (after keylist so overrides win)
        if self._engine_sim_enabled:
            try:
                with open(self._initialization_file, "r") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("=")
                        if len(parts) < 2:
                            continue
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Use plugin db_write so aux (key.Aux) handled by database.write
                        try:
                            self.parent.db_write(key, value)
                        except Exception as e:
                            self.log.error("Init file write failed for %s: %s", key, e)
            except Exception as e:
                self.log.error("Failed reading initialization file %s: %s", self._initialization_file, e)

        # General timing configuration
        cfg = getattr(self.parent, "config", {})
        self._tick_hz = float(cfg.get("tick_rate_hz", 10.0))
        if self._tick_hz <= 0:
            self._tick_hz = 10.0
        
        self._tick_dt = 1.0 / self._tick_hz
        self._segment_steps = int(cfg.get("segment_steps", 20))
        if self._segment_steps < 1:
            self._segment_steps = 20

        # Engine sim config with defaults
        self._rpm_mean = float(self._cfg_engine.get("rpm_mean", 2450.0))
        self._rpm_amp = float(self._cfg_engine.get("rpm_amp", 250.0))
        self._rpm_period = float(self._cfg_engine.get("rpm_period", 60.0))

        self._map_base = float(self._cfg_engine.get("map_base", 18.0))
        self._map_amp = float(self._cfg_engine.get("map_amp", 6.0))
        self._map_period = float(self._cfg_engine.get("map_period", 45.0))
        self._map_rpm_coeff = float(self._cfg_engine.get("map_rpm_coeff", 0.004))

        self._oilp_base = float(self._cfg_engine.get("oilp_base", 55.0))
        self._oilp_amp = float(self._cfg_engine.get("oilp_amp", 8.0))
        self._oilp_period = float(self._cfg_engine.get("oilp_period", 50.0))
        self._oilp_rpm_coeff = float(self._cfg_engine.get("oilp_rpm_coeff", 0.003))

        self._fuelf_base = float(self._cfg_engine.get("fuelf_base", 7.5))
        self._fuelf_amp = float(self._cfg_engine.get("fuelf_amp", 1.5))
        self._fuelf_period = float(self._cfg_engine.get("fuelf_period", 60.0))
        self._fuelf_rpm_coeff = float(self._cfg_engine.get("fuelf_rpm_coeff", 0.0015))

        self._oilt_base = float(self._cfg_engine.get("oilt_base", 85.0))
        self._oilt_rpm_coeff = float(self._cfg_engine.get("oilt_rpm_coeff", 0.01))
        self._oilt_sin_amp = float(self._cfg_engine.get("oilt_sin_amp", 5.0))
        self._oilt_sin_period = float(self._cfg_engine.get("oilt_sin_period", 180.0))
        self._oilt_alpha = float(self._cfg_engine.get("oilt_alpha", 0.02))

        self._egt_base = float(self._cfg_engine.get("egt_base", 650.0))
        self._egt_amp = float(self._cfg_engine.get("egt_amp", 40.0))
        self._egt_period = float(self._cfg_engine.get("egt_period", 30.0))

        self._cht_base = float(self._cfg_engine.get("cht_base", 200.0))
        self._cht_amp = float(self._cfg_engine.get("cht_amp", 20.0))
        self._cht_period = float(self._cfg_engine.get("cht_period", 120.0))
        self._cht_oilt_coeff = float(self._cfg_engine.get("cht_oilt_coeff", 0.05))
        self._cht_alpha = float(self._cfg_engine.get("cht_alpha", 0.02))

        # Optional full sweep configuration
        # full_sweep: if True, override normal sinusoid CHT/EGT calcs and BARTEST sweeps
        # full_sweep_period: seconds for one min->max or max->min transition (half triangular wave)
        self._full_sweep = bool(self._cfg_engine.get("full_sweep", False))
        self._full_sweep_period = float(self._cfg_engine.get("full_sweep_period", 10.0))
        if self._full_sweep_period <= 0.0:
            self._full_sweep_period = 10.0

        # Tanks to drain; default to detected FUELQ1..FUELQ3 in keylist order
        default_tanks = [k for k in ["FUELQ1", "FUELQ2", "FUELQ3", "FUELQ4"] if k in self.keylist]
        self._fuel_tanks = list(self._cfg_fuel.get("tanks", default_tanks))
        # Rate in gallons per hour (total across all tanks)
        self._fuel_rate_gph = float(self._cfg_fuel.get("rate_gph", 8.0))
        # Distribution weights (same length as tanks); if not provided, equal split
        if "weights" in self._cfg_fuel:
            self._fuel_weights = list(self._cfg_fuel.get("weights"))
        else:
            self._fuel_weights = [1.0 / max(1, len(self._fuel_tanks))] * max(1, len(self._fuel_tanks))
        # Normalize weights to sum=1 to avoid surprises
        s = sum(self._fuel_weights) or 1.0
        self._fuel_weights = [w / s for w in self._fuel_weights]

    def run(self):
        count = 0
        script_count = -1
        script_when = -1
        last_tick = time.time()
        while not self.getout:
            count += 1
            script_when += 1
            # Sleep for nominal dt then compute actual elapsed time to reduce timing drift
            time.sleep(self._tick_dt)
            now_tick = time.time()
            actual_dt = max(0.0, now_tick - last_tick)
            last_tick = now_tick
            touched = set()

            # print(f"script_when:{script_when}, script_count:{script_count}")
            if "NO DATA" == self.script[script_count]["MAVMSG"]:
                self.parent.db_write("MAVMSG", "NO DATA")
                time.sleep(0.6)

            if script_when == 0:
                script_count += 1
                for k, v in self.script[script_count].items():
                    # Skip script assigning engine keys; we provide continuous simulation for them
                    if k in self.engine_keys:
                        continue
                    if not isinstance(v, str):
                        self.parent.db_write(k, v)
                        touched.add(k)
                if script_count + 1 == len(self.script):
                    script_count = -1
            else:
                if script_count < len(self.script):
                    for k, v in self.script[script_count].items():
                        # Skip engine keys in interpolation as well
                        if k in self.engine_keys:
                            continue
                        if not isinstance(v, str):
                            nxt = self.script[script_count + 1].get(k, None)
                            if nxt is not None:
                                val = (((nxt - v) / self._segment_steps) * script_when) + v
                                self.parent.db_write(k, val)
                                touched.add(k)
                if script_when == (self._segment_steps - 1):
                    script_when = -1

            # Continuous engine simulation updates every tick
            self._update_engine(touched)

            # Optional fuel drain simulation every tick using actual elapsed time
            self._update_fuel(touched, dt=actual_dt)
                    
            for each in self.keylist:
                if each in touched:
                    continue
                x = self.parent.db_read(each)
                if each in ["LAT", "LONG"]:
                    y = x[0] + (0.0000001 if (count % 2) == 0 else -0.0000001)
                    self.parent.db_write(each, y)
                else:
                    self.parent.db_write(each, x)

        self.running = False

    def stop(self):
        self.getout = True

    # --- Internal helpers ---
    def _update_engine(self, touched):
        """Continuously update engine-related keys to avoid long flat periods.
        Generates smooth variations using simple sinusoids and slow integrators.
        """
        if not self._engine_sim_enabled:
            return

        now = time.time()
        t = now - self._engine_start
        # RPM around mean ± amp with configured period
        rpm = self._rpm_mean + self._rpm_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._rpm_period)))
        # MAP loosely correlated with RPM
        map1 = self._map_base + self._map_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._map_period))) + self._map_rpm_coeff * (rpm - self._rpm_mean)
        # Oil pressure correlated to RPM with a little ripple
        oilp = self._oilp_base + self._oilp_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._oilp_period))) + self._oilp_rpm_coeff * (rpm - self._rpm_mean)
        # Fuel flow roughly proportional to power
        fuelf = self._fuelf_base + self._fuelf_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._fuelf_period))) + self._fuelf_rpm_coeff * (rpm - self._rpm_mean)

        # Oil temp: slow-moving towards a target based on power and long-period variation
        target_oilt = self._oilt_base + self._oilt_rpm_coeff * (rpm - self._rpm_mean) + self._oilt_sin_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._oilt_sin_period)))
        self._oilt += (target_oilt - self._oilt) * self._oilt_alpha  # slow approach

        if self._full_sweep:
            # Triangular wave between aux min/max for specified keys.
            # One half-period (min->max or max->min) = self._full_sweep_period
            # Full cycle (min->max->min) = 2 * self._full_sweep_period
            sweep_t = (t % (2.0 * self._full_sweep_period))
            ascending = sweep_t < self._full_sweep_period
            pos = sweep_t if ascending else (sweep_t - self._full_sweep_period)
            frac = pos / self._full_sweep_period  # 0..1 over a half sweep

            def sweep_value(item_key):
                try:
                    itm = self.parent.db_get_item(item_key)
                except Exception:
                    return None
                # Prefer aux Min/Max if present else fall back to item min/max
                aux_min = None
                aux_max = None
                try:
                    aux_min = itm.get_aux_value("Min")
                except Exception:
                    pass
                try:
                    aux_max = itm.get_aux_value("Max")
                except Exception:
                    pass
                lo = aux_min if isinstance(aux_min, (int, float)) else itm.min
                hi = aux_max if isinstance(aux_max, (int, float)) else itm.max
                # If bounds unavailable, return None to signal fallback
                if lo is None or hi is None:
                    return None
                span = hi - lo
                if span == 0:
                    return lo
                val = lo + span * (frac if ascending else (1.0 - frac))
                return val

            # Sweep CHT1-6, EGT1-6 if they exist
            for cyl in self.cylinders:
                if cyl > 6:
                    continue  # per request limit to 1-6
                egt_key = f"EGT1{cyl}"
                cht_key = f"CHT1{cyl}"
                for key in (egt_key, cht_key):
                    if key in self.engine_keys:
                        v = sweep_value(key)
                        if v is not None:
                            self.parent.db_write(key, v)
                            touched.add(key)
            # Sweep BARTEST1-4 if present
            for bar in range(1, 5):
                bar_key = f"BARTEST{bar}"
                try:
                    self.parent.db_get_item(bar_key)
                except Exception:
                    continue
                v = sweep_value(bar_key)
                if v is not None:
                    self.parent.db_write(bar_key, v)
                    touched.add(bar_key)
        else:
            # Cylinder/EGT temps per cylinder with phase offsets (original behavior)
            for cyl in self.cylinders:
                egt_key = f"EGT1{cyl}"
                cht_key = f"CHT1{cyl}"
                phase_egt = self._phase.get(egt_key, 0.0)
                phase_cht = self._phase.get(cht_key, 0.0)
                egt = self._egt_base + self._egt_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._egt_period)) + phase_egt)
                target_cht = self._cht_base + self._cht_amp * math.sin(2.0 * math.pi * (t / max(1e-6, self._cht_period)) + phase_cht) + self._cht_oilt_coeff * (self._oilt - self._oilt_base)
                self._cht[cht_key] += (target_cht - self._cht[cht_key]) * self._cht_alpha
                if egt_key in self.engine_keys:
                    self.parent.db_write(egt_key, egt)
                    touched.add(egt_key)
                if cht_key in self.engine_keys:
                    self.parent.db_write(cht_key, self._cht[cht_key])
                    touched.add(cht_key)

        # Fuel pressure follows fuel flow weakly with small ripple
        fuelp = 28.0 + 0.5 * math.sin(2.0 * math.pi * (t / 35.0)) + 0.02 * (fuelf - self._fuelf_base)

        # Write primary engine keys
        for key, val in (
            ("TACH1", rpm),
            ("MAP1", map1),
            ("OILP1", oilp),
            ("OILT1", self._oilt),
            ("FUELF1", fuelf),
            ("FUELP1", fuelp),
        ):
            if key in self.engine_keys:
                self.parent.db_write(key, val)
                touched.add(key)

    def _update_fuel(self, touched, dt: float = 1.0):
        """Simulate draining fuel from configured tanks.
        dt is the elapsed time in seconds for this update (0.1 per tick).
        """
        if not self._fuel_enabled or not self._fuel_tanks:
            return
        # gallons per second total
        gps = self._fuel_rate_gph / 3600.0
        for idx, tank in enumerate(self._fuel_tanks):
            try:
                w = self._fuel_weights[idx] if idx < len(self._fuel_weights) else 0.0
            except Exception:
                w = 0.0
            if w <= 0.0:
                continue
            try:
                current = self.parent.db_read(tank)[0]
            except Exception:
                continue
            newv = max(0.0, float(current) - gps * w * dt)
            self.parent.db_write(tank, newv)
            touched.add(tank)


class Plugin(plugin.PluginBase):
    def __init__(self, name, config, config_meta):
        super(Plugin, self).__init__(name, config, config_meta)
        self.thread = MainThread(self)
        self.status = OrderedDict()

    def run(self):

        self.thread.start()

    def stop(self):
        self.thread.stop()
        if self.thread.is_alive():
            self.thread.join(1.0)
        if self.thread.is_alive():
            raise plugin.PluginFail

    #def get_status(self):
    #    return self.status
    def get_status(self):
        """Return basic status for the demo connection."""
        try:
            count = len(self.thread.keylist) if getattr(self, "thread", None) else 0
        except Exception:
            count = 0
        return OrderedDict({"Item Count": count})

