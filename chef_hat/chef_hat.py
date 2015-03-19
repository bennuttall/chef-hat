from RPi import GPIO
from w1thermsensor import W1ThermSensor
import energenie
import lcd
from datetime import datetime, timedelta
from time import sleep


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Chef(object):
    """
    Provides an implementation of temperature moderation for use in sous vide
    cooking with the Chef HAT add-on for Raspberry Pi. The API allows user
    control in Python, but can also be used with a minimal startup script and
    provides control through use of the HAT's buttons and LCD screen.
    """

    DEFAULT_TARGET_TEMPERATURE = 55
    DEFAULT_DURATION = 120

    TEMPERATURE_MARGIN = 1

    TEMPERATURE_INCREMENT = 1
    DURATION_INCREMENT = 5

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
        self.display_initial_info()

        if start:
            self.start()

    def _setup_gpio(self):
        """
        Setup the GPIO pins used in the Chef HAT (input buttons and status LED)
        and create an event on the back button to terminate the process.
        """

        GPIO.setup(self.LED, GPIO.OUT)
        self.turn_led_off()

        for button in self.BUTTONS:
            GPIO.setup(button, GPIO.IN, self.PULL)
            self.remove_button_event(button)

        self.add_button_event(self.BUTTON_BACK, self.terminate)

    def _wait_for_button_press(self, button):
        """
        Halts the program until a paticular button is pressed, then continues.
        """

        GPIO.wait_for_edge(button, self.EDGE)

    def _setup_up_down_buttons(self, increase_function, decrease_function):
        """
        Configures the *up* and *down* buttons on the Chef HAT to run
        particular increase and decrease functions accordingly. When the
        *enter* button is pressed removes the up/down button events and
        continues.
        """

        self.add_button_event(self.BUTTON_UP, increase_function)
        self.add_button_event(self.BUTTON_DOWN, decrease_function)

        self._wait_for_button_press(self.BUTTON_ENTER)

        self.remove_button_event(self.BUTTON_UP)
        self.remove_button_event(self.BUTTON_DOWN)

    def _set_target_temperature(self, temperature):
        """
        Sets the object's `target_temperature` property. If `temperature` is
        passed, sets it to the *float* of that value, otherwise sets it to its
        configured default value and provides the means to change the value
        using the up/down buttons and the LCD.
        """

        if temperature is not None:
            self.target_temperature = float(temperature)
        else:
            self.target_temperature = float(self.DEFAULT_TARGET_TEMPERATURE)

            self.display("Set temperature")
            sleep(1)

            self.display("Temperature: %sC", "%d" % self.target_temperature)

            self._setup_up_down_buttons(
                self.increase_target_temperature,
                self.decrease_target_temperature
            )

        self.target_temperature_margin_lower = self.target_temperature - 1
        self.target_temperature_margin_upper = self.target_temperature + 1

    def _set_duration(self, duration):
        """
        Sets the object's `duration` property. If `duration` is
        passed, sets it to the *int* of that value, otherwise sets it to its
        configured default value and provides the means to change the value
        using the up/down buttons and the LCD.
        """

        if duration is not None:
            self.duration = int(duration)
        else:
            self.duration = int(self.DEFAULT_DURATION)

            self.display("Set timer")
            sleep(1)

            self.display("Timer: %s mins", "%d" % self.duration)

            self._setup_up_down_buttons(
                self.increase_duration,
                self.decrease_duration
            )

    def start(self):
        """
        Progress the object's state to *preparing* and start the cooking
        process in the loop of temperature moderation and progressive state
        evolution.
        """

        self.state = self.STATE_PREPARING
        self.display("Preparing")

        while self.STATE_PREPARING <= self.state < self.STATE_FINISHED:
            temperature = self.get_temperature()
            self.state_machine(temperature)
            self.moderate_temperature(temperature)
            sleep(5)

        # State has reached "finished" so run the terminate function
        # to clean up
        self.terminate(None)

    def terminate(self, pin):
        """
        Moves the object status to *finished* in order to end the cooking
        process.
        """

        self.remove_button_event(self.BUTTON_BACK)
        self.state = self.STATE_FINISHED

    def display(self, text, data_1='', data_2=''):
        """
        Prints fomatted `text` and `data` and writes an abbreviated version to
        the LCD.
        """

        abbreviations = {
            'Set temperature':
                ('Set', 'temp'),
            'Temperature: %sC':
                ('Temp:', '%7sC' % data_1),
            'Set timer':
                ('Set', 'timer'),
            'Timer: %s mins':
                ('Timer:', '%3s mins' % data_1),
            'Temperature: %sC; Timer: %s mins':
                ('%sC' % data_1, '%s mins' % data_2),
            'Add food and press enter to continue':
                ('Add food', 'Press enter'),
            '%s %s left':
                ('%s %s' % (data_1, data_2)),
        }

        # replace the first instance of %s with data_1
        # and the second with data_2
        text_with_data = text.replace(
            '%s', str(data_1), 1
        ).replace(
            '%s', str(data_2), 1
        )

        for line in text_with_data.split('; '):
            print(text_with_data)

        if text in abbreviations:
            abbreviation = abbreviations[text]
            lcd.write(abbreviation[0], line=1)
            lcd.write(abbreviation[1], line=2)
        else:
            lcd.write(text_with_data[:8], line=1)
            lcd.write(text_with_data[8:16], line=2)

    def turn_led_on(self):
        """
        Turns the status LED on
        """

        GPIO.output(self.LED, True)

    def turn_led_off(self):
        """
        Turns the status LED off
        """

        GPIO.output(self.LED, False)

    def turn_cooker_on(self):
        """
        Uses energenie to switch the cooker on. Also turns on the status LED.
        """

        energenie.switch_on()
        self.turn_led_on()

    def turn_cooker_off(self):
        """
        Uses energenie to switch the cooker off. Also turns off the status LED.
        """

        energenie.switch_off()
        self.turn_led_off()

    def add_button_event(self, button, callback):
        """
        Adds a GPIO event to run a callback function when a particular button
        is pressed.
        """

        GPIO.add_event_detect(button, self.EDGE, callback, self.BOUNCETIME)

    def remove_button_event(self, button):
        """
        Removes a GPIO event for a particular button.
        """

        GPIO.remove_event_detect(button)

    def display_initial_info(self):
        """
        Displays temperature and duration values as previously configured.
        """

        temperature = "%d" % self.target_temperature
        duration = "%d" % self.duration
        self.display("Temperature: %sC; Timer: %s mins", temperature, duration)

    def increase_target_temperature(self, pin):
        """
        Increases the target temperature by the temperature increment and
        displays the new value on the LCD.
        """

        self.target_temperature += self.TEMPERATURE_INCREMENT
        self.display("Temperature: %sC", "%d" % self.target_temperature)

    def decrease_target_temperature(self, pin):
        """
        Decreases the target temperature by the temperature increment and
        displays the new value on the LCD.
        """

        self.target_temperature -= self.TEMPERATURE_INCREMENT
        self.display("Temperature: %sC", "%d" % self.target_temperature)

    def increase_duration(self, pin):
        """
        Increases the duration by the duration increment and displays the new
        value on the LCD.
        """

        self.duration += self.DURATION_INCREMENT
        self.display("Timer: %s mins", "%d" % self.duration)

    def decrease_duration(self, pin):
        """
        Decreases the duration by the duration increment and displays the new
        value on the LCD.
        """

        self.duration -= self.DURATION_INCREMENT
        self.display("Timer: %s mins", "%d" % self.duration)

    def update_status_to_ready(self):
        """
        Updates the object state to *ready* and adds a button press event for
        the user to proceed to the *food in* state.
        """

        self.state = self.STATE_READY
        self.add_button_event(self.BUTTON_ENTER, self.update_status_to_food_in)
        self.display("Add food and press enter to continue")

    def update_status_to_food_in(self, pin):
        """
        Updates the object state to *food in* and removes the button press
        event for updating to this state.
        """

        self.remove_button_event(self.BUTTON_ENTER)
        self.state = self.STATE_FOOD_IN
        self.display("Food in")

    def update_status_to_cooking(self):
        """
        Updates the object state to *cooking* and sets the timer according to
        the object's `duration` property, relative to the current time.
        """

        self.state = self.STATE_COOKING
        self.display("Cooking")
        current_time = datetime.now()
        print(current_time)
        self.end_time = current_time + timedelta(minutes=self.duration)
        print(self.end_time)

    def update_status_to_cooked(self):
        """
        Updates the object state to *cooked* and adds a button press event for
        the user to progress the state to *finished*.
        """

        self.state = self.STATE_COOKED
        self.display("Cooked")
        self.add_button_event(
            self.BUTTON_ENTER,
            self.update_status_to_finished
        )

    def update_status_to_finished(self, pin):
        """
        Updates the object state to *finished*.
        """

        self.state = self.STATE_FINISHED
        self.display("Finished")

    def get_temperature(self):
        """
        Returns the current temperature from the temperature sensor as a float.
        """

        return self.sensor.get_temperature()

    def moderate_temperature(self, temperature):
        """
        Moderates the temperature of the cooker. Switches it off if the
        temperature is too high, and switches it off if it's too low, relative
        to the object's `target_temperature` property. Also writes out the on
        or off action and the temperature value.
        """

        if temperature < self.target_temperature:
            self.turn_cooker_on()
            self.display("%.2f on" % temperature) ###
        else:
            self.turn_cooker_off()
            self.display("%.2f off" % temperature)

    def state_machine(self, temperature):
        """
        Does an appropriate action based on the current state of the object.

        State: Preparing
            temperature in range of target => update status to *ready*

        State: Food in
            temperature in range of target => update status to *cooking*

        State: Cooking
            time remaining => show remaining time
            time out => update status to *cooked*
        """

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
        """
        Prints the amount of cooking time remaining. If under 1 minute, shown
        in seconds, otherwise shown in minutes.
        """

        current_time = datetime.now()
        time_left = self.end_time - current_time
        secs_left = time_left.seconds
        mins_left = secs_left // 60

        if mins_left > 0:
            min_or_mins = 'min' if mins_left == 1 else 'mins'
            self.display("%s %s left", "%3d" % (mins_left, min_or_mins), line=2)
        else:
            sec_or_secs = 'sec' if secs_left == 1 else 'secs'
            self.display("%s %s left", "%3d" % (secs_left, sec_or_secs), line=2)

    def in_temperature_range(self, temperature):
        """
        Returns true if the passed `temperature` value is in range of the
        object's target temperature, according to the temperature margin.
        Otherwise returns false.
        """

        lower = self.target_temperature_margin_lower
        upper = self.target_temperature_margin_upper
        return lower < temperature < upper


if __name__ == '__main__':
    while True:
        chef = Chef()
        """
        It seems silly to keep reinstantiating the object in a while loop but
        it just throws the object away and lets the user start again
        """
