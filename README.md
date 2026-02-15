# LiTime BMS BLE - Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/rubenmuehlhans/litime-ble-hacs)](https://github.com/rubenmuehlhans/litime-ble-hacs/releases)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rubenmuehlhans&repository=litime-ble-hacs&category=integration)

Home Assistant custom integration for monitoring and controlling **LiTime**, **Redodo**, and **PowerQueen** LiFePO4 batteries via Bluetooth Low Energy (BLE).

## Features

- Automatic Bluetooth discovery of LiTime BMS devices
- Real-time monitoring of battery status, voltages, temperatures, and more
- Individual cell voltage monitoring (up to 16 cells)
- Charge/discharge control via switches
- Estimated time until 15% SOC (or full charge)
- Protection and failure status reporting
- Automatic reconnection and offline detection
- Multi-battery support
- German and English translations

## Supported Devices

This integration supports LiFePO4 batteries with BLE-capable BMS from:

- **LiTime** (device name prefix `LT-`)
- **Redodo** (device name prefix `LT-` or `L-`)
- **PowerQueen** (device name prefix `LT-` or `L-`)

The BMS must advertise BLE service UUID `0xFFE0`.

## Requirements

- Home Assistant 2024.2.0 or newer
- Bluetooth adapter on the Home Assistant host (built-in, USB dongle, or ESPHome Bluetooth Proxy)
- The BMS must not be connected to another BLE client (e.g. an ESP32 running ESPHome) at the same time

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/rubenmuehlhans/litime-ble-hacs` as a custom repository with category **Integration**
4. Search for **LiTime BMS BLE** and install it
5. Restart Home Assistant

### Manual

1. Download the `custom_components/litime_bms_ble` folder from this repository
2. Copy it into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Automatic discovery

If your Home Assistant host has a Bluetooth adapter, LiTime batteries within range will be discovered automatically. A notification will appear prompting you to set up the device.

### Manual setup

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **LiTime BMS BLE**
3. Select your battery from the list of discovered devices

## Entities

### Sensors

| Sensor | Unit | Description |
|---|---|---|
| Total voltage | V | Battery pack total voltage |
| Current | A | Charge/discharge current (negative = discharging) |
| Power | W | Calculated power (voltage x current) |
| State of charge | % | Battery charge level (SOC) |
| State of health | % | Battery health (SOH) |
| Cell temperature | °C | Battery cell temperature |
| MOSFET temperature | °C | BMS MOSFET temperature |
| Remaining capacity | Ah | Remaining usable capacity |
| Full charge capacity | Ah | Capacity at full charge |
| Discharge cycles | - | Total discharge cycle count |
| Total discharge | Ah | Cumulative discharge |
| Min cell voltage | V | Lowest individual cell voltage |
| Max cell voltage | V | Highest individual cell voltage |
| Delta cell voltage | V | Difference between min and max cell voltage |
| Cell voltage 1-16 | V | Individual cell voltages |
| Protection status | - | Active protection alerts (or "OK") |
| Failure status | - | Active failure alerts (or "OK") |
| Estimated time at 15% SOC | - | Timestamp when 15% SOC will be reached (or full charge when charging) |
| Remaining time to 15% SOC | h | Hours until 15% SOC is reached (or full charge when charging) |

### Binary Sensors

| Sensor | Description |
|---|---|
| Charging | Battery is currently charging |
| Discharging | Battery is currently discharging |
| Balancing | Cells are being balanced |
| Online | BLE connection is active |

### Switches

| Switch | Description |
|---|---|
| Charging | Enable/disable charging |
| Discharging | Enable/disable discharging |
| Connection | Enable/disable the BLE connection (turns off polling and disconnects) |

## BLE Protocol

The integration communicates with the BMS using GATT over BLE:

- **Service UUID:** `0000FFE0-0000-1000-8000-00805F9B34FB`
- **Notify characteristic (FFE1):** Receives status responses from the BMS
- **Write characteristic (FFE2):** Sends commands to the BMS

### Command frame format

Commands are 8 bytes:

```
{0x00, 0x00, 0x04, 0x01, CMD, 0x55, 0xAA, CHECKSUM}
```

Checksum = `0x04 + CMD`

### Commands

| Command | Code | Checksum | Description |
|---|---|---|---|
| Query status | `0x13` | `0x17` | Request 104-byte status response |
| Charge on | `0x0A` | `0x0E` | Enable charging |
| Charge off | `0x0B` | `0x0F` | Disable charging |
| Discharge on | `0x0C` | `0x10` | Enable discharging |
| Discharge off | `0x0D` | `0x11` | Disable discharging |

### Status response format

The BMS responds with a notification on FFE1. Valid status responses have byte `[2] == 0x65`. The response is at least 104 bytes, little-endian:

| Offset | Size | Type | Description |
|---|---|---|---|
| 2 | 1 | uint8 | Response marker (`0x65` for status) |
| 12-15 | 4 | uint32 | Total voltage (mV) |
| 16-47 | 32 | 16x uint16 | Cell voltages (mV each) |
| 48-51 | 4 | int32 | Current (mA, negative = discharging) |
| 52-53 | 2 | int16 | Cell temperature (°C) |
| 54-55 | 2 | int16 | MOSFET temperature (°C) |
| 62-63 | 2 | uint16 | Remaining capacity (x0.01 Ah) |
| 64-65 | 2 | uint16 | Full charge capacity (x0.01 Ah) |
| 68-71 | 4 | uint32 | Heat state (bit 0x80 = discharge disabled) |
| 76-79 | 4 | uint32 | Protection flags |
| 80-83 | 4 | uint32 | Failure flags |
| 84-87 | 4 | uint32 | Balancing state (per byte per cell) |
| 88-89 | 2 | uint16 | Battery state (0x0000=discharging, 0x0001=charging, 0x0004=charge disabled) |
| 90-91 | 2 | uint16 | State of charge (%) |
| 92-93 | 2 | uint16 | State of health (%) |
| 96-99 | 4 | uint32 | Discharge cycle count |
| 100-103 | 4 | uint32 | Total discharge (mAh) |

### Protection flags

| Flag | Value | Description |
|---|---|---|
| Overcharge | `0x00000004` | Cell overcharge protection |
| Over-discharge | `0x00000020` | Cell over-discharge protection |
| Charge overcurrent | `0x00000040` | Charge current too high |
| Discharge overcurrent | `0x00000080` | Discharge current too high |
| High temp 1 | `0x00000100` | Temperature warning level 1 |
| High temp 2 | `0x00000200` | Temperature warning level 2 |
| Low temp 1 | `0x00000400` | Low temperature warning level 1 |
| Low temp 2 | `0x00000800` | Low temperature warning level 2 |
| Short circuit | `0x00004000` | Short circuit detected |

## Troubleshooting

### Battery not discovered

- Ensure Bluetooth is enabled on your Home Assistant host
- Check that the battery is powered on and within BLE range (~10m)
- LiTime batteries advertise with names starting with `LT-` or `L-`
- Make sure no other BLE client (e.g. ESP32 with ESPHome) is connected to the BMS - BLE only allows one connection at a time
- Try adding the integration manually via **Settings** > **Devices & Services** > **Add Integration**

### "Timeout waiting for response"

- The BMS is connected but not responding to queries
- Check that the BMS firmware supports the status query command (`0x13`)
- Check the Home Assistant logs for debug output (`Notification: ... hex=...`)

### Connection drops / "InProgress" errors

- BLE range is limited to approximately 10 meters
- Consider using an [ESPHome Bluetooth Proxy](https://esphome.github.io/bluetooth-proxies/) to extend range
- The integration polls every 30 seconds and automatically reconnects
- If you see `InProgress` errors, restart Home Assistant to reset the Bluetooth adapter state

### Sensors show "Unavailable"

- The battery may be out of BLE range or powered off
- Check the **Online** binary sensor for connection status
- The integration starts with all sensors unavailable and updates them once a successful BLE response is received
- Use the **Connection** switch to manually disconnect/reconnect

## License

This project is licensed under the MIT License.
