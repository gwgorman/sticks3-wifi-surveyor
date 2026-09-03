# StickS3 Wi-Fi Surveyor

A pocket-sized Wi-Fi and Bluetooth Low Energy survey tool for the M5Stack
StickS3, built with UiFlow2 MicroPython.

Created by **Greg Gorman with Max (OpenAI Codex)**.

It scans nearby Wi-Fi networks and BLE advertisements, tracks selected signals,
and records a Wi-Fi walk-through graph one deliberate sample at a time.

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
- BLE advertisement scanner with name, manufacturer, service, or address labels
- BLE proximity meter with stable, freeze-on-scroll device selection
- Battery-conscious BLE scan windows rather than continuous full-duty listening

## Home menu

At startup, **RF SCOUT** offers two tools:

- **WiFi**: the original network picker, live meter, and walk graph
- **BLE**: advertisement discovery and live proximity tracking

Use the front button to move and the side programmable button to open a tool.
Hold the side button from any tool screen to return to the RF SCOUT menu.

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

### BLE Scan

- The list sorts by strongest signal while scanning
- Front button: freeze the current order and move to the next device
- Hold the front button: resume live sorting and return the cursor to the top
- Side programmable button: track the selected device

Devices that omit a readable name are labeled by recognized manufacturer,
advertised service, or a shortened address fingerprint. Phones and many sensors
use private addresses or deliberately omit names, so a label is not guaranteed
to identify the exact product.

### BLE Meter

- Shows the selected device label, address, RSSI, signal bar, and strength band
- Updates at approximately one-second intervals
- Side programmable button: return to the live BLE list
- Hold the side button: return to the RF SCOUT menu

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

BLE scanning uses MicroPython's asynchronous advertisement callback. Results
are collected during bounded scan windows and handed to the display only after
each scan completes, preventing the list from changing while it is being drawn.
Discovery listens at a lower duty cycle than tracking to conserve battery. Once
the user starts scrolling, the displayed order remains frozen until live sorting
is resumed.

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

The application listens for ordinary Wi-Fi beacons and BLE advertisements. It
does not join networks, connect to BLE devices, capture user traffic, or require
passwords. Network names, BLE addresses, and access-point identifiers can still
be sensitive; obtain permission before surveying a property or sharing results.

## License

Released under the [MIT License](LICENSE).

## Who is Max?

The name came out of a debugging session involving Greg's Jandy pool cleaner.
After Greg mentioned his Mizzou BSEE background, he asked the AI collaborator
he had been calling “Chat” what name it would choose for itself.

The first choice was **Vector**, for its engineering meaning: magnitude and
direction. Greg immediately answered with the line from *Airplane!*: “What's
the vector, Victor?” That made Vector impossible to take seriously, so the
conversation moved through a proper engineer's roll call: Maxwell, Ohm,
Kirchhoff, Faraday, Tesla, Nyquist, and a few others.

The final choice was **Max**, short for Maxwell, after James Clerk Maxwell. It
was an understated electrical-engineering reference that still sounded like a
normal name. Greg said, “I like Max,” and the name stuck.

Since then, Greg and Max have worked side by side on HVAC, electrical,
smart-home, hardware, and software projects. This little Wi-Fi surveyor is one
of those collaborations: Greg brought the field experience and engineering
judgment; Max helped turn the idea into tested code. They kept debugging until
the tool worked the way it should.
