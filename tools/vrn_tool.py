#!/usr/bin/env python3
"""vrn_tool — flash and configure a VRN (Vitalnode, Seeed XIAO ESP32-C5) over USB.

Requirements:  python -m pip install -r requirements.txt   (esptool, pyserial)

Commands
  ports                               list connected VRNs (USB VID 303A)
  flash  <image.bin> [--port P] [--app]
                                      write firmware. Full image (default) erases all settings;
                                      --app writes only the application and keeps the settings.
  setup  [--port P] --ssid S --pass W --server URL [options]
                                      write network settings over the USB console, then reboot
  get    [--port P]                   show settings (the Wi-Fi password is masked)
  status [--port P]                   show live status (MAC, Wi-Fi, server, time, device)
  console [--port P]                  interactive console (type commands, Ctrl+C to quit)

When --port is omitted and exactly one VRN is connected, that one is used.

Only network settings live on the VRN. What it acquires (monitor type, waves) is set on the
VitalServer web monitor and sent by the VRN server (bed device port = 4300@<VRN MAC>).

Examples
  python vrn_tool.py flash vrn-c5-0.4.2-full.bin              # new unit (erases settings)
  python vrn_tool.py flash vrn-c5-0.4.3-app.bin --app         # update, keeps settings
  python vrn_tool.py setup --ssid MyWiFi --pass secret --server ws://192.168.0.10:4300/vrn
  python vrn_tool.py setup --ssid HIS --pass secret --server ws://172.16.142.70:4300/vrn \
         --ip 172.16.10.21/24 --gateway 172.16.10.1 --dns 172.16.10.1
  python vrn_tool.py setup --server wss://vrn.example.org/vrn --ca myca.pem   # private CA
  python vrn_tool.py status                                   # -> mac=10bda3c85168 ...
"""
import argparse
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


def cmd_ports(_):
    found = find_ports()
    if not found:
        print("no VRN found")
    for p in found:
        print(f"{p.device}\t{p.description}\tSN={p.serial_number or '-'}")


def cmd_flash(a):
    port = pick_port(a.port)
    offset = "0x10000" if a.app else "0x0"
    args = [sys.executable, "-m", "esptool", "--chip", "esp32c5", "--port", port, "--baud", "460800",
            "write-flash", offset, a.image]
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
    "led": "1 (default) | 0 = status LED off",
}


def add_ca(c, path):
    """Install extra trust anchors (PEM) for a wss:// server with a private certificate."""
    pem = open(path, encoding="ascii").read().strip().splitlines()
    command(c, "ca add", 0.3)
    for line in pem:
        c.write((line.strip() + "\n").encode())
        time.sleep(0.02)
    time.sleep(0.8)
    out = c.read(1 << 16).decode(errors="replace")
    lines = [l.strip() for l in out.splitlines() if l.strip().startswith(("ok", "err"))]
    print(f"{'ca':8s} -> {lines[-1] if lines else '(no reply)'}")


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
        out = command(c, f"set {key}={val}")
        for s in secrets:
            out = out.replace(s, "********")
        lines = [l.strip() for l in out.splitlines() if l.strip().startswith(("ok", "err"))]
        print(f"{key:8s} -> {lines[-1] if lines else '(no reply)'}")
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
    f.add_argument("image")
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
