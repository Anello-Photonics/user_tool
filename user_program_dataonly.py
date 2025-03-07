import os
from contextlib import redirect_stdout
#suppress prints during import. on Mac, "import PySimpleGUI" causes print which messes up cutie menu.
with open(os.devnull, "w") as f, redirect_stdout(f):
    import cutie
    import time
    import sys
    import pathlib
    import json
    #import subprocess
    import serial
    from multiprocessing import Array, Value, Process, Manager
    import base64
    import socket
    import select
    import random
    import io
    try: #get pylru if possible, otherwise will use dictionary
        import pylru
    except ModuleNotFoundError:
        pass #prints blocked here, but should indicate an error in map

    parent_dir = str(pathlib.Path(__file__).parent)

    BOARD_TOOLS_DIR = os.path.join(parent_dir, "board_tools")
    SRC_DIR = os.path.join(BOARD_TOOLS_DIR, "src")
    MAP_DIR = os.path.join(BOARD_TOOLS_DIR, "map")
    sys.path.append(BOARD_TOOLS_DIR)
    sys.path.append(SRC_DIR)
    sys.path.append(MAP_DIR)
    from board_tools.src.tools import *
    from board_tools.user_program_config import *
    from board_tools.version_num import PROGRAM_VERSION
    from board_tools.ioloop import *
    from board_tools.log_config import log_board_config

    from user_program import UserProgram, clear_screen, show_and_pause, load_udp_settings, save_udp_settings, default_log_name

    if USE_GRAPHICS:
        import PySimpleGUI as sg
        from board_tools.convertLog import export_logs_detect_format
        from board_tools.map.geotiler_demo import draw_map, draw_dial
        from board_tools.file_picking import pick_one_file, pick_multiple_files
        LOGO_PATH = os.path.join(BOARD_TOOLS_DIR, "anello_scaled.png")
        ON_BUTTON_PATH = os.path.join(BOARD_TOOLS_DIR, ON_BUTTON_FILE)
        OFF_BUTTON_PATH = os.path.join(BOARD_TOOLS_DIR, OFF_BUTTON_FILE)
        DEFAULT_MAP_IMG_PATH = os.path.join(MAP_DIR, DEFAULT_MAP_IMAGE)
        ARROW_FILE_PATH = os.path.join(MAP_DIR, ARROW_FILE_NAME)


