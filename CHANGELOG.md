# Changelog

## 0.5.0 — 2026-11-16

VRN firmware 0.5.0 — **first version with over-the-air updates** (Vitalnode C5 and VRN2 S3)
- The VRN server can install new firmware remotely (README: "Over-the-air firmware updates").
  Only images with the release signature are accepted; no update while a patient is connected;
  a new image that does not reach the server within 5 minutes is rolled back automatically.
  Field-tested on a C5 and a VRN2 unit at a PACU (download + check ~6 s).
- The first monitor association after a restart waits until the time from the server arrives, so
  the first data are never recorded with a wrong clock.
- Console `rawdump 1|0` (diagnosis): copies the monitor's MIB frames to the USB console for a debug
  host. Patient demographics are not copied. Off by default; nothing extra goes over the network.

VRN server 0.5.0
- `vrcodes` and the new `ota` section in `vrnserver.yaml` apply when the file is saved — adding a
  group no longer restarts (and reconnects) every VRN. Other settings still need a restart.
- OTA: offers the configured signed images (`/fw/` serves only those files) and logs the VRN's
  report.
- `/status`: per-bed wave interruption statistics; board, OTA state.
- The web monitor no longer shows a number that stopped arriving: the last value is re-sent for
  10 s only.
- A state file save that fails (Windows file lock) is retried instead of closing the VRN's session.

vrn_tool.py
- `flash --app` also resets the OTA boot selection, so a USB update takes effect on a unit that was
  updated over the air before.

## 0.4.6 — 2026-11-16

VRN firmware 0.4.6
- **VRN2 hardware** (LilyGo T-QT Pro ESP32-S3) is supported: `vrn-s3-0.4.6-*.bin`. It has no PSRAM,
  so it sends uncompressed frames and keeps a small backlog (see README). Status is shown on its
  screen. Tested on a PACU IntelliVue against the intranet VitalServer.
- `status` shows the Wi-Fi power-save state (`ps=`); new console setting `ax` (0 = no Wi-Fi 6),
  for diagnosis only.

vrn_tool.py
- `flash` detects the chip, so it works for both the Vitalnode (C5) and VRN2 (S3) images.

VRN server: unchanged (0.4.5).

Field note: a VRN given a hospital MAC/IP slot whose original device is still on the network
connects and then drops every few seconds (two stations with one MAC). Check that a slot is free
(e.g. arping from a node on the same Wi-Fi with the VRN switched off) before using it.

## 0.4.5 — 2026-11-15

VRN firmware 0.4.5
- `tls_verify` setting (`vrn_tool.py setup --tls_verify 0`): connect to a `wss://` server without
  checking its certificate. Default 1 (checked). `--ca` remains the safer way for a private CA.

VRN server
- `tls_verify: false` in the short config: accept a private certificate of VitalServer or the
  upload server (default: checked).

vrn_tool.py
- `--tls_verify`; `setup` waits for each reply (a busy VRN could answer late, shown as "no reply").

## 0.4.4 — 2026-11-15

VRN server
- Fix: bed edits from the web monitor's device form were ignored (VitalServer sends them as a
  JSON string). Verified on vitaldb.net: form edit and Advanced Settings edit both apply live.
- Device types saved by Vital Recorder as `Philips : Intellivue` are sent to the VRN as
  `Intellivue`.
- No log line for VitalServer's per-reply `dt` command.

VRN firmware: unchanged (0.4.2).

## 0.4.3 — 2026-11-15

VRN server
- A bed device's port may be the VRN's MAC alone (`10bda3c85168`, `10:bd:a3:c8:51:68`,
  `10-BD-A3-C8-51-68`) as well as `4300@<MAC>`.

VRN firmware: unchanged (0.4.2).

## 0.4.2 — 2026-11-15

Setup is now three steps: register the VRN's MAC on the VitalServer web monitor
(device port `4300@<MAC>`), give the server `vitalserver` + `vrcodes`, and give the VRN
Wi-Fi + server URL.

VRN firmware
- Identity is the MAC; no device token.
- Device type and options come only from the VRN server (set on the web); USB keeps network
  settings only (`dev`, `wavs`, `token`, `ntp`, `dgmt` removed).
- Time comes from the VRN server (no NTP on the device); records are re-stamped after the first
  sync, and the monitor-time anchor is guarded against stale replies.
- Waits for its config before acquiring; one image for all device types.

VRN server
- Short configuration: `vitalserver:` and `vrcodes:`; each vrcode's beds are read from
  VitalServer and web edits apply live (local copy used when VitalServer is unreachable).
- Listens on 4300 by default (`listen:` accepts a bare port). Device ports `4300@<MAC>` in any MAC
  notation; a different port number is warned about in `/status`.
- Serves time and device config to the VRNs; MAC conflicts close both sessions for 60 s.
- One `.vital` file per patient (Vital Recorder cutting rules); upload like Vital Recorder
  (not yet verified against vitaldb.net — `upload: off` keeps files).
- Fixes: deadlock with the web relay, crash repair on Windows, resend after a server restart.


## 0.3.1 — 2026-11-14

First public release.

VRN firmware (Vitalnode / XIAO ESP32-C5)
- Philips IntelliVue MIB/RS-232 client on the node (association, numerics, waves, alarms).
- Streams full-resolution `.vital` packets to the VRN server; sequence numbers with server
  acknowledgement and a 4 MB resend buffer (no data lost on Wi-Fi drops while powered).
- No listening network ports; settings only over USB; per-device token.
- NTP (`auto` discovery), static IP, MAC override, hidden SSID, 2.4/5 GHz with 20 MHz channels,
  private CA certificates.

VRN server
- Token authentication, strict frame validation, fsync-then-acknowledge.
- Per-bed `.vital` recording with patient-connection file cutting (Vital Recorder rules),
  crash repair.
- Live relay to the VitalDB web monitor (Vital Recorder compatible JSON).
- Optional upload of finished files; `/status` endpoint.
