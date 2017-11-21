from collections import defaultdict
import yaml
import regex as re
import operator
from sys import maxint

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
        self._segment_regex = _set_regex(self.BOUNDARY, *self._all)
        self._token_regex = re.compile(self.TOKEN_REGEX.format(self._segment_regex))

        # finalize sets
        self._segments= dict(self._segments)
        self._features = dict(self._features)


    TARGET = u'_'
    BOUNDARY = u'#'
    EXPRESSION = ur'\[(?>[^\[\]]|(?R))*\]'
    PATTERN = ur'(?<={0}){1}(?={2})'
    def sound_change(self, rule, word):

        # split the rule into the change and condition
        count = rule.count('/')
        if count == 0:
            change = rule
            where = '_'
        elif count == 1:
            change, where = rule.split('/')
        else:
            raise Exception("NO")

        # split the change into from and to
        try:
            before, after = change.split('->')
        except ValueError:
            raise PhoneticsException(u"invalid change expression: '%s'" % change)
        before = self._input_sub(before)

        # get patterns for conditioning prefix and suffix
        try:
            prefix, suffix = where.split('_')
        except ValueError:
            raise PhoneticsException(u"invalid environment expression: '%s'" % where)
        prefix = self._input_sub(prefix)
        suffix = self._input_sub(suffix)

        # apply the rule to the word
        pattern = self.PATTERN.format(prefix, before, suffix)
        pattern = pattern.replace(self.BOUNDARY, r'\b')
        return re.sub(pattern, lambda m: self._output_sub(m, after), word)


    def _input_sub(self, string):
        """ Substitute expressions in the input with a set of candidates. """
        return re.sub(self.EXPRESSION, lambda m: self._input_expr(m), string)


    def _input_expr(self, match):
        """ Replace an expression with a regex matching the set of segments. """
        tokens = self.parse(match.group(0))
        segments = self.eval(tokens)
        return _set_regex(*segments)


    def _output_sub(self, match, after):
        """ Substitute expressions in the output with the best match to the
        given segment. """
        output = re.sub(self.EXPRESSION, lambda expr: self._output_expr(match, expr), after)
        return re.sub(r'\\(\d+)', lambda group: self._output_group(match, group), output)


    def _output_expr(self, match, expr):
        """ Evaluate each expression and pick the best candidate from the set
        of sounds which is closest to the given segment. """
        segment = match.group(0)
        tokens = self.parse(expr.group(0))
        candidates = self.eval(tokens)

        # find the best candidates from the evaluated candidates
        best_candidates = []
        best_distance = maxint
        for candidate in candidates:
            distance = len(self._features[segment] ^ self._features[candidate])
            if distance < best_distance:
                best_candidates = [candidate]
                best_distance = distance
            elif distance == best_distance:
                best_candidates.append(candidate)

        # return candidate if exactly one found else raise an error
        if len(best_candidates) > 1:
            raise PhoneticsException("multiple candidates for segment '%s': '%s'" % (segment, ','.join(candidates)))
        elif len(best_candidates) == 0:
            raise Exception("NO")
        return best_candidates.pop()


    def _output_group(self, match, group):
        """ Insert segments which were captured in the environment. """
        return match.group(int(group.group(1)))


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
    TOKEN_REGEX = _set_regex(CLASS, LEFT_BRACKET, RIGHT_BRACKET, OPERATOR, '.')

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
                    raise PhoneticsException("no matching left bracket")
                ops.pop()

            # raise an error on an invalid token
            else:
                raise PhoneticsException(u"invalid segment: '%s'" % token)
        
        # apply any remaining operators
        while len(ops) > 0:
            out.append(ops.pop().token)

        # return the parsed output
        return out


    def eval(self, tokens):
        """ Evaluate a set of parsed tokens into a set of segments. """

        # handle special case for an empty string
        if len(tokens) == 0:
            return set('')

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


class PhoneticsException(Exception):
    pass
