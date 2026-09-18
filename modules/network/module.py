import socket

from core.module_base import BaseModule


def get_local_ip():
    """
    Real private IP of the active interface (Wi-Fi or Ethernet).

    socket.gethostbyname(hostname) does NOT work on Raspbian: by default
    /etc/hosts maps the hostname to 127.0.1.1, so it always returns
    loopback. This trick opens a UDP socket "towards" a public IP
    without sending any data: it just forces the OS to pick the real
    outbound interface, and we read the local IP assigned to it.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "no network"
    finally:
        s.close()


class Module(BaseModule):
    def tick(self, ctx):
        hostname = socket.gethostname()
        ip = get_local_ip()
        return hostname[:16], f"IP: {ip}"
