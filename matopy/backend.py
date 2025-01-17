# smop -- Simple Matlab to Python compiler
# Copyright 2011-2016 Victor Leikehman

"""
Calling conventions:

call site:  nargout=N is passed if and only if N > 1
func decl:  nargout=1 must be declared if function may return
            more than one return value.  Otherwise optional.
return value:  return (x,y,z)[:nargout] or return x
"""

import logging

logger = logging.getLogger(__name__)

from . import node
from . import options
from .node import extend, exceptions
from .resolve import get_def_node

indent = " " * 4

optable = {
    "!": "not",
    "~=": "!=",
    "||": "or",
    "&&": "and",
    "^": "**",
    "**": "**",
    ".^": "**",
    "./": "/",
    ".*": "*",
    ".*=": "*",
    "./=": "/",
}


def backend(t, *args, **kwargs):
    return t._backend(level=1, *args, **kwargs)


# Sometimes user's variable names in the matlab code collide with Python
# reserved words and constants.  We handle this in the backend rather than in
# the lexer, to keep the target language separate from the lexer code.

# Some names, such as matlabarray, may collide with the user defined names.
# Both cases are solved by appending a trailing underscore to the user's names.

reserved = set(
    """
    and    assert  break class continue
    def    del     elif  else  except
    exec   finally for   from  global
    if     import  in    is    lambda
    not    or      pass  print raise
    return try     while with

    Data  Float Int   Numeric Oxphys
    array close float int     input
    open  range type  write

    len
    """.split()
)

STRUCTS = set()

# acos  asin atan  cos e
# exp   fabs floor log log10
# pi    sin  sqrt  tan


@extend(node.add)
def _backend(self, level=0):
    if self.args[0].__class__ is node.number and self.args[1].__class__ is node.number:
        return node.number(self.args[0].value + self.args[1].value)._backend(level)
    else:
        return "(%s+%s)" % (self.args[0]._backend(level), self.args[1]._backend(level))


@extend(node.arrayref)
def _backend(self, level=0):
    x = self.func_expr._backend(level)
    i = self.args._backend(level)
    if get_def_node(self.func_expr).props in "MW":
        return f"{x}[{i}]"
    else:
        return f"take({x},{i})"


@extend(node.break_stmt)
def _backend(self, level=0):
    return "break"


@extend(node.builtins)
def _backend(self, level=0):
    # if not self.ret:
    return "%s(%s)" % (self.__class__.__name__, self.args._backend(level))


@extend(node.cellarray)
def _backend(self, level=0):
    return "cellarray([%s])" % self.args._backend(level)


@extend(node.cellarrayref)
def _backend(self, level=0):
    return "%s[%s]" % (self.func_expr._backend(level), self.args._backend(level))


@extend(node.comment_stmt)
def _backend(self, level=0):
    s = self.value.strip()
    if not s:
        return ""
    if s[0] in "%#":
        return s.replace("%", "#")
    return self.value


@extend(node.concat_list)
def _backend(self, level=0):
    # import pdb; pdb.set_trace()
    return ",".join(["[%s]" % t._backend(level) for t in self])


@extend(node.continue_stmt)
def _backend(self, level=0):
    return "continue"


