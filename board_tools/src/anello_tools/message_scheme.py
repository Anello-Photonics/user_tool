from abc import ABC, abstractmethod


# message encoding scheme - can be $-type or aa4412 - type
class Scheme(ABC):

    def read_one_message(self, connection):
        pass

    def write_one_message(self, message, connection):
        pass

    def parse_message(self, data):
        m = Message()
        self.set_fields_general(m, data)
        return m

    def set_fields_general(self, message, data):
        pass

    def build_message_general(self, message):
        pass

    def check_valid(self, message):
        pass

    def decode_payload_for_type(self, message, msgtype, payload):
        pass

    def build_payload_for_type(self, message, msgtype):
        pass

    def set_fields_from_list(self, message, format_list, data):
        pass

    def compute_checksum(self, message):
        pass

    def checksum_passes(self, message):
        pass


# one message: has fields, can be valid or invalid
class Message:

    def __init__(self, var_dict={}):
        for name in var_dict:
            setattr(self, name, var_dict[name])

    def __str__(self):
        return "Message: " + str(self.__dict__)

    def __repr__(self):
        return "Message: " + str(self.__dict__)

