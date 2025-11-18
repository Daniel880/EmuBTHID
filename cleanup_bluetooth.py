#!/usr/bin/python3
"""
Helper script to unregister the Bluetooth HID profile
Run this if you get "UUID already registered" error
"""

import dbus
import sys

PROFILE_PATH = "/org/bluez/bthid_profile"

try:
    bus = dbus.SystemBus()
    bluez_obj = bus.get_object("org.bluez", "/org/bluez")
    manager = dbus.Interface(bluez_obj, "org.bluez.ProfileManager1")
    
    print(f"Attempting to unregister profile at {PROFILE_PATH}...")
    manager.UnregisterProfile(PROFILE_PATH)
    print("Successfully unregistered profile!")
    
except dbus.exceptions.DBusException as e:
    if "Does Not Exist" in str(e):
        print("Profile was not registered (which is fine)")
    else:
        print(f"Error: {e}")
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
