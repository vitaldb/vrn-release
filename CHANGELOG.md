# Changelog

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
