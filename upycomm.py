"""
upycomm - MicroPython Allen-Bradley PLC Communication Library
Version 27.0.0

A lightweight EtherNet/IP and PCCC implementation for ESP32 microcontrollers
running MicroPython, specifically tested on WT32-ETH01 and Micrologix 1400.

Supports:
- Reading N7, B3, F8, T4, C5 data files
- Writing to N7 and B3 files
- Bit-level read/write operations
- Allen-Bradley MicroLogix 1400 and similar PLCs

Usage:
    from upycomm import SLCComm
    
    plc = SLCComm("192.168.1.10")
    if plc.connect_ethernet() and plc.connect_plc():
        value = plc.read_tag("N7", 0) 
        plc.write_tag("N7", 0, 100)  #Write 100 to N7:0
        plc.disconnect()
"""

import socket
import struct
import machine # type: ignore



class SLCComm:
    '''
    Provides communication for SLC & Micrologix Allen Bradley PLC's

    '''
    VERSION = "v27.0.0"  # FIXED: Mask before data in write command!

    def __init__(self, plc_ip, plc_port=44818, timeout=5):
        print(f"SLCComm {self.VERSION}")
        self.plc_ip = plc_ip
        self.plc_port = plc_port
        self.timeout = timeout
        self.socket = None
        self.session_handle = 0
        self.connected = False
        self.sequence = 1
        self.conn_sequence = 2
        self.o_to_t_connection_id = 0
        self.t_to_o_connection_id = 0
        self.pccc_tns = 1  # Start at 1 like pycomm3

        # PCCC Constants
        self.SLC_CMD_CODE = 0x0F
        self.SLC_FNC_READ = 0xA2
        self.SLC_FNC_WRITE = 0xAB  # Write function code

        # File type codes
        self.PCCC_DATA_TYPE = {
            "N7": b'\x89',
            "B3": b'\x85',
            "F8": b'\x8A',
            "T4": b'\x86',
            "C5": b'\x87',
        }

        # Data sizes in bytes
        self.PCCC_DATA_SIZE = {
            "N7": 2,
            "B3": 2,
            "F8": 4,
            "T4": 6,
            "C5": 6,
        }

        # Generate a unique serial number from machine ID
        try:
            uid_bytes = machine.unique_id()
            # Convert first 4 bytes to unsigned 32-bit integer
            self.serial_number = struct.unpack('<I', uid_bytes[:4])[0]
        except Exception as e:
            # Fallback to static value if machine.unique_id() fails
            print(f"Warning: Could not get unique_id, using fallback serial number: {e}")
            self.serial_number = 0xaabbccdd    

    def connect_plc(self):
        """Establish EtherNet/IP connection to PLC"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print("TCP_NODELAY enabled")
            except:
                print("TCP_NODELAY not available")

            self.socket.settimeout(self.timeout)
            self.socket.connect((self.plc_ip, self.plc_port))

            if not self.register_session():
                print("Failed to register session")
                return False

            try:
                self.list_identity()
            except:
                pass

            if not self.forward_open():
                print("Failed to establish Forward Open connection")
                return False

            self.connected = True
            print(f"Connected to PLC at {self.plc_ip}:{self.plc_port}")

            return True

        except Exception as e:
            print(f"Failed to connect to PLC: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Close PLC connection"""
        if self.socket:
            try:
                self.forward_close()
                self.unregister_session()
            except:
                pass
            self.socket.close()
            self.connected = False
            print("Disconnected from PLC")

    def register_session(self):
        """Register EtherNet/IP session"""
        try:
            packet = bytearray(28)
            packet[0:2] = struct.pack('<H', 0x0065)
            packet[2:4] = struct.pack('<H', 4)
            packet[4:8] = struct.pack('<I', 0)
            packet[8:12] = struct.pack('<I', 0)
            packet[12:20] = b'\x00' * 8
            packet[20:24] = struct.pack('<I', 0)
            packet[24:26] = struct.pack('<H', 1)
            packet[26:28] = struct.pack('<H', 0)

            self.socket.send(packet)
            response = self.socket.recv(28)

            if len(response) >= 8:
                command = struct.unpack('<H', response[0:2])[0]
                status = struct.unpack('<I', response[8:12])[0]

                if command == 0x0065 and status == 0:
                    self.session_handle = struct.unpack('<I', response[4:8])[0]
                    print(f"Session registered: 0x{self.session_handle:08X}")
                    return True

            return False
        except Exception as e:
            print(f"Session registration failed: {e}")
            return False

    def unregister_session(self):
        """Unregister EtherNet/IP session"""
        if self.session_handle == 0:
            return

        try:
            packet = bytearray(24)
            packet[0:2] = struct.pack('<H', 0x0066)
            packet[2:4] = struct.pack('<H', 0)
            packet[4:8] = struct.pack('<I', self.session_handle)
            packet[8:12] = struct.pack('<I', 0)
            packet[12:20] = b'\x00' * 8
            packet[20:24] = struct.pack('<I', 0)

            self.socket.send(packet)
        except:
            pass

    def list_identity(self):
        """Send List Identity to get PLC info"""
        try:
            packet = bytearray(24)
            packet[0:2] = struct.pack('<H', 0x0063)
            packet[2:4] = struct.pack('<H', 0)
            packet[4:8] = struct.pack('<I', 0)
            packet[8:12] = struct.pack('<I', 0)
            packet[12:20] = b'\x00' * 8
            packet[20:24] = struct.pack('<I', 0)

            self.socket.send(packet)
            response = self.socket.recv(1024)

            if len(response) > 28:
                print("PLC Identity received")
                return True
            return False
        except:
            return False

    def forward_open(self):
        """Establish Forward Open connection"""
        try:
            self.o_to_t_connection_id = 0xddccbbaa #random.randint(0x00010000, 0xFFFFFFFF)

            cip_data = bytearray()

            cip_data.append(0x54)
            cip_data.append(0x02)
            cip_data.append(0x20)
            cip_data.append(0x06)
            cip_data.append(0x24)
            cip_data.append(0x01)
            cip_data.append(0x0A)
            cip_data.append(0xF9)

            cip_data += struct.pack('<I', self.o_to_t_connection_id)
            cip_data += struct.pack('<I', 0)
            cip_data += struct.pack('<H', 0x1971)
            cip_data += struct.pack('<H', 0x1009)
            cip_data += struct.pack('<I', 0x19711009)
            cip_data.append(0x00)
            cip_data += b'\x00\x00\x00'

            cip_data += struct.pack('<I', 200000)
            cip_data += struct.pack('<H', 0x43F4)
            cip_data += struct.pack('<I', 200000)
            cip_data += struct.pack('<H', 0x43F4)

            cip_data.append(0xA3)
            cip_data.append(0x03)
            cip_data.append(0x20)
            cip_data.append(0x02)
            cip_data.append(0x24)
            cip_data.append(0x01)
            cip_data.append(0x2C)
            cip_data.append(0x01)

            packet = self.create_send_rr_data(cip_data)
            self.socket.send(packet)

            response = self.socket.recv(1024)

            if len(response) >= 24:
                offset = 24
                offset += 6
                item_count = struct.unpack('<H', response[offset:offset + 2])[0]
                offset += 2

                for _ in range(item_count):
                    item_type = struct.unpack('<H', response[offset:offset + 2])[0]
                    item_length = struct.unpack('<H', response[offset + 2:offset + 4])[0]
                    offset += 4

                    if item_type == 0xB2:
                        service_reply = response[offset]
                        offset += 2

                        status = response[offset]

                        if status == 0:
                            offset += 1
                            ext_status_size = response[offset]
                            offset += 1 + ext_status_size

                            self.t_to_o_connection_id = struct.unpack('<I', response[offset:offset + 4])[0]
                            print(f"Forward Open successful!")
                            print(f"O->T Connection ID: 0x{self.o_to_t_connection_id:08X}")
                            print(f"T->O Connection ID: 0x{self.t_to_o_connection_id:08X}")
                            return True
                        else:
                            print(f"Forward Open failed with status: 0x{status:02X}")
                            return False

                    offset += item_length

            return False
        except Exception as e:
            print(f"Forward Open failed: {e}")
            return False

    def forward_close(self):
        """Close Forward Open connection"""
        if self.o_to_t_connection_id == 0:
            return

        try:
            cip_data = bytearray()

            cip_data.append(0x4E)
            cip_data.append(0x02)
            cip_data.append(0x20)
            cip_data.append(0x06)
            cip_data.append(0x24)
            cip_data.append(0x01)
            cip_data.append(0x0A)
            cip_data.append(0xF9)
            cip_data += struct.pack('<H', 0x1971)
            cip_data += struct.pack('<H', 0x1009)
            cip_data += struct.pack('<I', 0x19711009)
            cip_data.append(0x03)
            cip_data.append(0x20)
            cip_data.append(0x02)
            cip_data.append(0x24)
            cip_data.append(0x01)
            cip_data.append(0x2C)
            cip_data.append(0x01)

            packet = self.create_send_rr_data(cip_data)
            self.socket.send(packet)

            try:
                self.socket.recv(1024)
            except:
                pass

        except:
            pass

    def create_send_rr_data(self, cip_data):
        """Create Send RR Data packet"""
        packet_data = bytearray()

        packet_data += struct.pack('<I', 0)
        packet_data += struct.pack('<H', 0)
        packet_data += struct.pack('<H', 2)
        packet_data += struct.pack('<H', 0x00)
        packet_data += struct.pack('<H', 0)
        packet_data += struct.pack('<H', 0xB2)
        packet_data += struct.pack('<H', len(cip_data))
        packet_data += cip_data

        header = bytearray(24)
        header[0:2] = struct.pack('<H', 0x006F)
        header[2:4] = struct.pack('<H', len(packet_data))
        header[4:8] = struct.pack('<I', self.session_handle)
        header[8:12] = struct.pack('<I', 0)
        header[12:20] = b'\x00' * 8
        header[20:24] = struct.pack('<I', 0)

        return header + packet_data

    def create_pccc_command(self, file_type, file_number, element, element_count=1):
        """Create PCCC Execute command - PYCOMM3 EXACT structure"""

        # Get TNS and increment
        tns = self.pccc_tns
        self.pccc_tns = (self.pccc_tns + 1) % 65536

        # Build CIP wrapper
        cip_data = bytearray()

        # Service: 0x4B (Execute PCCC)
        cip_data.append(0x4B)

        # Request Path Size: 0x02 (2 words)
        cip_data.append(0x02)

        # Request Path: Class 0x67 (PCCC Class), Instance 0x01
        cip_data.append(0x20)  # 8-bit Class
        cip_data.append(0x67)  # PCCC Class
        cip_data.append(0x24)  # 8-bit Instance
        cip_data.append(0x01)  # Instance 1

        # Requestor ID Length: 7 bytes
        cip_data.append(0x07)

        # Requestor ID - Port/Link + Serial + CMD
        cip_data.append(0x09)  # Port 1
        cip_data.append(0x10)  # Link 0 (backplane)
        cip_data += struct.pack('<I', self.serial_number)  # 4-byte serial
        cip_data.append(self.SLC_CMD_CODE)  # 0x0F (CMD goes in requestor ID!)

        # After requestor ID: TNS + padding + FNC + parameters
        # NO DST/SRC/CMD/STS here!
        cip_data += struct.pack('<H', tns)  # TNS (2 bytes, little-endian)
        cip_data.append(0x00)  # Padding/separator

        # FNC: Function code (0xA2 for Protected Typed Logical Read)
        cip_data.append(self.SLC_FNC_READ)

        # Byte size to read
        byte_size = self.PCCC_DATA_SIZE[file_type] * element_count
        cip_data.append(byte_size)

        # File number
        cip_data.append(file_number)

        # File type
        cip_data.append(self.PCCC_DATA_TYPE[file_type][0])

        # Element number (2 bytes, little-endian)
        cip_data += struct.pack('<H', element)

        return bytes(cip_data)

    def create_pccc_write_command(self, file_type, file_number, element, value):
        """Create PCCC write command (FNC 0xAB - Protected Typed Write)"""
        # Increment TNS for this request
        tns = self.pccc_tns
        self.pccc_tns = (self.pccc_tns + 1) % 65536

        # Build CIP wrapper
        cip_data = bytearray()

        # Service: 0x4B (Execute PCCC)
        cip_data.append(0x4B)

        # Request Path Size: 0x02 (2 words)
        cip_data.append(0x02)

        # Request Path: Class 0x67 (PCCC Class), Instance 0x01
        cip_data.append(0x20)  # 8-bit Class
        cip_data.append(0x67)  # PCCC Class
        cip_data.append(0x24)  # 8-bit Instance
        cip_data.append(0x01)  # Instance 1

        # Requestor ID Length: 7 bytes
        cip_data.append(0x07)

        # Requestor ID - Port/Link + Serial + CMD
        cip_data.append(0x09)  # Port 1
        cip_data.append(0x10)  # Link 0 (backplane)
        cip_data += struct.pack('<I', self.serial_number)  # 4-byte serial
        cip_data.append(self.SLC_CMD_CODE)  # 0x0F (CMD goes in requestor ID!)

        # After requestor ID: TNS + padding + FNC + parameters
        cip_data += struct.pack('<H', tns)  # TNS (2 bytes, little-endian)
        cip_data.append(0x00)  # Padding/separator

        # FNC: Function code (0xAB for Protected Typed Logical Write)
        cip_data.append(self.SLC_FNC_WRITE)

        # Byte size to write (always 2 for integer/binary)
        byte_size = self.PCCC_DATA_SIZE[file_type]
        cip_data.append(byte_size)

        # File number
        cip_data.append(file_number)

        # File type
        cip_data.append(self.PCCC_DATA_TYPE[file_type][0])

        # Element number (2 bytes, little-endian)
        cip_data += struct.pack('<H', element)
        
        # Mask (2 bytes, little-endian) - comes BEFORE data!
        # 0xFFFF means "write all bits"
        cip_data += struct.pack('<H', 0xFFFF)
        
        # Data value (2 bytes, little-endian) - comes AFTER mask!
        # Handle signed integers for N7
        if file_type == "N7" and value < 0:
            value = value + 65536  # Convert to unsigned
        cip_data += struct.pack('<H', value & 0xFFFF)

        return bytes(cip_data)

    def send_rr_data_pccc(self, cip_data):
        """Send PCCC command via Send RR Data (unconnected messaging)"""
        try:
            packet = self.create_send_rr_data(cip_data)
            self.socket.send(packet)

            response = self.socket.recv(2048)
            if len(response) >= 24:
                return response
            return None

        except Exception as e:
            print(f"Communication error: {e}")
            return None

    def send_unit_data(self, cip_data):
        """Send via Send Unit Data (connected messaging)"""
        try:
            packet_data = bytearray()

            packet_data += struct.pack('<I', 0)
            packet_data += struct.pack('<H', 0)
            packet_data += struct.pack('<H', 2)

            packet_data += struct.pack('<H', 0xA1)
            packet_data += struct.pack('<H', 4)
            packet_data += struct.pack('<I', self.o_to_t_connection_id)

            data_with_seq = bytearray()
            data_with_seq += struct.pack('<H', self.conn_sequence)
            data_with_seq += cip_data

            self.conn_sequence = (self.conn_sequence + 1) % 65536

            packet_data += struct.pack('<H', 0xB1)
            packet_data += struct.pack('<H', len(data_with_seq))
            packet_data += data_with_seq

            header = bytearray(24)
            header[0:2] = struct.pack('<H', 0x0070)
            header[2:4] = struct.pack('<H', len(packet_data))
            header[4:8] = struct.pack('<I', self.session_handle)
            header[8:12] = struct.pack('<I', 0)
            header[12:20] = b'_wt32eth'
            header[20:24] = struct.pack('<I', 0)

            packet = header + packet_data

            print(f"Sending {len(packet)} bytes...")
            print(f"Full packet: {' '.join(f'{b:02x}' for b in packet[:80])}")
            self.socket.send(packet)

            print("Waiting for response (10 second timeout)...")
            old_timeout = self.socket.gettimeout()
            self.socket.settimeout(10.0)  # Longer timeout

            try:
                response = self.socket.recv(2048)  # Larger buffer
                self.socket.settimeout(old_timeout)

                if len(response) >= 24:
                    print(f"✓ Received {len(response)} bytes!")
                    hex_str = ' '.join(f'{b:02x}' for b in response[:80])
                    print(f"Response: {hex_str}")
                    return response
                else:
                    print(f"⚠ Received only {len(response)} bytes (too short)")
                    return None
            except socket.timeout:
                print("✗ Socket timeout - no response received")
                self.socket.settimeout(old_timeout)
                return None

        except Exception as e:
            print(f"Communication error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def parse_pccc_response(self, response):
        """Parse PCCC response from Send RR Data or Send Unit Data"""
        if not response or len(response) < 10:
            return None

        try:
            offset = 24  # Skip EIP header

            # Skip interface handle (4) + timeout (2)
            offset += 6

            # Item count
            item_count = struct.unpack('<H', response[offset:offset + 2])[0]
            offset += 2

            for _ in range(item_count):
                if offset + 4 > len(response):
                    return None

                item_type = struct.unpack('<H', response[offset:offset + 2])[0]
                item_length = struct.unpack('<H', response[offset + 2:offset + 4])[0]
                offset += 4

                # Look for data items (B1 for connected, B2 for unconnected)
                if item_type == 0xB1 or item_type == 0xB2:
                    # For connected (B1), skip connection sequence
                    if item_type == 0xB1:
                        offset += 2

                    # Service reply
                    service = response[offset]
                    offset += 1

                    # Reserved
                    offset += 1

                    # General status
                    status = response[offset]
                    offset += 1

                    if status != 0:
                        return None

                    # Extended status size
                    ext_status_size = response[offset]
                    offset += 1 + ext_status_size

                    # Now search for the PCCC CMD byte (0x4F) in the remaining data
                    # The requestor ID path and its size are variable, so just search for 0x4F
                    remaining_start = offset
                    while offset < len(response):
                        if response[offset] == 0x4F:
                            # Found PCCC reply command!
                            pccc_cmd = response[offset]
                            offset += 1

                            if offset + 3 > len(response):
                                print("Response too short after CMD")
                                return None

                            pccc_dst = response[offset]
                            pccc_src = response[offset + 1]
                            pccc_sts = response[offset + 2]
                            offset += 3

                            if pccc_sts != 0:
                                return None

                            # Data follows immediately
                            if offset < len(response):
                                return response[offset:]
                            return None
                        offset += 1

                    return None

                offset += item_length

            return None
        except Exception as e:
            return None

    def read_tag(self, file_type, element_number, bit_number=None, element_count=1):
        """Read PLC tag"""
        if not self.connected:
            print("Not connected to PLC")
            return None

        try:
            file_numbers = {"N7": 7, "B3": 3, "F8": 8, "T4": 4, "C5": 5}
            file_number = file_numbers.get(file_type, 0)

            pccc_cmd = self.create_pccc_command(
                file_type, file_number, element_number, element_count
            )

            # Try UNCONNECTED messaging first (MicroLogix may prefer this for PCCC)
            response = self.send_rr_data_pccc(pccc_cmd)

            if response:
                data = self.parse_pccc_response(response)

                if data and len(data) >= 2:
                    value = struct.unpack('<H', data[0:2])[0]

                    if bit_number is not None:
                        bit_value = (value >> bit_number) & 1
                        print(f"{file_type}:{element_number}/{bit_number} = {bit_value}")
                        return bit_value
                    else:
                        if file_type == "B3":
                            print(f"{file_type}:{element_number} = {value:016b} (0x{value:04X})")
                        else:
                            if file_type == "N7" and value > 32767:
                                value = value - 65536
                            print(f"{file_type}:{element_number} = {value}")
                        return value

            print(f"Failed to read {file_type}:{element_number}")
            return None
        except Exception as e:
            print(f"Error reading {file_type}:{element_number} - {e}")
            import traceback
            traceback.print_exc()
            return None

    def write_tag(self, file_type, element_number, value, bit_number=None):
        """Write PLC tag"""
        if not self.connected:
            print("Not connected to PLC")
            return False

        try:
            file_numbers = {"N7": 7, "B3": 3, "F8": 8, "T4": 4, "C5": 5}
            file_number = file_numbers.get(file_type, 0)

            # If writing a bit, read the current value first, modify the bit, then write back
            if bit_number is not None:
                # Read current value
                current_value = self.read_tag(file_type, element_number)
                if current_value is None:
                    print(f"Failed to read current value for bit write")
                    return False
                
                # Modify the specific bit
                if value:
                    # Set bit to 1
                    new_value = current_value | (1 << bit_number)
                else:
                    # Set bit to 0
                    new_value = current_value & ~(1 << bit_number)
                
                write_value = new_value
            else:
                write_value = value

            # Create write command
            pccc_cmd = self.create_pccc_write_command(
                file_type, file_number, element_number, write_value
            )

            # Send via unconnected messaging
            response = self.send_rr_data_pccc(pccc_cmd)

            if response:
                data = self.parse_pccc_response(response)
                
                # Write response has no data, just success/fail status
                # If we got here without error, write was successful
                if bit_number is not None:
                    print(f"Write successful: {file_type}:{element_number}/{bit_number} = {value}")
                else:
                    print(f"Write successful: {file_type}:{element_number} = {write_value}")
                return True

            print(f"Failed to write {file_type}:{element_number}")
            return False
        except Exception as e:
            print(f"Error writing {file_type}:{element_number} - {e}")
            import traceback
            traceback.print_exc()
            return False


# Export the main class
__all__ = ['SLCComm']
