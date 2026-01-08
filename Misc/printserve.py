"""
Print server - get data from plc and print label from params.zpl
Fixed version with proper tuple access and error handling
"""
from upycomm import SLCComm
import time, socket, params, machine, network # type: ignore
import uping # type: ignore

class print_obj:
    def __init__(self, ip:str, port=9100, label_list=1, tag="N7:0"):
        self.ip = ip
        self.port = port
        self.label_list = label_list
        self.addr_info = socket.getaddrinfo(ip, port)
        self.addr = self.addr_info[0][-1]
        self.tag = tag

def connect_ethernet():
    '''
    Ethernet configuration 
        params.eth_inf
        1 = WT32-ETH01
        2 = Edgebox-ESP-100
        3 = DFR0886
    '''
    if params.eth_inf == 1:
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

    elif params.eth_inf == 2:
        ''' EdgeBox-ESP-100 using W5500 '''
        bus = machine.SPI(1, 
            baudrate=2000000,
            sck = machine.Pin(13),   # FSPI_SCLK
            mosi = machine.Pin(12),  # FSPI_DO
            miso = machine.Pin(11))  # FSPI_DI

        lan = network.LAN(
            spi = bus,
            phy_type = network.PHY_W5500,
            phy_addr = 0,
            cs=machine.Pin(10),    # FSPI_CS0
            int=machine.Pin(14),   # INT#
            rst=machine.Pin(15)    # RST#        
        )        
    elif params.eth_inf == 3:
        ''' DFR0886 '''
        lan = network.LAN(
            mdc=4,              # P4/A0/Net-MDC → GPIO4
            mdio=13,            # P13/A4/Net-MDIO → GPIO13
            power=2,            # P2/Net-RST_N → GPIO2 (active high reset)
            phy_addr=1,         # Check PHY address (likely 0 or 1)
            phy_type=network.PHY_IP101,
            ref_clk_mode=network.ETH_CLOCK_GPIO0_IN  # External clock on GPIO0
        )

    # Activate the interface
    lan.active(True)

    # Wait for LAN to activate with timeout
    max_wait = 10  # Maximum wait time in seconds
    wait_count = 0
    while not lan.active():
        print("LAN is NOT Active")
        time.sleep(0.5)
        wait_count += 1
        if wait_count >= max_wait * 2:  # *2 because we sleep 0.5s each time
            print("LAN activation timeout")
            return False

    print("LAN is Active")

    # Static IP configuration
    static_config = params.serve_config
    lan.ifconfig(static_config)

    print(f"Network Config: {lan.ifconfig()}")
    
    return True

def service_plc(plc_obj, print_obj):
    """Service a single PLC/printer pair"""
    # Check if PLC is reachable
    if not any(uping.ping(plc_obj.plc_ip, count=1)):
        return 
    
    try:
        # Parse tag string (e.g., "N7:0" -> ["N7", "0"])
        tag_parts = print_obj.tag.split(":")
        file_type = tag_parts[0]
        element_num = int(tag_parts[1])
        
        # Read integer value from PLC
        value = plc_obj.read_tag(file_type, element_num)
        
        # Only print if value is non-zero
        if value is not None and value != 0:
            # Validate list index and value range
            if print_obj.label_list >= len(params.zpl):
                print(f"Error: List index {print_obj.label_list} out of range")
                return
            
            label_list = params.zpl[print_obj.label_list]
            
            # Check if value is within valid range for this list
            # Remember: index 0 is "Place Holder", so valid values are 1 to len-1
            if value < 1 or value >= len(label_list):
                print(f"Error: Label value {value} out of range for list {print_obj.label_list}")
                # Reset the PLC tag
                plc_obj.write_tag(file_type, element_num, 0)
                return
            
            # Get the ZPL label data
            zpl_data = label_list[value]
            
            # Check for date/time placeholders
            if "{TIME}" in zpl_data or "{DATE}" in zpl_data:
                print("Processing date/time placeholders")
                year, month, day, hour, minute, second, weekday, yearday = time.localtime()
                time_str = f"{hour:02d}:{minute:02d}"
                date_str = f"{day:02d}-{month:02d}-{year}"
                zpl_data = zpl_data.replace("{TIME}", time_str).replace("{DATE}", date_str)
            
            print(f"Printing label: {zpl_data[:50]}...")  # Show first 50 chars
            
            # Initialize socket and connect to printer
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)

            print(f"Connecting to printer at {print_obj.ip}:{print_obj.port}...")
            s.connect(print_obj.addr)
            print(f"Connected to printer at {print_obj.ip}")   

            # Send ZPL data to printer
            s.sendall(zpl_data.encode('utf-8') if isinstance(zpl_data, str) else zpl_data)            
            time.sleep(0.5)  # Give printer time to process

            s.close() 
            print("Label sent successfully")

            # Reset the PLC tag to 0 (acknowledge receipt) AFTER successful print
            max_retries = 3
            retry_count = 0
            reset_value = value  # Store the value we're trying to reset
            while reset_value != 0 and retry_count < max_retries:
                plc_obj.write_tag(file_type, element_num, 0)
                time.sleep(0.2)
                reset_value = plc_obj.read_tag(file_type, element_num)
                retry_count += 1
                
            if reset_value != 0:
                print(f"Warning: Failed to reset tag after {max_retries} attempts")
            
    except socket.error as e:
        print(f"Socket error: {e}")
    except Exception as e:
        print(f"Error in service_plc: {e}")
        import sys
        sys.print_exception(e)

