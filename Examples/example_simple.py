"""
Simple Example - Reading and Writing PLC Tags
"""
from upycomm import SLCComm
import time

# Configuration
PLC_IP = "192.168.1.10"

# Create PLC connection
plc = SLCComm(PLC_IP)

# Connect to network and PLC
if not plc.connect_ethernet():
    print("Failed to connect to Ethernet")
    exit()

if not plc.connect_plc():
    print("Failed to connect to PLC")
    exit()

print("Connected to PLC!")

try:
    # ===== WRITE EXAMPLES =====
    print("\n=== Writing to PLC ===")
    
    # Write integer value
    print("Writing 100 to N7:0...")
    if plc.write_tag("N7", 0, 100):
        print("  Success!")
    
    # Write negative value
    print("Writing -50 to N7:1...")
    if plc.write_tag("N7", 1, -50):
        print("  Success!")
    
    # Write binary value
    print("Writing 0x00FF to B3:0...")
    if plc.write_tag("B3", 0, 0x00FF):
        print("  Success!")
    
    # Write a single bit
    print("Setting B3:0/5 to 1...")
    if plc.write_tag("B3", 0, 1, bit_number=5):
        print("  Success!")
    
    time.sleep(0.5)  # Give PLC time to process
    
    # ===== READ EXAMPLES =====
    print("\n=== Reading from PLC ===")
    
    # Read integer values
    value = plc.read_tag("N7", 0)
    print(f"N7:0 = {value}")
    
    value = plc.read_tag("N7", 1)
    print(f"N7:1 = {value}")
    
    # Read binary value
    value = plc.read_tag("B3", 0)
    print(f"B3:0 = {value} (0x{value:04X})")
    
    # Read individual bit
    value = plc.read_tag("B3", 0, bit_number=5)
    print(f"B3:0/5 = {value}")
    
    print("\n=== All operations completed successfully! ===")
    
except KeyboardInterrupt:
    print("\nStopped by user")
except Exception as e:
    print(f"Error: {e}")
    import sys
    sys.print_exception(e)
finally:
    plc.disconnect()
    print("Disconnected from PLC")
