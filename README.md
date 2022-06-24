This repo contains tools for logging and configuring with the Anello A-1.

This is main branch which works for the most common A1 configuration. You should probably use this branch unless you asked for the higher rate configuration. The regular configuration has ASCII outputs such as #APIMU, #APINS, #APGPS. If your unit is configured with high rate binary outputs, use the high_rate_binary branch instead.


- contents:
    - board_tools/user_program.py  - interactive configuration and logging tool.
        - usage: python user_program.py
    - board_tools/graph_demo.py - graphing demo. will integrate this into user tool.
        - usage: python graph_demo.py
    - board_tools/src/tools: library for communicating with the A-1, used by the other tools

- requirements:
    - Python 3.9
    - python dependencies: install with "pip install -r requirements.txt"
        - cutie 0.2.2
        - numpy 1.19.3
        - matplotlib 3.3.3
        - pyserial 3.5
        - PySimpleGUI 4.45.0
    - Troubleshooting numpy / matplotlib issue in Linux:
        - on Raspberry Pi running Linux, the versions of matplotlib and numpy installed with pip did not work
        - To fix this, do:
            - pip install cutie
            - pip install pyserial
            - sudo apt install matplotlib
            - sudo apt install numpy
        - or if you already installed requirements.txt, do:
            - pip uninstall matplotlib
            - pip uninstall numpy
            - sudo apt install matplotlib
            - sudo apt install numpy

### Pip installation
To install the driver as a Python API install it as a package with pip.
```bash
cd board_tools/src
pip install .
```
You can then use the API functions in python
```python
from anello_tools.collector import Collector
```