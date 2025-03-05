#__________Main user program configs__________:
DEBUG = False
import time

import sys
import pathlib
parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src/tools/class_configs')
from readable_scheme_config import INI_UPD_ERROR_CODES
import os

def debug_print(text):
    if DEBUG:
        print(text)


MENU_OPTIONS = [
    "Refresh",
    "Connect",
    "Restart Unit",
    "Unit Configuration",
    "Vehicle Configuration", #TODO - show this only when firmware version high enough / if unit responds to VEH,R
    "Log",
    "Monitor",
    "NTRIP",
    "Send Inputs",
    "Save Configs",
    "Firmware Update",
    #"Plot", # put this back in menu when implemented
    "Exit"
]


MENU_OPTIONS_WHEN_DISCONNECTED = [
    "Refresh",
    "Connect",
    "Log",  # can do log -> export when not connected, but not start a log.
    "Exit"
]

# Error codes - should only get error 8 when using config.py
ERROR_CODES = {
    1: "No start character",
    2: "Missing r/w for config",
    3: "Incomplete Message",
    4: "Invalid Checksum",
    5: "Invalid Talker code",
    6: "Invalid Message Type",
    7: "Invalid Field",
    8: "Invalid Value",
    9: "Flash Locked",
    10: "Unexpected Character",
    11: "Feature Disabled"
}

# dictionary of user config codes to names. TODO - use a bidict for two way lookup?
CFG_CODES_TO_NAMES = {
    "odr":          "Output Data Rate (Hz)                   ",
    "bau":          "Data Port Baud Rate                     ",
    "bau_input":    "Config Port Baud Rate                   ",
    "orn":          "Orientation                             ",
    "aln":          "Alignment Angles                        ",
    "gps1":         "Enable GPS 1                            ",
    "gps2":         "Enable GPS 2                            ",
    "odo":          "Odometer                                ",
    "fog":          "Enable FOG                              ", #TODO - remove this? may not do anything.
    "dhcp":         "DHCP (Auto Assign IP)                   ",
    "lip":          "UDP ANELLO Product IP                   ",
    "rip":          "UDP Computer IP                         ",
    "rport1":       "UDP Computer Data Port                  ",
    "rport2":       "UDP Computer Configuration Port         ",
    "rport3":       "UDP Computer Odometer Port              ",
    "mfm":          "Message Format                          ",
    "uart":         "Serial Output                           ",
    "eth":          "Ethernet Output                         ",
    "sync":         "Time Sync                               ",
    "ptp":          "PTP Mode                                ",
    "lpa":          "Acceleration Low Pass Filter Cutoff (Hz)",
    "lpw":          "MEMS Gyro Low Pass Filter Cutoff (Hz)   ",
    "lpo":          "Optical Gyro Low Pass Filter Cutoff (Hz)",
    "min":          "Configuration Print Interval (minutes)  ",
    "nhc":          "Non-Holonomic Constraint                ",
    "ntrip":        "NTRIP Input Channel                     ",
    "nmea":         "NMEA messages enabled                   ",
    "nmea_rate":    "NMEA output rate (Hz)                   ",
    "dir_det":      "Forward/Backward Detection              ",
    "ahrs":         "AHRS Message Control                    ",
}

RAM_ONLY_CONFIGS = {
    "azupt":        "AHRS ZUPT Toggle                        ",
    "ahdg":         "AHRS User Heading (degrees)             ",
}

# UDP_FIELD_INDICES = [5, 6, 7, 8, 9]  # udp related field positions in CFG_FIELD_NAMES / CODES
UDP_FIELDS = ["dhcp", "lip", "rip", "rport1", "rport2"]

# suggestions on what you can enter. only for type in options
CFG_FIELD_EXAMPLES = {
    "orn": "(e.g. +X-Y-Z or any of the possible 24 right-handed frame options)",
    "lip": "(aaa.bbb.ccc.ddd)",
    "rip": "(aaa.bbb.ccc.ddd)",
    "rport1": "(int from 1 to 65535)",
    "rport2": "(int from 1 to 65535)",
    "rport3": "(int from 1 to 65535)",
}

