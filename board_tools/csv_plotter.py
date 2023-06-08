#tool to plot csv data
#will use this for output from rtcm parser, but could use for other things too

import tkinter as tk
from tkinter.filedialog import askopenfilename
import cutie
import pandas as pd
import matplotlib.pyplot as plt
import os

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    in_file_path = askopenfilename(initialdir=None, title="Select csv to plot")
    file_name = os.path.basename(in_file_path)
    #root.destroy()
    print(f"selected  file: {in_file_path}")
    frame = pd.read_csv(in_file_path)
    #print(f"\ndata frame:\n{frame}")
    column_names = [name for name in frame.columns]

    #add choices to plot a column in order, one vs another, deltas of a column, etc

    main_options = ["column in order", "delta", "column vs column", "exit"]
    while True:
        print("\nwhich kind of plot?")
        main_action = main_options[cutie.select(main_options)]
        if main_action == "exit":
            exit()
        elif main_action == "column in order":
            print("\npick a column to plot")
            var_to_plot = column_names[cutie.select(column_names)]
            #print(f"\nselected {var_to_plot}")
            column_data = frame[var_to_plot]
            #print(f"\ndata to plot:\n{column_data}")

            column_data.plot(title=f"{file_name}: {var_to_plot} in order", style=".")
            #frame.plot(title=f"{var_to_plot} in order", y=[var_to_plot]) #or can plot like this.
            plt.show()

        elif main_action == "delta":
            print("\npick a column to plot")
            var_to_plot = column_names[cutie.select(column_names)]
            # print(f"\nselected {var_to_plot}")
            column_data = frame[var_to_plot]
            diff_data = column_data.diff()
            diff_data.plot(title=f"{file_name}: {var_to_plot} differences", style=".")
            plt.show()
        elif main_action == "column vs column":
            print("not implemented")

