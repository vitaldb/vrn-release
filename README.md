# VRN — Vital Recorder Nano (binary releases)

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
| `vrn-c5-<ver>-full.bin` | VRN firmware for the Vitalnode (ESP32-C5), full image (first install; erases settings) |
| `vrn-c5-<ver>-app.bin` | VRN firmware for the Vitalnode, application only (update; keeps settings) |
| `vrn-c6-<ver>-full.bin` / `-app.bin` | the same firmware for the **C6 board** (Seeed XIAO ESP32-C6), see below (0.5.3+) |
| `vrn-s3-<ver>-full.bin` / `-app.bin` | the same firmware for the older **VRN2 hardware** (LilyGo T-QT Pro ESP32-S3), see below |
| `vrnserver-<ver>-linux-amd64` / `-linux-arm64` / `-windows-amd64.exe` | VRN server (single static binary; 0.6.0+ is written in Rust) |
| `vrn-*-<ver>-app.bin.sig` | release signature of the app image (for over-the-air updates, see below) |
| `vrnserver.example.yaml` | server configuration template |
| `SHA256SUMS` | checksums |

Supported monitor in this release: **Philips IntelliVue** (MIB/RS-232, 115200 8N1).

### C6 board (ESP32-C6, firmware 0.5.3+)

The `vrn-c6-*` images run on a Seeed XIAO ESP32-C6 wired like the Vitalnode (D0 TX, D1 RX, D2-D4
LED R/G/B, the same RS-232 cable) with an external antenna on its U.FL connector (selected at
boot). Settings, server and web setup are the same as the Vitalnode. Compared with the Vitalnode:

- **2.4 GHz Wi-Fi only** (`--band` is ignored).
- **No PSRAM, smaller backlog:** 96 KB of compressed frames in RAM, roughly 4 minutes of an
  IntelliVue with a few waves. A longer network or server outage loses the data beyond that.
- 4 MB flash; over-the-air updates work as on the other boards (`c6` image in `ota.images`).

### VRN2 hardware (ESP32-S3)

The `vrn-s3-*` images turn a VRN2 unit (LilyGo T-QT Pro S3 with the RS-232 board) into a VRN with
the same settings, server and web setup as the Vitalnode. Its round screen shows the node name,
IP and three dots instead of the LED: **PWR**, **MON** (monitor data), **SRV** (server link).
This board has no PSRAM, so compared with the Vitalnode:

- **2.4 GHz Wi-Fi only.**
- **Small backlog:** about 42 KB of compressed frames in RAM (0.5.3+; before: 48 KB uncompressed),
  roughly 1-2 minutes of data. A longer network or server outage loses the data beyond that (the
  Vitalnode keeps about 30 minutes).

Flashing a full image replaces the VRN2 firmware. To keep the old one, first save it with
`python -m esptool --port <PORT> read-flash 0 0x800000 vrn2_backup.bin`.

Security model: the VRN opens **no network port** — it only dials out to its VRN server. It never
forwards raw bytes from the network to the monitor; the server can only choose the device type
and its options. Network settings are written over USB only. Firmware 0.5+ accepts an
over-the-air update only if the image carries the **release signature** (checked on the VRN against
a key built into the firmware), so a VRN server — even a compromised one — cannot install its own
code.

---

## 1. On VitalServer (vitaldb.net web monitor)

1. **My VR → add a VR** to get a **vrcode**. One vrcode is one group (e.g. one ward or OR suite)
   and appears as one Vital Recorder with several beds. Set its group as usual.
2. Add the **beds**. In each bed, add the monitor as a device (e.g. type `Intellivue`) and set its
   **port** to the VRN's MAC (see `vrn_tool.py status`), alone or with the VRN server's port:

   ```
   10bda3c85168               the MAC alone
   4300@10bda3c85168          the same, with the VRN server's listen port
   ```

   The MAC may also be written `10:bd:a3:c8:51:68` or `10-BD-A3-C8-51-68`. (A MAC alone used
   to mean a VitalConnect device in Vital Recorder; that use is replaced by the VRN.)
   Device options (e.g. IntelliVue `wavs`) are set here too; the VRN server sends them to the VRN.

