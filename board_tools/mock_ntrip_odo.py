import os
import sys
import pathlib
src_directory = pathlib.Path(__file__).parent.joinpath("src")
sys.path.insert(0, str(src_directory))

import time
import base64
import select
from multiprocessing import Process, Array, Value, Pipe
from ioloop import connect_ntrip, build_gga, log_path, open_log_file
from user_program import proper_response
from user_program_config import FLUSH_FREQUENCY
from tools import *

ntrip_setting = {"caster": "na.l1l2.skylark.swiftnav.com", "port": 2101, "mountpoint": "RTK-MSM5", "username": "anello.mike", "password": "AmuvzibhRt", "gga": True}

# used for the gga message
sample_gps = b'APGPS,1280046.288,1359506054499649280,37.3991881,-121.9795420,-17.7610,12.1280,0.5690,272.4239,16.3650,9.9580,3.7600,3,8,0.9430,25.5339,0*5F\r\n' 


use_serial = True
unit_ip = "192.168.1.111"
unit_udp_data_port = 1111
unit_udp_config_port = 2222
unit_udp_odo_port = 3333

unit_com_data_port = "COM3"
unit_com_config_port = "COM6"

file_name = "test.txt"

odo_speed = 22.5
odo_data_rate = 100 #hz

send_ntrip = True
send_odo = True


connect_retries = 3
NTRIP_RETRY_SECONDS = 15

forward = True

gga_loop_period = 1

ascii_scheme = ReadableScheme()

def main():
    global file_name
    global odo_speed
    
    if len(sys.argv) < 2:
        file_name = input("attatch filename arguement or input here:")
    else:
        file_name = sys.argv[1]
    
    if not file_name.endswith(".txt"):
        file_name += ".txt"



    last_odo_time = 0
    # odo_wait_time = 1/odo_data_rate

    odo_wait_time = 0

    string_size = 500

    exitflag = Value('b', 0)

    #connection vars
    con_on = Value('b',0)
    con_start = Value('b',0)
    con_stop = Value('b',0)
    con_succeed = Value('b',0)
    con_type = Value('b',0)         # 0 = serial con : 1 = udp con
    com_port = Array('c',string_size)
    com_baud = Value('i',0)
    udp_ip = Array('c', string_size)
    udp_data_port = unit_udp_data_port
    udp_config_port = unit_udp_odo_port

    #log control vars
    log_on = Value('b',0)
    log_start = Value('b',0)
    log_stop = Value('b', 0)
    log_name = Array('c', string_size)

    #multiprocess ntrip control vars
    ntrip_on = Value('b', 0)
    ntrip_start = Value('b', 0)
    ntrip_stop = Value('b', 0)
    ntrip_succeed = Value('b', 0)

    #multiprocessing shared ntrip information vars
    ntrip_ip = Array('c', string_size)
    ntrip_port = Value('i', 0)
    ntrip_gga = Value('b')
    ntrip_req = Array('c', string_size)

    ntrip_recv, ntrip_sendv = Pipe(duplex=False)
    shared_args_ntrip_loop = (exitflag, ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                            ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
                            ntrip_sendv)


    shared_args_data_loop = (exitflag, con_on, con_start, con_stop, con_succeed,
                            con_type, com_port, com_baud, udp_ip, udp_data_port,
                            log_on, log_start, log_stop, log_name,
                            ntrip_recv)

    # fname = input("Log file name:")
    log_name.value = file_name.encode()
    setup_ntrip(ntrip_ip, ntrip_port, ntrip_req, ntrip_gga)

    data_loop_proc = Process(target=data_loop, args=shared_args_data_loop)
    ntrip_loop_proc = Process(target=ntrip_loop, args=shared_args_ntrip_loop)



    anello = setupEVK(con_type, com_port, com_baud, udp_ip, udp_config_port)
    
    if not anello:
        exitflag.value = 1


    data_loop_proc.start()
    ntrip_loop_proc.start()
    if not exitflag.value and startDataPort(con_start, con_on, con_succeed):
        print("EVK Connection: Successful")
    else:
        print("EVK Connection: Fail")
        print("Ensure script configs match EVK unit configs")
        exitflag.value = 1

    if not exitflag.value == 1:
        startNTRIP(ntrip_start, ntrip_on, ntrip_succeed)
        start_logging(log_start, log_on)
    try:
        while True:
            time.sleep(.001)
            
            if exitflag.value == 1:
                raise KeyboardInterrupt
            
            if time.time()-last_odo_time >= odo_wait_time:
                if send_odo:
                    send_new_odo(anello,round(odo_speed, 2),ntrip_on.value)
                odo_speed += .01
                if odo_speed > 30:
                    odo_speed = 25
    except (Exception, KeyboardInterrupt) as e:
        exitflag.value = 1
        print(e)
        anello.release_connections()
        ntrip_loop_proc.join()
        data_loop_proc.join()
        print("Exited Safely")
        return
    pass


