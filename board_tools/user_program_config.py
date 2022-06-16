#__________Main user program configs__________:
DEBUG = False

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
    "Upgrade",
    #"Plot", # put this back in menu when implemented
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

CFG_FIELD_NAMES = [
    "OUTPUT DATA RATE",
    "ORIENTATION",
    "ENABLE GPS",
    #"GPS 2",
    "ODOMETER",
    "ENABLE FOG",
    "DHCP (AUTO ASSIGN IP)",
    "UDP A-1 IP",
    "UDP COMPUTER IP",
    "UDP COMPUTER DATA PORT ",
    "UDP COMPUTER CONFIGURATION PORT",
    "UDP COMPUTER ODOMETER PORT"
]

# cfg codes in messaging. must match order of CFG_FIELD_NAMES
# TODO use a dict or 2-way lookup?
CFG_FIELD_CODES = [
    "odr",
    "orn",
    "gps1",
    #"gps2",
    "odo",
    "fog",
    "dhcp",
    "lip",
    "rip",
    "rport1",
    "rport2",
    "rport3"
]

#UDP_FIELD_INDICES = [5, 6, 7, 8, 9]  # udp related field positions in CFG_FIELD_NAMES / CODES
UDP_FIELDS = ["dhcp","lip", "rip", "rport1", "rport2"]

# suggestions on what you can enter. only for type in options
CFG_FIELD_EXAMPLES = {
    "orn": "(e.g. +X-Y-Z or any of the possible 24 right-handed frame options)",
    "lip": "(aaa.bbb.ccc.ddd)",
    "rip": "(aaa.bbb.ccc.ddd)",
    "rport1": "(int from 1 to 65535)",
    "rport2": "(int from 1 to 65535)",
    "rport3": "(int from 1 to 65535)"
}

# fixed list of values to select
CFG_VALUE_OPTIONS = {
    "orn": ["North-East-Down (+X+Y+Z)", "East-North-Up (+Y+X-Z)", "Select Other"],
    "odr": [20, 50, 100, 200],
    "gps1": ["on", "off"],
    #"gps2": ["on", "off"],
    "odo": ["mps", "mph", "kph", "fps"],
    "fog": ["on", "off"],
    "dhcp": ["on", "off"]
}

#can have notes for just 2 cases now - if more notes needed, do another list or dictionary
ORN_8_OPTIONS = [
    "+X+Y+Z (North-East-Down)",
    "+Y+X-Z (East-North-Up)",
    "-X-Y+Z",
    "+Y-X+Z",
    "-Y+X+Z",
    "+X-Y-Z",
    "-X+Y-Z",
    "-Y-X-Z"
]

VEH_FIELDS = {
    "LEVER ARM 1": (("x", "g1x"), ("y", "g1y"), ("z", "g1z")),
    "LEVER ARM 2": (("x", "g2x"), ("y", "g2y"), ("z", "g2z")),
    "VEHICLE CENTER": (("x", "cnx"), ("y", "cny"), ("z", "cnz")),
    "OUTPUT CENTER": (("x", "ocx"), ("y", "ocy"), ("z", "ocz"))
}

#UDP constants
#A1_port1 = UDP_LOCAL_DATA_PORT
#A1_port2 = UDP_LOCAL_CONFIG_PORT
UDP_CACHE = "udp_settings.txt"
NTRIP_CACHE = "ntrip_settings.txt"


CONNECT_RETRIES=3
RUNNING_RETRIES=10
FLUSH_FREQUENCY = 200

#__________Log export configs__________:
EXPORT_MESSAGE_TYPES = [b'IMU', b'INS', b'GPS']

# EXPORT_IMU_FIELDS = ["imu_time_ms","accel_x_g","accel_y_g","accel_z_g",
#                      "angrate_x_dps","angrate_y_dps","angrate_z_dps","fog_angrate_dps",

EXPORT_IMU_FIELDS = ["imu_time_ms", "sync_gps_ns",
                     "accel_x_g","accel_y_g","accel_z_g",
                     "angrate_x_dps","angrate_y_dps","angrate_z_dps","fog_angrate_z_dps",
                     "odometer_speed_mps","odometer_time_ms","temperature_c"]

EXPORT_GPS_FIELDS = ["imu_time_ms","gps_time_ns", "sync_gps_ns",
                     "lat_deg","lon_deg","alt_ellipsoid_m","alt_msl_m",
                    "speed_mps","heading_deg","accuracy_horizontal_m","accuracy_vertical_m","PDOP",
                    "gnss_fix_type","num_sats","speed_accuracy_mps", "heading_accuracy_deg","carrier_solution_status", "position_geojson"]

EXPORT_INS_FIELDS = ["imu_time_ms","gps_time_ns", "sync_gps_ns",
                     "ins_solution_status","lat_deg","lon_deg","alt_m",
                    "velocity_0_mps","velocity_1_mps","velocity_2_mps","attitude_0_deg", "attitude_1_deg","attitude_2_deg",
                     "zupt_flag", "position_geojson"]

EXPORT_DEFAULT_COLOR = [200,200,200]

EXPORT_GPS_RADIUS = 3
EXPORT_GPS_COLOR_BASED_ON = "carrier_solution_status"
EXPORT_GPS_COLORS = {0:[255, 0, 0], 1:[255, 255, 0], 2:[0, 255, 0]}

EXPORT_INS_RADIUS = 1
EXPORT_INS_COLOR_BASED_ON = "zupt_flag"
EXPORT_INS_COLORS = {0: [0, 255, 0], 1: [255, 0, 0]}

#__________monitor configs__________:
MONITOR_REFRESH_MS = 200 #100
MONITOR_DEFAULT_VALUE = "--------------"
ZERO_OUT_TIME = 5
SGTHEME = "Reddit"
# BASE_WIDTH = 1124
# BASE_HEIGHT = 554
MONITOR_TIMELABEL_SIZE = (10,1)
MONITOR_TIME_SIZE = (6,1)
MONITOR_VALUE_SIZE = (15, 1)
FONT_NAME = "arial"
VALUE_FONT_SIZE = 25
MONITOR_LABEL_SIZE = (11,1)
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
INS_SOLN_NAMES = {0: "Attitude Only", 1: "INS (Pos. Only)", 2: "INS (Full Soln.)", 3: "RTK Float", 4: "RTK Fix"} #TODO check these too
ZUPT_NAMES = {0: "Moving", 1: "Stationary"}