@extend(node.expr)
def _backend(self, level=0):
    if self.op in "~":
        return "logical_not(%s)" % self.args[0]._backend(level)

    if self.op == "&":
        return "logical_and(%s)" % self.args._backend(level)

    if self.op == "&&":
        return "%s and %s" % (
            self.args[0]._backend(level),
            self.args[1]._backend(level),
        )

    if self.op == "|":
        return "logical_or(%s)" % self.args._backend(level)

    if self.op == "||":
        return "%s or %s" % (self.args[0]._backend(level), self.args[1]._backend(level))

    if self.op == "@":  # FIXME
        return self.args[0]._backend(level)

    if self.op == "\\":
        return "linsolve(%s,%s)" % (
            self.args[0]._backend(level),
            self.args[1]._backend(level),
        )
    if self.op == "::":
        if not self.args:
            return ":"
        elif len(self.args) == 2:
            return "%s:%s" % (
                self.args[0]._backend(level),
                self.args[1]._backend(level),
            )
        elif len(self.args) == 3:
            return "%s:%s:%s" % (
                self.args[0]._backend(level),
                self.args[2]._backend(level),
                self.args[1]._backend(level),
            )
    if self.op == ":":
        return "arange(%s)" % self.args._backend(level)

    if self.op == "end":
        #        if self.args:
        #            return "%s.shape[%s]" % (self.args[0]._backend(level),
        #                                     self.args[1]._backend(level))
        #        else:
        return "end()"

    if self.op == ".":
        # import pdb; pdb.set_trace()
        try:
            is_parens = self.args[1].op == "parens"
        except:
            is_parens = False
        if not is_parens:
            return "%s%s" % (self.args[0]._backend(level), self.args[1]._backend(level))
        else:
            return "getattr(%s,%s)" % (
                self.args[0]._backend(level),
                self.args[1].args[0]._backend(level),
            )

    #     if self.op == "matrix":
    #         return "[%s]" % ",".join([t._backend(level) for t in self.args])
    if self.op == "parens":
        return "(%s)" % self.args[0]._backend(level)
    #    if self.op == "[]":
    #        return "[%s]" % self.args._backend(level)
    if not self.args:
        return self.op
    if len(self.args) == 1:
        return "%s %s" % (optable.get(self.op, self.op), self.args[0]._backend(level))
    if hasattr(self, "ret"):
        ret = f"{self.ret._backend(level)}="
        return ret + "%s(%s)" % (
            self.op,
            ",".join([t._backend(level) for t in self.args]),
        )
    op = " %s " % optable.get(self.op, self.op)
    return op.join([t._backend(level) for t in self.args])


@extend(node.expr_list)
def _backend(self, level=0):
    return ",".join([t._backend(level) for t in self])


@extend(node.expr_stmt)
def _backend(self, level=0):
    return self.expr._backend(level)


@extend(node.for_stmt)
def _backend(self, level=0):
    fmt = "for %s in %s.reshape(-1):%s"
    return fmt % (
        self.ident._backend(level),
        self.expr._backend(level),
        self.stmt_list._backend(level + 1),
    )


@extend(node.func_stmt)
def _backend(self, level=0):
    bindings = []
    STRUCTS.clear()
    if self.args and str((self.args[-1])) == "varargin":
        self.args[-1] = node.ident("*varargin")
        bindings.append(("nargin", "len(varargin)"))
    s = """
@function
def %s(%s):%s
""" % (
        self.ident._backend(level),
        self.args._backend(level),
        "\n    globals().update(load_all_vars())\n"
        + "".join(f"\n    {k} = {v}" for k, v in bindings),
    )
    return s


@extend(node.funcall)
def _backend(self, level=0):
    # import pdb; pdb.set_trace()
    f = self.func_expr._backend()
    if f == "eval":
        return "exec_(%s, globals(), locals())" % self.args._backend(level)
    if not self.nargout or self.nargout == 1:
        return "%s(%s)" % (f, self.args._backend(level))
    elif not self.args:
        return "%s(nargout=%s)" % (f, self.nargout)
    else:
        return "%s(%s,nargout=%s)" % (f, self.args._backend(level), self.nargout)


@extend(node.global_list)
def _backend(self, level=0):
    return ",".join([t._backend(level) for t in self])


@extend(node.ident)
def _backend(self, level=0):
    if self.name in reserved:
        self.name += "_"
    if self.init:
        return "%s=%s" % (self.name, self.init._backend(level))
    return self.name


@extend(node.if_stmt)
def _backend(self, level=0):
    s = "if %s:%s" % (
        self.cond_expr._backend(level),
        self.then_stmt._backend(level + 1),
    )
    if self.else_stmt:
        # Eech. This should have been handled in the parser.
        if self.else_stmt.__class__ == node.if_stmt:
            self.else_stmt = node.stmt_list([self.else_stmt])
        s += "\n" + indent * level
        s += "else:%s" % self.else_stmt._backend(level + 1)
    return s


@extend(node.lambda_expr)
def _backend(self, level=0):
    return "lambda %s: %s" % (self.args._backend(level), self.ret._backend(level))


