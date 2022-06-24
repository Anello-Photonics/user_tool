import serial
from abc import ABC
try:  # importing from inside the package
	from config.board_config import *
except ModuleNotFoundError:  # importing from outside the package
	from anello_tools.config.board_config import *

from builtins import input
import socket
import sys
import select


READ_SIZE = 1024 # excessively large to get whole buffer

# abstract connection class
class Connection(ABC):
	def __init__(self, port=None, baud=DEFAULT_BAUD, timeout=TIMEOUT_REGULAR, write_timeout=TIMEOUT_REGULAR):
		pass

	def read(self, size=1):
		raise Exception("base or dummy Connection has no read")

	def readall(self):
		raise Exception("base or dummy Connection has no readall")

	def read_until(self, expected='\n', size=None):
		raise Exception("base or dummy Connection has no read_until")

	def read_ready(self):
		pass

	def write(self, data):
		raise Exception("base or dummy Connection has no write")

	def reset_input_buffer(self):
		pass  # gets called on dummy

	def open(self):
		pass

	def close(self):
		pass   # gets called on dummy

	def __str__(self):
		return type(self).__name__ +": "+str(self.__dict__)

	def set_baud(self, baud):
		pass   # gets called on dummy

	def get_baud(self):
		raise Exception("base or dummy Connection has no get_baud")

	def set_port(self, port):
		pass

	def get_port(self):
		pass

	def set_timeout(self):
		pass

	def get_timeout(self):
		pass


# dummy for when we don't need data connection - configuration and bringup tools
class DummyConnection(Connection):
	pass


# actual connection to serial port
class SerialConnection(Connection):
	def __init__(self, port=None, baud=DEFAULT_BAUD, timeout=TIMEOUT_REGULAR, write_timeout=TIMEOUT_REGULAR):
		self.connection = serial.Serial(port, baud, timeout=timeout, write_timeout=write_timeout)

	def __repr__(self):
		return "SerialConnection: "+str(self.connection)

	def read(self, size=1):
		return self.connection.read(size)

	def readall(self):
		#fixed size read might not be enough sometimes
		return self.connection.read(self.connection.in_waiting)
		#return self.connection.read(READ_SIZE)

	def read_until(self, expected='\n', size=None):
		return self.connection.read_until(expected, size)

	def read_ready(self):
		return self.connection.in_waiting > 0

	def write(self, data):
		return self.connection.write(data)

	def reset_input_buffer(self):
		if self.connection.is_open:
			self.connection.reset_input_buffer()

	def open(self):
		self.connection.open()

	def close(self):
		self.connection.close()

	def set_baud(self, baud):
		self.connection.baudrate = baud

	def get_baud(self):
		return self.connection.baudrate

	def set_port(self, port):
		self.connection.port = port

	def get_port(self):
		return self.connection.port

	def set_timeout(self, timeout):
		self.connection.timeout = timeout

	def get_timeout(self):
		return self.connection.timeout


class UDPConnection(Connection):
	def __init__(self, remote_ip, remote_port, local_port, timeout=TIMEOUT_REGULAR):
		self.remote_ip = remote_ip
		self.remote_port = remote_port
		self.local_port = local_port
		self.sock = None
		self.addr = (remote_ip, remote_port)
		family_addr = socket.AF_INET

		#try:
		# allow this to except and catch it at higher level
		self.sock = socket.socket(family_addr, socket.SOCK_DGRAM)
		self.sock.bind(('', self.local_port))
		self.sock.setblocking(False)
		self.sock.settimeout(timeout)
		# except socket.error:
		# 	print('Failed to create socket')

	def read(self, size=1):
		try:
			reply, addr = self.sock.recvfrom(size) # buffsize < message length will error
			return reply
		except Exception as e:
			return None
		# need internal buffer to read smaller amounts?

	def readall(self):
		return self.read(READ_SIZE)

	def read_until(self, expected='\n', size=None):
		# either need a sock read_until method, or loop reading one at a time until expected reached
		pass

	def read_ready(self):
		reads, writes, errors = select.select([self.sock], [], [], 0)
		return reads != []

	def write(self, data):
		self.sock.sendto(data, self.addr)

	def reset_input_buffer(self):
		#no built in reset, so read the whole buffer
		temp_timeout = self.sock.gettimeout()
		self.sock.settimeout(0)
		while True:
			try:
				self.sock.recv(1024)
			except Exception as e:
				#print(str(type(e))+": "+str(e))
				break
		self.sock.settimeout(temp_timeout)

	def open(self):
		pass

	def close(self):
		self.sock.close()

	def __str__(self):
		return type(self).__name__ +": "+str(self.__dict__)

	# def set_port(self, port):
	# 	pass
	#
	# def get_port(self):
	# 	pass
	#
	# def set_timeout(self):
	# 	pass
	#
	# def get_timeout(self):
	# 	pass


# fake a serial connection to read byte data from a file
# does not use an actual or virtual com port, just writes/reads file.
class FileReaderConnection(Connection):
	# TODO check if it's ok for init to have different arguments. should it emulate timeout behavior?
	def __init__(self, filename):
		# open the file to read bytes
		self.filename = filename
		self.reader = open(filename, 'rb')

	# read <size> bytes from the file
	def read(self, size=1):
		return self.reader.read(size)

	# read until <expected> or until <size> bytes if not None
	def read_until(self, expected='\n', size=None):
		out = b''
		if size is None:
			while(True):
				data = self.reader.read(1)
				out += data
				if data == b'':  # end of file - return b'' from then on, as if connection is timing out
					return out
				if out[-len(expected):] == expected:
					break
		else:
			if size < 1:
				size = 1  # match behavior of Serial.read_until
			for i in range(size):
				data = self.reader.read(1)
				out += data
				if data == b'':
					return out
				if out[-len(expected):] == expected:
					break
		return out

	def close(self):
		self.reader.close()


# connection for writing bytes to a file - could use this to test message forming
class FileWriterConnection(Connection):
	def __init__(self, filename):
		# open the file
		self.filename = filename
		self.writer = open(filename, 'wb')

	def write(self, data):
		return self.writer.write(data)

	def close(self):
		self.writer.close()

# TODO use a virtual port pair with a file reader/writer on the other end?
# then, can pass the non-file end as a com port for SerialConnection - more elaborate spoof.
