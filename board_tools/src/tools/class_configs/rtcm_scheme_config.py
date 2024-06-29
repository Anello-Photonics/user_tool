#format for RTCM-style binary messages

#Common packet format:
#   Preamble    |   Reserved    |   Length  |message data |   CRC
#   0xD3        | 000000 (6 bit)|   10 bits |             |   3 byte

#but all message data starts with 16 bit message number plus subtype: parse that with common format, payload after that
#so then the general structure is:
#   Preamble    |   Reserved    |   Length  | msgtype               |   payload     |   CRC
#   0xD3        | 000000 (6 bit)|   10 bits | 12+4 bit = 2 bytes    |variable length|   3 byte

RTCM_PREAMBLE = b'\xD3' #1 byte
TYPE_LENGTH = 2 #12 bit message number + 4 bit subtype = 16bit = 2 bytes
LENGTH_LENGTH = 2 #10 bit length + 6 bit reserved = 16 bit = 2 bytes
ENDIAN = "little"
RTCM_CRC_LEN = 3

#rtcm message types are numbers
ANELLO_IDENTIFIER = 4058
RTCM_MSGTYPE_IMU = 1
RTCM_MSGTYPE_GPS = 2
RTCM_MSGTYPE_HEADING = 3
RTCM_MSGTYPE_INS = 4
RTCM_MSGTYPE_HPP = 5 #high precision position, not implemented yet
RTCM_MSGTYPE_IM1 = 6
RTCM_MSGTYPE_UBX1 = 14 #ublox 1 raw output, not implemented yet
RTCM_MSGTYPE_UBX2 = 15 #ublox 2 raw output, not implemented yet

#all the allowed types. TODO - should this be an enum? or use EQUIVALENT_MESSAGE_TYPES.keys as the list?
RTCM_MESSAGE_TYPES = [RTCM_MSGTYPE_IMU, RTCM_MSGTYPE_GPS, RTCM_MSGTYPE_HEADING, RTCM_MSGTYPE_INS, RTCM_MSGTYPE_HPP,
                      RTCM_MSGTYPE_IM1,RTCM_MSGTYPE_UBX1, RTCM_MSGTYPE_UBX2]

#use this to tag message ojbects with the same ascii message types
EQUIVALENT_MESSAGE_TYPES = {
    RTCM_MSGTYPE_IMU: b'IMU',
    RTCM_MSGTYPE_INS: b'INS',
    RTCM_MSGTYPE_GPS: b'GPS', #but also GP2 depending on the antenna id
    RTCM_MSGTYPE_IM1: b'IM1',
    RTCM_MSGTYPE_HEADING: b'HDG',
}

#IMU message:       payload (not including msgnum/subtype) adds to 48 bytes, agrees with payload length
#                                                                               bytes
# Message Number	UInt12 	4058                                                1.5
# Sub Type ID 		UInt4 	1                                                   0.5
# MCU Time 		    UInt64  us 		    Time since power on                     8       Q
# AX			    Int32 	15 g		Z-axis accel                            4       i or l
# AY			    Int32 	15 g		Y-axis accel                            4
# AZ			    Int32 	15 g		Z-axis accel                            4
# WX			    Int32 	450 dps		X-axis angular rate (MEMS)              4
# WY			    Int32 	450 dps		Y-axis angular rate (MEMS)              4
# WZ			    Int32 	450 dps		Z-axis angular rate (MEMS)              4
# OG_WZ			    Int32 	450 dps		High precision z-axis angular rate      4
# ODO			    Int16 	m/s		    Scaled composite odometer value         2       h
# ODR time		    Int64 	ms		    Timestamp of ODR reading                8       q
# Temp C			Int16   °C                                                  2       h

#name, type, scale factor
# RTCM_IMU_PAYLOAD_FIELDS = [
#     # ("msg_num", ""), #UInt12 ??
#     # ("sub_type_id", ""), #UInt4 ??
#     ("mcu_time_us", "Q"),
#     ("accel_x_g", "l"), #15g over max counts - should it be pow(2,16) instead?
#     ("accel_y_g", "l"),
#     ("accel_z_g", "l"),
#     ("rate_x_dps", "l"),
#     ("rate_y_dps", "l"),
#     ("rate_z_dps", "l"),
#     ("rate_fog_dps", "l",),
#     ("odo_mps", "h"),
#     ("odo_time_ms", "q"),
#     ("temp", "h")
# ]

