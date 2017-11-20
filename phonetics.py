from collections import defaultdict
import yaml
import regex as re
import operator


def _set_regex(*args):
    """ Build a regex for a set of segments. """
    return ur'(?:{0})'.format('|'.join(args))


class PhoneticsEngine(object):

    def __init__(self, filename):
        with open(filename, 'rb') as file:
            config = yaml.load(file)
        self._load_segments(config)

    def _load_segments(self, config):
        """ Load segments from configuration and group  by features. """

        stack = [([], config['segments'])]
        self._all = set()
        self._features = defaultdict(set)
        self._segments = defaultdict(set)

        # find all segments and add them to any ancestor feature classes
        while len(stack) > 0:
            features, segments = stack.pop()

            # if value is list add segments to parent classes
            if isinstance(segments, list):
                for feature in features:
                    for segment in segments:
                        self._all.add(segment)
                        self._segments[feature].add(segment)
                        self._features[segment].add(feature)

            # if value is a dictionary add another stack item for each entry
            elif isinstance(segments, dict):
                for key, value in segments.items():
                    stack.append((features + [key], value))

            # otherwise the configuration is badly formed
            else:
                raise Exception("NO")

        # set the regex for segment tokens
        self._segment_regex = _set_regex(*self._all)
        self._token_regex = re.compile(self.TOKEN_REGEX.format(self._segment_regex))

        # finalize sets
        self._all.add(ur'\b')
        self._segments= dict(self._segments)
        self._features = dict(self._features)


    TARGET = u'_'
    BOUNDARY = u'#'
    EXPRESSION = ur'\[(?>[^\[\]]|(?R))*\]'
    PATTERN = ur'{0}\K{1}(?={2})'
    def app_change(self, word, changes, where):
        prefix, suffix = self._affixes(where)
        target = self._target(changes)
        pattern = self.PATTERN.format(prefix, target, suffix)
        pattern = pattern.replace(self.BOUNDARY, r'\b')
        return re.sub(pattern, lambda match: self._sub(match, changes), word)


    def _affixes(self, where):
        """ Get patterns for conditioning prefix and suffix. """
        return tuple(
             re.sub(self.EXPRESSION, lambda m: self._expr(m), affix)
             for affix in where.split(self.TARGET)
        )


    def _expr(self, match):
        """ Replace an expression with a regex matching the set of segments. """
        tokens = self.parse(match.group(0))
        segments = self.eval(tokens)
        return _set_regex(*segments)


    def _target(self, changes):
        """ Get the pattern for the segment to be replaced. """
        segments = changes.keys()
        segments.sort(key=len, reverse=True)
        return _set_regex(*segments)


    def _sub(self, match, changes):
        return changes[match.group(0)]


    # definitions of functions for phonetic class expressions
    class Operator(object):
        def __init__(self, token, regex, arity, precedence, function):
            self.token = token
            self.regex = regex
            self.arity = arity
            self.precedence = precedence
            self.function = function

    NOT = Operator(token='-', regex=r'-(?=\[)', arity=1, precedence=2, function='_not')
    AND = Operator(token=',', regex=r',', arity=2, precedence=1, function='_and')
    OR = Operator(token='|', regex=r'\|', arity=2, precedence=0, function='_or')
    OPERATORS = {op.token: op for op in (NOT, AND, OR)}

    def _not(self, x):
        return self._all - x

    def _and(self, x, y):
        return x & y

    def _or(self, x, y):
        return x | y


    # regex definitions for matching phonetic expression tokens
    CLASS = r'[+-][\w-]+'
    LEFT_BRACKET = r'\['
    RIGHT_BRACKET = r'\]'
    OPERATOR = _set_regex(*[op.regex for op in OPERATORS.values()])
    TOKEN_REGEX = _set_regex(CLASS, LEFT_BRACKET, RIGHT_BRACKET, OPERATOR, '{0}', '.')

    def parse(self, expr):
        """ Parse an expression representing a set of segments. """

        out = []
        ops = []

        # parse tokens and evaluate segment set
        for match in self._token_regex.finditer(expr):
            token = match.group(0)

            # if set name append the set to the stack
            if re.match(self.CLASS, token):
                out.append(token)

            # if token is segment append to the stack
            elif re.match(self._segment_regex, token):
                out.append(token)

            # if operator apply previous operators if necessary and add to stack
            elif token in self.OPERATORS:
                op = self.OPERATORS[token]
                while len(ops) > 0 and isinstance(ops[-1], self.Operator) \
                and ops[-1].precedence >= op.precedence:
                    out.append(ops.pop().token)
                ops.append(op)

            # if left bracket add to operator stack
            elif re.match(self.LEFT_BRACKET, token):
                ops.append(token)

            # if right bracket apply operators until left bracket 
            elif re.match(self.RIGHT_BRACKET, token):
                while len(ops) > 0 and isinstance(ops[-1], self.Operator):
                    out.append(ops.pop().token)
                if len(ops) == 0 or not re.match(self.LEFT_BRACKET, ops[-1]):
                    print ops
                    raise ExpressionException("no matching left bracket")
                ops.pop()

            # raise an error on an invalid token
            else:
                raise ExpressionException("invalid segment: '%s'" % token)
        
        # apply any remaining operators
        while len(ops) > 0:
            out.append(ops.pop().token)

        # return the parsed output
        return out


    def eval(self, tokens):
        """ Evaluate a set of parsed tokens into a set of segments. """

        out = []
        for token in tokens:

            # if token is class put appropriate set on stack
            if re.match(self.CLASS, token):
                try:
                    if token[0] == '+':
                        out.append(self._segments[token[1:]])
                    elif token[0] == '-':
                        out.append(self._all - self._segments[token[1:]])
                    else:
                        raise ExpressionException("invalid token: '%s'" % token)
                except KeyError:
                    raise ExpressionException("invalid feature: '%s'" % token)

            # if token is segment put set containing it on stack
            elif re.match(self._segment_regex, token):
                out.append(set(token))

            # if token is operator apply to top of stack
            elif token in self.OPERATORS:
                try:
                    op = self.OPERATORS[token]
                    fn = getattr(self, op.function)
                    args = []
                    for i in range(op.arity):
                        args.append(out.pop())
                    out.append(fn(*args))
                except IndexError:
                    raise Exception("NO")

            # raise exception on invalid token
            else:
                raise ExpressionException("invalid token: '%s'" % token)

        # check for errors and return the final value on top of the stack
        if len(out) > 1 or not isinstance(out[0], set):
            raise Exception("NO")
        return out.pop()


class ExpressionException(Exception):
    pass

class PhoneticsException(Exception):
    pass
