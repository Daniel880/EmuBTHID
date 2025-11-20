#!/usr/bin/python3

import sys
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import os
import socket

"""
Controller MAC will be detected automatically
"""
CONTROLLER_MAC = None  # Will be auto-detected


# SDP record embedded so the script is fully self-contained
HID_SERVICE_RECORD = """<?xml version="1.0" encoding="UTF-8" ?>

<record>
    <attribute id="0x0001">
        <sequence>
            <uuid value="0x1124" />
        </sequence>
    </attribute>
    <attribute id="0x0004">
        <sequence>
            <sequence>
                <uuid value="0x0100" />
                <uint16 value="0x1011" />
            </sequence>
            <sequence>
                <uuid value="0x0011" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0005">
        <sequence>
            <uuid value="0x1002" />
        </sequence>
    </attribute>
    <attribute id="0x0006">
        <sequence>
            <uint16 value="0x656e" />
            <uint16 value="0x006a" />
            <uint16 value="0x0100" />
        </sequence>
    </attribute>
    <attribute id="0x0009">
        <sequence>
            <sequence>
                <uuid value="0x1124" />
                <uint16 value="0x0100" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x000d">
        <sequence>
            <sequence>
                <sequence>
                    <uuid value="0x0100" />
                    <uint16 value="0x1013" />
                </sequence>
                <sequence>
                    <uuid value="0x0011" />
                </sequence>
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0100">
        <text value="A Virtual Keyboard" />
    </attribute>
    <attribute id="0x0101">
        <text value="Keyboard > BT Keyboard" />
    </attribute>
    <attribute id="0x0102">
        <text value="Durgesh" />
    </attribute>
    <attribute id="0x0200">
        <uint16 value="0x0100" />
    </attribute>
    <attribute id="0x0201">
        <uint16 value="0x0111" />
    </attribute>
    <attribute id="0x0202">
        <uint8 value="0x40" />
    </attribute>
    <attribute id="0x0203">
        <uint8 value="0x00" />
    </attribute>
    <attribute id="0x0204">
        <boolean value="true" />
    </attribute>
    <attribute id="0x0205">
        <boolean value="true" />
    </attribute>
    <attribute id="0x0206">
        <sequence>
            <sequence>
                <uint8 value="0x22" />
                <text encoding="hex" value="05010906a101850175019508050719e029e715002501810295017508810395057501050819012905910295017503910395067508150026ff000507190029ff8100c0050c0901a1018503150025017501950b0a23020a21020ab10109b809b609cd09b509e209ea09e9093081029501750d8103c005010902a1010901a100850295037501050919012903150025018102950175058103750895020501093009311581257f46670c3699f36513550c8106c0c0" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0207">
        <sequence>
            <sequence>
                <uint16 value="0x0409" />
                <uint16 value="0x0100" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x020b">
        <uint16 value="0x0100" />
    </attribute>
    <attribute id="0x020c">
        <uint16 value="0x0c80" />
    </attribute>
    <attribute id="0x020d">
        <boolean value="false" />
    </attribute>
    <attribute id="0x020e">
        <boolean value="true" />
    </attribute>
    <attribute id="0x020f">
        <uint16 value="0x0640" />
    </attribute>
    <attribute id="0x0210">
        <uint16 value="0x0320" />
    </attribute>
</record>
"""


class BluetoothHIDProfile(dbus.service.Object):
    def __init__(self, bus, path):
        super(BluetoothHIDProfile, self).__init__(bus, path)
        self.fd = -1

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        raise NotImplementedError("Release")

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Cancel(self):
        raise NotImplementedError("Cancel")

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take()
        print("New Connection from (%s, %d)" % (path, self.fd))
        for k, v in properties.items():
            if k == "Version" or k == "Features":
                print("    %s = 0x%04x " % (k, v))
            else:
                print("    %s = %s" % (k, v))

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print("RequestDisconnection(%s)" % (path))

        if (self.fd > 0):
            os.close(self.fd)
            self.fd = -1


