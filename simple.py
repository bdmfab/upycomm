"""
Simple Example - Reading and Writing PLC Tags
"""
from upycomm import SLCComm
import time, socket, labels
import uping # type: ignore


# PLC Configuration
PLC_IP = "192.168.1.10"

# Create PLC connection
plc = SLCComm(PLC_IP)

# Create socket for printer
PRINTER_IP = '192.168.1.9'
PRINTER_PORT = 9100
addr_info = socket.getaddrinfo(PRINTER_IP, PRINTER_PORT)
addr = addr_info[0][-1]


# Connect to network and PLC
while not plc.connect_ethernet():
    print("Failed to connect to Ethernet")
    time.sleep(.5)
print("Connected to Ethernet!")

while not plc.connect_plc():
    print("Failed to connect to PLC")
    time.sleep(.5)
print("Connected to PLC!")

interval = 5000  # Write delay in ms
read_int = .5 # Read interval
cur_tim = time.ticks_ms()
last_tim = cur_tim
loop = 1

while True:

    if any(uping.ping(PLC_IP, count=1)):        
    
        try:
            # Read integer values
            value = plc.read_tag("N7", 0)
            #print(f"N7:0 = {value}")
            if value != 0:
                # Initailize a socket         
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)

                print(f"Connecting to printer at {addr}...")
                s.connect(addr)
                print("Connected!")            
                s.sendall(labels._1[value])            
                #time.sleep(.25)
                s.close() 
                plc.write_tag("N7", 0, 0)
                #time.sleep(.1)
                print("Printed a label " + str(value))         

        except Exception as e:
            print(f"Error: {e}")
            import sys
            sys.print_exception(e)
        
        finally:
            # ----------------------- Temporary for Testing -----------------------
            if loop > 10:
                loop = 1
            
            if time.ticks_diff(cur_tim, last_tim) >= interval:        
                plc.write_tag("N7", 0, loop)  
                time.sleep(.25)
                last_tim = cur_tim
                loop += 1 
            # --------------------- End Temporary for Testing ---------------------   
                
    time.sleep(read_int)
    cur_tim = time.ticks_ms()