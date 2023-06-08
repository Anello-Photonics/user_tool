import cutie
import os
import time
import calendar
import sys
import pathlib
import json
import subprocess
import serial
from multiprocessing import Array, Value, Process, Manager
import base64
import socket
import select

parent_dir = str(pathlib.Path(__file__).parent)
sys.path.append(parent_dir+'/src')
from anello_tools import *
from user_program_config import *

def open_log_file(location, name): #ioloop - goes in that file
    # location needs to double any slashes \\ - otherwise we risk \b or other special characters
    location = os.path.join(os.path.dirname(__file__), location)  # make it relative to this file
    os.makedirs(location, exist_ok=True)
    full_path = os.path.join(location, name)
    try:
        return open(full_path, 'wb')
    except Exception as e:
        print("error trying to open log file: "+location+"/"+name)
        return None


def connect_ntrip(num_retries, on, request, ip, port): #ioloop
    errmsg = "unknown error" # if we get to the end without succeeding or known error type
    reader = None
    for i in range(num_retries):
        debug_print("retry "+str(i))
        try:
            debug_print("close_ntrip")
            close_ntrip(on, reader) #make sure previous connection doesn't interfere
            debug_print("open socket")
            reader = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reader.settimeout(NTRIP_TIMEOUT_SECONDS) #will this prevent connect_ex? maybe set nonzero before, zero after
            debug_print("connect to ip")
            error = reader.connect_ex((ip.value.decode(), port.value)) #timeout mattters for this
            if error == 0:  # not an error
                #reader.settimeout(None) #keep the timeout in case it has an error after connecting
                debug_print("sending ntrip request:\n"+request.value.decode())
                reader.sendall(request.value)
                first_resp = reader.recv(4096) #TODO - can this block logging due to blocking read?
                debug_print("ntrip response:\n"+first_resp.decode() + "\n")
                # check the response codes:
                success = False
                if first_resp.find(b"SOURCETABLE 200 OK") >= 0:
                    errmsg = "caster responds with error: wrong mountpoint (sourcetable)" # error message to show when out of retries
                elif first_resp.find(b"200 OK") >= 0:
                    debug_print("caster returns success message")
                    success = True
                elif first_resp.find(b"404 Not Found") >= 0:
                    errmsg = "caster responds with error: wrong mountpoint (not found)"
                elif first_resp.find(b"400 Bad Request") >= 0:
                    errmsg ="caster responds with error: wrong mountpoint (bad request)"
                elif first_resp.find(b"401 Unauthorized") >= 0:
                    errmsg ="caster responds with error: wrong username/password"
                if success:
                    on.value = 1
                    reader.settimeout(0) #back to non-blocking mode, timeout probably not needed when connected.
                    return reader, "success"
                else:
                    continue # wrong response - retry
            else:
                errmsg = str(error)
                continue # error code: retry
        except Exception as e:
            # other errors are usually from wrong caster or not internet connected.
            # TODO - recognize more errors like 10065 when no internet, 11001 for wrong caster? but might depend on OS.
            debug_print(str(type(e))+": "+str(e))
            errmsg = str("could not reach caster")
            continue # exception: retry
    #out of retries: connection failed
    close_ntrip(on, reader)
    debug_print("connect_ntrip failed: "+errmsg)
    return None, errmsg


def close_ntrip(on, reader): #ioloop - only used by connect_ntrip currently
    if reader:
        reader.close()
    on.value = 0


# read gps message, return bytes to send as GGA message
#ex: $GPGGA,165631.00,4810.8483085,N,01139.900759,E,1,05,01.9,+00400,M,,M,,*??<CR><LF>
#     ("time", "time"), 		get from GPS: Joe will add it. could use gps_time from GPS/INS until then.
#     ("lat", "degrees"),		from INS or GPS lat. - check if it needs to minute/second convert
#     ("NS", bytes),		convert from lat sign
#     ("lon", "degrees"),		from INS or GPS lon
#     ("EW", bytes),		from lon sign
#     ("quality", bytes),		make dummy for now. or figure out conversion: GPS fix type?(was 3) or GPS carSoln is 0,1,2 vs quality 0,1,2,4,5
#     ("numSV", int),		GPS message
#     ("HDOP", float),		use GPS PDOP
#     ("alt", float),		GPS mean sea level alt
#     ("altUnit", bytes),		fixed M
#     ("sep", float),		leave blank
#     ("sepunit", bytes),		fixed M
#     ("diffAge", float),		leave blank
#     ("diffStation", float)]	leave blank

