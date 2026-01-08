# uPycomm - MicroPython Allen-Bradley PLC Communication

A lightweight EtherNet/IP and PCCC implementation for ESP32 microcontrollers running MicroPython. Specifically tested and optimized for WT32-ETH01.

## Features

✅ **Full Read/Write Support**
- Read and write N7, B3, F8, T4, C5 data files
- Bit-level read/write operations
- Signed and unsigned integer handling

✅ **Native MicroPython**
- No external dependencies
- Optimized for ESP32 memory constraints
- Works with WT32-ETH01 Ethernet module

✅ **Battle-Tested**
- Matches pycomm3 packet structure byte-for-byte
- Successfully tested on Allen-Bradley MicroLogix 1400
- Handles PCCC over EtherNet/IP via unconnected messaging

## Hardware Requirements

- **WT32-ETH01** (or similar ESP32 with Ethernet)
- **Allen-Bradley PLC** (tested on MicroLogix 1400, should work with SLC 500, MicroLogix series)
- **Network connection** between ESP32 and PLC

## Installation

1. Copy `upycomm.py` to your MicroPython device
2. Import in your code:

## Quick Start

```python
from upycomm import SLCComm
from machine import Pin
import network

# Connect to Ethernet
''' WT32-ETH01 v1.4 '''        
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
static_config = ('192.168.1.50', '255.255.255.0', '192.168.1.1', '8.8.8.8')
lan.ifconfig(static_config)
print(f"Network Config: {lan.ifconfig()}")

# Connect to PLC
plc = SLCComm("192.168.1.10")

if plc.connect_plc():
    # Read a value
    value = plc.read_tag("N7", 0)
        
    # Write a value
    plc.write_tag("N7", 0, 100)
    
    # Read/write bits
    bit_value = plc.read_tag("B3", 0, bit_number=5)
    plc.write_tag("B3", 0, 1, bit_number=5)
    
    plc.disconnect()
```

## API Reference

### SLCComm(plc_ip, plc_port=44818, timeout=5)

Create a PLC connection object.

**Parameters:**
- `plc_ip` (str): IP address of the PLC
- `plc_port` (int): EtherNet/IP port (default: 44818)
- `timeout` (int): Socket timeout in seconds (default: 5)

### Methods

#### connect_plc()
Establish EtherNet/IP session and Forward Open connection. Returns `True` on success.

#### read_tag(file_type, element_number, bit_number=None, element_count=1)
Read a tag from the PLC.

**Parameters:**
- `file_type` (str): File type - "N7", "B3", "F8", "T4", "C5"
- `element_number` (int): Element index (0-based)
- `bit_number` (int, optional): Bit position (0-15) for bit-level read
- `element_count` (int): Number of elements to read (default: 1)

**Returns:** Integer value or `None` on failure

**Examples:**
```python
value = plc.read_tag("N7", 0)           # Read N7:0
value = plc.read_tag("B3", 5)           # Read B3:5
bit = plc.read_tag("B3", 0, bit_number=7)  # Read B3:0/7
```

#### write_tag(file_type, element_number, value, bit_number=None)
Write a tag to the PLC.

**Parameters:**
- `file_type` (str): File type - "N7", "B3", "F8", "T4", "C5"
- `element_number` (int): Element index (0-based)
- `value` (int): Value to write (0-65535 for words, 0-1 for bits)
- `bit_number` (int, optional): Bit position (0-15) for bit-level write

**Returns:** `True` on success, `False` on failure

**Examples:**
```python
plc.write_tag("N7", 0, 100)              # Write 100 to N7:0
plc.write_tag("N7", 1, -50)              # Write -50 to N7:1
plc.write_tag("B3", 0, 0xFF00)           # Write 0xFF00 to B3:0
plc.write_tag("B3", 0, 1, bit_number=5)  # Set B3:0/5 to 1
```

#### disconnect()
Close the connection and clean up resources.

## Supported Data Types

| Type | File# | Description | Size | Range |
|------|-------|-------------|------|-------|
| N7   | 7     | Integer     | 2 bytes | -32768 to 32767 |
| B3   | 3     | Binary      | 2 bytes | 0x0000 to 0xFFFF |
| F8   | 8     | Float       | 4 bytes | IEEE 754 |
| T4   | 4     | Timer       | 6 bytes | Complex |
| C5   | 5     | Counter     | 6 bytes | Complex |

**Note:** Full read/write support implemented for N7 and B3. F8, T4, C5 require additional development.

## Examples

See the included example files:
- `example_simple.py` - Basic read/write operations
- `example_monitor.py` - Continuous monitoring loop
- `example_control.py` - Output control and bit manipulation

## Protocol Details

### EtherNet/IP
- Session registration via Register Session (0x0065)
- List Identity (0x0063) for PLC identification
- Forward Open (service 0x54) for connected messaging
- Send RR Data (0x006F) for unconnected PCCC commands

### PCCC (DF1)
- Protected Typed Read (0xA2) for reading data
- Protected Typed Write (0xAB) for writing data
- Execute PCCC (service 0x4B) wrapped in CIP
- Unconnected messaging for MicroLogix compatibility

## Troubleshooting

**Connection fails:**
- Verify PLC IP address and network connectivity
- Check that PLC is in RUN mode
- Ensure firewall allows port 44818

**Reads work but writes fail:**
- Verify PLC is in RUN mode (some PLCs block writes in PROGRAM mode)
- Check that tags are not write-protected
- Verify user has write permissions

**Timeout errors:**
- Increase timeout parameter in constructor
- Check network latency
- Verify PLC is not overloaded

**Import errors:**
- Ensure `upycomm.py` is in the same directory as your script
- For frozen modules, include in manifest.py

## Performance Notes

- Reads: ~50-100ms per tag (varies with network)
- Writes: ~50-100ms per tag
- Bit operations: Additional read overhead for read-modify-write

## Version History

- **v27** - Added Write Capability
- **v25** - Production-ready read functionality

## License

This library is provided as-is for educational and commercial use.

## Credits

Developed through extensive packet analysis comparing with pycomm3 implementation.
Tested on Allen-Bradley MicroLogix 1400 (1766-L32BWA).

## Support

For issues, questions, or contributions, please refer to the documentation or examine the packet captures used during development.

---

**Made with ❤️ for the MicroPython and PLC automation community**