@extend(node.let)
def _backend(self, level=0):
    if not options.no_numbers:
        t = "\n# %s:%s" % (options.filename, self.lineno)
    else:
        t = ""

    structs = set()
    def add_structs(n):
        if isinstance(n, node.expr) and n.op == ".":
            s = n.args[0]._backend()
            if s not in STRUCTS:
                STRUCTS.add(s)
                structs.add(s)
        elif isinstance(n, node.expr_list):
            for i in n:
                add_structs(i)

    s = ""
    if self.ret.__class__ is node.expr and self.ret.op == ".":
        try:
            if self.ret.args[1].op == "parens":
                s += "setattr(%s,%s,%s)" % (
                    self.ret.args[0]._backend(level),
                    self.ret.args[1].args[0]._backend(level),
                    self.args._backend(level),
                )
        except:
            s += "%s%s = copy(%s)" % (
                self.ret.args[0]._backend(level),
                self.ret.args[1]._backend(level),
                self.args._backend(level),
            )
        add_structs(self.ret)
    elif self.ret.__class__ is node.ident and self.args.__class__ is node.ident:
        s += "%s=copy(%s)" % (self.ret._backend(level), self.args._backend(level))
    elif isinstance(self.ret, node.ident) and self.ret.props == "W":
        s += "%s = matlabarray(%s)" % (
            self.ret._backend(level),
            self.args._backend(level),
        )
    elif isinstance(self.ret, node.arrayref) and not self.ret.func_expr.defs:
        name = self.ret.func_expr._backend(level)
        key = self.ret.args._backend(level)
        lhs = f"try: {name}\n"
        lhs += " " * (4 * level) + f"except: {name} = matlabarray()\n"
        lhs += " " * (4 * level) + f"{name}[{key}]"
        s += "%s = %s" % (lhs, self.args._backend(level))
    elif (
        isinstance(self.ret, node.arrayref)
        and self.args.__class__ is node.matrix
        and not self.args.args
    ):
        name = self.ret.func_expr._backend(level)
        key = self.ret.args._backend(level)
        s += f"{name} = {name}.delete({key})"
    else:
        s += "%s=%s" % (self.ret._backend(level), self.args._backend(level))
        add_structs(self.ret)
    for var in structs:
        s = f"{var} = check_struct({var})\n{' ' * 4 * level}" + s
    return s + t


@extend(node.logical)
def _backend(self, level=0):
    if self.value == 0:
        return "false"
    else:
        return "true"


@extend(node.matrix)
def _backend(self, level=0):
    # TODO empty array has shape of 0 0 in matlab
    # size([])
    # 0 0
    if not self.args:
        return "matlabarray([])"
    elif any(b.__class__ is node.string for a in self.args for b in a):
        return " + ".join(b._backend(level) for a in self.args for b in a)
    else:
        return "matlabarray([%s])" % self.args[0]._backend(level)


@extend(node.null_stmt)
def _backend(self, level=0):
    return ""


@extend(node.number)
def _backend(self, level=0):
    # if type(self.value) == int:
    #    return "%s.0" % self.value
    return str(self.value)


@extend(node.pass_stmt)
def _backend(self, level=0):
    return "pass"


@extend(node.persistent_stmt)  # FIXME
@extend(node.global_stmt)
def _backend(self, level=0):
    return "global %s" % self.global_list._backend(level)


@extend(node.return_stmt)
def _backend(self, level=0):
    if not self.ret:
        return "return"
    else:
        return "return %s" % self.ret._backend(level)


@extend(node.stmt_list)
def _backend(self, level=0):
    for t in self:
        if not isinstance(t, (node.null_stmt, node.comment_stmt)):
            break
    else:
        self.append(node.pass_stmt())
    sep = "\n" + indent * level
    return sep + sep.join([t._backend(level) for t in self])


@extend(node.string)
def _backend(self, level=0):
    return f"'{self.value}'"


@extend(node.sub)
def _backend(self, level=0):
    return "(%s-%s)" % (self.args[0]._backend(level), self.args[1]._backend(level))


@extend(node.transpose)
def _backend(self, level=0):
    return "%s.T" % self.args[0]._backend(level)


@extend(node.try_catch)
def _backend(self, level=0):
    fmt = "try:%s\n%sfinally:%s"
    return fmt % (
        self.try_stmt._backend(level + 1),
        indent * level,
        self.finally_stmt._backend(level + 1),
    )


@extend(node.while_stmt)
def _backend(self, level=0):
    fmt = "while %s:\n%s\n"
    return fmt % (self.cond_expr._backend(level), self.stmt_list._backend(level + 1))