# fixed list of values to select
CFG_VALUE_OPTIONS = {
    "orn": ["+X+Y+Z", "+Y+X-Z", "-X-Y+Z", "+Y-X+Z", "-Y+X+Z", "+X-Y-Z", "-X+Y-Z", "-Y-X-Z"],
    "mfm": ["1", "4", "0"], #1 = ASCII, 4 = RTCM. see CFG_VALUE_NAMES
    "odr": ["20", "50", "100", "200"],
    "bau": ["19200", "57600", "115200", "230400", "460800", "921600"],
    "bau_input": ["19200", "57600", "115200", "230400", "460800", "921600"],
    "gps1": ["on", "off"],
    "gps2": ["on", "off"],
    "odo": ["mps", "mph", "kph", "fps"],
    "fog": ["on", "off"],
    "dhcp": ["on", "off"],
    "uart": ["on", "off"],
    "eth": ["on", "off"],
    "sync": ["on", "off"],
    "nhc": ["0", "2", "7"],
    "ntrip": ["0", "1", "2"],
    "ptp":  ["off", "master", "slave"],
    "nmea": ["0", "1", "2", "3", "4", "5", "6", "7"],
    "dir_det": ['on', 'off'],
    "nmea_rate": ["1", "2", "4", "5"],
    "ahrs": ['1', '0'],
    "azupt": ['1', '0'],
}

# no RTCM format for X3. this is only used if setting X3 message format in user_program.py, should use x3_tool instead.
message_formats_X3 = ["1", "0"]

RS232_BAUDS = ["19200", "57600", "115200", "230400"]

CFG_VALUE_NAMES = {
    #put only the fully supported formats: ASCII/RTCM/Binary
    ("mfm", "1"): "ASCII",
    ("mfm", "4"): "RTCM",
    ("mfm", "0"): "Binary",
    #add any others ? eg odometer unit names ("odo", "mph" : "miles per hour")
    ("odo", "mps"): "meters per second",
    ("odo", "mph"): "miles per hour",
    ("odo", "kph"): "kilometers per hour",
    ("odo", "fps"): "feet per second",
    ("nhc", "0"): "car/default",
    ("nhc", "2"): "agricultural",
    ("nhc", "7"): "off",
    ("ntrip", "0"): "off",
    ("ntrip", "1"): "serial",
    ("ntrip", "2"): "ethernet",
    ("orn", "+X+Y+Z"): "+X+Y+Z (Forward-Right-Down)",  # give special names to the two most common orientations.
    ("orn", "+Y+X-Z"): "+Y+X-Z (Right-Forward-Up)",
    ("ahrs", "1"): "on",
    ("ahrs", "0"): "off",
    ("azupt", "1"): "on",
    ("azupt", "0"): "off",
}

# ORN options, now moved into CFG_VALUE_OPTIONS.
# used only in user_program_dataonly and user_program_internal - can remove after updating those.
ORN_8_OPTIONS = [
    "+X+Y+Z (Forward-Right-Down)",
    "+Y+X-Z (Right-Forward-Up)",
    "-X-Y+Z",
    "+Y-X+Z",
    "-Y+X+Z",
    "+X-Y-Z",
    "-X+Y-Z",
    "-Y-X-Z"
]

VEH_FIELDS = {
    "GPS Antenna 1    ": (("x", "g1x"), ("y", "g1y"), ("z", "g1z")),
    "GPS Antenna 2    ": (("x", "g2x"), ("y", "g2y"), ("z", "g2z")),
    "Rear Axle Center ": (("x", "cnx"), ("y", "cny"), ("z", "cnz")),
    "Output Center    ": (("x", "ocx"), ("y", "ocy"), ("z", "ocz")),
    "Antenna Baseline": "bsl",
    "Baseline Calibration": "bcal",
    "Ticks per rev ": "tic",
    "Wheel radius  ": "rad",
}

