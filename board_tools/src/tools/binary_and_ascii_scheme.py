# for X3: parse mix of binary output messages with ASCII configuration messages on one port

try:  # importing from inside the package
    from message_scheme import Scheme, Message
    from class_configs.readable_scheme_config import *
    from connection import *
    from readable_scheme import *
    from rtcm_scheme import *
    from binary_scheme import *
except ModuleNotFoundError:  # importing from outside the package
    from tools.message_scheme import Scheme, Message
    from tools.class_configs.readable_scheme_config import *
    from tools.connection import *
    from tools.readable_scheme import *
    from tools.rtcm_scheme import *
    from tools.binary_scheme import *

from enum import Enum

states = Enum("states", [
    "start",
    "ascii_preamble_1",
    "ascii_preamble_2",
    "ascii_body",
    "ascii_cs1",
    "ascii_cs2",
    "binary_preamble",
    "binary_type",
    "binary_length",
    "binary_body",
    # "binary_cs1",
    # "binary_cs2",
])
# make a separate function for each state update? or could use libraries like python-statemachine

READ_LIMIT_BYTES = 1000  # need a limit in case of wrong baud or wrong device. must be longer than longest message.


class Binary_and_ASCII_Scheme(Scheme):

    def __init__(self):
        self.state = states.start
        self.ascii_scheme = ReadableScheme()
        self.binary_scheme = Binary_Scheme()
        self.binary_length_counter = 0
        self.expected_body_length = 0
        self.message_data = b""
        self.returned_message_type = None

    # send config messages in ASCII.
    def write_one_message(self, message, connection):
        self.ascii_scheme.write_one_message(message, connection)

    def read_one_message(self, connection):
        message_type, message_data = self.mixed_reader(connection)

        if not message_data:
            return None

        parsed_msg = Message()
        if message_type == "ASCII":
            self.ascii_scheme.set_fields_general(parsed_msg, message_data)
        elif message_type == "Binary":
            self.binary_scheme.set_fields_general(parsed_msg, message_data)
        return parsed_msg

    # read one character at a time using state machine
    # on either start character, start reading message by the matching message format
    # on binary message: go until the specified length (unless too big) since C5, #, * could occur in binary data
    # on ASCII message: go until the *cs. or end early on C5, # which should not happen in message.

    def mixed_reader(self, connection):
        self.message_data = b""
        self.returned_message_type = None
        for i in range(READ_LIMIT_BYTES):
            # trying approach 1: read one character at a time here, no reading inside the state handlers
            next_char = connection.read(1)  # TODO - time out if next char doesn't read? -> return None or b""
            if next_char is None or len(next_char) == 0:
                # print("next_char is None")
                return None, None

            self.message_data += next_char   # do this here or inside handlers?
            # or approach 2: read inside the handlers: can do multiple reads for binary preamble, checksum, message body

            # do function for each state: make this a dictionary or something?
            if self.state == states.start:
                func = self.start_handler
            elif self.state == states.ascii_preamble_1:
                func = self.ascii_preamble_1_handler
            elif self.state == states.ascii_preamble_2:
                func = self.ascii_preamble_2_handler
            elif self.state == states.ascii_body:
                func = self.ascii_body_handler
            elif self.state == states.ascii_cs1:
                func = self.ascii_cs1_handler
            elif self.state == states.ascii_cs2:
                func = self.ascii_cs2_handler
            elif self.state == states.binary_preamble:
                func = self.binary_preamble_handler
            elif self.state == states.binary_type:
                func = self.binary_type_handler
            elif self.state == states.binary_length:
                func = self.binary_length_handler
            elif self.state == states.binary_body:
                func = self.binary_body_handler
            else:
                raise Exception(f"unexpected state: {self.state}")

            next_state, done = func(next_char)  # if reading in mixed_reader
            #print(next_char, func, next_state, done)

            self.state = next_state  # set this in handlers instead of returning it?

            if done:
                return self.returned_message_type, self.message_data
            #print(f"mixed_reader iteration {i}: char is <{next_char}>")
        # reached read limit
        return None, None

    # methods for each state update:

    # binary if one character read for state -> need state for second start char?

    def start_handler(self, next_char):
        if next_char == BINARY_PREAMBLE[0:1]:  # have to index like this or it becomes an int.
            next_state = states.binary_preamble
        elif next_char == READABLE_START:
            next_state = states.ascii_preamble_1
        else:
            self.message_data = b""
            next_state = states.start

        return next_state, False

    def ascii_preamble_1_handler(self, next_char):
        if next_char == OUR_TALKER[0:1]:  # have to index like this or it becomes an int.
            next_state = states.ascii_preamble_2
        else:
            self.message_data = b""
            next_state = states.start
        return next_state, False

    def ascii_preamble_2_handler(self, next_char):
        if next_char == OUR_TALKER[1:2]:  # have to index like this or it becomes an int.
            next_state = states.ascii_body
        else:
            self.message_data = b""
            next_state = states.start
        return next_state, False

    def binary_preamble_handler(self, next_char):
        if next_char == BINARY_PREAMBLE[1:2]:  # have to index like this or it becomes an int.
            next_state = states.binary_type
        # ASCII start (#) after C5 -> start on ascii message?
        # not continuing checksum: go back to start.
        else:
            self.message_data = b""
            next_state = states.start
        return next_state, False

    def binary_type_handler(self, next_char):
        # can be multiple types. check for valid types here?
        next_state = states.binary_length
        return next_state, False

    def binary_length_handler(self, next_char):
        # treat binary checksum as part of body for now, just need to find data of one binary message and then call binary parser.
        self.expected_body_length = int.from_bytes(next_char, BINARY_ENDIAN) + BINARY_CRC_LEN
        # TODO - treat as bad message if the length is too big? one byte should go up to 255 only
        self.binary_length_counter = 0  # start counter for body length
        next_state = states.binary_body
        return next_state, False

    def binary_body_handler(self, next_char):
        self.binary_length_counter += 1
        # message is finished when we reach expected body length (including checksum)
        if self.binary_length_counter >= self.expected_body_length:
            self.returned_message_type = "Binary"
            return states.start, True
        else:
            return states.binary_body, False

    # ASCII: treat the type and body as one state. ASCII parser can distinguish those later.
    # ASCII message goes until *cs , or end early on a new # or C5
    def ascii_body_handler(self, next_char):
        if next_char == READABLE_CHECKSUM_SEPARATOR:
            # reached checksum of ASCII message
            next_state = states.ascii_cs1
        elif next_char == BINARY_PREAMBLE[0]:
            # early exit to new binary message.
            self.message_data = b""
            next_state = states.binary_preamble
        elif next_char == READABLE_START:
            # early exit to new ASCII message.
            self.message_data = b""
            next_state = states.ascii_body
        else:
            # continue reading the ascii body
            next_state = states.ascii_body

        return next_state, False  # todo - done=True only on a complete message, or on partial/interrupted message too?

    def ascii_cs1_handler(self, next_char):
        # todo - ASCII checksum is alphanumeric only. so should it start new message on C5 or # here?
        next_state = states.ascii_cs2
        return next_state, False

    def ascii_cs2_handler(self, next_char):
        # todo - ASCII checksum is alphanumeric only. so should it start new message on C5 or # here?
        next_state = states.start
        self.returned_message_type = "ASCII"
        return next_state, True
