# VRN — Vital Recorder Node (binary releases)

VRN turns a patient monitor's serial port into a network data source for
[VitalDB](https://vitaldb.net). A **VRN** is a small Wi-Fi node (Vitalnode board, Seeed XIAO
ESP32-C5) that talks to the monitor itself and streams the data to a **VRN server**, which
records `.vital` files, relays the live view to the VitalDB web monitor and uploads finished
files.

```
Patient monitor ──RS-232──> VRN (Wi-Fi) ──WebSocket──> VRN server ──> VitalServer web monitor
                                                           └────────> .vital files (+ upload)
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

Security model: the VRN opens **no network port** — it only dials out to its VRN server. It never
forwards raw bytes from the network to the monitor; the server can only choose the device type
and its options. Network settings are written over USB only.

---

## 1. On VitalServer (vitaldb.net web monitor)

1. **My VR → add a VR** to get a **vrcode**. One vrcode is one group (e.g. one ward or OR suite)
   and appears as one Vital Recorder with several beds. Set its group as usual.
2. Add the **beds**. In each bed, add the monitor as a device (e.g. type `Intellivue`) and set its
   **port** to `4300@<VRN MAC>`:

   ```
   4300@10bda3c85168          the MAC may also be written 10:bd:a3:c8:51:68 or 10-BD-A3-C8-51-68
   ```

   `4300` is the VRN server's listen port, the MAC identifies the VRN (see `vrn_tool.py status`).
   Device options (e.g. IntelliVue `wavs`) are set here too; the VRN server sends them to the VRN.

Beds and devices can be changed on the web at any time; the VRN server applies the change live.

## 2. On the VRN server

1. Download `vrnserver-<ver>-<os>` and `vrnserver.example.yaml`, and install it as a service:
   - Linux: `server/vrnserver.service` (instructions inside)
   - Windows: put `vrnserver.exe` and `vrnserver.yaml` in one folder and run
     `server/install-windows.cmd` as Administrator (starts at boot, opens TCP 4300)
2. Write `vrnserver.yaml`:

   ```yaml
   vitalserver: wss://mod.vitaldb.net:443   # intranet: ws://172.16.142.27:80
   vrcodes: [abcd2345e, xyz789abc]          # the vrcodes this server records
   # listen: 4300                           # optional (default 4300)
   # data: ./data                           # optional
   # upload: off                            # optional: keep files, do not upload
   ```

   - The beds of each vrcode are read from VitalServer (step 1); nothing else to configure.
     A copy is kept in `data/conf/` so recording continues if VitalServer is unreachable.
   - `listen` is the port VRNs connect to (`ws://<this server>:4300/vrn`). Behind nginx with TLS,
     use `listen: 127.0.0.1:4300` and let the VRNs use `wss://<name>/vrn`.
   - Files go to `data/vital/`; open files end in `.vital.part` and are repaired automatically
     after a crash. Finished files are uploaded like Vital Recorder does (to vitaldb.net, or to
     the intranet VitalServer). In 0.4.2 the upload is implemented but **not yet verified**
     against vitaldb.net; set `upload: off` if files must stay on the server.
3. Keep the server's clock synced (NTP): **the VRNs take their time from this server.**
4. Check: `curl http://127.0.0.1:8090/status` — per bed: connected, data lag, gaps, current file.
   A device port whose number is not the listen port is listed under `port_warnings`.

## 3. On the PC that prepares VRNs

Needs Python 3.9+ and `tools/` from this repository:

```bash
python -m pip install -r tools/requirements.txt

python tools/vrn_tool.py ports                              # find the VRN's USB port
python tools/vrn_tool.py flash vrn-c5-0.4.2-full.bin        # new unit: full image, erases settings
python tools/vrn_tool.py flash vrn-c5-0.4.2-app.bin --app   # update: keeps Wi-Fi/server settings

python tools/vrn_tool.py setup --ssid MyWiFi --pass 'wifi-password' \
    --server ws://192.168.0.10:4300/vrn                     # writes settings, then reboots
python tools/vrn_tool.py status                             # shows the MAC -> register it on the web
```

| setup option | meaning |
|---|---|
| `--ssid`, `--pass` | Wi-Fi (hidden SSIDs are fine) — **required** |
| `--server` | VRN server URL — **required**. `ws://<server>:4300/vrn`, or `wss://<name>/vrn` when the server is behind TLS |
| `--ip`, `--gateway`, `--netmask`, `--dns` | static IPv4, e.g. `--ip 172.16.10.21/24 --gateway 172.16.10.1 --dns 172.16.10.1` (no `--ip` = DHCP) |
| `--band` | `auto` (default) \| `2g` \| `5g` (20 MHz channels always) |
| `--mac` | use this Wi-Fi MAC instead of the factory one (e.g. to take over a registered network slot) |
| `--name` | label shown in logs (default: last 4 hex of the MAC) |
| `--baud`, `--serial` | only if the monitor's port speed/format was changed from the factory value |
| `--led 0` | status LED off |
| `--ca file.pem` | trust a private CA for a `wss://` server with its own certificate |

The monitor type and waves are **not** set here: they come from the VRN server (step 1).
`get` shows the stored settings (password masked); `console` opens an interactive console
(`help` lists commands).

If flashing fails: unplug the VRN, hold its **BOOT** button while plugging the USB cable in,
release after 1 s, and run the command again. Use a USB **data** cable.

Then connect the VRN to the monitor's serial port and power it.

LEDs: at power-up R → G → B; then **R** = powered, **G** blinks with monitor data,
**B** = connected to the server.

## Cable

The VRN's 3.5 mm jack carries RS-232 TX/RX/GND. The Vitalnode cable is wired for a monitor or PC
serial port (DTE, DB9 male): no null-modem adapter is needed. Push the jack in fully — a
half-inserted plug passes data in one direction only.

## Versions

See [CHANGELOG.md](CHANGELOG.md).