BASELINE_TOLERANCE_FOR_WARNING = 0.1  # allow 10 cm before warning
BCAL_LEVER_ARM_WAIT_SECONDS = 3

#UDP constants

#A1_port1 = UDP_LOCAL_DATA_PORT
#A1_port2 = UDP_LOCAL_CONFIG_PORT
UDP_CACHE = os.path.join("board_tools", "udp_settings.txt")
NTRIP_CACHE = os.path.join("board_tools", "ntrip_settings.txt")
NTRIP_TIMEOUT_SECONDS = 2
NTRIP_RETRY_SECONDS = 30
#NTRIP_READ_SIZE = 2048 # how much it reads from caster at once
NTRIP_MAX_BYTES_PER_INTERVAL = 5000  # don't send in more that this much data per NTRIP_READ_INTERVAL_SECONDS
NTRIP_MAX_BYTES_PER_WRITE = 1400  # don't send in more that this much data per write
NTRIP_READ_INTERVAL_SECONDS = 1  # interval for NTRIP bytes limit
MAX_SINGLE_NTRIP_MESSAGE_SIZE = 1400  # max size of a single message to send to caster

CONNECT_RETRIES = 3
RUNNING_RETRIES = 10
FLUSH_FREQUENCY = 200

#__________Log export configs__________:

EXPORT_IMU_FIELDS = ["imu_time_ms", "sync_time_ms",
                     "accel_x_g", "accel_y_g", "accel_z_g",
                     "angrate_x_dps", "angrate_y_dps", "angrate_z_dps", "fog_angrate_z_dps",
                     "odometer_speed_mps", "odometer_time_ms",
                     "temperature_c"]

EXPORT_IM1_FIELDS = ["imu_time_ms", "sync_time_ms",
                     "accel_x_g", "accel_y_g", "accel_z_g",
                     "angrate_x_dps", "angrate_y_dps", "angrate_z_dps", "fog_angrate_z_dps",
                     #IM1 has no odometer info
                     "temperature_c"]

EXPORT_GPS_FIELDS = ["imu_time_ms", "gps_time_ns",
                     "lat_deg", "lon_deg", "alt_ellipsoid_m", "alt_msl_m",
                     "speed_mps", "heading_deg", "accuracy_horizontal_m", "accuracy_vertical_m", "PDOP",
                     "gnss_fix_type", "num_sats", "speed_accuracy_mps", "heading_accuracy_deg",
                     "carrier_solution_status", "position_geojson"]

EXPORT_GP2_FIELDS = EXPORT_GPS_FIELDS #make them same for now, but name this so it can change later.

EXPORT_INS_FIELDS = ["imu_time_ms", "gps_time_ns",
                     "ins_solution_status_and_gps_used", "ins_solution_status", "gps_used",
                     "lat_deg", "lon_deg", "alt_m",
                     "velocity_north_mps", "velocity_east_mps", "velocity_down_mps",
                     "roll_deg", "pitch_deg", "heading_deg",
                     "zupt_flag", "position_geojson"]

EXPORT_HDG_FIELDS = [
    "imu_time_ms", "gps_time_ns",
    "relPosN_m", "relPosE_m", "relPosD_m",
    "relPosLen_m", "relPosHeading_deg",
    "relPosLenAcc_m", "relPosHeadingAcc_deg",
    "flags",
    "gnssFixOK",
    "diffSoln",
    "relPosValid",
    "carrSoln",
    "isMoving",
    "refPosMiss", "refObsMiss",
    "relPosHeading_Valid", "relPos_Normalized",
]

EXPORT_AHRS_FIELDS = [
    "imu_time_ms", "sync_time_ms",
    "roll_deg", "pitch_deg", "heading_deg",
    "zupt_flag",
]

