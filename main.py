# SPDX-FileCopyrightText: 2026 Greg Gorman
# SPDX-License-Identifier: MIT
# Project: Greg Gorman with Max (OpenAI Codex)

"""Interactive 2.4 GHz Wi-Fi survey tool for the M5Stack StickS3.

The UiFlow2 ``wlan.scan()`` call is synchronous and normally freezes both the
display and button polling for several seconds.  This application keeps the
interface responsive by assigning all radio scans to one worker thread.  The
main thread owns the display, buttons, speaker, and application state; the two
threads exchange one pending request and one completed result under a lock.

Three user modes are provided:

* Pick Wi-Fi: scan and select a visible SSID.
* Meter: continuously show the strongest AP broadcasting the selected SSID.
* Walk Graph: capture deliberate, button-triggered RSSI samples around a room.

The code targets UiFlow2 MicroPython rather than desktop CPython.  It relies on
M5Stack-specific display, button, and speaker APIs.
"""

import M5
from M5 import *
import network
import time
import _thread


# ---------------------------------------------------------------------------
# Display palette and device initialization
# ---------------------------------------------------------------------------

BG = 0x101820
WHITE = 0xFFFFFF
MUTED = 0x91A0B5
GREEN = 0x49E56D
YELLOW = 0xFFD34E
RED = 0xFF6868
BLUE = 0x4EA1FF

M5.begin()
display = M5.Display
display.fillScreen(BG)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Application state is owned and mutated by the main thread only.
mode = 0
target = ""
visible_networks = []
selected_index = 0
graph_points = []
graph_generation = 0
last_meter_request = 0

# Worker handoff state.  A request is ``(kind, ssid, graph_generation)``.
# A result is ``(request, scan_rows, error_message)``.  Keeping a single radio
# owner prevents overlapping calls into the MicroPython network stack.
scan_lock = _thread.allocate_lock()
scan_request = None
scan_result = None
scan_busy = False


def safe_ssid(raw):
    """Decode an SSID and replace glyphs unsupported by the small display font."""

    try:
        value = raw.decode()
    except Exception:
        return "<?>"
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
    }
    for original, replacement in replacements.items():
        value = value.replace(original, replacement)
    return "".join(c if 32 <= ord(c) <= 126 else "?" for c in value)


def color_for(rssi):
    """Return the display color for an RSSI value measured in dBm."""

    return GREEN if rssi >= -55 else (YELLOW if rssi >= -70 else RED)


def text(value, x, y, color=WHITE, large=False):
    """Draw a short text label using one of the two application font sizes."""

    display.setFont(display.FONTS.DejaVu18 if large else display.FONTS.DejaVu12)
    display.setTextColor(color, BG)
    display.drawString(str(value), x, y)


def footer(action):
    """Draw the standard front-button and side-button hint."""

    text("A:%s  B:mode" % action, 3, 222, MUTED)


def beep(frequency=5000, duration=100):
    """Play a non-critical UI tone; keep running if audio is unavailable."""

    try:
        Speaker.tone(frequency, duration)
    except Exception:
        pass


def request_scan(kind, name="", generation=0):
    """Queue a scan, replacing any older request that has not started yet.

    Replacing a pending request is intentional: the newest user action is more
    useful than an obsolete automatic meter refresh.
    """

    global scan_request
    scan_lock.acquire()
    scan_request = (kind, name, generation)
    scan_lock.release()


def worker_loop():
    """Own the Wi-Fi radio and publish completed scans to the main thread."""

    global scan_request, scan_result, scan_busy
    while True:
        request = None
        scan_lock.acquire()
        if scan_request is not None:
            request = scan_request
            scan_request = None
            scan_busy = True
        scan_lock.release()

        if request is None:
            time.sleep_ms(20)
            continue

        try:
            rows = wlan.scan()
            result = (request, rows, None)
        except Exception as error:
            result = (request, None, str(error))

        scan_lock.acquire()
        scan_result = result
        scan_busy = False
        scan_lock.release()


def take_result():
    """Atomically consume the worker's most recently completed result."""

    global scan_result
    scan_lock.acquire()
    result = scan_result
    scan_result = None
    scan_lock.release()
    return result


def radio_idle():
    """Return True when no scan is active or waiting to start."""

    scan_lock.acquire()
    idle = not scan_busy and scan_request is None
    scan_lock.release()
    return idle