def build_gga(gps_message): #ioloop
    # dummy with correct format:
    #return b'$GNGGA,024416.00,3723.94891,N,12158.75467,W,1,12,1.09,3.9,M,-29.9,M,,*7B\r\n'
    if not gps_message or not gps_message.valid:
        # TODO - give an error here? can't make gga without the GPS message
        raise ValueError
    #time: HHMMSS.SS
    gps_time_s = gps_message.gps_time_ns * 1e-9
    utc_time = time.strftime("%H%M%S.00", time.gmtime(gps_time_s)).encode() # this loses  the fractional second - does it matter?
    # still need to convert time?

    # lat: format to DDMM.MMMMM
    lat_float = gps_message.lat_deg
    NS = b'N' if lat_float > 0 else b'S'
    lat_deg = "{:0>2d}".format(abs(int(lat_float)))
    lat_min = "{:08.5f}".format(60 * abs(lat_float - int(lat_float)))
    lat = (lat_deg+lat_min).encode()

    # lon: format to DDDMM.MMMMM
    lon_float = gps_message.lon_deg
    EW = b'E' if lon_float > 0 else b'W'
    lon_deg = "{:0>3d}".format(abs(int(lon_float)))
    lon_min = "{:08.5f}".format(60 * abs(lon_float - int(lon_float)))
    lon = (lon_deg+lon_min).encode()

    fixtype = b'4' #dummy - just pretend we got good fix? not sure if it matters

    # numSV: send to 2 digits
    numsv = "{:0>2d}".format(gps_message.num_sats).encode()
    HDOP = str(gps_message.PDOP).encode() #not the same but should be close . P.P
    alt_msl = str(gps_message.alt_msl_m).encode()  # how many digits?
    altUnit = b'M'
    sep = b'' # ntrip example didn't have this, so skip
    sepunit = b'M'
    diffAge = b'' #example didn't have
    diffStation = b''
    # build payload. later - could assemble a Message() with the GGA fields and use ReadableScheme to build payload?
    payload = b'GNGGA,'+utc_time+b','+lat+b','+NS+b','+lon+b','+EW+b','+fixtype+b','+numsv+b','+HDOP+b','+alt_msl+b','+\
        altUnit+b','+sep+b','+sepunit+b','+diffAge+b','+diffStation
    checksum = int_to_ascii(ReadableScheme().compute_checksum(payload))
    gga_data = b'$'+payload+b'*'+checksum+b'\r\n'
    debug_print(gga_data)
    return gga_data

#put into logs folder with sub-directory by date, eg: logs/Monday_5_24_2021
def log_path():
    #base = "../logs"
    ltime = time.localtime()
    #month directory name: "2021_06" for june 21, 2021
    month_dir = "_".join([str(ltime.tm_year), str(ltime.tm_mon)])
    #day directory name: "21" for june 21, 2021
    day_dir = str(ltime.tm_mday)
    return os.path.join("..", "logs", month_dir, day_dir)

