# uPycomm - MicroPython Allen-Bradley PLC Communication

A lightweight EtherNet/IP implementation for ESP32 microcontrollers running MicroPython. Specifically tested and optimized for WT32-ETH01.

## Features

✅ **Dual Protocol Support**
- **PCCC**: File-based addressing for SLC/MicroLogix PLCs
- **CIP**: Tag-based addressing for CompactLogix/ControlLogix/Micro800 PLCs

✅ **Full Read/Write Support**
- Auto type detection for Logix tags
- Bit-level operations for SLC
- All CIP data types (BOOL, INT, DINT, REAL, etc.)

✅ **Native MicroPython**
- No external dependencies
- Optimized for ESP32 memory constraints
- Works with WT32-ETH01 Ethernet module

## Hardware Requirements

- **WT32-ETH01** (or similar ESP32 with Ethernet)
- **Allen-Bradley PLC**:
  - MicroLogix (1100, 1400, 1500)
  - CompactLogix (1769-L series)
  - ControlLogix (1756-L series)
  - Micro800 (2080-LC series)
- **Network connection** between ESP32 and PLC

## Installation

1. Copy `upycomm.py` to your MicroPython device
2. Import in your code

## Quick Start - SLC/MicroLogix (PCCC)

```python
from upycomm import SLC
import machine
import network

# Initialize Ethernet (WT32-ETH01 v1.4)
lan = network.LAN(
    mdc=machine.Pin(23),
    mdio=machine.Pin(18),
    power=machine.Pin(16),
    phy_type=network.PHY_LAN8720,
    phy_addr=1,
    ref_clk_mode=machine.Pin.IN,
    ref_clk=machine.Pin(0)
)
lan.active(True)
lan.ifconfig(('192.168.1.50', '255.255.255.0', '192.168.1.1', '8.8.8.8'))
print(f"Network: {lan.ifconfig()[0]}")

# Connect to PLC
plc = SLC("192.168.1.10")

if plc.connect():
    # Read a value
    value = plc.read("N7", 0)
    print(f"N7:0 = {value}")
    
    # Write a value
    plc.write("N7", 0, 100)
    
    # Read/write bits
    bit = plc.read("B3", 0, bit_number=5)
    plc.write("B3", 0, 1, bit_number=5)
    
    plc.disconnect()
```

## Quick Start - Logix (CIP)

```python
from upycomm import Logix
import machine
import network

# Initialize Ethernet (same as above)
lan = network.LAN(
    mdc=machine.Pin(23),
    mdio=machine.Pin(18),
    power=machine.Pin(16),
    phy_type=network.PHY_LAN8720,
    phy_addr=1,
    ref_clk_mode=machine.Pin.IN,
    ref_clk=machine.Pin(0)
)
lan.active(True)
lan.ifconfig(('192.168.1.50', '255.255.255.0', '192.168.1.1', '8.8.8.8'))

# Connect to PLC
plc = Logix("192.168.1.10")

if plc.connect():
    # Read tags (auto-detect type)
    value = plc.read("Counter")
    print(f"Counter = {value}")
    
    # Write tags (auto-detect type)
    plc.write("Counter", 1000)
    plc.write("Temperature", 72.5)
    plc.write("RunMode", True)
    
    # Write with explicit type (faster)
    plc.write("Speed", 1500, 'INT')
    plc.write("Total", 50000, 'DINT')
    
    plc.disconnect()
```

## Quick Start - CompactLogix with Routing

```python
from upycomm import Logix

# For CompactLogix in a chassis (slot-based routing)
plc = Logix("192.168.1.10", slot=2, use_routing=True)

if plc.connect():
    value = plc.read("ProductCount")
    plc.write("ProductCount", value + 1)
    plc.disconnect()
```

## API Reference

### SLC(plc_ip, plc_port=44818, timeout=5)

Create a SLC/MicroLogix PLC connection object.

**Parameters:**
- `plc_ip` (str): IP address of the PLC
- `plc_port` (int): EtherNet/IP port (default: 44818)
- `timeout` (int): Socket timeout in seconds (default: 5)

#### Methods

##### connect()
Establish EtherNet/IP session and Forward Open connection. Returns `True` on success.

##### read(file_type, element_number, bit_number=None, element_count=1)
Read a tag from the PLC.

**Parameters:**
- `file_type` (str): File type - "N7", "B3", "F8", "T4", "C5"
- `element_number` (int): Element index (0-based)
- `bit_number` (int, optional): Bit position (0-15) for bit-level read
- `element_count` (int): Number of elements to read (default: 1)

