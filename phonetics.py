from collections import defaultdict
import yaml
import regex as re

class PhoneticsEngine(object):

    def __init__(self, filename):
        with open(filename, 'rb') as file:
            config = yaml.load(file)
        self._segments = set()
        self._classes = defaultdict(set)
        for segment, features in config['segments'].items():
            self._segments.add(segment)
            for feature in features:
                self._classes[feature].add(segment)


    # tokens for writing operations
    FEATURE = r'[\w-]+'
    AND = '+'
    NOT = r'-'
    OR = '|'
    LEFT_BRACKET = '('
    RIGHT_BRACKET = ')'
    PRECEDENCE = {AND: 1, NOT: 1, OR: 0}


    def is_operator(self, token):
        return re.match('^(%s)$' % '|'.join((AND, NOT, OR))) is not None

    def is_feature(self, token):
        return False

    TARGET = '_'
    BOUNDARY = '#'
    EXPRESSION = r'\[(?>[^\[\]]|(?R))*\]'
    PATTERN = r'{0}\K{1}(?={2})'
    def app_change(self, word, changes, where):
        prefix, suffix = self._affixes(where)
        target = self._target(changes)
        pattern = self.PATTERN.format(prefix, target, suffix)
        pattern = pattern.replace(self.BOUNDARY, r'\b')
        return re.sub(pattern, lambda match: self._sub(match, changes), word)


    def _affixes(self, where):
        """ Get patterns for conditioning prefix and suffix. """
        print where, self.TARGET
        try:
            return tuple(
                re.sub(self.EXPRESSION, self._expr, affix)
                for affix in where.split(self.TARGET)
            )
        except ValueError:
            raise PhoneticsException('no')


    def _target(self, changes):
        """ Get the pattern for the segment to be replaced. """
        segments = changes.keys()
        segments.sort(key=len, reverse=True)
        return r'(?:{0})'.format('|'.join(segments))


    def _sub(self, match, changes):
        return changes[match.group(0)]


    def _expr(self, expr):
        tokens = re.findall('(%s)' % '|'.join([SET, AND, NOT, OR, LEFT_BRACKET, RIGHT_BRACKET]))
        output = [self._segments[theuniversalset]]
        operators = []

        # parse tokens and evaluate segment set
        for token in tokens:

            # if set name append the set to the stack
            if is_value(token):
                try:
                    output.append(self._classes[token])
                except KeyError:
                    raise ExpressionException("invalid feature: '%s'" % token)

            # if operator apply previous operators if necessary and add to stack
            elif is_operator(token):
                while len(operators) > 0 and PRECEDENCE[operators[-1]] >= PRECEDENCE[token]:
                    output.append(operators.pop())
                operators.append(token)

            # if left bracket add to operator stack
            elif token == self.LEFT_BRACKET:
                operators.append(token)

            # if right bracket apply operators until left bracket 
            elif token == self.RIGHT_BRACKET:
                while len(operators) > 0 and operators[-1] != LEFT_BRACKET:
                    _operate(operators.pop(), stack)
                if len(operators) == 0:
                    raise ExpressionException("no matching left bracket")
                operators.pop()

            # raise an error on an invalid token
            else:
                raise ExpressionException("invalid token: '%s'" % token)
        
        # apply any remaining operators
        while len(operators) > 0:
            _operate(output, operators)

        # return the final result in the output stack
        return output.pop()


    def _operate(self, output, operators):
        x = output.pop()
        y = output.pop()
        operator = operators.pop()
        if operator == AND:
            pass
        elif operator == NOT:
            pass
        elif operator == OR:
            pass
        else:
            raise Exception("invalid operator: '%s'" % token)

class ExpressionException(Exception):
    pass

class PhoneticsException(Exception):
    pass
