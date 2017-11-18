from collections import defaultdict
import yaml
import regex as re
import operator


def _set_regex(*args):
    return r'(?:{0})'.format('|'.join(args))


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
        self._classes = dict(self._classes)

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
        return _set_regex(*segments)


    def _sub(self, match, changes):
        return changes[match.group(0)]


    # tokens for writing operations
    CLASS = r'[+-][\w-]+'
    AND = r','
    OR = r'|'
    LEFT_BRACKET = r'['
    RIGHT_BRACKET = r']'
    OPERATOR = _set_regex(AND, re.escape(OR))
    TOKEN = _set_regex(CLASS, AND, re.escape(OR), re.escape(LEFT_BRACKET), re.escape(RIGHT_BRACKET), '.')
    PRECEDENCE = {AND: 1, OR: 0, LEFT_BRACKET: -1}
    FUNCTIONS = {AND: operator.__and__, OR: operator.__or__}
    def parse(self, expr):
        out = []
        ops = []

        # parse tokens and evaluate segment set
        for match in re.finditer(self.TOKEN, expr):
            token = match.group(0)

            # if set name append the set to the stack
            if re.match(self.CLASS, token):
                out.append(token)

            # if operator apply previous operators if necessary and add to stack
            elif re.match(self.OPERATOR, token):
                while len(ops) > 0 and self.PRECEDENCE[ops[-1]] >= self.PRECEDENCE[token]:
                    out.append(ops.pop())
                ops.append(token)

            # if left bracket add to operator stack
            elif token == self.LEFT_BRACKET:
                ops.append(token)

            # if right bracket apply operators until left bracket 
            elif token == self.RIGHT_BRACKET:
                while len(ops) > 0 and ops[-1] != self.LEFT_BRACKET:
                    out.append(ops.pop())
                if len(ops) == 0:
                    raise ExpressionException("no matching left bracket")
                ops.pop()

            # raise an error on an invalid token
            else:
                raise ExpressionException("invalid token: '%s'" % token)
        
        # apply any remaining operators
        while len(ops) > 0:
            out.append(ops.pop())

        # return the parsed output
        return out


    def eval(self, tokens):
        out = []
        for token in tokens:
            if re.match(self.CLASS, token):
                try:
                    if token[0] == '+':
                        print 'om'
                        out.append(self._classes[token[1:]])
                    elif token[0] == '-':
                        out.append(self._segments - self._classes[token[1:]])
                    else:
                        raise ExpressionException("invalid token: '%s'" % token)
                except KeyError:
                    raise ExpressionException("invalid feature: '%s'" % token)

            elif re.match(self.OPERATOR, token):
                try:
                    x = out.pop()
                    y = out.pop()
                    out.append(self.FUNCTIONS[token](x, y))
                except IndexError:
                    raise Exception("NO")

            else:
                raise ExpressionException("invalid token: '%s'" % token)
        return out.pop()


    @classmethod
    def _op(cls, out, ops):
        x = out.pop()
        y = out.pop()
        op = ops.pop()
        try:
            fn = FUNCTIONS[op](x, y)
        except KeyError:
            raise Exception("invalid")


class ExpressionException(Exception):
    pass

class PhoneticsException(Exception):
    pass