def grouped(rows):
    """Group raw AP rows by SSID and retain each network's strongest radio.

    A grouped row has the shape ``(best_rssi, channel, ap_count, ssid)``.
    Hidden SSIDs are counted separately so they do not crowd the pick screen.
    """

    networks = {}
    hidden = 0
    for item in rows:
        ssid = safe_ssid(item[0])
        if not ssid:
            hidden += 1
            continue
        if ssid not in networks:
            networks[ssid] = [item[3], item[2], 1]
        else:
            networks[ssid][2] += 1
            if item[3] > networks[ssid][0]:
                networks[ssid][0] = item[3]
                networks[ssid][1] = item[2]
    visible = sorted(
        [(v[0], v[1], v[2], name) for name, v in networks.items()],
        reverse=True,
    )
    return visible, hidden


def target_result(rows, name):
    """Return strongest RSSI, channel, and AP count for one selected SSID."""

    matches = [item for item in rows if safe_ssid(item[0]) == name]
    if not matches:
        return None, None, 0
    best = max(matches, key=lambda item: item[3])
    return best[3], best[2], len(matches)


# ---------------------------------------------------------------------------
# Pick Wi-Fi mode
# ---------------------------------------------------------------------------


def draw_list():
    """Render the selectable, scrolling list of grouped network names."""

    display.fillScreen(BG)
    text("PICK WIFI", 4, 4, WHITE, True)
    text("%d found" % len(visible_networks), 4, 26, MUTED)
    if not visible_networks:
        text("Scanning...", 4, 65, YELLOW)
    start = selected_index - 6 if selected_index >= 7 else 0
    for row_index, item_index in enumerate(range(start, min(start + 7, len(visible_networks)))):
        rssi, channel, count, ssid = visible_networks[item_index]
        marker = ">" if item_index == selected_index else " "
        color = WHITE if marker == ">" else color_for(rssi)
        text("%s%3d %02d/%d %s" % (marker, rssi, channel, count, ssid[:7]),
             1, 49 + row_index * 24, color)
    text("A:pick B:select", 3, 222, MUTED)


def start_list_scan():
    """Clear the previous list, show progress, and queue a fresh discovery."""

    global visible_networks, selected_index
    visible_networks = []
    selected_index = 0
    draw_list()
    request_scan("list")


# ---------------------------------------------------------------------------
# Live Meter mode
# ---------------------------------------------------------------------------


def draw_meter_shell():
    """Draw static meter elements once so later scans do not blank the screen."""

    display.fillScreen(BG)
    text("METER", 4, 4, WHITE, True)
    text(target[:16], 4, 29, BLUE)
    display.drawRect(8, 119, 119, 25, MUTED)
    text("Waiting...", 7, 78, MUTED, True)
    footer("read")