EXPORT_ALL_MESSAGES = {
    b'GPS': EXPORT_GPS_FIELDS,
    b'GP2': EXPORT_GPS_FIELDS,
    b'INS': EXPORT_INS_FIELDS,
    b'IMU': EXPORT_IMU_FIELDS,
    b'IM1': EXPORT_IM1_FIELDS,
    b'HDG': EXPORT_HDG_FIELDS,
    b'AHRS': EXPORT_AHRS_FIELDS,
}

EXPORT_DEFAULT_COLOR = [200, 200, 200]

EXPORT_GPS_RADIUS = 3
EXPORT_GPS_COLOR_BASED_ON = "carrier_solution_status"
EXPORT_GPS_COLORS = {0: [255, 0, 0], 1: [255, 255, 0], 2: [0, 255, 0]}

EXPORT_INS_RADIUS = 1
EXPORT_INS_COLOR_BASED_ON = "zupt_flag"
EXPORT_INS_COLORS = {0: [0, 255, 0], 1: [255, 0, 0]}

#__________monitor configs__________:

ON_BUTTON_FILE = "button_on.png"
OFF_BUTTON_FILE = "button_off.png"

#general configs
MONITOR_MAP_TAB_TITLE = "MAP"
MONITOR_INS_TAB_TITLE = "INS"
MONITOR_IMU_TAB_TITLE = "IMU"
MONITOR_GPS_TAB_TITLE = "GPS"
MONITOR_GP2_TAB_TITLE = "GP2"
MONITOR_HDG_TAB_TITLE = "HDG"
MONITOR_AHRS_TAB_TITLE = "AHRS"
MONITOR_REFRESH_MS = 200 #100
ZERO_OUT_TIME = 5
ODOMETER_ZERO_TIME = 10 #put a long time because odo in monitor updates slowly. at 5, it can blank with odo running.
SGTHEME = "Reddit"
table_color_2 = "light blue"
# BASE_WIDTH = 1124
# BASE_HEIGHT = 554
MONITOR_ALIGN = "right" #alignemnt for label and value text in monitor. can be "left", "right", "center"

#tab 1: numbers monitoring
MONITOR_DEFAULT_VALUE = "--------------"
MONITOR_TIMELABEL_SIZE = (10, 1)
MONITOR_TIME_SIZE = (6, 1)

# fonts are "font family", "size", "style"
# style = italic, roman, bold, normal, underline, overstrike
LABEL_FONT = ("Tahoma", 24, "bold")
VALUE_FONT = ("Tahoma", 24, "normal")

# use different text box sizes per tab.
# aim to have all tabs sum ~ 40, but bold is larger than non-bold
INS_TAB_LABEL_SIZE = 18  # largest: "Number of Satellites"
INS_TAB_VALUE_SIZE = 22  # largest: GPS time ns number

AHRS_TAB_LABEL_SIZE = 18  # largest : "IMU time (ms)"  : 10 cuts off, 18 fits
AHRS_TAB_VALUE_SIZE = 22  # largest: imu time or sync time, 18 fits

IMU_TAB_LABEL_SIZE = 20  # largest:  Odometer Speed (m/s) : 18 slightly too small, 20 fits.
IMU_TAB_VALUE_SIZE = 20  # largest: imu time or sync time. 18 fits imu time

GPS_TAB_LABEL_SIZE = 24  # minimum 23 to fit "Altitude, Mean Sea Level (m)" which is 28 characters.
GPS_TAB_VALUE_SIZE = 15  # longest: lat and lon, 12 is close fit

HDG_TAB_LABEL_SIZE = 27  # largest: Reference Observation Miss Flag : 26 close fit, sometimes cuts off.
HDG_TAB_VALUE_SIZE = 12

