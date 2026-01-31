"""
uPycomm - MicroPython Allen-Bradley PLC Communication Library
Version 28.0.0

A lightweight EtherNet/IP implementation for ESP32 microcontrollers
running MicroPython, specifically tested on WT32-ETH01.

Supports:
- SLC/MicroLogix (PCCC protocol): File-based addressing (N7, B3, etc.)
- CompactLogix/ControlLogix (CIP protocol): Tag-based addressing

Usage:
    # For MicroLogix (PCCC)
    from upycomm import SLC
    plc = SLC("192.168.1.10")
    if plc.connect():
        value = plc.read("N7", 0)
        plc.write("N7", 0, 100)
        plc.disconnect()
    
    # For CompactLogix (CIP)
    from upycomm import Logix
    plc = Logix("192.168.1.10")
    if plc.connect():
        value = plc.read("TagName")
        plc.write("TagName", 100)
        plc.disconnect()
"""

import socket
import time
import struct
import random

try:
    import machine
    import network
    from machine import Pin
    MACHINE_AVAILABLE = True
except ImportError:
    MACHINE_AVAILABLE = False
    machine = None
    network = None
    Pin = None


# ============================================================================
# SLC/MicroLogix Driver (PCCC Protocol)
# ============================================================================

class SLC:
    VERSION = "v28.0.0"  # FIXED: Mask before data in write command!

    def __init__(self, plc_ip, plc_port=44818, timeout=5):
        #print(f"SLC {self.VERSION}")
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

        # Get unique serial from hardware
        try:
            uid_bytes = machine.unique_id()
            # Convert first 4 bytes to unsigned 32-bit integer
            self.serial_number = struct.unpack('<I', uid_bytes[:4])[0]
        except Exception:
            self.serial_number = 0xAABBCCDD


    def connect(self):
        """Establish EtherNet/IP connection to PLC"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                #print("TCP_NODELAY enabled")
            except:
                #print("TCP_NODELAY not available")

            self.socket.settimeout(self.timeout)
            self.socket.connect((self.plc_ip, self.plc_port))

            if not self.register_session():
                #print("Failed to register session")
                return False

            try:
                self.list_identity()
            except:
                pass

            if not self.forward_open():
                #print("Failed to establish Forward Open connection")
                return False

            self.connected = True
            #print(f"Connected to PLC at {self.plc_ip}:{self.plc_port}")

            return True

        except Exception as e:
            #print(f"Failed to connect to PLC: {e}")
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
            #print("Disconnected from PLC")

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
                    #print(f"Session registered: 0x{self.session_handle:08X}")
                    return True

            return False
        except Exception as e:
            #print(f"Session registration failed: {e}")
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
                #print("PLC Identity received")
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
                            #print(f"Forward Open successful!")
                            #print(f"O->T Connection ID: 0x{self.o_to_t_connection_id:08X}")
                            #print(f"T->O Connection ID: 0x{self.t_to_o_connection_id:08X}")
                            return True
                        else:
                            #print(f"Forward Open failed with status: 0x{status:02X}")
                            return False

                    offset += item_length

            return False
        except Exception as e:
            #print(f"Forward Open failed: {e}")
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
            #print(f"Communication error: {e}")
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

            #print(f"Sending {len(packet)} bytes...")
            #print(f"Full packet: {' '.join(f'{b:02x}' for b in packet[:80])}")
            self.socket.send(packet)

            #print("Waiting for response (10 second timeout)...")
            old_timeout = self.socket.gettimeout()
            self.socket.settimeout(10.0)  # Longer timeout

            try:
                response = self.socket.recv(2048)  # Larger buffer
                self.socket.settimeout(old_timeout)

                if len(response) >= 24:
                    #print(f"✓ Received {len(response)} bytes!")
                    hex_str = ' '.join(f'{b:02x}' for b in response[:80])
                    #print(f"Response: {hex_str}")
                    return response
                else:
                    #print(f"⚠ Received only {len(response)} bytes (too short)")
                    return None
            except socket.timeout:
                #print("✗ Socket timeout - no response received")
                self.socket.settimeout(old_timeout)
                return None

        except Exception as e:
            #print(f"Communication error: {e}")
            import traceback
            traceback.#print_exc()
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
                                #print("Response too short after CMD")
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

    def read(self, file_type, element_number, bit_number=None, element_count=1):
        """Read PLC tag"""
        if not self.connected:
            #print("Not connected to PLC")
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
                        #print(f"{file_type}:{element_number}/{bit_number} = {bit_value}")
                        return bit_value
                    else:
                        if file_type == "B3":
                            #print(f"{file_type}:{element_number} = {value:016b} (0x{value:04X})")
                        else:
                            if file_type == "N7" and value > 32767:
                                value = value - 65536
                            #print(f"{file_type}:{element_number} = {value}")
                        return value

            #print(f"Failed to read {file_type}:{element_number}")
            return None
        except Exception as e:
            #print(f"Error reading {file_type}:{element_number} - {e}")
            import traceback
            traceback.#print_exc()
            return None

    def write(self, file_type, element_number, value, bit_number=None):
        """Write PLC tag"""
        if not self.connected:
            #print("Not connected to PLC")
            return False

        try:
            file_numbers = {"N7": 7, "B3": 3, "F8": 8, "T4": 4, "C5": 5}
            file_number = file_numbers.get(file_type, 0)

            # If writing a bit, read the current value first, modify the bit, then write back
            if bit_number is not None:
                # Read current value
                current_value = self.read_tag(file_type, element_number)
                if current_value is None:
                    #print(f"Failed to read current value for bit write")
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
                    #print(f"Write successful: {file_type}:{element_number}/{bit_number} = {value}")
                else:
                    #print(f"Write successful: {file_type}:{element_number} = {write_value}")
                return True

            #print(f"Failed to write {file_type}:{element_number}")
            return False
        except Exception as e:
            #print(f"Error writing {file_type}:{element_number} - {e}")
            import traceback
            traceback.#print_exc()
            return False


# Export the main class
__all__ = ['SLC']


# ============================================================================
# Logix Driver (CIP Protocol)  
# ============================================================================

class Logix:
    """Driver for Allen-Bradley Logix PLCs"""
    
    VERSION = "v28.0.0"  # Auto-detect type by reading tag first (default behavior)
    
    # CIP Data Type Codes (for reference and decode)
    DATA_TYPES = {
        0xC1: ('BOOL', 1),
        0xC2: ('SINT', 1),
        0xC3: ('INT', 2),
        0xC4: ('DINT', 4),
        0xCA: ('REAL', 4),
    }
    
    # CIP Data Type Constants (use these for write operations)
    CIP_BOOL = 0xC1   # Boolean (1 bit/byte)
    CIP_SINT = 0xC2   # Signed 8-bit integer
    CIP_INT = 0xC3    # Signed 16-bit integer
    CIP_DINT = 0xC4   # Signed 32-bit integer
    CIP_LINT = 0xC5   # Signed 64-bit integer
    CIP_USINT = 0xC6  # Unsigned 8-bit integer
    CIP_UINT = 0xC7   # Unsigned 16-bit integer
    CIP_UDINT = 0xC8  # Unsigned 32-bit integer
    CIP_ULINT = 0xC9  # Unsigned 64-bit integer
    CIP_REAL = 0xCA   # 32-bit floating point
    CIP_LREAL = 0xCB  # 64-bit floating point
    CIP_STRING = 0xD0 # String (not yet implemented)
    
    def __init__(self, plc_ip, plc_port=44818, timeout=5, slot=0, use_routing=False):
        """
        Initialize Logix driver
        
        Args:
            plc_ip: IP address of the PLC
            plc_port: EtherNet/IP port (default 44818)
            timeout: Socket timeout in seconds
            slot: PLC slot number in chassis (default 0)
            use_routing: Route through backplane/slot (True for ControlLogix, False for Micro800)
        """
        #print(f"Logix {self.VERSION}")
        self.plc_ip = plc_ip
        self.plc_port = plc_port
        self.timeout = timeout
        self.slot = slot
        self.use_routing = use_routing
        
        self.socket = None
        self.session_handle = 0
        self.connected = False
        self.context = b'_pycomm_'
        
        # Get unique serial from hardware
        try:
            uid_bytes = machine.unique_id()
            # Convert first 4 bytes to unsigned 32-bit integer
            self.originator_serial = struct.unpack('<I', uid_bytes[:4])[0]
        except Exception:
            self.originator_serial = 0xAABBCCDD
        
    def connect(self):
        """Establish connection to PLC"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            
            try:
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                #print("TCP_NODELAY enabled")
            except:
                pass
            
            #print(f"Connecting to {self.plc_ip}:{self.plc_port}...")
            self.socket.connect((self.plc_ip, self.plc_port))
            
            if not self.register_session():
                return False
            
            self.connected = True
            #print(f"Connected to PLC at {self.plc_ip}:{self.plc_port}")
            return True
            
        except Exception as e:
            #print(f"Connection failed: {e}")
            return False
    
    def register_session(self):
        """Register EtherNet/IP session"""
        try:
            packet = bytearray(28)
            packet[0:2] = struct.pack('<H', 0x0065)
            packet[2:4] = struct.pack('<H', 4)
            packet[4:8] = struct.pack('<I', 0)
            packet[8:12] = struct.pack('<I', 0)
            packet[12:20] = self.context
            packet[20:24] = struct.pack('<I', 0)
            packet[24:26] = struct.pack('<H', 1)
            packet[26:28] = struct.pack('<H', 0)
            
            self.socket.send(packet)
            response = self.socket.recv(1024)
            
            if len(response) >= 28:
                self.session_handle = struct.unpack('<I', response[4:8])[0]
                #print(f"Session registered: 0x{self.session_handle:08X}")
                return True
            
            return False
            
        except Exception as e:
            #print(f"Register session failed: {e}")
            return False
    
    def send_rr_data(self, cip_data):
        """Send unconnected message via SendRRData"""
        try:
            # Build CPF (Common Packet Format)
            cpf_data = bytearray()
            
            # Interface handle (4 bytes) - always 0 for CIP
            cpf_data += struct.pack('<I', 0)
            
            # Timeout (2 bytes) - always 0
            cpf_data += struct.pack('<H', 0)
            
            # Item count (2 items: null address + unconnected data)
            cpf_data += struct.pack('<H', 2)
            
            # Item 1: Null address item
            cpf_data += struct.pack('<H', 0x0000)  # Type: Null address
            cpf_data += struct.pack('<H', 0)  # Length: 0
            
            # Item 2: Unconnected data item
            cpf_data += struct.pack('<H', 0x00B2)  # Type: Unconnected data
            cpf_data += struct.pack('<H', len(cip_data))  # Length
            cpf_data += cip_data  # The actual CIP command
            
            # Build EtherNet/IP header
            header = bytearray(24)
            header[0:2] = struct.pack('<H', 0x006F)  # SendRRData command
            header[2:4] = struct.pack('<H', len(cpf_data))  # Length of CPF data
            header[4:8] = struct.pack('<I', self.session_handle)  # Session handle
            header[8:12] = struct.pack('<I', 0)  # Status (0 for request)
            header[12:20] = self.context  # Sender context
            header[20:24] = struct.pack('<I', 0)  # Options (always 0)
            
            packet = header + cpf_data
            self.socket.send(packet)
            
            response = self.socket.recv(2048)
            return response if len(response) > 24 else None
            
        except Exception as e:
            #print(f"SendRRData error: {e}")
            return None
    
    def build_tag_path(self, tag_name):
        """Build EPATH for tag name"""
        path = bytearray()
        
        # ANSI Extended Symbol Segment (0x91)
        tag_bytes = tag_name.encode('utf-8')
        path.append(0x91)
        path.append(len(tag_bytes))
        path += tag_bytes
        
        # Pad to word boundary
        if len(tag_bytes) % 2:
            path.append(0x00)
        
        return path
    
    def wrap_with_routing(self, cip_command):
        """
        Wrap CIP command with Unconnected Send for routing through backplane
        
        Args:
            cip_command: The raw CIP service request (e.g., Read Tag)
            
        Returns:
            Wrapped command ready to send
        """
        if not self.use_routing:
            # Direct access - no routing needed
            return cip_command
        
        # Build Unconnected Send wrapper
        wrapper = bytearray()
        wrapper.append(0x52)  # Unconnected Send service
        wrapper.append(0x02)  # Path size (2 words = 4 bytes)
        wrapper.append(0x20)  # Logical Segment: Class ID
        wrapper.append(0x06)  # Connection Manager class
        wrapper.append(0x24)  # Logical Segment: Instance ID
        wrapper.append(0x01)  # Instance 1
        
        # Priority/Time Tick
        wrapper.append(0x0A)
        
        # Timeout ticks
        wrapper.append(0x05)
        
        # Message request size
        wrapper += struct.pack('<H', len(cip_command))
        
        # The actual CIP command
        wrapper += cip_command
        
        # Route path - to backplane/slot
        wrapper.append(0x01)  # Route path size (1 word pair = 2 bytes)
        wrapper.append(0x00)  # Reserved
        wrapper.append(0x20)  # Port segment: Backplane
        wrapper.append(0x02)  # Port identifier: Backplane (1)
        wrapper.append(0x24)  # Slot segment
        wrapper.append(self.slot)  # Slot number
        
        return wrapper
    
    def read(self, tag_name, element_count=1):
        """Read a tag from the PLC"""
        if not self.connected:
            #print("Not connected to PLC")
            return None
        
        try:
            # Build Read Tag Service request
            cip_command = bytearray()
            cip_command.append(0x4C)  # Read Tag service
            
            # Build tag path
            tag_path = self.build_tag_path(tag_name)
            path_size = len(tag_path) // 2  # Size in words
            cip_command.append(path_size)
            cip_command += tag_path
            
            # Element count
            cip_command += struct.pack('<H', element_count)
            
            # Wrap with routing if needed (for ControlLogix in chassis)
            cip_data = self.wrap_with_routing(cip_command)
            
            #print(f"Reading tag '{tag_name}'...")
            if self.use_routing:
                #print(f"  Routing through backplane, slot {self.slot}")
            hex_data = ' '.join(f'{byte:02x}' for byte in cip_data[:32])
            #print(f"  CIP command: {hex_data}")
            
            # Send via unconnected messaging
            response = self.send_rr_data(cip_data)
            
            if response:
                #print(f"  Response: {len(response)} bytes")
                return self.parse_read_response(response)
            else:
                #print("  No response")
            
            return None
            
        except Exception as e:
            #print(f"Read error: {e}")
            import sys
            sys.#print_exception(e)
            return None
    
    def parse_read_response(self, response):
        """Parse Read Tag response"""
        try:
            # Skip EIP header (24 bytes) + interface handle (4) + timeout (2)
            offset = 30
            
            # Find B2 item (unconnected data)
            item_count = struct.unpack('<H', response[offset:offset+2])[0]
            offset += 2
            
            for _ in range(item_count):
                item_type = struct.unpack('<H', response[offset:offset+2])[0]
                item_length = struct.unpack('<H', response[offset+2:offset+4])[0]
                offset += 4
                
                if item_type == 0x00B2:  # Unconnected data
                    service_reply = response[offset]
                    status = response[offset + 2]
                    
                    #print(f"  Service: 0x{service_reply:02X}, Status: 0x{status:02X}")
                    
                    # Check if this is a routed response (Unconnected Send reply)
                    if service_reply == 0xD2:  # Unconnected Send reply
                        # Skip to embedded response
                        # Status is at offset+2, extended status size at offset+3
                        ext_status_size = response[offset + 3]
                        embedded_offset = offset + 4 + (ext_status_size * 2)
                        
                        # Now parse the embedded Read Tag reply
                        service_reply = response[embedded_offset]
                        status = response[embedded_offset + 2]
                        #print(f"  Embedded Service: 0x{service_reply:02X}, Status: 0x{status:02X}")
                        
                        if service_reply == 0xCC and status == 0:
                            data_type = struct.unpack('<H', response[embedded_offset + 4:embedded_offset + 6])[0]
                            data_offset = embedded_offset + 6
                            #print(f"  Data type: 0x{data_type:04X}")
                            value = self.decode_value(data_type, response[data_offset:])
                            return value
                    
                    # Direct response (no routing)
                    elif service_reply == 0xCC and status == 0:  # Read Tag reply, success
                        data_type = struct.unpack('<H', response[offset + 4:offset + 6])[0]
                        data_offset = offset + 6
                        
                        #print(f"  Data type: 0x{data_type:04X}")
                        
                        value = self.decode_value(data_type, response[data_offset:])
                        return value
                    else:
                        #print(f"  Read failed: Status 0x{status:02X}")
                        return None
                
                offset += item_length
            
            return None
            
        except Exception as e:
            #print(f"  Parse error: {e}")
            import sys
            sys.#print_exception(e)
            return None
    
    def decode_value(self, data_type, data):
        """Decode value based on CIP data type"""
        if data_type == 0xC1:  # BOOL
            return data[0] != 0
        elif data_type == 0xC2:  # SINT
            return struct.unpack('<b', data[0:1])[0]
        elif data_type == 0xC3:  # INT
            return struct.unpack('<h', data[0:2])[0]
        elif data_type == 0xC4:  # DINT
            return struct.unpack('<i', data[0:4])[0]
        elif data_type == 0xC7:  # UINT
            return struct.unpack('<H', data[0:2])[0]
        elif data_type == 0xC8:  # UDINT
            return struct.unpack('<I', data[0:4])[0]
        elif data_type == 0xCA:  # REAL
            return struct.unpack('<f', data[0:4])[0]
        else:
            #print(f"  Unknown data type: 0x{data_type:04X}")
            return None
    
    def write(self, tag_name, value, data_type=None, auto_detect=True):
        """
        Write a tag to the PLC
        
        Args:
            tag_name: Name of the tag
            value: Value to write
            data_type: Force specific CIP type (optional) - can be:
                      - String: 'INT', 'DINT', 'REAL', 'BOOL', etc.
                      - Constant: Logix.CIP_INT, Logix.CIP_DINT, etc.
                      - Hex code: 0xC3, 0xC4, 0xCA, etc.
            auto_detect: If True and data_type is None, read tag first to get type (default True)
        
        Returns:
            bool: True if successful
            
        Examples:
            plc.write("Counter", 1000)                    # Auto-detect type by reading
            plc.write("Setpoint", 75.5)                   # Auto-detect type by reading
            plc.write("MyINT", 500, 'INT')                # Explicit type (no read needed)
            plc.write("MyINT", 500, auto_detect=False)    # Skip read, use default DINT
        """
        if not self.connected:
            #print("Not connected to PLC")
            return False
        
        try:
            # Auto-detect type by reading if not specified
            if data_type is None and auto_detect:
                #print(f"Auto-detecting type for '{tag_name}'...")
                detected_type = self._read_tag_type(tag_name)
                if detected_type is not None:
                    type_name = {0xC1: 'BOOL', 0xC2: 'SINT', 0xC3: 'INT', 0xC4: 'DINT',
                                0xC5: 'LINT', 0xC6: 'USINT', 0xC7: 'UINT', 0xC8: 'UDINT',
                                0xC9: 'ULINT', 0xCA: 'REAL', 0xCB: 'LREAL'}.get(detected_type, f'0x{detected_type:02X}')
                    #print(f"  Detected type: {type_name}")
                    data_type = detected_type
                else:
                    #print(f"  Could not detect type, using default")
            
            # Build Write Tag Service request
            cip_command = bytearray()
            cip_command.append(0x4D)  # Write Tag service
            
            # Build tag path
            tag_path = self.build_tag_path(tag_name)
            path_size = len(tag_path) // 2
            cip_command.append(path_size)
            cip_command += tag_path
            
            # Encode value and get data type
            encoded_data, auto_type = self.encode_value(value, force_type=data_type)
            
            # Data type
            cip_command += struct.pack('<H', auto_type)
            
            # Element count (always 1 for now)
            cip_command += struct.pack('<H', 1)
            
            # Data
            cip_command += encoded_data
            
            # Wrap with routing if needed
            cip_data = self.wrap_with_routing(cip_command)
            
            type_name = {0xC1: 'BOOL', 0xC2: 'SINT', 0xC3: 'INT', 0xC4: 'DINT', 
                        0xC7: 'UINT', 0xC8: 'UDINT', 0xCA: 'REAL'}.get(auto_type, f'0x{auto_type:02X}')
            #print(f"Writing '{tag_name}' = {value} (as {type_name})...")
            if self.use_routing:
                #print(f"  Routing through backplane, slot {self.slot}")
            hex_data = ' '.join(f'{byte:02x}' for byte in cip_data[:32])
            #print(f"  CIP command: {hex_data}")
            
            # Send via unconnected messaging
            response = self.send_rr_data(cip_data)
            
            if response:
                #print(f"  Response: {len(response)} bytes")
                return self.parse_write_response(response)
            else:
                #print("  No response")
                return False
            
        except Exception as e:
            #print(f"Write error: {e}")
            import sys
            sys.#print_exception(e)
            return False
    
    def _read_tag_type(self, tag_name):
        """
        Read a tag to determine its data type (internal helper)
        
        Args:
            tag_name: Name of the tag
            
        Returns:
            CIP data type code or None if failed
        """
        try:
            # Build Read Tag Service request
            cip_command = bytearray()
            cip_command.append(0x4C)  # Read Tag service
            
            # Build tag path
            tag_path = self.build_tag_path(tag_name)
            path_size = len(tag_path) // 2
            cip_command.append(path_size)
            cip_command += tag_path
            
            # Element count (just 1 to minimize data transfer)
            cip_command += struct.pack('<H', 1)
            
            # Wrap with routing if needed
            cip_data = self.wrap_with_routing(cip_command)
            
            # Send via unconnected messaging
            response = self.send_rr_data(cip_data)
            
            if response:
                # Parse response to extract data type
                offset = 30  # Skip EIP header + interface + timeout
                item_count = struct.unpack('<H', response[offset:offset+2])[0]
                offset += 2
                
                for _ in range(item_count):
                    item_type = struct.unpack('<H', response[offset:offset+2])[0]
                    item_length = struct.unpack('<H', response[offset+2:offset+4])[0]
                    offset += 4
                    
                    if item_type == 0x00B2:  # Unconnected data
                        service_reply = response[offset]
                        status = response[offset + 2]
                        
                        # Check for routed response
                        if service_reply == 0xD2:  # Unconnected Send reply
                            ext_status_size = response[offset + 3]
                            embedded_offset = offset + 4 + (ext_status_size * 2)
                            service_reply = response[embedded_offset]
                            status = response[embedded_offset + 2]
                            
                            if service_reply == 0xCC and status == 0:
                                data_type = struct.unpack('<H', response[embedded_offset + 4:embedded_offset + 6])[0]
                                return data_type
                        
                        # Direct response
                        elif service_reply == 0xCC and status == 0:
                            data_type = struct.unpack('<H', response[offset + 4:offset + 6])[0]
                            return data_type
                    
                    offset += item_length
            
            return None
            
        except Exception as e:
            #print(f"  Type detection error: {e}")
            return None
    
    def encode_value(self, value, force_type=None):
        """
        Encode value and determine data type
        
        Args:
            value: Value to encode
            force_type: Force specific CIP type - can be:
                       - Integer code (0xC3, 0xC4, etc.)
                       - String name ('INT', 'DINT', 'BOOL', etc.)
                       - Class constant (Logix.CIP_INT, etc.)
        
        Returns:
            tuple: (encoded_bytes, data_type_code)
        """
        # Convert string type names to codes
        if isinstance(force_type, str):
            type_map = {
                'BOOL': self.CIP_BOOL,
                'SINT': self.CIP_SINT,
                'INT': self.CIP_INT,
                'DINT': self.CIP_DINT,
                'LINT': self.CIP_LINT,
                'USINT': self.CIP_USINT,
                'UINT': self.CIP_UINT,
                'UDINT': self.CIP_UDINT,
                'ULINT': self.CIP_ULINT,
                'REAL': self.CIP_REAL,
                'LREAL': self.CIP_LREAL,
            }
            force_type = type_map.get(force_type.upper())
            if force_type is None:
                raise ValueError(f"Unknown type name. Use: {', '.join(type_map.keys())}")
        
        if force_type is not None:
            # User specified exact type
            if force_type == 0xC1:  # BOOL
                return struct.pack('<B', 1 if value else 0), 0xC1
            elif force_type == 0xC2:  # SINT
                return struct.pack('<b', value), 0xC2
            elif force_type == 0xC3:  # INT
                return struct.pack('<h', value), 0xC3
            elif force_type == 0xC4:  # DINT
                return struct.pack('<i', value), 0xC4
            elif force_type == 0xC5:  # LINT
                return struct.pack('<q', value), 0xC5
            elif force_type == 0xC6:  # USINT
                return struct.pack('<B', value), 0xC6
            elif force_type == 0xC7:  # UINT
                return struct.pack('<H', value), 0xC7
            elif force_type == 0xC8:  # UDINT
                return struct.pack('<I', value), 0xC8
            elif force_type == 0xC9:  # ULINT
                return struct.pack('<Q', value), 0xC9
            elif force_type == 0xCA:  # REAL
                return struct.pack('<f', value), 0xCA
            elif force_type == 0xCB:  # LREAL
                return struct.pack('<d', value), 0xCB
            else:
                raise ValueError(f"Unsupported type code: 0x{force_type:02X}")
        
        # Auto-detect type
        if isinstance(value, bool):
            return struct.pack('<B', 1 if value else 0), 0xC1  # BOOL
        elif isinstance(value, int):
            # Default to DINT for integers (safer for most PLCs)
            # This avoids type mismatch errors
            if -2147483648 <= value <= 2147483647:
                return struct.pack('<i', value), 0xC4  # DINT
            else:
                raise ValueError(f"Integer {value} out of DINT range")
        elif isinstance(value, float):
            return struct.pack('<f', value), 0xCA  # REAL
        else:
            raise ValueError(f"Unsupported type: {type(value)}")
    
    def parse_write_response(self, response):
        """Parse Write Tag response"""
        try:
            # Skip EIP header (24 bytes) + interface handle (4) + timeout (2)
            offset = 30
            
            # Find B2 item (unconnected data)
            item_count = struct.unpack('<H', response[offset:offset+2])[0]
            offset += 2
            
            for _ in range(item_count):
                item_type = struct.unpack('<H', response[offset:offset+2])[0]
                item_length = struct.unpack('<H', response[offset+2:offset+4])[0]
                offset += 4
                
                if item_type == 0x00B2:  # Unconnected data
                    service_reply = response[offset]
                    status = response[offset + 2]
                    
                    #print(f"  Service: 0x{service_reply:02X}, Status: 0x{status:02X}")
                    
                    # Check if this is a routed response (Unconnected Send reply)
                    if service_reply == 0xD2:  # Unconnected Send reply
                        # Skip to embedded response
                        ext_status_size = response[offset + 3]
                        embedded_offset = offset + 4 + (ext_status_size * 2)
                        
                        # Now parse the embedded Write Tag reply
                        service_reply = response[embedded_offset]
                        status = response[embedded_offset + 2]
                        #print(f"  Embedded Service: 0x{service_reply:02X}, Status: 0x{status:02X}")
                        
                        if service_reply == 0xCD and status == 0:
                            #print("  Write successful!")
                            return True
                        else:
                            #print(f"  Write failed: Status 0x{status:02X}")
                            return False
                    
                    # Direct response (no routing)
                    elif service_reply == 0xCD and status == 0:  # Write Tag reply, success
                        #print("  Write successful!")
                        return True
                    else:
                        #print(f"  Write failed: Status 0x{status:02X}")
                        return False
                
                offset += item_length
            
            return False
            
        except Exception as e:
            #print(f"  Parse error: {e}")
            import sys
            sys.#print_exception(e)
            return False
    
    def disconnect(self):
        """Close connection"""
        try:
            if self.socket:
                # Unregister session
                packet = bytearray(24)
                packet[0:2] = struct.pack('<H', 0x0066)
                packet[2:4] = struct.pack('<H', 0)
                packet[4:8] = struct.pack('<I', self.session_handle)
                self.socket.send(packet)
                
                self.socket.close()
                self.socket = None
                
            self.connected = False
            #print("Disconnected")
            
        except:
            pass




# Export classes and constants
__all__ = [
    'SLC',
    'Logix',
    # CIP Type Constants (for Logix)
    'CIP_BOOL',
    'CIP_SINT',
    'CIP_INT',
    'CIP_DINT',
    'CIP_LINT',
    'CIP_USINT',
    'CIP_UINT',
    'CIP_UDINT',
    'CIP_ULINT',
    'CIP_REAL',
    'CIP_LREAL',
]

# Make Logix constants available at module level
CIP_BOOL = Logix.CIP_BOOL
CIP_SINT = Logix.CIP_SINT
CIP_INT = Logix.CIP_INT
CIP_DINT = Logix.CIP_DINT
CIP_LINT = Logix.CIP_LINT
CIP_USINT = Logix.CIP_USINT
CIP_UINT = Logix.CIP_UINT
CIP_UDINT = Logix.CIP_UDINT
CIP_ULINT = Logix.CIP_ULINT
CIP_REAL = Logix.CIP_REAL
CIP_LREAL = Logix.CIP_LREAL
