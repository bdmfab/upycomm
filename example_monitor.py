"""
Continuous Monitoring Example
Reads PLC data in a loop and displays it
"""
from upycomm import SLCComm
import time

# Configuration
PLC_IP = "192.168.1.10"
SCAN_INTERVAL = 5  # seconds

# Create PLC connection
plc = SLCComm(PLC_IP)

if not plc.connect_ethernet() or not plc.connect_plc():
    print("Failed to connect to PLC")
    exit()

print("Starting continuous monitoring...")
print(f"Scan interval: {SCAN_INTERVAL} seconds")
print("Press Ctrl+C to stop\n")

try:
    while True:
        # Get timestamp
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
        timestamp = f"{hour:02d}:{minute:02d}:{second:02d}"
        
        print("=" * 50)
        print(f"Scan at {timestamp}")
        print("=" * 50)
        
        # Read N7 integers
        print("\nN7 Integer File:")
        print("-" * 30)
        for i in range(5):
            value = plc.read_tag("N7", i)
            if value is not None:
                print(f"  N7:{i} = {value}")
            else:
                print(f"  N7:{i} = Read failed")
        
        # Read B3 binary
        print("\nB3 Binary File:")
        print("-" * 30)
        for i in range(3):
            value = plc.read_tag("B3", i)
            if value is not None:
                print(f"  B3:{i} = {value:016b} (0x{value:04X})")
            else:
                print(f"  B3:{i} = Read failed")
        
        # Read individual bits from B3:0
        print("\nB3:0 Bits:")
        print("-" * 30)
        bits = []
        for bit in range(16):
            value = plc.read_tag("B3", 0, bit_number=bit)
            if value is not None:
                bits.append(str(value))
            else:
                bits.append("?")
        
        # Display in groups of 8
        print(f"  Bits 15-8:  {' '.join(bits[8:16])}")
        print(f"  Bits 7-0:   {' '.join(bits[0:8])}")
        
        # Wait before next scan
        time.sleep(SCAN_INTERVAL)
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user")
except Exception as e:
    print(f"\nError: {e}")
    import sys
    sys.print_exception(e)
finally:
    plc.disconnect()
    print("Disconnected from PLC")