Beds and devices can be changed on the web at any time; the VRN server applies the change live.
The device form (type / name / port) rewrites the whole device, as it does for Vital Recorder:
options such as `wavs` are dropped. Set options in **Advanced Settings**, which edits the conf
text shown below.

### Bed examples

The web monitor's VR settings show the group as Vital Recorder's `vr.conf` text. Each bed is a
`[BED/<name>]` section and each monitor a `[DEV/<name>]` section below it; one VRN per monitor.

**One bed, MAC only** — the monitor sends its default waves:

```ini
[BED/OR1]

[DEV/Intellivue]
type=Intellivue
port=10bda3c85168
```

**Choosing the waves** — `wavs` lists the waves to request, in priority order (names or Vital
Recorder's numeric ids). Names: `I II III V V1`…`V6 AVR AVL AVF MCL MCL1 PLETH ART ABP AOP CVP
PAP FAP ICP EEG CO2 RESP AWP AWF`. The monitor sends those it has, up to its own limit.

```ini
[BED/OR2]

[DEV/Intellivue]
type=Intellivue
port=4300@10:bd:a3:cc:15:18
wavs=II,V5,PLETH,ART,CVP,CO2,AWP
```

**A ward (one vrcode, several beds) with file-cutting rules** — the keys at the top apply to the
whole group, as in Vital Recorder:

```ini
CUT_FILE=1
CUT_BY=any
PT_WAITING_TIME=5
CUT_HOURLY=0

[BED/PACU1]

[DEV/Intellivue]
type=Intellivue
port=10bda3c85168

[BED/PACU2]

[DEV/Intellivue]
type=Intellivue
port=10-BD-A3-CF-A3-68
```

| key | meaning |
|---|---|
| `CUT_FILE` | `1` = one `.vital` file per patient (default), `0` = no patient detection |
| `CUT_BY` | a patient is connected when there is: `any` = HR or SpO2, `hr`, `spo2`, empty = HR and SpO2 (BIS/PSI/INVOS always count) |
| `PT_WAITING_TIME` | minutes without a patient before the file is closed (default 5) |
| `CUT_HOURLY` | `1` = also start a new file every hour |

Do not put comments on these lines: everything after `=` is the value.

**Beds that are not VRNs** stay as they are: a port such as `COM3` or `4300@35.183` (an older
recorder) is kept in the conf but not recorded by the VRN server.

In this release a VRN drives **Philips IntelliVue** only (`type=Intellivue`). Another type is
refused by the VRN and shown as `cfg_error` in the server's `/status`.


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
   # tls_verify: false                      # optional: VitalServer has a private certificate
   ```

   - The beds of each vrcode are read from VitalServer (step 1); nothing else to configure.
     A copy is kept in `data/conf/` so recording continues if VitalServer is unreachable.
   - `listen` is the port VRNs connect to (`ws://<this server>:4300/vrn`). Behind nginx with TLS,
     use `listen: 127.0.0.1:4300` and let the VRNs use `wss://<name>/vrn`.
   - Files go to `data/vital/`; open files end in `.vital.part` and are repaired automatically
     after a crash. Finished files are uploaded like Vital Recorder does (to vitaldb.net, or to
     the intranet VitalServer). In 0.4.2 the upload is implemented but **not yet verified**
     against vitaldb.net; set `upload: off` if files must stay on the server.
   - `tls_verify: false` accepts a private certificate on VitalServer or the upload server. Better:
     add the hospital CA to the server's OS trust store and keep the check on. (Vital Recorder's
     setting for the same thing is `TLS_INSECURE`; its default `1` does not check.)
3. Keep the server's clock synced (NTP): **the VRNs take their time from this server.**
4. Check: `curl http://127.0.0.1:8090/status` — per bed: connected, data lag, gaps, current file.
   A `4300@<MAC>` port whose number is not the listen port is listed under `port_warnings`.
5. Changes to `vrcodes` and `ota` in `vrnserver.yaml` apply when the file is saved (0.5.0+); the
   VRNs of the other groups stay connected. Other settings need a restart of the service.

### Over-the-air firmware updates (VRN firmware 0.5.0+)