def error_handler(e):
    raise RuntimeError(str(e))


class BluetoothHIDService(object):
    PROFILE_PATH = "/org/bluez/bthid_profile_mouse"

    HOST = 0
    PORT = 1

    def __init__(self, service_record, MAC, remote_mac=None):
        self.P_CTRL = 0x0011
        self.P_INTR = 0x0013
        self.SELFMAC = MAC
        self.service_record = service_record
        self.remote_mac = remote_mac
        self.bus = dbus.SystemBus()
        self.manager = None
        self.ccontrol = None
        self.cinter = None
        self.connected = False
        self.sock_control_listen = None
        self.sock_inter_listen = None
        
        # Initial connection
        self._connect()
    
    def _connect(self):
        """Internal method to establish connection"""
        # Try to cleanup any existing profile first
        self.cleanup_profile()
        
        bluez_obj = self.bus.get_object("org.bluez", "/org/bluez")
        self.manager = dbus.Interface(bluez_obj, "org.bluez.ProfileManager1")

        BluetoothHIDProfile(self.bus, self.PROFILE_PATH)
        opts = {
            "ServiceRecord": self.service_record,
            "Name": "BTMouseProfile",
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "Service": "MY BTHID MOUSE",
            "Role": "server"
        }

        self.manager.RegisterProfile(self.PROFILE_PATH, "00001124-0000-1000-8000-00805f9b34fb", opts)
        print("Registered")

        # If remote_mac is provided, try to connect to existing device
        if self.remote_mac:
            print(f"Attempting to connect to existing device: {self.remote_mac}")
            try:
                sock_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
                sock_control.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock_inter = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
                sock_inter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                print(f"Connecting control channel to {self.remote_mac}:{self.P_CTRL}...")
                sock_control.connect((self.remote_mac, self.P_CTRL))
                print("Control channel connected!")
                
                print(f"Connecting interrupt channel to {self.remote_mac}:{self.P_INTR}...")
                sock_inter.connect((self.remote_mac, self.P_INTR))
                print("Interrupt channel connected!")
                
                self.ccontrol = sock_control
                self.cinter = sock_inter
                self.connected = True
                return
            except Exception as e:
                print(f"Failed to connect to existing device: {e}")
                print("Falling back to waiting for incoming connection...")
        
        # Fall back to waiting for incoming connection
        self.sock_control_listen = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sock_control_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_inter_listen = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sock_inter_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_control_listen.bind((self.SELFMAC, self.P_CTRL))
        self.sock_inter_listen.bind((self.SELFMAC, self.P_INTR))
        
        self.sock_control_listen.listen(1)
        self.sock_inter_listen.listen(1)
        print(f"Waiting for connection at controller {self.SELFMAC}...")
        self.ccontrol, cinfo = self.sock_control_listen.accept()
        print("Control channel connected to " + cinfo[self.HOST])
        self.remote_mac = cinfo[self.HOST]  # Save remote MAC for reconnection
        self.cinter, cinfo = self.sock_inter_listen.accept()
        print("Interrupt channel connected to " + cinfo[self.HOST])
        self.connected = True
    
    def reconnect(self, max_attempts=5, delay=2):
        """Attempt to reconnect after connection loss"""
        print(f"\n⚠️  Connection lost! Attempting to reconnect to {self.remote_mac}...")
        
        # Close existing connections
        try:
            if self.ccontrol:
                self.ccontrol.close()
            if self.cinter:
                self.cinter.close()
        except:
            pass
        
        self.connected = False
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Reconnection attempt {attempt}/{max_attempts}...")
                
                # Try to connect to the known remote device
                if self.remote_mac:
                    sock_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
                    sock_control.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock_inter = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
                    sock_inter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                    sock_control.connect((self.remote_mac, self.P_CTRL))
                    print("✓ Control channel reconnected!")
                    
                    sock_inter.connect((self.remote_mac, self.P_INTR))
                    print("✓ Interrupt channel reconnected!")
                    
                    self.ccontrol = sock_control
                    self.cinter = sock_inter
                    self.connected = True
                    print("✓ Reconnection successful!\n")
                    return True
                    
            except Exception as e:
                print(f"✗ Attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    print(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
        
        print(f"✗ Failed to reconnect after {max_attempts} attempts")
        return False

    def send(self, bytes_buf):
        if self.cinter and self.connected:
            try:
                self.cinter.send(bytes_buf)
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"\n⚠️  Send failed: {e}")
                self.connected = False
                raise  # Re-raise to let caller handle reconnection
            
    def cleanup_profile(self):
        """Unregister the profile if it exists"""
        try:
            bluez_obj = self.bus.get_object("org.bluez", "/org/bluez")
            manager = dbus.Interface(bluez_obj, "org.bluez.ProfileManager1")
            manager.UnregisterProfile(self.PROFILE_PATH)
            print(f"Cleaned up existing profile at {self.PROFILE_PATH}")
            time.sleep(0.5)  # Give it time to unregister
        except dbus.exceptions.DBusException as e:
            if "Does Not Exist" not in str(e):
                print(f"Note: {e}")
        except Exception as e:
            pass

