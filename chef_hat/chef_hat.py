from RPi import GPIO
from w1thermsensor import W1ThermSensor
import energenie
import lcd
from datetime import datetime, timedelta
from time import sleep


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Chef(object):
    DEFAULT_TARGET_TEMPERATURE = 55
    DEFAULT_DURATION = 120

    DEFAULT_TEMPERATURE_INCREMENT = 1
    DEFAULT_DURATION_INCREMENT = 5
    DEFAULT_TEMPERATURE_MARGIN = 1

    LED = 15
    BUTTON_UP = 2
    BUTTON_DOWN = 3
    BUTTON_ENTER = 4
    BUTTON_BACK = 10
    BUTTONS = [BUTTON_UP, BUTTON_DOWN, BUTTON_ENTER, BUTTON_BACK]

    def __init__(self, **kwargs):
        self._setup_gpio()
        self.end_time = None

        self.sensor = W1ThermSensor()
        self.lcd = lcd
        self.lcd.init()

        if 'temperature' in kwargs:
            self.target_temperature = float(kwargs['temperature'])
        else:
            self.set_target_temperature()

        if 'duration' in kwargs:
            self.duration = float(kwargs['duration'])
        else:
            self.set_duration()

        self.write("%dC" % self.target_temperature)
        self.write("%d mins" % self.duration, 2)

        self.target_temperature_lower = (
            self.target_temperature - self.DEFAULT_TEMPERATURE_MARGIN
        )
        self.target_temperature_upper = (
            self.target_temperature + self.DEFAULT_TEMPERATURE_MARGIN
        )

        sleep(3)
        self.write("Enter")
        self.write("to start", 2)

        GPIO.wait_for_edge(self.BUTTON_ENTER, GPIO.FALLING)
        self.start()

    def _setup_gpio(self):
        GPIO.setup(self.LED, GPIO.OUT)
        self.turn_led_off()

        for button in self.BUTTONS:
            GPIO.setup(button, GPIO.IN, GPIO.PUD_UP)

        GPIO.add_event_detect(self.BUTTON_BACK, GPIO.FALLING, restart, 1000)

    def set_target_temperature(self):
        self.write("Set")
        self.write("temp", 2)
        sleep(1)

        self.target_temperature = self.DEFAULT_TARGET_TEMPERATURE
        self.write("Temp:")
        self.write("%7dC" % self.target_temperature, 2)

        GPIO.add_event_detect(
            self.BUTTON_UP, GPIO.FALLING, self.increase_temperature, 100
        )
        GPIO.add_event_detect(
            self.BUTTON_DOWN, GPIO.FALLING, self.decrease_temperature, 100
        )

        GPIO.wait_for_edge(self.BUTTON_ENTER, GPIO.FALLING)

        GPIO.remove_event_detect(self.BUTTON_UP)
        GPIO.remove_event_detect(self.BUTTON_DOWN)

    def set_duration(self):
        self.write("Set")
        self.write("timer", 2)
        sleep(1)

        self.duration = self.DEFAULT_DURATION
        self.write("Timer:")
        self.write("%2d mins" % self.duration, 2)

        GPIO.add_event_detect(
            self.BUTTON_UP, GPIO.FALLING, self.increase_duration, 100
        )
        GPIO.add_event_detect(
            self.BUTTON_DOWN, GPIO.FALLING, self.decrease_duration, 100
        )

        GPIO.wait_for_edge(self.BUTTON_ENTER, GPIO.FALLING)

        GPIO.remove_event_detect(self.BUTTON_UP)
        GPIO.remove_event_detect(self.BUTTON_DOWN)

    def increase_temperature(self, pin):
        self.target_temperature += self.DEFAULT_TEMPERATURE_INCREMENT
        self.write("Temp:")
        self.write("%7dC" % self.target_temperature, 2)

    def decrease_temperature(self, pin):
        self.target_temperature -= self.DEFAULT_TEMPERATURE_INCREMENT
        self.write("Temp:")
        self.write("%7dC" % self.target_temperature, 2)

    def increase_duration(self, pin):
        self.duration += self.DEFAULT_DURATION_INCREMENT
        self.write("Timer:")
        self.write("%3d mins" % self.duration, 2)

    def decrease_duration(self, pin):
        self.duration -= self.DEFAULT_DURATION_INCREMENT
        self.write("Timer:")
        self.write("%3d mins" % self.duration, 2)

    def get_temperature(self):
        return self.sensor.get_temperature()

    def write(self, text, line=1):
        lcd.write(text, line)
        print(text)

    def turn_led_on(self):
        GPIO.output(self.LED, True)

    def turn_led_off(self):
        GPIO.output(self.LED, False)

    def turn_cooker_on(self):
        energenie.switch_on()
        self.turn_led_on()

    def turn_cooker_off(self):
        energenie.switch_off()
        self.turn_led_off()

    def in_temperature_range(self, temperature):
        lower = self.target_temperature_lower
        upper = self.target_temperature_upper

        return lower < temperature < upper

    def display_info(self, temperature):
        row_1 = "%2.2fC" % temperature

        if self.end_time is None:
            if self.in_temperature_range(temperature):
                row_2 = "Ready"
            else:
                row_2 = "Wait..."
        else:
            current_time = datetime.now()
            time_left = self.end_time - current_time
            mins_left = time_left.seconds // 60
            if mins_left > 0:
                min_or_mins = 'mins' if mins_left > 1 else 'min'
                row_2 = "%s %s" % (mins_left, min_or_mins)
            else:
                row_2 = "FINISHED"

        self.write(row_1)
        self.write(row_2, 2)

    def flash_led(self):
        while True:
            self.turn_led_on()
            sleep(0.5)
            self.turn_led_off()
            sleep(0.5)

    def moderate_temperature(self, temperature):
        if temperature < self.target_temperature_lower:
            self.turn_cooker_on()
        elif temperature > self.target_temperature_upper:
            self.turn_cooker_off()

    def start_timer(self, pin):
        current_time = datetime.now()
        self.end_time = current_time + timedelta(minutes=self.duration)
        GPIO.remove_event_detect(self.BUTTON_ENTER)

    def start(self):
        GPIO.add_event_detect(
            self.BUTTON_ENTER, GPIO.FALLING, self.start_timer
        )

        while True:
            temperature = self.get_temperature()
            self.moderate_temperature(temperature)
            self.display_info(temperature)
            sleep(5)


def restart(pin):
    main()


def main():
    chef = Chef()


if __name__ == '__main__':
    main()
