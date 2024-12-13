import sys
import pathlib
parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src')
from tools import *
import os
from file_picking import pick_one_file, pick_multiple_files
import json
from configs_x3 import *

#default values: currently 0 for everything. could set a different value per field and message type

imu_header = ",".join(EXPORT_IMU_FIELDS)
def imu_defaults(name):
    return ""
    #return "missing"

all_show_fields = {
                   b'IMU': EXPORT_IMU_FIELDS,
    }

all_defaults = {b'IMU': imu_defaults}


#format of some field in the csv:
def format_field(msgtype, var_name, value):
    # float: force decimal since Kepler.gl will turn exponential notation into "string"
    if type(value) is float:
        return "{:.10f}".format(value).rstrip('0').rstrip('.')
    # can do more conditions using var_name and msgtype here. what about time formats?
    else:
        return str(value)


def export_logs_detect_format():
    default_dir = os.path.join(os.path.dirname(__file__), "../logs")
    file_paths = pick_multiple_files(initialdir=default_dir, title="Select one or multiple logs to convert")
    if not file_paths or len(file_paths) == 0:  # empty on cancel
        print("cancelled")
        return False  # indicates cancel

    for file_path in file_paths:
        if log_is_ascii(file_path):
            print(f"\nexporting {file_path} (detected ascii format)")
            if export_log_by_format(file_path, "ascii"):
                print(f"\nfinished exporting {file_path}")
        elif log_is_rtcm(file_path):
            print(f"\nexporting {file_path} (detected rtcm format)")
            if export_log_by_format(file_path, "rtcm"):
                print(f"\nfinished exporting {file_path}")
        elif log_is_binary(file_path):
            print(f"\nexporting {file_path} (detected binary format)")
            if export_log_by_format(file_path, "binary"):
                print(f"\nfinished exporting {file_path}")
        else:
            print(f"\ncould not detect format for file: {file_path}")
    return True


def export_log_by_format(file_path, format="rtcm"):
    if format == "ascii":
        parse_scheme = ReadableScheme()
        #start_char = b'#'
    elif format == "rtcm":
        parse_scheme = RTCM_Scheme()
        #start_char = b'\xD3'
    elif format == "binary":
        parse_scheme = Binary_Scheme()
    else:
        print(f"unknown format {format}, must be ascii, binary or rtcm")
        return

    # if format == "ascii":
    #     reader = FileReaderConnection(input_path) #wrapper around input file, has read_until method which ascii uses
    # elif format == "rtcm":
    #     reader = open(input_path, 'rb')

    reader = FileReaderConnection(file_path) #should work for either format

    # pick name and location for output files
    input_location = os.path.dirname(file_path)
    input_filename = os.path.basename(file_path) # should it take off the .txt or other extension?
    if "." in input_filename:
        input_notype = input_filename[:input_filename.find(".")] # before the .
    else:
        input_notype = input_filename

    # create new csv files for IMU, INS, GPS messages
    export_path = os.path.join(os.path.dirname(__file__), "..", "exports", input_notype) # exports directory
    #export_subdir = "export_"+input_notype  # sub-directory for this export only
    #export_fullpath = os.path.join(export_topdir, export_subdir)
    os.makedirs(export_path, exist_ok=True)

    imu_file_path = os.path.join(export_path, f"{input_notype}_imu.csv")
    print("exporting to " + os.path.normpath(imu_file_path))
    imu_out = open(imu_file_path, 'w')
    imu_out.write(imu_header)

    all_outputs = {b'IMU': imu_out}

    # for each line in log file (read though, split on start or end codes):
        # parse as a message: this is the most readable way of specifying fields - by names instead of index
        # put in the csv for that type

    # line = reader.readline()
    # line = line.strip(start_char)

    #print("line: "+line.decode())
    errors_count = 0
    line_num = 0
    while True: #until read empty - TODO figure out the loop condition

        #show progress: dot per some number of lines
        if line_num % 1000 == 0:
            print(".", end="", flush=True)
        line_num += 1

        if format == "ascii":
            m = parse_scheme.read_one_message(reader)
        elif format == "rtcm":
            m = parse_scheme.read_message_from_file(reader)
        elif format == "binary":
            m = parse_scheme.read_one_message_withlength(reader)

        if m is None: #done reading
            break

        #print(m)
        if m and m.valid and m.msgtype in EXPORT_MESSAGE_TYPES:
            # put whichever data we want based on message type and write to the csv for that type.
            # get each att rby name so it doesn't get show message.valid, checksum_input, etc
            # TODO - make a "message fields" structure in message for the fields so its not mixed together
            out_list = []
            msgtype = m.msgtype
            defaults = all_defaults[msgtype]
            out_file = all_outputs[msgtype]

            for name in all_show_fields[msgtype]: # or show_fields[m.msgtype]
                # use the existing message field, or default value
                if hasattr(m, name):
                    value = getattr(m, name)
                    out_list.append(format_field(msgtype, name, value))
                else:
                    out_list.append(str(defaults(name)))
            out_line = "\n"+",".join(out_list)
            out_file.write(out_line) # outputs[m.msgtype].write(out_line)

        else:
            errors_count += 1
            debug_print(f"\ninvalid message on line {line_num}: type = {m.msgtype if hasattr(m, 'msgtype') else 'None'}, valid = {m.valid}")
            debug_print(m)

    reader.close()
    imu_out.close()

    if errors_count == 1:
        print(f"\n1 message failed to parse")
    elif errors_count > 0:
        print(f"\n{errors_count} messages failed to parse")

    return True #indicate success. TODO - check for errors and return error code/False?


def log_is_ascii(log_path):
    ascii_scheme = ReadableScheme()
    file_reader = FileReaderConnection(log_path)
    for i in range(3):
        m = ascii_scheme.read_one_message(file_reader)
        if m and hasattr(m, "valid") and m.valid:
            file_reader.close()
            return True
    file_reader.close()
    return False


def log_is_rtcm(log_path):
    rtcm_scheme = RTCM_Scheme()
    file_reader = FileReaderConnection(log_path)
    for i in range(3):
        #could use rtcm_scheme.read_one_message here but it reads wrong when start char 0xD3 occurs inside the message
        #read_message_from_file uses pyrtcm read and is more reliable. TODO - make read_one_message work like that?
        m = rtcm_scheme.read_message_from_file(file_reader)
        if m and hasattr(m, "valid") and m.valid:
            file_reader.close()
            return True
    file_reader.close()
    return False

def log_is_binary(log_path):
    binary_scheme = Binary_Scheme()
    file_reader = FileReaderConnection(log_path)
    for i in range(3):
        m = binary_scheme.read_one_message(file_reader)
        if m and hasattr(m, "valid") and m.valid:
            file_reader.close()
            return True
    file_reader.close()
    return False


if __name__ == "__main__":
    export_logs_detect_format()
