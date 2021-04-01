from threading import Thread
import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import copy
import time
import pathlib
import math
import os

try:  # importing from inside the package
    import readable_scheme
    from scheme import Message
    import connection
    from config.board_config import *
except ModuleNotFoundError:  # importing from outside the package
    import tools.readable_scheme
    from tools.scheme import Message
    import tools.connection
    from tools.config.board_config import *


def default_log_name():
    time_str = time.ctime(time.time()).replace(" ", "_").replace(":", "_")
    return "output_"+time_str+LOG_FILETYPE

# Gets messages from a Board, stores and plots them
class Collector:
    def __init__(self, board, log_messages=False, message_file_name=None, log_detailed=False, log_debug=False,
                 debug_file_name=None, detect_misses_with_counters=False, transformation=None):
        self.board = board
        self.isRun = True
        self.isReceiving = False
        self.thread = None
        self.messages = []
        self.gps_messages = []
        self.invalid_messages = []

        self.log_messages = log_messages
        self.message_file_name = message_file_name
        self.log_messages_detailed = log_detailed
        self.message_file = None
        if log_messages:  # for main log: open log file name if given, else default name
            if not message_file_name:
                message_file_name = default_log_name()
            self.message_file = self.open_log_file(LOG_PATH, message_file_name)

        self.log_debug = log_debug
        self.debug_file_name = debug_file_name
        self.debug_file = None
        if log_debug and debug_file_name:  # for debug: log to file if given, else only print debug
            self.debug_file = self.open_log_file(DEBUG_PATH, debug_file_name)

        self.statistics = SessionStatistics(detect_misses_with_counters)
        self.transformation = transformation  # tuple of (field list, operation)
        self.last_message_time = None
        self.last_gps_message_time = None

    def open_log_file(self, location, name):
        # location needs to double any slashes \\ - otherwise we risk \b or other special characters
        location = os.path.join(os.path.dirname(__file__), location)  # make it relative to this file
        os.makedirs(location, exist_ok=True)
        full_path = os.path.join(location, name)
        try:
            return open(full_path, 'w')
        except Exception as e:
            print("error trying to open log file: "+location+"/"+name)
            return None

    # debug - print information not needed for user. only do if log_debug flag set
    # print and log to file (if file specified)
    def debug(self, text):
        if self.log_debug:
            if self.debug_file:
                self.debug_file.write(text)
            print(text)

    def debug_line(self, text):
        self.debug(text + "\n")

    # log: info user would want, like message outputs
    # only go to file, don't print out. if debug set, should print, so call debug.
    def log(self, text):
        if self.log_messages and self.message_file:
            self.message_file.write(text)
        self.debug(text)

    def log_line(self, text):
        self.log(text + "\n")

    def start_reading(self):
        self.debug_line("________Beginning Read________")
        self.statistics.start_timing()
        if self.thread is None:
            self.thread = Thread(target=self.backgroundThread)
            self.thread.start()
            # Block till we start receiving values
            while not self.isReceiving:
                time.sleep(0.1)

    def backgroundThread(self):
        self.board.clear_inputs()
        while self.isRun:
            self.read_one_message()
            self.isReceiving = True

    # get one message from board's data channel, save it
    def read_one_message(self):
        message = self.board.read_one_message()
        if message:
            self.add_if_valid(message)
        return message

    # if message is valid,add it to self.valid, do transformations, update statistics
    # called only on the streaming messages - may not work on control message responses
    # TODO handle GPS messages in streaming too
    def add_if_valid(self, message):
        if message.valid:
            if message.msgtype == b'GPS':
                self.add_delta_t_gps(message)
                self.gps_messages.append(message)
            elif message.msgtype in [b'CAL', b'IMU']:
                self.add_delta_t(message)
                self.transform_message_data(message)
                self.messages.append(message)
            elif message.msgtype == b'INS':
                # could collect these into a list too.
                # and could get delta t of the IMU time or the GPS time. probably IMU time
                pass
            if self.log_messages_detailed:
                self.log_line("Message: " + str(message.__dict__))
            else:
                self.log_line(message.data.decode())
            self.statistics.count_valid(message)
        else:
            self.invalid_messages.append(message)
            self.debug_line("invalid message: error = " + str(message.error) + ", data = " + str(message.data))
            self.statistics.count_invalid()
        return message.valid

    # get the last message. used for real time plot.
    def last_message(self):
        if len(self.messages) > 0:
            return self.messages[-1]
        return None

    def last_gps_message(self):
        if len(self.gps_messages) > 0:
            return self.gps_messages[-1]
        return None

    def stop_reading(self):
        self.isRun = False
        self.statistics.stop_timing()
        if self.thread:
            self.thread.join()
        self.debug_line("closing connection")

    def stop_logging(self):
        if self.message_file:
            self.message_file.close()
        if self.debug_file:
            self.debug_file.close()

    def log_configurations(self):
        self.debug_line("________Configurations:________")
        self.debug_line("board: " + str(self.board.__dict__))

    def log_final_statistics(self):
        self.debug_line("________Final Statistics:________")
        self.debug_line(str(self.statistics.__dict__))

        # get statistics on each variable
        # TODO current way is inefficient but should work for now. could do running totals to use less memory for long runs
        # also look into numpy or other numerical libraries to process this

        # times = [m.time for m in self.messages]
        # time_diffs = [times[i+1]-times[i] for i in range(len(self.messages)-1)]
        # # find skips based on timing? - eg time difference too far from odr or other time differences
        # self.log_line("\nstatistics for time differences:")
        # self.log(str(self.one_var_statistics(time_diffs)))

        for var in ["delta_t", "accel_x", "accel_y", "accel_z", "rate_x", "rate_y", "rate_z", "temperature"]:
            self.debug_line("statistics for " + var + ":")
            values = self.get_vector(var) #[getattr(m, var) for m in self.messages]
            self.debug(str(self.one_var_statistics(values)))

        # #plot the time differences:
        # plt.plot(times[1:], time_diffs)
        # plt.xlabel("time")
        # plt.ylabel("time between messages")
        # plt.title("time betweeen messages versus time")
        # plt.show()

    def one_var_statistics(self, val_list):
        statistics = {}
        statistics["length"] = len(val_list)
        statistics["max"] = max(val_list)
        statistics["min"] = min(val_list)
        statistics["mean"] = sum(val_list) / len(val_list)
        return statistics

    # add extra fields like delta t
    def add_delta_t(self, message):
        if self.last_message_time:
            message.delta_t = message.time - self.last_message_time
        self.last_message_time = message.time
        # for first message, can't add delta_t - need to indicate that with something?

    # for gps messages only - they have imu_time_ms and gps_time_ms instead of time field
    def add_delta_t_gps(self, message):
        if self.last_gps_message_time:
            message.delta_t = message.imu_time_ms - self.last_gps_message_time
        self.last_gps_message_time = message.imu_time_ms

    # do a transformation on one message
    # message - the message to be transformed
    # attr_list: the attributes of the message to transform
    # should only be used on message's numerical fields, not things like message type, valid, data
    # operator: transformation as a vector -> vector operation
    def transform_message_data(self, message):
        if self.transformation is None:
            return
        attr_list, operator = self.transformation
        old_vec = np.zeros(len(attr_list))
        for i, name in enumerate(attr_list):
            try:
                old_vec[i] = getattr(message, name)
            except AttributeError:  # does not have that field - cant do the transform. can happen for delta_t.
                return  # TODO how to handle a message that cant be transformed? like this, it is unmodified.
        new_vec = operator(old_vec)
        for i, name in enumerate(attr_list):
            setattr(message, name, new_vec[i])

    def print_messages(self):
        print("messages:\n")
        for i, m in enumerate(self.messages):
            print("message "+str(i)+": "+str(m.__dict__)+"\n")

    # get vector of some variable for all messages
    # TODO - cache vectors when calling this, or update vectors on receiving message?
    def get_vector(self, var_name):
        return np.array([getattr(m, var_name) for m in self.messages if hasattr(m, var_name)])

    def get_vector_gps(self, var_name):
        return np.array([getattr(m, var_name) for m in self.gps_messages if hasattr(m, var_name)])

    def num_messages(self):
        return len(self.messages)

    def num_gps_messages(self):
        return len(self.gps_messages)

    # plotting collected data - not in real-time
    def plot(self, independentVar, dependentVar, gps=False):
        if gps:
            messages_copy = copy.deepcopy(self.gps_messages)
            independent_data = self.get_vector_gps(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            dependent_data = self.get_vector_gps(dependentVar)
        else:
            messages_copy = copy.deepcopy(self.messages)  # copy in case messages are still coming in
            independent_data = self.get_vector(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            dependent_data = self.get_vector(dependentVar)  # [getattr(m, dependentVar) for m in messages_copy]
        plt.plot(independent_data, dependent_data)
        plt.xlabel(independentVar)
        plt.ylabel(dependentVar)
        plt.title(dependentVar + " as a function of " + independentVar)
        plt.show()

    # plot multiple variables versus 1. dependentVars is a list of variable name strings.
    def plot_multi_together(self, independentVar, dependentVars, gps=False):
        if gps:
            messages_copy = copy.deepcopy(self.gps_messages)
            independent_data = self.get_vector_gps(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            for var in dependentVars:
                dependent_data = self.get_vector_gps(var)  # [getattr(m, var) for m in messages_copy]
                plt.plot(independent_data, dependent_data, label=var)
        else:
            messages_copy = copy.deepcopy(self.messages)
            independent_data = self.get_vector(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            for var in dependentVars:
                dependent_data = self.get_vector(var)  # [getattr(m, var) for m in messages_copy]
                plt.plot(independent_data, dependent_data, label=var)
        plt.xlabel(independentVar)
        plt.title(str(dependentVars)+" versus "+str(independentVar))
        plt.legend()
        plt.show()

    # plot multiple vars in separate plots
    # length of arrays has to match, so can't put delta_t here alongside other things since it has one less.
    def plot_multi_separately(self, independentVar, dependentVars, gps=False, columns=2):
        num_rows = math.ceil(len(dependentVars) / columns)
        fig, a = plt.subplots(nrows=num_rows, ncols=columns, sharex=True, sharey=False)
        if gps:
            get_func = self.get_vector_gps
        else:
            get_func = self.get_vector
        independent_data = get_func(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
        for i, var in enumerate(dependentVars):
            dependent_data = get_func(var)
            #special handling for delta_t which has no value at first message
            if var == "delta_t":
                dependent_data = np.concatenate((np.array([None]), dependent_data))
            a.flat[i].plot(independent_data, dependent_data)
            a.flat[i].set_title(var, loc='center')
            #a.flat[i].set_ylabel(var, rotation=0, fontsize=7, labelpad=20)
        plt.xlabel(independentVar)
        plt.show()

    def plot_all_accelerations(self):
        self.plot_multi_separately("time", ["accel_x", "accel_y", "accel_z"])

    def plot_everything(self, ncols=2):
        names = ["accel_x", "accel_y", "accel_z", "rate_x", "rate_y", "rate_z", "temperature", "delta_t"]
        self.plot_multi_separately("time", names, columns=ncols)

    def plot_all_gps(self, ncols=2):
        names = ["gps_time_ms", "lat", "lon", "alt_ellipsoid_m", "alt_msl_m", "speed_m_per_s", "heading_degrees",
                 "acc_horizontal_m", "acc_vertical_m", "PDOP", "fix-type", "numSV", "spdacc", "hdsacc", "delta_t"]

        self.plot_multi_separately("imu_time_ms", names, gps=True, columns=ncols)


# tracks the statistics for one session, like total messages, invalid messages, missed messages
class SessionStatistics:
    def __init__(self, detect_misses_with_counters):
        self.number_valid = 0
        self.number_invalid = 0
        self.start_time = None
        self.end_time = None
        self.elapsed_time = None
        self.average_rate = None
        self.detect_misses_with_counters = detect_misses_with_counters
        if detect_misses_with_counters:
            self.number_missed = 0
            self.invalid_since_valid = 0
            self.last_valid_counter = None
            self.missed_notes = []

    # on valid message- check counter, see how many missed since last counter
    # invalid messages in that span don't count as missed
    def count_valid(self, message):
        self.number_valid += 1
        if self.detect_misses_with_counters:
            counter = message.counter
            if self.last_valid_counter:
                missed = counter - self.last_valid_counter -1 - self.invalid_since_valid
                if missed > 0:
                    self.missed_notes.append("missed "+str(missed)+" message(s) between counters "+str(self.last_valid_counter)+" and "+str(counter))
                    self.number_missed += missed
            self.invalid_since_valid = 0
            self.last_valid_counter = counter

    def count_invalid(self):
        self.number_invalid += 1
        if self.detect_misses_with_counters:
            if self.last_valid_counter:
                self.invalid_since_valid += 1

    def start_timing(self):
        self.start_time = time.time()

    def stop_timing(self):
        if self.start_time and not self.end_time:
            self.end_time = time.time()
            self.elapsed_time = self.end_time - self.start_time
        # compute final statistics in stop_timing? or make it a separate method
        self.average_rate = (self.number_valid + self.number_invalid) / self.elapsed_time


# plots the data recorded by a Collector in real time.
class RealTimePlot:

    def __init__(self, collector, plotVars, maxlength=100, ymin=-5000, ymax=5000, gps=False):
        self.collector = collector
        self.plotMaxLength = maxlength
        
        self.pltInterval = 50    # Period at which the plot animation updates [ms]
        self.plotTimer = 0  # time range for the plot
        self.previousTimer = 0
        self.plotVars = plotVars
        self.gps = gps
        
        xmin = 0
        xmax = self.plotMaxLength
        self.ymin = ymin
        self.ymax = ymax
        self.fig = plt.figure()
        ax = plt.axes(xlim=(xmin, xmax), ylim=(float(ymin - (ymax - ymin) / 10), float(ymax + (ymax - ymin) / 10)))
        ax.set_title('Real Time Plot')
        ax.set_xlabel("Time(seconds)")
        lineLabel = plotVars
        big_styles = ['r-', 'g-', 'b-','ro', 'bo', 'go', 'r+', 'b+', 'g+']
        style = big_styles[0:len(self.plotVars)]
        timeText = ax.text(0.50, 0.95, '', transform=ax.transAxes)
        lines = []
        lineValueText = []
        for i, var in enumerate(self.plotVars):
            lines.append(ax.plot([], [], style[i], label=lineLabel[i])[0])
            lineValueText.append(ax.text(0.70, 0.90-i*0.05, '', transform=ax.transAxes))

        self.fargs=(lines, lineValueText, lineLabel, timeText)

        self.data = []
        for var in self.plotVars:
            self.data.append(collections.deque([0] * self.plotMaxLength, maxlen=self.plotMaxLength))

        anim = animation.FuncAnimation(self.fig, self.getData, fargs=self.fargs, interval=self.pltInterval)
        plt.legend(loc="upper left")
        plt.show()

    # gets data from the Collector to plot
    # TODO - currently it gets the most recent message only - update to get all messages since last getData? Could matter at high message rate.
    def getData(self, frame, lines, lineValueText, lineLabel, timeText):
        currentTimer = time.perf_counter()
        self.plotTimer = int((currentTimer - self.previousTimer) * 1000)
        self.previousTimer = currentTimer
        timeText.set_text('Plot Interval = ' + str(self.plotTimer) + 'ms')
        if self.gps:
            last_msg = self.collector.last_gps_message()
        else:
            last_msg = self.collector.last_message()
        for i, name in enumerate(self.plotVars):
            value = getattr(last_msg, name)
            self.data[i].append(value)
            lines[i].set_data(range(self.plotMaxLength), self.data[i])
            lineValueText[i].set_text('[' + lineLabel[i] + '] = ' + str(value))

