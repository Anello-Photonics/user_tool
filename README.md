This repo contains tools for logging and configuring with the Anello A-1.

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

This project is licensed under the MIT License.

License information for maps feature: the user can select OpenStreetMap or Stamen in the dropdown in maps tab of monitor window.

With "osm" selected: Map images from OpenStreetMap under ODbL (openstreetmap.org/copyright)",
With "stamen-terrain" selected: Map tiles by Stamen Design (stamen.com) under CC BY 3.0 (creativecommons.org/licenses/by/3.0). Data by OpenStreetMap under ODbL (openstreetmap.org/copyright)
