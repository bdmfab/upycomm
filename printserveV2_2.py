"""
Print server - get data from plc and print label from params.zpl
FIXED: Properly handles multiple printers using the same PLC by sharing connections
"""
from upycomm_OF import SLCComm
import time, socket
import machine, network, os # type: ignore
import uping # type: ignore
from pcf8563 import PCF8563
import params
import ssd1306
import gc

eth_inf = 3
led = machine.Pin(15, machine.Pin.OUT)
btn = machine.Pin(38, machine.Pin.IN)
led.value(1)

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
        eth_inf
        1 = WT32-ETH01
        2 = Edgebox-ESP-100
        3 = DFR0886
    '''
    if eth_inf == 1:
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

    elif eth_inf == 2:
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
    elif eth_inf == 3:
        ''' DFR0886 '''
        print("Using interface #3")
        lan = network.LAN(
            mdc=4,              # P4/A0/Net-MDC → GPIO4
            mdio=13,            # P13/A4/Net-MDIO → GPIO13
            power=2,            # P2/Net-RST_N → GPIO2 (active high reset)
            phy_addr=1,         
            phy_type=network.PHY_IP101,
            ref_clk_mode=machine.Pin.IN
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
    if not any(uping.ping(plc_obj.plc_ip, count=1, quiet=True)):
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
            
            # Copy 1 entire list
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
                year, month, day, weekday, hour, minute, seconds, subseconds = rtc.datetime()
                time_str = f"{hour:02d}:{minute:02d}"
                date_str = f"{month:02d}-{day:02d}-{year}"
                zpl_data = zpl_data.replace("{TIME}", time_str).replace("{DATE}", date_str)            
            
            # Initialize socket and connect to printer
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)

            #print(f"Connecting to printer at {print_obj.ip}:{print_obj.port}...")
            s.connect(print_obj.addr)
            #print(f"Connected to printer at {print_obj.ip}")   

            # Send ZPL data to printer
            s.sendall(zpl_data.encode('utf-8') if isinstance(zpl_data, str) else zpl_data)            
            time.sleep(0.5)  # Give printer time to process

            s.close() 
            print(f"Label sent successfully to printer {print_obj.ip}")

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
            
    except OSError as e:
        print(f"Socket error: {e}")
    except Exception as e:
        print(f"Error in service_plc: {e}")
        import sys
        sys.print_exception(e)    
        
def comment_line():
    file_path = "/sd/params.py"
    search_string = "date_time" 
    lines = []
    modified_lines = []

    try:
        # 1. Read file into a variable
        with open(file_path, 'r') as f:
            lines = f.readlines()
        f.close()
        
        # 2. Iterate through the lines and modify the relevant one(s)
        for line in lines:
            if search_string in line: #and not line.strip().startswith('#')
                # Add '#' and a space before the line content if it's not already commented
                modified_lines.append('#' + line)
            else:
                modified_lines.append(line)
            
        with open(file_path, 'w') as f:
            for l in modified_lines:
                f.write(l)
        f.close()
        print(f"File {file_path} updated. Lines containing '{search_string}' are now commented.")

    except OSError as e:
        print(f"Error writing to file {file_path}: {e}")  
  
def run_webserver():
    """Clean up memory and start web server"""
    global plc_dict, printer_list, station_to_plc
    
    display.fill(0)            
    display.text('Cleaning memory...', 0, 10, 1)
    display.show()
    
    # Delete large objects to free memory
    print("Freeing memory before starting web server...")
    
    # Clear PLC connections
    for plc_ip, plc_obj in plc_dict.items():
        try:
            plc_obj.close_plc()
        except:
            pass
    
    del plc_dict
    del printer_list
    del station_to_plc
    
    # Force garbage collection
    gc.collect()
    
    print(f"Free memory: {gc.mem_free()} bytes")
    
    display.fill(0)            
    display.text('Server IP:', 18, 1, 1)
    display.text(params.serve_config[0], 10, 14, 1)
    display.text("----------------------", 0, 39, 1)
    display.text("WEBSERVER ACTIVE", 0, 49, 1)
    display.text("----------------------", 0, 59, 1)
    display.show()
    time.sleep(.1)
    
    import ws_info    # Start web server
      
  
# ==================== MAIN PROGRAM ====================

# Initialize I2C - DFR0886
SDA_PIN = machine.Pin(18)
SCL_PIN = machine.Pin(23)
i2c = machine.I2C(1, scl=SCL_PIN, sda=SDA_PIN, freq=400000)

# Create the RTC & Display instance
pcf = PCF8563(i2c)
display = ssd1306.SSD1306_I2C(128, 64, i2c)
rtc = machine.RTC()

# Set RTC (Real Time Clock)
# Format: (year, month, day, weekday, hours, minutes, seconds, subseconds)
# January 6, 2026, 8:42:00 PM (Tuesday, weekday=1)
if hasattr(params, "date_time"):
    pcf.set_datetime((params.date_time))
    print(f"\nPCF set: {pcf.datetime()}")
    comment_line()

# Set time to internal RTC from PCF module
t = pcf.datetime() # Returns  (year, month, date, day, hours, minutes, seconds)
rtc_t = (t[0] + 2000, t[1], t[2], t[3], t[4], t[5], t[6], 0) # Need compatable tuple
rtc.datetime(rtc_t) # Use rtc for timestamp


print("=" * 50)
print("Print Server Starting")
print("=" * 50)

# Declarations and Objects
plc_dict = {}  # Dictionary to store unique PLC objects by IP
printer_list = []
station_to_plc = []  # Maps each station to its PLC object

# Read from params and create objects
# params.sta format: [("plc_ip", "printer_ip", list_num, "tag"), ...]
print(f"Number of configured stations: {len(params.sta)}")

for idx, station in enumerate(params.sta):
    plc_ip = station[0]
    printer_ip = station[1]
    list_num = station[2]
    tag = station[3]
    
    print(f"Station {idx}: PLC={plc_ip}, Printer={printer_ip}, List={list_num}, Tag={tag}")
    
    # FIXED: Create only ONE PLC object per unique IP address
    if plc_ip not in plc_dict:
        plc_dict[plc_ip] = SLCComm(plc_ip)
        print(f"  Created new PLC object for {plc_ip}")
    else:
        print(f"  Reusing existing PLC object for {plc_ip}")
    
    # Map this station to the appropriate PLC object
    station_to_plc.append(plc_dict[plc_ip])
    
    # Create printer object for each station
    printer_list.append(print_obj(ip=printer_ip, label_list=list_num, tag=tag))

obj_count = len(params.sta)
print(f"Created {obj_count} station(s) using {len(plc_dict)} unique PLC(s)")

# Show initial free memory
gc.collect()
print(f"Free memory after setup: {gc.mem_free()} bytes")

# Initialize Ethernet
print("\nInitializing Ethernet...")
retry_count = 0
max_retries = 10
while not connect_ethernet():
    retry_count += 1
    print(f"Failed to connect to Ethernet (attempt {retry_count}/{max_retries})")
    if retry_count >= max_retries:
        print("FATAL: Could not initialize Ethernet")
        display.fill(0)
        display.text('Ethernet Failed', 18, 1, 1)
        display.show()
        raise Exception("Ethernet initialization failed")
    time.sleep(0.5)
print("Ethernet connected successfully")
display.fill(0)
display.text('Ethernet Connected', 0, 10, 1)
display.show()

# Connect to unique PLCs only once
print("\nConnecting to PLCs...")
for plc_ip, plc_obj in plc_dict.items():
    retry_count = 0
    max_retries = 3
    while not plc_obj.connect_plc():
        retry_count += 1
        print(f"Failed to connect to PLC at {plc_ip} (attempt {retry_count}/{max_retries})")
        display.fill(0)
        display.text('PLC Unreachable' , 0, 10, 1)
        display.text(str(retry_count) + " / " + str(max_retries), 30, 20, 1)
        display.show()
        
        if retry_count >= max_retries:
            print(f"WARNING: Could not connect to PLC at {plc_ip}")
            print("Starting web server for configuration...")
            time.sleep(1)
            run_webserver()
            # If we return here, web server is running and we should exit
            raise SystemExit("Web server mode activated")
        time.sleep(0.5)
    
    print(f"Connected to PLC at {plc_ip}")

print(f"Successfully connected to {len(plc_dict)} unique PLC(s)")
display.fill(0)
display.text('PLC Connected', 0, 1, 1)
display.show()

# Loop variables 
read_interval = .5  # Read interval in seconds
last_time = time.ticks_ms()
loop_counter = 1
increment_interval = 5000  # Write delay in milliseconds
cnt = 0

display.fill(0)
display.text('Server IP:', 18, 1, 1)
display.text(params.serve_config[0], 10, 14, 1)
display.text("Hold KEY for ", 12, 32, 1)
display.text("web page ", 26, 44, 1)
display.show()

print("\n" + "=" * 50)
print("Entering main service loop")
print("=" * 50)

# Main service loop
while True: 
    current_time = time.ticks_ms()
    led.value(0)
    # Service all PLC/printer pairs
    for idx in range(obj_count):
        try:
            # Use the mapped PLC object for this station
            service_plc(station_to_plc[idx], printer_list[idx])
            time.sleep(.1)
        except Exception as e:
            print(f"Error servicing station {idx}: {e}")
        finally:
            led.value(1)
                
    # ----------------------- Temporary for Testing -----------------------
    # Auto-increment test counter 
    if loop_counter > 10:
        loop_counter = 1
    if time.ticks_diff(current_time, last_time) >= increment_interval:        
        try:
            # Get the first PLC object (there's only one in your case)
            first_plc = list(plc_dict.values())[0]
            first_plc.write_tag("N7", 0, loop_counter)  
            first_plc.write_tag("N7", 1, loop_counter)  
            print(f"Test: Set N7:0 and N7:1 = {loop_counter}")
        except Exception as e:
            print(f"Test write error: {e}")
        time.sleep(0.25)
        last_time = current_time
        loop_counter += 1 
    # --------------------- End Temporary for Testing ---------------------
    
    if btn.value() == False:
        cnt += 1
    else:
        cnt = 0
        
    if cnt == 3:
        led.toggle()
        if led.value() == False:
            print("Button pressed - starting web server...")
            run_webserver()
            # If we return here, web server is running
            raise SystemExit("Web server mode activated")
                
    time.sleep(read_interval)