def io_loop(exitflag, con_on, con_start, con_stop, con_succeed,
            con_type, com_port, com_baud, udp_ip, udp_port, gps_received,
            log_on, log_start, log_stop, log_name,
            ntrip_on, ntrip_start, ntrip_stop, ntrip_succeed,
            ntrip_ip, ntrip_port, ntrip_gga, ntrip_req,
            last_ins_msg, last_gps_msg, last_gp2_msg, last_imu_msg, last_hdg_msg):

    data_connection = None
    ntrip_reader = None
    ntrip_retrying = False
    ntrip_stop_time = 0
    log_file = None
    flush_counter=0
    #last_valid_gps = None
    ascii_scheme = ReadableScheme()
    binary_scheme = RTCM_Scheme()

    while True:
        time.sleep(1e-3) #slow down loop to reduce cpu use, 1 ms wait should be fine
        #first handle all start/stop signals.
        if con_stop.value: #TODO - currently not using this since I release before new connection anyway
            debug_print("io_loop con stop")
            if data_connection:
                data_connection.close()
                data_connection = None
            con_stop.value = 0
        elif log_stop.value:
            debug_print("io_loop log stop")
            if log_file:
                log_file.close()
                log_file = None
            log_stop.value = 0
        elif ntrip_stop.value:
            debug_print("io_loop ntrip stop")
            if ntrip_reader:
                ntrip_reader.close()
                ntrip_reader=None
            ntrip_stop.value = 0
        # handle exit after stops just in case.
        elif exitflag.value:
            # exit should release everything in case not released
            if data_connection:
                data_connection.close()
            if ntrip_reader:
                ntrip_reader.close()
            if log_file:
                log_file.close()
            exit()
        elif con_start.value:
            con_start.value = 0
            try:
                # release existing connection:
                if data_connection:
                    data_connection.close()
                debug_print("io_loop con start")
                if con_type.value == b"COM":
                    debug_print("io_loop connect COM")
                    data_connection = SerialConnection(com_port.value.decode(), com_baud.value)
                elif con_type.value == b"UDP":
                    debug_print("io_loop connect UDP")
                    data_connection = UDPConnection(udp_ip.value.decode(), UDP_LOCAL_DATA_PORT, udp_port.value)
                con_succeed.value = 1 # success
            except Exception as e:
                debug_print(str(type(e))+": "+str(e))
                con_succeed.value = 2  # fail
                if data_connection:
                    data_connection.close()
        elif log_start.value:
            debug_print("io_loop log start")
            log_file = open_log_file(log_path(), log_name.value.decode())
            log_start.value = 0
        elif ntrip_start.value:
            debug_print("io_loop ntrip start")
            ntrip_reader, ntrip_connect_result = connect_ntrip(CONNECT_RETRIES, ntrip_on, ntrip_req, ntrip_ip, ntrip_port)
            #print(ntrip_connect_result) #this will show when user connects.
            if ntrip_reader: # signal success to ntrip_start in user thread
                ntrip_succeed.value = 1
            else: # failed
                print("ntrip connect failed: "+ntrip_connect_result)
                ntrip_succeed.value = 2
            ntrip_start.value = 0

        #debug_print("ioloop doing work: ntrip_on = "+str(ntrip_on.value)+", ntrip_reader = "+str(ntrip_reader))
        if ntrip_retrying:
            # reconnect after a delay, but keep logging and everything else until then
            if time.time() - ntrip_stop_time >= NTRIP_RETRY_SECONDS:
                ntrip_stop_time = time.time()
                ntrip_reader, ntrip_connect_result = connect_ntrip(1, ntrip_on, ntrip_req, ntrip_ip, ntrip_port)
                if ntrip_reader:
                    ntrip_retrying = False
                    debug_print("ntrip reconnected")
                else:
                    debug_print("ntrip reconnect failed")

        if ntrip_on.value and con_on.value and data_connection and ntrip_reader and ntrip_reader.fileno() >= 0:
            #print("ntrip work to do")
            try:
                #this select can raise ValueError when ntrip turns off, but fileno() >=0 check should prevent it.
                reads, writes, errors = select.select([ntrip_reader], [], [], 0)
                # ntrip data incoming -> take it and send to data connection.
                if ntrip_reader in reads:
                    ntrip_data = ntrip_reader.recv(1024) #TODO can this block logging? hopefully not at timeout 0.
                    if not ntrip_data:
                        #empty read means disconnected: go to the catch
                        raise ConnectionResetError
                    debug_print("\nntrip data (len "+str(len(ntrip_data))+"):\n")
                    #debug_print(ntrip_data)
                    data_connection.write(ntrip_data)
            except ConnectionResetError:
                debug_print("ntrip disconnected")
                ntrip_on.value = 0
                ntrip_retrying = True
                ntrip_stop_time = time.time()

            except Exception as e: #catchall - assume its a single bad read/write. only stop if we know it disconnected.
                debug_print(str(type(e))+": "+str(e))

        # A1 has output: log it
        #if log_on.value and data_connection and data_connection.read_ready():
        if con_on.value and data_connection:
            try:
                #TODO - verify connection state? read_ready fails on COM if disconnected, but no error on UDP lost here
                read_ready = data_connection.read_ready()
                if read_ready: # read whether logging or not to keep buffer clear

                    #use readall to make sure it's up to date. could read one or multiple messages.
                    in_data = data_connection.readall()

                    #try handling as ascii and rtcm and do whichever works. TODO - make a combined parser?
                    for parse_scheme, start_char in [(ascii_scheme, READABLE_START), (binary_scheme, RTCM_PREAMBLE)]:
                        #parts = in_data.split(READABLE_START) #TODO - do a read_one_message from this?
                        #parts = in_data.split(RTCM_PREAMBLE)
                        parts = in_data.split(start_char) #TODO - do a read_one_message from buffer instead? this will split on start char in message.
                        for part in parts:
                            #last_msg = binary_scheme.parse_message(part)
                            #last_msg = ascii_scheme.parse_message(part)
                            #print(f"will parse using {parse_scheme}, part = {part}")
                            last_msg = parse_scheme.parse_message(part)
                            #print(f"last_msg: {last_msg}")
                            if not last_msg.valid:
                                continue #todo - could try to recombine split messages here.
                            #debug_print(last_msg)
                            elif last_msg.msgtype == b'INS':
                                last_ins_msg.value = part #send valid INS message to monitor
                                #print(f"\nlast_ins_msg {type(parse_scheme)}:\n{part}")
                            elif last_msg.msgtype in [b'IMU', b'IM1']:
                                last_imu_msg.value = part #send valid IMU message to monitor
                                #print(f"\nlast_imu_msg {type(parse_scheme)}:\n{last_msg}")
                            elif last_msg.msgtype == b'HDG':
                                last_hdg_msg.value = part
                            elif last_msg.msgtype == b'GPS':
                                #print(f"\nlast_gps_msg {type(parse_scheme)}:\n{part}")
                                last_gps_msg.value = part # save if needed for ntrip start or delayed sending
                                gps_received.value = 1 #will allow setting gga on in ntrip
                                #build and send GGA message if ntrip on
                                if ntrip_on.value and ntrip_reader and ntrip_gga:
                                    # build GGA
                                    gga_message = build_gga(last_msg)
                                    try:
                                        ntrip_reader.sendall(gga_message)
                                    except Exception as e: #ntrip error, not data_connection
                                        #TODO - handle this as if ntrip disconnected? then close (if open) and retry
                                        debug_print("error sending gga message")
                            elif last_msg.msgtype == b'GP2':
                                #print(f"\nlast_gp2_msg {type(parse_scheme)}:\n{part}")
                                last_gp2_msg.value = part # save if needed for ntrip start or delayed sending
                    if log_on and log_file: #TODO - what about close in mid-write? could pass message and close here. or catch exception
                        #pass
                        #debug_print(in_data.decode())
                        #log_file.write("< " + str(flush_counter) + " >")
                        log_file.write(in_data)
                        #periodically flush so we see file size progress
                        flush_counter += 1
                        #debug_print("< "+str(flush_counter)+" >")
                        if flush_counter >= FLUSH_FREQUENCY:
                            flush_counter = 0
                            log_file.flush()
                            os.fsync(log_file.fileno())
            except (socket.error, socket.herror, socket.gaierror, socket.timeout, serial.SerialException, serial.SerialTimeoutException) as e:
                # connection errors: indicate connection lost. I only saw the the serial errors happen here.
                print("connection error: "+str(e)+"\nplease reconnect") #TODO - auto-reconnect after error?
                data_connection.close()
                con_on.value = 0