GPS_TEXT = "GPS "
LOG_TEXT = "DATA LOGGING "
TOGGLE_TEXT = {True: "ON", False: "OFF"}
TOGGLE_COLORS = {True: "green", False: "red"}
BUTTON_DISABLE_COLOR = "gray"
GPS_SOLN_NAMES = {0: "No Fix", 1: "Float", 2: "Fix"}
GPS_FIX_NAMES = {0: "No Fix",
                 1: "Dead Reckoning Only",
                 2: "2D-Fix",
                 3: "3D-Fix",
                 4: "GNSS + Dead Reckoning",
                 5: "Time Only Fix" } #from nav-pvt fix-type: see https://www.u-blox.com/en/docs/UBX-18010854
INS_SOLN_NAMES = {255: "Uninitialized", 0: "Attitude Initialized", 1: "Position Initialized",
                  2: "Full Solution Initialized", 3: "RTK Float", 4: "RTK Fix"}
ZUPT_NAMES = {0: "Moving", 1: "Stationary"}

# monitor label text

# INS tab
INS_LAT_TEXT = "Latitude (deg)"
INS_LON_TEXT = "Longitude (deg)"
INS_SPEED_TEXT = "Speed (m/s)"
INS_ROLL_TEXT = "Roll (deg)"
INS_PITCH_TEXT = "Pitch (deg)"
INS_HEADING_TEXT = "Heading (deg)"
INS_SOLN_TEXT = "INS Status"
INS_ZUPT_TEXT = "State"
INS_ALT_TEXT = "Altitude (m)"

# timestamps used across imu/ins/gps
IMU_TIME_TEXT = "IMU Time (ms)"
GPS_TIME_TEXT = "GPS Time (ns)"
SYNC_TIME_TEXT = "Sync Time (ms)"

# GPS and GP2 Tabs
GPS_LAT_TEXT = "Latitude (deg)"
GPS_LON_TEXT = "Longitude (deg)"
GPS_ALT_ELLIPSOID_TEXT = "Altitude, Ellipsoid (m)"
GPS_ALT_MSL_TEXT = "Altitude, Mean Sea Level (m)"
GPS_SPEED_TEXT = "Speed (m/s)"
GPS_HEADING_TEXT = "Heading (deg)"
GPS_HACC_TEXT = "Horizontal Accuracy (m)"
GPS_VACC_TEXT = "Vertical Accuracy (m)"
GPS_PDOP_TEXT = "PDOP"
GPS_FIX_TEXT = "Fix Type"
GPS_NUMSV_TEXT = "Number of Satellites"
GPS_CARRSOLN_TEXT = "RTK Fix Status"
GPS_SPEEDACC_TEXT = "Speed Accuracy (m/s)"
GPS_HDG_ACC_TEXT = "Heading Accuracy (deg)"

# IMU tab
MEMS_AX_TEXT = "Accel x (g)"
MEMS_AY_TEXT = "Accel y (g)"
MEMS_AZ_TEXT = "Accel z (g)"
MEMS_WX_TEXT = "MEMS Rate x (deg/s)"
MEMS_WY_TEXT = "MEMS Rate y (deg/s)"
MEMS_WZ_TEXT = "MEMS Rate z (deg/s)"
FOG_WZ_TEXT = "FOG Rate z (deg/s)"
TEMP_C_TEXT = "Temperature (C)"
ODO_TEXT = "Odometer Speed (m/s)"

