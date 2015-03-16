from RPi import GPIO
from w1thermsensor import W1ThermSensor
import energenie
from datetime import datetime, timedelta
from time import sleep


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Chef(object):
    DEFAULT_TARGET_TEMPERATURE = 55
    DEFAULT_DURATION = 120

    TEMPERATURE_MARGIN = 1

    DEFAULT_TEMPERATURE_INCREMENT = 1
    DEFAULT_DURATION_INCREMENT = 5

    LED = 15
    BUTTON_UP = 2
    BUTTON_DOWN = 3
    BUTTON_ENTER = 4
    BUTTON_BACK = 10
    BUTTONS = [BUTTON_UP, BUTTON_DOWN, BUTTON_ENTER, BUTTON_BACK]

    BOUNCETIME = 100
    PULL = GPIO.PUD_UP
    EDGE = GPIO.FALLING

    STATE_SETUP = 0
    STATE_PREPARING = 1
    STATE_READY = 2
    STATE_FOOD_IN = 3
    STATE_COOKING = 4
    STATE_COOKED = 5
    STATE_FINISHED = 6

    def __init__(self, temperature=None, duration=None, start=True):
        self.state = self.STATE_SETUP
        self.sensor = W1ThermSensor()
        self.end_time = None

        self._setup_gpio()
        self._set_target_temperature(temperature)
        self._set_duration(duration)

        if start:
            self.start()

    def _setup_gpio(self):
        GPIO.setup(self.LED, GPIO.OUT)
        self.turn_led_off()

        for button in self.BUTTONS:
            GPIO.setup(button, GPIO.IN, self.PULL)

        self.add_button_event(self.BUTTON_BACK, self.terminate)

    def terminate(self, pin):
        self.remove_button_event(self.BUTTON_BACK)
        self.state = self.STATE_FINISHED

    def write(self, text, line=1):
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

    def add_button_event(self, button, callback):
        GPIO.add_event_detect(button, self.EDGE, callback, self.BOUNCETIME)

    def remove_button_event(self, button):
        GPIO.remove_event_detect(button)

    def _wait_for_button_press(self, button):
        GPIO.wait_for_edge(button, self.EDGE)

    def _setup_up_down_buttons(self, increase_function, decrease_function):
        self.add_button_event(self.BUTTON_UP, increase_function)
        self.add_button_event(self.BUTTON_DOWN, decrease_function)

        self._wait_for_button_press(self.BUTTON_ENTER)

        self.remove_button_event(self.BUTTON_UP)
        self.remove_button_event(self.BUTTON_DOWN)

    def _set_target_temperature(self, temperature):
        if temperature is not None:
            self.target_temperature = temperature
        else:
            self.target_temperature = self.DEFAULT_TARGET_TEMPERATURE

            self.write("Set")
            self.write("temp", 2)
            sleep(1)

            self.write("Temp:")
            self.write("%7dC" % self.target_temperature, 2)

            self._setup_up_down_buttons(
                self.increase_temperature,
                self.decrease_temperature
            )

        self.target_temperature_margin_lower = self.target_temperature - 1
        self.target_temperature_margin_upper = self.target_temperature + 1

    def _set_duration(self, duration):
        if duration is not None:
            self.duration = duration
        else:
            self.duration = self.DEFAULT_DURATION
            self.write("Set")
            self.write("timer", 2)
            sleep(1)

            self.write("Timer:")
            self.write("%2d mins" % self.duration, 2)

            self._setup_up_down_buttons(
                self.increase_duration,
                self.decrease_duration
            )

    def display_initial_info(self):
        self.write("%dC" % self.target_temperature)
        self.write("%d mins" % self.duration, 2)

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

    def update_status_to_ready(self):
        self.state = self.STATE_READY
        self.add_button_event(self.BUTTON_ENTER, self.update_status_to_food_in)
        self.write("Add food and press enter to continue")

    def update_status_to_food_in(self, pin):
        self.remove_button_event(self.BUTTON_ENTER)
        self.state = self.STATE_FOOD_IN
        self.write("Food in")

    def update_status_to_cooking(self):
        self.state = self.STATE_COOKING
        self.write("Cooking")
        current_time = datetime.now()
        print(current_time)
        self.end_time = current_time + timedelta(minutes=self.duration)
        print(self.end_time)

    def update_status_to_cooked(self):
        self.state = self.STATE_COOKED
        self.write("Cooked")
        self.add_button_event(self.BUTTON_ENTER, self.update_status_to_finished)

    def update_status_to_finished(self, pin):
        self.state = self.STATE_FINISHED
        self.write("Finished")

    def get_temperature(self):
        return self.sensor.get_temperature()

    def moderate_temperature(self, temperature):
        if temperature < self.target_temperature:
            self.turn_cooker_on()
            self.write("%s Turning cooker on" % temperature)
        else:
            self.turn_cooker_off()
            self.write("%s Turning cooker off" % temperature)

    def state_machine(self, temperature):
        if self.state == self.STATE_PREPARING:
            if self.in_temperature_range(temperature):
                self.update_status_to_ready()
        elif self.state == self.STATE_FOOD_IN:
            if self.in_temperature_range(temperature):
                self.update_status_to_cooking()
        elif self.state == self.STATE_COOKING:
            current_time = datetime.now()
            if self.end_time > current_time:
                self.show_remaining_time()
            else:
                self.update_status_to_cooked()

    def show_remaining_time(self):
        current_time = datetime.now()
        time_left = self.end_time - current_time
        mins_left = time_left.seconds // 60
        if mins_left > 0:
            min_or_mins = 'min' if mins_left == 1 else 'mins'
            print("%s %s left" % (mins_left, min_or_mins))
        else:
            print("mins left <= 0")
            min_or_mins = 'min' if mins_left == 1 else 'mins'
            print("%s %s left" % (mins_left, min_or_mins))

    def in_temperature_range(self, temperature):
        lower = self.target_temperature_margin_lower
        upper = self.target_temperature_margin_upper
        return lower < temperature < upper

    def start(self):
        self.state = self.STATE_PREPARING
        self.write("Preparing")

        while self.STATE_PREPARING <= self.state < self.STATE_FINISHED:
            temperature = self.get_temperature()
            self.state_machine(temperature)
            self.moderate_temperature(temperature)
            sleep(5)

        # State has reached "finished" so run the terminate function to clean up
        self.terminate(None)


if __name__ == '__main__':
    while True:
        chef = Chef()
        """
        It seems silly to keep reinstantiating the object in a while loop but
        it just throws the object away and lets the user start again
        """
