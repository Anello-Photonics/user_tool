from math import sqrt
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
    import re
    import traceback

    parent_dir = str(pathlib.Path(__file__).parent)
    BOARD_TOOLS_DIR = os.path.join(parent_dir, "board_tools")
    SRC_DIR = os.path.join(BOARD_TOOLS_DIR, "src")
    sys.path.append(BOARD_TOOLS_DIR)
    sys.path.append(SRC_DIR)

    from board_tools.src.tools import *
    from board_tools.configs_x3 import *
    from board_tools.ioloop import *
    from board_tools.src.tools.x3_unit import X3_Unit
    from board_tools.log_config_x3 import log_board_config
    from user_program import default_log_name

    USE_GRAPHICS = True
    if '-h' in sys.argv or '--headless' in sys.argv:
        USE_GRAPHICS = False

    if USE_GRAPHICS:
        import PySimpleGUI as sg
        from board_tools.convertLog_x3 import export_logs_detect_format
        from board_tools.file_picking import pick_one_file, pick_multiple_files
        LOGO_PATH = os.path.join(BOARD_TOOLS_DIR, "anello_scaled.png")
        ON_BUTTON_PATH = os.path.join(BOARD_TOOLS_DIR, ON_BUTTON_FILE)
        OFF_BUTTON_PATH = os.path.join(BOARD_TOOLS_DIR, OFF_BUTTON_FILE)


X3_TOOL_VERSION = "1.0"

