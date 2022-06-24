try:  # importing from inside the package
    from message_scheme import Scheme, Message
    from config.readable_scheme_config import *
    from connection import *
except ModuleNotFoundError:  # importing from outside the package
    from anello_tools.message_scheme import Scheme, Message
    from anello_tools.config.readable_scheme_config import *
    from anello_tools.connection import *

# b'AA' -> 170
def ascii_to_int(x):
    return int(x, 16)

#170 -> b'AA'
def int_to_ascii(x):
    return "{0:0{1}X}".format(x,2).encode()

#messages encoded in readable form with start and end codes, comma separted values
class ReadableScheme(Scheme):
    
    #since there are start and end codes, read everything between them as one message
    def read_one_message(self, connection):
        # UDPConnection doesn't have a read_until, it reads entire lines. So need different handling here
        # TODO - moving read_one_message into connection class might be more tidy. then it needs to know start/end codes
        if type(connection) is UDPConnection:
            data = connection.readall() #TODO does it need a read until end char function?
        else:
            before = connection.read_until(READABLE_START)
            #TODO can handle partial start on whatever came before start code
            data = connection.read_until(READABLE_END)
        if not data:
            return None
        #print("receiving: "+data.decode())
        if data[:len(READABLE_START)] == READABLE_START: #chop off start code if present
            data = data[len(READABLE_START):]
        if data[-len(READABLE_END):] == READABLE_END: #chop off end code if present
            data = data[:-len(READABLE_END)]
        else:
            pass #TODO if no end code, could handle partial read or give an error
        if data:
            message = Message()
            self.set_fields_general(message, data)
            return message

    #write a single message to the connection
    def write_one_message(self, message, connection):
        data = READABLE_START + self.build_message_general(message) + READABLE_END
        #print("sending: "+data.decode()) #debug message creation
        connection.write(data)

    def set_fields_general(self, message, data):
        try:
            message.data = data
            sep_index = data.find(READABLE_CHECKSUM_SEPARATOR)
            message.checksum_input = data[:sep_index]
            message.checksum = ascii_to_int(data[sep_index+len(READABLE_CHECKSUM_SEPARATOR):]) #int(data[sep_index+len(READABLE_PAYLOAD_SEPARATOR):], 16) #it has bytes which read as the hex value

            #could split these from data or from message.checksum_input
            message.talker = data[0: READABLE_TALKER_LENGTH]
            message.msgtype = data[READABLE_TALKER_LENGTH: READABLE_TALKER_LENGTH + READABLE_TYPE_LENGTH]
            message.payload = data[READABLE_TALKER_LENGTH + READABLE_TYPE_LENGTH + len(READABLE_PAYLOAD_SEPARATOR): sep_index]
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
        #then, message can be formed in Session and still work with ByteScheme, assuming message types and fields are consistent.
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
            b'CAL': self.set_payload_fields_CAL,
            b'IMU': self.set_payload_fields_IMU,
            b'GPS': self.set_payload_fields_GPS,
            b'ERR': self.set_payload_fields_ERR,
            b'CFG': self.set_payload_fields_with_names,
            b'VER': self.set_payload_fields_VER,
            b'SER': self.set_payload_fields_SER,
            b'PID': self.set_payload_fields_PID,
            b'STA': self.set_payload_fields_with_names,
            b'RST': self.set_payload_fields_RST,
            b'PNG': self.set_payload_fields_PNG,
            b'ECH': self.set_payload_fields_ECH,
            b'ODO': self.set_payload_fields_ODO,
            b'INS': self.set_payload_fields_INS,
            b'VEH': self.set_payload_fields_with_names
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
            b'STA': self.build_payload_no_fields,
            b'RST': self.build_payload_RST,
            b'PNG': self.build_payload_no_fields,
            b'ECH': self.build_payload_ECH,
            b'ODO': self.build_payload_fields_ODO
        }
        encoderFunc = encoders.get(msgtype)
        if encoderFunc:
            return encoderFunc(message)
        else:
            raise Exception("trying to build unknown message type: "+msgtype.decode())

    def set_payload_fields_CAL(self, message, payload):
        self.set_fields_from_list(message, FORMAT_CAL, payload) 

    def set_payload_fields_IMU(self, message, payload):
        #check with format by number of commas. num commas = num fields - 1
        num_commas = payload.count(READABLE_PAYLOAD_SEPARATOR)
        if num_commas == len(FORMAT_IMU) -1:
            self.set_fields_from_list(message, FORMAT_IMU, payload)
        elif num_commas == len(FORMAT_IMU_WITH_FOG_VOLTS) - 1:
            self.set_fields_from_list(message, FORMAT_IMU_WITH_FOG_VOLTS, payload)

    def set_payload_fields_INS(self, message, payload):
        # check with format by number of commas. num commas = num fields - 1
        num_commas = payload.count(READABLE_PAYLOAD_SEPARATOR)
        if num_commas == len(FORMAT_INS) - 1:
            self.set_fields_from_list(message, FORMAT_INS, payload)
        elif num_commas == len(FORMAT_INS_EXTRA_COMMA) - 1:
            self.set_fields_from_list(message, FORMAT_INS_EXTRA_COMMA, payload)

    def set_payload_fields_GPS(self, message, payload):
        self.set_fields_from_list(message, FORMAT_GPS, payload)

    def set_payload_fields_ERR(self, message, payload):
        self.set_fields_from_list(message, FORMAT_ERR, payload)

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

    def set_payload_fields_VER(self, message, payload):
        self.set_fields_from_list(message, FORMAT_VER, payload)
    
    def set_payload_fields_SER(self, message, payload):
        self.set_fields_from_list(message, FORMAT_SER, payload)
    
    def set_payload_fields_PID(self, message, payload):
        self.set_fields_from_list(message, FORMAT_PID, payload)
    
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