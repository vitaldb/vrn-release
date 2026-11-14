# Changelog

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
