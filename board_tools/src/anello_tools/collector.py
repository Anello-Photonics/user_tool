from threading import Thread
import collections
import matplotlib.pyplot as plt
plt.rcParams['axes.grid'] = True
import matplotlib.animation as animation
import numpy as np
import copy
import time
import pathlib
import math
import os
#from scipy.signal import welch

try:  # importing from inside the package
    import readable_scheme
    from message_scheme import Message
    import connection
    from config.board_config import *
except ModuleNotFoundError:  # importing from outside the package
    import anello_tools.readable_scheme as readable_scheme
    from anello_tools.message_scheme import Message
    import anello_tools.connection
    from anello_tools.config.board_config import *


def default_log_name(serialNum = None):
    #time_str = time.ctime(time.time()).replace(" ", "_").replace(":", "_")
    local = time.localtime()
    date_nums = [local.tm_year, local.tm_mon, local.tm_mday]
    time_nums = [local.tm_hour, local.tm_min, local.tm_sec]
    date_str = "date_" + "_".join([str(num) for num in date_nums])
    time_str = "time_" + "_".join([str(num) for num in time_nums])
    if serialNum is None:
        return "output_" + date_str + "_" + time_str + LOG_FILETYPE
    else:
        return "output_" + date_str + "_" + time_str + "_SN_"+str(serialNum) + LOG_FILETYPE

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

        self.detect_misses_with_counters = detect_misses_with_counters
        self.statistics = SessionStatistics(detect_misses_with_counters)
        self.transformation = transformation  # tuple of (field list, operation)
        self.last_message_time = None
        self.last_gps_message_time = None

    # re-initialize in case board has to re-initialize
    def reset(self):
        self.stop_reading()
        self.board.reset_connections()
        self.__init__(self.board, self.log_messages, self.message_file_name, self.log_messages_detailed, self.log_debug,
                      self.debug_file_name, self.detect_misses_with_counters, self.transformation)
        self.start_reading()  # should this start, or start separately?
        # wait for first new message - might not be necessary since it passed without this
        num_msg = len(self.messages)
        while len(self.messages) == num_msg:
            pass  # should it fail if no new messages in some amount of time?

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
        self.debug("\n"+text)

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
            elif message.msgtype == b'CAL':
                self.add_delta_t_cal(message)
                self.transform_message_data(message)
                self.messages.append(message)
            elif message.msgtype == b'IMU':
                self.add_delta_t_imu(message)
                self.transform_message_data(message)
                self.messages.append(message)
            elif message.msgtype == b'INS':
                # could collect these into a list too.
                # and could get delta t of the IMU time or the GPS time. probably IMU time
                pass
            if self.log_messages_detailed:
                self.log_line("Message: " + str(message.__dict__))
            else:
                self.log_line((readable_scheme.READABLE_START+message.data).decode())
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

        for var in ["accel_x_g", "accel_y_g", "accel_z_g", "angrate_x_dps", "angrate_y_dps", "angrate_z_dps"]: #, "temperature_c"]:
            self.debug_line("statistics for " + var + ":")
            values = self.get_vector(var) #[getattr(m, var) for m in self.messages]
            self.debug(str(self.one_var_statistics(values)))

        # #plot the time differences:fd
        # plt.plot(times[1:], time_diffs)
        # plt.xlabel("time")
        # plt.ylabel("time between messages")
        # plt.title("time betweeen messages versus time")
        # plt.show()

    def log_final_statistics_cal(self):
        print("________Final Statistics:________")
        print(str(self.statistics.__dict__))

        for var in ["accel_x", "accel_y", "accel_z", "rate_x", "rate_y", "rate_z", "rate_fog", "temperature"]: #, "temperature_c"]:
            print("statistics for " + var + ":")
            values = self.get_vector(var) #[getattr(m, var) for m in self.messages]
            print(str(self.one_var_statistics(values)))

    def one_var_statistics(self, val_list):
        statistics = {}
        statistics["length"] = len(val_list)
        statistics["max"] = max(val_list)
        statistics["min"] = min(val_list)
        statistics["mean"] = sum(val_list) / len(val_list)
        return statistics

    # add extra fields like delta t
    def add_delta_t_imu(self, message):
        try:
            if self.last_message_time:
                message.delta_t = message.imu_time_ms - self.last_message_time
            self.last_message_time = message.imu_time_ms
            # for first message, can't add delta_t - need to indicate that with something?
        except Exception as e:
            print("could not compute time for message: "+str(message))

    def add_delta_t_cal(self, message):
        try:
            if self.last_message_time:
                message.delta_t = message.time - self.last_message_time
            self.last_message_time = message.time
        except Exception as e:
            print("could not compute time for message: "+str(message))

    # for gps messages only - they have imu_time_ms and gps_time_ms instead of time field
    def add_delta_t_gps(self, message):
        try:
            if self.last_gps_message_time:
                message.delta_t = message.imu_time_ms - self.last_gps_message_time
            self.last_gps_message_time = message.imu_time_ms
        except Exception as e:
            print("could not compute time for message: "+str(message))

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
        #return np.array([getattr(m, var_name) for m in self.messages if hasattr(m, var_name)])

        #longer version to show when anything is missing
        #print("get vector: "+str(var_name))
        values = []
        for m in self.messages:
            if hasattr(m, var_name):
                values.append(getattr(m, var_name))
            else:
                print("missing attribute "+str(var_name)+ " in message: "+str(m))
        return np.array(values)

    def get_vector_gps(self, var_name):
        return np.array([getattr(m, var_name) for m in self.gps_messages if hasattr(m, var_name)])

    def num_messages(self):
        return len(self.messages)

    def num_gps_messages(self):
        return len(self.gps_messages)

    # plotting collected data with one variable against another
    def plot(self, independentVar, dependentVar, gps=False):
        if gps:
            messages_copy = copy.deepcopy(self.gps_messages)
            independent_data = self.get_vector_gps(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            dependent_data = self.get_vector_gps(dependentVar)
        else:
            messages_copy = copy.deepcopy(self.messages)  # copy in case messages are still coming in
            independent_data = self.get_vector(independentVar)  # [getattr(m, independentVar) for m in messages_copy]
            dependent_data = self.get_vector(dependentVar)  # [getattr(m, dependentVar) for m in messages_copy]
            if dependentVar == "delta_t":
                independent_data = independent_data[1:] #fix size mismatch for delta t
        plt.plot(independent_data, dependent_data)
        plt.xlabel(independentVar)
        plt.ylabel(dependentVar)
        plt.title(dependentVar + " as a function of " + independentVar)
        plt.show()

    #plot a variable in message order, not vs another var
    def plot_in_order(self, dependentVar, gps=False):
        if gps:
            dependent_data = self.get_vector_gps(dependentVar)
        else:
            dependent_data = self.get_vector(dependentVar)  # [getattr(m, dependentVar) for m in messages_copy]
        plt.plot(dependent_data, "rx")
        plt.ylabel(dependentVar)
        plt.title(dependentVar + " in message order ")
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
            a.flat[i].plot(independent_data, dependent_data, '.')
            a.flat[i].set_title(var, loc='center')
            #a.flat[i].set_ylabel(var, rotation=0, fontsize=7, labelpad=20)
            #plt.grid()
        plt.xlabel(independentVar)
        #plt.grid()
        plt.show()

    def plot_all_accelerations(self):
        self.plot_multi_separately("imu_time_ms", ["accel_x_g", "accel_y_g", "accel_z_g"], columns=1)

    def plot_all_rates(self):
        self.plot_multi_separately("imu_time_ms", ["angrate_x_dps", "angrate_y_dps", "angrate_z_dps"], columns=1)

    def plot_everything_imu(self, ncols=2):
        names = ["accel_x_g", "angrate_x_dps", "accel_y_g", "angrate_y_dps", "accel_z_g", "angrate_z_dps", "fog_angrate_dps", "temperature_c"]
        self.plot_multi_separately("imu_time_ms", names, columns=ncols)

    def plot_everything_cal(self, ncols=2):
        names = ["accel_x", "rate_x", "accel_y", "rate_y", "accel_z", "rate_z", "rate_fog", "temperature"]
        self.plot_multi_separately("time", names, columns=ncols)

    def plot_fog_cal(self):
        #self.plot_multi_separately("time", ["rate_fog"], columns=1)
        self.plot("time", "rate_fog")

    # def plot_psd(self, var, freq):
    #     analyse_data = self.get_vector(var)
    #     f, Pxx = welch(analyse_data, freq)
    #     plt.plot(f, Pxx)
    #     plt.ylabel("psd")
    #     plt.xlabel("frequency (Hz)")
    #     plt.title("Welch Power Spectral Density of "+var)
    #     plt.show()

    #numpy.fft.fft(array, input length (default axis length), axis (default last one), norm(default backward))
    def plot_fft(self, var):
        analyse_data = self.get_vector(var)
        out = np.fft.fft(analyse_data)
        # print("complex output: ")
        # print("out: "+str(out))
        complex_magnitude = np.absolute(out)
        complex_phase = np.angle(out)

        #separate magnitude and phase plots
        # plt.plot(complex_magnitude)
        # plt.ylabel("magnitude")
        # #plt.xlabel("frequency (Hz)")
        # plt.title("FFT of "+var+": magnitude")
        # plt.show()
        #
        # plt.plot(complex_phase)
        # plt.ylabel("phase")
        # # plt.xlabel("frequency (Hz)")
        # plt.title("FFT of " + var+": phase")
        # plt.show()

        #try subplots?
        fig, a = plt.subplots(nrows=2, ncols=1, sharex=True, sharey=False)
        a.flat[0].plot(complex_magnitude)
        a.flat[0].set_title(var+" fft magnitude", loc='center')
        #a.flat[0].set_ylabel("magnitude", rotation=0, fontsize=7, labelpad=20)
        a.flat[1].plot(complex_phase)
        a.flat[1].set_title(var+" fft phase", loc='center')
        #a.flat[0].set_ylabel("phase", rotation=0, fontsize=7, labelpad=20)
        plt.show()

    def plot_fft_vs_fft_freq(self, var, subtract_avg=True):
        analyse_data = self.get_vector(var)
        if subtract_avg:
            analyse_data = analyse_data - np.ones(analyse_data.shape) * np.average(analyse_data)
        fft_out = np.fft.fft(analyse_data)
        # print("complex output: ")
        # print("out: "+str(out))
        complex_magnitude = np.absolute(fft_out)
        freq = np.fft.fftfreq(analyse_data.shape[-1])

        #separate magnitude and phase plots
        #plt.plot(freq, complex_magnitude)
        plt.semilogy(freq, complex_magnitude)
        plt.ylabel("magnitude")
        #plt.xlabel("frequency (Hz)")
        plt.title("FFT of "+var+": magnitude")
        plt.show()

    def plot_times(self):
        self.plot_in_order("imu_time_ms")
        self.plot_in_order("delta_t")
        self.plot("imu_time_ms", "delta_t")

    def plot_all_vs_temp(self, ncols=2):
        names = ["accel_x_g", "angrate_x_dps", "accel_y_g", "angrate_y_dps", "accel_z_g", "angrate_z_dps", "fog_angrate_dps"]
        self.plot_multi_separately("temperature_c", names, columns=ncols)

    def plot_all_gps(self, ncols=2):
        names = ["gps_time_ms", "lat", "lon", "alt_ellipsoid_m", "alt_msl_m", "speed_m_per_s", "heading_degrees",
                 "acc_horizontal_m", "acc_vertical_m", "PDOP", "fix-type", "numSV", "spdacc", "hdsacc"]

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

    def __init__(self, collector, plotVars, maxlength=100, title="Real Time Plot", ymin=-5000, ymax=5000, gps=False, interval_ms=50):
        self.collector = collector
        self.plotMaxLength = maxlength
        
        self.pltInterval = interval_ms    # Period at which the plot animation updates [ms]
        self.plotTimer = 0  # time range for the plot
        self.previousTimer = 0
        self.plotVars = plotVars
        self.gps = gps
        
        xmin = 0
        #xmax should be time in seconds for data to cross the window: (max points) * (time per point)
        xmax = self.plotMaxLength
        #xmax = self.plotMaxLength * (interval_ms / 1000) #self.plotMaxLength
        self.ymin = ymin
        self.ymax = ymax
        self.fig = plt.figure()
        ax = plt.axes(xlim=(xmin, xmax), ylim=(float(ymin - (ymax - ymin) / 10), float(ymax + (ymax - ymin) / 10)))
        ax.set_title(title)
        ax.set_xlabel("data samples (1 per "+str(self.pltInterval) + " ms)")
        lineLabel = plotVars
        big_styles = ['r-', 'g-', 'b-', 'ro', 'bo', 'go', 'r+', 'b+', 'g+']
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
