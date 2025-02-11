# configs for x3_tool. import everything from user_program_config, but can also overwrite or add new configs here.
from user_program_config import *

#__________Main user program configs__________:
DEBUG = False
import time


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
    "mfm": ["1", "0"], #1 = ASCII, 0 = Binary. No RTCM for X3.
    "odr": ["20", "50", "100", "200"],
    "bau": ["19200", "57600", "115200", "230400", "460800", "921600"],
    "sync": ["on", "off"],
}

CFG_VALUE_NAMES = {
    ("mfm", "1"): "ASCII",
    ("mfm", "4"): "RTCM",
    ("mfm", "0"): "Binary",
}

#__________Log export configs__________:
EXPORT_MESSAGE_TYPES = [b'IMU']

EXPORT_IMU_FIELDS = ["imu_time_ms", "sync_time_ms",
                     "accel_x_g", "accel_y_g", "accel_z_g",
                     "angrate_x_dps", "angrate_y_dps", "angrate_z_dps",
                     "fog_angrate_x_dps", "fog_angrate_y_dps", "fog_angrate_z_dps",
                     "mag_x", "mag_y", "mag_z",
                     "temperature_c"]
