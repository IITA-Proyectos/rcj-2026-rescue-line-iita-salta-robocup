##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# serial: UART communication testing with Teensy.
import serial
# time: delays between transmissions.
import time

##################################################

### CONFIGURACION GLOBAL

##################################################

PORT = '/dev/serial0'       # Serial device path.
BAUDRATE = 115200           # Communication speed.
MESSAGE = [255, 40, 254, 90]  # Example packet to send.
DELAY = 1.0                 # Delay between sends in seconds.

##################################################

### FUNCIONES AUXILIARES

##################################################

def open_serial():
    """
    Technical description.

    Open serial port with configured parameters.

    Parameters:
    None

    Returns:
    serial.Serial: opened serial connection.

    Side effects:
    - Accesses serial hardware.
    """
    return serial.Serial(PORT, BAUDRATE)


def send_packet(ser):
    """
    Technical description.

    Send predefined MESSAGE bytes over the serial connection.

    Parameters:
    ser (serial.Serial): open serial connection.

    Returns:
    None

    Side effects:
    - Writes bytes to serial hardware.
    """
    ser.write(bytearray(MESSAGE))

##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: open serial link, send MESSAGE repeatedly with delay, and keep
# running until interrupted.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
def main():
    """
    Technical description.

    Initialize serial port and periodically transmit MESSAGE.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - Continuous serial transmission with delays.
    """
    ser = open_serial()
    while True:
        send_packet(ser)
        time.sleep(DELAY)


if __name__ == "__main__":
    main()
