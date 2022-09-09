try:  # importing from inside the package
    import message_scheme
    from message_scheme import Message
    from config import *
    from readable_scheme import ReadableScheme, int_to_ascii, ascii_to_int
    from connection import SerialConnection, FileReaderConnection, FileWriterConnection, UDPConnection
    from board import IMUBoard
    from collector import Collector, SessionStatistics, RealTimePlot
except ModuleNotFoundError:  # importing from outside of the package
    import anello_tools.message_scheme
    from anello_tools.message_scheme import Message
    from anello_tools.config import *
    from anello_tools.readable_scheme import ReadableScheme, int_to_ascii, ascii_to_int
    from anello_tools.connection import SerialConnection, FileReaderConnection, FileWriterConnection, UDPConnection
    from anello_tools.board import IMUBoard
    from anello_tools.collector import Collector, SessionStatistics, RealTimePlot
