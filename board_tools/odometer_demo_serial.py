#demo of odometer messaging over serial

#replace config_port with your configuration serial port number shown in user_program eg "COM6" or "/dev/ttyUSB3"
#replace speed with a call to your odometer

import serial
from time import sleep

config_port = "COM6" # configuration port for usb connection - use user program to check it.
con = serial.Serial(config_port, 921600) #default baudrate is 921600


def compute_checksum(data):
    total = 0
    for num in data: #this treats each byte as an integer
        total ^= num #xor each byte
    return format(total, 'x')


while True:
    try:
        code = "APODO"
        speed = 22.5  # replace this by getting speed from your odometer
        body = code + "," + str(speed)
        checksum = compute_checksum(body.encode())
        msg = "#" + body + "*" + checksum + "\r\n"  # should be: #APODO,22.5*62\r\n
        con.write(msg.encode())
        #print(msg)
        sleep(0.05) #can remove this if you wait for odometer data
    except: #ctr-c to end
        con.close() #release serial connections
        exit()

