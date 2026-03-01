# waves
BLE Channel Sounding tones analysis tool

## Current status

As of now the tool contains:
- CS Initiator and Reflector samples based on Nordic Semiconductor Connect SDK 3.2.2. The samples perform channel sounding procedure and log raw CS data through UART to a PC.
- Python toolset with GUI parsing samples UART output and performing basic processing of the data, such as calculating magnitude and phase shift of each step and printing the statictics of the measurements.

TODO:
- phase unwrapping
- inverse fft
- music algorithm
- mode-3 support
- missing channels interpolation
- extract and use cs configuration, and selected procedure parameters
- add uart control to the samples so the python app can control when to start cs procedure

## Repo structure
* cs_ini  - channel sounding initiator
* cs_ref  - channel sounding reflector
* toolset - various python tools for channel sounding PBR data processing

## How to build and run

- install NCS 3.2.2
- build cs_ini and cs_ref samples
- flash them to two nrf54l15dk boards
- `python3 run.py -i /dev/ttyACM1 -r /dev/ttyACM3 --uart --log-uart`, adjust COM-port names if needed

## Background
Channel sounding is BLE 6.0 feature allowing devices to perform measurements of radio medium - specifically, phase and amplitude shift on different channels.

The main use-case is distance measurement allowing users to find distance between two BLE devices.

The repo provides different tools to learn basic principles of CS tones data processing. It aims to lower a threshold to start exploring channel sounding capabilities and demonstrate use-cases beyond distance measurement.
