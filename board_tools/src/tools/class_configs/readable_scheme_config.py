READABLE_START = b'#'
READABLE_END = b'\r\n'
READABLE_TALKER_LENGTH = 2
READABLE_TYPE_LENGTH = 3
READABLE_CHECKSUM_SEPARATOR = b'*'
READABLE_CHECKSUM_LENGTH = 2 #one calculated checksum byte, but represent as 2 ascii chars for the hex value
READABLE_PAYLOAD_SEPARATOR = b','
OUR_TALKER = b'AP'

#codes for CFG and FLA type
WRITE_RAM = b'w'
READ_RAM = b'r'
WRITE_FLASH = b'W'
READ_FLASH = b'R'


# APIMU,7757199.318,-0.0004,0.0131,0.5096,1.8946,-0.2313,-0.4396,0*7E
FORMAT_IMU_NO_SYNC = [ #normal EVK, length 11
    ("imu_time_ms", float),
    #("sync_time_ms", float),
    ("accel_x_g", float),
    ("accel_y_g", float),
    ("accel_z_g", float),
    ("angrate_x_dps", float),
    ("angrate_y_dps", float),
    ("angrate_z_dps", float),
    ("fog_angrate_z_dps", float),
    ("odometer_speed_mps", float),
    ("odometer_time_ms", float),
    ("temperature_c", float)
]

#new version with sync time after imu time (old sync gps ns was at end of message)
FORMAT_IMU_WITH_SYNC = [ #normal EVK, length 12
    ("imu_time_ms", float),
    ("sync_time_ms", float),
    ("accel_x_g", float),
    ("accel_y_g", float),
    ("accel_z_g", float),
    ("angrate_x_dps", float),
    ("angrate_y_dps", float),
    ("angrate_z_dps", float),
    ("fog_angrate_z_dps", float),
    ("odometer_speed_mps", float),
    ("odometer_time_ms", float),
    ("temperature_c", float)
]

#IMU type has no odometer, may or may not have fog.
# FORMAT_IMU_NO_ODO = [ #length 9
#     ("imu_time_ms", float),
#     ("accel_x_g", float),
#     ("accel_y_g", float),
#     ("accel_z_g", float),
#     ("angrate_x_dps", float),
#     ("angrate_y_dps", float),
#     ("angrate_z_dps", float),
#     ("fog_angrate_z_dps", float),
#     ("temperature_c", float)
# ]

#for IMU type without the fog
# FORMAT_IMU_NO_ODO_NO_FOG = [ #length 8
#     ("imu_time_ms", float),
#     ("accel_x_g", float),
#     ("accel_y_g", float),
#     ("accel_z_g", float),
#     ("angrate_x_dps", float),
#     ("angrate_y_dps", float),
#     ("angrate_z_dps", float),
#     ("temperature_c", float)
# ]

#3 fog with no sync format- is this still used?
FORMAT_IMU_3FOG = [ #length 13
    ("imu_time_ms", float),
    ("accel_x_g", float),
    ("accel_y_g", float),
    ("accel_z_g", float),
    ("angrate_x_dps", float),
    ("angrate_y_dps", float),
    ("angrate_z_dps", float),
    ("fog_angrate_x_dps", float),
    ("fog_angrate_y_dps", float),
    ("fog_angrate_z_dps", float),
    ("odometer_speed_mps", float),
    ("odometer_time_ms", float),
    ("temperature_c", float)
]

#older A1 firmware has fog volts, removed in v0.2.1
# FORMAT_IMU_WITH_FOG_VOLTS = [ #length 12
#     ("imu_time_ms", float),
#     ("accel_x_g", float),
#     ("accel_y_g", float),
#     ("accel_z_g", float),
#     ("angrate_x_dps", float),
#     ("angrate_y_dps", float),
#     ("angrate_z_dps", float),
#     ("fog_volts", float),
#     ("fog_angrate_z_dps", float),
#     ("odometer_speed_mps", float),
#     ("odometer_time_ms", float),
#     ("temperature_c", float)
# ]


FORMAT_IM1 = [ #for IMU or IMU+: no odo, has sync time. has FOG rate even if disabled (then shows 0)
    ("imu_time_ms", float),
    ("sync_time_ms", float), #TODO how is this defined?
    ("accel_x_g", float),
    ("accel_y_g", float),
    ("accel_z_g", float),
    ("angrate_x_dps", float),
    ("angrate_y_dps", float),
    ("angrate_z_dps", float),
    ("fog_angrate_z_dps", float),
    ("temperature_c", float)
]

UNLOCK_FLASH_CODE = b'704E2590'
LOCK_FLASH_CODE = b'1'
FLASH_UNLOCKED_VALUE = b'Unlocked'
FLASH_LOCKED_VALUE = b'Locked'

FORMAT_UNL = [
    ('locked', bytes)
]

FORMAT_VER = [
    ('ver', bytes)
]

FORMAT_SER = [
    ('ser', bytes)
]

FORMAT_PID = [
    ('pid', bytes)
]

FORMAT_IHW = [
    ('ihw', int)
]

FORMAT_FHW = [
    ('fhw', int)
]

FORMAT_FSN = [
    ('fsn', int)
]

# Error message has error code - int indicating which kind of error
FORMAT_ERR = [
    ('err', int)
]
ERROR_NO_START = 1
ERROR_NO_READ_WRITE = 2
ERROR_INCOMPLETE = 3
ERROR_CHECKSUM = 4
ERROR_TALKER = 5
ERROR_MSG_TYPE = 6
ERROR_FIELD = 7
ERROR_VALUE = 8
ERROR_FLASH_LOCKED = 9
ERROR_UNEXPECTED_CHAR = 10
ERROR_FEATURE_DISABLED = 11