A VRN running 0.5.0 or later can be updated from its VRN server instead of over USB. Download the
`-app.bin` **and** its `.sig` for each board into one folder on the server, then add:

```yaml
ota:
  enable: true
  dir: C:/vrnserver/fw                 # holds vrn-c5-0.5.3-app.bin(.sig), vrn-c6-..., vrn-s3-...
  version: "VRNIV 0.5.3"               # the firmware the VRNs should run
  images: {c5: vrn-c5-0.5.3-app.bin, c6: vrn-c6-0.5.3-app.bin, s3: vrn-s3-0.5.3-app.bin}
  beds: [OR1, OR2]                     # optional: only these beds (empty = all)
  # force: true                        # optional: update even while a patient is connected
```

- The server offers the image to each VRN that runs another version, **never while a patient is
  connected** (it waits). The VRN downloads it from the same server address it already uses
  (works through relays/NAT; the VRN still opens no port), checks the SHA-256 and the release
  signature, writes it to its second firmware slot and restarts (~10 s of data from that VRN).
- The new firmware must hold a server connection for 30 s to confirm itself. Otherwise — or if it
  crashes — the VRN returns to the previous firmware after at most 5 minutes and will not take that
  version again. The server log shows `OTA offered / rebooting / ok / failed / rolled-back`.
- Units below 0.5.0 need one USB update (`flash ... -app.bin --app`) first.
- `force: true` updates beds with a patient too (the VRN restarts for ~20 s; firmware 0.5.2+
  honours it, 0.5.0/0.5.1 still wait until the patient is gone).

### Debug capture (VRN firmware 0.5.2+)

Add `debug=1` to a bed's device in the VR settings on the web monitor (next to `type=` and
`wavs=`). The VRN then also sends every frame it exchanges with the monitor to its VRN server,
which keeps them per bed and day in `data/debug/<bed>/raw-YYYYMMDD.log.gz` for 14 days
(`YYYY-MM-DD HH:MM:SS RAW RX|TX <epoch> <hex>`). Remove it (or set `debug=0`) to stop. Switching
it does not interrupt the monitor connection. **The capture contains patient data, including
demographics: keep the server's data folder as protected as the recordings.** Capture frames are
dropped first when the network is busy; the recording is never affected.

## 3. On the PC that prepares VRNs

Needs Python 3.9+ and `tools/` from this repository:

```bash
python -m pip install -r tools/requirements.txt

python tools/vrn_tool.py ports                              # find the VRN's USB port
python tools/vrn_tool.py flash                              # new unit: full image, erases settings
python tools/vrn_tool.py flash --app                        # update: keeps Wi-Fi/server settings
# flash reads the chip and takes the newest vrn-<c5|c6|s3>-*-full.bin (-app.bin with --app) from
# the current folder (or give a folder / an image file); an image for another chip is refused.

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
| `--led 1` | status LED on (0.5.3+: off by default; the bed's VR settings can also set it) |
| `--ca file.pem` | trust a private CA for a `wss://` server with its own certificate |
| `--tls_verify 0` | `wss://` without checking the server certificate (a private certificate whose CA you do not have). Still encrypted, but any server could pose as yours: prefer `--ca` |

The monitor type and waves are **not** set here: they come from the VRN server (step 1).
`get` shows the stored settings (password masked); `console` opens an interactive console
(`help` lists commands).

If flashing fails: unplug the VRN, hold its **BOOT** button while plugging the USB cable in,
release after 1 s, and run the command again. Use a USB **data** cable.

Then connect the VRN to the monitor's serial port and power it.

LEDs: at power-up R → G → B; then **R** = powered, **G** blinks with monitor data,
**B** = connected to the server. From 0.5.3 they stay dark after the power-up sequence unless
`--led 1` (or the bed's VR settings) turns them on. On VRN2 hardware the screen shows the same as
dots (PWR / MON / SRV); with the LED off the screen is off.

## Cable

The VRN's 3.5 mm jack carries RS-232 TX/RX/GND. The Vitalnode cable is wired for a monitor or PC
serial port (DTE, DB9 male): no null-modem adapter is needed. Push the jack in fully — a
half-inserted plug passes data in one direction only.

## Versions

See [CHANGELOG.md](CHANGELOG.md).
