#!/bin/bash

# Script to build EmuBTHID executables using PyInstaller

echo "=== EmuBTHID Build Script ==="
echo ""

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Create build directory if it doesn't exist
mkdir -p dist

echo ""
echo "Building main_mouse_demo (Mouse HID Demo)..."
pyinstaller --onefile \
    --name=EmuBTHID-Mouse \
    --add-data="sdp_record_kbd.xml:." \
    --hidden-import=dbus \
    --hidden-import=dbus.mainloop.glib \
    --hidden-import=gi \
    --hidden-import=gi.repository.GLib \
    main_mouse_demo.py

echo ""
echo "Building main (Keyboard & Mouse HID with GUI)..."
pyinstaller --onefile \
    --name=EmuBTHID-Full \
    --add-data="sdp_record_kbd.xml:." \
    --add-data="keycode.txt:." \
    --hidden-import=dbus \
    --hidden-import=dbus.mainloop.glib \
    --hidden-import=gi \
    --hidden-import=gi.repository.GLib \
    --hidden-import=Xlib \
    --hidden-import=Xlib.display \
    --hidden-import=Xlib.X \
    --hidden-import=Xlib.Xutil \
    main.py

echo ""
echo "=== Build Complete! ==="
echo ""
echo "Executables created in 'dist/' directory:"
echo "  - EmuBTHID-Mouse  (Mouse demo only)"
echo "  - EmuBTHID-Full   (Full keyboard + mouse with GUI)"
echo ""
echo "To run on Linux Mint, the target system needs:"
echo "  - Python 3 runtime libraries (usually pre-installed)"
echo "  - BlueZ (Bluetooth stack) - sudo apt install bluez"
echo "  - D-Bus (usually pre-installed)"
echo "  - GTK/GLib (for gi.repository) - sudo apt install python3-gi"
echo ""
echo "Usage on target system:"
echo "  sudo ./dist/EmuBTHID-Mouse"
echo "  sudo ./dist/EmuBTHID-Full"
echo ""