def compute_checksum(data):
    total = 0
    for num in data: #this treats each byte as an integer
        total ^= num #xor each byte
    return format(total, 'x')

def send_new_odo(unit, speed, on):
    code = "APODO"
    magnitude = abs(speed)
    sign_symbol  = "+" if forward else "-"
    body = code + "," + sign_symbol + "," + str(magnitude)
    checksum = compute_checksum(body.encode())
    msg = "#" + body + "*" + checksum + "\r\n"  # should be: #APODO,22.5*62\r\n
    # print(f"{msg}:{on}")
    unit.control_connection.write(msg.encode())

def retry_command(board, method, response_types, args=[], retries=6):
    connection_errors = [1, 3, 4]
    #may need to clear input buffer here so some old message isn't read as a response.
    board.control_connection.reset_input_buffer() #TODO - make this actually do something for UDP
    for i in range(retries):
        try:
            output_msg = method(*args)
            # no response: retry
            if not output_msg:
                continue
            # connection errors: retry. content errors like invalid fields/values don't retry
            if output_msg.msgtype == b'ERR' and output_msg.msgtype in connection_errors:
                continue
            # invalid response message or unexpected response type: retry
            if not proper_response(output_msg, response_types):
                continue
            else:
                return output_msg
        except Exception as e:
            continue #error - treat as fail, retry
    #raise Exception("retry method: " + str(method) + " failed")
    # if it failed after retries, there is a connection problem
    print(f"error in function {method.__name__}, types={response_types}, args = {args}")
    return None #didn't work -> function that calls this should check for None

def setupEVK(con_type, com_port, com_baud, udp_ip, udp_port):

    if use_serial:
        con_type.value = 0
        com_port.value = str(unit_com_data_port).encode()
        com_baud.value = 921600    

        anello = IMUBoard(data_port=None, control_port=unit_com_config_port)



        if anello.control_port_name:
            serialnum = retry_command(anello, method=anello.get_serial, response_types=[b'SER']).ser.decode()
            print(f"Serialnum: {serialnum}")
            print("connected to A-1 at config port = "+anello.control_port_name)
        else:
            print("failed to detect A-1 com port, check connections.")
            exit()

    else:
        con_type.value = 1
        udp_ip.value = unit_ip.encode()
        udp_port = unit_udp_data_port

        anello = IMUBoard.from_udp(ip=unit_ip, data_port=None, control_port=unit_udp_config_port, odometer_port=None)


        if hasattr(anello, "control_connection") and anello.control_connection:
            try:
                serialnum = retry_command(anello, method=anello.get_serial, response_types=[b'SER']).ser.decode()
                print(f"Serialnum: {serialnum}")
            except AttributeError:
                print("EVK not responsive (no connection)")
                return None
            print("\nA-1 at odometer port: "+str(anello.control_connection))
            time.sleep(0.5)
    
    return anello

