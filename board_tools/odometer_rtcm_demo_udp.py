#demo of odometer and rtcm messaging over UDP

# to edit, see the #CHANGE TO:  comments
# change A1_ip with ip address of your unit on your network, which is shown in user configurations
# change odometer_udb_port and data_udp_port to open ports on your computer.
#   set the same ports as UDP COMPUTER DATA PORT and UDP COMPUTER ODOMETER PORT user configurations.
#   If your unit has no udp odometer port, use the udp config port. After upgrading you should change it to odometer port.
# change the "if counter % 100000 == 0" to a checks if the odometer or rtcm data is ready.
#   select.select is a good way to check, as shown for the unit's output.
#   If you use a different check, it it should prevent a single measurement from being sent repeatedly.
#   When not ready, it should return False immediately and not wait to be ready. Otherwise it will block the other messages.
# change speed to the speed from your odometer
# change rtcm_data to your data

import socket
import select

A1_ip = "10.1.10.107" #CHANGE TO: address of your unit on the network - see user configurations.
data_udp_port = 1111 #CHANGE TO: "udp computer data port" configuration
odometer_udp_port = 3333  #CHANGE TO: "udp computer config port" or "udp computer odometer port" configuration

odo_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
odo_socket.bind(('', odometer_udp_port))

data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
data_socket.setblocking(False)
data_socket.bind(('', data_udp_port))

MAX_READ = 1024 #for output data reads


#our message checksum: xor all the bytes together, return as hex string
def compute_checksum(data):
    total = 0
    for num in data: #this counts each byte of the data
        total ^= num #xor each byte
    return format(total, 'x')


counter = 0 #CHANGE TO: you can remove this after putting proper checks for rtcm and odometer ready

while True:
    try:
        #read unit output when it's ready
        reads, writes, errors = select.select([data_socket], [], [], 0)
        if data_socket in reads:  #if it has any data
            out_data = data_socket.recv(MAX_READ)
            print("unit output: " + out_data.decode())
            #you can parse the message or log to a file here

        # get odometer data and send to the unit.
        if counter % 100000 == 0: #CHANGE TO: check if your odometer has data, like the select.select check on data_socket above.
            code = "APODO"
            speed = 22.5  #CHANGE TO: speed from your odometer, matching the odometer unit configuration
            body = code+","+str(speed)
            checksum = compute_checksum(body.encode())
            odo_msg = "#"+body+"*"+checksum+"\r\n"  #will look like: #APODO,22.5*62\r\n
            odo_socket.sendto(odo_msg.encode(), (A1_ip, 3)) #odometer messages go to port 3 on unit
            print("odometer message in: " + odo_msg)

        #send rtcm data to the units
        if counter % 100000 == 0: #CHANGE TO: check if you have new rtcm data, like the select.select check on data_socket above.
            rtcm_data = b'data' #CHANGE TO: get your rtcm data
            data_socket.sendto(rtcm_data, (A1_ip, 1)) #corrections go to UDP port 1 on unit
            print("rtcm in: ")
            print(rtcm_data)

        counter += 1 #CHANGE TO: you can remove this after putting proper checks for rtcm and odometer ready

    except KeyboardInterrupt: #ctr-c to end
        print("keyboard interrupt")
        odo_socket.close() #release udp ports
        data_socket.close()
        print("exit")
        exit()

    except Exception as e: #other error - show it and exit
        print(str(type(e)) + ": "+str(e))
        odo_socket.close()  # release udp ports
        data_socket.close()
        print("exit")
        exit()

