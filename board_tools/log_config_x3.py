# WIP NOT FINISHED

import time

from config_configs import (
    CFG_FIELD_CODES_TO_NAMES,
    CFG_VALUE_NAMES,
    ERROR_CODES,
)

import sys
import pathlib
import cutie

parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir + "/src")
from src.tools import *
from ioloop import log_path


def log_board_config(board=None):
    """Logs the EVK configs to the logs folder in a config subdirectory

    Args:
        board (IMUBoard, optional): EVK object. Defaults to None.
    """

    if board is None:
        options = ["Auto", "Manual"]
        selected = options[cutie.select(options)]

        if selected == "Auto":
            anello = IMUBoard.auto(set_data_port=False)
        elif selected == "Manual":
            anello = IMUBoard()
            anello.connect_manually(set_data_port=False)
        else:
            print("Cutie option error")
            exit()
    else:
        anello = board

    serialnum = retry_command(
        anello, method=anello.get_serial, response_types=[b"SER"]
    ).ser.decode()

    root_python_code = pathlib.Path(__file__).parent.parent

    # without editing the original log_path had to edit the beginning of the given path
    config_path = pathlib.Path(
        log_path().replace("..", str(root_python_code))
    ).joinpath("config")
    config_path.mkdir(parents=True, exist_ok=True)

    filename = default_log_name(serialnum).replace("output", "config")
    config_path = config_path.joinpath(filename)

    with open(config_path, "w") as f:
        success = True
        max_retries = 6
        try:
            # use retry to increase success rate
            # user configurations
            resp = retry_command(
                anello, method=anello.get_cfg_flash, response_types=[b"CFG"], args=[[]]
            )
            f.write("User Configurations:\n")
            f.write(
                get_dict_str(
                    resp.configurations,
                    field_label=CFG_FIELD_CODES_TO_NAMES,
                    field_value=CFG_VALUE_NAMES,
                )
            )

            # write the firmware version to the log file
            resp = retry_command(
                board=anello,
                method=anello.get_version, 
                response_types=[b"VER"]
            ).ver
            dict = {"Firmware Version": resp}
            f.write(get_dict_str(dict))

        except Exception as e:
            print(e)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("Error sending message... missing configs")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            exit()
        pass
    return config_path


def get_dict_str(dict, field_label=[], field_value=[], value_start=50):
    """Returns a string formatted to be output from a dictionary

    Args:
        dict (_type_): _description_
        field_label (dict, optional): dictionary for the field labels to convert to readable names. Defaults to [].
        field_value (((String, String),String), optional): dictionary defined as (Field_label, Field_Value)->Decoded_Field_Value. Defaults to [].
        value_start (int, optional): The starting column for the Field values so they all line up. Defaults to 50.

    Returns:
        _type_: _description_
    """

    out_str = ""

    tab_str = "\t" * 1
    for item in dict:
        key = item
        value = dict[item].decode()

        if item in field_label:
            key = field_label[item]
        if (item, dict[item]) in field_value:
            value = field_value[(item, dict[item])]

        # calc number of spaces needed for all vals to start on the same line
        # num spaces =
        spaces = " " * (value_start - (len(key) + 4))

        out_str += f"\t{key}{spaces}:{tab_str}{value}\n"
    return out_str


def proper_response(message, expected_types): #UserProgram
    if not message:
        return False
    if not message.valid:  # actual problem with the message format or checksum fail, don't expect this
        print("\nMessage parsing error: "+message.error)
        return False
    elif message.msgtype in expected_types:
        return True
    elif message.msgtype == b'ERR':  # Error message, like if you sent a bad request
        print("\nError: " + ERROR_CODES[message.err])
        return False
    else:
        print('\nUnexpected response type: '+message.msgtype.decode())
        return False


def retry_command(board, method, response_types, args=[], retries=6):
    connection_errors = [1, 3, 4]
    # may need to clear input buffer here so some old message isn't read as a response.
    board.control_connection.reset_input_buffer()  # TODO - make this actually do something for UDP
    for i in range(retries):
        try:
            output_msg = method(*args)
            # no response: retry
            if not output_msg:
                continue
            # connection errors: retry. content errors like invalid fields/values don't retry
            if output_msg.msgtype == b"ERR" and output_msg.msgtype in connection_errors:
                continue
            # invalid response message or unexpected response type: retry
            if not proper_response(output_msg, response_types):
                continue
            else:
                return output_msg
        except Exception as e:
            continue  # error - treat as fail, retry
    # raise Exception("retry method: " + str(method) + " failed")
    # if it failed after retries, there is a connection problem
    return None  # didn't work -> function that calls this should check for None


def default_log_name(serialNum=None):
    # time_str = time.ctime(time.time()).replace(" ", "_").replace(":", "_")
    local = time.localtime()
    date_nums = [local.tm_year, local.tm_mon, local.tm_mday]
    time_nums = [local.tm_hour, local.tm_min, local.tm_sec]
    date_str = "date_" + "_".join([str(num).zfill(2) for num in date_nums])
    time_str = "time_" + "_".join([str(num).zfill(2) for num in time_nums])
    if serialNum is None:
        return "output_" + date_str + "_" + time_str + LOG_FILETYPE
    else:
        return (
            "output_"
            + date_str
            + "_"
            + time_str
            + "_SN_"
            + str(serialNum)
            + LOG_FILETYPE
        )


if __name__ == "__main__":
    log_board_config()
