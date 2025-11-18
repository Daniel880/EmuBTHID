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
            
    def cleanup(self):
        """Clean up connections and unregister profile"""
        try:
            if self.ccontrol:
                self.ccontrol.close()
            if self.cinter:
                self.cinter.close()
            if self.sock_control_listen:
                self.sock_control_listen.close()
            if self.sock_inter_listen:
                self.sock_inter_listen.close()
        except:
            pass
            
        self.cleanup_profile()
        self.connected = False
