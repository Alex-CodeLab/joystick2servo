import queue
import threading
import rcpy
import rcpy.servo as servo
from evdev import InputDevice, categorize, ecodes
import signal

class InputThread(threading.Thread):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.stop_event = threading.Event()

    def run(self):
        # Open the input device
        dev = InputDevice('/dev/input/event1')

        # Loop through the input events and put them into the queue
        for event in dev.read_loop():
            if self.stop_event.is_set():
                self.queue.put(event.value)
                return
            if event.type == ecodes.EV_ABS and event.code in [
                ecodes.ABS_X,
                # ecodes.ABS_Y,
            ]:
                self.queue.put(event.value)


    def stop(self):
        self.stop_event.set()

class ServoThread(threading.Thread):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        rcpy.set_state(rcpy.RUNNING)
        self.servo = rcpy.servo.Servo(1)
        rcpy.clock.Clock(self.servo, .1).start()
        rcpy.servo.enable()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

    def run(self):
        # Loop indefinitely, reading values from the queue and setting the servo position
        while True:
            value = self.queue.get()
            if value is None:
                break
            position = self.scale(value, 0, 65536, -1.5, 1.5)
            self.servo.set(position)
            self.queue.task_done()
            if self.stop_event.is_set():
                return

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)

    @staticmethod
    def scale(value, in_min, in_max, out_min, out_max):
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min



class Program:
    def __init__(self):
        # Create the queue and the threads
        self.queue = queue.Queue()
        self.input_thread = InputThread(self.queue)
        self.servo_thread = ServoThread(self.queue)
        self.input_thread.daemon = True
        self.servo_thread.daemon = True
    def start(self):
        # Start the threads
        self.input_thread.start()
        self.servo_thread.start()

        # Set up signal handler for graceful exit
        signal.signal(signal.SIGINT, self.graceful_exit)

        # Wait for the threads to finish
        self.input_thread.join()
        self.servo_thread.join()

    def graceful_exit(self, signal, frame):
        print("Exiting gracefully...")
        # set exit flag and allow threads to exit gracefully
        self.input_thread.stop()
        self.servo_thread.stop()

        self.input_thread.join(timeout=.1)
        self.servo_thread.join(timeout=.1)
        exit()


def main():
    # Create the program instance and start it
    program = Program()
    program.start()


if __name__ == '__main__':
    main()
