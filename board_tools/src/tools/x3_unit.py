# X3 subclass of IMUBoard, to fix connecting and config reading on X3
# handle mixed binary or ASCII output messaging with ASCII config messaging

import sys
import time
from pathlib import Path
ABS_PATH = Path(__file__)
sys.path.append(str(ABS_PATH.parent.parent.parent.parent))

try:
    from board import IMUBoard, DEFAULT_PORT_LATENCY_S, MAX_PORT_LATENCY_S
    from binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from message_scheme import Message
    from readable_scheme import OUTPUT_MESSAGE_TYPES
    from connection import *
except ModuleNotFoundError:
    from tools.board import IMUBoard, DEFAULT_PORT_LATENCY_S, MAX_PORT_LATENCY_S
    from tools.binary_and_ascii_scheme import Binary_and_ASCII_Scheme
    from tools.message_scheme import Message
    from tools.readable_scheme import OUTPUT_MESSAGE_TYPES
    from tools.connection import *

class X3_Unit(IMUBoard):

    # put any X3 specific methods here, otherwise it uses the IMUBoard method

    # X3 unit init: change default schemes to mixed parser.
    def __init__(self, data_port=None, control_port=None, baud=460800, data_baud=None, data_scheme=Binary_and_ASCII_Scheme(),
                 control_scheme=Binary_and_ASCII_Scheme(), try_manual=True, timeout=None):
        super().__init__(data_port=data_port, control_port=control_port, baud=baud, data_baud=data_baud,
                         data_scheme=data_scheme, control_scheme=control_scheme, try_manual=try_manual, timeout=timeout)

    @staticmethod
    def parse_png_code(response):
        if not response or not response.valid or getattr(response, "msgtype", None) != b'PNG':
            return None
        code = getattr(response, "code", None)
        if code is None:
            return None
        try:
            if isinstance(code, bytes):
                code = code.decode(errors="ignore").strip()
            if isinstance(code, str):
                code = code.strip()
            return int(code)
        except Exception:
            return None

    # indicate if it's proper config port.
    # accept ping response of 2 (X3 config port) or 0 (old X3, other products), but not 1 (X3 data port)
    def check_control_port(self):
        for _ in range(3):
            code = self.parse_png_code(self.ping())
            if code is None:
                continue
            return code != 1
        return False

    # ping data port instead.  accept 1 (X3 data port) or 0 (old X3, other products) but not 2 (config port)
    # todo: should it handle old X3 firmware which has no config messaging on data port? then read output messaging.
    def check_data_port(self):
        m = Message({'msgtype': b'PNG'})
        for _ in range(3):
            response = self.send_control_message(m, self.data_connection)
            code = self.parse_png_code(response)
            if code is None:
                continue
            return code != 2
        # fallback for firmware/builds where config messaging on the data port is unreliable
        return super().check_data_port()

    # allow sending config messages on either port for X3. default to designated "control port"
    def send_control_message(self, message, connection=None):
        if connection is None:
            connection = self.control_connection

        # clear and then write to whichever connection.
        # data port can have much more backlog at low baud, so clear with a longer latency window there.
        clear_wait_s = DEFAULT_PORT_LATENCY_S
        if connection is getattr(self, "data_connection", None):
            clear_wait_s = MAX_PORT_LATENCY_S * 2
        self.clear_connection(connection, self.control_scheme, clear_wait_s)
        self.control_scheme.write_one_message(message, connection)
        if connection is getattr(self, "data_connection", None):
            time.sleep(1e-2)
        resp = self.read_one_control_message(connection)
        if resp:
            return resp
        else:  # timed out waiting for response -> list error as invalid message
            m = Message()
            m.valid = False
            m.error = "Timeout"

    # also needs a connection argument in read_one_control_message so send_control_message works.
    # todo - ok to use control_scheme always, or add a scheme argument?
    def read_one_control_message(self, connection=None):
        if connection is None:
            connection = self.control_connection

        for i in range(100):  # give up after too many tries - TODO what should limit be?
            resp = self.control_scheme.read_one_message(connection)
            if not resp:  # timeout , return None
                return None
            # skip any output types, for firmware versions that output on both ports
            if hasattr(resp, "msgtype") and resp.msgtype in OUTPUT_MESSAGE_TYPES:
                continue
            return resp

    # override auto_port for X3 to: use longer timeout during autobaud, skip non-x3 cases
    def auto_port(self, control_baud, set_data_port=True):
        port_names = self.list_ports()
        for control_port in reversed(port_names):
            try:
                self.control_connection = SerialConnection(port=control_port, baud=control_baud, timeout=TIMEOUT_REGULAR)
                if self.check_control_port():  # success - can set things
                    print(f"connected control port: {control_port}")
                    self.control_port_name = control_port
                    self.control_baud = control_baud

                    # Current X3 firmware uses one shared BAU setting for both user UART ports.
                    data_baud = control_baud
                    self.data_baud = data_baud

                    data_port = None
                    if set_data_port:
                        data_port = self.find_data_port_gnss_imu() #this finds and connects, don't need to set self.data_connection
                        if data_port is None: #fail on data port not found
                            self.release_connections()
                            continue
                        self.data_port_name = data_port
                    return control_port, data_port, control_baud, data_baud
                else:
                    self.release_connections()
            except Exception as e:
                self.release_connections()
                continue
        # no ports worked - clean up and report fail
        self.release_connections()
        return None


if __name__ == "__main__":
    x = X3_Unit(data_port="COM11", control_port="COM12", timeout=0.4)
    print("done")
