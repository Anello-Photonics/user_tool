from ctypes import *
import os
import struct
from bitstring import Bits
from pyrtcm import RTCMReader, crc2bytes, calc_crc24q
try:  # importing from inside the package
    from pyrtcm import RTCMReader, RTCMParseError
    from class_configs.rtcm_scheme_config import * #TODO make config file with fomats
    from readable_scheme import extract_flags_HDG
    from message_scheme import Scheme, Message
except ModuleNotFoundError:  # importing from outside the package
    from anello_tools.class_configs.rtcm_scheme_config import *
    from anello_tools.readable_scheme import extract_flags_HDG
    from anello_tools.message_scheme import Scheme, Message

#decoder for RTCM-style binary messages

#Common packet format:
#   Preamble    |   Reserved    |   Length  |   payload |   CRC
#   0xD3        | 000000 (6 bit)|   10 bits |           |   3 byte


class RTCM_Scheme(Scheme):
    def read_one_message(self, connection):
        try:
            stream = RTCMReader(connection)
            message = Message()
            self.set_fields_general(message, stream.read()[0][1:])
        except:
            # TODO be more specific about exception
            pass
        return message

    #read one message from file using RTCMReader . could use that for usb or ethernet reading too
    def read_message_from_file(self, input_file):
        if (not hasattr(self, "reader")) or self.reader is None:
            self.reader = RTCMReader(input_file)
        message = Message()
        try:
            raw, parsed = self.reader.read()
            #strip off preamble then pass the raw data to set_fields_general.
            #or if using parsed, it would already have the message tye (4058) and checksum split from payload
            if raw:
                data = raw.lstrip(RTCM_PREAMBLE)
                self.set_fields_general(message, data)
            else: #complete. TODO - is this the correct check for end of file? seems to work.
                return None
        except RTCMParseError: #error from RTCMReader.read if checksum fails
            message.valid = False
            message.error = "checksum"
        except Exception as e: #catchall error
            message.valid = False
            message.error = "parsing error: "+str(e)
        return message

    #   Preamble    |   Reserved    |   Length  | msgtype               |   payload     |   CRC
    #   0xD3        | 000000 (6 bit)|   10 bits | 12+4 bit = 2 bytes    |variable length|   3 byte

    def set_fields_general(self, message, full_data):
        #split into preamble/lentgh/payload/crc , then check_valid
        try:
            #message.data = data
            length_and_reserved = Bits(full_data[0: LENGTH_LENGTH]) #6 bit reserved zeros, 10 bit lenght - separate them too?
            type_and_subtype = Bits(full_data[LENGTH_LENGTH: LENGTH_LENGTH + TYPE_LENGTH])  # 12+4 bit = 2 bytes. TODO - split them?
            #print(f"type_and_subtype = {type_and_subtype}")

            #split reserved/payload length
            reserved, rtcm_length = Bits(bin=length_and_reserved.bin[:6]).uint, Bits(bin=length_and_reserved.bin[6:]).uint
            payload_length = rtcm_length - TYPE_LENGTH #if rtcm length includes the whole "data message", payload is smaller
            message.payload_length = payload_length

            #split type/subtype
            company_code, msgtype = Bits(bin=type_and_subtype.bin[:12]).uint, Bits(bin=type_and_subtype.bin[12:]).uint
            message.company_code = company_code
            message.rtcm_msgtype = msgtype

            message.payload = full_data[LENGTH_LENGTH + TYPE_LENGTH: LENGTH_LENGTH + TYPE_LENGTH + payload_length]
            checksum_bytes = full_data[LENGTH_LENGTH + TYPE_LENGTH + payload_length:
                                  LENGTH_LENGTH + TYPE_LENGTH + payload_length + RTCM_CRC_LEN]

            #message.data: up to expected end, ignore extras after. should it do anythinig with the extras?
            message.data = full_data[0: LENGTH_LENGTH + TYPE_LENGTH + payload_length + RTCM_CRC_LEN]
            message.checksum = int.from_bytes(checksum_bytes, ENDIAN, signed=True)
            #message.checksum_input = message.rtcm_msgtype + payload_length_b + message.payload #TODO - what goes into checksum?
            if self.check_valid(message):
                self.decode_payload_for_type(message, message.rtcm_msgtype, message.payload)

            #tag as message types equivalent to ascii messages, including GPS/GP2 depending on gps message antenna id
            message.msgtype = EQUIVALENT_MESSAGE_TYPES.get(msgtype, b'Unknown')
            if msgtype == RTCM_MSGTYPE_GPS and hasattr(message, "antenna_id"):
                message.msgtype = b'GPS' if message.antenna_id == 0 else b'GP2'

            #imu time ns to ms conversion: keep both on the message
            if hasattr(message, "imu_time_ns"):
                message.imu_time_ms = message.imu_time_ns / 1e6
            if hasattr(message, "odometer_time_ns"):
                message.odometer_time_ms = message.odometer_time_ns / 1e6
            if hasattr(message, "sync_time_ns"):
                message.sync_time_ms = message.sync_time_ns / 1e6
            #TODO - tag delta t by message type too?

        except Exception as e:
            #print(f"error in set_fields_general for data: {full_data}")
            #print(e)
            message.valid=False

    def check_valid(self, message):
        try:
            if message.rtcm_msgtype not in RTCM_MESSAGE_TYPES:
                message.valid = False
                message.error = "Msgtype"
            #check lengths add up?
            # elif message.payload_length + TYPE_LENGTH + LENGTH_LENGTH + CRC_LENGTH != len(message.data):
            #     print(f'Payload length: {message.payload_length}')
            #     print(f'Type length: {TYPE_LENGTH}')
            #     print(f'Length length: {LENGTH_LENGTH}')
            #     print(f'CRC length: {CRC_LENGTH}')
            #     print(f'Length sum: {message.payload_length + TYPE_LENGTH + LENGTH_LENGTH + CRC_LENGTH}')
            #     print(f'len(message.data): {len(message.data)}')
            #     message.valid = False
            #     message.error = "Length"
            elif not self.checksum_passes(message):
                message.valid = False
                message.error = "Checksum Fail"
            else:
                message.valid = True
                message.error = None
            return message.valid
        except Exception as err:
            #print("exception checking message with data: "+str(message.data)+" , len = "+str(len(message.data)))
            message.valid = False
            message.error = "Check Error: "+str(err)

    def decode_payload_for_type(self, message, msgtype, payload):
        # RTCM_MESSAGE_TYPES = [RTCM_MSGTYPE_IMU, RTCM_MSGTYPE_GPS, RTCM_MSGTYPE_HEADING, RTCM_MSGTYPE_INS]
        if message.rtcm_msgtype not in RTCM_MESSAGE_TYPES:
            return
        if message.rtcm_msgtype == RTCM_MSGTYPE_IMU:
            self.set_fields_from_list_scaled(message, RTCM_IMU_PAYLOAD_FIELDS_WITH_SYNC, payload)
            #if parse with one format fails, try the other (or should it decide using length?)
            if not message.valid:
                message.valid = True #need this or it will stay invalid. will be invalid again if second parse fails.
                self.set_fields_from_list_scaled(message, RTCM_IMU_PAYLOAD_FIELDS_NO_SYNC, payload)
        elif message.rtcm_msgtype == RTCM_MSGTYPE_IM1:
            self.set_fields_from_list_scaled(message, RTCM_IM1_PAYLOAD_FIELDS, payload)
        elif message.rtcm_msgtype == RTCM_MSGTYPE_INS:
            self.set_fields_from_list_scaled(message, RTCM_INS_PAYLOAD_FIELDS, payload)
        elif message.rtcm_msgtype == RTCM_MSGTYPE_GPS:
            self.set_fields_from_list_scaled(message, RTCM_GPS_PAYLOAD_FIELDS, payload)
        elif message.rtcm_msgtype == RTCM_MSGTYPE_HEADING:
            self.set_fields_from_list_scaled(message, RTCM_DUAL_ANT_HEAD_FIELDS, payload)
            extract_flags_HDG(message) #separate the heading flags in "flags" attribute, from ReadableScheme

        #do any computed fields like adjusting time units after?

    #Individual decoders go here
    # TODO this might also go in the message type handler
    def set_fields_from_list(self, message, format_list, data):
        try:
            #print(f'Payload length: {message.payload_length}')
            format_str = "<" if ENDIAN == "little" else ">"
            attr_names = []
            for (name, format_code) in format_list:
                format_str += format_code
            values = struct.unpack(format_str, data)
            for i, (name, format_code) in enumerate(format_list):
                setattr(message, name, values[i])
        except Exception as e:
            # print("error in set_fields_from_list")
            # print(e)
            message.valid = False
            message.error = "Length(unpack)"

    #version with optional scale factor as 3rd number of tuple in format_list
    def set_fields_from_list_scaled(self, message, format_list, data):
        try:
            #print(f'Payload length: {message.payload_length}')
            data_offset = 0
            for item in format_list:
                if len(item) == 3:
                    name, format_code, scale = item
                elif len(item) == 2:
                    name, format_code = item
                    scale = 1
                else:
                    #print(f"wrong length in format: {item}")
                    continue
                format_str = "<" if ENDIAN == "little" else ">"
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
            #print("error in set_fields_from_list")
            #print(e)
            message.valid = False
            message.error = "Length(unpack)"

    # def compute_checksum(self, message):
    #     #TODO - implement 3-byte RTCM checksum
    #     pass

    def checksum_passes(self, message):
        #return self.compute_checksum(message) == message.checksum or something
        #if computed on whole message data including the checksum, should be 0.
        return crc2bytes(RTCM_PREAMBLE + message.data) == b'\00\x00\x00'
        #return True