**Returns:** Integer value or `None` on failure

**Examples:**
```python
value = plc.read("N7", 0)              # Read N7:0
value = plc.read("B3", 5)              # Read B3:5
bit = plc.read("B3", 0, bit_number=7)  # Read B3:0/7
```

##### write(file_type, element_number, value, bit_number=None)
Write a tag to the PLC.

**Parameters:**
- `file_type` (str): File type - "N7", "B3"
- `element_number` (int): Element index (0-based)
- `value` (int): Value to write (0-65535 for words, 0-1 for bits)
- `bit_number` (int, optional): Bit position (0-15) for bit-level write

**Returns:** `True` on success, `False` on failure

**Examples:**
```python
plc.write("N7", 0, 100)                # Write 100 to N7:0
plc.write("N7", 1, -50)                # Write -50 to N7:1
plc.write("B3", 0, 0xFF00)             # Write 0xFF00 to B3:0
plc.write("B3", 0, 1, bit_number=5)    # Set B3:0/5 to 1
```

##### disconnect()
Close the connection and clean up resources.

---

### Logix(plc_ip, plc_port=44818, timeout=5, slot=0, use_routing=False)

Create a Logix (CompactLogix/ControlLogix/Micro800) PLC connection object.

**Parameters:**
- `plc_ip` (str): IP address of the PLC
- `plc_port` (int): EtherNet/IP port (default: 44818)
- `timeout` (int): Socket timeout in seconds (default: 5)
- `slot` (int): PLC slot in chassis (default: 0)
- `use_routing` (bool): Enable backplane routing for ControlLogix (default: False)

#### Methods

##### connect()
Establish EtherNet/IP session. Returns `True` on success.

##### read(tag_name, count=1)
Read a tag from the PLC.

**Parameters:**
- `tag_name` (str): Name of the tag (e.g., "Counter", "Temperature")
- `count` (int): Number of elements to read (default: 1)

**Returns:** Tag value or `None` on failure

**Examples:**
```python
value = plc.read("Counter")            # Read integer tag
value = plc.read("Temperature")        # Read float tag
value = plc.read("RunMode")            # Read boolean tag
```

##### write(tag_name, value, data_type=None, auto_detect=True)
Write a tag to the PLC.

**Parameters:**
- `tag_name` (str): Name of the tag
- `value` (int/float/bool): Value to write
- `data_type` (str/int, optional): Force specific type ('INT', 'DINT', 'REAL', etc.)
- `auto_detect` (bool): Auto-detect type by reading tag first (default: True)

**Returns:** `True` on success, `False` on failure

**Examples:**
```python
# Auto-detect type (reads tag first, then writes)
plc.write("Counter", 1000)             # Auto-detects DINT
plc.write("Temperature", 72.5)         # Auto-detects REAL
plc.write("RunMode", True)             # Auto-detects BOOL

# Explicit type (faster, no read needed)
plc.write("Speed", 1500, 'INT')        # Force INT type
plc.write("Total", 50000, 'DINT')      # Force DINT type
plc.write("Setpoint", 75.5, 'REAL')    # Force REAL type

# Using constants (imported from upycomm)
from upycomm import CIP_INT, CIP_DINT, CIP_REAL
plc.write("Speed", 1500, CIP_INT)
plc.write("Total", 50000, CIP_DINT)
plc.write("Setpoint", 75.5, CIP_REAL)

# Skip auto-detect (use default type)
plc.write("Value", 100, auto_detect=False)  # Uses DINT default
```

##### disconnect()
Close the connection and clean up resources.

## Supported Data Types

### SLC/MicroLogix (PCCC)

| Type | File# | Description | Size | Range |
|------|-------|-------------|------|-------|
| N7   | 7     | Integer     | 2 bytes | -32768 to 32767 |
| B3   | 3     | Binary      | 2 bytes | 0x0000 to 0xFFFF |
| F8   | 8     | Float       | 4 bytes | IEEE 754 |
| T4   | 4     | Timer       | 6 bytes | Complex |
| C5   | 5     | Counter     | 6 bytes | Complex |

**Note:** Full read/write support for N7 and B3. F8, T4, C5 require additional development.

### Logix (CIP)