# ==================== MAIN PROGRAM ====================

print("=" * 50)
print("Print Server Starting")
print("=" * 50)

# Declarations and Objects
plc_list = []
printer_list = []

# Read from params and create objects
# params.sta format: [("plc_ip", "printer_ip", list_num, "tag"), ...]
print(f"Number of configured stations: {len(params.sta)}")

for idx, station in enumerate(params.sta):
    plc_ip = station[0]
    printer_ip = station[1]
    list_num = station[2]
    tag = station[3]
    
    print(f"Station {idx}: PLC={plc_ip}, Printer={printer_ip}, List={list_num}, Tag={tag}")
    
    plc_list.append(SLCComm(plc_ip))
    printer_list.append(print_obj(ip=printer_ip, label_list=list_num, tag=tag))

obj_count = len(params.sta)
print(f"Created {obj_count} PLC/printer pair(s)")

# Initialize Ethernet
print("\nInitializing Ethernet...")
retry_count = 0
max_retries = 10
while not connect_ethernet():
    retry_count += 1
    print(f"Failed to connect to Ethernet (attempt {retry_count}/{max_retries})")
    if retry_count >= max_retries:
        print("FATAL: Could not initialize Ethernet")
        raise Exception("Ethernet initialization failed")
    time.sleep(0.5)
print("Ethernet connected successfully")

# Connect to PLC(s)
print("\nConnecting to PLCs...")
for idx, plc in enumerate(plc_list):
    retry_count = 0
    max_retries = 10
    while not plc.connect_plc():
        retry_count += 1
        print(f"Failed to connect to PLC {idx} (attempt {retry_count}/{max_retries})")
        if retry_count >= max_retries:
            print(f"FATAL: Could not connect to PLC {idx}")
            raise Exception(f"PLC {idx} connection failed")
        time.sleep(0.5)
    print(f"Connected to PLC {idx}")

# Set RTC (Real Time Clock)
# Format: (year, month, day, weekday, hours, minutes, seconds, subseconds)
# January 6, 2026, 8:42:00 PM (Tuesday, weekday=1)
rtc = machine.RTC()
rtc.datetime((2026, 1, 6, 1, 20, 42, 0, 0))
print(f"\nRTC set: {rtc.datetime()}")

# Loop variables 
read_interval = 0.5  # Read interval in seconds
last_time = time.ticks_ms()
loop_counter = 1
increment_interval = 5000  # Write delay in milliseconds

print("\n" + "=" * 50)
print("Entering main service loop")
print("=" * 50)

# Main service loop
while True: 
    current_time = time.ticks_ms()
    
    # Service all PLC/printer pairs
    for idx in range(obj_count):
        try:
            service_plc(plc_list[idx], printer_list[idx])
        except Exception as e:
            print(f"Error servicing station {idx}: {e}")
    
    # ----------------------- Temporary for Testing -----------------------
    # Auto-increment test counter every increment_interval milliseconds
    if loop_counter > 10:
        loop_counter = 1
            
    if time.ticks_diff(current_time, last_time) >= increment_interval:        
        try:
            plc_list[0].write_tag("N7", 0, loop_counter)  
            print(f"Test: Set N7:0 = {loop_counter}")
        except Exception as e:
            print(f"Test write error: {e}")
        time.sleep(0.25)
        last_time = current_time
        loop_counter += 1 
    # --------------------- End Temporary for Testing ---------------------   
                
    time.sleep(read_interval)
