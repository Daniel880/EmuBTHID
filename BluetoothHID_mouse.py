import dbus
import dbus.service
import os
import socket
import time


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

    def __init__(self, service_record, MAC):
        self.P_CTRL = 0x0011
        self.P_INTR = 0x0013
        self.SELFMAC = MAC
        self.bus = dbus.SystemBus()
        self.manager = None
        self.ccontrol = None
        self.cinter = None
        
        # Try to cleanup any existing profile first
        self.cleanup_profile()
        
        bluez_obj = self.bus.get_object("org.bluez", "/org/bluez")
        self.manager = dbus.Interface(bluez_obj, "org.bluez.ProfileManager1")

        BluetoothHIDProfile(self.bus, self.PROFILE_PATH)
        opts = {
            "ServiceRecord": service_record,
            "Name": "BTMouseProfile",
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "Service": "MY BTHID MOUSE",
            "Role": "server"
        }

        sock_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        sock_control.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_inter = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        sock_inter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_control.bind((self.SELFMAC, self.P_CTRL))
        sock_inter.bind((self.SELFMAC, self.P_INTR))
        
        self.manager.RegisterProfile(self.PROFILE_PATH, "00001124-0000-1000-8000-00805f9b34fb", opts)
        print("Registered")
        
        sock_control.listen(1)
        sock_inter.listen(1)
        print(f"waiting for connection at controller {MAC}, please double check with the MAC in bluetoothctl")
        self.ccontrol, cinfo = sock_control.accept()
        print("Control channel connected to " + cinfo[self.HOST])
        self.cinter, cinfo = sock_inter.accept()
        print("Interrupt channel connected to " + cinfo[self.HOST])

    def send(self, bytes_buf):
        if self.cinter:
            self.cinter.send(bytes_buf)
            
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
            
    def cleanup(self):
        """Clean up connections and unregister profile"""
        try:
            if self.ccontrol:
                self.ccontrol.close()
            if self.cinter:
                self.cinter.close()
        except:
            pass
            
        self.cleanup_profile()
