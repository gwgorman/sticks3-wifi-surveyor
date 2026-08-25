# StickS3 Wi-Fi Surveyor

A pocket-sized 2.4 GHz Wi-Fi survey tool for the M5Stack StickS3, built with
UiFlow2 MicroPython.

Created by **Greg Gorman with Max (OpenAI Codex)**.

It scans nearby networks, follows the strongest access point broadcasting a
selected SSID, and records a walk-through signal graph one deliberate sample at
a time.

## Features

- Select any visible Wi-Fi network
- Live RSSI meter with a color-coded strength bar
- Channel and mesh-radio count
- Walk Graph mode with up to 50 recorded samples
- Audible capture confirmation
- Hold-to-clear protection for graph data
- Smart-punctuation cleanup for the StickS3 display font
- Background Wi-Fi worker so buttons and display remain responsive during scans
- No Wi-Fi credentials required

## Tested hardware and firmware

- M5Stack StickS3 with ESP32-S3-PICO-1
- UiFlow2 firmware 2.4.8
- MicroPython 1.27.0 (M5Stack build dated 2026-06-26)

The StickS3 radio scans **2.4 GHz only**. It cannot survey 5 GHz or 6 GHz.

## Controls

### Pick Wi-Fi

- Front blue button (`BtnA`): move the selection cursor
- Side programmable button (`BtnB`): select the highlighted network and open Meter mode

### Meter

- Updates automatically in the background
- Front blue button: request an immediate refresh
- Side programmable button: open Walk Graph mode

### Walk Graph

- Stop at a measurement location and press the front blue button
- Hold position while `SAMPLING #N...` is displayed
- A high beep confirms a captured point
- A low beep means the selected network was not found
- Hold the front blue button to clear all graph points
- Side programmable button: return to the network list

The bottom-left power/reset control is not a mode button. Single-click it to
reset or power on, double-click it to power off, and avoid holding it because a
long press enters firmware-download mode.

## Installation

The application is [main.py](main.py). Back up any existing `main.py` on the
device before replacing it.

1. Install current UiFlow2 firmware for StickS3 with M5Burner.
2. Upload this repository's `main.py` to the root of the StickS3 filesystem.
3. Set UiFlow2's boot option to `0` (`Run main.py directly`).
4. Restart the device.

UiFlow2 stores the boot choice in NVS under namespace `uiflow`, key
`boot_option`. From a MicroPython prompt, it can be set with:

```python
import esp32
nvs = esp32.NVS("uiflow")
nvs.set_u8("boot_option", 0)
nvs.commit()
```

Then restart with:

```python
import machine
machine.reset()
```

## Recovery

UiFlow2 remains installed. To restore its startup menu, hold the large front
button while briefly clicking reset or while powering on. The UiFlow2 startup
code changes `boot_option` back to `1`.

Keep a backup of the original device `main.py` before installation.

## How it works

The program separates responsibilities so a synchronous Wi-Fi scan does not
freeze the controls:

- The main loop owns the display, buttons, sounds, and mode state.
- A worker thread exclusively owns `wlan.scan()`.
- A small lock-protected handoff passes completed scans back to the main loop.
- Results belonging to an old mode, network, or cleared graph are ignored.

Meter mode keeps the previous reading visible until a new scan completes.
Graph mode records the scan initiated by the button press rather than silently
substituting an older cached value.

## Signal colors

- Green: `-55 dBm` or stronger
- Yellow: `-56` through `-70 dBm`
- Red: weaker than `-70 dBm`

RSSI is useful for relative room surveys, but it is not a calibrated RF
measurement. Body position, device orientation, walls, furniture, and nearby
radio activity can all affect readings.

## Privacy and responsible use

The application listens for ordinary Wi-Fi beacon broadcasts. It does not join
networks, capture user traffic, or require passwords. Network names and access
point identifiers can still be sensitive; obtain permission before surveying a
property or sharing results.

## License

Released under the [MIT License](LICENSE).
