#tool to plot csv data
#will use this for output from rtcm parser, but could use for other things too

import tkinter as tk
from tkinter.filedialog import askopenfilename
import cutie
import pandas as pd
import matplotlib.pyplot as plt
import os

# powers of 10 rane which will show without exponential notation
EXP_CUTOFF_LOW = -4
EXP_CUTOFF_HIGH = 4


def column_of_type(frame, column_names, column_type):
    data_out, description_out = [], ""
    if column_type == "exit":
        exit()

    elif column_type == "one column":
        print("\npick the column:")
        var_to_plot = column_names[cutie.select(column_names)]
        column_data = frame[var_to_plot]
        data_out = column_data
        description_out = var_to_plot

    elif column_type == "deltas of one column":
        print("\npick the column:")
        var_to_plot = column_names[cutie.select(column_names)]
        column_data = frame[var_to_plot]
        diff_data = column_data.diff()  # TODO - pad it with a 0 because diff array is one shorter?
        data_out = diff_data
        description_out = f"deltas of {var_to_plot}"

    elif column_type == "difference of two columns":
        print("this will plot column 1 minus column 2")
        print("\npick column 1")
        var1 = column_names[cutie.select(column_names)]
        print("\npick column 2")
        var2 = column_names[cutie.select(column_names)]
        # print(f"\nselected {var_to_plot}")
        differences = frame[var1] - frame[var2]
        data_out = differences
        description_out = f"{var1} minus {var2}"

    elif column_type == "difference of column deltas":
        print("this will plot delta(column 1) minus delta(column 2)")
        print("\npick column 1")
        var1 = column_names[cutie.select(column_names)]
        print("\npick column 2")
        var2 = column_names[cutie.select(column_names)]
        data_out = frame[var1].diff() - frame[var2].diff()
        description_out = f"deltas of {var1} minus deltas of {var2}"

    elif column_type == "ratio of two columns":
        print("this will plot column 1 divided by column 2")
        print("\npick column 1")
        var1 = column_names[cutie.select(column_names)]
        print("\npick column 2")
        var2 = column_names[cutie.select(column_names)]
        # print(f"\nselected {var_to_plot}")
        ratios = frame[var1] / frame[var2]
        data_out = ratios
        description_out = f"{var1} / {var2}"

    # TODO - can add ratios, product, other functions of one or two columns

    # can skip index option since "index" was added to the frame and will appear in column_names selection
    # elif column_type == "data point number":
    #     data_out = frame["index"]
    #     description_out = f"data point number"

    else:
        print(f"unknown plotting option {column_type}")
        exit()

    return data_out, description_out


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    in_file_path = askopenfilename(initialdir=None, title="Select csv to plot")
    root.destroy()
    file_name = os.path.basename(in_file_path)
    print(f"selected  file: {in_file_path}")
    frame = pd.read_csv(in_file_path)

    # make a column called "index" with values 0,1,2 etc. warning - may overwrite a csv column called "index"
    frame.reset_index(inplace=True)
    column_names = [name for name in frame.columns]

    main_options = ["one column", "deltas of one column", "difference of two columns", "difference of column deltas", "ratio of two columns", "exit"]

    while True:
        print("\n_______pick variables to plot next_______")

        print("\n_______select y (dependent) variable _______")
        y_type = main_options[cutie.select(main_options)]
        y_data, y_name = column_of_type(frame, column_names, y_type)

        print("\n_______select x (independent) variable _______")
        x_type = main_options[cutie.select(main_options)]
        x_data, x_name = column_of_type(frame, column_names, x_type)

        print(f"plotting [{y_name}] vs [{x_name}]")
        plot_style = "."  # disconnected dots
        plt.title(f"{file_name}:\n[{y_name}] vs [{x_name}]")
        plt.xlabel(x_name)
        plt.ylabel(y_name)
        plt.minorticks_on()
        plt.grid(visible=True, which='major', axis='both')
        plt.plot(x_data, y_data, color='blue', marker='.', linestyle="None")
        plt.ticklabel_format(axis='both', style='sci', scilimits=(EXP_CUTOFF_LOW, EXP_CUTOFF_HIGH))
        plt.show()

        # TODO - compute stats on the data too?

        #     print("\npick column to compute stats")
        #     var1 = column_names[cutie.select(column_names)]
        #     column_data = frame[var1]
        #     print(f"stats for {var1}")
        #     print(f"mean: {}")
