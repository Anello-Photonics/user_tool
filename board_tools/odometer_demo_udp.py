#demo of odometer messaging over UDP

#replace A1_ip with ip address of your unit on your network, shown in user configurations
#replace odometer_usb_port with an open port on your computer.
# Set that same port number as UDP COMPUTER ODOMETER PORT in user configurations
#replace "speed" with a call to your odometer

import socket
from time import sleep
from random import uniform

A1_ip = "192.168.1.111" #"10.1.10.21" #address of your unit on the network - see user configurations.

odometer_udp_port, A1_udp_port = 3333, 3 #computer's port for odometer messages. should match user configuration
#odometer_udp_port, A1_udp_port = 2222, 2 #config port

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('', odometer_udp_port))

ODO_RATE_HZ = 100.0 #pick the rate to send odometer messages

#checksum: xor all the bytes together, return as hex string
def compute_checksum(data):
    total = 0
    for num in data: #this treats each byte as an integer
        total ^= num #xor each byte
    return format(total, 'x')


while True:
    try:
        code = "APODO"
        #speed = 12.3  #replace this by getting speed from your odometer
        speed = uniform(0, 20) #random float in the range
        body = code+",+," + '%.2f' % speed
        checksum = compute_checksum(body.encode())
        msg = "#"+body+"*"+checksum+"\r\n"  #should be: #APODO,22.5*62\r\n
        s.sendto(msg.encode(), (A1_ip, A1_udp_port)) #odometer messages go to port 3 on unit
        print(msg)
        sleep(1.0/ODO_RATE_HZ) #can remove this if you wait for odometer data
    except: #ctr-c to end
        s.close() #release udp ports
        exit()