#interface for X3 configuration and logging
class UserProgram:

    #(data_connection, logging_on, log_name, log_file, ntrip_on, ntrip_reader, ntrip_request, ntrip_ip, ntrip_port)
    def __init__(self, exitflag, con_on, con_start, con_stop, con_succeed,
                 con_type, com_port, data_port_baud, config_port_baud, udp_ip, udp_port, gps_received,
                 log_on, log_start, log_stop, log_name,
                 ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                 ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                 last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg,
                 last_imu_time,
                 shared_serial_number
                 ):
        self.connection_info = None
        self.board = None
        self.serialnum = ""
        self.shared_serial_number = shared_serial_number
        self.shared_serial_number.value = b""
        self.version = ""
        self.product_id = ""

        #keep the shared vars as class attributes so other UserProgram methods have them.
        #set them like self.log_name.value = x so change is shared. not self.log_name = x
        self.exitflag, self.con_on, self.con_start, self.con_stop, self.con_succeed = exitflag, con_on, con_start, con_stop, con_succeed
        self.con_type, self.com_port, self.data_port_baud, self.control_port_baud, self.udp_ip, self.udp_port, self.gps_received =\
            con_type, com_port, data_port_baud, control_port_baud, udp_ip, udp_port, gps_received
        self.log_on, self.log_start, self.log_stop, self.log_name = log_on, log_start, log_stop, log_name
        self.ntrip_on, self.ntrip_start, self.ntrip_stop, self.ntrip_succeed = ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed
        self.ntrip_ip, self.ntrip_port, self.ntrip_gga, self.ntrip_req = ntrip_ip, ntrip_port, ntrip_gga, ntrip_req
        self.last_ins_msg, self.last_gps_msg, self.last_gp2_msg, self.last_imu_msg, self.last_hdg_msg = last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg
        self.last_imu_time = last_imu_time

        #any features which might or not be there - do based on firmware version?
        self.available_configs = []

    def mainloop(self):
        while True:
            try:
                clear_screen()
                self.show_info()
                print("\nSelect One:")

                if self.board:
                    # is connected -> normal options
                    menu_options = MENU_OPTIONS_X3.copy()
                    if not USE_GRAPHICS:
                        menu_options.remove("Monitor")
                        menu_options.remove("Firmware Update")

                else:
                    # not connected: reduced options
                    menu_options = MENU_OPTIONS_WHEN_DISCONNECTED

                action = menu_options[cutie.select(menu_options)]
                if action == "Connect":
                    self.connect()
                elif action == "Unit Configuration":
                    self.configure()
                elif action == "Save Configs":
                    self.save_configurations()
                    show_and_pause("")  # pause to show config path here, since save_configurations doesn't pause
                elif action == "Log":
                    self.log()
                elif action == "Monitor":
                    self.monitor()
                elif action == "Firmware Update":
                    self.upgrade()
                elif action == "Plot":
                    self.plot()
                elif action == "Refresh":
                    self.refresh()
                elif action == "Exit":
                    self.exit()
                elif action == "Restart Unit":
                    self.reset()
                else:
                    raise Exception("invalid action: " + str(action))
            except (socket.error, socket.herror, socket.gaierror, socket.timeout, serial.SerialException, serial.SerialTimeoutException) as e:
                print(e)
                self.release()
                show_and_pause("connection error. check cable and reconnect")
            # #TODO - handle udp connection error, other errors

    #exit: close connections, signal iothread to exit (which will close its own connections)
    def exit(self):
        self.release()
        self.exitflag.value = 1
        exit()

    # release all connections before connecting again
    def release(self):
        self.stop_logging()
        #close_ntrip(self.ntrip_on, self.ntrip_reader)
        self.connection_info = None
        if self.board:
            self.board.release_connections()  # must release or reconnecting to the same ports will error
            self.board = None
        #signal iothread to stop data connection
        self.con_on.value = 0
        self.con_stop.value = 1

    # stop operations and data port before bootloader, but still need config port to send enter_bootloading command.
    def release_for_bootload(self):
        self.stop_logging()
        #self.connection_info = None #probably don't set to None - this tracks udp/com and port numbers.
        if self.board:
            #close board's data and odometer connections, keep control connection open.
            if hasattr(self.board, "data_connection"):  #setting con_stop to 1 -> ioloop will also close it.
                self.board.data_connection.close()
            if hasattr(self.board, "odometer_connection") and self.board.odometer_connection:
                self.board.odometer_connection.close()

        #signal iothread to stop data connection
        #Todo - should it signal and close, or close only, or signal only? set flags back after bootloading?
        self.con_on.value = 0
        self.con_stop.value = 1
        time.sleep(1) #wait for communications to stop - can it check for stop?

    # if we clear after every action, refresh does nothing extra
    def refresh(self):
        pass

    def show_info(self):
        print(f"\nANELLO X3 Setup Tool, version {X3_TOOL_VERSION}, " + date_time())
        if not USE_GRAPHICS:
            print("headless mode: graphics are disabled")
        print("\nSystem Status:")
        self.show_device()
        self.show_connection()
        self.show_logging()

    def show_device(self):
        if self.con_on.value and self.connection_info:
            print(
                  f"    Product type: {self.product_id.upper()}"
                  f"\n    Serial: {self.serialnum}"
                  f"\n    Firmware version: {self.version}")

    def show_connection(self):
        con = self.connection_info
        if con and self.con_on.value:
            # example is "A-1:SN is Connected on COM57"  - connect and get serial number?
            output = "    Connection: "+con["type"]+": "
            output += "configuration port = "+con["control port"]+", data port = "+con["data port"]
            print(output)
        else:
            print("    Connection: Not connected")

    def show_logging(self):
        if self.log_on.value:
            # TODO - count messages logged: either read file (if safe while writing) or communicate with process
            print("    Log: Logging to "+self.log_name.value.decode()) #+" ("+str(num_messages)+" messages logged )")
        else:
            print("    Log: Not logging")

    # connect using com port or UDP IP and port
    # save output in a json
    # shows current connection on top of menu options
    def connect(self):
        while True:
            control_success = False
            try:  # catch connect_com and connect_udp errors here since there is a cancel
                clear_screen()
                self.show_connection()

                result = self.connect_com()
                if result == "cancel":
                    return  # canceled in the auto/manual/cancel menu
                elif result:
                    new_connection = result
                    self.connection_info = new_connection
                    control_success = True
                else:  # connect_com failed: returns None
                    continue

            except Exception as e: # error on control connection fail - need this since con_start might not be sent
                control_success = False
                self.release()
                show_and_pause("error connecting - check connections and try again")
                continue

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
        options = ["Auto", "Manual", "cancel"]
        selected = options[cutie.select(options)]
        if selected == "Auto":
            self.release()
            board = X3_Unit.auto(set_data_port=True)
            if not board:
                return None
        elif selected == "Manual":
            print("\nFor ANELLO X3: use port number of RS422 cable as 'data' and UART cable as 'configuration'")
            self.release()
            board = X3_Unit()
            manual_result = board.connect_manually(set_data_port=True)
            if manual_result is None:
                return None
        else:  # cancel
            return "cancel"

        self.board = board
        data_port_name = board.data_port_name
        board.data_connection.close()

        # get product info, or assume bad connection if can't read it
        if not self.product_info_on_connect(board):
            board.release_connections()
            show_and_pause("\nfailed to read product info. Check connection settings and try again.")
            return None

        # let io_thread do the data connection - give it the signal, close this copy
        self.com_port.value, self.data_port_baud.value, self.control_port_baud.value = data_port_name.encode(), board.data_baud, board.control_baud
        self.con_type.value = b"COM"
        self.con_on.value = 1
        self.con_start.value = 1
        return {"type": "COM", "control port": board.control_port_name, "data port": data_port_name}

    def product_info_on_connect(self, board):
        combinations = (
            (board.get_serial, b'SER', 'ser', 'serialnum'),
            (board.get_version, b'VER', 'ver', 'version'),
            (board.get_pid, b'PID', 'pid', 'product_id'))

        for (getter_method, msgtype, attr_name, name_here) in combinations:
            get_response = self.retry_command(method=getter_method, response_types=[msgtype])
            if hasattr(get_response, attr_name):
                setattr(self, name_here, getattr(get_response, attr_name).decode()) # self.product_id = get_response.pid.decode()
            else:
                return False  # indicate failed connection

        self.shared_serial_number.value = self.serialnum.encode()
        return True   # success if none of the reads failed

    def configure(self):
        if not self.board:
            show_and_pause("Must connect before configuring")
            return
        clear_screen()
        if not self.read_all_configs(self.board):  # show configs automatically
            return #false means read failed -> go back to menu
        #check connection again since error can be caught in read_all_configs
        if not self.con_on.value:
            return
        #print("configure:")
        actions = ["Edit", "Done"]
        selected_action = actions[cutie.select(actions)]
        if selected_action == "Edit":
            self.set_cfg()
            self.configure()  # go back to configure screen to view/edit again. or remove this line -> main screen
        else:
            return

    def set_cfg(self):
        print("\nselect configurations to write\n")

        # allow setting only the configs which come back from the read, in that order.
        field_codes = [code for code in self.available_configs if code in CFG_CODES_TO_NAMES]
        field_names = [CFG_CODES_TO_NAMES[code] for code in field_codes]

        # cutie select for index, including cancel.
        # TODO - if bidict, can do name = options[cutie.select(options)], code = dict[name] , instead of index
        options = field_names + ["cancel"]
        selected_index = cutie.select(options)
        if options[selected_index] == "cancel":
            return
        args = {}
        name, code = field_names[selected_index], field_codes[selected_index]
        if code == "aln":
            print("\nEnter alignment angles")
            value = form_aln_string_prompt()
        elif code in CFG_VALUE_OPTIONS:
            print("\nselect " + name)
            value_options = CFG_VALUE_OPTIONS[code].copy()
            value_option_names = [CFG_VALUE_NAMES.get((code, opt), opt) for opt in value_options]  # cfg and vale code -> value name
            value = value_options[cutie.select(value_option_names)]
        elif code in CFG_FIELD_EXAMPLES:
            print("\nEnter value for " + name + ":\n" + CFG_FIELD_EXAMPLES[code])
            value = input()
        else:
            print("\nEnter value for " + name)
            value = input()
        args[code] = value.encode()

        resp = self.retry_command(method=self.board.set_cfg_flash, args=[args], response_types=[b'CFG', b'ERR'])
        if not proper_response(resp, b'CFG'):
            show_and_pause("") # proper_response already shows error, just pause to see it.

    # read and show all user configurations
    def read_all_configs(self, board):
        resp = self.retry_command(method=board.get_cfg_flash, args=[[]], response_types=[b'CFG'])
        if proper_response(resp, b'CFG'):
            configs_dict = resp.configurations

            #TODO - print the configs in order of CFG_CODES_TO_NAMES,
            # and put available_configs in that order too? maybe not needed

            self.available_configs = list(configs_dict.keys())
            print("Unit Configurations:")
            for cfg_field_code in configs_dict:
                if cfg_field_code in CFG_CODES_TO_NAMES:
                    full_name = CFG_CODES_TO_NAMES[cfg_field_code]
                    value_code = configs_dict[cfg_field_code].decode()
                    value_name = CFG_VALUE_NAMES.get((cfg_field_code, value_code), value_code)
                    print("\t" + full_name + ":\t" + value_name)
            return True
        else:
            show_and_pause(f"Error reading unit configs. Try again or check cables.\n")
            return False
            
    def save_configurations(self):
        if not self.board:
            show_and_pause("\nMust connect before saving")
            return

        config_path = log_board_config(self.board)
        print(f"\n Configuration Saved to {config_path}")
        time.sleep(.1)
        pass

    # logging mode:
    # prompt for file name with default suggestion
    # stay in logging mode with indicator of # messages logged updated once/sec
    # also count NTRIP messages if connected
    # stop when esc or q is entered
    def log(self):
        clear_screen()
        self.show_logging()
        actions = ["cancel"]
        # csv export needs graphics for file picker
        if USE_GRAPHICS:
            actions = ["Export to CSV"] + actions
        if self.log_on.value:
            actions = ["Stop"]+actions
        else:
            actions = ["Start"] + actions
        selected_action = actions[cutie.select(actions)]
        if selected_action == "Export to CSV":
            print("\nSelect logs in the file picker window")
            if export_logs_detect_format():
                show_and_pause("\nfinished exporting") #show if not canceled
            else: #canceled in file picker. #TODO - handle export errors here too?
                return
        elif selected_action == "Start":
            self.start_logging()
        elif selected_action == "Stop":
            self.stop_logging()
        else: #cancel
            return

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
            self.save_configurations()

    def stop_logging(self):
        self.log_on.value = 0
        self.log_stop.value = 1 #send stop signal to other thread which will close the log

    def monitor(self):

        if not USE_GRAPHICS:
            show_and_pause("\nno monitor when USE_GRAPHICS flag is false")
            return

        if not self.board:
            show_and_pause("connect before monitoring")
            return

        #main window freezes until monitor closes - explain that.
        clear_screen()
        print("\nMonitoring in other window. Close it to continue.")

        # prevent prints in monitor, like PySimpleGUI prints on mac
        # this didn't stop geotiler prints when no internet -> do in geotiler_demo too?
        with open(os.devnull, "w") as f, redirect_stdout(f):
            self.monitor_main()

    def monitor_main(self):
        ascii_scheme = ReadableScheme()
        #binary_scheme = RTCM_Scheme() #ByteScheme()
        binary_scheme = Binary_Scheme()
        rtcm_scheme = RTCM_Scheme()

        sg.theme(SGTHEME)

        # label_font = LABEL_FONT
        # value_font = VALUE_FONT

        #________________Top bar with log button and logo_______________________
        starting_img = ON_BUTTON_PATH if self.log_on.value else OFF_BUTTON_PATH
        log_button = sg.Button(image_filename=starting_img, key="log_button", enable_events=True,
                               button_color=sg.theme_background_color(), border_width=0)
        anello_logo = sg.Image(LOGO_PATH, size=(300, 80))
        log_label = sg.Text(LOG_TEXT, font=LABEL_FONT)
        buttons_row = [sg.Push(), log_label, log_button, sg.Push(), sg.Push(), sg.Push(), sg.Push(), anello_logo]

        # ________________ IMU Data _______________________

        ax_value = sg.Text(MONITOR_DEFAULT_VALUE, key="ax_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        ay_value = sg.Text(MONITOR_DEFAULT_VALUE, key="ay_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        az_value = sg.Text(MONITOR_DEFAULT_VALUE, key="az_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        wx_value = sg.Text(MONITOR_DEFAULT_VALUE, key="wx_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        wy_value = sg.Text(MONITOR_DEFAULT_VALUE, key="wy_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        wz_value = sg.Text(MONITOR_DEFAULT_VALUE, key="wz_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)

        fog_x_value = sg.Text(MONITOR_DEFAULT_VALUE, key="fog_x_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        fog_y_value = sg.Text(MONITOR_DEFAULT_VALUE, key="fog_y_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        fog_z_value = sg.Text(MONITOR_DEFAULT_VALUE, key="fog_z_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)

        mag_x_value = sg.Text(MONITOR_DEFAULT_VALUE, key="mag_x_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        mag_y_value = sg.Text(MONITOR_DEFAULT_VALUE, key="mag_y_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        mag_z_value = sg.Text(MONITOR_DEFAULT_VALUE, key="mag_z_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)

        temp_value = sg.Text(MONITOR_DEFAULT_VALUE, key="temp_value", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        imu_time_value = sg.Text(MONITOR_DEFAULT_VALUE, key="imu_cpu_time", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)
        imu_sync_value = sg.Text(MONITOR_DEFAULT_VALUE, key="imu_sync_time", size=IMU_TAB_VALUE_SIZE, font=VALUE_FONT, justification=MONITOR_ALIGN)

        ax_label = sg.Text(MEMS_AX_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        ay_label = sg.Text(MEMS_AY_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        az_label = sg.Text(MEMS_AZ_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        wx_label = sg.Text(MEMS_WX_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        wy_label = sg.Text(MEMS_WY_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        wz_label = sg.Text(MEMS_WZ_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)

        fog_x_label = sg.Text("FOG Rate x (deg/s)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        fog_y_label = sg.Text("FOG Rate y (deg/s)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        fog_z_label = sg.Text("FOG Rate z (deg/s)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)

        mag_x_label = sg.Text("Magnetometer x (G)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        mag_y_label = sg.Text("Magnetometer y (G)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        mag_z_label = sg.Text("Magnetometer z (G)", size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)

        temp_label = sg.Text(TEMP_C_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)

        imu_time_label = sg.Text(IMU_TIME_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)
        imu_sync_label = sg.Text(SYNC_TIME_TEXT, size=IMU_TAB_LABEL_SIZE, font=LABEL_FONT, justification=MONITOR_ALIGN)

        imu_col1 = sg.Column(alternating_color_table(
            [[imu_time_label, imu_time_value],
             [ax_label, ax_value],
             [ay_label, ay_value],
             [az_label, az_value],
             [mag_x_label, mag_x_value],
             [mag_y_label, mag_y_value],
             [mag_z_label, mag_z_value],
             [temp_label, temp_value]]))

        imu_col2 = sg.Column(alternating_color_table(
            [[imu_sync_label, imu_sync_value],
             [wx_label, wx_value],
             [wy_label, wy_value],
             [wz_label, wz_value],
             [fog_x_label, fog_x_value],
             [fog_y_label, fog_y_value],
             [fog_z_label, fog_z_value]]))

        imu_tab_layout = [[sg.vtop(imu_col1), sg.Push(), sg.vtop(imu_col2)]]
        imu_tab = sg.Tab(MONITOR_IMU_TAB_TITLE, imu_tab_layout, key="imu-tab")

        tab_group = sg.TabGroup([[imu_tab]])
        try_set_expand(tab_group)

        #group elements by size for resizing  - can this be assembled from ins_fields, imu_fields etc?
        label_font_elements = [ax_label, ay_label, az_label, wx_label, wy_label, wz_label,
                               fog_x_label, fog_y_label, fog_z_label, mag_x_label, mag_y_label, mag_z_label,
                               temp_label, imu_time_label, imu_sync_label ]

        value_font_elements = [ax_value, ay_value, az_value, wx_value, wy_value, wz_value,
                               fog_x_value, fog_y_value, fog_z_value, mag_x_value, mag_y_value, mag_z_value,
                               temp_value, imu_time_value, imu_sync_value]
        buttons = [log_button]

        top_layout = [buttons_row, [sg.HSeparator()], [tab_group]] #buttons on top, then tab 1 or 2
        window = sg.Window(title="Output monitoring", layout=top_layout, finalize=True, resizable=True)
        #any updates on elements need to be after this "finalize=True" statement (or after window.read if not finalized)

        window.bind('<Configure>', "Configure")
        base_width, base_height = window.size
        debug_print("BASE_WIDTH: "+str(base_width))
        debug_print("BASE_HEIGHT:" +str(base_height))

        last_last_imu = b''
        last_imu_time = time.time()
        #last_odo_speed = None
        last_odo_time = last_imu_time

        #fields by message type and tab, for zeroing out when no data.
        imu_fields = [ax_value, ay_value, az_value, wx_value, wy_value, wz_value,
                      fog_x_value, fog_y_value, fog_z_value, mag_x_value, mag_y_value, mag_z_value,
                      temp_value, imu_time_value, imu_sync_value]

        # update loop: check for new messages or button clicks, then update the displayed data
        while True:

            event, values = window.read(timeout=MONITOR_REFRESH_MS, timeout_key="timeout")
            active_tab = tab_group.get() #check this early so it can update only the active tab
            if event != "timeout":
                debug_print("event: " + str(event))
                debug_print("values: " + str(values))

            if event == sg.WIN_CLOSED:  # close - return to wait_for_monitor_start
                window.close() #needs this to close properly on raspberry pi. not needed in windows.
                break
            elif event == "log_button":
                #stop if on, start if off
                if self.log_on.value:
                    self.stop_logging()
                    log_button.update(image_filename=OFF_BUTTON_PATH)
                else:
                    #start log with default name
                    logname = default_log_name(self.serialnum)
                    self.log_name.value = logname.encode()
                    self.log_on.value = 1
                    self.log_start.value = 1
                    log_button.update(image_filename=ON_BUTTON_PATH)
            elif event == "Configure": #resize, move. also triggers on button for some reason.
                debug_print("size:")
                debug_print(repr(window.size))
                width, height = window.size
                scale = min(width / base_width, height / base_height)
                for item in value_font_elements:
                    fontname, fontsize, fontstyle = VALUE_FONT
                    item.update(font=(fontname, int(fontsize * scale), fontstyle))
                for item in label_font_elements:
                    fontname, fontsize, fontstyle = LABEL_FONT
                    item.update(font=(fontname, int(fontsize * scale), fontstyle))
                for item in buttons:
                    fontname, fontsize, fontstyle = LABEL_FONT
                    item.font = (fontname, int(fontsize * scale), fontstyle)

            if hasattr(self.last_imu_msg, "raw"):
                #print(f"has last_imu_msg: {self.last_imu_msg.raw}")
                #update for new imu message
                elapsed = time.time() - last_imu_time
                #TODO - can update any "time since imu" indicator here
                #if self.last_imu_msg.value == last_last_imu:
                if self.last_imu_msg.raw == last_last_imu:
                    # did not change - no update. but if it's been too long, zero the fields
                    # time_since_ins.update(str(elapsed))
                    # window.refresh()
                    if (elapsed > ZERO_OUT_TIME) and active_tab == "imu-tab":  # zero out the numbers tab
                        for field in imu_fields:
                            field.update(MONITOR_DEFAULT_VALUE)
                else:  # changed - update the last_ins and counter, then update display from the new values
                    # last_last_imu = self.last_imu_msg.value
                    last_last_imu = self.last_imu_msg.raw
                    last_imu_time = time.time()
                    imu_msg = try_multiple_parsers([binary_scheme, ascii_scheme, rtcm_scheme], self.last_imu_msg.raw)
                    if active_tab == 'imu-tab':
                        #print(f"\nimu_msg: {imu_msg}")
                        #update the imu fields from the message
                        window["ax_value"].update('%.4f'%imu_msg.accel_x_g if hasattr(imu_msg, "accel_x_g")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["ay_value"].update('%.4f' % imu_msg.accel_y_g if hasattr(imu_msg, "accel_y_g")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["az_value"].update('%.4f' % imu_msg.accel_z_g if hasattr(imu_msg, "accel_z_g")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["wx_value"].update('%.4f' % imu_msg.angrate_x_dps if hasattr(imu_msg, "angrate_x_dps")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["wy_value"].update('%.4f' % imu_msg.angrate_y_dps if hasattr(imu_msg, "angrate_y_dps")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["wz_value"].update('%.4f' % imu_msg.angrate_z_dps if hasattr(imu_msg, "angrate_z_dps")
                                                  else MONITOR_DEFAULT_VALUE)
                        window["fog_x_value"].update('%.4f' % imu_msg.fog_angrate_x_dps
                                                   if hasattr(imu_msg, "fog_angrate_x_dps") else MONITOR_DEFAULT_VALUE)
                        window["fog_y_value"].update('%.4f' % imu_msg.fog_angrate_y_dps
                                                   if hasattr(imu_msg, "fog_angrate_y_dps") else MONITOR_DEFAULT_VALUE)
                        window["fog_z_value"].update('%.4f' % imu_msg.fog_angrate_z_dps
                                                   if hasattr(imu_msg, "fog_angrate_z_dps") else MONITOR_DEFAULT_VALUE)
                        window["mag_x_value"].update('%.4f' % imu_msg.mag_x
                                                   if hasattr(imu_msg, "mag_x") else MONITOR_DEFAULT_VALUE)
                        window["mag_y_value"].update('%.4f' % imu_msg.mag_y
                                                   if hasattr(imu_msg, "mag_y") else MONITOR_DEFAULT_VALUE)
                        window["mag_z_value"].update('%.4f' % imu_msg.mag_z
                                                   if hasattr(imu_msg, "mag_z") else MONITOR_DEFAULT_VALUE)
                        window["temp_value"].update('%.2f' % imu_msg.temperature_c
                                                   if hasattr(imu_msg, "temperature_c") else MONITOR_DEFAULT_VALUE)
                        window["imu_cpu_time"].update('%.2f' % imu_msg.imu_time_ms
                                                    if hasattr(imu_msg, "imu_time_ms") else MONITOR_DEFAULT_VALUE)
                        window["imu_sync_time"].update('%.2f' % imu_msg.sync_time_ms
                                                    if hasattr(imu_msg, "sync_time_ms") else MONITOR_DEFAULT_VALUE)

    # tell them to get bootloader exe and hex, give upgrade instructions. Will not do this automatically yet.
    # prompt to activate boot loader mode
    def upgrade(self):
        print("\nFirmware upgrade process")
        print("\nNotes:")
        print("\tGet the firmware file from ANELLO Photonics: X3_v<version number>.hex")
        print("\tSoftware update is over USB only, not ethernet.")
        print("\tSupports Windows and Linux OS.")

        if not (self.board and self.connection_info["type"] == "COM"):
            show_and_pause("\nMust connect by USB before upgrading (not over ethernet)")
            return

        # check OS bootloader compatible before starting, prevent update if no valid bootloader.
        bootloader_name = os.path.join(BOARD_TOOLS_DIR, self.board.find_bootloader_name())
        if bootloader_name is None:
            return

        print("\nSelect the firmware file")
        hex_files_only_option = [("hex files", ".hex")]  # only allows picking .hex file.
        hex_file_path = pick_one_file(initialdir=None,
                                      title="Select hex file to load: X3_<version>.hex",
                                      filetypes=hex_files_only_option)
        if not hex_file_path: #on cancel, askopenfilename returns ""
            show_and_pause("\nfile not selected")
            return  # cancel the upgrade. TODO - should it open file picker again?
        hex_file_location, hex_file_name = os.path.split(hex_file_path) #or use os.path.basename, dirname

        print(f"\nSelected {hex_file_name}. Upgrade now?")
        options = ["Yes", "No"]
        if options[cutie.select(options)] == "Yes":
            self.release_for_bootload() #release data port and stop functions that use it like logging, ntrip
            try:
                expect_version_after = "unknown"  # this means it won't check expected version
                self.board.bootload_with_file_path(bootloader_name, hex_file_path, expect_version_after, num_attempts=1)
            except Exception as e:
                print(f"\nError during firmware upgrade: {type(e)}: {e}\n")
                traceback.print_exc()
                show_and_pause("\nTry cycling power on unit and connect again. If it doesn't start up, contact ANELLO Photonics")
                return #should it try to connect here?

            show_and_pause(f"\n\nFinished updating")
            self.connect()  # go back to connect step since it disconnects during bootload.

        else:
            return

    # send regular reset, not bootloading reset
    def reset(self):
        if not self.board:
            show_and_pause("must connect to unit before resetting")
            return

        # serial connection needs to use new bauds if they changed.
        new_control_baud = self.board.get_control_baud_flash()
        new_data_baud = self.board.get_data_baud_flash()
        print("\nrestarting")
        self.board.reset_with_waits(new_control_baud, new_data_baud)

        # tell ioloop to use the new data port baud
        self.data_port_baud.value = new_data_baud
        self.con_start.value = 1
        while self.con_succeed.value == 0:
            time.sleep(0.1)
        data_success = (self.con_succeed.value == 1)  # 0 waiting, 1 succeed, 2 fail
        self.con_succeed.value = 0

    def plot(self):
        show_and_pause("Not implemented yet")

    # retry command on error responses (APERR type)
    # retry only on error codes from connection issues: no start, incomplete, checksum fail
    # don't retry on invalid field, invalid value which could happen from bad user input
    # method: the function to call. args: list of arguments
    def retry_command(self, method, response_types, args=[], retries=6):
        connection_errors = [1, 3, 4]
        for i in range(retries):
            try:
                output_msg = method(*args)
                # no response: retry
                if not output_msg:
                    continue
                # connection errors: retry. content errors like invalid fields/values don't retry
                if output_msg.msgtype == b'ERR' and output_msg.msgtype in connection_errors:
                    continue
                # invalid response message or unexpected response type: retry
                if not proper_response(output_msg, response_types):
                    continue
                else:
                    # clear possible old response if there were any retries
                    if i > 0:
                        clear_old_response = self.board.read_one_control_message()
                    return output_msg
            except Exception as e:
                continue  # error - treat as fail, retry
        # if it failed after retries, there is a connection problem
        if DEBUG:
            print(f"error in function {method.__name__}, types={response_types}, args = {args}")
        clear_old_response = self.board.read_one_control_message()
        return None  # didn't work -> function that calls this should check for None


#try setting expandable for a pysimplegui object - needs updated pysimplegui
def try_set_expand(gui_object, x=True, y=True):
    try:
        gui_object.expand_x = x
        gui_object.expand_y = y
    except Exception as e: #will happen on old PySimpleGUI that doesn't support expand, or wrong object type
        print(f"error setting expand on {gui_object}: {e}")


def version_greater_or_equal(our_ver, compareto):

    # chop any letters from front of our_ver, so we can compare by number
    for i in range(len(our_ver)):
        if our_ver[0].isalpha():
            our_ver = our_ver[1:]
        else:
            break

    try:
        our_nums = [int(c) for c in our_ver.split(".")]
        other_nums = [int(c) for c in compareto.split(".")]
    except Exception:
        return False #default False which will usually mean feature does not exist
    #compare from most important -> least important digit
    for i in range(3):
        if our_nums[i] > other_nums[i]:
            return True
        elif our_nums[i] < other_nums[i]:
            return False
    return True #equal

#try parsing a message by multiple parsers, return result of whichever worked (valid)
def try_multiple_parsers(parser_list, raw_data):
    for parser in parser_list:
        message = parser.parse_message(raw_data)
        #print(f"\n{type(parser)} parses: {message}")
        if message.valid:
            return message
    return None #fail, no parsers worked


# pause on messages if it will refresh after
def show_and_pause(text): #UserProgram
    print(text)
    print("enter to continue:")
    input()


def clear_screen(): #UserProgram
    if not DEBUG:
        if os.name == 'nt':  # Windows
            os.system('cls')
        elif os.name == 'posix':  # Linux, Mac
            os.system('clear')
        else:
            # the only other os.name is 'java' - not sure what OS has that.
            pass


# one string of the date and time
def date_time(): #UserProgram
    return time.ctime()
    # could also make it from parts:
    # time_parts = time.localtime()
    # year = time_parts.tm_year
    # month = time_parts.tm_mon
    # and tm_hour, tm_min, tm_sec, tm_wday, tm_mday, tm_yday
    # or time.strftime(format[,t])


def proper_response(message, expected_types): #UserProgram
    if not message:
        return False
    if not message.valid:  # actual problem with the message format or checksum fail, don't expect this
        return False
    elif message.msgtype in expected_types:
        return True
    elif message.msgtype == b'ERR':  # Error message, like if you sent a bad request
        print("\nError: " + ERROR_CODES[message.err])
        return False
    else:
        print('\nUnexpected response type: '+message.msgtype.decode())
        return False


# prompt to form aln config from 3 angles into one string
# TODO - check what angle range to allow for these
def form_aln_string_prompt():
    roll_angle = cutie.get_number(prompt="roll adjustment (degrees): ", min_value=-360, max_value=360, allow_float=True)
    pitch_angle = cutie.get_number(prompt="pitch adjustment (degrees): ", min_value=-360, max_value=360, allow_float=True)
    heading_angle = cutie.get_number(prompt="heading adjustment (degrees): ", min_value=-360, max_value=360, allow_float=True)
    return f"{roll_angle:+.6f}{pitch_angle:+.6f}{heading_angle:+.6f}"

def alternating_color_table(layout_grid):
    new_layout = []
    for i, row_list in enumerate(layout_grid):
        row_frame = sg.Frame("", [row_list], border_width=0)
        # alternating rows: recolor frame and contents background
        if (i % 2) == 1:
            row_frame.BackgroundColor = table_color_2
            for elem in row_list:
                if hasattr(elem, "BackgroundColor"):
                    elem.BackgroundColor = table_color_2
        new_layout.append([row_frame])
    return new_layout

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
    prog = UserProgram(exitflag, con_on, con_start, con_stop, con_succeed,
                       con_type, com_port, data_port_baud, control_port_baud, udp_ip, udp_port, gps_received,
                       log_on, log_start, log_stop, log_name,
                       ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                       ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                       last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg,  # ignore AHRS for x3
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
                   last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg,last_ahrs_msg, last_imu_time,
                   serial_number,               
    )
    io_process = Process(target=io_loop, args=shared_args)
    io_process.start()
    runUserProg(*shared_args) # must do this in main thread so it can take inputs
    io_process.join()