def startNTRIP(ntrip_start, ntrip_on, ntrip_succeed):
    ntrip_start.value = 1
    ntrip_on.value = 1

    while ntrip_succeed.value == 0:
        time.sleep(.1)

    if ntrip_succeed.value == 1:
        print("NTRIP Connection Successful")    
        time.sleep(1)
        return True
    else:
        print("NTRIP Connection Failed")
        time.sleep(1)
        return False

def setup_ntrip(ntrip_ip, ntrip_port, ntrip_req, ntrip_gga):
    caster = ntrip_setting['caster']
    port = ntrip_setting['port']
    mountpoint = ntrip_setting['mountpoint']
    username = ntrip_setting['username']
    password = ntrip_setting['password']
    send_gga = ntrip_setting['gga']

    ntrip_gga.value = send_gga
    ntrip_port.value = int(port)
    mountpoint = mountpoint.encode()
    ntrip_ip.value = caster.encode()

        

    userAgent = b'NTRIP Anello Client'
    ntrip_version = 1
    ntrip_auth = "Basic" #TODO - add more options for these

    userAgent = b'NTRIP Anello Client'
    ntrip_version = 1
    ntrip_auth = "Basic"

    if ntrip_version == 1 and ntrip_auth == "Basic":
        auth_str = username + ":" + password
        auth_64 = base64.b64encode(auth_str.encode("ascii"))
        ntrip_req.value = b'GET /' + mountpoint + b' HTTP/1.0\r\nUser-Agent: ' + userAgent + b'\r\nAuthorization: Basic ' + auth_64 + b'\r\n\r\n'
    else:
        # TODO make request structure for NTRIP v2, other auth options.
        print("not implemented: version = " + str(ntrip_version) + ", auth = " + str(ntrip_auth))
        ntrip_req.value=b'' # will work as False for conditions
            #signal io_thread to connect the ntrip.
    return

def start_logging(log_start, log_on):
    log_start.value = 1
    log_on.value = 1

def stop_logging(log_stop, log_on):
    log_on.value =  0
    log_stop.value = 1

def startDataPort(con_start, con_on, con_succeed):
    con_on.value = 1
    con_start.value = 1

    while con_succeed.value == 0:
        time.sleep(.1)

    return con_succeed.value == 1

def ntrip_loop(exitflag, ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
                ntrip_ip, ntrip_port, ntrip_gga, ntrip_req, ntrip_sender_pipe):

    ntrip_reader = None
    ntrip_retrying = False
    ntrip_stop_time = 0
    
    last_gga_loop_time = time.time()

    try:
        while True:
            time.sleep(.001)
            
            #connect to ntrip
            if ntrip_start.value:
                print("start")
                ntrip_reader, ntrip_connect_res = connect_ntrip(connect_retries, ntrip_on, ntrip_req, ntrip_ip, ntrip_port)
                
                
                if ntrip_reader:
                    ntrip_succeed.value = 1
                else:
                    print(f"ntrip connect failed: {ntrip_connect_res}")
                    ntrip_succeed.value = 2
                    exitflag.value = 1
                    #maybe set retrying on here
                ntrip_start.value = 0

            # close reader then exit
            elif exitflag.value:
                print("exit")
                if ntrip_reader:
                    ntrip_reader.close()
                raise KeyboardInterrupt

            #close reader
            elif ntrip_stop.value:
                print("Stopping NTRIP")
                if ntrip_reader:
                    ntrip_reader.close()
                    ntrip_reader = None
                ntrip_stop.value = 0

            # try to reconnect
            elif ntrip_retrying:
                print("retrying")
                if time.time()-ntrip_stop_time >= NTRIP_RETRY_SECONDS:
                    print("attempting NTRIP reconnect")
                    ntrip_stop_time = time.time()
                    ntrip_reader, ntrip_connect_res = connect_ntrip(1, ntrip_on, ntrip_req, ntrip_ip, ntrip_port)

                    if ntrip_reader:
                        print("Reconnect Success")
                        ntrip_retrying = False
                    else:
                        print("Reconnect Failed")

            #send ntrip data to pipe
            elif ntrip_on.value and ntrip_reader and ntrip_reader.fileno():
                try:
                    reads, writes, errors = select.select([ntrip_reader],[],[],0)
                    
                    if ntrip_reader in reads:
                        ntrip_data = ntrip_reader.recv(1024)
                        if not ntrip_data:
                            raise ConnectionResetError
                        ntrip_sender_pipe.send(ntrip_data)
                except ConnectionResetError:
                    print("NTRIP disconnected")
                    ntrip_on.value = 0
                    ntrip_retrying = True
                    ntrip_stop_time = time.time()
                except Exception as e:
                    print(f"{str(type(e))}: {str(e)}")

            #send saved gga message to caster
            if ntrip_on.value and ntrip_reader and ntrip_gga.value and time.time() - last_gga_loop_time > gga_loop_period:
                last_gga_loop_time = time.time()
                msg = ascii_scheme.parse_message(sample_gps)
                if not msg.valid:
                    print("message parse error")
                    continue
                gga_msg = build_gga(msg)
                try:
                    ntrip_reader.sendall(gga_msg)
                    # print("GGA sent")
                except Exception as e:
                    print("gga error")
            # else:
            #     print(f"on:{ntrip_on.value}...ntrip_reader:{bool(ntrip_reader)}...ntrip_gga:{ntrip_gga.value}")

    except (Exception, KeyboardInterrupt) as e:
        if ntrip_reader:
            ntrip_reader.close()
        ntrip_reader = None
        return

    return