# HDG tab
HDG_HEADING_TEXT = "Dual Antenna Heading (deg)"
HDG_LENGTH_TEXT = "Dual Antenna Length (m)"
HDG_NORTH_TEXT = "Relative Position North (m)"
HDG_EAST_TEXT = "Relative Position East (m)"
HDG_DOWN_TEXT = "Relative Position Down (m)"
HDG_LEN_ACC_TEXT = "Length Accuracy (m)"
HDG_HDG_ACC_TEXT = "Heading Accuracy (deg)"
HDG_FLAGS_TEXT = "Dual Antenna Flags"
HDG_FLAGS_FIXOK_TEXT = "Fix OK Flag"
HDG_FLAGS_DIFFSOLN_TEXT = "Differential Solution Flag"
HDG_FLAGS_POSVALID_TEXT = "Relative Position Valid Flag"
HDG_FLAGS_ISMOVING_TEXT = "Is Moving Flag"
HDG_FLAGS_REFPOSMISS_TEXT = "Reference Position Miss Flag"
HDG_FLAGS_REFOBSMISS_TEXT = "Reference Observation Miss Flag"
HDG_FLAGS_HDGVALID_TEXT = "Heading Valid Flag"
HDG_FLAGS_NORMALIZED_TEXT = "Normalized Flag"
HDG_FLAGS_CARRSOLN_TEXT = "Carrier Solution Flag"

# AHRS tab - use same names as in IMU/INS?
AHRS_TIME_TEXT = IMU_TIME_TEXT
AHRS_SYNC_TEXT = SYNC_TIME_TEXT
AHRS_ROLL_TEXT = INS_ROLL_TEXT
AHRS_PITCH_TEXT = INS_PITCH_TEXT
AHRS_HEADING_TEXT = INS_HEADING_TEXT
AHRS_ZUPT_TEXT = INS_ZUPT_TEXT

# map tab

#sources for map, should be exact string that geotiler.draw_map uses. # TODO : use other names like "Open Street Map" <-> "osm" ?
# MAP_PROVIDERS = ["osm", "stamen-terrain"] #osm and stamen-terrain seem like good options
MAP_PROVIDERS = ["osm"]  # stamen not working in geotiler now - put back when it is fixed.

##all providers in geotiler, for testing. most of these have less detail than osm and stamen-terrain.
# MAP_PROVIDERS = ["osm", #good default option.
#                  "stamen-terrain", "stamen-terrain-lines", "stamen-terrain-background", #terrain map, or parts of it
#                  "stamen-toner", "stamen-toner-lite", #black/white map, less detail
#                  "stamen-watercolor", #nice painted look, but not much detail
#                  "bluemarble"] #color satellite pictures, but can't zoom in close
##or thunderforest-cycle but it needs an api key

#provider credits as text. TODO - make clickable link?
MAP_PROVIDER_CREDITS = {
    "osm": "Map images from OpenStreetMap under ODbL (openstreetmap.org/copyright)",
    "stamen-terrain": "Map tiles by Stamen Design (stamen.com) under CC BY 3.0 (creativecommons.org/licenses/by/3.0). Data by OpenStreetMap under ODbL (openstreetmap.org/copyright)"
}

#"Map tiles by Stamen Design (stamen.com) under CC BY 3.0 (creativecommons.org/licenses/by/3.0)\n Data by OpenStreetMap under ODbL (openstreetmap.org/copyright)"

PROVIDER_CREDIT_SIZE = 10

ARROW_FILE_NAME = "map_arrow_larger_center.png" #name of image file inside map directory
MAP_ARROW_SIZE = 50
MAP_ZOOM_MAX = 18 #19 is max for OSM but stamen-terrain seems to only go to 18. TODO - separate min and max for each provider?
MAP_ZOOM_MIN = 8 #could go down to 1=whole earth, but 3 and below have some load errors
MAP_ZOOM_DEFAULT = 16
DEFAULT_MAP_IMAGE = "default_map.png"
MAP_DIMENSIONS = (1200, 700)
MAX_CACHE_TILES = 2000 #max tiles in map LRU cache in case of memory limit. TODO - calculate how many we can fit in memory.
# at office: 700x500 pixel map was 9 or 12 tiles, full zoom range with osm and stamen-terrain was 240 total

#roll/pitch dials
DIAL_SIDE_PIXELS = 200
DIAL_OFFSET_DEG = 0
DIAL_ANGLE_STEP = 15
DIAL_DIRECTION = -1 #should be +1 or -1, to set direction of angles in dials
DIAL_TEXT_SIZE = 15
