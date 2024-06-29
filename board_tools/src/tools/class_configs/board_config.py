DEFAULT_BAUD = 921600
#all allowed bauds, put in the order that autobaud should try. usually 921600 for EVK, 230400 for GNSS and IMU
ALLOWED_BAUD = [921600, 230400, 19200, 460800, 115200, 57600] #[57600, 115200, 230400, 460800, 921600]
ALLOWED_SMP = [200, 400, 500, 1000, 2000]
TIMEOUT_AUTOBAUD = 0.2 #timeout (s) while searching for units/checking baud
TIMEOUT_REGULAR = 0.4 #normal timeout when connected. todo - does it ever need a longer timeout? #was 4
#connection info for imuboard.auto(). paths relative to files in Python_Code/board_tools/src/tools
CONNECTION_CACHE_WITH_DATA_PORT = "connection_cache_dataport.txt"  #when data port used
CONNECTION_CACHE_NO_DATA_PORT = "connection_cache_no_dataport.txt" #when data port not used
LOG_PATH = "../../../logs"
DEBUG_PATH = "../../../debug"
LOG_FILETYPE = ".txt"
UDP_LOCAL_DATA_PORT = 1
UDP_LOCAL_CONFIG_PORT = 2
UDP_LOCAL_ODOMETER_PORT = 3
