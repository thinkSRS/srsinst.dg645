# srsinst.dg645

Python instrument driver for the **SRS DG645 Digital Delay Generator**.

The DG645 is an 8-channel digital delay and pulse generator capable of generating
precise time delays from 0 to 2000 seconds with 5 ps resolution. This driver
provides a Pythonic interface to all remote-control commands over VXI-11, TCP/IP
(raw socket), VISA, and RS-232 interfaces.

---

## Installation

```bash
pip install srsinst.dg645
```

For development (editable install):

```bash
git clone https://github.com/thinkSRS/srsinst.dg645.git
cd srsinst.dg645
pip install -e .
```

---

## Quick Start

```python
from srsinst.dg645 import DG645, Keys

# Connect via VXI-11
dg = DG645('vxi11', '192.168.0.10')

# Connect via TCP/IP (raw socket, port 5025)
dg = DG645('tcpip', '192.168.0.10', 5025)

# Connect via RS-232
dg = DG645('serial', 'COM3', 9600)

# Connect via GPIB
# (needs pyvisa)
dg = DG645('visa', 'GPI0::15::INSTR')

# Set trigger source to internal at 1 kHz
dg.trigger.trigger_source = 'internal'
dg.trigger.trigger_rate = 1000.0

# Configure channel A: 100 ns after T0
dg.delays.delay['A']['T0'] = 100e-9

# Configure channel B: 500 ns after channel A
dg.delays.delay['B']['A'] = 500e-9

# Read back delay (returns reference channel index, delay time in seconds)
ref, t = dg.delays.delay['B']
print(f'Channel B: ref={ref}, delay={t*1e9:.1f} ns')

# Set output AB amplitude to 3.5 V, positive polarity
dg.outputs.amplitude['AB'] = 3.5
dg.outputs.polarity['AB'] = True

# Fire a single trigger
dg.trigger_now()

# Check instrument status
print(dg.get_status())

dg.disconnect()
```

---

## Component Reference

| Attribute | Class | Description |
|---|---|---|
| `dg.interface` | `Interface` | IEEE-488.2 standard commands (`*IDN`, `*OPC`, `*RST`, `*CLS`, `*TRG`, `*WAI`, `*CAL`, `*TST`) |
| `dg.system` | `System` | Settings storage: `*SAV`, `*RCL`, `*PSC` |
| `dg.status` | `Status` | Status registers (INSR, ESR, STB, SRE, ESE) and LERR error queue |
| `dg.display` | `Display` | Front-panel display: `SHDP` (on/off), `DISP` (display type) |
| `dg.trigger` | `Trigger` | Trigger source, rate, level, holdoff, inhibit, prescale |
| `dg.burst` | `Burst` | Burst mode enable, count, period, delay, T0 config |
| `dg.delays` | `Delays` | Per-channel delay (`DLAY`), reference link (`LINK`), step size (`SSDL`) |
| `dg.outputs` | `Outputs` | Per-output amplitude (`LAMP`), offset (`LOFF`), polarity (`LPOL`) |
| `dg.network` | `Network` | Ethernet MAC, timebase, local/remote control, interface lock |

---

## Delay Channel Index Map

Delay channels can be addressed by name (string) or integer index:

| Name | Index | Description |
|---|---|---|
| `'T0'` | 0 | T0 output |
| `'T1'` | 1 | T1 output |
| `'A'`–`'H'` | 2–9 | Delay channels A through H |

```python
# Equivalent ways to set channel A delay:
dg.delays.delay['A']['T0'] = 100e-9
dg.delays.delay[2][0] = 100e-9          # using integer indices
```

## Output BNC Index Map

Output BNCs can be addressed by name (string) or integer index:

| Name | Index | Description |
|---|---|---|
| `'T0'` | 0 | T0 BNC output |
| `'AB'` | 1 | AB BNC output |
| `'CD'` | 2 | CD BNC output |
| `'EF'` | 3 | EF BNC output |
| `'GH'` | 4 | GH BNC output |

```python
# Equivalent ways to set AB amplitude:
dg.outputs.amplitude['AB'] = 3.5
dg.outputs.amplitude[1] = 3.5           # using integer index
```

---

## Available Interfaces

| Interface | Connection | Default |
|---|---|---|
| VXI-11 | `DG645('vxi11', '<ip>')` | Port 1861 (standard) |
| TCP/IP | `DG645('tcpip', '<ip>', 5025)` | Port 5025 |
| VISA | `DG645('visa', '<resource>')` | — |
| RS-232 | `DG645('serial', '<port>', <baud>)` | Selectable: 4800–115200 |

The RS-232 baud rate is set on the instrument front panel; the driver accepts any
rate from `[4800, 9600, 19200, 38400, 57600, 115200]`.

---

## Integration Tests

The test suite requires a live DG645 connected to the PC.

**Via VXI-11 or TCP/IP:**
```bash
pytest -v -s tests/ --ip 192.168.0.10
```

**Via RS-232:**
```bash
pytest -v -s tests/ --port COM3
```

**Via GPIB (or any VISA resource):**
```bash
pytest -v -s tests/ --resource GPIB0::15::INSTR
```

Use `-s` to allow the connection-retry prompt when the initial connection fails.

---

## License

MIT License — Copyright (c) 2026 Stanford Research Systems
