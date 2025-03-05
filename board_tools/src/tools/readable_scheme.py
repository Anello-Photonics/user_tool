try:  # importing from inside the package
    from message_scheme import Scheme, Message
    from class_configs.readable_scheme_config import *
    from connection import *
except ModuleNotFoundError:  # importing from outside the package
    from tools.message_scheme import Scheme, Message
    from tools.class_configs.readable_scheme_config import *
    from tools.connection import *


# b'AA' -> 170
def ascii_to_int(x):
    return int(x, 16)


#170 -> b'AA'
def int_to_ascii(x):
    return "{0:0{1}X}".format(x,2).encode()


# get one bit from a combined flags integer
def nth_bit(combined_val, position):
    return (combined_val >> position) & 1


#extract flags as a separate function independent of paylod -> can use it in RTCM too.
def extract_flags_HDG(message):
    if hasattr(message, "flags"):
        flag_bits = format(message.flags, '010b') #int into string of 9 bits, zero padded
        flag_bits_reversed = "".join(reversed(flag_bits)) #put backward
        for i in HEADING_FLAGS:
            setattr(message, HEADING_FLAGS[i], int(flag_bits_reversed[i]))  #TODO - is this the right bit order or backwards?
    #combine the carrSoln: should have both bit attributes in HEADING_FLAGS
    if hasattr(message, "carrSoln_bit1") and hasattr(message, "carrSoln_bit2"):
        setattr(message, "carrSoln", 2*message.carrSoln_bit2 + message.carrSoln_bit1) #TODO - is this the right bit order or backwards?


# convert the aln user config, such as "+0.00000-1.123456+3.234000" into 3 floats which are easier to compare.
def split_aln_string(aln_string):
    if type(aln_string) is bytes:
        aln_string = aln_string.decode()
    # put comma before each + or - sign, then split on those, preserving the sign.
    comma_separated = aln_string.replace("+", ",+").replace("-", ",-")
    parts = comma_separated.split(",")
    try:
        return [float(parts[i]) for i in [1, 2, 3]]  # first part is empty, next parts are the numbers.
    except Exception as e:  # could have exceptions on wrong aln string format
        return None

