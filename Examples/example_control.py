"""
Control Example - Toggle Outputs
Demonstrates controlling PLC outputs by writing to bits
"""
from upycomm import SLCComm
import time

# Configuration
PLC_IP = "192.168.1.10"
OUTPUT_FILE = "B3"
OUTPUT_ELEMENT = 0

# Create PLC connection
plc = SLCComm(PLC_IP)

if not plc.connect_ethernet() or not plc.connect_plc():
    print("Failed to connect to PLC")
    exit()

print("Control Example - Output Toggle")
print("=" * 50)
print(f"Controlling: {OUTPUT_FILE}:{OUTPUT_ELEMENT}")
print("=" * 50)

try:
    # Example 1: Turn on specific outputs
    print("\n1. Turning ON bits 0, 2, 4...")
    for bit in [0, 2, 4]:
        plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 1, bit_number=bit)
        time.sleep(0.1)
    
    # Verify
    value = plc.read_tag(OUTPUT_FILE, OUTPUT_ELEMENT)
    print(f"   Result: {OUTPUT_FILE}:{OUTPUT_ELEMENT} = {value:016b}")
    time.sleep(2)
    
    # Example 2: Turn off specific outputs
    print("\n2. Turning OFF bits 0, 2, 4...")
    for bit in [0, 2, 4]:
        plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 0, bit_number=bit)
        time.sleep(0.1)
    
    # Verify
    value = plc.read_tag(OUTPUT_FILE, OUTPUT_ELEMENT)
    print(f"   Result: {OUTPUT_FILE}:{OUTPUT_ELEMENT} = {value:016b}")
    time.sleep(2)
    
    # Example 3: Blink an output
    print("\n3. Blinking bit 5 (5 times)...")
    for i in range(5):
        # Turn on
        plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 1, bit_number=5)
        print(f"   Blink {i+1}: ON")
        time.sleep(0.5)
        
        # Turn off
        plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 0, bit_number=5)
        print(f"   Blink {i+1}: OFF")
        time.sleep(0.5)
    
    # Example 4: Write entire word at once
    print("\n4. Writing entire word (pattern 0xAA55)...")
    plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 0xAA55)
    
    # Verify
    value = plc.read_tag(OUTPUT_FILE, OUTPUT_ELEMENT)
    print(f"   Result: {OUTPUT_FILE}:{OUTPUT_ELEMENT} = {value:016b} (0x{value:04X})")
    time.sleep(2)
    
    # Example 5: Clear all
    print("\n5. Clearing all outputs...")
    plc.write_tag(OUTPUT_FILE, OUTPUT_ELEMENT, 0x0000)
    
    # Verify
    value = plc.read_tag(OUTPUT_FILE, OUTPUT_ELEMENT)
    print(f"   Result: {OUTPUT_FILE}:{OUTPUT_ELEMENT} = {value:016b}")
    
    print("\n=== All control examples completed! ===")
    
except KeyboardInterrupt:
    print("\nStopped by user")
except Exception as e:
    print(f"Error: {e}")
    import sys
    sys.print_exception(e)
finally:
    plc.disconnect()
    print("Disconnected from PLC")
