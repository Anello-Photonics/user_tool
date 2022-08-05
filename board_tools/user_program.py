import cutie
import os
import time
import sys
import pathlib
import json
import subprocess
import serial
from multiprocessing import Array, Value, Process, Manager
import base64
import socket
import select
from user_program_config import *
from ioloop import *
import PySimpleGUI as sg
from convertLog import export_logs# TODO - put under src directory?

parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src')
from tools import *


#interface for A1 configuration and logging
class UserProgram:

    #(data_connection, logging_on, log_name, log_file, ntrip_on, ntrip_reader, ntrip_request, ntrip_ip, ntrip_port)
    def __init__(self, exitflag, con_on, con_start, con_stop, con_succeed,
                 con_type, com_port, com_baud, udp_ip, udp_port, gps_received,
                 log_on, log_start, log_stop, log_name,
                 ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                 ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                 last_ins_msg, last_gps_msg, last_imu_msg):
        self.connection_info = None
        self.board = None
        self.serialnum = ""
        self.version = ""
        self.pid = ""

        #keep the shared vars as class attributes so other UserProgram methods have them.
        #set them like self.log_name.value = x so change is shared. not self.log_name = x
        self.exitflag, self.con_on, self.con_start, self.con_stop, self.con_succeed = exitflag, con_on, con_start, con_stop, con_succeed
        self.con_type, self.com_port, self.com_baud, self.udp_ip, self.udp_port, self.gps_received =\
            con_type, com_port, com_baud, udp_ip, udp_port, gps_received
        self.log_on, self.log_start, self.log_stop, self.log_name = log_on, log_start, log_stop, log_name
        self.ntrip_on, self.ntrip_start, self.ntrip_stop, self.ntrip_succeed = ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed
        self.ntrip_ip, self.ntrip_port, self.ntrip_gga, self.ntrip_req = ntrip_ip, ntrip_port, ntrip_gga, ntrip_req
        self.last_ins_msg, self.last_gps_msg, self.last_imu_msg = last_ins_msg, last_gps_msg, last_imu_msg

        #any features which might or not be there - do based on firmware version?
        self.has_odo_port = False

    def mainloop(self):
        while True:
            try:
                clear_screen()
                self.show_info()
                print("\nSelect One:")
                action = MENU_OPTIONS[cutie.select(MENU_OPTIONS)]
                if action == "Connect":
                    self.connect()
                elif action == "Unit Configuration":
                    self.configure()
                elif action == "Vehicle Configuration":
                    self.vehicle_configure()
                elif action == "Log":
                    self.log()
                elif action == "Monitor":
                    self.monitor()
                elif action == "NTRIP":
                    self.ntrip_menu()
                elif action == "Upgrade":
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

    # if we clear after every action, refresh does nothing extra
    def refresh(self):
        pass

    def show_info(self):
        print("\nAnello Python Program " + date_time())
        print("\nSystem Status:")
        self.show_device()
        self.show_connection()
        self.show_ntrip()
        self.show_logging()

    def show_device(self):
        if self.con_on.value and self.connection_info:
            print("Device: "+self.pid+": "+self.serialnum+", firmware version "+self.version)

    def show_connection(self):
        con = self.connection_info
        if con and self.con_on.value:
            # example is "A-1:SN is Connected on COM57"  - connect and get serial number?
            output = "Connection: "+con["type"]+": "
            if con["type"] == "COM":
                output += "configuration port = "+con["control port"]+", data port = "+con["data port"]
            elif con["type"] == "UDP":
                output += "ip = "+con["ip"]+", data port = "+con["port1"]+", configuration port = "+con["port2"]
            print(output)
        else:
            print("Connection: Not connected")

    def show_ntrip(self):
        if self.ntrip_on.value:  #and ntrip_target:
            ip = self.ntrip_ip.value.decode()
            port = self.ntrip_port.value
            status = "NTRIP: Connected to "+ip+":"+str(port)
        else:
            status = "NTRIP: Not connected"
        print(status)

    def show_logging(self):
        if self.log_on.value:
            # TODO - count messages logged: either read file (if safe while writing) or communicate with process
            print("Log: Logging to "+self.log_name.value.decode()) #+" ("+str(num_messages)+" messages logged )")
        else:
            print("Log: Not logging")

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
        options = ["Auto", "Manual", "cancel"]
        selected = options[cutie.select(options)]
        if selected == "Auto":
            self.release()
            board = IMUBoard.auto(set_data_port=True)
        elif selected == "Manual":
            self.release()
            board = IMUBoard()
            board.connect_manually(set_data_port=True)
        else:  # cancel
            return
        self.board = board
        data_port_name = board.data_port_name
        board.data_connection.close()

        self.serialnum = self.retry_command(method=board.get_serial, response_types=[b'SER']).ser.decode()
        self.version = self.retry_command(method=board.get_version, response_types=[b'VER']).ver.decode()
        self.pid = self.retry_command(method=board.get_pid, response_types=[b'PID']).pid.decode()

        #let io_thread do the data connection - give it the signal, close this copy
        self.com_port.value, self.com_baud.value = data_port_name.encode(), board.baud
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
        #data_connection = UDPConnection(remote_ip=A1_ip, remote_port=UDP_LOCAL_DATA_PORT, local_port=data_port)
        control_connection = UDPConnection(remote_ip=A1_ip, remote_port=UDP_LOCAL_CONFIG_PORT, local_port=config_port)
        board = IMUBoard()
        board.release_connections()
        board.control_connection = control_connection
        #board.data_connection = data_connection
        self.board = board
        #data_connection = board.data_connection
        self.serialnum = self.retry_command(method=board.get_serial, response_types=[b'SER']).ser.decode()  # this works like a ping - error or timeout if bad connection
        self.version = self.retry_command(method=board.get_version, response_types=[b'VER']).ver.decode()
        self.pid = self.retry_command(method=board.get_pid, response_types=[b'PID']).pid.decode()
        if selected == "Manual":
            save_udp_settings(A1_ip, data_port, config_port)

        #send udp start info to io thread:
        self.udp_ip.value, self.udp_port.value = A1_ip.encode(), data_port
        self.con_type.value = b"UDP"
        self.con_on.value = 1
        self.con_start.value = 1
        return {"type": "UDP", "ip": A1_ip, "port1": str(data_port), "port2": str(config_port)}

    def configure(self):
        if not self.board:
            show_and_pause("Must connect before configuring")
            return
        clear_screen()
        self.read_all_configs(self.board)  # show configs automatically
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
        # hide udp settings if connected by udp. otherwise you can break the connection. or should we allow it?
        #skip_indices = UDP_FIELD_INDICES if self.connection_info["type"] == "UDP" else []

        #check if it has odometer port or not, then show/hide in options
        field_names = CFG_FIELD_NAMES[:]
        field_codes = CFG_FIELD_CODES[:]
        if not self.has_odo_port:
            ind = field_codes.index('rport3')
            field_names.pop(ind)
            field_codes.pop(ind)

        options = field_names + ["cancel"]
        selected_index = cutie.select(options)
        if options[selected_index] == "cancel":
            return
        args = {}
        name, code = field_names[selected_index], field_codes[selected_index]

        if code == "orn": # special case: choose between two common options or choose to enter it
            value = self.select_orientation()
        elif code in CFG_VALUE_OPTIONS:
            print("\nselect " + name)
            options = CFG_VALUE_OPTIONS[code]
            value = str(options[cutie.select(options)]).encode()
        else:
            print("\nenter value for " + name + " " + CFG_FIELD_EXAMPLES[code])
            value = input().encode()
        args[code] = value

        #if connected by udp, changing udp settings can disconnect - give warning
        if code in UDP_FIELDS and self.connection_info["type"] == "UDP":
            change_anyway = cutie.prompt_yes_or_no("Changing UDP settings while connected by UDP may close the connection. Change anyway?")
            if not change_anyway:
                return

        #if setting odometer unit, first set odometer to on, then set the unit
        if code == "odo":
            args2 = {"odo": b'on'}
            resp = self.retry_command(method=self.board.set_cfg_flash, args=[args2], response_types=[b'CFG', b'ERR'])

        resp = self.retry_command(method=self.board.set_cfg_flash, args=[args], response_types=[b'CFG', b'ERR'])
        if not proper_response(resp, b'CFG'):
            show_and_pause("") # proper_response already shows error, just pause to see it.

    def select_orientation(self):
        #use the orientation selector depending on version
        if version_greater_or_equal(self.version, '0.3.4'):
            return self.select_orn_8_opts()
        return self.select_orn_24_opts()

    #firmware before 0.3.4: 24 options - just show the 2 typical ones and allow entering others
    def select_orn_24_opts(self):
        print("\nselect ORIENTATION:")
        options = CFG_VALUE_OPTIONS["orn"]
        chosen = options[cutie.select(options)]
        if "+X+Y+Z" in chosen:
            return b'+X+Y+Z'
        elif "+Y+X-Z" in chosen:
            return b'+Y+X-Z'
        else:  # select it yourself
            print("\nenter value for orientation "+ CFG_FIELD_EXAMPLES["orn"])
            return input().encode()

    #firmware 0.3.4 or later: 8 orientations: must end in +-Z -> show all 8
    def select_orn_8_opts(self):
        print("\nselect ORIENTATION:")
        options = ORN_8_OPTIONS
        chosen = options[cutie.select(options)]
        #allow notes like (north east up) in the name
        if "+X+Y+Z" in chosen:
            return b'+X+Y+Z'
        elif "+Y+X-Z" in chosen:
            return b'+Y+X-Z'
        else:
            #if no note, the value is correct
            return chosen.encode()

    # read all configurations.
    def read_all_configs(self, board):
        resp = self.retry_command(method=board.get_cfg, args=[[]], response_types=[b'CFG'])
        #if proper_response(resp, b'CFG'):
        self.has_odo_port = ('rport3' in resp.configurations)
        print("Unit Configurations:")
        for name in resp.configurations:
            if name in CFG_FIELD_CODES:
                full_name = CFG_FIELD_NAMES[CFG_FIELD_CODES.index(name)]
                print("\t" + full_name + ":\t" + resp.configurations[name].decode())

    # Vehicle Configs: same pattern as user configs
    def vehicle_configure(self):
        if not self.board:
            show_and_pause("Must connect before configuring")
            return
        clear_screen()
        if self.read_all_veh(self.board):  # show configs automatically
            #check connection again since error can be caught in read_all_configs
            if not self.con_on.value:
                return
            #print("configure:")
            actions = ["Edit", "Done"]
            selected_action = actions[cutie.select(actions)]
            if selected_action == "Edit":
                self.set_veh()
                self.vehicle_configure()  # recursion to view/edit again until picking "done".
            else:
                return
        else:
            show_and_pause("not available - requires firmware upgrade")

    #new version to set one 3-vector at a time
    def set_veh(self):
        print("\nselect configurations to write\n")
        field_names = VEH_FIELDS.copy()

        #choose which vehicle config
        options = list(VEH_FIELDS.keys()) + ["cancel"]
        chosen = options[cutie.select(options)]
        if chosen == "cancel":
            return

        #enter the components of the chosen config
        print("enter components for: "+chosen)
        args = {} #dict of VEH to write
        codes = VEH_FIELDS[chosen]
        for axis, code in codes:
            value = input(axis+": ").encode() #TODO - show better name like x,y,z?
            args[code] = value

        #send VEH message
        resp = self.retry_command(method=self.board.set_veh_flash, args=[args], response_types=[b'VEH', b'ERR'])
        if not proper_response(resp, b'VEH'):
            show_and_pause("") # proper_response already shows error, just pause to see it.

    # read all configurations. return true on success or false on fail
    def read_all_veh(self, board):
        resp = self.retry_command(method=board.get_veh_flash, args=[[]], response_types=[b'VEH', b'ERR'])
        #retry until VEH (works) or ERR (fail). still retries on split message or checksum errors
        if resp.msgtype == b'VEH': #read success -> print the configs
            # if proper_response(resp, b'VEH'):
            print("Vehicle Configurations:")
            for name in VEH_FIELDS:
                line = "    "+name+": "
                for axis, code in VEH_FIELDS[name]:
                    val_or_blank = "------"
                    if code in resp.configurations:
                        val_or_blank = axis+": "+resp.configurations[code].decode()
                    line += val_or_blank+"    "
                print(line)
            return True
        else:
            return False

    # logging mode:
    # prompt for file name with default suggestion
    # stay in logging mode with indicator of # messages logged updated once/sec
    # also count NTRIP messages if connected
    # stop when esc or q is entered
    def log(self):
        clear_screen()
        self.show_logging()
        actions = ["Export to CSV", "cancel"]
        if self.log_on.value:
            actions = ["Stop"]+actions
        else:
            actions = ["Start"] + actions
        selected_action = actions[cutie.select(actions)]
        if selected_action == "Export to CSV":
            export_logs() #import from convertLog.py
            show_and_pause("finished exporting")
            #TODO - handle export errors here?
        elif selected_action == "Start":
            self.start_logging()
        elif selected_action == "Stop":
            self.stop_logging()
        else:
            return

    def start_logging(self):
        if self.log_on.value:
            show_and_pause("already logging")
            return
        elif not self.board:
            show_and_pause("must connect before logging")
            return
        else:
            suggested = collector.default_log_name(self.serialnum)
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

    def stop_logging(self):
        self.log_on.value = 0
        self.log_stop.value = 1 #send stop signal to other thread which will close the log

    def ntrip_menu(self):
        if self.connection_info: # and self.connection_info["type"] == "UDP":
            #before A1 fw ver 0.4.3, ntrip is over udp only
            if self.connection_info["type"] == "UDP" or version_greater_or_equal(self.version, "0.4.3"):
                clear_screen()
                self.show_ntrip()
                options = ["cancel"]
                if self.ntrip_on.value:
                    options = ["Stop"] + options
                else:
                    options = ["Start"] + options
                selected = options[cutie.select(options)]
                if selected == "Start":
                    self.start_ntrip()
                elif selected == "Stop":
                    self.stop_ntrip()
                else: #cancel
                    return
            else:
                show_and_pause("must connect by UDP to use NTRIP")
                return
        else:
            show_and_pause("must connect before starting NTRIP")
            return

    #NTRIP has Server and Port
    def start_ntrip(self):
        success = False
        clear_screen()
        while not success:
            print("Select NTRIP:")
            ntrip_settings = load_ntrip_settings()
            options = ["Manual", "cancel"]
            captions = []

            if ntrip_settings:
                #saved_string = "Saved: " + str(ntrip_settings)
                captions = range(1, 1+len(ntrip_settings))
                saved_vals = ["\t"+str(k)+": "+str(ntrip_settings[k]) for k in ntrip_settings]
                options = ["Saved: "] + saved_vals + options
            selected = options[cutie.select(options, caption_indices=captions)]
            if selected == "cancel":
                return
            elif selected == "Manual":
                caster = input("caster:")
                port = int(cutie.get_number("port:"))
                mountpoint = input("mountpoint:")
                username = input("username:")
                password = input("password:")
                send_gga = cutie.prompt_yes_or_no("send gga? (requires gps connection)") #TODO - do regular cutie select so style doesn't change?
                ntrip_settings = {"caster": caster, "port": port, "mountpoint": mountpoint, "username": username,
                                  "password": password, "gga": send_gga}
                save_ntrip_settings(ntrip_settings) # TODO - save later on after confirming it works?
            else: #Saved
                #TODO - if any of these missing, can't load from save - check first and hide saved option?
                caster = ntrip_settings["caster"]
                port = ntrip_settings["port"]
                mountpoint = ntrip_settings["mountpoint"]
                username = ntrip_settings["username"]
                password = ntrip_settings["password"]
                send_gga = ntrip_settings["gga"]

            port = int(port)
            mountpoint = mountpoint.encode()
            #ntrip_target = (caster, port)
            self.ntrip_ip.value = caster.encode()
            self.ntrip_port.value = port
            self.ntrip_gga.value = send_gga # seems to convert True/False to 1/0

            # _______NTRIP Connection Configs_______
            userAgent = b'NTRIP Anello Client'
            ntrip_version = 1
            ntrip_auth = "Basic" #TODO - add more options for these

            if ntrip_version == 1 and ntrip_auth == "Basic":
                auth_str = username + ":" + password
                auth_64 = base64.b64encode(auth_str.encode("ascii"))
                self.ntrip_req.value = b'GET /' + mountpoint + b' HTTP/1.0\r\nUser-Agent: ' + userAgent + b'\r\nAuthorization: Basic ' + auth_64 + b'\r\n\r\n'
            else:
                # TODO make request structure for NTRIP v2, other auth options.
                print("not implemented: version = " + str(ntrip_version) + ", auth = " + str(ntrip_auth))
                self.ntrip_req.value=b'' # will work as False for conditions
            #signal io_thread to connect the ntrip.
            clear_screen()
            self.ntrip_on.value = 1
            self.ntrip_start.value = 1
            #wait for success or fail message
            while self.ntrip_succeed.value == 0:
                continue
                # should it time out eventually?
            success = (self.ntrip_succeed.value == 1) # 0 waiting, 1 succeed, 2 fail
            self.ntrip_succeed.value = 0
            debug_print(success)

    #set flags and iothread will close ntrip connection
    def stop_ntrip(self):
        self.ntrip_on.value = 0
        self.ntrip_stop.value = 1

    def monitor(self):
        if not self.board:
            show_and_pause("connect before monitoring")
            return

        #main window freezes until monitor closes - explain that.
        clear_screen()
        print("\nMonitoring in other window. Close it to continue.")

        ascii_scheme = ReadableScheme()
        sg.theme(SGTHEME)

        label_font = (FONT_NAME, LABEL_FONT_SIZE)
        value_font = (FONT_NAME, VALUE_FONT_SIZE)

        #GPS and Log toggles
        gps_is_on = False
        gps_working = False
        resp = self.retry_command(method=self.board.get_cfg, args=[["gps1"]], response_types=[b'CFG'])
        if hasattr(resp, "configurations"):
            gps_is_on = resp.configurations["gps1"] == b'on'
            gps_working = True
            gps_button = sg.Button(GPS_TEXT+TOGGLE_TEXT[gps_is_on], key="gps_button", enable_events=True,
                                   font=value_font, button_color=TOGGLE_COLORS[gps_is_on])
        else:
            gps_button = sg.Button(GPS_TEXT + "disabled", key="gps_button", enable_events=False,
                                   font=value_font, button_color=BUTTON_DISABLE_COLOR)
        log_button = sg.Button(LOG_TEXT+TOGGLE_TEXT[self.log_on.value], key="log_button",  enable_events=True,
                               font = value_font, button_color=TOGGLE_COLORS[self.log_on.value])

        time_since_gps_label = sg.Text("Last GPS (s): ", size=MONITOR_TIMELABEL_SIZE, font=label_font)
        time_since_gps = sg.Text(MONITOR_DEFAULT_VALUE, key="since_gps", size=MONITOR_TIME_SIZE, font=label_font)
        time_since_ins_label = sg.Text("Last INS (s): ", size=MONITOR_TIMELABEL_SIZE, font=label_font)
        time_since_ins = sg.Text(MONITOR_DEFAULT_VALUE, key="since_ins", size=MONITOR_TIME_SIZE, font=label_font)
        anello_logo = sg.Image('anello_scaled.png', size=(300,80))

        #put rtk status in top row
        gps_carrsoln_label = sg.Text("Carrier Soln: ", size=MONITOR_LABEL_SIZE, font=label_font)
        gps_carrsoln = sg.Text(MONITOR_DEFAULT_VALUE, key="gps_carrsoln", size=MONITOR_VALUE_SIZE, font=value_font)
        gps_fix_label = sg.Text("GPS Fix: ", size=MONITOR_LABEL_SIZE, font=label_font)
        gps_fix = sg.Text(MONITOR_DEFAULT_VALUE, key="gps_fix", size=MONITOR_VALUE_SIZE, font=value_font)
        # carrier solution vs fix type - need both? put both for now.

        gps_fix_row = [gps_carrsoln_label, gps_carrsoln, gps_fix_label, gps_fix]

        #ins data: lat, lon, vx, vy, attitude x,y,z
        lat = sg.Text(MONITOR_DEFAULT_VALUE, key="lat", size=MONITOR_VALUE_SIZE, font=value_font)
        lon = sg.Text(MONITOR_DEFAULT_VALUE, key="lon", size=MONITOR_VALUE_SIZE, font=value_font)
        speed = sg.Text(MONITOR_DEFAULT_VALUE, key="speed", size=MONITOR_VALUE_SIZE, font=value_font)
        # vx = sg.Text(MONITOR_DEFAULT_VALUE, key="vx", size=MONITOR_VALUE_SIZE, font=value_font)
        # vy = sg.Text(MONITOR_DEFAULT_VALUE, key="vy", size=MONITOR_VALUE_SIZE, font=value_font)
        att0 = sg.Text(MONITOR_DEFAULT_VALUE, key="att0", size=MONITOR_VALUE_SIZE, font=value_font)
        att1 = sg.Text(MONITOR_DEFAULT_VALUE, key="att1", size=MONITOR_VALUE_SIZE, font=value_font)
        att2 = sg.Text(MONITOR_DEFAULT_VALUE, key="att2", size=MONITOR_VALUE_SIZE, font=value_font)
        soln = sg.Text(MONITOR_DEFAULT_VALUE, key="soln", size=MONITOR_VALUE_SIZE, font=value_font)
        zupt = sg.Text(MONITOR_DEFAULT_VALUE, key="zupt", size=MONITOR_VALUE_SIZE, font=value_font)

        lat_label = sg.Text("Lat. (deg):", size=MONITOR_LABEL_SIZE, font=label_font)
        lon_label = sg.Text("Lon. (deg):", size=MONITOR_LABEL_SIZE, font=label_font)
        speed_label = sg.Text("Speed (m/s):", size=MONITOR_LABEL_SIZE, font=label_font)
        #vx_label = sg.Text("velocity x:", size=MONITOR_LABEL_SIZE, font=label_font)
        #vy_label = sg.Text("velocity y:", size=MONITOR_LABEL_SIZE, font=label_font)
        att0_label = sg.Text("Roll (deg):", size=MONITOR_LABEL_SIZE, font=label_font)
        att1_label = sg.Text("Pitch (deg):", size=MONITOR_LABEL_SIZE, font=label_font)
        att2_label = sg.Text("Heading (deg):", size=MONITOR_LABEL_SIZE, font=label_font)
        soln_label = sg.Text("Solution:", size=MONITOR_LABEL_SIZE, font=label_font)
        zupt_label = sg.Text("State:", size=MONITOR_LABEL_SIZE, font=label_font)

        buttons_row = [gps_button, log_button, time_since_gps_label, time_since_gps, anello_logo]
        latlon_row = [lat_label, lat, lon_label, lon]
        velocity_row = [speed_label, speed, att2_label, att2]
        att_row = [att0_label, att0, att1_label, att1]
        flags_row = [soln_label, soln, zupt_label, zupt]
        layout = [buttons_row, [sg.HSeparator()], latlon_row, velocity_row, att_row, flags_row, gps_fix_row]

        #group elements by size for resizing
        label_font_elements = [lat_label, lon_label, speed_label, att0_label, att1_label, att2_label,
                               soln_label, zupt_label, gps_carrsoln_label, gps_fix_label]
        value_font_elements = [lat, lon, speed, att0, att1, att2, soln, zupt, gps_carrsoln, gps_fix]
        buttons = [gps_button, log_button]
        # layout = [gps_row, log_row, ['---'], latlon_row, velocity_row, att_row, flags_row]

        window = sg.Window(title="Output monitoring", layout=layout, finalize=True, resizable=True)
        window.bind('<Configure>', "Configure")
        base_width, base_height = window.size
        debug_print("BASE_WIDTH: "+str(base_width))
        debug_print("BASE_HEIGHT:" +str(base_height))

        last_last_ins = b''
        last_last_gps = b''
        last_ins_time = time.time()
        last_gps_time = last_ins_time

        ins_fields = [lat, lon, speed, att0, att1, att2, soln, zupt]
        gps_fields = [gps_carrsoln, gps_fix]

        while True:
            # check for new messages and update the displayed data

            if last_ins_msg.value:
                elapsed = time.time() - last_ins_time
                # window["since_ins"].update('%.2f' % elapsed)
                if last_ins_msg.value == last_last_ins:
                    #did not change - no update. but if it's been too long, zero the fields
                    #time_since_ins.update(str(elapsed))
                    #window.refresh()
                    if elapsed > ZERO_OUT_TIME:
                        for field in ins_fields:
                            field.update(MONITOR_DEFAULT_VALUE)
                else: #changed - update the last_ins and counter, then update display from the new values
                    last_last_ins = last_ins_msg.value
                    last_ins_time = time.time()

                    ins_msg = ascii_scheme.parse_message(last_ins_msg.value)
                    # debug_print(msg)
                    # for label, attrname in configs:
                    # textval = str(getattr(msg, attrname) if hasattr(msg, attrname) else default_value
                    # window[label].update(textval)
                    window["lat"].update(str(ins_msg.lat_deg) if hasattr(ins_msg, "lat_deg") else MONITOR_DEFAULT_VALUE)
                    window["lon"].update(str(ins_msg.lon_deg) if hasattr(ins_msg, "lon_deg") else MONITOR_DEFAULT_VALUE)

                    #compute ins speed as magnitude. include vz? should be small anyway
                    vx = float(ins_msg.velocity_0_mps) if hasattr(ins_msg, "velocity_0_mps") else 0
                    vy = float(ins_msg.velocity_1_mps) if hasattr(ins_msg, "velocity_1_mps") else 0
                    vz = float(ins_msg.velocity_2_mps) if hasattr(ins_msg, "velocity_2_mps") else 0
                    magnitude = ((vx**2)+(vy**2)+(vz**2))**(1/2)
                    # print("vx: " + str(vx))
                    # print("vy: " + str(vy))
                    # print("vz: " + str(vz))
                    # print("speed: "+str(magnitude))
                    window["speed"].update('%.3f'%magnitude)
                    window["att0"].update(
                        '%.2f'%ins_msg.attitude_0_deg if hasattr(ins_msg, "attitude_0_deg") else MONITOR_DEFAULT_VALUE)
                    window["att1"].update(
                        '%.2f'%ins_msg.attitude_1_deg if hasattr(ins_msg, "attitude_1_deg") else MONITOR_DEFAULT_VALUE)
                    window["att2"].update(
                        '%.2f'%ins_msg.attitude_2_deg if hasattr(ins_msg, "attitude_2_deg") else MONITOR_DEFAULT_VALUE)
                    window["soln"].update(
                        INS_SOLN_NAMES[ins_msg.ins_solution_status] if hasattr(ins_msg, "ins_solution_status") else MONITOR_DEFAULT_VALUE)
                    window["zupt"].update(ZUPT_NAMES[ins_msg.zupt_flag] if hasattr(ins_msg, "zupt_flag") else MONITOR_DEFAULT_VALUE)
                # window.refresh()
            if last_gps_msg.value:
                elapsed = time.time() - last_gps_time
                window["since_gps"].update('%.2f' % elapsed)
                if last_gps_msg.value == last_last_gps:
                    #did not change - no update. but if it's been too long, zero the fields
                    # time_since_gps.update(str(elapsed))
                    # window.refresh()
                    if elapsed > ZERO_OUT_TIME:
                        for field in gps_fields:
                            field.update(MONITOR_DEFAULT_VALUE)
                else:
                    last_last_gps = last_gps_msg.value
                    last_gps_time = time.time()
                    gps_msg = ascii_scheme.parse_message(last_gps_msg.value)
                    window["gps_carrsoln"].update(GPS_SOLN_NAMES[gps_msg.carrier_solution_status] if hasattr(gps_msg, "carrier_solution_status") else MONITOR_DEFAULT_VALUE)
                    window["gps_fix"].update(GPS_FIX_NAMES[gps_msg.gnss_fix_type] if hasattr(gps_msg, "gnss_fix_type") else MONITOR_DEFAULT_VALUE)

            # handle events from this side: gps toggle or close.
            # if counter == 0:
            event, values = window.read(timeout=MONITOR_REFRESH_MS, timeout_key="timeout")
            if event != "timeout":
                debug_print("event: " + str(event))
                debug_print("values: " + str(values))
            if event == sg.WIN_CLOSED:  # close - return to wait_for_monitor_start
                window.close() #needs this to close properly on raspberry pi. not needed in windows.
                break
            elif event == "gps_button" and gps_working:
                #switch to opposite state
                if gps_is_on:
                    configs = {'gps1': b'off', 'gps2': b'off'}
                else:
                    configs = {'gps1': b'on', 'gps2': b'on'}
                write_resp = self.retry_command(method=self.board.set_cfg, args=[configs], response_types=[b'CFG']) #toggle gps in RAM only
                #read again to update button in case of failure
                read_resp = self.retry_command(method=self.board.get_cfg, args=[["gps1"]], response_types=[b'CFG'])
                gps_is_on = read_resp.configurations["gps1"] == b'on'
                gps_button.update(GPS_TEXT+TOGGLE_TEXT[gps_is_on], button_color=TOGGLE_COLORS[gps_is_on])
            elif event == "log_button":
                #stop if on, start if off
                if self.log_on.value:
                    self.stop_logging()
                else:
                    #start log with default name
                    logname = collector.default_log_name(self.serialnum)
                    self.log_name.value = logname.encode()
                    self.log_on.value = 1
                    self.log_start.value = 1
                #update color
                log_button.update(LOG_TEXT+TOGGLE_TEXT[self.log_on.value], button_color=TOGGLE_COLORS[self.log_on.value])
            elif event == "Configure": #resize, move. also triggers on button for some reason.
                debug_print("size:")
                debug_print(repr(window.size))
                width, height = window.size
                scale = min(width / base_width , height / base_height)
                for item in value_font_elements:
                    item.update(font=(FONT_NAME, int(VALUE_FONT_SIZE * scale)))
                for item in label_font_elements:
                    item.update(font=(FONT_NAME, int(LABEL_FONT_SIZE * scale)))
                for item in buttons:
                    item.font = (FONT_NAME, int(LABEL_FONT_SIZE * scale))
                #zupt.update(font = (FONT_NAME, int(VALUE_FONT_SIZE * scale)))

    # tell them to get bootloader exe and hex, give upgrade instructions. Will not do this automatically yet.
    # prompt to activate boot loader mode
    def upgrade(self):

        # TODO - make a user_program_config file with these strings?
        print("\nSoftware upgrade steps:")
        print("download our boot loader executable and update hex file.") #TODO say where to get them
        print("Turn on upgrade mode here. The A1 will pause until upgrade complete or power is cycled.")
        print("Run the bootloader commands in terminal:")
        print("\tHtxAurixBootLoader START TC36X 6 <data port number> 115200 0 0 0 0")
        print("\tHtxAurixBootLoader PROGRAMVERIFY <hex file name> 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF0000 0x0")
        print("\tHtxAurixBootLoader END")
        print("For example on Windows, if the A1 uses ports COM3 through COM6, enter \"3\" for the data port number.")

        if self.board and self.connection_info["type"] == "COM":
            print("\nenter upgrade mode now? A1 will pause until bootloader executable runs or power is cycled.")
            options = ["Yes", "No"]
            selected = options[cutie.select(options)]
            if selected == "Yes":
                self.board.enter_bootloading()
                self.release()
                show_and_pause("Entered upgrade mode. Run bootloader and then reconnect.")
        else:
            show_and_pause("\nMust connect by COM port before entering upgrade mode")

    # send regular reset, not bootloading reset
    def reset(self):
        if self.board:
            self.board.send_reset_regular()
            #TODO - does it need to re-connect here or wait for reset to complete?
        else:
            show_and_pause("must connect to unit before resetting")

    def plot(self):
        show_and_pause("Not implemented yet")

    # retry command on error responses (APERR type)
    # retry only on error codes from connection issues: no start, incomplete, checksum fail
    # don't retry on invalid field, invalid value which could happen from bad user input
    # method: the function to call. args: list of arguments
    def retry_command(self, method, response_types, args=[], retries=6):
        connection_errors = [1, 3, 4]
        #may need to clear input buffer here so some old message isn't read as a response.
        self.board.control_connection.reset_input_buffer() #TODO - make this actually do something for UDP
        for i in range(retries):
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
                return output_msg
        #raise Exception("retry method: " + str(method) + " failed")
        # if it failed after retries, there is a connection problem
        self.release()
        show_and_pause("connection error - check cables and reconnect")


