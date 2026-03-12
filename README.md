# waves

<img src="waves_icon.png" width="125"/>
BLE Channel Sounding phase-based ranging analysis tool

## Background
Channel sounding is BLE 6.0 feature allowing devices to perform measurements of radio medium - specifically, phase and amplitude shift on different channels.

The main use-case of the BLE CS is distance measurement allowing users to find distance between two BLE devices.

The repo provides different tools to learn basic principles of CS tones data processing. It does not contain any ready-to-use solution for distance measurement, but rather serves as a playground for learning and experimenting with BLE CS data.

## Repo structure
* cs_ini  - channel sounding initiator firmware sample for nrf54l15dk
* cs_ref  - channel sounding reflector firmware sample for nrf54l15dk
* toolset - various python tools for channel sounding PBR data processing

## How to build and run

- install NCS 3.2.2
- build cs_ini and cs_ref samples (can skip if using prebuilt .hex for standard nrf54l15 devkits)
- flash them to two nrf54l15dk boards
- `python3 run.py -i /dev/ttyACM1 -r /dev/ttyACM3 --uart --log-uart`, adjust COM-port names if needed

## Current status

As of now the tool contains:
- CS Initiator and Reflector samples based on Nordic Semiconductor Connect SDK 3.2.2. The samples perform channel sounding procedure and log raw CS data through UART to a PC.
- Python toolset with GUI parsing samples UART output and performing basic processing of the data, such as calculating magnitude and phase shift of each step and printing the statistics of the measurements.

TODO:
- phase unwrapping
- inverse fft
- music algorithm
- mode-3 support
- missing channels interpolation
- extract and use cs configuration, and selected procedure parameters
- add uart control to the samples so the python app can control when to start cs procedure

## Links

- [How to install nrf connect sdk](https://docs.nordicsemi.com/bundle/ncs-3.2.2/page/nrf/installation/install_ncs.html)
- [BLE Channel Sounding Tech Overview](https://www.bluetooth.com/channel-sounding-tech-overview/)