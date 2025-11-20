# EmuBTHID (Mouse Demo, Single Script)

`main.py` is a standalone Bluetooth HID mouse demo. It registers a BlueZ HID profile, auto-detects your controller MAC, waits for a connection (or reconnects to an already connected device), and then draws circles with the mouse. No extra files are required; the SDP record is embedded.

Based on https://github.com/Alkaid-Benetnash/EmuBTHID.

## Requirements
- Linux with BlueZ running (`bluetoothd`).
- Python 3 with the deps in `requirements.txt` (dbus-python, pycairo, PyGObject).
- Root/sudo to bind the HID L2CAP ports.

Install Ubuntu dep
```bash
sudo apt update && sudo apt install python3 python3-dbus python3-dbus python3-cairo python3-gi
```

## Quick Start
1) Ensure `bluetoothd` runs without the `input` plugin (e.g. `-P input`) so BlueZ allows custom HID. This will probably disables ability to use Bluetooth mouse and keyboard on the system. To change the service, create an override:  

```bash
sudo systemctl edit bluetooth
```

2) In the editor, add:

```bash
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd -P input
```

The file should look like this:

```bash
### Editing /etc/systemd/system/bluetooth.service.d/override.conf
### Anything between here and the comment below will become the contents of the drop-in file

[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd -P input

### Edits below this comment will be discarded

```

3) Reload and restart bluetooth service

```bash
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
```

4) Make sure the changes are applied succesfully. Run this command:
```bash
sudo systemctl status bluetooth
```

adn check if there is no errors and there is this line present:

```bash
/usr/libexec/bluetooth/bluetoothd -P input
```

5) Pair/connect from your target device. The script will print connection status.  

6) Run the demo as root:  
```bash
sudo python3 main.py
```  


7) It will immediately start the circle-drawing demo. Stop with `Ctrl+C`.

## After work revert changes of the bluetooth service:
```bash
sudo systemctl revert bluetooth
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
```