class MouseEmulator:
    def __init__(self, bthid_service):
        self.bthid_service = bthid_service
        self.mouse_state = bytearray([
            0xA1,
            0x02,  # Report ID
            0x00,  # mouse button, in this byte XXXXX(button2)(button1)(button0)
            0x00,  # X displacement
            0x00,  # Y displacement
        ])
    
    def send_with_reconnect(self, data):
        """Send data with automatic reconnection on failure"""
        max_retries = 3
        for retry in range(max_retries):
            try:
                self.bthid_service.send(data)
                return True
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                if retry < max_retries - 1:
                    print(f"Attempting to reconnect (retry {retry + 1}/{max_retries})...")
                    if self.bthid_service.reconnect():
                        continue  # Try sending again
                    else:
                        print("Reconnection failed!")
                        return False
                else:
                    print("Max retries reached!")
                    return False
        return False
        
    def move_mouse(self, x_displacement, y_displacement):
        """
        Move mouse by specified displacement
        x_displacement: horizontal movement (-128 to 127, negative is left, positive is right)
        y_displacement: vertical movement (-128 to 127, negative is up, positive is down)
        """
        # Clamp values to valid range
        x_displacement = max(-128, min(x_displacement, 127))
        y_displacement = max(-128, min(y_displacement, 127))
        
        # Convert negative values to unsigned byte representation
        self.mouse_state[3] = x_displacement if x_displacement >= 0 else (256 + x_displacement)
        self.mouse_state[4] = y_displacement if y_displacement >= 0 else (256 + y_displacement)
        
        print(f"Moving mouse: X={x_displacement}, Y={y_displacement}")
        if not self.send_with_reconnect(bytes(self.mouse_state)):
            raise Exception("Failed to send mouse movement after reconnection attempts")
        
        # Reset to zero movement after sending
        self.mouse_state[3] = 0x00
        self.mouse_state[4] = 0x00
        
    def click(self, button=1):
        """
        Click a mouse button (1=left, 2=right, 3=middle)
        """
        # Press button
        self.mouse_state[2] |= 1 << (button - 1)
        if not self.send_with_reconnect(bytes(self.mouse_state)):
            raise Exception("Failed to send mouse click after reconnection attempts")
        time.sleep(0.05)  # Small delay
        
        # Release button
        self.mouse_state[2] &= ~(1 << (button - 1))
        if not self.send_with_reconnect(bytes(self.mouse_state)):
            raise Exception("Failed to send mouse release after reconnection attempts")
        
    def demo_movement(self):
        """
        Demo: Draw circles with the mouse continuously
        """
        import math
        
        print("\n=== Starting Infinite Circle Demo ===")
        print("Drawing circles continuously... Press Ctrl+C to stop")
        
        # Draw circles - 3x larger radius
        radius = 60  # 3x larger (was effectively 20)
        steps = 36   # Number of steps to complete the circle
        
        circle_num = 0
        try:
            while True:  # Infinite loop
                circle_num += 1
                print(f"Circle {circle_num}")
                for step in range(steps):
                    angle = (2 * math.pi * step) / steps
                    
                    # Calculate the next position
                    next_angle = (2 * math.pi * (step + 1)) / steps
                    
                    # Calculate displacement from current to next point
                    dx = int(radius * (math.cos(next_angle) - math.cos(angle)))
                    dy = int(radius * (math.sin(next_angle) - math.sin(angle)))
                    
                    self.move_mouse(dx, dy)
                    time.sleep(0.05)  # Small delay between movements
                
                # No pause between circles - continuous drawing
                
        except KeyboardInterrupt:
            print(f"\n=== Demo stopped after {circle_num} circles ===")
        
    def continuous_demo(self):
        """
        Continuously move mouse in a pattern every few seconds
        """
        print("\n=== Starting Continuous Mouse Demo ===")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                print("\nMoving RIGHT...")
                for i in range(3):
                    self.move_mouse(30, 0)
                    time.sleep(0.3)
                
                time.sleep(2)
                
                print("Moving LEFT...")
                for i in range(3):
                    self.move_mouse(-30, 0)
                    time.sleep(0.3)
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\nDemo stopped by user")


