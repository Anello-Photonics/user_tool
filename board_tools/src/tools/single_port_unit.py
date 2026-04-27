# subclass of IMUBoard to do data and config messaging on one serial port
# can use this for marine box, also for X3 on one port.

import sys
from pathlib import Path
ABS_PATH = Path(__file__)
sys.path.append(str(ABS_PATH.parent.parent.parent.parent))
import time
import os
import json
import cutie

try:
    from board import IMUBoard, DEFAULT_PORT_LATENCY_S, debug_print, show_and_pause
    from binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from message_scheme import Message
    from readable_scheme import OUTPUT_MESSAGE_TYPES, ReadableScheme
    from connection import *
except ModuleNotFoundError:
    from tools.board import IMUBoard, DEFAULT_PORT_LATENCY_S, debug_print, show_and_pause
    from tools.binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from tools.message_scheme import Message
    from tools.readable_scheme import OUTPUT_MESSAGE_TYPES, ReadableScheme
    from tools.connection import *


class Single_Port_Unit(IMUBoard):

    def __init__(self, serial_port=None, baud=DEFAULT_BAUD, parser=ReadableScheme(), try_manual=True, timeout=None):

        self.parser = parser  # IMUBoard has separate data_scheme, control_scheme
        self.serial_baud = baud  # IMUBoard has separate control_baud, data_baud
        self.timeout = timeout
        self.serial_connection = None
        self.port_name = None
        self.connect_success = None

        success = self.connect_to_ports(serial_port, baud)  # todo update after defining connect_to_ports
        if try_manual and not success:
            print(f"failed to connect at port = {serial_port},  baud = {baud}")
            self.connect_manually()
        self.msg_format = b'1' #default ascii to make sure this is defined

    def __repr__(self):
        return "Single_Port_Unit: "+str(self.__dict__)

    # for anything that wants data_connection or control_connection, just give serial_connection
    # if anything wants to set these, would need to add: @data_connection.setter , @control_connection.setter methods
    @property
    def data_connection(self):
        return self.serial_connection

    @property
    def control_connection(self):
        return self.serial_connection

    @property
    def control_port_name(self):
        return self.port_name

    @property
    def data_port_name(self):
        return self.port_name

    @property
    def control_baud(self):
        return self.serial_baud

    @property
    def data_baud(self):
        return self.serial_baud

    @classmethod
    def auto(cls, manual_fallback=True):
        board = cls()
        try:
            success = True
            # read/write connection settings with set_data_port=False , use only "control" port and baud
            serial_port, unused_port, serial_baud, unused_baud = board.read_connection_settings()
            if not serial_port:  # or not data_port:
                success = False
            success = success and board.connect_to_ports(serial_port, serial_baud)
        except Exception as e:
            success = False
        if success:
            board.write_connection_settings()  # should do only on success - from auto or from manual
        else:
            # file not exist, or connecting based on file fails -> detect the settings, then save in a file
            board.release_connections()
            if board.auto_no_cache(manual_fallback):  # None on fail
                board.write_connection_settings()  # also counts as success -> save.
            else:
                board.release_connections()
                return None
        return board

        # with no cached value - auto connect by trying baud 921600 for all ports first, then other bauds
    def auto_no_cache(self, manual_fallback=True):
        bauds = X3_TRY_BAUD_ORDER.copy()  # already in preferred order
        for control_baud in bauds:
            outcome = self.auto_port(control_baud)
            if outcome:  # (control_port, data_port) if succeeded, None if failed
                return True
            else:
                continue
        if manual_fallback:
            return self.connect_manually(auto_baud=False)
        return None # connect_manually returns None on fail

    # detect ports with known baud rate, returns ports or None on fail
    def auto_port(self, fixed_baud):
        debug_print(f"auto_port, baud = {fixed_baud}")
        port_names = self.list_ports()
        for try_port in reversed(port_names):
            try:
                self.serial_connection = SerialConnection(port=try_port, baud=fixed_baud, timeout=TIMEOUT_AUTOBAUD)
                if self.check_port():  # success - can set things
                    print(f"connected control port: {try_port}")
                    self.port_name = try_port
                    self.serial_connection.set_timeout(TIMEOUT_REGULAR)
                    self.serial_baud = fixed_baud

                    return try_port, fixed_baud
                else:
                    self.release_connections()
            except Exception as e:
                debug_print("skipping over port " + try_port + " with error: " + str(e))
                self.release_connections()
                continue
        # no ports worked - clean up and report fail
        self.release_connections()
        return None

    def read_connection_settings(self):
        try:
            cache_path = os.path.join(os.path.dirname(__file__), CONNECTION_CACHE_SINGLE_PORT)
            with open(cache_path, 'r') as settings_file:
                settings = json.load(settings_file)
                serial_port = settings["serial_port"]
                serial_baud = settings["serial_baud"]
                return serial_port, serial_baud,
        except Exception as e:
            return None

    def write_connection_settings(self):
        try:
            serial_port, serial_baud = self.port_name, self.serial_baud
            # avoid writing null for ports
            if serial_port is None:
                return None
            settings = {"serial_port": serial_port, "serial_baud": serial_baud}
            cache_path = os.path.join(os.path.dirname(__file__), CONNECTION_CACHE_SINGLE_PORT)
            with open(cache_path, 'w') as settings_file:
                json.dump(settings, settings_file)
        except Exception as e:
            print("error writing connection settings: "+str(e))
            return None

    def connect_to_ports(self, serial_port=None, serial_baud=DEFAULT_BAUD):
        success = True
        timeout = self.timeout if self.timeout else TIMEOUT_REGULAR
        try:
            if serial_port is None:
                self.serial_connection = DummyConnection()
            else:
                self.serial_connection = SerialConnection(serial_port, serial_baud, timeout)
                self.serial_baud = serial_baud

            success = (serial_port is None) or self.check_port()

            if not success: #try other baud rates, then check again
                detected_baud = self.auto_detect_baud()
                success = detected_baud is not None  #((serial_port is None) or self.check_port())
                #print(f"trying on baud {baud} instead: success is {success}")

        except Exception as e:  # serial error
            debug_print("error: "+str(e))
            success = False
        if success:
            self.port_name = serial_port
        else:
            self.release_connections()

        self.connect_success = success
        return success

    # check if port is correct. use ping for now - could also check for output messages
    def check_port(self):
        response = self.ping()
        return response and response.valid and response.msgtype == b'PNG'

    def clear_inputs(self):
        self.clear_connection(self.serial_connection, self.parser, DEFAULT_PORT_LATENCY_S)

    # programs for other products expect clear_data_port or clear_control_port
    def clear_data_port(self):
        self.clear_inputs()

    def clear_control_port(self):
        self.clear_inputs()

    def send_control_message(self, message):
        self.clear_inputs()
        self.parser.write_one_message(message, self.serial_connection)
        # time.sleep(1e-1)  try without sleep since this is not for UDP.
        resp = self.read_one_control_message()
        if resp:
            return resp
        else:  # timed out waiting for response -> list error as invalid message
            m = Message()
            m.valid = False
            m.error = "Timeout"

    def send_control_no_wait(self, message):
        self.parser.write_one_message(message, self.serial_connection)

    # reads one message of any type
    def read_one_message(self, num_attempts=1):
        return self.parser.read_one_message(self.serial_connection)

    # read messages until it's not an output type, so it's a config response.
    def read_one_control_message(self):
        for i in range(100):  # give up after too many tries - TODO what should limit be? this takes a long time if odr=1
            resp = self.read_one_message()
            if not resp:  # timeout , return None
                return None
            # # skip any output types for firmware versions that output on both ports.
            # # TODO - should it check for the expected message type instead? same type as request, or APERR
            if not hasattr(resp, "msgtype") or resp.msgtype in OUTPUT_MESSAGE_TYPES:
                continue
            return resp

    def release_connections(self):
        if hasattr(self, "serial_connection") and self.serial_connection is not None:
            self.serial_connection.close()

    def connect_manually(self, auto_baud=True):  # todo - does it need set_data_port, set_config_port dummy args for compatibility?
        port_names = self.list_ports()
        if not port_names:
            show_and_pause("no ports found.")
            return None
        # Add option to manually enter port path (for non-standard ports like /dev/ttyUART*)
        port_names.append("enter manually")
        port_names.append("cancel")

        data_port = None
        while True:
            try:
                print("\nselect serial port")
                data_port = port_names[cutie.select(port_names, selected_index=0)]
                if data_port == "cancel":
                    return None
                if data_port == "enter manually":
                    data_port = input("enter data port path (e.g. /dev/ttyUART0): ").strip()
                    if not data_port:
                        continue

                # connect with default baud. then check baud automatically, or ask for baud if that fails.
                data_con = SerialConnection(data_port, self.serial_baud, timeout=TIMEOUT_REGULAR)
                self.serial_connection = data_con
                # baud: use manual select if auto_baud False or if auto detect fails
                baud = None
                if auto_baud:
                    baud = self.auto_detect_baud()
                if baud is None:
                    baud_options = ALLOWED_BAUD_SORTED.copy()
                    baud_options.append("auto detect")
                    print("\nselect baud rate")
                    baud = baud_options[cutie.select(baud_options, selected_index=0)]
                    if baud == "auto detect":
                        self.auto_detect_baud()
                    else:
                        self.set_connection_baud(baud)
                # todo - should it do ping or other test to check connection here, or just believe you picked the right port?
                # todo - call self.write_connection_settings here?
                print(f"\nconnected to data port: {data_port}")
                self.port_name = data_port
                return True

            except serial.serialutil.SerialException as e:
                print(f"\nerror connecting to {data_port} - wrong port number or port is busy")
                continue

    def auto_detect_baud(self):
        bauds = X3_TRY_BAUD_ORDER.copy() #already in preferred order
        for baud in bauds:
            self.serial_connection.set_baud(baud)
            self.serial_baud = baud
            if self.check_port():
                return baud
        return None

    # re-implement reset_with_waits with one port and one baud
    # fake_extra_baud is not used, but keeps it compatible with IMUBoard.reset_with_waits(new_control_baud, new_data_baud)
    def reset_with_waits(self, new_baud=None, fake_extra_baud=None):
        wait_time = 0.5
        time.sleep(wait_time)
        self.send_reset_regular()
        time.sleep(wait_time)

        # use the new baud if it changed, otherwise ping and other messages will fail.
        self.set_connection_baud(new_baud)

        time_before = time.time()
        while self.ping() is None:
            if time.time() - time_before > 10:
                return False # indicate error in restart
            time.sleep(wait_time)

        return True #indicate successful restart

    def set_connection_baud(self, new_baud=None):
        if new_baud:
            self.serial_baud = new_baud
            self.serial_connection.set_baud(new_baud)

        # clear any bad data at the old baud
        self.serial_connection.readall()

    # reimplement clear_connections, since the IMUBoard method can loop forever for marine box.
    def clear_connection(self, connection, scheme, wait_time_seconds):
        # temporarily set timeout to zero, and read data until read is empty
        connection.reset_input_buffer()
        old_timeout = connection.get_timeout()
        try:
            connection.set_timeout(0)

            last_data = connection.readall()
            iters = 0
            while last_data and (iters < 100):
                last_data = connection.readall()
                iters += 1

            time.sleep(wait_time_seconds)

            iters = 0
            last_data = connection.readall()
            while last_data and (iters < 100):
                last_data = connection.readall()
                iters += 1

        finally:
            connection.set_timeout(old_timeout)


if __name__ == "__main__":
    test_port = "COM24" # x3 on my usb hub
    #test_port = "COM29"  #my laptop on the marine box usb hub
    test_baud = 460800
    # test_baud = 115200 # wrong baud on purpose -> it should automatically find the right baud.

    # unit = Single_Port_Unit(test_port, test_baud)
    # print(unit)
    # print(f"\nping: {unit.ping()}")

    print("auto connect unit:")
    unit2 = Single_Port_Unit.auto()
    print(f"\nping: {unit2.ping()}")
