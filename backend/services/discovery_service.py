import subprocess
import socket
import re
import cv2
import asyncio
from typing import List, Dict, Any

class DiscoveryService:
    """Service to discover local (V4L2) and network (ONVIF) cameras."""

    @staticmethod
    async def discover_v4l2_devices() -> List[Dict[str, Any]]:
        """Discover local video devices (USB webcams, CSI cameras)."""
        devices = []
        try:
            # Try using v4l2-ctl for better labels
            result = subprocess.run(
                ['v4l2-ctl', '--list-devices'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                sections = result.stdout.strip().split('\n\n')
                for section in sections:
                    lines = section.split('\n')
                    if not lines:
                        continue
                    
                    label = lines[0].strip()
                    # Example section:
                    # USB Camera: USB Camera (usb-0000:00:14.0-1):
                    #         /dev/video0
                    #         /dev/video1
                    
                    # Find all /dev/video* devices in this section
                    for line in lines[1:]:
                        if '/dev/video' in line:
                            dev_path = line.strip().split(' ')[0]
                            # Only include the primary device (usually the even number)
                            # or just include it if it's the first one we find for this label
                            # To be safe and simple, we'll try to open it with OpenCV
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
                                    break # Usually first one is the video stream
            
            # Fallback specifically for Pi if v4l2-ctl failed or returned nothing
            if not devices:
                for i in range(10):
                    dev_path = f"/dev/video{i}"
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        cap.release()
                        if ret:
                            devices.append({
                                "name": f"Local Camera {i}",
                                "type": "v4l2",
                                "url": dev_path,
                                "id": dev_path
                            })
        except Exception as e:
            print(f"V4L2 Discovery error: {e}")
            
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
        v4l2_task = asyncio.create_task(self.discover_v4l2_devices())
        onvif_task = asyncio.create_task(self.discover_onvif_devices())
        
        v4l2_results, onvif_results = await asyncio.gather(v4l2_task, onvif_task)
        return v4l2_results + onvif_results

discovery_service = DiscoveryService()
