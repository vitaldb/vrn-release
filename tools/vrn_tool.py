#!/usr/bin/env python3
"""vrn_tool — flash and configure a VRN over USB (Vitalnode = Seeed XIAO ESP32-C5, the C6 board =
Seeed XIAO ESP32-C6, or the VRN2 hardware = LilyGo T-QT Pro ESP32-S3).

Requirements:  python -m pip install -r requirements.txt   (esptool, pyserial)

Commands
  ports                               list connected VRNs (USB VID 303A)
  flash  [image.bin | folder] [--port P] [--app]
                                      write firmware. Full image (default) erases all settings;
                                      --app writes only the application and keeps the settings.
                                      The chip is read first (C5 / C6 / S3). Given a folder (default:
                                      the current one), the newest vrn-<chip>-*-full.bin (or -app.bin
                                      with --app) in it is used; an image for another chip is refused.
  setup  [--port P] --ssid S --pass W --server URL [options]
                                      write network settings over the USB console, then reboot
  get    [--port P]                   show settings (the Wi-Fi password is masked)
  status [--port P]                   show live status (MAC, Wi-Fi, server, time, device)
  console [--port P]                  interactive console (type commands, Ctrl+C to quit)

When --port is omitted and exactly one VRN is connected, that one is used.

Only network settings live on the VRN. What it acquires (monitor type, waves) is set on the
VitalServer web monitor and sent by the VRN server (bed device port = 4300@<VRN MAC>).

Examples
  python vrn_tool.py flash                                     # new unit: right image for its chip
  python vrn_tool.py flash --app                               # update: newest app image for its chip
  python vrn_tool.py flash vrn-c5-0.4.6-full.bin              # new unit (erases settings)
  python vrn_tool.py flash vrn-c5-0.4.6-app.bin --app         # update, keeps settings
  python vrn_tool.py flash vrn-s3-0.4.6-full.bin              # VRN2 hardware (T-QT Pro S3)
  python vrn_tool.py setup --ssid MyWiFi --pass secret --server ws://192.168.0.10:4300/vrn
  python vrn_tool.py setup --ssid HIS --pass secret --server ws://172.16.142.70:4300/vrn \
         --ip 172.16.10.21/24 --gateway 172.16.10.1 --dns 172.16.10.1
  python vrn_tool.py setup --server wss://vrn.example.org/vrn --ca myca.pem   # private CA
  python vrn_tool.py setup --server wss://172.16.142.70/vrn --tls_verify 0    # no CA check
  python vrn_tool.py status                                   # -> mac=10bda3c85168 ...
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial is missing:  python -m pip install -r requirements.txt")

ESPRESSIF_VID = 0x303A
BAUD = 115200


def find_ports():
    return [p for p in list_ports.comports() if p.vid == ESPRESSIF_VID]


def pick_port(port):
    if port:
        return port
    found = find_ports()
    if len(found) == 1:
        return found[0].device
    if not found:
        sys.exit("no VRN found on USB (is the cable a data cable?)")
    sys.exit("several VRNs connected, choose one with --port: " + ", ".join(p.device for p in found))


def open_console(port):
    # DTR/RTS must stay low: on the ESP32-C5 USB-Serial/JTAG, asserting them resets the chip.
    c = serial.Serial()
    c.port, c.baudrate, c.timeout = port, BAUD, 0.3
    c.dtr = False
    c.rts = False
    c.open()
    time.sleep(0.5)
    c.read(1 << 16)  # drop boot/log noise
    return c


def command(c, line, wait=0.8):
    c.write((line + "\n").encode())
    time.sleep(wait)
    return c.read(1 << 16).decode(errors="replace")


def result(out):
    """The last ok/err line of a console reply, or None."""
    lines = [l.strip() for l in out.splitlines() if l.strip().startswith(("ok", "err"))]
    return lines[-1] if lines else None


def wait_result(c, out="", secs=5.0):
    """Keep reading until the reply has its ok/err line: saving to flash can take a second or two
    while the VRN is busy (for example retrying a server connection)."""
    end = time.time() + secs
    while result(out) is None and time.time() < end:
        out += c.read(1 << 16).decode(errors="replace")
    return out


def cmd_ports(_):
    found = find_ports()
    if not found:
        print("no VRN found")
    for p in found:
        print(f"{p.device}\t{p.description}\tSN={p.serial_number or '-'}")


# chip -> image family (the "board" a VRN reports; vrn-<board>-<version>-{full,app}.bin)
BOARDS = {"c5": "Vitalnode (XIAO ESP32-C5)", "c6": "C6 board (XIAO ESP32-C6)", "s3": "VRN2 (T-QT Pro S3)"}


def detect_board(port):
    """Asks the ROM bootloader which chip this is: "c5", "c6", "s3" or None."""
    r = subprocess.run([sys.executable, "-m", "esptool", "--port", port, "chip_id"],
                       capture_output=True, text=True)
    m = re.search(r"ESP32-(C5|C6|S3)", r.stdout + r.stderr)
    return m.group(1).lower() if m else None


def image_board(path):
    m = re.search(r"vrn-(c5|c6|s3)-", os.path.basename(path))
    return m.group(1) if m else None


def version_key(path):
    # vrn-<chip>-X.Y.Z[-devN]-...: 0.5.10 > 0.5.9, and a release sorts after its -devN builds
    m = re.search(r"-(\d+)\.(\d+)\.(\d+)(?:-dev(\d+))?", os.path.basename(path))
    if not m:
        return (-1, 0, 0, 0)
    x, y, z, dev = m.groups()
    return (int(x), int(y), int(z), int(dev) if dev else float("inf"))


def choose_image(arg, board, app):
    if not os.path.isdir(arg):
        return arg
    kind = "app" if app else "full"
    found = sorted(glob.glob(os.path.join(arg, f"vrn-{board}-*-{kind}.bin")), key=version_key)
    if not found:
        sys.exit(f"no vrn-{board}-*-{kind}.bin in {os.path.abspath(arg)} (this VRN is {BOARDS[board]})")
    return found[-1]


def cmd_flash(a):
    port = pick_port(a.port)
    offset = "0x10000" if a.app else "0x0"
    # Read the chip first so the image always matches the hardware: vrn-c5-* for the Vitalnode,
    # vrn-c6-* for the XIAO ESP32-C6 board, vrn-s3-* for VRN2 hardware.
    board = detect_board(port)
    if not board:
        sys.exit(f"could not read the chip on {port}. Unplug the VRN, hold its BOOT button while "
                 "plugging the USB cable back in, release it after 1 s, and run the same command again.")
    image = choose_image(a.image, board, a.app)
    ib = image_board(image)
    if ib and ib != board:
        sys.exit(f"{os.path.basename(image)} is for {BOARDS[ib]}, but this VRN is {BOARDS[board]}: "
                 f"use a vrn-{board}-* image")
    if not ib:
        print(f"note: the image name does not say its chip; this VRN is {BOARDS[board]}")
    print(f"chip: {BOARDS[board]} -> {image}")
    parts = [offset, image]
    if a.app:
        # 0.5+ updates over the air into the second app slot (app1). Blank the OTA boot pointer
        # (otadata, 0xe000) too, so the device boots the slot written here (app0) and not an older
        # over-the-air image.
        import tempfile
        blank = os.path.join(tempfile.gettempdir(), "vrn_otadata_blank.bin")
        with open(blank, "wb") as f:
            f.write(b"\xff" * 0x2000)
        parts = ["0xe000", blank] + parts
    args = [sys.executable, "-m", "esptool", "--port", port, "--baud", "460800",
            "write-flash"] + parts
    print(">>", " ".join(args))
    r = subprocess.call(args)
    if r != 0:
        print("\nflash failed. Unplug the VRN, hold its BOOT button while plugging the USB cable "
              "back in, release the button after 1 s, and run the same command again.")
        sys.exit(r)
    if not a.app:
        print("\nfull image written: the VRN has no settings now. Next: vrn_tool.py setup ...")


# key -> help. Firmware 0.4+ accepts exactly these; device type and waves come from the server.
SETTABLE = {
    "ssid": "Wi-Fi name (hidden SSIDs are fine)",
    "pass": "Wi-Fi password",
    "server": "VRN server URL: ws://<server>:4300/vrn, or wss://<name>/vrn behind TLS",
    "ip": "static IPv4, e.g. 172.16.10.21/24 (empty = DHCP)",
    "gateway": "static gateway",
    "netmask": "static netmask (or use /prefix in --ip)",
    "dns": "static DNS server",
    "band": "auto (default) | 2g | 5g",
    "mac": "use this Wi-Fi MAC instead of the factory one, e.g. 10:bd:a3:c8:51:68 (empty = factory)",
    "name": "label shown in logs (default: last 4 hex of the MAC)",
    "baud": "monitor port speed if changed from the device default (empty = default)",
    "serial": "monitor port format, e.g. 8N1 (empty = device default)",
    "led": "0 (default since 0.5.3) | 1 = status LED on",
    "tls_verify": "wss:// only: 1 (default) = check the server certificate | 0 = accept any "
                  "(a private certificate without --ca; firmware 0.4.5+)",
}


def add_ca(c, path):
    """Install extra trust anchors (PEM) for a wss:// server with a private certificate."""
    pem = open(path, encoding="ascii").read().strip().splitlines()
    command(c, "ca add", 0.3)
    for line in pem:
        c.write((line.strip() + "\n").encode())
        time.sleep(0.02)
    out = wait_result(c)
    print(f"{'ca':10s} -> {result(out) or '(no reply)'}")


