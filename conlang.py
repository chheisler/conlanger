import yaml
import random
import re
from phonetics import PhoneticsEngine

def weighted_choice(items):
    """ Make a weighted choice from a sequence of item, weight tuples. """
    items = list(items)
    scale = sum(weight for item, weight in items)
    roll = random.uniform(0, scale)
    for item, weight in items:
        roll -= weight
        if roll < 0:
            return item

def normalize(items):
    return tuple(x(item) for item in items)

def x(item):
    if item is None:
        return u''
    elif isinstance(item, str):
        return unicode(item)
    return item

class WordGenerator(object):
    def __init__(self, config_filename):
        with open(config_filename, 'rb') as config_file:
            config = yaml.load(config_file)
        self._boundaries = set(config['boundaries'])
        self._syllables = [tuple(syllable) for syllable in config['syllables']]
        self._machine = StateMachine(config)
        self._changes = config['changes']

    def generate_word(self, num_syllables=None):
        print
        num_syllables = num_syllables or weighted_choice(self._syllables)
        self._machine.reset()
        output = []
        for i in range(num_syllables):
            output += self.generate_syllable()
        word = ''.join(output)
        print(u'original: {0}'.format(word))
        return self.apply_changes(word)

    def generate_syllable(self):
        output = []
        while True:
            output.append(self._machine.next())
            if self._machine.state in self._boundaries:
                break
        return output

    def apply_changes(self, word):
        for change in self._changes:
            word = self.apply_change(word, change)

    def apply_change(self, word, change):
        phonetics = PhoneticsEngine('phonetics.yaml')
        for rule in change['rules']:
            word = phonetics.sound_change(rule, word)
        print u'{0}: {1}'.format(change['name'], word)
        return word

class StateMachine(object):
    """ Simple state machine for producing initial words. """

    def __init__(self, config):
        self._start = self._state = config['start']
        self._states = {
            state: {
                next_state: [normalize(transition) for transition in transitions]
                for next_state, transitions in next_states.items()
            }
            for state, next_states in config['states'].items()
        }

    @property
    def state(self):
        """ Get the current state of the machine. """
        return self._state

    def next(self):
        """ Advance the machine to the next state and return the output of
        the transition. """
        next_state, output = weighted_choice(self._transitions())
        self._state = next_state
        return output

    def reset(self):
        """ Reset the machine to its starting state. """
        self._state = self._start

    def _transitions(self):
        """ Generate a list of transitions, outputs and waits for the current
        state of the machine. """
        for next_state, transitions in self._states[self._state].items():
            for output, weight in transitions:
                yield((next_state, output), weight)