RTCM_IMU_PAYLOAD_FIELDS_WITH_SYNC = [
    #ascii has imu_time_ms - convert us to ms with a scale factor, or add another field?
    ("imu_time_ns", "Q"), #"mcu_time_us" #TODO - is this nanoseconds?
    ("sync_time_ns", "Q"),
    ("odometer_time_ns", "q"), #odo_time_ms
    ("accel_x_g", "l", 15/pow(2, 31)), #accel_x_g  #15g over max counts - should it be pow(2,16) instead?
    ("accel_y_g", "l", 15/pow(2, 31)), #accel_y_g
    ("accel_z_g", "l", 15/pow(2, 31)), #accel_z_g
    ("angrate_x_dps", "l", 450/pow(2, 31)), #rate_x_dps
    ("angrate_y_dps", "l", 450/pow(2, 31)), #rate_y_dps
    ("angrate_z_dps", "l", 450/pow(2, 31)), #rate_z_dps
    ("fog_angrate_z_dps", "l", 450/pow(2, 31)), #rate_fog_dps
    ("odometer_speed_mps", "h", 1e-2), #odo_mps
    ("temperature_c", "h", 1e-2) #temp
]

RTCM_IMU_PAYLOAD_FIELDS_NO_SYNC = [ #length 48 - auto compute from the list?
    #ascii has imu_time_ms - convert us to ms with a scale factor, or add another field?
    ("imu_time_ns", "Q"), #"mcu_time_us" #TODO - is this nanoseconds?
    ("odometer_time_ns", "q"), #odo_time_ms
    ("accel_x_g", "l", 15/pow(2, 31)), #accel_x_g  #15g over max counts - should it be pow(2,16) instead?
    ("accel_y_g", "l", 15/pow(2, 31)), #accel_y_g
    ("accel_z_g", "l", 15/pow(2, 31)), #accel_z_g
    ("angrate_x_dps", "l", 450/pow(2, 31)), #rate_x_dps
    ("angrate_y_dps", "l", 450/pow(2, 31)), #rate_y_dps
    ("angrate_z_dps", "l", 450/pow(2, 31)), #rate_z_dps
    ("fog_angrate_z_dps", "l", 450/pow(2, 31)), #rate_fog_dps
    ("odometer_speed_mps", "h", 1e-2), #odo_mps
    ("temperature_c", "h", 1e-2) #temp
]

#sensor output for IMU/IMU+ units, has no odometer. equivalent to ASCII APIM1
#has sync time. will there be a version with no sync time too?
RTCM_IM1_PAYLOAD_FIELDS = [
    ("imu_time_ns", "Q"),
    ("sync_time_ns", "Q"),
    ("accel_x_g", "l", 15/pow(2, 31)), #accel_x_g  #15g over max counts - should it be pow(2,16) instead?
    ("accel_y_g", "l", 15/pow(2, 31)), #accel_y_g
    ("accel_z_g", "l", 15/pow(2, 31)), #accel_z_g
    ("angrate_x_dps", "l", 450/pow(2, 31)), #rate_x_dps
    ("angrate_y_dps", "l", 450/pow(2, 31)), #rate_y_dps
    ("angrate_z_dps", "l", 450/pow(2, 31)), #rate_z_dps
    ("fog_angrate_z_dps", "l", 450/pow(2, 31)), #rate_fog_dps
    ("temperature_c", "h", 1e-2) #temp
]

# GPS PVT message
#
# Message Number    UInt12      4058
# Sub Type ID       UInt4       3
# Time              UInt64      ns
# GPS Time          UInt64
# Latitude          Int64
# Longitude         Int64
# Alt ellipsoid     Int32
# Alt msl           Int32
# Speed             Int32
# Heading           Int32
# Hor_Acc           UInt32
# Ver_Acc           UInt32
# PDOP              UInt16
# FixType           UInt8
# SatNum            UInt8
# Speed Acc         UInt32
# Hdg Acc           UInt32
# RTK Status        UInt8
# Antenna ID        Uint8

