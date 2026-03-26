"""
GPU Acceleration Utility Module

Provides functions to detect and select the best available compute device
(CUDA, MPS, or CPU) for PyTorch/Ultralytics inference.
"""

import torch


def get_device() -> str:
    """
    Returns the best available device for inference.
    
    Priority:
    1. CUDA (NVIDIA GPU)
    2. MPS (Apple Silicon)
    3. CPU (fallback)
    
    Returns:
        str: Device string ('cuda', 'mps', or 'cpu')
    """
    if torch.cuda.is_available():
        return 'cuda'
    elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return 'mps'
    else:
        return 'cpu'


def get_gpu_info() -> dict:
    """
    Returns detailed information about the available compute device.
    
    Returns:
        dict: Device information including:
            - device: Device string ('cuda', 'mps', 'cpu')
            - name: Human-readable device name
            - available: Whether GPU acceleration is available
            - memory: GPU memory info (CUDA only)
    """
    device = get_device()
    
    info = {
        'device': device,
        'name': 'CPU',
        'available': device != 'cpu',
        'memory': None,
        'type': 'cpu'
    }
    
    if device == 'cuda':
        info['name'] = torch.cuda.get_device_name(0)
        info['type'] = 'nvidia'
        try:
            memory_total = torch.cuda.get_device_properties(0).total_memory
            memory_allocated = torch.cuda.memory_allocated(0)
            info['memory'] = {
                'total': memory_total,
                'total_gb': round(memory_total / (1024**3), 2),
                'allocated': memory_allocated,
                'allocated_gb': round(memory_allocated / (1024**3), 2)
            }
        except Exception:
            pass
    elif device == 'mps':
        info['name'] = 'Apple Silicon GPU'
        info['type'] = 'apple'
    
    return info


def is_gpu_available() -> bool:
    """Check if any GPU acceleration is available."""
    return get_device() != 'cpu'
