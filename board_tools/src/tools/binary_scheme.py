from ctypes import *
import os
import struct
from bitstring import Bits
from pyrtcm import RTCMReader, crc2bytes, calc_crc24q
try:  # importing from inside the package
    #from pyrtcm import RTCMReader, RTCMParseError
    #from pyrtcm.rtcmtypes_core import ERR_RAISE, ERR_LOG, ERR_IGNORE
    from class_configs.binary_scheme_config import * #TODO make config file with fomats
    from readable_scheme import extract_flags_HDG, SIPHOG_STATUS_BIT_POSITIONS, nth_bit
    from message_scheme import Scheme, Message
except ModuleNotFoundError:  # importing from outside the package
    from tools.class_configs.binary_scheme_config import *
    from tools.readable_scheme import extract_flags_HDG, SIPHOG_STATUS_BIT_POSITIONS, nth_bit
    from tools.message_scheme import Scheme, Message

#decoder for our custom binary messages, shorter than RTCM format

class Binary_Scheme(Scheme):

    # simple version by getting data between preambles. TODO - use state machine and check the length
    def read_one_message(self, connection):
        read_data = connection.read_until(BINARY_PREAMBLE)
        if read_data == BINARY_PREAMBLE: #first one gets just preamble -> read again
            read_data = connection.read_until(BINARY_PREAMBLE)
        #read_data = read_data.rstrip(BINARY_PREAMBLE).lstrip(BINARY_PREAMBLE)  # remove preamble from end
        # TODO - sometimes preamble ends in C5 or 50 byte, so this causes about 2/256 checksum fails.

        if read_data:
            parsed_msg = Message()
            self.set_fields_general(parsed_msg, read_data)
            return parsed_msg

    # try using length field -> do actual state machine or just go through all steps in one function call?
    # TODO - reading fixed number of characters may not work on UDP connection -> add a buffer?
    def read_one_message_withlength(self, connection):
        m = Message()
        m.valid = False  # set_fields_general will set this true if it parses correctly.

        # read until preamble, keep going until preamble found or length limit
        find_preamble_tries = 200
        buf = b''
        found_preamble = False
        for i in range(find_preamble_tries):
            next_char = connection.read(1)
            if next_char in [b'', None]:
                return None  # happens at end of file or closed port -> let calling function handle it.
            buf += next_char
            if buf.endswith(BINARY_PREAMBLE):
                found_preamble = True
                break
        if not found_preamble:
            return m  # empty message , so it reads as invalid message instead of port closed

        # get type, reset if not a known type.
        msgtype_bytes = connection.read(BINARY_TYPE_LENGTH)
        binary_msgtype = int.from_bytes(msgtype_bytes, BINARY_ENDIAN)

        equivalent_type = BINARY_EQUIVALENT_MESSAGE_TYPES.get(binary_msgtype, b'Unknown')
        if equivalent_type == b'Unknown':
            m.error = "Msgtype"
            return m

        # get length:
        length_bytes = connection.read(BINARY_LENGTH_LENGTH)
        payload_length = int.from_bytes(length_bytes, BINARY_ENDIAN)
        # TODO: reset if length too big? 1 length byte -> up to 255 length, biggest binary message is 48.

        # read payload of the expected length, then checksum.
        payload_bytes = connection.read(payload_length)
        checksum_bytes = connection.read(BINARY_CRC_LEN)

        # parse the payload in other function (or it could use the parsed fields here)
        full_data = msgtype_bytes + length_bytes + payload_bytes + checksum_bytes
        self.set_fields_general(m, full_data)
        return m

    # read one message from file using RTCMReader . could use that for usb or ethernet reading too
    # def read_message_from_file(self, input_file):
    #     if (not hasattr(self, "reader")) or self.reader is None:
    #         self.reader = RTCMReader(input_file, quitonerror=ERR_RAISE) #ERR_RAISE means errors raise RTCMParseError
    #     message = Message()
    #     parsed = None  # for error handlers if reader.read() fails
    #     try:
    #         raw, parsed = self.reader.read()
    #         if raw:
    #             self.set_fields_general(message, raw)
    #         elif parsed is None:  # end of file returns (raw = None, parsed = None)
    #             return None
    #         else:  # errors could return (None, Error Code) but should raise RTCMParseERROR if using ERR_RAISE
    #             message.valid = False
    #             message.error = "RTCM parsing error" # + str(parsed)
    #     except RTCMParseError:  # errors from RTCMReader.read
    #         message.valid = False
    #         message.error = "RTCM parsing error" # + str(parsed)
    #     except Exception as e:  # catchall error
    #         message.valid = False
    #         message.error = "parsing error: "+str(e)
    #     return message

    def set_fields_general(self, message, raw_data):
        #split into preamble/lentgh/payload/crc , then check_valid
        try:
            #print(f"set_fields_general:    {raw_data}")

            # 'raw_data = raw_data.rstrip(BINARY_PREAMBLE).lstrip(BINARY_PREAMBLE)  # remove preamble from ends if present
            # TODO - sometimes checksum ends in C5 or 50 byte, so this causes about 2/256 checksum fails.

            # take preamble off if it starts with preamble. no need to remove from end
            preamble_length = len(BINARY_PREAMBLE)
            if raw_data[:preamble_length] == BINARY_PREAMBLE:
                raw_data = raw_data[preamble_length:]

            # data here is:  msgtype, length, payload, checksum  (preamble already removed)
            msgtype_ind = 0
            length_ind = BINARY_TYPE_LENGTH
            payload_ind = BINARY_TYPE_LENGTH + BINARY_LENGTH_LENGTH

            msgtype_bytes = raw_data[msgtype_ind: length_ind] #[0: BINARY_TYPE_LENGTH]
            #print(f"msgtype bytes: {msgtype_bytes}")
            binary_msgtype = int.from_bytes(msgtype_bytes, BINARY_ENDIAN)
            #print(f'msgtype number: {binary_msgtype}')
            message.binary_msgtype = binary_msgtype

            length_bytes = raw_data[length_ind: payload_ind]
            #print(f"length bytes: {length_bytes}")
            payload_length = int.from_bytes(length_bytes, BINARY_ENDIAN)
            message.payload_length = payload_length
            #print(f"converted length: {payload_length}")

            checksum_ind = BINARY_TYPE_LENGTH + BINARY_LENGTH_LENGTH + payload_length
            end_ind = BINARY_TYPE_LENGTH + BINARY_LENGTH_LENGTH + payload_length + BINARY_CRC_LEN

            message.payload = raw_data[payload_ind: checksum_ind]
            checksum_bytes = raw_data[checksum_ind: end_ind]
            message.checksum = checksum_bytes  # int.from_bytes(checksum_bytes, BINARY_ENDIAN, signed=True)

            # the preamble bytes and checksum itself are not used in checksum : so is it type, length, payload?
            # preamble was already removed, so this is everything before the checksum
            message.checksum_input = raw_data[:checksum_ind]
            #print(f"data for checksum calc: {message.checksum_input}")

            #message.data: up to expected end, ignore extras after. should it do anythinig with the extras?
            message.raw_data = raw_data
            message.data = raw_data[: end_ind]

            #tag as message types equivalent to ascii messages, including GPS/GP2 depending on gps message antenna id
            equivalent_type = BINARY_EQUIVALENT_MESSAGE_TYPES.get(message.binary_msgtype, b'Unknown')
            message.msgtype = equivalent_type
            #print(f"equivalent message type: {equivalent_type}")

            if self.check_valid(message):
                self.decode_payload_for_type(message, message.binary_msgtype, message.payload)
                #pass

            #Binary GPS/GP2: 4 bit carrsoln, 4 bit fix type
            if hasattr(message, "carrsoln_and_fix"):
                message.carrier_solution_status = message.carrsoln_and_fix // 16 #first 4/8 bits
                message.gnss_fix_type = message.carrsoln_and_fix % 16 #last 4/8 bits

            # carrier solution >= 8 means GPS off. separate into two attributes.
            if hasattr(message, "ins_solution_status_and_gps_used"):
                status_and_gps = message.ins_solution_status_and_gps_used
                if 255 > status_and_gps >= 8:
                    message.ins_solution_status = status_and_gps - 8
                    message.gps_used = False
                else:
                    message.ins_solution_status = status_and_gps
                    message.gps_used = True

            # imu time ns to ms conversion: keep both on the message
            if hasattr(message, "imu_time_ns"):
                message.imu_time_ms = message.imu_time_ns / 1e6
            if hasattr(message, "odometer_time_ns"):
                message.odometer_time_ms = message.odometer_time_ns / 1e6
            if hasattr(message, "sync_time_ns"):
                message.sync_time_ms = message.sync_time_ns / 1e6
            #TODO - tag delta t by message type too?

            # do MEMS range conversions -> scale the accel and rate
            # mems ranges: 5 bits accel range, 11 bits rate range. fog range is just one
            # don't adjust for fog range yet, not used and usually set to 0
            if message.msgtype == b'IMU' and message.valid:
                message.accel_range = message.mems_ranges // pow(2,11)
                message.rate_range = message.mems_ranges - (message.accel_range * pow(2,11))

                for accel_attr in ["accel_x_g", "accel_y_g", "accel_z_g"]:
                    setattr(message, accel_attr, message.accel_range * getattr(message, accel_attr))

                for rate_attr in ["angrate_x_dps", "angrate_y_dps", "angrate_z_dps"]:
                    setattr(message, rate_attr, message.rate_range * getattr(message, rate_attr))



        except Exception as e:
            print(f"error in set_fields_general for data: {raw_data}")
            print(e)
            message.valid=False

    def check_valid(self, message):
        try:
            if message.binary_msgtype not in BINARY_MESSAGE_TYPES:
                message.valid = False
                message.error = "Msgtype"
            #check lengths add up?
            # elif message.payload_length + BINARY_TYPE_LENGTH + BINARY_LENGTH_LENGTH + CRC_LENGTH != len(message.data):
            #     print(f'Payload length: {message.payload_length}')
            #     print(f'Type length: {TYPE_LENGTH}')
            #     print(f'Length length: {LENGTH_LENGTH}')
            #     print(f'CRC length: {CRC_LENGTH}')
            #     print(f'Length sum: {message.payload_length + BINARY_TYPE_LENGTH + BINARY_LENGTH_LENGTH + CRC_LENGTH}')
            #     print(f'len(message.data): {len(message.data)}')
            #     message.valid = False
            #     message.error = "Length"
            elif not self.checksum_passes(message):
                message.valid = False
                message.error = "Checksum Fail"
                #print(f"checksum failed on message: {message}")
            else:
                #print("checksum pass")
                message.valid = True
                message.error = None
            return message.valid
        except Exception as err:
            #print("exception checking message with data: "+str(message.data)+" , len = "+str(len(message.data)))
            message.valid = False
            message.error = "Check Error: "+str(err)

    def decode_payload_for_type(self, message, msgtype, payload):
        # look up the message format and parse for that format.

        msgtype = message.binary_msgtype
        if msgtype not in BINARY_MESSAGE_TYPES:
            return

        msg_format = BINARY_MESSAGE_TYPES[msgtype]
        self.set_fields_from_list_scaled(message, msg_format, payload)

        # any parsing special cases go here

        # HDG: extra flags to extract
        if msgtype == BINARY_MSGTYPE_HDG:
            extract_flags_HDG(message)  # separate the heading flags in "flags" attribute, from ReadableScheme

        # split X3 status bit fields. one "16 bit" int is really 12 bits, 4 status bits per siphog
        if msgtype == BINARY_MSGTYPE_X3_IMU and hasattr(message, "status_info"):
            axis_offsets = {"x": 0, "y": 8, "z": 4}  # 4 bits per axis starting at 0, in xzy order
            for ax, offset in axis_offsets.items():
                single_flags = {}
                for flag_name, ind in SIPHOG_STATUS_BIT_POSITIONS.items():
                    single_flags[flag_name] = nth_bit(message.status_info, ind+offset)
                setattr(message, f"siphog_{ax}_status_bits", single_flags)

    #Individual decoders go here
    # TODO this might also go in the message type handler
    # def set_fields_from_list(self, message, format_list, data):
    #     try:
    #         #print(f'Payload length: {message.payload_length}')
    #         format_str = "<" if BINARY_ENDIAN == "little" else ">"
    #         attr_names = []
    #         for (name, format_code) in format_list:
    #             format_str += format_code
    #         values = struct.unpack(format_str, data)
    #         for i, (name, format_code) in enumerate(format_list):
    #             setattr(message, name, values[i])
    #     except Exception as e:
    #         # print("error in set_fields_from_list")
    #         # print(e)
    #         message.valid = False
    #         message.error = "Length(unpack)"

    #version with optional scale factor as 3rd number of tuple in format_list
    def set_fields_from_list_scaled(self, message, format_list, data):
        try:
            #print(f'Payload length: {message.payload_length}')
            data_offset = 0
            for item in format_list:
                if len(item) == 3:
                    name, format_name, scale = item
                elif len(item) == 2:
                    name, format_name = item
                    scale = 1
                else:
                    #print(f"wrong length in format: {item}")
                    continue
                format_str = "<" if BINARY_ENDIAN == "little" else ">"
                format_code = NUMBER_TYPES.get(format_name, format_name)  # lookup name -> code. if not found, name itself is the code
                format_str += format_code
                chunk_size = struct.calcsize(format_str)
                data_chunk = data[data_offset:data_offset+chunk_size]
                #message.setattr()
                #value = struct.unpack_from(format_str, data, offset=data_offset)[0]
                value = struct.unpack(format_str, data_chunk)[0]
                data_offset += chunk_size #struct.calcsize(format_str)
                #scale the value if numerical, put in the message.
                # todo: should it put the un-scaled value in the message too? group the values as a dictionary?

                if type(value) in [int, float]:
                    scaled_value = scale * value
                else:
                    scaled_value = value

                # setattr(message, name, value)
                #setattr(message, name+"_scaled", scaled_value)
                setattr(message, name, scaled_value) #scaled only

                # print(f"\nfor item {item}:")
                # print(f"format_str = {format_str}")
                # print(f"chunk_size = {chunk_size}")
                # print(f"data_chunk = {data_chunk}")
                # print(f"value = {value}")
                # print(f"scaled value = {scaled_value}")

        except Exception as e:
            print("error in set_fields_from_list")
            print(e)
            message.valid = False
            message.error = "Length(unpack)"

    def checksum_passes(self, message):
        #print(f"checksum passes: message = {message}")
        computed_checksum = binary_checksum(message.checksum_input)
        #print(f"computed checksum: {computed_checksum}")
        return computed_checksum == message.checksum


#checksum for binary format, same as ublox and Siphog. takes bytes, returns bytes
def binary_checksum(input_data):
    checksum_a = 0
    checksum_b = 0
    for msg_char in input_data:  # loops over bytes as ints.
        checksum_a = checksum_a + msg_char  # do %256 here?
        checksum_b = checksum_b + checksum_a  # do %256 here?
    # turn them back into bytes types, append
    return (checksum_a % 256).to_bytes(1, BINARY_ENDIAN) + (checksum_b % 256).to_bytes(1, BINARY_ENDIAN)  # needs checking