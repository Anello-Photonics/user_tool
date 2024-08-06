
CFG_FIELD_CODES_TO_NAMES = {
    "odr": "Output Data Rate (Hz)",
    "msg": "Output Message Type",
    "lpa": "MEMS Accel LPF Cutoff Frequency (Hz)",
    "lpw": "MEMS Rate LPF Cutoff Frequency (Hz)",
    "lpo": "Optical Gyro LPF Cutoff Frequency (Hz)",
    "orn": "Orientation",
    "aln": "Alignment Angles",
    "gps1": "GPS 1",
    "gps2": "GPS 2",
    "bau": "Data Port Baud Rate",
    "bau_input": "Config Port Baud Rate",
    "odo": "Odometer Units",
    "fog": "Enable Fog",
    "dhcp": "DHCP (auto assign ip address)",
    "lip": "UDP A-1 IP",
    "rip": "UDP Computer IP",
    "rport1": "UDP Computer Port 1 (data)",
    "rport2": "UDP Computer Port 2 (configuration)",
    "rport3": "UDP Computer Port 3 (odometer)",
    "min": "Minutes Between Configuration Print",
    "mfm": "Message Format",
    "sync": "SYNC",
    "nhc": "NHC",
    "odcov": "Odometer Covariance",
    "uart": "Serial Output",
    "eth": "Ethernet Output",
    "ntrip": "NTRIP Input Channel",
    "ptp": "PTP Mode",
    "nmea": "NMEA GGA output",
    "aln_est": "Alignment Estimation",
    "rwc_est": "Rear Wheel Center Estimation",
    "dir_det": "Forward/Backward Detection",
}


CFG_VALUE_NAMES = {
    #(field code, value code) : value display name
    ("mfm", b"0"): "binary (0)",
    ("mfm", b"1"): "ascii (1)",
    ("mfm", b"4"): "rtcm (4)",

    ("odo", b"mps"): "meters per second",
    ("odo", b"mph"): "miles per hour",
    ("odo", b"kph"): "kilometers per hour",
    ("odo", b"fps"): "feet per second",

    ("nhc", b"0"): "car/default (20 cm/s)",
    ("nhc", b"1"): "truck (30 cm/s)",
    ("nhc", b"2"): "agricultural (50 cm/s)",
    ("nhc", b"3"): "80 cm/s",
    ("nhc", b"4"): "100 cm/s",
    ("nhc", b"5"): "150 cm/s",
    ("nhc", b"6"): "20 cm/s",
    ("nhc", b"7"): "off",

    ("odcov", b"0"): "default (20 cm/s)",
    ("odcov", b"1"): "old odometer (2 cm/s)",
    ("odcov", b"2"): "10 cm/s",
    ("odcov", b"3"): "20 cm/s",
    ("odcov", b"4"): "30 cm/s",
    ("odcov", b"5"): "40 cm/s",
    ("odcov", b"6"): "50 cm/s",
    ("odcov", b"7"): "off",

    ("ntrip", b"0"): "off",
    ("ntrip", b"1"): "serial",
    ("ntrip", b"2"): "ethernet",

    ("nmea", b"0"): "off",
    ("nmea", b"1"): "on",

    ("orn", b"+X+Y+Z"): "+X+Y+Z (Forward-Right-Down)",
    ("orn", b"+Y+X-Z"): "+Y+X-Z (Right-Forward-Up)",
}

ERROR_CODES = {
    1: "No start character",
    2: "Missing r/w for config",
    3: "Incomplete Message",
    4: "Invalid Checksum",
    5: "Invalid Talker code",
    6: "Invalid Message Type",
    7: "Invalid Field",
    8: "Invalid Value",
    9: "Flash Locked",
    10: "Unexpected Character",
    11: "Feature Disabled"
}