def update_meter(rows):
    """Update only dynamic meter regions from a completed background scan."""

    rssi, channel, count = target_result(rows, target)
    display.fillRect(0, 54, 135, 54, BG)
    display.fillRect(9, 120, 117, 23, BG)
    display.drawRect(8, 119, 119, 25, MUTED)
    display.fillRect(0, 151, 135, 52, BG)
    if rssi is None:
        text("NOT FOUND", 7, 78, RED, True)
        return
    color = color_for(rssi)
    display.setFont(display.FONTS.DejaVu40)
    display.setTextColor(color, BG)
    display.drawString(str(rssi), 18, 58)
    text("dBm", 88, 82, color)
    # Map the useful -90..-30 dBm range onto a simple 0..100 bar.
    quality = max(0, min(100, (rssi + 90) * 100 // 60))
    display.fillRect(11, 122, quality * 113 // 100, 19, color)
    text("Channel %d" % channel, 8, 157, WHITE)
    text("Mesh radios %d" % count, 8, 180, WHITE)


# ---------------------------------------------------------------------------
# Walk Graph mode
# ---------------------------------------------------------------------------


def graph_y(rssi):
    """Map -30..-90 dBm onto the graph's top-to-bottom pixel range."""

    clipped = max(-90, min(-30, rssi))
    return 50 + ((-30 - clipped) * 140 // 60)


def draw_graph(message=None, message_color=MUTED):
    """Redraw the graph, its latest 12 visible points, and optional status."""

    display.fillScreen(BG)
    text("WALK GRAPH", 4, 4, WHITE, True)
    text(target[:13] + "  %d pts" % len(graph_points), 4, 27, BLUE)
    for level in (-40, -60, -80):
        y = graph_y(level)
        display.drawLine(28, y, 128, y, 0x344052)
        text(str(level), 1, y - 6, MUTED)
    display.drawRect(27, 49, 102, 142, MUTED)
    shown = graph_points[-12:]
    previous = None
    for index, value in enumerate(shown):
        x = 31 + index * 8
        y = graph_y(value)
        if previous is not None:
            display.drawLine(previous[0], previous[1], x, y, BLUE)
        display.fillCircle(x, y, 3, color_for(value))
        previous = (x, y)
    if message is not None:
        text(message, 7, 196, message_color)
    elif shown:
        text("Last %d dBm" % shown[-1], 31, 196, color_for(shown[-1]))
    else:
        text("Walk, then press A", 7, 196, MUTED)
    footer("point")


# ---------------------------------------------------------------------------
# State transitions and worker-result processing
# ---------------------------------------------------------------------------


def change_mode():
    """Advance List -> Meter -> Graph and initialize the destination mode."""

    global mode, target, graph_points, graph_generation, last_meter_request
    if mode == 0 and visible_networks:
        chosen = visible_networks[selected_index][3]
        if chosen != target:
            target = chosen
            graph_points = []
            # Invalidate an in-flight point belonging to the old SSID.
            graph_generation += 1
    mode = (mode + 1) % 3
    beep(4200, 60)
    if mode == 0:
        start_list_scan()
    elif mode == 1:
        draw_meter_shell()
        last_meter_request = time.ticks_ms()
        request_scan("meter", target)
    else:
        draw_graph()


def process_result(result):
    """Apply a completed scan only if it still belongs to the active state."""

    global visible_networks, selected_index, last_meter_request
    if result is None:
        return
    request, rows, error = result
    kind, name, generation = request
    if error is not None:
        if mode == 2 and kind == "graph":
            draw_graph("SCAN ERROR", RED)
            beep(1800, 250)
        return
    if kind == "list" and mode == 0:
        visible_networks, hidden = grouped(rows)
        selected_index = 0
        for index, item in enumerate(visible_networks):
            if item[3] == target:
                selected_index = index
                break
        draw_list()
    elif kind == "meter" and mode == 1 and name == target:
        update_meter(rows)
        last_meter_request = time.ticks_ms()
    # The generation token prevents a scan started before graph-clear or an
    # SSID change from quietly adding a stale point afterward.
    elif kind == "graph" and mode == 2 and name == target and generation == graph_generation:
        rssi, channel, count = target_result(rows, target)
        if rssi is None:
            draw_graph("NOT FOUND", RED)
            beep(1800, 250)
        else:
            graph_points.append(rssi)
            if len(graph_points) > 50:
                graph_points.pop(0)
            draw_graph()
            beep(5000, 120)


# ---------------------------------------------------------------------------
# Startup and responsive main loop
# ---------------------------------------------------------------------------


_thread.start_new_thread(worker_loop, ())
start_list_scan()

while True:
    # M5.update() must run frequently for click/hold events to be recognized.
    M5.update()
    process_result(take_result())

    if BtnB.wasClicked():
        change_mode()
    elif mode == 2 and BtnA.wasHold():
        graph_points = []
        graph_generation += 1
        draw_graph("GRAPH CLEARED", YELLOW)
        beep(2500, 100)
    elif BtnA.wasClicked():
        if mode == 0:
            if visible_networks:
                selected_index = (selected_index + 1) % len(visible_networks)
                draw_list()
        elif mode == 1:
            request_scan("meter", target)
            last_meter_request = time.ticks_ms()
        else:
            draw_graph("SAMPLING #%d..." % (len(graph_points) + 1), YELLOW)
            request_scan("graph", target, graph_generation)

    # Meter refreshes are opportunistic: never queue one over a user-requested
    # graph sample or another scan already using the radio.
    if mode == 1 and radio_idle() and time.ticks_diff(time.ticks_ms(), last_meter_request) >= 1000:
        request_scan("meter", target)
        last_meter_request = time.ticks_ms()

    time.sleep_ms(20)