#TODO Add data port to the code for recording data plus logging
def data_loop(exit_flag, con_on, con_start, con_stop, con_succeed,
                con_type, com_port, com_baud, udp_ip, udp_data_port,
                log_on, log_start, log_stop, log_name,
                ntrip_receiver_pipe):
    flush_counter = 0
    log_file = None
    data_connection = None
    try:
        while True:
            time.sleep(.001)
            if exit_flag.value == 1:
                raise KeyboardInterrupt

            if con_stop.value:
                if data_connection:
                    data_connection.close()
                    data_connection = None
                con_stop.value = 0
            if con_start.value:
                con_start.value = 0
                try:
                    if data_connection:
                        data_connection.close()
                    if con_type.value == 0:         #SERIAL
                        print("Connecting COM...")
                        data_connection = SerialConnection(com_port.value.decode(), com_baud.value)
                    if con_type.value == 1:         #UDP
                        print("Connecting UDP...")
                        data_connection = UDPConnection(udp_ip.value.decode(), UDP_LOCAL_DATA_PORT, udp_data_port)
                        pass
                    con_succeed.value = 1
                    pass
                except Exception as e:
                    con_succeed.value = 2
                    if data_connection:
                        data_connection.close()

            if log_start.value:
                log_file = open_log_file(log_path(), log_name.value.decode())
                log_start.value = 0
            if con_on.value and data_connection:
                try:
                    read_ready = data_connection.read_ready()
                    if read_ready:
                        in_data = data_connection.readall()
                        if log_on and log_file:
                            log_file.write(in_data)
                            flush_counter += 1

                            if flush_counter >= FLUSH_FREQUENCY:
                                flush_counter = 0
                                log_file.flush()
                                os.fsync(log_file.fileno())
                except Exception as e:
                    exit_flag.value = 1
                    if data_connection:
                        data_connection.close()
                    print("Connection Error")
                    
            if ntrip_receiver_pipe.poll():
                ntrip_data = ntrip_receiver_pipe.recv()
                if data_connection and ntrip_data:
                    print(f"ntrip_written: {sys.getsizeof(ntrip_data)} bytes")
                    data_connection.write(ntrip_data)
    except (KeyboardInterrupt,Exception) as e:
        if type(e) != KeyboardInterrupt:
            print(f"dataloop:{e}")

        exit_flag.value = 1
        if data_connection:
            data_connection.close()
        
        if log_file:
            log_file.flush()
            log_file.close()
        return


if __name__ == '__main__':
    main()

pass