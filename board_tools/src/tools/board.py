import sys
import os
import cutie
import json
import subprocess
import os
import re
import serial.tools.list_ports as list_ports
import time
from pathlib import Path


ABS_PATH = Path(__file__)
sys.path.append(str(ABS_PATH.parent.parent.parent.parent))

try:  # importing from inside the package
    from readable_scheme import *
    from rtcm_scheme import *
    from binary_scheme import *
    from binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from message_scheme import Message
    from connection import *
    from class_configs.board_config import *
    from detect_os import os_type, processor_type
except ModuleNotFoundError:  # importing from outside the package
    from tools.readable_scheme import *
    from tools.rtcm_scheme import *
    from tools.binary_scheme import *
    from tools.binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from tools.message_scheme import Message
    from tools.connection import *
    from tools.class_configs.board_config import *
    from tools.detect_os import os_type, processor_type

debug = False
COMMANDS_RETRY = 5  # retry limit for commands. mostly matters for USB with lower baud, large commands

# windows com port settings: latency timer can be 1 to 255 ms , default 16 ms
DEFAULT_PORT_LATENCY_S = 0.016
MAX_PORT_LATENCY_S = 0.255


def debug_print(text):
    if debug:
        print(text)


# abstraction of the board and its inputs and outputs
class IMUBoard:
    #def __init__(self, data_port=None, control_port=None, baud=DEFAULT_BAUD, data_scheme=RTCM_Scheme(), control_scheme=ReadableScheme(), try_manual=True, timeout=None):
    def __init__(self, data_port=None, control_port=None, baud=DEFAULT_BAUD, data_baud=None, data_scheme=ReadableScheme(), control_scheme=ReadableScheme(), try_manual=True, timeout=None):

        if data_baud is None:
            data_baud = baud

        self.data_scheme = data_scheme
        self.control_scheme = control_scheme
        self.control_baud = baud
        self.data_baud = data_baud
        self.timeout = timeout
        success = self.connect_to_ports(data_port, control_port, control_baud=baud, data_baud=data_baud)
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
            control_port, data_port, control_baud, data_baud = board.read_connection_settings(set_data_port)
            if not control_port: #or not data_port:
                #print("no control port in cache -> fail")
                success = False
            if not set_data_port:
                data_port = None
            success = success and board.connect_to_ports(data_port, control_port, control_baud, data_baud)
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
            if board.auto_no_cache(set_data_port): # None on fail
                board.write_connection_settings(set_data_port) #also counts as success -> save.
            else:
                board.release_connections()
                return None
        return board

    @classmethod
    def auto_from_sn(cls, serial_number: str, set_data_port=True):
        board = cls()
        try:
            success = True
            control_port, data_port, control_baud, data_baud = board.read_connection_settings(set_data_port)
            if not control_port: #or not data_port:
                #print("no control port in cache -> fail")
                success = False
            if not set_data_port:
                data_port = None
            success = success and board.connect_to_ports(data_port, control_port, control_baud, data_baud)
            success = ((success) and (board.retry_get_serial().decode() == serial_number))
        except Exception as e:
            success = False

        if success:
            pass
        else:
            board.release_connections()
            if board.auto_no_cache_from_sn(serial_number, set_data_port):
                pass
            else:
                board.release_connections()
                return None
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
                control_port = settings["control_port"]
                control_baud = settings["control_baud"]
                #TODO - should it fall back on "baud" if no "control_baud" and "data_baud"?
                if using_data_port:
                    data_port = settings["data_port"]
                    data_baud = settings["data_baud"]
                else:
                    data_port, data_baud = None, None
                return control_port, data_port, control_baud, data_baud
        except Exception as e:
            #print("error reading connection settings: "+str(e))
            return None

    def write_connection_settings(self, using_data_port):
        try:
            cache_name = CONNECTION_CACHE_WITH_DATA_PORT if using_data_port else CONNECTION_CACHE_NO_DATA_PORT
            control_port, control_baud = self.control_port_name, self.control_baud
            # avoid writing null for ports
            if control_port is None:
                return None
            settings = {"control_port": control_port, "control_baud": control_baud}
            if using_data_port:
                data_port = self.data_port_name
                # if data is None: #would this happen?
                #     data = self.compute_data_port()  # TODO- maybe wrong for GNSS and IMU
                settings["data_port"] = data_port
                settings["data_baud"] = self.data_baud
            cache_path = os.path.join(os.path.dirname(__file__), cache_name)
            #print("writing to " + str(cache_path))
            with open(cache_path, 'w') as settings_file:
                json.dump(settings, settings_file)
        except Exception as e:
            print("error writing connection settings: "+str(e))
            return None

    # connect to the port numbers. return true if succesful connection, false if serial error or ping fails.
    #TODO - call connect_data_port here since it is similar, and make a connect_control_port too?

    def connect_to_ports(self, data_port=None, control_port=None, control_baud=DEFAULT_BAUD, data_baud=None):

        if data_baud is None:
            data_baud = control_baud

        #print(f"connect_to_ports: data_port = {data_port}, control_port = {control_port}, baud = {baud}")
        success = True
        timeout = self.timeout if self.timeout else TIMEOUT_REGULAR
        try:
            if data_port is None:
                self.data_connection = DummyConnection()
            else:
                self.data_connection = SerialConnection(data_port, data_baud, timeout)
                self.data_baud = data_baud
            if control_port is None:
                self.control_connection = DummyConnection()
            else:
                self.control_connection = SerialConnection(control_port, control_baud, timeout)
                self.control_baud = control_baud
            control_success = (control_port is None) or self.check_control_port()
            data_success = (data_port is None) or self.check_data_port()
            success = control_success and data_success
            #print(f"control_success is {control_success}, data_success is {data_success}, success is {success}")

            if not success: #try other baud rates, then check again
                config_baud, data_baud = self.auto_detect_baud()
                success = ((control_port is None) or self.check_control_port()) and ((data_port is None) or self.check_data_port())
                #print(f"trying on baud {baud} instead: success is {success}")

            # TODO - verify data connection? but can't tell anything if odr=0
        except Exception as e:  # serial error
            debug_print("error: "+str(e))
            success = False
        if success:
            self.data_port_name = data_port
            self.control_port_name = control_port
        else:
            self.release_connections()
        self.connect_success = success
        return success

    def connect_data_port(self, data_port, baud=DEFAULT_BAUD):
        timeout = self.timeout if self.timeout else TIMEOUT_REGULAR
        self.release_data_port()
        try:
            self.data_connection = SerialConnection(data_port, baud, timeout)
            self.data_port_name = data_port
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
        # must get proper ping response.
        # Don't count APPNG,1 which comes from X3 data port. accept 2 (X3 config port) or 0 (old X3, other products).
        return response and response.valid and response.msgtype == b'PNG' and response.code != 1

    def setup_data_port(self):
        # check the message format so it can parse IMU message
        self.msg_format, = self.retry_get_cfg_flash(["mfm"])  # TODO - handle None response? then can't unpack or get [0]
        #print(f"format: {msg_format}")
        if self.msg_format == b'1':
            self.data_scheme = ReadableScheme()
        elif self.msg_format == b'4':
            self.data_scheme = RTCM_Scheme()
        elif self.msg_format == b'0':
            self.data_scheme = Binary_Scheme()

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
            if msg and hasattr(msg, "msgtype") and msg.msgtype in OUTPUT_MESSAGE_TYPES:
                check_success = True
                break
        #change uart or odr back if changed.
        if changed_odr:
            self.set_cfg_flash({"odr": b"0"})
        if changed_uart:
            self.set_cfg({"uart": b"off"})
        return check_success

    def clear_inputs(self):
        self.clear_data_port()
        self.clear_control_port()
        # reset odometer port here? but need check for not exists/is dummy/is None

    def clear_connection(self, connection, scheme, wait_time_seconds):
        # temporarily set timeout to zero, and read data until read is empty
        connection.reset_input_buffer()
        old_timeout = connection.get_timeout()
        connection.set_timeout(0)

        # read all data. then wait for delayed arrivals and read all data again.
        last_byte = connection.read(1)
        while (last_byte is not None) and len(last_byte) > 0:
            last_byte = connection.read(1)

        time.sleep(wait_time_seconds)
        last_byte = connection.read(1)
        while (last_byte is not None) and len(last_byte) > 0:
            last_byte = connection.read(1)

        # use read_one_message to clear any partial messages
        while True:
            try:
                m = scheme.read_one_message(connection)
                # print(m)
                if m is None:
                    break
                elif hasattr(m, "valid"):
                    # UDP connection has no "connection" or "in_waiting". TODO - does it need a similar check for UDP?
                    if not hasattr(connection, "connection"):  # UDP connection
                        break
                    if m.valid and connection.connection.in_waiting < 50:
                        break
                    if m.error == "Length(unpack)":
                        break
            except AssertionError:
                continue

        connection.set_timeout(old_timeout)

    def clear_control_port(self):
        # use shorter delay for control port clearing: used more often, less crucial to get all old messages
        self.clear_connection(self.control_connection, self.control_scheme, DEFAULT_PORT_LATENCY_S)

    def clear_data_port(self):
        # use longer delay for data port to make sure old outputs are cleared.  not called frequently.
        self.clear_connection(self.data_connection, self.data_scheme, MAX_PORT_LATENCY_S*2)

    def release_connections(self):
        if hasattr(self, "data_connection"):
            self.data_connection.close()
        if hasattr(self, "control_connection"):
            self.control_connection.close()
        if hasattr(self, "odometer_connection") and self.odometer_connection:
            self.odometer_connection.close()

    # connect again on serial after disconnecting. TOD0 - make a version for ethernet too?
    def reconnect_serial(self):
        #self.connect_to_ports(data_port=self.data_port_name, control_port=self.control_port_name)
        # todo - clear config and data ports here? or inside init?
        self.__init__(self.data_port_name, self.control_port_name, baud=self.control_baud, data_baud=self.data_baud,
                      data_scheme=self.data_scheme, control_scheme=self.control_scheme)

    # disconnect and reconnect serial. TODO - does this work for ethernet?
    def reset_connections(self):
        self.release_connections()
        self.reconnect_serial()

    def list_ports(self):
        return sorted([p.device for p in list_ports.comports()])

    # with no cached value - auto connect by trying baud 921600 for all ports first, then other bauds
    def auto_no_cache(self, set_data_port=True):
        #print("\n_____auto no cache_____")
        bauds = ALLOWED_BAUD.copy() #already in preferred order
        for control_baud in bauds:
            outcome = self.auto_port(control_baud, set_data_port)
            if outcome: #(control_port, data_port) if succeeded, None if failed
                #control_port, data_port, control_baud, data_baud = outcome
                return True
            else:
                continue
        return self.connect_manually(set_data_port) #TODO - turn this off, or do based on a "manual_fallback" arg?

    # detect ports with known baud rate, returns ports or None on fail
    def auto_port(self, control_baud, set_data_port=True):
        debug_print(f"auto_port, baud = {control_baud}, set_data_port = {set_data_port}")
        port_names = self.list_ports()
        for control_port in reversed(port_names):
            try:
                self.control_connection = SerialConnection(port=control_port, baud=control_baud, timeout=TIMEOUT_AUTOBAUD)
                if self.check_control_port():  # success - can set things
                    print(f"connected control port: {control_port}")
                    self.control_port_name = control_port
                    self.control_connection.set_timeout(TIMEOUT_REGULAR)
                    self.control_baud = control_baud
                    data_baud = self.get_data_baud_flash()
                    self.data_baud = data_baud
                    data_port = None
                    if set_data_port:
                        pid = self.get_pid().pid  # TODO - handle errors and retry?
                        if (b'EVK' in pid) or (b'A1' in pid) or (b'A-1' in pid):
                            #EVK case, including old EVK pid variations: subtract 3.
                            data_port = self.compute_data_port()
                            self.data_connection = SerialConnection(data_port, data_baud)
                        #if b'GNSS' in pid or b'IMU' in pid:
                        # elif b'X3' in pid:
                        #     data_port = self.compute_data_port_x3()
                        #     self.data_connection = SerialConnection(data_port, baud)
                        else:
                            #pick the port which outputs IMU or CAL - but won't work if odr 0, and could get a different unit.
                            data_port = self.find_data_port_gnss_imu() #this finds and connects, don't need to set self.data_connection
                            #print(f"data port was {data_port}")
                            #data_port = self.data_port_name
                        if data_port is None: #fail on data port not found
                            return None
                        self.data_port_name = data_port
                    return control_port, data_port, control_baud, data_baud
                else:
                    self.release_connections()
            except Exception as e:
                debug_print("skipping over port " + control_port + " with error: " + str(e))
                self.release_connections()
                continue
        # no ports worked - clean up and report fail
        self.release_connections()
        return None

        # with no cached value - auto connect by trying baud 921600 for all ports first, then other bauds
    def auto_no_cache_from_sn(self, serial_number: str, set_data_port=True):
        #print("\n_____auto no cache_____")
        bauds = ALLOWED_BAUD.copy() #already in preferred order
        for baud in bauds:
            outcome = self.auto_port_from_sn(baud, serial_number, set_data_port)
            if outcome: #(control_port, data_port) if succeeded, None if failed
                return outcome + (baud,)
            else:
                continue
        return self.connect_manually(set_data_port) #TODO - turn this off, or do based on a "manual_fallback" arg?
        
    #TODO adapt this function for serial number
    def auto_port_from_sn(self, baud, serial_number: str, set_data_port=True):
        debug_print(f"auto_port, baud = {baud}, set_data_port = {set_data_port}")
        port_names = self.list_ports()
        for control_port in reversed(port_names):
            try:
                self.control_connection = SerialConnection(port=control_port, baud=baud, timeout=TIMEOUT_AUTOBAUD)
                if self.check_control_port():  # success - can set things
                    if self.retry_get_serial().decode() == serial_number:
                        print(f"connected control port: {control_port}")
                        self.control_port_name = control_port
                        self.control_connection.set_timeout(TIMEOUT_REGULAR)
                        data_port = None
                        if set_data_port:
                            pid = self.get_pid().pid  # TODO - handle errors and retry?
                            if (b'EVK' in pid) or (b'A1' in pid) or (b'A-1' in pid):
                                #EVK case, including old EVK pid variations: subtract 3.
                                data_port = self.compute_data_port_from_sn(serial_number)
                                self.data_connection = SerialConnection(data_port, baud)
                            #if b'GNSS' in pid or b'IMU' in pid:
                            # elif b'X3' in pid:
                            #     data_port = self.compute_data_port_x3()
                            #     self.data_connection = SerialConnection(data_port, baud)
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
                else:
                    self.release_connections()
            except Exception as e:
                debug_print("skipping over port " + control_port + " with error: " + str(e))
                self.release_connections()
                continue
        # no ports worked - clean up and report fail
        self.release_connections()
        return None
        pass

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

    def compute_data_port_from_sn(self, serial_number: str):
        def is_port_outputting(port_name: str):
            iteration_count = 10
            data_arr = []
            conn = None
            try:
                conn = SerialConnection(port_name, self.data_baud, timeout=TIMEOUT_REGULAR)
                for i in range(iteration_count):
                    time.sleep(.01)
                    data_arr.append(len(conn.readall()))    
                conn.close()
            except Exception as e:
                if not conn is None:
                    conn.close()
                return False

            halfway_index = int(iteration_count / 2)
            return sum(data_arr[halfway_index:]) > 0            # only look at last half to avoid old data thats been cached on the port

        if self.control_port_name is None:
            return None  # when control_port = None, data_port will always be None too
        try:
            # get serial output state
            uart_state = self.retry_get_cfg(['uart'])[0]
            self.retry_set_cfg({'uart': b'on'})


            # get all ports outputting data
            outputting_ports = []
            ports = self.list_ports()
            for port in ports:
                if is_port_outputting(port):
                    outputting_ports.append(port)


            # set serial output state 'off'
            self.retry_set_cfg({'uart': b'off'})
            
            # of the previously outputting data, which have stopped outputting after sending "uart off" command
            final_candidates = []
            for port in outputting_ports:
                if not is_port_outputting(port):
                    final_candidates.append(port)

            self.retry_set_cfg({'uart': uart_state})
            
            if len(final_candidates) != 1:
                raise Exception(f"{len(final_candidates)} objects for port:{self.control_port_name} when 1 is expected")
            
            return final_candidates[0]
        except Exception as e:
            debug_print(str(e))
            return None

    # for X3 with new connector board, data port = config_port - 1
    def compute_data_port_x3(self):
        if self.control_port_name is None:
            return None  # when control_port = None, data_port will always be None too
        try:
            pattern = re.compile(r'\d*$')  # match as many digits as possible at the end of the string
            m = pattern.search(self.control_port_name)
            prefix, numbers = self.control_port_name[:m.start()], self.control_port_name[m.start():]
            minus_one = str(int(numbers) - 1)
            #print(f"computing data port for x3: config {numbers} -> data is {minus_one}")
            return prefix+minus_one
        except Exception as e:
            return None

    def find_data_port_gnss_imu(self):
        all_ports = self.list_ports()
        debug_print(f"find_data_port_gnss_imu: possible data ports are {all_ports}")
        dataPortNum = None #is this needed?

        # #check the message format here? but check_data_port does it anyway.
        # msg_format, = self.retry_get_cfg_flash(["mfm"]) #TODO - handle None response? then can't unpack or get [0]
        # if msg_format == b'1':
        #     self.data_scheme = ReadableScheme()
        # elif msg_format == b'4':
        #     self.data_scheme = RTCM_Scheme()
        
        for possible_data_port in all_ports:
            debug_print(f"looking for data port at {possible_data_port}, data scheme is {self.data_scheme}")
            if self.connect_data_port(possible_data_port, self.data_baud):
                debug_print(f"connected at {possible_data_port}")
                if self.check_data_port():
                    debug_print(f"check success at {possible_data_port}")
                    dataPortNum = possible_data_port
                    break #avoids the release_data_port
            self.release_data_port()  # wrong data port -> release it
        return dataPortNum #actual port number or None if not found

    # test baud using ping to find the right one, set it for control and data ports
    # requires board to have control_connection and data_connection already set to the right ports
    def auto_detect_baud(self):
        bauds = ALLOWED_BAUD.copy() #already in preferred order
        for control_baud in bauds:
            self.control_connection.set_baud(control_baud)
            self.control_baud = control_baud
            self.control_connection.reset_input_buffer()
            if self.check_control_port():
                data_baud = self.get_data_baud_flash()
                self.data_baud = data_baud
                self.data_connection.set_baud(data_baud)
                self.data_connection.reset_input_buffer()
                return control_baud, data_baud
        return None

    #set the serial connections baud (does not set baud configuration on the product)
    # if UDP connection, set_baud does nothing.
    def set_connection_baud(self, new_control_baud=None, new_data_baud=None):
        if new_control_baud:
            self.control_baud = new_control_baud
            self.control_connection.set_baud(new_control_baud)
        if new_data_baud:
            self.data_baud = new_data_baud
            self.data_connection.set_baud(new_data_baud)

        # clear any bad data at the old baud
        self.control_connection.readall()
        self.data_connection.readall()

    def connect_manually(self, set_data_port=False, set_config_port=True):
        # get the port numbers
        # stream = os.popen("python -m serial.tools.list_ports")
        # port_names = [line.strip() for line in stream.readlines()]
        port_names = self.list_ports()
        if not port_names:
            show_and_pause("no ports found.")
            return None
        port_names.append("cancel")
        data_con = DummyConnection()
        serial_con = DummyConnection()

        # connect to data port if we want to
        if set_data_port:
            connected = False
            while not connected:
                try:
                    print("\nselect data port")
                    data_port = port_names[cutie.select(port_names, selected_index=0)]
                    if data_port == "cancel":
                        data_con.close() #disconnect in case it's needed
                        serial_con.close()
                        return None
                    if not set_config_port:
                        valid_baud_rates = ALLOWED_BAUD_SORTED.copy()
                        print("\nselect baud rate")
                        baud = valid_baud_rates[cutie.select(valid_baud_rates, selected_index=0)]
                        data_con = SerialConnection(data_port, baud, timeout=TIMEOUT_REGULAR)
                    else:
                        data_con = SerialConnection(data_port, DEFAULT_BAUD, timeout=TIMEOUT_REGULAR)
                except serial.serialutil.SerialException:
                    print("\nerror connecting to " + data_port + " - wrong port number or port is busy")
                    continue
                connected = True
                print("\nconnected to data port: " + data_port)
        else:
            data_port = None
            data_con = DummyConnection()

        if not set_config_port:
            config_con = DummyConnection()

            self.data_connection = data_con
            self.data_port_name = data_port
            self.control_connection = config_con
            self.control_port_name = "None"
            self.data_baud = baud
            return True

        # connect to control port - need this to configure the board
        connected = False
        while not connected:
            try:
                print("\nselect configuration port")
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
        control_baud, data_baud = self.auto_detect_baud()
        # print("auto detected baud = "+str(baud))
        self.write_connection_settings(set_data_port)
        return True #control_port, data_port, baud #{"control port": port, "data port": data_port, "baud": baud}

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
        self.clear_control_port()
        self.control_scheme.write_one_message(message, self.control_connection)
        time.sleep(1e-1)  # wait for response, seems to need it if UDPConnection has timeout 0.
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

    def form_custom_message(self, message_text):
        message_text = message_text.lstrip(READABLE_START)  # remove any starting #
        checksum = int_to_ascii(self.control_scheme.compute_checksum(message_text))
        full_msg = READABLE_START + message_text + READABLE_CHECKSUM_SEPARATOR + checksum + READABLE_END
        return full_msg

    # read control message - for example response after we send a control message
    def read_one_control_message(self):
        # return self.control_scheme.read_one_message(self.control_connection) #old version

        for i in range(100):  # give up after too many tries - TODO what should limit be?
            resp = self.control_scheme.read_one_message(self.control_connection)
            if not resp:  # timeout , return None
                return None
            # skip any output types, for firmware versions that output on both ports
            if hasattr(resp, "msgtype") and resp.msgtype in OUTPUT_MESSAGE_TYPES:
                continue
            return resp

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

    def set_cfg_flash_no_wait(self, configurations):
        m = Message({'msgtype': b'CFG', 'mode': WRITE_FLASH, 'configurations': configurations})
        return self.send_control_no_wait(m)

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

    # enter bootloading, verify no ping response, retry up to a limit.
    def retry_enter_bootloading(self):
        for i in range(5):
            self.enter_bootloading()
            time.sleep(0.1)
            if self.ping() is None:
                return True
        return False

    # alternate version which checks if data output stops along with ping
    # currently user_program releases data port first, so can't use this version yet.
    def retry_enter_bootloading_with_data_port(self):
        for i in range(5):
            self.enter_bootloading()
            self.clear_data_port()
            time.sleep(0.1)
            remaining = self.data_connection.readall()
            if (self.ping() is None) and len(remaining) == 0:
                return True
        return False

    # makes lookup tables from flash apply to ram without restarting the unit.
    # unlike rst 0 and 2, this doesn't restart the unit, so it gets a response.
    # TODO - this is added in X3 0.0.27 firmware. Move into X3_Board class, or will other products have it too?
    def apply_lookup_tables(self):
        m = Message({'msgtype': b'RST', 'code': 3})
        return self.send_control_message(m)

    #send odometer message: over the udp odometer connection if exists, else config connection
    #config connection can take odometer messages but it could interfere with other config messaging
    def send_odometer(self, speed):
        m = Message({'msgtype': b'ODO', 'speed': speed})
        if hasattr(self, "odometer_connection") and self.odometer_connection:
            self.control_scheme.write_one_message(m, self.odometer_connection)
        else:
            self.send_control_no_wait(m)

    def send_init(self, configurations):
        m = Message({'msgtype': b'INI', 'configurations': configurations})
        return self.send_control_message(m)

    def send_update(self, configurations):
        m = Message({'msgtype': b'UPD', 'configurations': configurations})
        return self.send_control_message(m)

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
                elif configs_different(configs_dict, resp.configurations):
                    debug_print( f"{method.__name__}: {configs_dict} resp had wrong configurations, retrying.\nresponse:{resp.configurations}\nexpected:{configs_dict}")
                else:
                    return True

            except Exception as e:
                debug_print(f"error setting {expect_response_type}, retrying: {e}")
        debug_print(f"retry limit: could not set attributes {configs_dict}") #make this debug_print too?
        return False  # did not find it within retry limit

    # setter for multiple config types, does one value at a time with retries.
    # will use this for float types like SEN which need match with tolerance. use in other methods too?
    def set_configs(self, method, expect_response_type, configs_dict):
        all_success = []
        for k, v in configs_dict.items():
            success = False
            for i in range(COMMANDS_RETRY):
                try:
                    time.sleep(0.1)
                    if type(v) is str:
                        v_encoded = v.encode()
                    elif type(v) in [int, float]:
                        v_encoded = str(v).encode()
                    elif type(v) is bytes:
                        v_encoded = v
                    else:
                        debug_print(f"unexpected type {type(v)} for attribute {k}")
                        return False

                    resp = method({k: v_encoded})

                    if not resp:
                        debug_print(f"{method.__name__}: {k}: {v} resp failed check (no response), retrying")
                    elif not resp.valid:
                        debug_print(f"{method.__name__}: {k}: {v} resp failed check (invalid, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                    elif resp.msgtype != expect_response_type:
                        debug_print(f"{method.__name__}: {k}: {v} resp failed check (wrong type, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                    elif not hasattr(resp, "configurations"):
                        debug_print(f"{method.__name__}: {k}: {v} resp failed check (no configurations, type {resp.msgtype}, error {resp.err if hasattr(resp, 'err') else resp.error}), retrying")
                    elif k not in resp.configurations:
                        debug_print(f"{method.__name__}: {k}: {v} resp configurations missing {k} retrying.\nresponse:{resp.configurations}")
                    else:
                        ret_val = resp.configurations[k] # bytes type

                        #float: match with tolerance.
                        if type(v) is float:
                            ret_val = float(ret_val.decode())
                            if v == 0.0 and ret_val == 0.0:
                                success = True
                                break
                            elif abs((ret_val - v) / v) < 0.01: #expect 1/1000 match.
                                success = True
                                break
                            else:
                                debug_print(f"setter response value (float) does not match: {v} vs {ret_val}")
                        # any other types: compare equality as bytes
                        elif v_encoded == ret_val:
                            success = True
                            break
                        else:
                            debug_print(f"setter response value (non-float) does not match: {v} vs {ret_val}")
                except Exception as e:
                    debug_print(f"error setting {expect_response_type}, retrying: {e}")
            all_success.append(success)
            if not success:
                debug_print(f"retry limit: could not set attribute {k}")  # make this debug_print too?
        return all(all_success)

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

    # read baud configs in a way that works on old and new firmware.
    # before 1.3 release: "bau" config is baud for data and config ports
    # after: "bau" is data port baud only, "bau_input" is config port baud.
    def get_data_baud_flash(self):
        try:
            return int(self.retry_get_cfg_flash(["bau"])[0])
        except Exception as e:
            return None

    def get_control_baud_flash(self):
        try:
            bau_input_resp = self.retry_get_cfg_flash(["bau_input"])
            if bau_input_resp:
                return int(bau_input_resp[0])
            else:
                return int(self.retry_get_cfg_flash(["bau"])[0])
        except Exception as e:
            return None

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

    # use this to reset safely in programs
    # use new_baud only if baud changed, otherwise leave None
    def reset_with_waits(self, new_control_baud=None, new_data_baud=None):
        wait_time = 0.5
        time.sleep(wait_time)
        self.send_reset_regular()
        time.sleep(wait_time)

        # use the new baud if it changed, otherwise ping and other messages will fail.
        self.set_connection_baud(new_control_baud, new_data_baud)

        while self.ping() is None:
            #TODO - should this time out eventually -> retry connection?
            time.sleep(wait_time)

    def find_bootloader_name(self):
        windows_bootloader_name = "crossplatform_bootloader_windows_x86_release.exe"
        linux_arm_bootloader_name = "crossplatform_bootloader_linux_arm"
        linux_x86_bootloader_name = "crossplatform_bootloader_linux_x86"
        bootloader_v2_name = "HtxAurixBootLoader_v2.0.0.exe"  # IMU+ still requires this, for Windows only.

        linux_bootloaders = {
            "Linux x86": linux_x86_bootloader_name,
            "Linux ARM": linux_arm_bootloader_name,
        }

        try:
            prod_id = self.retry_get_pid().decode()
        except Exception as e:
            print("could not read product id -> canceled bootloading")
            return

        computer_os = os_type()
        computer_processor = processor_type()

        if "IMU+" in prod_id:
            # only IMU+ needs V2 bootloader. IMU/EVK/GNSS/X3 are all V1.
            if computer_os.lower() == "windows":
                return bootloader_v2_name
            else:
                show_and_pause("Bootloader requires Windows OS for IMU+ product")
                return
        elif computer_os.lower() == "windows":
            return windows_bootloader_name
        elif computer_os.lower() == "linux":
            if computer_processor.lower() == "x86":
                return linux_x86_bootloader_name
            elif computer_processor.lower() == "arm":
                return linux_arm_bootloader_name
            else:
                print(f"\nArchitecture not recognized for Linux: {computer_processor}")
                print("Select an option that matches your system, or cancel if none match:")
                options = list(linux_bootloaders.keys()) + ["cancel"]
                chosen = options[cutie.select(options)]
                if chosen == "cancel":
                    return
                return linux_bootloaders[chosen]
        else:
            show_and_pause(f"\nBootloader does not support {computer_os} Operating System")
            return
        # TODO should it check for 32 bit, or Windows ARM vs x86?

    # bootloader function taking hex file path and expected version after
    def bootload_with_file_path(self, bootloader_path, hex_file_path, expected_version_after="unknown", num_attempts=1):
        if bootloader_path is None:
            return
        print(f"\nUpdating firmware with {bootloader_path}")
        print("\nKeep plugged in until update finishes.")
        print("If update fails: cycle power, then connect user_program again to check firmware version.")

        if not self.retry_enter_bootloading():
            show_and_pause("\nCould not enter update mode: please check cable connections and try again")
            return

        self.release_connections()
        # send bootloader commands. TODO - should it use subprocess.call() instead of os.system()?
        port_prefix, port_number = split_port_name(self.data_port_name)

        computer_os = os_type()
        if computer_os.lower() == "windows":
            subprocess.call([bootloader_path, 'START', 'TC36X', '6', str(port_number), '115200', '0', '0', '0', '0'])
            subprocess.call([bootloader_path, 'PROGRAM', hex_file_path])
            subprocess.call([bootloader_path, 'END'])

        elif computer_os.lower() == "linux":
            # on Linux: make the bootloader executable first, and "sudo" all commands to make sure it has permissions.
            subprocess.call(['sudo', 'chmod', '+x', bootloader_path])
            subprocess.call(['sudo', bootloader_path, 'START', 'TC36X', '6', str(port_number), '115200', '0', '0', '0', '0'])
            subprocess.call(['sudo', bootloader_path, 'PROGRAM', hex_file_path])
            subprocess.call(['sudo', bootloader_path, 'END'])
        
        else:
            # find_bootloader_name should already catch if OS not supported.
            show_and_pause(f"Bootloader does not support {computer_os} Operating System")
            return

        # connect again after disconnect (this is specific to serial connection). TODO - handle errors here?
        time.sleep(1)  # pause to let it restart.
        self.reconnect_serial()

        # Check SW Version
        version_after_resp = self.retry_get_version()
        version_after_resp_string = version_after_resp.decode() if version_after_resp else "None"

        if (version_after_resp_string == expected_version_after) or (expected_version_after == "unknown"):
            print(f"\nsuccessfully updated to version {version_after_resp_string}")
        else:
            print(f"\nversion afterward {version_after_resp_string} did not match expected {expected_version_after}")
            print("check version and retry update if needed")


    # to set vehicle configs in terminal with cutie. put here to share with user_program.py and config.py
    def set_veh_terminal_interface(self, allowed_configs=None):

        # only allow writing the configs it can read
        # by default, read from vehicle configs here. or can take allowed configs as an argument
        if allowed_configs is None:
            read_configs = self.retry_get_veh_flash_all()
            allowed_configs = list(read_configs.keys())

        # choose which vehicle config to set, only give options from allowed_configs
        allow_veh_fields = VEH_FIELDS_MAIN.copy()
        for name, code_or_tuple in VEH_FIELDS_MAIN.items():
            # skip bcal since antenna baseline has its own menu which sets bsl and bcal.
            if code_or_tuple == "bcal":
                try:
                    del(allow_veh_fields[name])  # skip these, will handle separately
                except KeyError:
                    pass
            if type(code_or_tuple) is tuple:
                # xyz groupings: check for the first code, since it should have all or none
                expect_code = code_or_tuple[0][1]
            else:
                # single config: allow it if it's in allowed_configs
                expect_code = code_or_tuple

            if expect_code not in allowed_configs:
                try:
                    del(allow_veh_fields[name])
                except KeyError:
                    pass

        options = list(allow_veh_fields.keys())
        options += ["cancel"]

        print("\nselect configurations to write\n")
        chosen = options[cutie.select(options)]
        if chosen == "cancel":
            return

        # enter the components of the chosen config
        print(f"\nEnter {chosen}:")
        args = {}  # dict of VEH to write
        grouping = VEH_FIELDS_MAIN[chosen]

        # combined menu for bsl and bcal
        if grouping == "bsl":
            manually_text = "Enter manually"
            auto_text = "Auto calibrate (requires open sky view)"
            lever_arm_text = "Calculate from lever arms (must be accurate to 1 cm)"
            cancel_text = "cancel"
            baseline_options = [manually_text, auto_text, lever_arm_text, cancel_text]
            bsl_chosen = baseline_options[cutie.select(baseline_options)]
            if bsl_chosen == cancel_text:
                return
            elif bsl_chosen == manually_text:
                self.retry_set_veh_flash({"bcal": b'99'})  # cancel any calibration in progress first
                enter_value = input("\nEnter antenna baseline in meters (must be accurate to 1 cm):\n")
                args["bsl"] = enter_value.encode()
            elif bsl_chosen == auto_text:
                show_and_pause("\nEnsure you are in open skies and your antennae are fixed in their position.")
                args["bcal"] = b'1'
            elif bsl_chosen == lever_arm_text:
                args["bcal"] = b'2'

        # menu for zupt calibration
        elif grouping == "zcal":
            auto_text = "Auto calibrate"
            reset_text = "Reset"
            cancel_text = "cancel"
            baseline_options = [auto_text, reset_text, cancel_text]
            chosen_option = baseline_options[cutie.select(baseline_options)]
            if chosen_option == cancel_text:
                return
            elif chosen_option == auto_text:
                args["zcal"] = b'1'
            elif chosen_option == reset_text:
                args["zcal"] = b'3'

        # grouping like x/y/z parts: ask for each of them
        elif type(grouping) is tuple:
            for axis, code in grouping:
                value = input(axis + ": ").encode()
                args[code] = value

        # single config: just ask for the one
        elif type(grouping) is str:
            if grouping in VEH_VALUE_OPTIONS:
                # if there are options: pick from the options, showing as a name if there are names.
                value_options = VEH_VALUE_OPTIONS[grouping]
                name_options = [VEH_VALUE_NAMES.get((grouping, val), val) for val in value_options]
                name_options.append("cancel")
                chosen_index = cutie.select(name_options)
                if name_options[chosen_index] == "cancel":
                    return
                value = value_options[chosen_index].encode()
            else:
                value = input().encode()
            args[grouping] = value

        write_success = self.retry_set_veh_flash(args)
        # skip error check for now since it thinks response 1.000000 doesn't match value 1, etc. TODO - check as number?
        if not write_success:
            show_and_pause("Error setting Vehicle configs: try again or check connections")

    # change it to return a string that can be printed. on fail, return emtpy string.
    def read_all_veh_terminal_interface(self, veh_configs=None):
        # get configs by default, or allow passing them.
        if veh_configs is None:
            veh_configs = self.retry_get_veh_flash_all()

        if veh_configs:  # read success -> print the configs
            # if proper_response(resp, b'VEH'):
            out_str = "\nVehicle Configurations:  (all vectors in meters with center of ANELLO unit as origin)"

            for name, grouping in VEH_FIELDS_MAIN.items():

                # don't show baseline calibration here, since we have separate print for calibration in progress.
                if grouping == "bcal":
                    continue

                decimal_places = 3

                # tuple means multi-part like x/y/z: show all in one line, blank any missing
                if type(grouping) is tuple:
                    line = "\n    " + name + ": "
                    has_any_axis = False
                    for axis, code in grouping:
                        named_value = "--------"  # show blank if not found
                        if code in veh_configs:
                            raw_val = veh_configs[code].decode()
                            # show the name if there is one
                            named_value = VEH_VALUE_NAMES.get((code, raw_val), raw_val)
                            has_any_axis = True
                        line += f"{axis}: {truncate_decimal(named_value, decimal_places, 'm')}    "
                    # show the x,y,z grouping only if at least one was in the read.
                    if has_any_axis:
                        out_str += line

                # single config: show it only if in the response.
                elif type(grouping) is str and grouping in veh_configs:
                    raw_val = veh_configs[grouping].decode()
                    named_value = VEH_VALUE_NAMES.get((grouping, raw_val), raw_val)

                    # clearer explanation for baseline calibration status.
                    if grouping == "bcal" and raw_val != "0":
                        named_value = f"In Progress ({named_value})"

                    # also show zupt calibration in a simplified way.
                    elif grouping == "zcal":
                        if raw_val == "0":
                            # not calibrating now: check if any nonzero values. After reset or on new product, all are 0
                            values_are_nonzero = [(float(v) != 0.0) for (k, v) in veh_configs.items() if k in VEH_ZUPT_CAL_LIST]
                            if any(values_are_nonzero):
                                named_value = "Calibrated"
                            else:
                                named_value = "Not Calibrated"
                        elif raw_val == "1":
                            named_value = "Calibration in progress"

                    line = f"\n    {name}: {truncate_decimal(named_value, decimal_places, 'm')}"
                    out_str += line
            return out_str
        else:
            return ""  # indicates fail


# compare expected vs actual configs and print the differences - copied from config.py
# remove config_type_str for simplicity -> do tolerance abs check for anything that can convert to float?
def configs_different(expected_configs, confirmed_configs):
    #actual_user = read_cfg.configurations
    veh_tolerance = 0.000001 #have tolerance for floats in vehicle . TODO - use this for any float type?
    differences = "" #TODO - change to dictionary or tuple from string?
    for name in expected_configs:

        # try comparing as floats: may have ValueError
        try:
            float_difference = abs(float(expected_configs[name]) - float(confirmed_configs[name]))
            both_float = True
        except ValueError:
            float_difference = None
            both_float = False

        if name not in confirmed_configs:
            differences += f"{name}: expected {expected_configs[name]} , was missing\n"
        elif both_float and float_difference < veh_tolerance:
            continue #skip the != check below since it's close enough
        elif expected_configs[name] != confirmed_configs[name]: #need tolerance for float types
            differences += f"{name}: expected {expected_configs[name]} , was {confirmed_configs[name]}\n"
    if differences:
        debug_print(f"\nSome configs failed to write. differences:\n{differences}")
    else:
        debug_print(f"\nAll configs wrote successfully")
    return differences


def show_and_pause(text):
    print(text)
    print("enter to continue:")
    input()


def truncate_decimal(num_or_str, places, unit=None):
    try:
        # try to format with that many places as long as it can be converted to float
        out_str = f"{float(num_or_str):.{places}f}"
        # put the unit here if any
        if unit is not None:
            out_str += f" {unit}"
        return out_str
    except (ValueError, TypeError):
        # if can't convert, just return the original thing (could be None, non-numerical string, etc)
        # don't add the unit since it's non-numerical
        return num_or_str


# use recursive dict to show differences arranged the same way as the tested dictionaries.
# expect everything in expect_dict to be in actual_dict, but not the other way around.
# returns {} if everything is as expected (no differences)
# could also try: deepdiff.DeepDiff(expect_dict, actual_dict) and check for only "dictionary_item_added"
def config_dict_differences(expect_dict, actual_dict):
    diffs = {}
    for k, expect_val in expect_dict.items():
        if k not in actual_dict:
            diffs[k] = {"expected": expect_val, "actual": "missing"}
            continue
        actual_val = actual_dict[k]

        # check recursively in sub-dictionaries.
        if (type(expect_val) is dict) and (type(actual_val) is dict):
            recursive_diffs = config_dict_differences(expect_val, actual_val)
            if recursive_diffs != {}:
                diffs[k] = recursive_diffs
        else:
            if expect_val != actual_val:
                diffs[k] = {"expected": expect_val, "actual": actual_val}
    return diffs


# split port name into prefix and numbers
# Windows COM1, Linux /dev/ttyUSB1, etc.
def split_port_name(port_name):
    try:
        pattern = re.compile(r'\d*$')  # match as many digits as possible at the end of the string
        m = pattern.search(port_name)
        prefix, number = port_name[:m.start()], port_name[m.start():]
        return prefix, int(number)
    except Exception as e:
        return None, None