| Type | String | Constant | Size | Range |
|------|--------|----------|------|-------|
| BOOL | 'BOOL' | CIP_BOOL | 1 byte | True/False |
| SINT | 'SINT' | CIP_SINT | 1 byte | -128 to 127 |
| INT | 'INT' | CIP_INT | 2 bytes | -32,768 to 32,767 |
| DINT | 'DINT' | CIP_DINT | 4 bytes | -2.1B to 2.1B |
| LINT | 'LINT' | CIP_LINT | 8 bytes | 64-bit signed |
| USINT | 'USINT' | CIP_USINT | 1 byte | 0 to 255 |
| UINT | 'UINT' | CIP_UINT | 2 bytes | 0 to 65,535 |
| UDINT | 'UDINT' | CIP_UDINT | 4 bytes | 0 to 4.2B |
| ULINT | 'ULINT' | CIP_ULINT | 8 bytes | 64-bit unsigned |
| REAL | 'REAL' | CIP_REAL | 4 bytes | 32-bit float |
| LREAL | 'LREAL' | CIP_LREAL | 8 bytes | 64-bit float |

**Auto-detection (when type not specified):**
- `bool` → BOOL
- `int` → DINT (safest default)
- `float` → REAL

## Protocol Details

### EtherNet/IP (Common)
- Session registration via Register Session (0x0065)
- Send RR Data (0x006F) for unconnected messaging
- Forward Open (0x0054) for connected messaging (SLC only)

### PCCC (SLC/MicroLogix)
- Protected Typed Read (0xA2) for reading data
- Protected Typed Write (0xAB) for writing data
- Execute PCCC (service 0x4B) wrapped in CIP
- File-based addressing (N7:0, B3:5/7)

### CIP (Logix)
- Read Tag (0x4C) for reading tags
- Write Tag (0x4D) for writing tags
- Tag-based addressing (tag names)
- Unconnected Send (0x52) for backplane routing
- Optional routing through chassis slots

## Troubleshooting

**Connection fails:**
- Verify PLC IP address and network connectivity
- Check that PLC is accessible (ping test)
- Ensure firewall allows port 44818
- For Logix with routing: verify slot number

**Reads work but writes fail:**
- Verify PLC is in RUN mode
- Check that tags/files are not write-protected
- For Logix: verify tag exists and data type matches

**Type mismatch errors (Logix):**
- Use auto-detect: `plc.write("Tag", value)` (reads tag first)
- Or specify type: `plc.write("Tag", value, 'INT')`
- For INT tags, must specify 'INT' or use auto-detect

**Timeout errors:**
- Increase timeout parameter in constructor
- Check network latency
- Verify PLC is not overloaded

**Import errors:**
- Ensure `upycomm.py` is in the same directory
- For frozen modules, include in manifest.py

## Performance Notes

### SLC/MicroLogix
- Reads: ~50-100ms per tag
- Writes: ~50-100ms per tag
- Bit operations: Additional overhead for read-modify-write

### Logix
- Reads: ~30-60ms per tag
- Writes (auto-detect): ~60-120ms (read + write)
- Writes (explicit type): ~30-60ms (write only)
- Recommendation: Use explicit types for performance

## Comparison: SLC vs Logix

| Feature | SLC (PCCC) | Logix (CIP) |
|---------|------------|-------------|
| **Addressing** | File-based (N7:0) | Tag-based ("Counter") |
| **PLCs** | MicroLogix, SLC 500 | CompactLogix, Micro800, ControlLogix |
| **Read** | `plc.read("N7", 0)` | `plc.read("Counter")` |
| **Write** | `plc.write("N7", 0, 100)` | `plc.write("Counter", 100)` |
| **Bit Access** | `bit_number` parameter | Read tag directly |
| **Type Detection** | Not needed | Auto or explicit |
| **Routing** | Not needed | Optional for chassis |

## Version History

- **v28.0.0** - Unified library with SLC and Logix support
  - Renamed SLCComm → SLC
  - Added Logix class for CompactLogix/ControlLogix/Micro800
  - Consistent API across both protocols
  - Auto type detection for Logix tags
  - Hardware-based serial number generation
- **v27.0.0** - Added write capability for SLC
- **v25.0.0** - Production-ready read functionality

## License

This library is provided as-is for educational and commercial use.

## Credits

Developed through extensive packet analysis comparing with pycomm3 implementation.

**Tested on:**
- Allen-Bradley MicroLogix 1400 (1766-L32BWA)
- Allen-Bradley Micro800 (2080-LC20-20QBB)
- WT32-ETH01 (ESP32 with LAN8720 PHY)

## Support

For issues, questions, or contributions, please refer to the documentation or examine the packet captures used during development.

---

**Made with ❤️ for the MicroPython and PLC automation community**