# temporary status format: APSTA,errs,0,warnings,0,overall,PEACHY!*10
FORMAT_STA = [
    ("errs", int),
    ("warnings", int),
    ("overall", bytes)
]

# Reset has a code for reset type: 0-processor, 1-algorithm

FORMAT_RST = [
    ("code", int)
]

# ping response has a single number, constant
FORMAT_PNG = [
    ("code", int)
]

#APGPS elements (derived from ublox NAV-PVT message):
#APGPS,50057648,320315000.000,37.3990838,-121.9791725,-28.0670,1.8220,0.0360,232.6868,5.8751,5.8751,1.2600,3,20*72

# payload:                      ex value
    # imu time [msec]           50057648
    # gps (ITOW) time [msec]    320315000.000
    # lat [deg]                 37.3990838
    # lon [deg]                 -121.9791725
    # alt above ellipsoid [m]   -28.0670
    # alt above MSL [m]         1.8220
    # speed [m/s]               0.0360
    # heading [deg]             232.6868
    # Accur meas [m]            5.8751
    # Accur meas [m]            5.8751
    # PDOP                      1.2600
    # fix-type                  3
    # number of satellites      20

#APGPS: data from first antenna
FORMAT_GPS = [
    ("imu_time_ms", float),
    ("gps_time_ns", int),
    ("lat_deg", float),
    ("lon_deg", float),
    ("alt_ellipsoid_m", float),
    ("alt_msl_m", float),
    ("speed_mps", float),
    ("heading_deg", float),
    ("accuracy_horizontal_m", float),
    ("accuracy_vertical_m", float),
    ("PDOP", float),
    ("gnss_fix_type", int),
    ("num_sats", int),
    ("speed_accuracy_mps", float),
    ("heading_accuracy_deg", float),
    ("carrier_solution_status", int)
]

#APGP2 message from second antenna: same format as APGPS
FORMAT_GP2 = FORMAT_GPS

FORMAT_ODO = [
    ("speed", float)
]

#most of these can be blank if not initialized
FORMAT_INS = [
    ("imu_time_ms", int),
    ("gps_time_ns", int),
    ("ins_solution_status", int), #was heading_initialized
    ("lat_deg", float),
    ("lon_deg", float),
    ("alt_m", float),
    ("velocity_north_mps", float), #relative to the orientation setting, will be north, east, down in default +X+Y+Z
    ("velocity_east_mps", float),
    ("velocity_down_mps", float),
    ("roll_deg", float),
    ("pitch_deg", float),
    ("heading_deg", float),
    ("zupt_flag", int)
]

#for old A1 firmware, INS message has extra comma when position not initialized
FORMAT_INS_EXTRA_COMMA = [
    ("imu_time_ms", int),
    ("gps_time_ns", int),
    ("extra comma", int), #for the extra comma
    ("ins_solution_status", int),
    ("lat_deg", float),
    ("lon_deg", float),
    ("alt_m", float),
    ("velocity_north_mps", float),
    ("velocity_east_mps", float),
    ("velocity_down_mps", float),
    ("roll_deg", float),
    ("pitch_deg", float),
    ("heading_deg", float),
    ("zupt_flag", int)
]

# dual antenna heading message:
# #APHDG,977410.011,1361746447249999872,0.00,0.00,0.00,0.00,0.00000,0.0000,0.00000,1*5B
#        imu_time_ms  gps_time_ns,       N,   E,    D,   L    Head,  l acc, h acc, flags * cs
FORMAT_HDG = [
    ("imu_time_ms", float),
    ("gps_time_ns", int),
    ("relPosN_m", float),
    ("relPosE_m", float),
    ("relPosD_m", float),
    ("relPosLen_m", float),
    ("relPosHeading_deg", float),
    ("relPosLenAcc_m", float),
    ("relPosHeadingAcc_deg", float),
    ("flags", int), #10 bits of flags, see HEADING_FLAGS below.
]

HEADING_FLAGS = {
    0: "gnssFixOK",
    1: "diffSoln",
    2: "relPosValid",
    3: "carrSoln_bit1", #combine these when parsing.
    4: "carrSoln_bit2",
    5: "isMoving",
    6: "refPosMiss",
    7: "refObsMiss",
    8: "relPosHeading_Valid",
    9: "relPos_Normalized",
}

# put VEH options here so VEH methods can go in IMUBoard. originally in user_program_config.py
VEH_FIELDS = {
    "GPS Antenna 1    ": (("x", "g1x"), ("y", "g1y"), ("z", "g1z")),
    "GPS Antenna 2    ": (("x", "g2x"), ("y", "g2y"), ("z", "g2z")),
    "Rear Axle Center ": (("x", "cnx"), ("y", "cny"), ("z", "cnz")),
    "Output Center    ": (("x", "ocx"), ("y", "ocy"), ("z", "ocz")),
    "Antenna Baseline": "bsl",
    "Baseline Calibration": "bcal",
    "Ticks per rev ": "tic",
    "Wheel radius  ": "rad",
    "GPS accuracy floor (m)": "rmin",
}

VEH_VALUE_OPTIONS = {
    "bcal": ["1", "2", "99"]  # allow setting 0/None?
}

VEH_VALUE_NAMES = {
    ("bcal", "1"): "Auto calibrate",
    ("bcal", "2"): "From lever arms",
    ("bcal", "99"): "Reset",
    ("bcal", "0"): "Complete",
}

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
