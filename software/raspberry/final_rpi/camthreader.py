from threading import Lock, Thread
import cv2

class WebcamVideoStream:
    def __init__(self, src = 0, width = 160, height = 120):
        # initialize the video camera stream and read the first frame
        # from the stream

        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # self.stream.set(cv2.CAP_PROP_FPS, 60)
        print(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # print(self.stream.get(cv2.CAP_PROP_FPS))
        (self.grabbed, self.frame) = self.stream.read()
        # initialize the variable used to indicate if the thread should
        # be stopped
        self.stopped = False
        self.lock = Lock()
        self.thread = None

    def start(self):
        # start the thread to read frames from the video stream
        self.thread = Thread(target=self.update, args=(), daemon=True)
        self.thread.start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        while True:
            # if the thread indicator variable is set, stop the thread
            if self.stopped:
                return
            # otherwise, read the next frame from the stream
            grabbed, frame = self.stream.read()
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame

    def read(self):
        # return the frame most recently read
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def get_dim(self):  # width, height
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True
        self.stream.release()