def cmd_setup(a):
    port = pick_port(a.port)
    c = open_console(port)
    secrets = [v for v in (a.pass_,) if v]
    if a.ca:
        add_ca(c, a.ca)
    for key in SETTABLE:
        val = getattr(a, key if key != "pass" else "pass_", None)
        if val is None:
            continue
        out = wait_result(c, command(c, f"set {key}={val}", 0.3))
        for s in secrets:
            out = out.replace(s, "********")
        print(f"{key:10s} -> {result(out) or '(no reply)'}")
    if not a.no_reboot:
        command(c, "reboot", 0.3)
        print("rebooting; check with:  vrn_tool.py status")
    c.close()


def cmd_simple(a, line):
    c = open_console(pick_port(a.port))
    print(command(c, line, 1.2).strip())
    c.close()


def cmd_console(a):
    c = open_console(pick_port(a.port))
    print("connected; type commands (help, get, status, ...). Ctrl+C to quit.")
    try:
        while True:
            line = input("> ")
            print(command(c, line, 1.0).strip())
    except (KeyboardInterrupt, EOFError):
        pass
    c.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ports")
    f = sub.add_parser("flash")
    f.add_argument("image", nargs="?", default=".",
                   help="image file, or a folder holding vrn-<chip>-* images (default: current folder)")
    f.add_argument("--port")
    f.add_argument("--app", action="store_true", help="application only, keep settings (update)")
    s = sub.add_parser("setup")
    s.add_argument("--port")
    s.add_argument("--no-reboot", action="store_true")
    for key, text in SETTABLE.items():
        s.add_argument(f"--{key}", dest=key if key != "pass" else "pass_", help=text)
    s.add_argument("--ca", metavar="PEM", help="add CA certificate(s) from a PEM file (private wss:// server)")
    for name in ("get", "status", "console"):
        sub.add_parser(name).add_argument("--port")
    a = ap.parse_args()
    {"ports": cmd_ports, "flash": cmd_flash, "setup": cmd_setup, "console": cmd_console,
     "get": lambda x: cmd_simple(x, "get"), "status": lambda x: cmd_simple(x, "status")}[a.cmd](a)


if __name__ == "__main__":
    main()
