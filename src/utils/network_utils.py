"""
网络工具模块
"""
import socket


def get_local_ip():
    """
    获取本地局域网（内网）IP地址
    
    Returns:
        str: IP地址，失败时返回 '127.0.0.1'
    """
    def _is_private(ip: str) -> bool:
        # Private IPv4 ranges
        return ip.startswith('10.') or ip.startswith('192.168.') or (
            ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31
        )

    s = None
    try:
        # First attempt: UDP trick to let OS pick the outbound interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Use a well-known public IP (doesn't send packets) to choose interface
        s.connect(('8.8.8.8', 80))
        ip_address = s.getsockname()[0]
        # If the chosen IP is a private LAN address, return it
        if _is_private(ip_address):
            return ip_address
    except Exception:
        pass
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass

    # Second attempt: inspect host name addresses and pick a private one
    try:
        hostname = socket.gethostname()
        for res in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            candidate = str(res[4][0])
            if candidate and not candidate.startswith('127.') and _is_private(candidate):
                return candidate
    except Exception:
        pass

    # Fallback: try gethostbyname (may return an IP on some systems)
    try:
        candidate = socket.gethostbyname(socket.gethostname())
        if candidate and not candidate.startswith('127.') and _is_private(candidate):
            return candidate
    except Exception:
        pass

    # Final fallback: loopback
    return '127.0.0.1'
