import cv2
import threading
import queue
import numpy as np
import requests

class CSI_Camera:
    def __init__(self):
        # Initialize instance variables
        # OpenCV video capture element
        self.video_capture = None
        # The last captured image from the camera
        self.frame = None
        self.grabbed = False
        # The thread where the video capture runs
        self.read_thread = None
        self.read_lock = threading.Lock()
        self.running = False

    def open(self, gstreamer_pipeline_string):
        try:
            self.video_capture = cv2.VideoCapture(
                gstreamer_pipeline_string, cv2.CAP_GSTREAMER
            )
            # Grab the first frame to start the video capturing
            self.grabbed, self.frame = self.video_capture.read()

        except RuntimeError:
            self.video_capture = None
            print("Unable to open camera")
            print("Pipeline: " + gstreamer_pipeline_string)


    def start(self):
        if self.running:
            print('Video capturing is already running')
            return None
        # create a thread to read the camera image
        if self.video_capture != None:
            self.running = True
            self.read_thread = threading.Thread(target=self.updateCamera)
            self.read_thread.start()
        return self

    def stop(self):
        self.running = False
        # Kill the thread
        self.read_thread.join()
        self.read_thread = None

    def updateCamera(self):
        # This is the thread to read images from the camera
        while self.running:
            try:
                grabbed, frame = self.video_capture.read()
                with self.read_lock:
                    self.grabbed = grabbed
                    self.frame = frame
            except RuntimeError:
                print("Could not read image from camera")
        # FIX ME - stop and cleanup thread
        # Something bad happened

    def read(self):
        with self.read_lock:
            frame = self.frame.copy()
            grabbed = self.grabbed
        return grabbed, frame

    def release(self):
        if self.video_capture != None:
            self.video_capture.release()
            self.video_capture = None
        # Now kill the thread
        if self.read_thread != None:
            self.read_thread.join()
            
def gstreamer_pipeline(
    sensor_id=0,
    capture_width=640,
    capture_height=480,
    display_width=640,
    display_height=480,
    framerate=20,
    flip_method=0,
):
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )

frame_queue = queue.Queue(maxsize=1)
running = True  # Global flag for thread termination
file_path = "home/insight/Firefly_sky/images/image.jpg"
window_title = "Dual CSI Cameras"


def send_data():
    global running
    while running:
        if not frame_queue.empty():
            frame = frame_queue.get()
            _, buffer = cv2.imencode(".jpg", frame)
            data = buffer.tobytes()

            response = requests.post("http://192.168.219.104:8000/receive-image/", data=data)
            print(response.json())

def run_cameras():
    global running
    left_camera = CSI_Camera()
    left_camera.open(
        gstreamer_pipeline(
            sensor_id=0,
            capture_width=640,
            capture_height=480,
            flip_method=0,
            display_width=960,
            display_height=540,
        )
    )
    left_camera.start()

    right_camera = CSI_Camera()
    right_camera.open(
        gstreamer_pipeline(
            sensor_id=1,
            capture_width=640,
            capture_height=480,
            flip_method=0,
            display_width=960,
            display_height=540,
        )
    )
    right_camera.start()

    while running:
        _, left_image = left_camera.read()
        _, right_image = right_camera.read()
        if left_image is not None and right_image is not None:
            left_image = cv2.flip(left_image, 0)
            right_image = cv2.flip(right_image, 0)
            camera_images = np.hstack((left_image, right_image)) 
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()  # Discard the oldest frame
                except queue.Empty:
                    pass
            frame_queue.put(camera_images)

    left_camera.stop()
    left_camera.release()
    right_camera.stop()
    right_camera.release()

def run_func():
    global running

    # Create threads
    run_thread = threading.Thread(target=send_data)
    video_thread = threading.Thread(target=run_cameras)

    # Start threads
    run_thread.start()
    video_thread.start()

    # Wait for threads to finish
    video_thread.join()
    running = False  # Signal all threads to stop
    run_thread.join()

if __name__ == "__main__":
    run_func()
