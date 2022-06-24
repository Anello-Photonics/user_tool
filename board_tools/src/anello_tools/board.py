import os
import cutie
import json
import subprocess
import os
import re
import serial.tools.list_ports as list_ports
try:  # importing from inside the package
    from readable_scheme import *
    from message_scheme import Message
    from connection import *
    from config.board_config import *
except ModuleNotFoundError:  # importing from outside the package
    from anello_tools.readable_scheme import *
    from anello_tools.message_scheme import Message
    from anello_tools.connection import *
    from anello_tools.config.board_config import *


# abstraction of the board and its inputs and outputs
class IMUBoard:

    def __init__(self, data_port=None, control_port=None, baud=DEFAULT_BAUD, scheme=ReadableScheme(), try_manual=True, timeout=None):
        self.scheme = scheme
        self.timeout = timeout
        success = self.connect_to_ports(data_port, control_port, baud)
        if try_manual and not success:
            print("failed to connect with control port = "+str(control_port)+", data port = "+str(data_port)+", baud = "+str(baud))
            self.connect_manually()

    def __repr__(self):
        return "IMUBoard: "+str(self.__dict__)

    @classmethod
    def auto(cls, set_data_port=True):
        board = cls()
        try:
            success = True
            control_port, data_port, baud = board.read_connection_settings()
            if not control_port or not data_port:
                success = False
            if not set_data_port:
                data_port = None
            success = success and board.connect_to_ports(data_port, control_port, baud)
        except Exception as e:
            success = False
            #print("connect from cache failed: " + str(e))
        if not success:
            # file not exist, or connecting based on file fails -> detect the settings, then save in a file
            board.release_connections()
            board.auto_no_cache(set_data_port)
            board.write_connection_settings()
        return board

    #initialize on udp. TODO - could put cache options here too.
    @classmethod
    def from_udp(cls, ip, data_port, control_port):
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
        except Exception as e:
            print(e)
            return None
        return board

    def read_connection_settings(self):
        try:
            cache_path = os.path.join(os.path.dirname(__file__), CONNECTION_CACHE)
            #print("reading from "+str(cache_path))
            with open(cache_path, 'r') as settings_file:
                settings = json.load(settings_file)
                control, data, baud = settings["control_port"], settings["data_port"], settings["baud"]
                if data is None:
                    data = self.compute_data_port()
                return control, data, baud
        except Exception as e:
            #print("error reading connection settings: "+str(e))
            return None

    def write_connection_settings(self):
        try:
            control, data, baud = self.control_port_name, self.data_port_name, self.baud
            # avoid writing null for ports
            if control is None:
                return None
            if data is None:
                data = self.compute_data_port()
            settings = {"control_port": control, "data_port": data, "baud": baud}
            cache_path = os.path.join(os.path.dirname(__file__), CONNECTION_CACHE)
            #print("writing to " + str(cache_path))
            with open(cache_path, 'w') as settings_file:
                json.dump(settings, settings_file)
        except Exception as e:
            print("error writing connection settings: "+str(e))
            return None

    # connect to the port numbers. return true if succesful connection, false if serial error or ping fails.
    def connect_to_ports(self, data_port=None, control_port=None, baud=DEFAULT_BAUD):
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
            success = (control_port is None) or self.check_control_port()
            # TODO - verify data connection? but can't tell anything if odr=0
        except Exception as e:  # serial error
            #print("error: "+str(e))
            success = False
        if success:
            self.data_port_name = data_port
            self.control_port_name = control_port
            self.baud = baud
        else:
            self.release_connections()
        return success

    # check control port by pinging.
    def check_control_port(self):
        response = self.ping()
        return response and response.valid and response.msgtype == b'PNG'

    def clear_inputs(self):
        self.data_connection.reset_input_buffer()
        self.control_connection.reset_input_buffer()

    def release_connections(self):
        if hasattr(self, "data_connection"):
            self.data_connection.close()
        if hasattr(self, "control_connection"):
            self.control_connection.close()

    def reset_connections(self):
        self.release_connections()
        self.__init__(self.data_port_name, self.control_port_name, self.baud, self.scheme)

    def list_ports(self):
        return sorted([p.device for p in list_ports.comports()])

    # with no cached value - auto connect by trying baud 921600 for all ports first, then other bauds
    def auto_no_cache(self, set_data_port=True):
        #print("auto no cache")
        bauds = ALLOWED_BAUD.copy()
        bauds.reverse()  # start with high bauds which are more likely
        for baud in bauds:
            outcome = self.auto_port(baud, set_data_port)
            if outcome: #(control_port, data_port) if succeeded, None if failed
                return outcome + (baud,)
            else:
                continue
        return self.connect_manually(set_data_port)

        # detect ports with known baud rate
    def auto_port(self, baud, set_data_port=True):
        port_names = self.list_ports()
        for control_port in reversed(port_names):
            try:
                self.control_connection = SerialConnection(port=control_port, baud=baud, timeout=TIMEOUT_AUTOBAUD)
                if self.check_control_port():  # success - can set things
                    self.control_port_name = control_port
                    self.control_connection.set_timeout(TIMEOUT_REGULAR)
                    self.baud = baud
                    data_port = None
                    if set_data_port:
                        data_port = self.compute_data_port()
                        self.data_connection = SerialConnection(data_port, baud)
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

    # test baud using ping to find the right one, set it for control and data ports
    # requires board to have control_connection and data_connection already set to the right ports
    def auto_detect_baud(self):
        bauds = ALLOWED_BAUD.copy()
        bauds.reverse()  # start with high bauds which are more likely
        for baud in bauds:
            self.control_connection.set_baud(baud)
            self.control_connection.reset_input_buffer()
            response = self.ping()
            if response and response.valid and response.msgtype == b'PNG':
                self.data_connection.set_baud(baud)
                self.data_connection.reset_input_buffer()
                return baud
        return None

    def connect_manually(self, set_data_port=False):
        # get the port numbers
        # stream = os.popen("python -m serial.anello_tools.list_ports")
        # port_names = [line.strip() for line in stream.readlines()]
        port_names = self.list_ports()
        if not port_names:
            print("no ports found.")
            return None

        print("\nmanually select ports")
        # connect to data port if we want to
        if set_data_port:
            connected = False
            while not connected:
                try:
                    print("\nselect data port (should be lowest of the 4 consecutive ports)")
                    data_port = port_names[cutie.select(port_names, selected_index=0)]
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
                control_port = port_names[cutie.select(port_names, selected_index=3)]
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
        self.write_connection_settings()
        return control_port, data_port, baud #{"control port": port, "data port": data_port, "baud": baud}

    # reads one message - returns None if there is no message
    # this does not error on None since Session loop just keeps waiting
    def read_one_message(self):
        message = self.scheme.read_one_message(self.data_connection)
        return message

    # send a message on the control channel
    # we expect a response for each control message, so show an error if there is none.
    def send_control_message(self, message):
        self.scheme.write_one_message(message, self.control_connection)
        resp = self.read_one_control_message()
        if resp:
            return resp
        else:  # timed out waiting for response -> list error as invalid message
            m = Message()
            m.valid = False
            m.error = "Timeout"

    # send and don't wait for response- use this for odo message
    def send_control_no_wait(self, message):
        self.scheme.write_one_message(message, self.control_connection)

    # read control message - for example response after we send a control message
    def read_one_control_message(self):
        return self.scheme.read_one_message(self.control_connection)

    # build and send messages by type: board methods
    def get_version(self):
        m = Message({'msgtype': b'VER'})
        return self.send_control_message(m)

    def get_serial(self):
        m = Message({'msgtype': b'SER'})
        return self.send_control_message(m)

    def get_pid(self):
        m = Message({'msgtype': b'PID'})
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

    def send_odometer(self, speed):
        m = Message({'msgtype': b'ODO', 'speed': speed})
        return self.send_control_no_wait(m)

    # enable odometer config in ram or flash - need this for test setup since odo=off can't set to other values
    def enable_odo_ram(self):
        return self.set_cfg({"odo": b'on'})

    def enable_odo_flash(self):
        return self.set_cfg_flash({"odo": b'off'})