#interface for A1 configuration and logging
class UserProgram_dataonly(UserProgram):

    # inherits most methods from UserProgram, including __init__
    # only need to override some methods to make it not use the config port.

    def mainloop(self):

        #replaces the MENU_OPTIONS from user_program_config since some options require data connection.
        menu_options_no_config_port = [
            "Refresh",
            "Connect",
            "Log",
            "Monitor",
            "NTRIP",
            "Exit"
        ]

        if not USE_GRAPHICS:
            menu_options_no_config_port.remove("Monitor")

        while True:
            try:
                clear_screen()
                self.show_info()
                print("\nSelect One:")
                action = menu_options_no_config_port[cutie.select(menu_options_no_config_port)]
                if action == "Connect":
                    self.connect()
                elif action == "Log":
                    self.log()
                elif action == "Monitor":
                    self.monitor()
                elif action == "NTRIP":
                    self.ntrip_menu()
                elif action == "Refresh":
                    self.refresh()
                elif action == "Exit":
                    self.exit()
                else:
                    raise Exception("invalid action: " + str(action))
            except (socket.error, socket.herror, socket.gaierror, socket.timeout, serial.SerialException, serial.SerialTimeoutException) as e:
                print(e)
                self.release()
                show_and_pause("connection error. check cable and reconnect")
            # #TODO - handle udp connection error, other errors

    def show_device(self):
        pass  # can't do this since it won't know product type or serial number

    # connect using com port or UDP IP and port
    # save output in a json
    # shows current connection on top of menu options
    def connect(self):
        while True:
            control_success = False
            try:  # catch connect_com and connect_udp errors here since there is a cancel
                clear_screen()
                self.show_connection()
                options = ["COM", "UDP", "cancel"]
                selected = options[cutie.select(options)]
                if selected == "COM":
                    new_connection = self.connect_com()
                    if new_connection:
                        self.connection_info = new_connection
                        control_success = True
                    else: #connect_com failed or canceled
                        continue
                elif selected == "UDP":
                    new_connection = self.connect_udp()
                    if new_connection:
                        self.connection_info = new_connection
                        self.con_type.value = b"UDP"
                        control_success = True
                    else: #connect_udp failed or canceled
                        continue
                else: # cancel
                    return  # TODO - check if its the "return inside try" problem
            except Exception as e: # error on control connection fail - need this since con_start might not be sent
                control_success = False
                self.release()
                show_and_pause("error connecting - check connections and try again")
                continue
            self.gps_received.value = False # need to see gps message again after each connect
            #check success from ioloop. TODO - maybe check new_connection here - will be None for cancel, then dont wait
            debug_print("wait for connect success")
            while self.con_succeed.value == 0:
                time.sleep(0.1)
                # should it time out eventually?
            debug_print("done waiting")
            data_success = (self.con_succeed.value == 1) # 0 waiting, 1 succeed, 2 fail
            debug_print("data success: "+str(data_success)+", control success: "+str(control_success))
            self.con_succeed.value = 0
            if data_success and control_success:
                return
            else:
                self.release()
                show_and_pause("error connecting - check connections and try again")
                continue

    def connect_com(self):
        print("\nConnect by COM port:")
        options = ["Manual", "cancel"]
        selected = options[cutie.select(options)]
        if selected == "Auto":
            self.release()
            board = IMUBoard.auto(set_data_port=True)
            if not board:
                return
        elif selected == "Manual":
            self.release()
            board = IMUBoard()
            board.connect_manually(set_data_port=True, set_config_port=False)
        else:  # cancel
            return
        self.board = board
        data_port_name = board.data_port_name
        board.data_connection.close()

        #let io_thread do the data connection - give it the signal, close this copy
        self.com_port.value, self.data_port_baud.value = data_port_name.encode(), board.data_baud
        self.con_type.value = b"COM"
        self.con_on.value = 1
        self.con_start.value = 1
        return {"type": "COM", "control port": board.control_port_name, "data port": data_port_name}

    # connect by UDP:
    # assume we already configured by com and have set all the ip and ports
    # to connect by udp: need to enter A1's ip ("local ip") and both computer ("remote") ports matching config
        # could cache these - use remembered one or enter again.
    # config remote ip needs to match this computer
    # A1 port numbers will be constants so put them in here.

    def connect_udp(self):
        print("\nConnect by UDP port:")
        options = ["Manual", "cancel"]
        settings = load_udp_settings()
        auto_name = ""
        if settings: # only show saved option if it loads
            lip, rport1, rport2 = settings
            auto_name = "Saved: A-1 ip = "+lip+", computer data port = "+str(rport1)+", computer config port = "+str(rport2)
            options = [auto_name]+options

        selected = options[cutie.select(options)]

        if settings and (selected == auto_name):
            A1_ip, data_port, config_port = lip, rport1, rport2
        elif selected == "Manual":
            print("enter udp settings: if unsure, connect by com and check configurations")
            A1_ip = input("A1 ip address: ")
            data_port = cutie.get_number('data port: ', min_value=1, max_value=65535, allow_float=False)
            config_port = cutie.get_number('configuration port: ', min_value=1, max_value=65535, allow_float=False)
        else:  # cancel
            return

        self.release()
        board = IMUBoard()
        self.board = board
        if selected == "Manual":
            save_udp_settings(A1_ip, data_port, config_port)

        # send udp start info to io thread:
        self.udp_ip.value, self.udp_port.value = A1_ip.encode(), data_port
        self.con_type.value = b"UDP"
        self.con_on.value = 1
        self.con_start.value = 1
        return {"type": "UDP", "ip": A1_ip, "port1": str(data_port), "port2": str(config_port)}

    def start_logging(self):
        if self.log_on.value:
            show_and_pause("already logging")
            return
        elif not self.board:
            show_and_pause("must connect before logging")
            return
        else:
            suggested = default_log_name(self.serialnum)
            options = ["default: " + suggested, "other"]
            print("\nFile name:")
            selected_option = cutie.select(options)
            if selected_option == 0:
                chosen_name = suggested
            else:
                chosen_name = input("file name: ")
            self.log_name.value = chosen_name.encode()
            self.log_on.value = 1
            self.log_start.value = 1


