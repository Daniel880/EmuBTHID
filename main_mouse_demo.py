#!/usr/bin/python3

import sys
import time
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

"""
Controller MAC will be detected automatically
"""
CONTROLLER_MAC = None  # Will be auto-detected

# Import the modified BluetoothHID service for mouse
from BluetoothHID_mouse import BluetoothHIDService

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
    service_record = open("sdp_record_kbd.xml").read()
    
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
