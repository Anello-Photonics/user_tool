try:  # importing from inside the package
    import message_scheme
    from message_scheme import Message
    from class_configs import *
    from readable_scheme import ReadableScheme, int_to_ascii, ascii_to_int
    from rtcm_scheme import RTCM_Scheme
    from binary_scheme import Binary_Scheme
    from connection import SerialConnection, FileReaderConnection, FileWriterConnection, UDPConnection
    from board import IMUBoard
except ModuleNotFoundError:  # importing from outside of the package
    import tools.message_scheme
    from tools.message_scheme import Message
    from tools.class_configs import *
    from tools.readable_scheme import ReadableScheme, int_to_ascii, ascii_to_int
    from tools.rtcm_scheme import RTCM_Scheme
    from tools.binary_scheme import Binary_Scheme
    from tools.connection import SerialConnection, FileReaderConnection, FileWriterConnection, UDPConnection
    from tools.board import IMUBoard
