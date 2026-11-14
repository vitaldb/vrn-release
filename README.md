# VRN — Vital Recorder Node (binary releases)

VRN turns a patient monitor's serial port into a network data source for
[VitalDB](https://vitaldb.net). A **VRN** is a small Wi-Fi node (Vitalnode board, Seeed XIAO
ESP32-C5) that talks to the monitor itself and streams the data to a **VRN server**, which
records `.vital` files and relays the live view to the VitalDB web monitor.

```
Patient monitor ──RS-232──> VRN (Wi-Fi) ──WSS──> VRN server ──> VitalServer web monitor
                                                     └─────────> .vital files (+ upload)
```

This repository publishes **binaries, tools and documentation only**. Download them from
[Releases](../../releases).

> **Not a medical device.** For research and data-verification use. Do not use for clinical
> decisions or alarms.

| Release asset | What |
|---|---|
| `vrn-c5-<ver>-full.bin` | VRN firmware, full image (first install; erases settings) |
| `vrn-c5-<ver>-app.bin` | VRN firmware, application only (update; keeps settings) |
| `vrnserver-<ver>-linux-amd64` / `-linux-arm64` / `-windows-amd64.exe` | VRN server |
| `vrnserver.example.yaml` | server configuration template |
| `SHA256SUMS` | checksums |

Supported monitor in this release: **Philips IntelliVue** (MIB/RS-232, 115200 8N1).

---

## 1. Flash a VRN

Needs Python 3.9+ and the tools in `tools/`:

```bash
python -m pip install -r tools/requirements.txt
python tools/vrn_tool.py ports                        # find the VRN's USB port
python tools/vrn_tool.py flash vrn-c5-0.3.1-full.bin  # first install
python tools/vrn_tool.py flash vrn-c5-0.3.1-app.bin --app   # later updates (keeps settings)
```

If flashing fails: unplug the VRN, hold its **BOOT** button while plugging the USB cable in,
release after 1 s, and run the command again. Use a USB **data** cable.

## 2. Configure a VRN

Settings are written over the USB console only (never over the network).

```bash
python tools/vrn_tool.py setup --ssid MyWiFi --pass 'wifi-password' \
    --server wss://vrn.example.org/vrn --token 'device-token' --name bed-01
python tools/vrn_tool.py status
```

| key | meaning |
|---|---|
| `ssid`, `pass` | Wi-Fi (hidden SSIDs are fine) |
| `server` | VRN server URL, `wss://host[:port]/vrn` (or `ws://` on a closed network) |
| `token` | the device's secret; the server stores only its SHA-256 |
| `ip`, `gateway`, `netmask`, `dns` | static IPv4 (empty `ip` = DHCP), e.g. `--ip 10.0.0.20/24` |
| `ntp` | `auto` (default: DHCP, then DNS servers, gateway, pool.ntp.org) or a list |
| `mac` | override the Wi-Fi MAC (e.g. to take over a registered network slot) |
| `band` | `auto` \| `2g` \| `5g` (20 MHz channels always) |
| `wavs` | waves requested from the monitor, e.g. `II,V5,PLETH,ART,CVP,CO2,AWP` |
| `dgmt` | UTC − local time in minutes (KST = −540) |

`get` shows all settings; secrets are masked. `python tools/vrn_tool.py console` opens an
interactive console (`help` lists commands).

LEDs: at power-up R → G → B; then **R** = powered, **G** blinks with monitor data,
**B** = connected to the server.

## 3. Run a VRN server

```bash
cp vrnserver.example.yaml vrnserver.yaml        # edit: storage, upstream, groups/beds
./vrnserver hash-token 'device-token'           # -> token_sha256 for that bed
./vrnserver -config vrnserver.yaml
curl http://127.0.0.1:8090/status               # per-bed status
```

- Put it behind nginx (TLS) at `/vrn`, or give it a certificate in `listen.tls`.
- Each bed is identified by the VRN's MAC; a **group** has one VitalServer `vrcode` and appears
  as one Vital Recorder with several beds on the web monitor.
- Files go to `storage.dir/vital/<yymmdd>/`. Open files end in `.vital.part` and are repaired
  automatically after a crash. Uploading is off when `upstream.upload` is empty.
- Service examples: `server/vrnserver.service` (systemd) and `server/install-windows.cmd`.

## 4. Cable

The VRN's 3.5 mm jack carries RS-232 TX/RX/GND. The Vitalnode cable is wired for a monitor or PC
serial port (DTE, DB9 male): no null-modem adapter is needed. Push the jack in fully — a
half-inserted plug passes data in one direction only.

## Versions

See [CHANGELOG.md](CHANGELOG.md).
