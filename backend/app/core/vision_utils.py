import cv2

def extract_frame(video_path, frame_number):
    """
    Extracts a specific frame from a video file.
    """
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    return frame
