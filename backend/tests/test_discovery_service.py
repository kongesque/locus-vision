import pytest
from unittest.mock import MagicMock, patch
from services.discovery_service import DiscoveryService

@pytest.mark.asyncio
async def test_v4l2_discovery_mock():
    # Mock subprocess for v4l2-ctl
    mock_stdout = "Dummy Camera (usb-123):\n\t/dev/video0\n\t/dev/video1\n\n"
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout)
        
        # Mock cv2.VideoCapture
        with patch('cv2.VideoCapture') as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, None)
            mock_vc.return_value = mock_cap
            
            discovery = DiscoveryService()
            results = await discovery.discover_v4l2_devices()
            
            assert len(results) == 1
            assert results[0]['name'] == 'Dummy Camera (usb-123)'
            assert results[0]['url'] == '/dev/video0'

@pytest.mark.asyncio
async def test_onvif_discovery_mock():
    # Mock socket for ONVIF discovery
    with patch('socket.socket') as mock_socket:
        mock_sock_inst = MagicMock()
        mock_socket.return_value = mock_sock_inst
        
        # Simulate a WS-Discovery response
        xml_response = """
        <Envelope xmlns="http://www.w3.org/2003/05/soap-envelope">
            <Body>
                <ProbeMatches>
                    <ProbeMatch>
                        <XAddrs>http://192.168.1.100:80/onvif/device_service</XAddrs>
                        <Types>dn:NetworkVideoTransmitter</Types>
                        <Scopes>onvif://www.onvif.org/name/Test_Camera</Scopes>
                    </ProbeMatch>
                </ProbeMatches>
            </Body>
        </Envelope>
        """
        mock_sock_inst.recvfrom.return_value = (xml_response.encode('utf-8'), ('192.168.1.100', 3702))
        
        discovery = DiscoveryService()
        results = await discovery.discover_onvif_devices()
        
        assert len(results) == 1
        assert results[0]['name'] == 'Test_Camera'
        assert results[0]['id'] == '192.168.1.100'
