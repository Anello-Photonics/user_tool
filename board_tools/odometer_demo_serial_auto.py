#demo of odometer messaging over serial with auto-detect and message generation.

#put this in user_tools/board_tools directory so the import works.
#it will automatically find the unit's serial port and create the odometer messages.
#replace "speed" with a call to your odometer

from time import sleep

import pathlib
import sys
parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src')
from anello_tools import *

A1 = IMUBoard.auto(set_data_port=False) #auto-detect unit on serial ports

while True:
    try:
        speed = 22.5 #replace with speed from your odometer
        A1.send_odometer(speed) #creates and sends APODO messsage with that speed
        sleep(0.05) #can remove this if you wait for odometer data
    except: #ctrl-c to end
        A1.release_connections() #release serial connections
        exit()
