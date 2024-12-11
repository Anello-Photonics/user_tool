#__________Main user program configs__________:
DEBUG = False
import time

# import sys
# import pathlib
# parent_dir = str(pathlib.Path(__file__).parent)
# sys.path.append(parent_dir+'/src/tools/class_configs')
# from readable_scheme_config import FORMAT_CAL_3FOG, FORMAT_BIAS, INI_UPD_ERROR_CODES

def debug_print(text):
    if DEBUG:
        print(text)


MENU_OPTIONS_X3 = [
    "Refresh",
    "Connect",
    "Restart Unit",
    "Unit Configuration",
    "Log",
    "Monitor",
    "Save Configs",
    "Firmware Update",
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
    "bau":          "Baud Rate                               ",
    "mfm":          "Message Format                          ",
    "sync":         "Time Sync                               ",
    "lpa":          "Acceleration Low Pass Filter Cutoff (Hz)",
    "lpw":          "MEMS Gyro Low Pass Filter Cutoff (Hz)   ",
    "lpo":          "Optical Gyro Low Pass Filter Cutoff (Hz)",
}

# suggestions on what you can enter. only for type in options
FILTER_EXPLANATION = "integer 1Hz to 90 Hz, or 0 = no filter"
CFG_FIELD_EXAMPLES = {
    "lpo": FILTER_EXPLANATION,
    "lpa": FILTER_EXPLANATION,
    "lpw": FILTER_EXPLANATION,
}

# fixed list of values to select
CFG_VALUE_OPTIONS = {
    "mfm": ["1", "0"], #1 = ASCII, 4 = RTCM. see CFG_VALUE_NAMES
    "odr": ["20", "50", "100", "200"],
    "bau": ["19200", "57600", "115200", "230400", "460800", "921600"],
    "sync": ["on", "off"],
}

message_formats_X3 = ["1", "0"]  # no RTCM for X3, just binary and ASCII

CFG_VALUE_NAMES = {
    ("mfm", "1"): "ASCII",
    ("mfm", "4"): "RTCM",
    ("mfm", "0"): "Binary",
}

CONNECT_RETRIES = 3
RUNNING_RETRIES = 10
FLUSH_FREQUENCY = 200

#__________Log export configs__________:
EXPORT_MESSAGE_TYPES = [b'IMU']

EXPORT_IMU_FIELDS = ["imu_time_ms", "sync_time_ms",
                     "accel_x_g", "accel_y_g", "accel_z_g",
                     "angrate_x_dps", "angrate_y_dps", "angrate_z_dps",
                     "fog_angrate_x_dps", "fog_angrate_y_dps", "fog_angrate_z_dps",
                     "mag_x", "mag_y", "mag_z",
                     "temperature_c"]

EXPORT_DEFAULT_COLOR = [200, 200, 200]

#__________monitor configs__________:
#general configs
MONITOR_MAP_TAB_TITLE = "MAP"
MONITOR_INS_TAB_TITLE = "INS"
MONITOR_IMU_TAB_TITLE = "IMU"
MONITOR_GPS_TAB_TITLE = "GPS"
MONITOR_GP2_TAB_TITLE = "GP2"
MONITOR_HDG_TAB_TITLE = "HDG"
MONITOR_REFRESH_MS = 200 #100
ZERO_OUT_TIME = 5
ODOMETER_ZERO_TIME = 10 #put a long time because odo in monitor updates slowly. at 5, it can blank with odo running.
SGTHEME = "Reddit"
# BASE_WIDTH = 1124
# BASE_HEIGHT = 554
MONITOR_ALIGN = "right" #alignemnt for label and value text in monitor. can be "left", "right", "center"

#tab 1: numbers monitoring
MONITOR_DEFAULT_VALUE = "--------------"
MONITOR_TIMELABEL_SIZE = (10,1)
MONITOR_TIME_SIZE = (6,1)
MONITOR_VALUE_SIZE = (15, 1)
FONT_NAME = "arial"
VALUE_FONT_SIZE = 25
MONITOR_LABEL_SIZE = (25, 1)
LABEL_FONT_SIZE = 20
GPS_TEXT = "GPS: "
LOG_TEXT = "LOG: "
TOGGLE_TEXT = {True:"ON", False: "OFF"}
TOGGLE_COLORS = {True: "green", False: "red"}
BUTTON_DISABLE_COLOR = "gray"
GPS_SOLN_NAMES = {0: "No solution", 1: "Float", 2: "Fix"}
GPS_FIX_NAMES = {0: "No Fix",
                 1: "Dead Reckoning Only",
                 2: "2D-Fix",
                 3: "3D-Fix",
                 4: "GNSS + Dead Reckoning",
                 5: "Time Only Fix" } #from nav-pvt fix-type: see https://www.u-blox.com/en/docs/UBX-18010854
INS_SOLN_NAMES = {255: "No Attitude", 0: "Attitude Only", 1: "INS (Pos. Only)", 2: "INS (Full Soln.)", 3: "RTK Float", 4: "RTK Fix"}
ZUPT_NAMES = {0: "Moving", 1: "Stationary"}

# monitor label text

# timestamps used across imu/ins/gps
IMU_TIME_TEXT = "IMU Time (ms):"
GPS_TIME_TEXT = "GPS Time (ns):"
SYNC_TIME_TEXT = "Sync Time (ms):"

# IMU tab
MEMS_AX_TEXT = "Accel x (g):"
MEMS_AY_TEXT = "Accel y (g):"
MEMS_AZ_TEXT = "Accel z (g):"
MEMS_WX_TEXT = "MEMS Rate x (deg/s):"
MEMS_WY_TEXT = "MEMS Rate y (deg/s):"
MEMS_WZ_TEXT = "MEMS Rate z (deg/s):"
FOG_WZ_TEXT = "FOG Rate z (deg/s):"
TEMP_C_TEXT = "Temperature (C):"
ODO_TEXT = "Odometer Speed (m/s):"
