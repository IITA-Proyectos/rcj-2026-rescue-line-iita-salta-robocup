from threading import Lock, Thread
import time

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
        # SECUENCIA Y SELLO DE CAPTURA.
        #
        # Este es el patron "ultimo frame disponible": el hilo pisa `self.frame`
        # a la velocidad de la camara y `read()` devuelve lo que haya. Eso esta
        # bien -es lo que evita acumular latencia de cola- pero SIN estos dos
        # campos el lazo no puede saber:
        #     * si proceso un frame NUEVO o el mismo dos veces
        #     * cuantos frames se salteo
        #     * que EDAD tenia el frame cuando lo proceso
        # y sin eso no se puede atribuir el retardo total: si el robot reacciona
        # tarde, no se distingue "la camara entrego un frame viejo" de "la Pi
        # tardo en procesar" o de "la Teensy tardo en ejecutar".
        # Lo pidio ChatGPT en la auditoria del 25-ago y estaba en el protocolo
        # del sabado como campo faltante.
        self.seq = 0
        self.t_cap = time.monotonic()

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
            ahora = time.monotonic()
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame
                if grabbed:
                    self.seq += 1
                    self.t_cap = ahora

    def read(self):
        # return the frame most recently read
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def read_meta(self):
        """(frame, seq, edad_ms). `read()` sigue existiendo y sin cambios.

        `seq` es el numero de frame que la camara entrego: si dos vueltas
        seguidas del lazo ven el MISMO seq, la vision proceso dos veces la misma
        imagen y una de las dos decisiones es aire. Si salta de 10 a 14, se
        perdieron 3.

        `edad_ms` es cuanto hacia que ese frame se habia capturado. Es el primer
        eslabon del retardo total, y el unico que hoy no se medía.
        """
        with self.lock:
            if self.frame is None:
                return None, self.seq, 0.0
            edad = (time.monotonic() - self.t_cap) * 1000.0
            return self.frame.copy(), self.seq, edad

    def get_dim(self):  # width, height
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True
        self.stream.release()