RTCM_GPS_PAYLOAD_FIELDS = [
    #ascii has imu_time_ms - do scale conversion or have both?
    ("imu_time_ns", "Q"), #mcu_time_us
    ("gps_time_ns", "Q"), #gps_time_ns
    ("lat_deg", "i", 1e-7), #lat_frac_deg
    ("lon_deg", "i", 1e-7), #lon_frac_deg
    ("alt_ellipsoid_m", "i", 1e-3), #altitude_ell
    ("alt_msl_m", "i", 1e-3), #altitude_msl
    ("speed_mps", "i", 1e-3), #speed_frac_mps
    ("heading_deg", "i", 1e-3), #heading_frac_deg
    ("accuracy_horizontal_m", "I", 1e-3), #horiz_acc_frac_m
    ("accuracy_vertical_m", "I", 1e-3), #vert_acc_frac_m
    ("heading_accuracy_deg", "I", 1e-5), #heading_acc_frac_deg
    ("speed_accuracy_mps", "I", 1e-3), #speed_acc_frac_mps
    ("PDOP", "H", 1e-2), #p_dop
    ("gnss_fix_type", "B"), #fix_type
    ("num_sats", "B"), #n_sats
    ("carrier_solution_status", "B"), #rtk_status
    ("antenna_id", "B") #antenna_id - this is not in ASCII gps messages: equivalent to GPS/GP2 distinction
]

RTCM_DUAL_ANT_HEAD_FIELDS = [
    ("imu_time_ns", "Q"), #mcu_time_us   - goes to imu_time_ms in ascii
    ("gps_time_ns", "Q"),
    ("relPosN_m", "i", 1e-2), #convert to meters to match ascii.
    ("relPosE_m", "i", 1e-2),
    ("relPosD_m", "i", 1e-2),
    ("relPosLen_m", "i", 1e-2),
    ("relPosHeading_deg", "i", 1e-5), #convert to degrees
    ("relPosLenAcc_m", "i", 1e-4), #0.1mm in rtcm -> convert to meters
    ("relPosHeadingAcc_deg", "I", 1e-5), #convert to degrees
    ("flags", "H"), #adding "flags", uint16? docs says "may or may not keep this"
]

#INS message:                   bytes:62 in "payload" not including type plus msgtype, but got 64
# Message Number    UInt12      1.5
# Sub Type ID       UInt4       0.5
# Time              UInt64      8
# GPS Time          UInt64      8
# Status            UInt8       1
# Latitude          Int64       8
# Longitude         Int64       8
# Alt ellipsoid     Int32       4
# Vn                Int32       4
# Ve                Int32       4
# Vd                Int32       4
# Roll              Int32       4
# Pitch             Int32       4
# Heading/Yaw       Int32       4
# ZUPT              UInt8       1


RTCM_INS_PAYLOAD_FIELDS = [
    #ascii has imu_time_ms - do scale conversion or have both?
    ("imu_time_ns", "Q"), #mcu_time_us #todo: is this nanoseconds?
    ("gps_time_ns", "Q"), #gps_time_ns
    ("lat_deg", "i", 1e-7), #lat_deg
    ("lon_deg", "i", 1e-7), #lon_deg
    ("alt_m", "i", 1e-3), #alt_m
    ("velocity_north_mps", "i", 1e-3), #v_n_frac_mps #TODO - these n/e/d names are better than 0/1/2 like in ascii
    ("velocity_east_mps", "i", 1e-3), #v_e_frac_mps
    ("velocity_down_mps", "i", 1e-3), #v_d_frac_mps
    ("roll_deg", "i", 1e-5), #roll_frac_deg #todo - roll/pitch/heading probably better than the ascii 0/1/2
    ("pitch_deg", "i", 1e-5), #pitch_frac_deg
    ("heading_deg", "i", 1e-5), #head_frac_deg
    ("zupt_flag", "B"), #zupt_flag
    ("ins_solution_status_and_gps_used", "B") #status
]
