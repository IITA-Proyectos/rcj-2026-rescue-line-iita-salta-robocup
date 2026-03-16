##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# threading.Thread: separate frame capture loop without blocking main thread.
from threading import Thread
# OpenCV: camera access and frame acquisition.
import cv2

##################################################

### DEFINICION DE CLASES

##################################################

class WebcamVideoStream:
    """
    Threaded video capture wrapper over OpenCV VideoCapture.

    Responsabilidad:

    * Manage asynchronous frame acquisition.
    * Maintain latest grabbed frame for consumers.
    * Control start and stop of capture thread.

    Entradas principales:
    * src (int/str): camera device index or stream path.
    * width (int): requested capture width.
    * height (int): requested capture height.

    Salidas principales:
    * Latest frame read from the stream via read().
    """
    def __init__(self, src = 0, width = 160, height = 120):
        # Initialize capture stream and set requested dimensions.
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # self.stream.set(cv2.CAP_PROP_FPS, 60)
        print(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # print(self.stream.get(cv2.CAP_PROP_FPS))
        (self.grabbed, self.frame) = self.stream.read()
        # Thread stop flag for safe termination.
        self.stopped = False

    def start(self):
        """
        Launch frame acquisition thread and return self for chaining.

        Parameters:
        None

        Returns:
        WebcamVideoStream: instance with active background thread.

        Side effects:
        - Starts new OS thread reading frames.
        """
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        """
        Background loop that continuously updates the latest frame.

        Parameters:
        None

        Returns:
        None: exits when stop flag is set.

        Side effects:
        - Continuous access to camera hardware.
        """
        # keep looping infinitely until the thread is stopped
        while True:
            # Stop condition from external call.
            if self.stopped:
                return
            # Read next frame from the stream.
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        """
        Return the most recent frame captured by the thread.

        Parameters:
        None

        Returns:
        ndarray: last captured frame from OpenCV stream.

        Side effects:
        - None.
        """
        return self.frame

    def get_dim(self):
        """
        Provide capture dimensions from the underlying stream.

        Parameters:
        None

        Returns:
        tuple: (width, height) as reported by VideoCapture.

        Side effects:
        - None.
        """
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def stop(self):
        """
        Signal the acquisition thread to halt.

        Parameters:
        None

        Returns:
        None.

        Side effects:
        - Sets stop flag, thread exits on next iteration.
        """
        self.stopped = True