#messages encoded in readable form with start and end codes, comma separted values
class ReadableScheme(Scheme):
    
    #since there are start and end codes, read everything between them as one message
    def read_one_message(self, connection):

        # get one message as raw data: implemented in SerialConnection, UDPConnection, FileReaderConnection
        data = connection.read_one_message(start_char=READABLE_START, end_char=READABLE_END)

        if not data:
            return None
        #print("receiving: "+data.decode())
        # if data[:len(READABLE_START)] == READABLE_START: #chop off start code if present
        #     data = data[len(READABLE_START):]
        # if data[-len(READABLE_END):] == READABLE_END: #chop off end code if present
        #     data = data[:-len(READABLE_END)]
        # else:
        #     pass #TODO if no end code, could handle partial read or give an error
        #if data:
        message = Message()
        self.set_fields_general(message, data)
        return message

    # def read_message_from_file(self, input_file):
    #     # if (not hasattr(self, "reader")) or self.reader is None:
    #     #     self.reader = RTCMReader(input_file)
    #     message = Message()
    #     try:
    #         #raw, parsed = self.reader.read()
    #
    #         before = connection.read_until(READABLE_START)
    #         # TODO can handle partial start on whatever came before start code
    #         data = connection.read_until(READABLE_END)
    #
    #         #strip off preamble then pass the raw data to set_fields_general.
    #         #or if using parsed, it would already have the message tye (4058) and checksum split from payload
    #         if raw:
    #             data = raw.lstrip(RTCM_PREAMBLE)
    #             self.set_fields_general(message, data)
    #         else: #complete. TODO - is this the correct check for end of file? seems to work.
    #             return None
    #     except RTCMParseError: #error from RTCMReader.read if checksum fails
    #         message.valid = False
    #         message.error = "checksum"
    #     except Exception as e: #catchall error
    #         message.valid = False
    #         message.error = "parsing error: "+str(e)
    #     return message

    #write a single message to the connection
    def write_one_message(self, message, connection):
        data = READABLE_START + self.build_message_general(message) + READABLE_END
        #print("sending: "+data.decode()) #debug message creation
        connection.write(data)

    def set_fields_general(self, message, data):
        try:

            if data[:len(READABLE_START)] == READABLE_START: #chop off start code if present
                data = data[len(READABLE_START):]
            if data[-len(READABLE_END):] == READABLE_END: #chop off end code if present
                data = data[:-len(READABLE_END)]

            #message.data = data
            sep_index = data.find(READABLE_CHECKSUM_SEPARATOR)
            checksum_start_index = sep_index + len(READABLE_CHECKSUM_SEPARATOR)
            checksum_end_index = checksum_start_index + READABLE_CHECKSUM_LENGTH

            message.data = data[:checksum_end_index] #take off any extras after checksum
            message.checksum_input = data[:sep_index]
            message.checksum = ascii_to_int(data[checksum_start_index:checksum_end_index]) #int(data[sep_index+len(READABLE_PAYLOAD_SEPARATOR):], 16) #it has bytes which read as the hex value

            #could split these from data or from message.checksum_input
            message.talker = data[0: READABLE_TALKER_LENGTH]

            # messsage type is after "AP" until first comma (like APCFG,W... ) or * (like APPNG*48)
            first_special_char = min(data.find(READABLE_PAYLOAD_SEPARATOR), sep_index)
            if first_special_char < 0:
                message.valid = False
                message.error = "Parsing error: no character indicating end of message type"
                return

            message.msgtype = data[READABLE_TALKER_LENGTH: first_special_char]
            message.payload = data[first_special_char + len(READABLE_PAYLOAD_SEPARATOR): sep_index]
            if self.check_valid(message):
                self.decode_payload_for_type(message, message.msgtype, message.payload)
        except Exception as err:
            message.valid = False
            message.error = "Parsing Error: "+str(err)

    #make the structure for all message types in this scheme
    #input - a message object with attributes: talker, msgtype, 
    #return the bytes to write
    def build_message_general(self, message):
        msgtype = message.msgtype
        #adds OUR_TALKER here so talker is not a message attribute
        data = OUR_TALKER + msgtype
        payload = self.build_payload_for_type(message, msgtype)
        if payload:
            data += READABLE_PAYLOAD_SEPARATOR + payload
        checksum = int_to_ascii(self.compute_checksum(data))
        data += READABLE_CHECKSUM_SEPARATOR
        data += checksum
        return data

    def check_valid(self, message):
        try:
            if not self.checksum_passes(message):
                message.valid = False
                message.error = "Checksum Fail"
            else:
                message.valid = True
                message.error = None
            return message.valid
        except Exception as err:
            print("exception checking message with data: "+str(message.data)+" , len = "+str(len(message.data)))
            message.valid = False
            message.error = "Check Error: "+str(err)

    #use decoder for each type. TODO make separate classes for these.
    def decode_payload_for_type(self, message, msgtype, payload):
        decoders = {
            b'IMU': self.set_payload_fields_IMU,
            b'IM1': self.set_payload_fields_IM1,
            b'GPS': self.set_payload_fields_GPS,
            b'GP2': self.set_payload_fields_GP2,
            b'HDG': self.set_payload_fields_HDG,
            b'ERR': self.set_payload_fields_ERR,
            b'CFG': self.set_payload_fields_with_names,
            b'VER': self.set_payload_fields_VER,
            b'SER': self.set_payload_fields_SER,
            b'PID': self.set_payload_fields_PID,
            b'IHW': self.set_payload_fields_IHW,
            b'FHW': self.set_payload_fields_FHW,
            b'FSN': self.set_payload_fields_FSN,
            b'STA': self.set_payload_fields_with_names,
            b'RST': self.set_payload_fields_RST,
            b'PNG': self.set_payload_fields_PNG,
            b'ECH': self.set_payload_fields_ECH,
            b'ODO': self.set_payload_fields_ODO,
            b'INS': self.set_payload_fields_INS,
            b'VEH': self.set_payload_fields_with_names,
            b'INI': self.set_payload_fields_INI_UPD,
            b'UPD': self.set_payload_fields_INI_UPD,
            b'AHRS': self.set_payload_field_AHRS,
        }
        decoderFunc = decoders.get(msgtype)
        if decoderFunc:
            decoderFunc(message, payload)
        else:
            message.valid = False
            message.error = "Unknown msgtype: "+msgtype.decode()
    
    def build_payload_for_type(self, message, msgtype):
        encoders = {
            b'CFG': self.build_payload_CFG,
            b'VEH': self.build_payload_CFG,
            b'VER': self.build_payload_no_fields,
            b'SER': self.build_payload_no_fields,
            b'PID': self.build_payload_no_fields,
            b'IHW': self.build_payload_no_fields,
            b'FHW': self.build_payload_no_fields,
            b'FSN': self.build_payload_no_fields,
            b'STA': self.build_payload_no_fields,
            b'RST': self.build_payload_RST,
            b'PNG': self.build_payload_no_fields,
            b'ECH': self.build_payload_ECH,
            b'ODO': self.build_payload_fields_ODO,
            b'INI': self.build_payload_INI_UPD,
            b'UPD': self.build_payload_INI_UPD,
        }
        encoderFunc = encoders.get(msgtype)
        if encoderFunc:
            return encoderFunc(message)
        else:
            raise Exception("trying to build unknown message type: "+msgtype.decode())

    def set_payload_fields_IMU(self, message, payload):
        #check with format by number of commas. num commas = num fields - 1
        #this relies on each format having different length.
        num_commas = payload.count(READABLE_PAYLOAD_SEPARATOR)

        for msg_format in [FORMAT_IMU_WITH_SYNC, FORMAT_IMU_NO_SYNC, FORMAT_IMU_X3_NO_STATUS, FORMAT_IMU_X3_WITH_STATUS, FORMAT_IMU_3FOG]:
            if num_commas == len(msg_format) - 1:
                self.set_fields_from_list(message, msg_format, payload)

                # split X3 status bit fields
                for bitfield_name in ["siphog_x_status", "siphog_y_status", "siphog_z_status"]:
                    if not hasattr(message, bitfield_name):
                        continue
                    combined_val = getattr(message, bitfield_name)
                    single_flags = {}
                    for flag_name, ind in SIPHOG_STATUS_BIT_POSITIONS.items():
                        single_flags[flag_name] = nth_bit(combined_val, ind)
                    setattr(message, f"{bitfield_name}_bits", single_flags)

                break

        else:
            message.valid = False
            message.error = f"unexpected length for IMU:  {num_commas}"

    #new IM1 type for IMU unit with/out FOG. should only have one length -> no need to count commas
    def set_payload_fields_IM1(self, message, payload):
        self.set_fields_from_list(message, FORMAT_IM1, payload)

    def set_payload_fields_INS(self, message, payload):
        # check with format by number of commas. num commas = num fields - 1
        num_commas = payload.count(READABLE_PAYLOAD_SEPARATOR)
        if num_commas == len(FORMAT_INS) - 1:
            self.set_fields_from_list(message, FORMAT_INS, payload)
        elif num_commas == len(FORMAT_INS_EXTRA_COMMA) - 1:
            self.set_fields_from_list(message, FORMAT_INS_EXTRA_COMMA, payload)
        #print(message)
        else:
            message.valid = False
            message.error = f"unexpected length for INS: {num_commas}"

        # carrier solution >= 8 means GPS off. separate into two attributes.
        if hasattr(message, "ins_solution_status_and_gps_used"):
            status_and_gps = message.ins_solution_status_and_gps_used
            if 255 > status_and_gps >= 8:
                message.ins_solution_status = status_and_gps - 8
                message.gps_used = False
            else:
                message.ins_solution_status = status_and_gps
                message.gps_used = True

    def set_payload_fields_GPS(self, message, payload):
        self.set_fields_from_list(message, FORMAT_GPS, payload)

    def set_payload_fields_GP2(self, message, payload):
        self.set_fields_from_list(message, FORMAT_GP2, payload)

    def set_payload_fields_ERR(self, message, payload):
        self.set_fields_from_list(message, FORMAT_ERR, payload)

    def set_payload_fields_HDG(self, message, payload):
        self.set_fields_from_list(message, FORMAT_HDG, payload)
        extract_flags_HDG(message)

            #CFG response: could have cfg data in response to CFG read
    #for CFG write - some confirmation message or error
    #all cfg fields are name, then value
    #TODO figure out type conversions
    def set_payload_fields_with_names(self, message, payload):
        separated = payload.split(READABLE_PAYLOAD_SEPARATOR)
        configurations = {}
        for i in range(0, len(separated), 2):
            cfg_name = separated[i].decode()
            cfg_value = separated[i+1]
            configurations[cfg_name] = cfg_value
        message.configurations = configurations

    def set_payload_fields_INI_UPD(self, message, payload):
        separated = payload.split(READABLE_PAYLOAD_SEPARATOR)
        configurations = {}

        # if first value is a number, treat it as timestamp, rest are name1,value1,name2,value2
        # not number start -> go straight to name,value,name,value
        try:
            timestamp = float(separated[0])
            configurations["timestamp"] = timestamp
            remaining_fields = separated[1:]
        except ValueError as e:
            remaining_fields = separated

        for i in range(0, len(remaining_fields), 2):
            cfg_name = remaining_fields[i].decode()
            cfg_value = remaining_fields[i+1]
            configurations[cfg_name] = cfg_value
        message.configurations = configurations

    def set_payload_fields_VER(self, message, payload):
        self.set_fields_from_list(message, FORMAT_VER, payload)
    
    def set_payload_fields_SER(self, message, payload):
        self.set_fields_from_list(message, FORMAT_SER, payload)
    
    def set_payload_fields_PID(self, message, payload):
        self.set_fields_from_list(message, FORMAT_PID, payload)

    def set_payload_fields_IHW(self, message, payload):
        self.set_fields_from_list(message, FORMAT_IHW, payload)

    def set_payload_fields_FHW(self, message, payload):
        self.set_fields_from_list(message, FORMAT_FHW, payload)

    def set_payload_fields_FSN(self, message, payload):
        self.set_fields_from_list(message, FORMAT_FSN, payload)
    
    def set_payload_fields_STA(self, message, payload):
        self.set_fields_from_list(message, FORMAT_STA, payload)
    
    def set_payload_fields_RST(self, message, payload):
        self.set_fields_from_list(message, FORMAT_RST, payload)
    
    def set_payload_fields_PNG(self, message, payload):
        self.set_fields_from_list(message, FORMAT_PNG, payload)
    
    def set_payload_fields_ECH(self, message, payload):
        message.contents = payload

    def set_payload_fields_ODO(self, message, payload):
        self.set_fields_from_list(message, FORMAT_ODO, payload)

    def set_payload_field_AHRS(self, message, payload):
        self.set_fields_from_list(message, FORMAT_AHRS, payload)

    #config message: mode is read or write
    #write has name, value pairs:   APCFG,w,odr,100,msg,IMU  is CFG with mode = write, odr = 10, msg = IMU
    #read has names only:           APCFG,r,odr,msg     is CFG with odr, msg
    #read configurations from a dictionary so they are not mixed with msgtype, etc. write as name,value,name,value
    def build_payload_CFG(self, message):
        mode = message.mode
        data = mode
        if mode in (WRITE_RAM, WRITE_FLASH):
            for name in message.configurations.keys():
                data += READABLE_PAYLOAD_SEPARATOR + name.encode() + READABLE_PAYLOAD_SEPARATOR + message.configurations[name]
        elif mode in (READ_RAM, READ_FLASH):
            for name in message.configurations:
                data += READABLE_PAYLOAD_SEPARATOR + name.encode()
        else:
            raise Exception("unknown mode for CFG message")
        return data

    #many messages have no fields, mostly if they are requests(requested resource is the message type)
    def build_payload_no_fields(self, message):
        return None

    def build_payload_RST(self, message):
        return str(message.code).encode()

    def build_payload_ECH(self, message):
        return message.contents

    def build_payload_fields_ODO(self, message):
        return str(message.speed).encode()

    # Combined INI and UPD function since they have the same fields.
    # use key1,value1,key2,value2... like APCFG
    def build_payload_INI_UPD(self, message):
        data = b""
        for name, val in message.configurations.items():
            assert name in INI_UPD_FIELDS, f"unexpected init or update field: {name}"
            data += name.encode() + READABLE_PAYLOAD_SEPARATOR + val.encode() + READABLE_PAYLOAD_SEPARATOR
        return data[:-1]  # remove ending comma

    # get fields based on config with the correct type like int, float, bytes
    def set_fields_from_list(self, message, format_list, data):
        #allow passing data as bytes -> split, or list already split
        if type(data) is list:
            separated = data
        else:
            separated = data.split(READABLE_PAYLOAD_SEPARATOR)
        for i, part in enumerate(separated):
            if part:    #missing field will be None, can't convert to float
                var_name, var_type = format_list[i]
                #handle special cases: time, degrees
                #TODO can take these out if we remove GPS types from board output
                if var_type == "time": 
                    #time in hhmmss.ss format -> hours(int), min(int), second(float)
                    hours_part = int(part[:2])
                    minutes_part = int(part[2:4])
                    seconds_part = float(part[4:])
                    setattr(message, var_name+"_hours", hours_part)
                    setattr(message, var_name+"_minutes", minutes_part)
                    setattr(message, var_name+"_seconds", seconds_part)
                elif var_type == "degrees":
                    #angle in (d)ddmm.mmmmm format -> degrees(int), minutes(float)
                    #could be 2 or 3 degrees digits, but has 2 m digits before .
                    split_point = part.find(b'.') - 2
                    degrees_part = int(part[:split_point])
                    seconds_part = float(part[split_point:])
                    setattr(message, var_name+"_degrees", degrees_part)
                    setattr(message, var_name+"_minutes", seconds_part)
                    pass
                else: 
                    #regular case- use a python type
                    value = var_type(part)
                    setattr(message, var_name, value)

    #compute the checksum as an int
    def compute_checksum(self, data):
        total = 0
        for num in data: #this treats each byte as an integer
            total ^= num
        return total

    def checksum_passes(self, message):
        return self.compute_checksum(message.checksum_input) == message.checksum
