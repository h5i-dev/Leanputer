"""Fixed logical primitive typing rules, never unchecked environment axioms.

Initial slice is Lean's empty proposition and its dependent empty eliminator.
There is no constructor and hence no iota rule for this empty datatype.
"""


def primitive_code(expression):
    return 0 if expression[1]=='False' else 1


def primitive_type(expression):
    if expression[1]=='False': return ('sort',0)
    false = ('builtin','False')
    level = expression[2]
    return ('pi',('pi',false,('sort',level)),
            ('pi',false,('app',('var',1),('var',0))))


# Postorder schema for False.rec.{u}. a/b child indices are relative to the
# first allocated cell. None denotes the concrete universe parameter u.
EMPTY_ELIMINATOR = (
    (7,0,0,0), (2,0,0,None), (3,0,1,0), (1,0,0,1),
    (1,0,0,0), (5,3,4,0), (3,0,5,0), (3,2,6,0),
)
