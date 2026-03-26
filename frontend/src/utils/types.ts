// Job/Task types
export interface Job {
  id: string;
  name: string;
  filename: string;
  videoPath: string;
  framePath: string;
  frameWidth: number;
  frameHeight: number;
  status: "pending" | "processing" | "completed" | "error";
  progress: number;
  zones: Zone[];
  confidence: number;
  model: string;
  trackerConfig: TrackerConfig;
  detectionData: DetectionEvent[];
  dwellData: DwellEvent[];
  lineCrossingData: Record<string, LineCrossing>;
  heatmapData: number[][] | null;  // 2D grid for activity heatmap
  processTime: number;
  sourceType: "file" | "rtsp" | "webcam";
  streamUrl?: string;
  createdAt: string;
}

// Zone types
export interface Point {
  x: number;
  y: number;
}

export interface Zone {
  id: string;
  points: Point[];
  classIds: number[]; // Array of COCO class IDs for multi-class detection
  color: [number, number, number]; // RGB
  label: string;
}

// Tracker configuration
export interface TrackerConfig {
  track_high_thresh: number;
  track_low_thresh: number;
  match_thresh: number;
  track_buffer: number;
}

// Detection events
export interface DetectionEvent {
  time: number;
  zone_id: string;
  class_id: number;
  class_counts?: Record<number, number>;
  count: number;
  in_count?: number;
  out_count?: number;
  direction?: "in" | "out";
}

// Dwell time tracking
export interface DwellEvent {
  zone_id: string;
  track_id: number;
  entry_time: number;
  exit_time: number;
  duration: number;
}

// Line crossing data
export interface LineCrossing {
  in: number;
  out: number;
}

// GPU/System info
export interface SystemInfo {
  gpu: {
    available: boolean;
    name: string;
  };
  version: string;
}

// API response types
export interface ProgressResponse {
  progress: number;
  status: string;
}

export interface UploadResponse {
  taskId: string;
  success: boolean;
}

// COCO classes (subset of common ones)
export const COCO_CLASSES: Record<number, string> = {
  0: "person",
  1: "bicycle",
  2: "car",
  3: "motorcycle",
  4: "airplane",
  5: "bus",
  6: "train",
  7: "truck",
  8: "boat",
  9: "traffic light",
  10: "fire hydrant",
  11: "stop sign",
  12: "parking meter",
  13: "bench",
  14: "bird",
  15: "cat",
  16: "dog",
  17: "horse",
  18: "sheep",
  19: "cow",
  20: "elephant",
  21: "bear",
  22: "zebra",
  23: "giraffe",
  24: "backpack",
  25: "umbrella",
  26: "handbag",
  27: "tie",
  28: "suitcase",
  29: "frisbee",
  30: "skis",
  31: "snowboard",
  32: "sports ball",
  33: "kite",
  34: "baseball bat",
  35: "baseball glove",
  36: "skateboard",
  37: "surfboard",
  38: "tennis racket",
  39: "bottle",
  40: "wine glass",
  41: "cup",
  42: "fork",
  43: "knife",
  44: "spoon",
  45: "bowl",
  46: "banana",
  47: "apple",
  48: "sandwich",
  49: "orange",
  50: "broccoli",
  51: "carrot",
  52: "hot dog",
  53: "pizza",
  54: "donut",
  55: "cake",
  56: "chair",
  57: "couch",
  58: "potted plant",
  59: "bed",
  60: "dining table",
  61: "toilet",
  62: "tv",
  63: "laptop",
  64: "mouse",
  65: "remote",
  66: "keyboard",
  67: "cell phone",
  68: "microwave",
  69: "oven",
  70: "toaster",
  71: "sink",
  72: "refrigerator",
  73: "book",
  74: "clock",
  75: "vase",
  76: "scissors",
  77: "teddy bear",
  78: "hair drier",
  79: "toothbrush",
};

// Model options
export const MODEL_OPTIONS = [
  { value: "yolo11n.pt", label: "YOLO11 Nano (Fastest)" },
  { value: "yolo11s.pt", label: "YOLO11 Small" },
  { value: "yolo11m.pt", label: "YOLO11 Medium" },
  { value: "yolo11l.pt", label: "YOLO11 Large" },
  { value: "yolo11x.pt", label: "YOLO11 XLarge (Most Accurate)" },
];
