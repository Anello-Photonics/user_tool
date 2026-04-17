import sys
import time
import os
from pathlib import Path
ABS_PATH = Path(__file__)
sys.path.append(str(ABS_PATH.parent.parent.parent.parent))
import subprocess
import re
import time
import serial
import cutie
from user_program import show_and_pause

try:
    from board import IMUBoard, DEFAULT_PORT_LATENCY_S, debug_print, show_and_pause
    from single_port_unit import Single_Port_Unit
    from binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from connection import *
    from detect_os import os_type, processor_type
except ModuleNotFoundError:
    from tools.board import IMUBoard, DEFAULT_PORT_LATENCY_S, debug_print, show_and_pause
    from tools.single_port_unit import Single_Port_Unit
    from tools.binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from tools.connection import *
    from tools.detect_os import os_type, processor_type


class X3_Single_Port(Single_Port_Unit):
    # single port unit: def __init__(self, serial_port=None, baud=DEFAULT_BAUD, parser=ReadableScheme(), try_manual=True, timeout=None):
    def __init__(self, serial_port=None, baud=460800, parser=Binary_and_ASCII_Scheme(), try_manual=True, timeout=None):
        super().__init__(serial_port=serial_port, baud=baud, parser=parser, try_manual=try_manual, timeout=timeout)

    # todo - implement connect_manually here, IMUBoard.connect_manually expects data_connection attribute
    # or implement it in single_port_unit class

        # bootloader function taking hex file path and expected version after
    def bootload_with_file_path(self, bootloader_path, hex_file_path, com_port=None, expected_version_after="unknown", num_attempts=1):
        if bootloader_path is None:
            return
        print(f"\nBootloading with {bootloader_path}")

        print("\nKeep plugged in until upgrade finishes.")
        print("If bootload fails: cycle power, then connect user_program again to check firmware version.")

        self.enter_bootloading()
        self.release_connections()
        # send bootloader commands. TODO - should it use subprocess.call() instead of os.system()?
        if com_port is None:
            com_port = self.data_port_name
        port_prefix, port_number = split_port_name(com_port)

        print(f"Using port {self.data_port_name} split into prefix '{port_prefix}' and number {port_number}")

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


     # connect again on serial after disconnecting. TODO - make a version for ethernet too?
    def reconnect_serial(self):
        #self.connect_to_ports(data_port=self.data_port_name, control_port=self.control_port_name)
        # todo - clear config and data ports here? or inside init?
        self.__init__(self.data_port_name, baud=self.data_baud,
                      parser=Binary_and_ASCII_Scheme())  

    # detect ports with known baud rate, returns ports or None on fail
    def auto_port(self, fixed_baud):
        debug_print(f"auto_port, baud = {fixed_baud}")
        port_names = self.list_ports()
        for try_port in port_names:
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
        
    @classmethod
    def auto(cls, manual_fallback=True):
        board = cls()
        try:
            success = True
            # read/write connection settings with set_data_port=False , use only "control" port and baud
            unused_port, serial_port, unused_baud, serial_baud = board.read_connection_settings()
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