def version_greater_or_equal(our_ver, compareto):
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


# save and load udp settings, like IMUBoard connection cache
# TODO - should udp and com cache both go in IMUBoard? or both in user_program?
def load_udp_settings(): #UserProgram
    try:
        cache_path = os.path.join(os.path.dirname(__file__), UDP_CACHE)
        with open(cache_path, 'r') as settings_file:
            settings = json.load(settings_file)
            return settings["lip"], settings["rport1"], settings["rport2"]
    except Exception as e:
        return None


def save_udp_settings(lip, rport1, rport2): #UserProgram
    try:
        settings = {"lip": lip, "rport1": rport1, "rport2": rport2}
        cache_path = os.path.join(os.path.dirname(__file__), UDP_CACHE)
        with open(cache_path, 'w') as settings_file:
            json.dump(settings, settings_file)
    except Exception as e:
        print("error writing connection settings: "+str(e))
        return None


#not using yet: ntrip_version = 1/2 , ntrip_auth = "Basic"/"Digest"/"None"
def load_ntrip_settings(): #UserProgram
    try:
        cache_path = os.path.join(os.path.dirname(__file__), NTRIP_CACHE)
        with open(cache_path, 'r') as settings_file:
            settings = json.load(settings_file)
            return settings
    except Exception as e:
        return None


