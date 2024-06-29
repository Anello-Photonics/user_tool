# format for custom binary message, shorter than RTCM

# Common packet format:
#   Preamble          |  msgtype   |  Length  | payload  |   checksum
#   0xC5 50  (2 byte) | 1 byte 1-6 |  1 byte  | variable |   2 byte

BINARY_PREAMBLE = b'\xC5\x50' #2 byte
BINARY_TYPE_LENGTH = 1
BINARY_LENGTH_LENGTH = 1
BINARY_ENDIAN = "little"
BINARY_CRC_LEN = 2

# binary  message types are numbers
BINARY_MSGTYPE_CAL = 1
BINARY_MSGTYPE_IMU = 2
BINARY_MSGTYPE_GPS = 3
BINARY_MSGTYPE_GP2 = 4
BINARY_MSGTYPE_HDG = 5
BINARY_MSGTYPE_INS = 6

#all the allowed types. TODO - should this be an enum or dictionary?
BINARY_MESSAGE_TYPES = [
    BINARY_MSGTYPE_CAL,
    BINARY_MSGTYPE_IMU,
    BINARY_MSGTYPE_GPS,
    BINARY_MSGTYPE_GP2,
    BINARY_MSGTYPE_HDG,
    BINARY_MSGTYPE_INS,
]

# use this to tag messages with the same ascii message types
BINARY_EQUIVALENT_MESSAGE_TYPES = {
    BINARY_MSGTYPE_CAL: b'CAL',
    BINARY_MSGTYPE_IMU: b'IMU',
    BINARY_MSGTYPE_INS: b'INS',
    BINARY_MSGTYPE_GPS: b'GPS',
    BINARY_MSGTYPE_GP2: b'GP2',
    BINARY_MSGTYPE_HDG: b'HDG',
}

# convert usual names to struct.pack/unpack codes. see: https://docs.python.org/3/library/struct.html
# long / unsigned long : l/L  are same size as int32 - any point using them?
# f float, d double : probably not using
NUMBER_TYPES = {
    'int8':     "b",
    'uint8':    "B",
    'int16':    "h",
    'uint16':   "H",
    'int32':    "i",
    'uint32':   "I",
    'int64':    "q",
    'uint64':   "Q",
}


# message formats: name, number type, scale (default 1)

BINARY_FORMAT_IMU = [
    ("imu_time_ns", "uint64"),  #keep this, also convert to imu_time_ms
    ("sync_time_ns", "uint64"), #keep this, also convert to sync_time_ms
    ("odometer_time_ns", "uint64"),  #keep this, also convert to odometer_time_ms
    ("accel_x_g", "int16", 0.0000305),  # also scaled by the accel range
    ("accel_y_g", "int16", 0.0000305),
    ("accel_z_g", "int16", 0.0000305),
    ("angrate_x_dps", "int16", 0.000035),  # also scaled by the rate range
    ("angrate_y_dps", "int16", 0.000035),
    ("angrate_z_dps", "int16", 0.000035),
    ("fog_angrate_z_dps", "int32", 1.0/10000000.0), #TODO - will there be a version with fog x/y rates too?
    ("odometer_speed_mps", "int16", 1.0/100),
    ("temperature_c", "int16", 1.0/100.0),
    ("mems_ranges", "uint16"),
    ("fog_range", "uint16"),
]

BINARY_FORMAT_INS = [
    ("imu_time_ns", "uint64"),  # keep this, also convert to imu_time_ms
    ("gps_time_ns", "uint64"),  # keep as ns only, no ms conversion
    ("lat_deg", "int32", 1.0/10000000),
    ("lon_deg", "int32", 1.0/10000000),
    ("alt_m", "int32", 1.0/100),  # altitude ellipsoid, but call it alt_m for consistency with ascii. TODO make it alt_ellipsoid_m everywhere?
    ("velocity_north_mps", "int16", 1.0/100),
    ("velocity_east_mps", "int16", 1.0/100),
    ("velocity_down_mps", "int16", 1.0/100),
    ("roll_deg", "int16", 1.0/100),
    ("pitch_deg", "int16", 1.0/100),
    ("heading_deg", "int16", 1.0/100),
    ("zupt_flag", "uint8"),
    ("ins_solution_status_and_gps_used", "uint8"),
]

BINARY_FORMAT_GPS = [
    ("imu_time_ns", "uint64"),  #keep this and convert to imu_time_ms too
    ("gps_time_ns", "uint64"),
    ("lat_deg", "int32", 1.0/10000000),
    ("lon_deg", "int32", 1.0/10000000),
    ("alt_ellipsoid_m", "int32", 1.0/100),
    ("alt_msl_m", "int32", 1.0/100),
    ("speed_mps", "int16", 1.0/100),
    ("heading_deg", "int16", 1.0/100),
    ("accuracy_horizontal_m", "uint16", 1.0/1000),
    ("accuracy_vertical_m", "uint16", 1.0/1000),
    ("PDOP", "uint16", 1.0/100),
    ("speed_accuracy_mps", "uint16", 1.0/1000),
    ("heading_accuracy_deg", "uint16", 1.0/100),
    ("num_sats", "uint8"),
    ("carrsoln_and_fix", "uint8"), #first 4 bits fix type, last 4 bits rtk status. handled in binary_scheme
]

BINARY_FORMAT_GP2 = BINARY_FORMAT_GPS

BINARY_FORMAT_HDG = [
    ("imu_time_ns", "uint64"), # keep this and convert to imu_time_ms
    ("gps_time_ns", "uint64"),
    ("relPosN_m", "int16", 1.0/100), # ascii has relpos N/E/D/len in meters but binary doc has cm: scale to meters?
    ("relPosE_m", "int16", 1.0/100),
    ("relPosD_m", "int16", 1.0/100),
    ("relPosLen_m", "int16", 1.0/100),
    ("relPosHeading_deg", "int16", 1.0/100),
    ("relPosLenAcc_m", "uint16", 1.0/10000),
    ("relPosHeadingAcc_deg", "uint16", 1.0/100),
    ("flags", "uint16"),
]
