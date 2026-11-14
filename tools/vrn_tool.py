#!/usr/bin/env python3
"""vrn_tool — flash and configure a VRN (Vitalnode, Seeed XIAO ESP32-C5) over USB.

Requirements:  python -m pip install -r requirements.txt   (esptool, pyserial)

Commands
  ports                               list connected VRNs (USB VID 303A)
  flash  <image.bin> [--port P] [--app]
                                      write firmware. Full image (default) erases all settings;
                                      --app writes only the application and keeps the settings.
  setup  [--port P] --ssid S --pass W --server URL --token T [options]
                                      write settings over the USB console, then reboot
  get    [--port P]                   show settings (secrets are masked by the device)
  status [--port P]                   show live status
  console [--port P]                  interactive console (type commands, Ctrl+C to quit)

When --port is omitted and exactly one VRN is connected, that one is used.
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


SETTABLE = ["name", "ssid", "pass", "server", "token", "band", "ip", "gateway", "netmask", "dns",
            "ntp", "mac", "dev", "baud", "serial", "wavs", "led", "dgmt"]


def cmd_setup(a):
    port = pick_port(a.port)
    c = open_console(port)
    secrets = [v for v in (a.pass_, a.token) if v]
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
    for key in SETTABLE:
        s.add_argument(f"--{key}", dest=key if key != "pass" else "pass_")
    for name in ("get", "status", "console"):
        sub.add_parser(name).add_argument("--port")
    a = ap.parse_args()
    {"ports": cmd_ports, "flash": cmd_flash, "setup": cmd_setup, "console": cmd_console,
     "get": lambda x: cmd_simple(x, "get"), "status": lambda x: cmd_simple(x, "status")}[a.cmd](a)


if __name__ == "__main__":
    main()
