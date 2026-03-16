import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np

# We need the main app to use the TestClient
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

client = TestClient(app)

def test_camera_snapshot_success():
    """Test successful capture of a JPEG frame from a camera."""
    
    # Mock cv2.VideoCapture and cv2.imencode
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    
    # Create a dummy image frame (e.g. 10x10 blue square)
    dummy_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    dummy_frame[:] = (255, 0, 0) 
    mock_cap.read.return_value = (True, dummy_frame)
    
    # Dummy encoded byte array
    dummy_encoded = np.array([1, 2, 3, 4], dtype=np.uint8)

    with patch('cv2.VideoCapture', return_value=mock_cap) as mock_vc:
        with patch('cv2.imencode', return_value=(True, dummy_encoded)) as mock_imencode:
            # The source '0' should be interpreted as an integer index
            response = client.get("/api/cameras/snapshot?source=0")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.content == dummy_encoded.tobytes()
            
            # Verify VideoCapture was called with integer 0
            mock_vc.assert_called_once_with(0)
            mock_cap.read.assert_called_once()
            mock_cap.release.assert_called_once()
            mock_imencode.assert_called_once()

def test_camera_snapshot_camera_not_found():
    """Test behavior when the camera index/source cannot be opened."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    
    with patch('cv2.VideoCapture', return_value=mock_cap) as mock_vc:
        response = client.get("/api/cameras/snapshot?source=999")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Could not open camera"
        mock_vc.assert_called_once_with(999)

def test_camera_snapshot_read_fails():
    """Test behavior when the camera is opened but frame reading fails."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)
    
    with patch('cv2.VideoCapture', return_value=mock_cap) as mock_vc:
        response = client.get("/api/cameras/snapshot?source=0")
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to capture frame"
        mock_vc.assert_called_once_with(0)
        mock_cap.release.assert_called_once()