def get_controller_mac():
    """Get MAC address of the local Bluetooth adapter"""
    try:
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" in interfaces:
                adapter = interfaces["org.bluez.Adapter1"]
                mac = adapter.get("Address")
                name = adapter.get("Name", "Unknown")
                print(f"Found Bluetooth adapter: {name} ({mac})")
                return mac
        return None
    except Exception as e:
        print(f"Error finding Bluetooth adapter: {e}")
        return None


def get_connected_device_mac():
    """Get MAC address of connected Bluetooth device"""
    try:
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                device = interfaces["org.bluez.Device1"]
                if device.get("Connected", False):
                    mac = device.get("Address")
                    name = device.get("Name", "Unknown")
                    print(f"Found connected device: {name} ({mac})")
                    return mac
        return None
    except Exception as e:
        print(f"Error finding connected device: {e}")
        return None


def cleanup_profile():
    """Cleanup any existing Bluetooth profile registration"""
    import dbus
    PROFILE_PATH = "/org/bluez/bthid_profile_mouse"
    try:
        bus = dbus.SystemBus()
        bluez_obj = bus.get_object("org.bluez", "/org/bluez")
        manager = dbus.Interface(bluez_obj, "org.bluez.ProfileManager1")
        manager.UnregisterProfile(PROFILE_PATH)
        print("Cleaned up existing profile registration")
        time.sleep(0.5)
    except:
        pass  # Profile wasn't registered, which is fine


if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    service_record = HID_SERVICE_RECORD
    
    # Clean up any existing profile first
    cleanup_profile()
    
    bthid_srv = None
    try:
        print("Initializing Bluetooth HID Service...")
        
        # Auto-detect controller MAC if not specified
        controller_mac = CONTROLLER_MAC
        if not controller_mac:
            controller_mac = get_controller_mac()
            if not controller_mac:
                print("ERROR: Could not detect Bluetooth adapter MAC address!")
                sys.exit(1)
        
        # Try to find already connected device
        remote_mac = get_connected_device_mac()
        
        bthid_srv = BluetoothHIDService(service_record, controller_mac, remote_mac)
        
        print("\nBluetooth HID Service connected!")
        emulator = MouseEmulator(bthid_srv)
        
        # Run the demo
        emulator.demo_movement()
        
        # Uncomment the line below for continuous demo instead
        # emulator.continuous_demo()
        
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if bthid_srv:
            bthid_srv.cleanup()
        cleanup_profile()
        print("Exit")
