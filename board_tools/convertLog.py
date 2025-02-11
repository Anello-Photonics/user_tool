import sys
import pathlib
parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src')
from tools import *
import os
from file_picking import pick_one_file, pick_multiple_files
import json
from user_program_config import *

# default value for missing message fields. all empty string for now but can add special cases here.
def default_value(msgtype, field_name):
    return ""

# formatted point feature to put in csv
def position_for_csv(msg):
    lat, lon, props = 0,0, {}
    if msg.msgtype == b'INS' or msg.msgtype == b'IN':
        lat = msg.lat_deg if hasattr(msg, "lat_deg") else default_value(msg.msgtype, "lat_deg")
        lon = msg.lon_deg if hasattr(msg, "lon_deg") else default_value(msg.msgtype, "lon_deg")
        try:
            fillColor = EXPORT_INS_COLORS[getattr(msg, EXPORT_INS_COLOR_BASED_ON)]
        except Exception: # missing attribute or bad value
            fillColor = EXPORT_DEFAULT_COLOR
        props = {"radius": EXPORT_INS_RADIUS, "fillColor": fillColor} # could do radius and color based on variables
    elif msg.msgtype == b'GPS' or msg.msgtype == b'GP2' or msg.msgtype == b'GP':
        lat = msg.lat_deg if hasattr(msg, "lat_deg") else default_value(msg.msgtype, "lat_deg")
        lon = msg.lon_deg if hasattr(msg, "lon_deg") else default_value(msg.msgtype, "lon_deg")
        try:
            fillColor = EXPORT_GPS_COLORS[getattr(msg, EXPORT_GPS_COLOR_BASED_ON)]
        except Exception:
            fillColor = EXPORT_DEFAULT_COLOR
        props = {"radius": EXPORT_GPS_RADIUS, "fillColor": fillColor}
    geo_dict = {"type": "Point", "coordinates": [lon, lat]}
    feature_dict = {"type": "Feature", "geometry": geo_dict, "properties": props}
    return "\"" + json.dumps(feature_dict).replace("\"", "\"\"") + "\""


# format of some field in the csv:
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
    elif format == "rtcm":
        parse_scheme = RTCM_Scheme()
    elif format == "binary":
        parse_scheme = Binary_Scheme()
    else:
        print(f"unknown format {format}, must be ascii, binary or rtcm")
        return

    reader = FileReaderConnection(file_path) #should work for either format

    # pick name and location for output files: log file name with extension removed
    input_filename = os.path.basename(file_path)
    if "." in input_filename:
        input_notype = input_filename[:input_filename.find(".")]
    else:
        input_notype = input_filename

    # add directory where csv will go, based on log file name
    export_path = os.path.join(os.path.dirname(__file__), "..", "exports", input_notype)
    os.makedirs(export_path, exist_ok=True)

    # create log files and put header line in each
    all_outputs = {}
    message_counts = {}

    for msgtype, fields in EXPORT_ALL_MESSAGES.items():
        msgtype_string = msgtype.decode().lower()
        csv_file_path = os.path.join(export_path, f"{input_notype}_{msgtype_string}.csv")
        out_file = open(csv_file_path, 'w')
        csv_header = ",".join(fields)
        out_file.write(csv_header)

        all_outputs[msgtype] = out_file
        message_counts[msgtype] = 0

    # for each line in log file (read though, split on start or end codes):
        # parse as a message: this is the most readable way of specifying fields - by names instead of index
        # put in the csv for that type

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

        if m and m.valid and m.msgtype in EXPORT_ALL_MESSAGES:
            # put whichever data we want based on message type and write to the csv for that type.
            # get each att rby name so it doesn't get show message.valid, checksum_input, etc
            # TODO - make a "message fields" structure in message for the fields so its not mixed together
            out_list = []
            msgtype = m.msgtype
            out_file = all_outputs[msgtype]

            for name in EXPORT_ALL_MESSAGES[msgtype]:
                # do any constructed fields like position_geojson which are not in the message
                if name == "position_geojson":
                    out_list.append(position_for_csv(m))
                else:
                    # use the existing message field, or default value
                    if hasattr(m, name):
                        value = getattr(m, name)
                        out_list.append(format_field(msgtype, name, value))
                    else:
                        out_list.append(str(default_value(m.msgtype, name)))
            out_line = "\n"+",".join(out_list)
            out_file.write(out_line)
            message_counts[msgtype] += 1

        elif m and m.valid:
            # valid message but not in EXPORT_MESSAGE_TYPES : currently INF is this. do anything for these?
            pass
        else:
            errors_count += 1
            debug_print(f"\ninvalid message on line {line_num}: type = {m.msgtype if hasattr(m, 'msgtype') else 'None'}, valid = {m.valid}")
            debug_print(m)

    reader.close()

    for out_file in all_outputs.values():
        out_file.close()

    # remove any empty csv, for message types which were not in the log
    for msgtype, count in message_counts.items():
        if count == 0:
            os.remove(all_outputs[msgtype].name)

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
