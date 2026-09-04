import subprocess
import platform
import socket
import re
import cv2
import asyncio
from typing import List, Dict, Any

class DiscoveryService:
    """Service to discover local (V4L2) and network (ONVIF) cameras."""

    @staticmethod
    def _get_macos_camera_names() -> List[str]:
        """Get camera names on macOS via system_profiler."""
        names = []
        try:
            result = subprocess.run(
                ['system_profiler', 'SPCameraDataType'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    # Camera names appear as top-level entries ending with ':'
                    # e.g. "FaceTime HD Camera (Built-in):"
                    if line.endswith(':') and not line.startswith('Camera') and 'SPCamera' not in line:
                        names.append(line.rstrip(':').strip())
        except Exception:
            pass
        return names

    @staticmethod
    def _discover_v4l2(devices: List[Dict[str, Any]]) -> None:
        """Try Linux v4l2-ctl discovery."""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '--list-devices'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                sections = result.stdout.strip().split('\n\n')
                for section in sections:
                    lines = section.split('\n')
                    if not lines:
                        continue
                    label = lines[0].strip().rstrip(':')
                    for line in lines[1:]:
                        if '/dev/video' in line:
                            dev_path = line.strip().split(' ')[0]
                            cap = cv2.VideoCapture(dev_path)
                            if cap.isOpened():
                                ret, _ = cap.read()
                                cap.release()
                                if ret:
                                    devices.append({
                                        "name": label,
                                        "type": "v4l2",
                                        "url": dev_path,
                                        "id": dev_path
                                    })
                                    break
        except FileNotFoundError:
            pass  # v4l2-ctl not installed (e.g. macOS) — handled by fallback
        except Exception as e:
            print(f"[Discovery] v4l2-ctl error: {e}")

    @staticmethod
    async def discover_local_devices() -> List[Dict[str, Any]]:
        """Discover local video devices (USB webcams, CSI cameras, built-in cameras)."""
        devices: List[Dict[str, Any]] = []

        # Step 1: On Linux, try v4l2-ctl for labeled device info
        if platform.system() == 'Linux':
            DiscoveryService._discover_v4l2(devices)

        # Step 2: If v4l2-ctl didn't find anything, probe with OpenCV indices
        # This works on all platforms (macOS AVFoundation, Linux V4L2, Windows MSMF)
        if not devices:
            # On macOS, get friendly camera names
            mac_names = []
            if platform.system() == 'Darwin':
                mac_names = DiscoveryService._get_macos_camera_names()

            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    if ret:
                        name = mac_names[len(devices)] if len(devices) < len(mac_names) else f"Camera {i}"
                        devices.append({
                            "name": name,
                            "type": "local",
                            "url": str(i),
                            "id": f"local:{i}"
                        })
                else:
                    cap.release()

        return devices

    @staticmethod
    async def discover_onvif_devices() -> List[Dict[str, Any]]:
        """
        Discover ONVIF cameras using WS-Discovery probe.
        Standard multicast address: 239.255.255.250:3702
        """
        devices = []
        # WS-Discovery Probe Message
        PROBE_MSG = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<Envelope xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
            'xmlns:dn="http://www.onvif.org/ver10/network/wsdl" '
            'xmlns="http://www.w3.org/2003/05/soap-envelope">'
            '<Header>'
            '<wsa:MessageID xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
            'uuid:f505508a-23d2-436d-96a8-a006c0993092'
            '</wsa:MessageID>'
            '<wsa:To xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
            'urn:schemas-xmlsoap-org:ws:2004:08:discovery'
            '</wsa:To>'
            '<wsa:Action xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
            'http://schemas.xmlsoap.org/ws/2004/08/discovery/Probe'
            '</wsa:Action>'
            '</Header>'
            '<Body>'
            '<Probe xmlns="http://schemas.xmlsoap.org/ws/2004/08/discovery">'
            '<Types>tds:Device</Types>'
            '</Probe>'
            '</Body>'
            '</Envelope>'
        ).encode('utf-8')

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            # Multicast address for WS-Discovery
            MCAST_GRP = '239.255.255.250'
            MCAST_PORT = 3702
            
            sock.sendto(PROBE_MSG, (MCAST_GRP, MCAST_PORT))
            
            # Collect responses
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 2.0:
                try:
                    data, addr = sock.recvfrom(4096)
                    xml = data.decode('utf-8')
                    
                    # Very simple extraction of XAddrs (the service URL)
                    xaddr_match = re.search(r'<[^>]*XAddrs[^>]*>([^<]+)</[^>]*XAddrs[^>]*>', xml)
                    if xaddr_match:
                        xaddr = xaddr_match.group(1).split(' ')[0] # Use first address
                        
                        # Try to find a name if possible
                        name_match = re.search(r'onvif://www.onvif.org/name/([^<\s]+)', xml)
                        name = name_match.group(1) if name_match else f"IP Camera ({addr[0]})"
                        
                        # Check if we already have this IP
                        if not any(d['id'] == addr[0] for d in devices):
                            devices.append({
                                "name": name,
                                "type": "onvif",
                                "url": xaddr,
                                "id": addr[0]
                            })
                except socket.timeout:
                    break
                except Exception as e:
                    print(f"Socket receive error: {e}")
                    break
            sock.close()
        except Exception as e:
            print(f"ONVIF Discovery error: {e}")
            
        return devices

    async def discover_all(self) -> List[Dict[str, Any]]:
        """Combine all discovery methods."""
        local_task = asyncio.create_task(self.discover_local_devices())
        onvif_task = asyncio.create_task(self.discover_onvif_devices())
        
        local_results, onvif_results = await asyncio.gather(local_task, onvif_task)
        return local_results + onvif_results

discovery_service = DiscoveryService()