def save_ntrip_settings(settings): #UserProgram
    try:
        cache_path = os.path.join(os.path.dirname(__file__), NTRIP_CACHE)
        with open(cache_path, 'w') as settings_file:
            json.dump(settings, settings_file)
    except Exception as e:
        print("error writing ntrip settings: "+str(e))
        return None


#(data_connection, logging_on, log_name, log_file, ntrip_on, ntrip_reader, ntrip_request, ntrip_ip, ntrip_port)
def runUserProg(exitflag, con_on, con_start, con_stop, con_succeed,
                con_type, com_port, com_baud, udp_ip, udp_port, gps_received,
                log_on, log_start, log_stop, log_name,
                ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                last_ins_msg, last_gps_msg, last_imu_msg):
    prog = UserProgram(exitflag, con_on, con_start, con_stop, con_succeed,
                       con_type, com_port, com_baud, udp_ip, udp_port, gps_received,
                       log_on, log_start, log_stop, log_name,
                       ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                       ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                       last_ins_msg, last_gps_msg, last_imu_msg)
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
    com_baud = Value('i', 0) #int
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
    last_imu_msg = Array('c', string_size)

    shared_args = (exitflag, con_on, con_start, con_stop, con_succeed,
                   con_type, com_port, com_baud, udp_ip, udp_port, gps_received,
                   log_on, log_start, log_stop, log_name,
                   ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed, ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                   last_ins_msg, last_gps_msg, last_imu_msg)
    io_process = Process(target=io_loop, args=shared_args)
    io_process.start()
    runUserProg(*shared_args) # must do this in main thread so it can take inputs
    io_process.join()

