import os
import cutie
import json
import subprocess
import os
import re
import serial.tools.list_ports as list_ports
import time
try:  # importing from inside the package
    from readable_scheme import *
    from rtcm_scheme import *
    from message_scheme import Message
    from connection import *
    from class_configs.board_config import *
except ModuleNotFoundError:  # importing from outside the package
    from anello_tools.readable_scheme import *
    from anello_tools.rtcm_scheme import *
    from anello_tools.message_scheme import Message
    from anello_tools.connection import *
    from anello_tools.class_configs.board_config import *

debug = False
COMMANDS_RETRY = 5 #retry limit for commands. mostly matters for USB with lower baud, large commands


def debug_print(text):
    if debug:
        print(text)

# abstraction of the board and its inputs and outputs
class IMUBoard:
    #def __init__(self, data_port=None, control_port=None, baud=DEFAULT_BAUD, data_scheme=RTCM_Scheme(), control_scheme=ReadableScheme(), try_manual=True, timeout=None):
    def __init__(self, data_port=None, control_port=None, baud=DEFAULT_BAUD, data_scheme=ReadableScheme(), control_scheme=ReadableScheme(), try_manual=True, timeout=None):
        self.data_scheme = data_scheme
        self.control_scheme = control_scheme
        self.timeout = timeout
        success = self.connect_to_ports(data_port, control_port, baud)
        if try_manual and not success:
            print("failed to connect with control port = "+str(control_port)+", data port = "+str(data_port)+", baud = "+str(baud))
            self.connect_manually()
        self.msg_format = b'1' #default ascii to make sure this is defined

    def __repr__(self):
        return "IMUBoard: "+str(self.__dict__)

    @classmethod
    def auto(cls, set_data_port=True):
        board = cls()
        try:
            success = True
            control_port, data_port, baud = board.read_connection_settings(set_data_port)
            if not control_port: #or not data_port:
                #print("no control port in cache -> fail")
                success = False
            if not set_data_port:
                data_port = None
            success = success and board.connect_to_ports(data_port, control_port, baud)
        except Exception as e:
            success = False
            #print("connect from cache error: " + str(e))
        if success:
            #print("connection from cache success.")
            board.write_connection_settings(set_data_port)  # should do only on success - from auto or from manual
        else:
            # file not exist, or connecting based on file fails -> detect the settings, then save in a file
            #print("connection from cache failed -> do auto search")
            board.release_connections()
            if board.auto_no_cache(set_data_port): #None on fail
                board.write_connection_settings(set_data_port) #also counts as success -> save.
        return board

    #initialize on udp. TODO - could put cache options here too.
    @classmethod
    def from_udp(cls, ip, data_port, control_port, odometer_port=None):
        board = cls()
        try:
            if data_port:
                board.data_connection = UDPConnection(ip, UDP_LOCAL_DATA_PORT, data_port)
            else:
                board.data_connection = DummyConnection()
            if control_port:
                board.control_connection = UDPConnection(ip, UDP_LOCAL_CONFIG_PORT, control_port)
            else:
                board.control_connection = DummyConnection()
            if odometer_port:
                board.odometer_connection = UDPConnection(ip, UDP_LOCAL_ODOMETER_PORT, odometer_port)
            else:
                board.odometer_connection = None

        except Exception as e:
            print(e)
            return None
        return board

    def read_connection_settings(self, using_data_port):
        try:
            cache_name = CONNECTION_CACHE_WITH_DATA_PORT if using_data_port else CONNECTION_CACHE_NO_DATA_PORT
            cache_path = os.path.join(os.path.dirname(__file__), cache_name)
            #print("reading from "+str(cache_path))
            with open(cache_path, 'r') as settings_file:
                settings = json.load(settings_file)
                control, baud = settings["control_port"], settings["baud"]
                if using_data_port:
                    data = settings["data_port"] #TODO - handle None case here?
                else:
                    data = None
                return control, data, baud
        except Exception as e:
            #print("error reading connection settings: "+str(e))
            return None

    def write_connection_settings(self, using_data_port):
        try:
            cache_name = CONNECTION_CACHE_WITH_DATA_PORT if using_data_port else CONNECTION_CACHE_NO_DATA_PORT
            control, baud = self.control_port_name, self.baud
            # avoid writing null for ports
            if control is None:
                return None
            settings = {"control_port": control, "baud": baud}
            if using_data_port:
                data = self.data_port_name
                # if data is None: #would this happen?
                #     data = self.compute_data_port()  # TODO- maybe wrong for GNSS and IMU
                settings["data_port"] = data
            cache_path = os.path.join(os.path.dirname(__file__), cache_name)
            #print("writing to " + str(cache_path))
            with open(cache_path, 'w') as settings_file:
                json.dump(settings, settings_file)
        except Exception as e:
            print("error writing connection settings: "+str(e))
            return None

    # connect to the port numbers. return true if succesful connection, false if serial error or ping fails.
    #TODO - call connect_data_port here since it is similar, and make a connect_control_port too?
    def connect_to_ports(self, data_port=None, control_port=None, baud=DEFAULT_BAUD):
        #print(f"connect_to_ports: data_port = {data_port}, control_port = {control_port}, baud = {baud}")
        success = True
        timeout = self.timeout if self.timeout else TIMEOUT_REGULAR
        try:
            if data_port is None:
                self.data_connection = DummyConnection()
            else:
                self.data_connection = SerialConnection(data_port, baud, timeout)
            if control_port is None:
                self.control_connection = DummyConnection()
            else:
                self.control_connection = SerialConnection(control_port, baud, timeout)
            control_success = (control_port is None) or self.check_control_port()
            data_success = (data_port is None) or self.check_data_port()
            success = control_success and data_success
            #print(f"control_success is {control_success}, data_success is {data_success}, success is {success}")

            if not success: #try other baud rates, then check again
                baud = self.auto_detect_baud()
                success = ((control_port is None) or self.check_control_port()) and ((data_port is None) or self.check_data_port())
                #print(f"trying on baud {baud} instead: success is {success}")

            # TODO - verify data connection? but can't tell anything if odr=0
        except Exception as e:  # serial error
            debug_print("error: "+str(e))
            success = False
        if success:
            self.data_port_name = data_port
            self.control_port_name = control_port
            self.baud = baud
        else:
            self.release_connections()
        return success

    def connect_data_port(self, data_port, baud=DEFAULT_BAUD):
        timeout = self.timeout if self.timeout else TIMEOUT_REGULAR
        self.release_data_port()
        try:
            self.data_connection = SerialConnection(data_port, baud, timeout)
            self.data_port_name = data_port
            self.baud = baud
            return True
        except Exception as e:
            self.release_data_port()
            self.data_connection = DummyConnection()
            return False
        #TODO - any success/fail check for data port?

    def release_data_port(self):
        if self.data_connection:
            self.data_connection.close()

    # check control port by pinging.
    def check_control_port(self):
        response = self.ping()
        return response and response.valid and response.msgtype == b'PNG'

    def setup_data_port(self):
        # check the message format so it can parse IMU message
        self.msg_format, = self.retry_get_cfg_flash(["mfm"])  # TODO - handle None response? then can't unpack or get [0]
        #print(f"format: {msg_format}")
        if self.msg_format == b'1':
            self.data_scheme = ReadableScheme()
        elif self.msg_format == b'4':
            self.data_scheme = RTCM_Scheme()
    #check data port is right: should output CAL/IMU/IM1 message types
    #possible issues:
    # 1. if odr 0, no message -> have to set nonzero. also uart on if off.
    #   TODO - check eth on/off too? also if RTCM and CAL, there is no output message -> change to ASCII then?
    # 2. if multiple products connected, all their data ports look the same , so could get the wrong one.
    # 3. if in other message format, need to check for those message types instead.
    def check_data_port(self):
        debug_print(f"check_data_port start")
        changed_odr, changed_uart, check_success = False, False, False
        #turn on output if off. #TODO handle any errors in this block
        #if self.get_cfg(["odr"]).configurations["odr"] == b'0':
        try:
            if self.retry_get_cfg_flash(["odr"])[0] == b'0':
                changed_odr = True
                #TODO - for old firmware, does it need to set odr in flash, then restart? otherwise set ram, no restart
                self.set_cfg_flash({"odr": b"100"}) #maybe change to set_cfg
                self.reset_with_waits() #maybe remove this

            self.setup_data_port()

            #also turn on uart output in ram if off so we can detect data port.
            if self.retry_get_cfg(["uart"])[0] == b"off":
                changed_uart = True
                self.set_cfg({"uart": b"on"})
        except Exception as e:
            #old firmware that can't handle uart or mfm toggle might have error here -> just skip this part.
            debug_print(f"error in check_data_port: {e}")
            pass

        self.data_connection.readall()  # clear old messages which may be wrong type
        for i in range(4):
            msg = self.read_one_message()
            debug_print(f"check_data_port message {i}: {msg}")
            if msg and msg.valid and msg.msgtype in [b'CAL', b'IMU', b'IM1', b'INS', b'GPS', b'GP2', b'HDG']:
                #print("True")
                check_success = True
        #change uart or odr back if changed.
        if changed_odr:
            self.set_cfg_flash({"odr": b"0"})
        if changed_uart:
            self.set_cfg({"uart": b"off"})
        return check_success

    def clear_inputs(self):
        self.data_connection.reset_input_buffer()
        self.control_connection.reset_input_buffer()
        self.data_connection.readall()
        self.control_connection.readall()
        #reset odometer port here? but need check for not exists/is dummy/is None

    def release_connections(self):
        if hasattr(self, "data_connection"):
            self.data_connection.close()
        if hasattr(self, "control_connection"):
            self.control_connection.close()
        if hasattr(self, "odometer_connection") and self.odometer_connection:
            self.odometer_connection.close()

    def reset_connections(self):
        self.release_connections()
        self.__init__(self.data_port_name, self.control_port_name, self.baud, self.data_scheme, self.control_scheme)

    def list_ports(self):
        return sorted([p.device for p in list_ports.comports()])

    # with no cached value - auto connect by trying baud 921600 for all ports first, then other bauds
    def auto_no_cache(self, set_data_port=True):
        #print("\n_____auto no cache_____")
        bauds = ALLOWED_BAUD.copy() #already in preferred order
        for baud in bauds:
            outcome = self.auto_port(baud, set_data_port)
            if outcome: #(control_port, data_port) if succeeded, None if failed
                return outcome + (baud,)
            else:
                continue
        return self.connect_manually(set_data_port) #TODO - turn this off, or do based on a "manual_fallback" arg?

    # detect ports with known baud rate, returns ports or None on fail
    def auto_port(self, baud, set_data_port=True):
        debug_print(f"auto_port, baud = {baud}, set_data_port = {set_data_port}")
        port_names = self.list_ports()
        for control_port in reversed(port_names):
            try:
                self.control_connection = SerialConnection(port=control_port, baud=baud, timeout=TIMEOUT_AUTOBAUD)
                if self.check_control_port():  # success - can set things
                    print(f"connected control port: {control_port}")
                    self.control_port_name = control_port
                    self.control_connection.set_timeout(TIMEOUT_REGULAR)
                    self.baud = baud
                    data_port = None
                    if set_data_port:
                        pid = self.get_pid().pid  # TODO - handle errors and retry?
                        if (b'EVK' in pid) or (b'A1' in pid) or (b'A-1' in pid):
                            #EVK case, including old EVK pid variations: subtract 3.
                            data_port = self.compute_data_port()
                            self.data_connection = SerialConnection(data_port, baud)
                        #if b'GNSS' in pid or b'IMU' in pid:
                        else:
                            #pick the port which outputs IMU or CAL - but won't work if odr 0, and could get a different unit.
                            data_port = self.find_data_port_gnss_imu() #this finds and connects, don't need to set self.data_connection
                            #print(f"data port was {data_port}")
                            #data_port = self.data_port_name
                        if data_port is None: #fail on data port not found
                            return None
                        self.data_port_name = data_port
                    return control_port, data_port
                else:
                    self.release_connections()
            except Exception as e:
                #print("skipping over port " + control_port + " with error: " + str(e))
                self.release_connections()
                continue
        # no ports worked - clean up and report fail
        self.release_connections()
        return None

    # compute data port from control port by subtracting 3 from the number part.
    # eg "COM10" -> "COM7"
    #TODO - do other logic for GNSS/INS and IMU which don't have that port number pattern?
    def compute_data_port(self):
        if self.control_port_name is None:
            return None  # when control_port = None, data_port will always be None too
        try:
            pattern = re.compile(r'\d*$')  # match as many digits as possible at the end of the string
            m = pattern.search(self.control_port_name)
            prefix, numbers = self.control_port_name[:m.start()], self.control_port_name[m.start():]
            minus_three = str(int(numbers) - 3)
            return prefix+minus_three
        except Exception as e:
            return None

    def find_data_port_gnss_imu(self):
        all_ports = self.list_ports()
        dataPortNum = None #is this needed?

        # #check the message format here? but check_data_port does it anyway.
        # msg_format, = self.retry_get_cfg_flash(["mfm"]) #TODO - handle None response? then can't unpack or get [0]
        # if msg_format == b'1':
        #     self.data_scheme = ReadableScheme()
        # elif msg_format == b'4':
        #     self.data_scheme = RTCM_Scheme()
        
        for possible_data_port in all_ports:
            debug_print(f"looking for data port at {possible_data_port}, data scheme is {self.data_scheme}")
            if self.connect_data_port(possible_data_port, self.baud): #230400):  #TODO: 2300400 baud for GNSS - or should it use self.baud?
                if self.check_data_port():
                    dataPortNum = possible_data_port
                    break #avoids the release_data_port
            self.release_data_port()  # wrong data port -> release it
        return dataPortNum #actual port number or None if not found

    # test baud using ping to find the right one, set it for control and data ports
    # requires board to have control_connection and data_connection already set to the right ports
    def auto_detect_baud(self):
        bauds = ALLOWED_BAUD.copy() #already in preferred order
        for baud in bauds:
            self.control_connection.set_baud(baud)
            self.control_connection.reset_input_buffer()
            response = self.ping()
            if response and response.valid and response.msgtype == b'PNG':
                self.data_connection.set_baud(baud)
                self.data_connection.reset_input_buffer()
                return baud
        return None

    #set the serial connections baud (does not set baud configuration on the product)
    # if UDP connection, set_baud does nothing.
    def set_connection_baud(self, baud):
        self.baud = baud
        self.control_connection.set_baud(baud)
        self.data_connection.set_baud(baud)
        # clear any bad data at the old baud
        self.control_connection.readall()
        self.data_connection.readall()

    def connect_manually(self, set_data_port=False):
        # get the port numbers
        # stream = os.popen("python -m serial.anello_tools.list_ports")
        # port_names = [line.strip() for line in stream.readlines()]
        port_names = self.list_ports()
        if not port_names:
            print("no ports found.")
            return None
        port_names.append("cancel")
        data_con = DummyConnection()
        serial_con = DummyConnection()

        print("\nmanually select ports")
        # connect to data port if we want to
        if set_data_port:
            connected = False
            while not connected:
                try:
                    print("\nselect data port (should be lowest of the 4 consecutive ports)")
                    data_port = port_names[cutie.select(port_names, selected_index=0)]
                    if data_port == "cancel":
                        data_con.close() #disconnect in case it's needed
                        serial_con.close()
                        return
                    data_con = SerialConnection(data_port, DEFAULT_BAUD, timeout=TIMEOUT_REGULAR)
                except serial.serialutil.SerialException:
                    print("\nerror connecting to " + data_port + " - wrong port number or port is busy")
                    continue
                connected = True
                print("\nconnected to data port: " + data_port)
        else:
            data_port = None
            data_con = DummyConnection()

        # connect to control port - need this to configure the board
        connected = False
        while not connected:
            try:
                print("\nselect configuration port (should be highest of the 4 consecutive ports)")
                control_port = port_names[cutie.select(port_names, selected_index=0)] #min(3, len(port_names)))]
                if control_port == "cancel":
                    data_con.close()  # disconnect in case it's needed
                    serial_con.close()
                    return  # TODO - need to disconnect from anything first?
                control_con = SerialConnection(control_port, DEFAULT_BAUD, timeout=TIMEOUT_REGULAR)
            except serial.serialutil.SerialException:
                print("\nerror connecting to " + control_port + " - wrong port number or port is busy")
                continue
            connected = True
            print("\nconnected to control port:" + control_port)

        self.data_connection = data_con
        self.data_port_name = data_port
        self.control_connection = control_con
        self.control_port_name = control_port
        baud = self.auto_detect_baud()
        self.baud = baud
        # print("auto detected baud = "+str(baud))
        self.write_connection_settings(set_data_port)
        return control_port, data_port, baud #{"control port": port, "data port": data_port, "baud": baud}

    # reads one message - returns None if there is no message
    # this does not error on None since Session loop just keeps waiting
    def read_one_message(self, num_attempts=1):
        debug_print("read_one_message")
        message = None
        # When UDP is used it returns empty messages. This while loop is used to ensure there is a message 
        # before exiting
        attempt_count = 0 
        while message == None or message.__dict__ == {}: 
            if hasattr(self, "msg_format") and self.msg_format == b"4" and hasattr(self.data_connection, "sock"):
                #   When UDP and RTCM is use we can only get message this way 
                message = self.data_scheme.read_one_message(self.data_connection.sock)
            else:
                message = self.data_scheme.read_one_message(self.data_connection)
            if debug: print(message)
            if attempt_count >= num_attempts:
                debug_print(f"attempt count: {attempt_count}")
                break
            attempt_count += 1

        return message

    # send a message on the control channel
    # we expect a response for each control message, so show an error if there is none.
    def send_control_message(self, message):
        self.control_connection.readall() #read everything to clear any old responses
        self.control_scheme.write_one_message(message, self.control_connection)
        time.sleep(1e-1) #wait for response, seems to need it if UDPConnection has timeout 0.
        resp = self.read_one_control_message()
        if resp:
            return resp
        else:  # timed out waiting for response -> list error as invalid message
            m = Message()
            m.valid = False
            m.error = "Timeout"

    # send and don't wait for response- use this for odo message
    def send_control_no_wait(self, message):
        self.control_scheme.write_one_message(message, self.control_connection)

    # read control message - for example response after we send a control message
    def read_one_control_message(self):
        return self.control_scheme.read_one_message(self.control_connection)

    # methods to build and send messages by type
    # These all return a message object for the response.
    def get_version(self):
        m = Message({'msgtype': b'VER'})
        return self.send_control_message(m)

    def get_serial(self):
        m = Message({'msgtype': b'SER'})
        return self.send_control_message(m)

    def get_pid(self):
        m = Message({'msgtype': b'PID'})
        return self.send_control_message(m)

    def get_ihw(self):
        m = Message({'msgtype': b'IHW'})
        return self.send_control_message(m)

    def get_fhw(self):
        m = Message({'msgtype': b'FHW'})
        return self.send_control_message(m)

    def get_fsn(self):
        m = Message({'msgtype': b'FSN'})
        return self.send_control_message(m)

    #user config methods: can read/write in flash/ram
    def set_cfg(self, configurations):
        m = Message({'msgtype': b'CFG', 'mode': WRITE_RAM, 'configurations': configurations})
        return self.send_control_message(m)

    def set_cfg_flash(self, configurations):
        m = Message({'msgtype': b'CFG', 'mode': WRITE_FLASH, 'configurations': configurations})
        return self.send_control_message(m)

    def get_cfg(self, names_list):
        m = Message({'msgtype': b'CFG', 'mode': READ_RAM, 'configurations': names_list})
        return self.send_control_message(m)

    def get_cfg_flash(self, names_list):
        m = Message({'msgtype': b'CFG', 'mode': READ_FLASH, 'configurations': names_list})
        return self.send_control_message(m)

    #vehicle config methods: only flash part is fully implemented now.
    def set_veh_flash(self, configurations):
        m = Message({'msgtype': b'VEH', 'mode': WRITE_FLASH, 'configurations': configurations})
        return self.send_control_message(m)

    def get_veh_flash(self, names_list):
        m = Message({'msgtype': b'VEH', 'mode': READ_FLASH, 'configurations': names_list})
        return self.send_control_message(m)

    def get_status(self):
        m = Message({'msgtype': b'STA'})
        return self.send_control_message(m)

    def ping(self):
        m = Message({'msgtype': b'PNG'})
        return self.send_control_message(m)

    def echo(self, contents):
        m = Message({'msgtype': b'ECH', 'contents': contents})
        return self.send_control_message(m)

    def send_reset(self, code):
        m = Message({'msgtype': b'RST', 'code': code})
        return self.send_control_no_wait(m)  # after reset it may not respond

    def send_reset_regular(self):
        self.send_reset(0)

    def enter_bootloading(self):
        self.send_reset(2)

    #send odometer message: over the udp odometer connection if exists, else config connection
    #config connection can take odometer messages but it could interfere with other config messaging
    def send_odometer(self, speed):
        m = Message({'msgtype': b'ODO', 'speed': speed})
        if hasattr(self, "odometer_connection") and self.odometer_connection:
            self.control_scheme.write_one_message(m, self.odometer_connection)
        else:
            self.send_control_no_wait(m)

    # enable odometer config in ram or flash - need this for test setup since odo=off can't set to other values
    def enable_odo_ram(self):
        return self.set_cfg({"odo": b'on'})

    def enable_odo_flash(self):
        return self.set_cfg_flash({"odo": b'on'})

    #functions to retry commands (in case of error) and return the raw values (from Temp_Cal_Verify_Data_Collection)
    #or should I use retry_command from user_program.py instead?

    #getters without keyword: call on self.get_version , etc.
    # method is a reference to the function like self.get_version. or should it be string -> do getattr(self, "get_version")()
    def retry_get_info(self, method, expect_response_type, attr_name):
        # resp_attr = None
        for i in range(COMMANDS_RETRY):
            try:
                time.sleep(0.1)
                resp = method()  # get pid() etc take no argument
                #if resp and resp.valid and resp.msgtype == expect_response_type and hasattr(resp, attr_name):
                    # resp_attr = getattr(resp, attr_name)
                    #return getattr(resp, attr_name)
                if not resp:
                    debug_print(f"{method.__name__}: resp failed check (no response), retrying")
                elif not resp.valid:
                    debug_print(f"{method.__name__}: resp failed check (invalid, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif resp.msgtype != expect_response_type:
                    debug_print(f"{method.__name__}: resp failed check (wrong type, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif not hasattr(resp, attr_name):
                    debug_print(f"{method.__name__}: resp failed check (no attribute {attr_name}, retrying")
                else:
                    return getattr(resp, attr_name)
            except Exception as e:
                debug_print(f"error getting {expect_response_type}, retrying: {e}")
        print(f"retry limit: could not find attribute {attr_name}") #make this debug_print too?
        return None  # did not find it within retry limit

    # retry getters with keywords , like self.get_cfg, self.get_cfg_flash, self.get_sensor, self.get_vehicle,
    # if return_dict==True, return configurations as dictionary. otherwise returns a list in attr_name_list order.
    # to get everything, use: attr_name_list = [], return_dict = True
    def retry_get_info_keywords(self, method, expect_response_type, attr_name_list, return_dict=False):
        # resp_attr = None
        for i in range(COMMANDS_RETRY):
            try:
                time.sleep(0.1)
                resp = method(attr_name_list)
                if not resp:
                    debug_print(f"{method.__name__}: {attr_name_list} resp failed check (no response), retrying")
                elif not resp.valid:
                    debug_print(f"{method.__name__}: {attr_name_list} resp failed check (invalid, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif resp.msgtype != expect_response_type:
                    debug_print(f"{method.__name__}: {attr_name_list} resp failed check (wrong type, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif not hasattr(resp, "configurations"):
                    debug_print(f"{method.__name__}: {attr_name_list} resp failed check (no configurations, type {resp.msgtype}, error {resp.error}), retrying")
                #if resp and resp.valid and resp.msgtype == expect_response_type and hasattr(resp, "configurations"):
                else: #all working
                    # resp_attr = getattr(resp, attr_name)
                    if return_dict:
                        return resp.configurations #return the configurations dictionary if you ask for that.
                    else:
                        return [resp.configurations[attr] for attr in attr_name_list]  # list in order of attr_name_list
                # else:
                #     #print(f"resp failed check: {resp}")
                #     print(f"{method.__name__}: resp failed check {}, retrying")
            except Exception as e:
                debug_print(f"error getting {expect_response_type}, retrying: {e}")
        debug_print(f"retry limit: could not find attributes {attr_name_list}") #make this debug_print too?
        return None  # did not find it within retry limit

    # to set configs/factory which use key/value
    # TODO - make a version which does individual writes?
    def retry_set_keywords(self, method, expect_response_type, configs_dict):
        for i in range(COMMANDS_RETRY):
            try:
                time.sleep(0.1)
                resp = method(configs_dict)
                # if resp and resp.valid and resp.msgtype == expect_response_type and hasattr(resp,"configurations") and resp.configurations == configs_dict:
                #     return True
                # else:
                #     print(f"{method.__name__}: {configs_dict} resp failed check, retrying")

                if not resp:
                    debug_print(f"{method.__name__}: {configs_dict} resp failed check (no response), retrying")
                elif not resp.valid:
                    debug_print(f"{method.__name__}: {configs_dict} resp failed check (invalid, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif resp.msgtype != expect_response_type:
                    debug_print(f"{method.__name__}: {configs_dict} resp failed check (wrong type, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif not hasattr(resp, "configurations"):
                    debug_print(f"{method.__name__}: {configs_dict} resp failed check (no configurations, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                elif resp.configurations != configs_dict:
                    debug_print(f"{method.__name__}: {configs_dict} resp had wrong configurations, retrying.\nresponse:{resp.configurations}\nexpected:{configs_dict}")
                else:
                    return True

            except Exception as e:
                debug_print(f"error setting {expect_response_type}, retrying: {e}")
        debug_print(f"retry limit: could not set attributes {configs_dict}") #make this debug_print too?
        return False  # did not find it within retry limit

    # methods to retry the specific commands by using the retry functions on that function
    # these return the getter info instead of a message object, so simpler to use in other code.
    # don't use for "no response" types since it won't know to retry -> just use the original method.

    #getters with no keywords list: use retry_get_info
    def retry_get_version(self):
        return self.retry_get_info(self.get_version, b'VER', 'ver')

    def retry_get_serial(self):
        return self.retry_get_info(self.get_serial, b'SER', 'ser')

    def retry_get_pid(self):
        return self.retry_get_info(self.get_pid, b'PID', 'pid')

    def retry_get_ihw(self):
        return self.retry_get_info(self.get_ihw, b'IHW', 'ihw')

    def retry_get_fhw(self):
        return self.retry_get_info(self.get_fhw, b'FHW', 'fhw')

    def retry_get_fsn(self):
        return self.retry_get_info(self.get_fsn, b'FSN', 'fsn')

    def retry_get_status(self):
        #m = Message({'msgtype': b'STA'})
        return self.retry_get_info(self.get_status, b'STA', 'payload') #could change later if we finish implementing status

    #getters with keywords: use retry_get_info_keywords
    #use this like: odr, msgtype = b.retry_get_cfg_flash(["odr", "msgtype"]). single value:  odr, = b.retry_get_cfg_flash(["odr"])
    #make return_dict an arg for these too, or just return list always?
    def retry_get_cfg(self, names_list, as_dict=False):
        return self.retry_get_info_keywords(self.get_cfg, b'CFG', names_list, return_dict=as_dict)

    def retry_get_cfg_flash(self, names_list, as_dict=False):
        return self.retry_get_info_keywords(self.get_cfg_flash, b'CFG', names_list, return_dict=as_dict)

    def retry_get_veh_flash(self, names_list, as_dict=False):
        return self.retry_get_info_keywords(self.get_veh_flash, b'VEH', names_list, return_dict=as_dict)

    # TODO - make a wrapper for single arg that unwraps it? like:  odr = retry_get_flash("odr") ?
    #ex: def_retry_get_cfg(self, single_name): return self.retry_get_cfg([single_name])[0]

    #to read all for keyword getters: returns the dictionary
    def retry_get_cfg_all(self):
        return self.retry_get_info_keywords(self.get_cfg, b'CFG', [], return_dict=True)

    def retry_get_cfg_flash_all(self):
        return self.retry_get_info_keywords(self.get_cfg_flash, b'CFG', [], return_dict=True)

    def retry_get_veh_flash_all(self):
        return self.retry_get_info_keywords(self.get_veh_flash, b'VEH', [], return_dict=True)

    #setters with keywords: retry_set_keywords
    def retry_set_cfg(self, configurations):
        return self.retry_set_keywords(self.set_cfg, b'CFG', configurations)

    def retry_set_cfg_flash(self, configurations):
        return self.retry_set_keywords(self.set_cfg_flash, b'CFG', configurations)

    def retry_set_veh_flash(self, configurations):
        return self.retry_set_keywords(self.set_veh_flash, b'VEH', configurations)

    #def retry_ping(self):  - should it have this?
    #def retry_echo(self, contents): - should it have this?

    #no retry methods for resets (bootloader/regular) or odometer since they don't respond.

    # def retry_enable_odo_ram(self):
    #     return self.set_cfg({"odo": b'on'})
    #
    # def retry_enable_odo_flash(self):
    #     return self.set_cfg_flash({"odo": b'on'})
    #

    #config write functions with separate writes and retry, by type
    #should it return pass/fail, or lists of which set, which failed to set?
    def set_user_configs_ram(self, configs):
        for k, v in configs.items():
            self.retry_set_cfg({k: v})

    def set_user_configs_flash(self, configs):
        for k, v in configs.items():
            self.retry_set_cfg_flash({k: v})

    def set_vehicle_configs(self, configs):
        for k, v in configs.items():
            self.retry_set_veh_flash({k: v})

    #reset with sleeps before/after, like in verify_algo off but not checking algo
    #use this to reset safely in programs
    # use new_baud only if baud changed, otherwise leave None
    def reset_with_waits(self, new_baud=None):
        wait_time = 0.5
        time.sleep(wait_time)
        self.send_reset_regular()
        time.sleep(wait_time)

        #use the new baud if it changed, otherwise ping and other messages will fail.
        if new_baud:
            self.set_connection_baud(new_baud)

        while self.ping() is None:
            #TODO - should this time out eventually -> retry connection?
            #print("waiting on reset")
            time.sleep(wait_time)
