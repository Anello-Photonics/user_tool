# version number for user_program and other tools
PROGRAM_VERSION = "1.3.5"

# ________________VERSION NOTES____________________

# _____ V1.3.5: Support AHRS message and X3 binary, monitor window improvements _____

#       add x3_tool.py which works for X3 units in binary or ASCII output
#       now the applications are:
#            x3_tool.py: for X3
#            user_program.py: for EVK, GNSS, IMU+
#            user_program_dataonly.py: for EVK, GNSS, IMU+ on a single serial cable with data port only
#       AHRS message: show in monitor window and in csv export, only for firmware versions with that message
#       monitor window: adjust layout and text to look better and be more readable

# _____ V1.3: updates to support EVK/GNSS/IMU firmware v1.3 release _____

# Support new features for firmware 1.3 release:
#       Zupt Calibration: manual or automatic
#       increase optional NMEA message outputs to include GGA,GSA, RMC at rates of 1-5 Hz.
#       Allow user to send position and heading to the unit
#       Allow separate baud rates on the config and data serial ports
#       Non-holonomic constraint options: car/default, agricultural, off
#       forward/backward detection: on/off

# Make user_program handle X3 product:
#       fix serial connecting issues
#       hide menus and monitor tabs which don't apply to X3
#       export X3 message format including 3 Optical Gyros and magnetometer.

# change to PySimpleGUI-4-foss version

# _____ V1.2: updates to support firmware v1.2 release _____

#   new configurations in 1.2:
#       alignment: fine adjustment of x,y,z angles in degrees
#   configs added after user_program v1.1, but before v1.2:
#       PTP mode (off / slave / master) - for GNSS product only
#       nmea GGA output (on/off) : optional GGA message output
#       antenna baseline and baseline configuration: vehicle configs for dual antenna heading

#   support new binary output format, with smaller messages than RTCM format
#       output formats are now:  ASCII, RTCM, Binary
#       handle the Binary format in monitor window and CSV export

#   vehicle configs page: improve the status and warning text

#   Firmware update:
#       call the bootloader automatically so user doesn't have to paste commands in terminal.
#       add bootloader version 2 exe for IMU+. user_program will pick the bootloader based on product type.

#   fix bugs:
#       fix the flood of NTRIP data when coming back onto network, which can cause errors in GPS module or ethernet
#       hide strange prints which happened in python dependency imports and file pickers.


# _____ V1.1: updates to support with firmware v1.1 release _____

#   support new configurations in v1.1 firmware:
# 	    serial output on/off
# 	    ethernet output on/off
# 	    NTRIP channel serial/ethernet/off
# 	    time sync on/off
# 	    acceleration low pass filter (Hz)
# 	    MEMS gyro low pass filter (Hz)
# 	    optical gyro low pass filter (Hz)
# 	    output message format RTCM/ASCII
#
#   support RTCM message format in monitor and csv export
#
#   add new tabs in monitor for each message type (INS/IMU/GPS/GP2/HDG)
#
#   add monitor map tab - requires GPS signal and internet connection
#
#   add GP2 and HDG messages to csv export
#
#   various improvements and bug fixes