#(data_connection, logging_on, log_name, log_file, ntrip_on, ntrip_reader, ntrip_request, ntrip_ip, ntrip_port)
def runUserProg(exitflag, con_on, con_start, con_stop, con_succeed,
                con_type, com_port, data_port_baud, control_port_baud, udp_ip, udp_port, gps_received,
                log_on, log_start, log_stop, log_name,
                ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg, last_ahrs_msg,
                last_imu_time,
                serial_number
                ):
    prog = UserProgram_dataonly(exitflag, con_on, con_start, con_stop, con_succeed,
                       con_type, com_port, data_port_baud, control_port_baud, udp_ip, udp_port, gps_received,
                       log_on, log_start, log_stop, log_name,
                       ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                       ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                       last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg, last_ahrs_msg,
                       last_imu_time,
                       serial_number
                       )
    prog.mainloop()


if __name__ == "__main__":

    string_size = 500 # make Arrays big unless I find out how to resize
    #shared vars

    exitflag = Value('b', 0)
    con_on = Value('b', 0)
    con_start = Value('b', 0)
    con_stop = Value('b', 0)
    con_succeed = Value('b', 0)
    con_type = Array('c', string_size) #com/udp
    com_port = Array('c', string_size)#str
    data_port_baud = Value('i', 0)
    control_port_baud = Value('i', 0)  # maybe not used
    udp_ip = Array('c', string_size) #str
    udp_port = Value('i', 0) #int
    gps_received = Value('b', 0)
    # bundle all connection ones into one structure? same for logging / ntrip
    # or group into arrays by type: all single flags, all ints, etc

    log_on = Value('b', 0) # for current status
    log_start = Value('b', 0) # start signal
    log_stop = Value('b', 0) # stop signal
    log_name = Array('c', string_size) #Array('c', b'')

    ntrip_on = Value('b',0)
    ntrip_start = Value('b', 0)
    ntrip_stop = Value('b', 0)
    ntrip_succeed = Value('b', 0)
    ntrip_ip = Array('c', string_size)
    ntrip_port = Value('i', 0)
    ntrip_gga = Value('b', 0)
    ntrip_req = Array('c', string_size)  # b'') #probably biggest string - allocate more?

    #shared vars for monitor
    last_ins_msg = Array('c', string_size)
    last_gps_msg = Array('c', string_size)
    last_gp2_msg = Array('c', string_size)
    last_imu_msg = Array('c', string_size)
    last_hdg_msg = Array('c', string_size)
    last_ahrs_msg = Array('c', string_size)

    last_imu_time = Value('d', 0)

    serial_number = Array('c', string_size)

    shared_args = (exitflag, con_on, con_start, con_stop, con_succeed,
                   con_type, com_port, data_port_baud, control_port_baud, udp_ip, udp_port, gps_received,
                   log_on, log_start, log_stop, log_name,
                   ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed, ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                   last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg, last_ahrs_msg, last_imu_time,
                   serial_number,               
                   )
    io_process = Process(target=io_loop, args=shared_args)
    io_process.start()
    runUserProg(*shared_args) # must do this in main thread so it can take inputs
    io_process.join()

