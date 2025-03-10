# Copyright (c) 2006-2011, 2013-2014 LOGILAB S.A. (Paris, FRANCE) <contact@logilab.fr>
# Copyright (c) 2011-2014 Google, Inc.
# Copyright (c) 2012 Tim Hatch <tim@timhatch.com>
# Copyright (c) 2013-2020 Claudiu Popa <pcmanticore@gmail.com>
# Copyright (c) 2014 Brett Cannon <brett@python.org>
# Copyright (c) 2014 Arun Persaud <arun@nubati.net>
# Copyright (c) 2015 Rene Zhang <rz99@cornell.edu>
# Copyright (c) 2015 Florian Bruhin <me@the-compiler.org>
# Copyright (c) 2015 Steven Myint <hg@stevenmyint.com>
# Copyright (c) 2015 Ionel Cristian Maries <contact@ionelmc.ro>
# Copyright (c) 2016 Erik <erik.eriksson@yahoo.com>
# Copyright (c) 2016 Jakub Wilk <jwilk@jwilk.net>
# Copyright (c) 2017 Łukasz Rogalski <rogalski.91@gmail.com>
# Copyright (c) 2017 Martin von Gagern <gagern@google.com>
# Copyright (c) 2018 Lucas Cimon <lucas.cimon@gmail.com>
# Copyright (c) 2018 ssolanki <sushobhitsolanki@gmail.com>
# Copyright (c) 2018 Natalie Serebryakova <natalie.serebryakova@Natalies-MacBook-Pro.local>
# Copyright (c) 2018 Sushobhit <31987769+sushobhit27@users.noreply.github.com>
# Copyright (c) 2018 Carey Metcalfe <carey@cmetcalfe.ca>
# Copyright (c) 2018 Mike Frysinger <vapier@gmail.com>
# Copyright (c) 2018 Alexander Todorov <atodorov@otb.bg>
# Copyright (c) 2018 Ville Skyttä <ville.skytta@iki.fi>
# Copyright (c) 2019, 2021 Pierre Sassoulas <pierre.sassoulas@gmail.com>
# Copyright (c) 2019 Djailla <bastien.vallet@gmail.com>
# Copyright (c) 2019 Hugo van Kemenade <hugovk@users.noreply.github.com>
# Copyright (c) 2020 hippo91 <guillaume.peillex@gmail.com>
# Copyright (c) 2020 Ram Rachum <ram@rachum.com>
# Copyright (c) 2020 Anthony Sottile <asottile@umich.edu>
# Copyright (c) 2021 Daniël van Noord <13665637+DanielNoord@users.noreply.github.com>
# Copyright (c) 2021 Nick Drozd <nicholasdrozd@gmail.com>
# Copyright (c) 2021 Marc Mueller <30130371+cdce8p@users.noreply.github.com>

# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE

"""Checks for various exception related errors."""
import builtins
import inspect
from typing import TYPE_CHECKING, Any, List, Optional

import astroid
from astroid import nodes, objects

from pylint import checkers, interfaces
from pylint.checkers import utils

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def _builtin_exceptions():
    def predicate(obj):
        return isinstance(obj, type) and issubclass(obj, BaseException)

    members = inspect.getmembers(builtins, predicate)
    return {exc.__name__ for (_, exc) in members}


def _annotated_unpack_infer(stmt, context=None):
    """Recursively generate nodes inferred by the given statement.

    If the inferred value is a list or a tuple, recurse on the elements.
    Returns an iterator which yields tuples in the format
    ('original node', 'inferred node').
    """
    if isinstance(stmt, (nodes.List, nodes.Tuple)):
        for elt in stmt.elts:
            inferred = utils.safe_infer(elt)
            if inferred and inferred is not astroid.Uninferable:
                yield elt, inferred
        return
    for inferred in stmt.infer(context):
        if inferred is astroid.Uninferable:
            continue
        yield stmt, inferred


def _is_raising(body: List) -> bool:
    """Return whether the given statement node raises an exception."""
    return any(isinstance(node, nodes.Raise) for node in body)


OVERGENERAL_EXCEPTIONS = ("BaseException", "Exception")

MSGS = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    "E0701": (
        "Bad except clauses order (%s)",
        "bad-except-order",
        "Used when except clauses are not in the correct order (from the "
        "more specific to the more generic). If you don't fix the order, "
        "some exceptions may not be caught by the most specific handler.",
    ),
    "E0702": (
        "Raising %s while only classes or instances are allowed",
        "raising-bad-type",
        "Used when something which is neither a class, an instance or a "
        "string is raised (i.e. a `TypeError` will be raised).",
    ),
    "E0703": (
        "Exception context set to something which is not an exception, nor None",
        "bad-exception-context",
        'Used when using the syntax "raise ... from ...", '
        "where the exception context is not an exception, "
        "nor None.",
    ),
    "E0704": (
        "The raise statement is not inside an except clause",
        "misplaced-bare-raise",
        "Used when a bare raise is not used inside an except clause. "
        "This generates an error, since there are no active exceptions "
        "to be reraised. An exception to this rule is represented by "
        "a bare raise inside a finally clause, which might work, as long "
        "as an exception is raised inside the try block, but it is "
        "nevertheless a code smell that must not be relied upon.",
    ),
    "E0710": (
        "Raising a new style class which doesn't inherit from BaseException",
        "raising-non-exception",
        "Used when a new style class which doesn't inherit from "
        "BaseException is raised.",
    ),
    "E0711": (
        "NotImplemented raised - should raise NotImplementedError",
        "notimplemented-raised",
        "Used when NotImplemented is raised instead of NotImplementedError",
    ),
    "E0712": (
        "Catching an exception which doesn't inherit from Exception: %s",
        "catching-non-exception",
        "Used when a class which doesn't inherit from "
        "Exception is used as an exception in an except clause.",
    ),
    "W0702": (
        "No exception type(s) specified",
        "bare-except",
        "Used when an except clause doesn't specify exceptions type to catch.",
    ),
    "W0703": (
        "Catching too general exception %s",
        "broad-except",
        "Used when an except catches a too general exception, "
        "possibly burying unrelated errors.",
    ),
    "W0705": (
        "Catching previously caught exception type %s",
        "duplicate-except",
        "Used when an except catches a type that was already caught by "
        "a previous handler.",
    ),
    "W0706": (
        "The except handler raises immediately",
        "try-except-raise",
        "Used when an except handler uses raise as its first or only "
        "operator. This is useless because it raises back the exception "
        "immediately. Remove the raise operator or the entire "
        "try-except-raise block!",
    ),
    "W0707": (
        "Consider explicitly re-raising using the 'from' keyword",
        "raise-missing-from",
        "Python 3's exception chaining means it shows the traceback of the "
        "current exception, but also the original exception. Not using `raise "
        "from` makes the traceback inaccurate, because the message implies "
        "there is a bug in the exception-handling code itself, which is a "
        "separate situation than wrapping an exception.",
    ),
    "W0711": (
        'Exception to catch is the result of a binary "%s" operation',
        "binary-op-exception",
        "Used when the exception to catch is of the form "
        '"except A or B:".  If intending to catch multiple, '
        'rewrite as "except (A, B):"',
    ),
    "W0715": (
        "Exception arguments suggest string formatting might be intended",
        "raising-format-tuple",
        "Used when passing multiple arguments to an exception "
        "constructor, the first of them a string literal containing what "
        "appears to be placeholders intended for formatting",
    ),
    "W0716": (
        "Invalid exception operation. %s",
        "wrong-exception-operation",
        "Used when an operation is done against an exception, but the operation "
        "is not valid for the exception in question. Usually emitted when having "
        "binary operations between exceptions in except handlers.",
    ),
}


class BaseVisitor:
    """Base class for visitors defined in this module."""

    def __init__(self, checker, node):
        self._checker = checker
        self._node = node

    def visit(self, node):
        name = node.__class__.__name__.lower()
        dispatch_meth = getattr(self, "visit_" + name, None)
        if dispatch_meth:
            dispatch_meth(node)
        else:
            self.visit_default(node)

    def visit_default(self, _: nodes.NodeNG) -> None:
        """Default implementation for all the nodes."""


class ExceptionRaiseRefVisitor(BaseVisitor):
    """Visit references (anything that is not an AST leaf)."""

    def visit_name(self, node: nodes.Name) -> None:
        if node.name == "NotImplemented":
            self._checker.add_message("notimplemented-raised", node=self._node)

    def visit_call(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Name):
            self.visit_name(node.func)
        if (
            len(node.args) > 1
            and isinstance(node.args[0], nodes.Const)
            and isinstance(node.args[0].value, str)
        ):
            msg = node.args[0].value
            if "%" in msg or ("{" in msg and "}" in msg):
                self._checker.add_message("raising-format-tuple", node=self._node)


class ExceptionRaiseLeafVisitor(BaseVisitor):
    """Visitor for handling leaf kinds of a raise value."""

    def visit_const(self, node: nodes.Const) -> None:
        self._checker.add_message(
            "raising-bad-type", node=self._node, args=node.value.__class__.__name__
        )

    def visit_instance(self, instance: objects.ExceptionInstance) -> None:
        cls = instance._proxied
        self.visit_classdef(cls)

    # Exception instances have a particular class type
    visit_exceptioninstance = visit_instance

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        if not utils.inherit_from_std_ex(node) and utils.has_known_bases(node):
            if node.newstyle:
                self._checker.add_message("raising-non-exception", node=self._node)

    def visit_tuple(self, _: nodes.Tuple) -> None:
        self._checker.add_message("raising-bad-type", node=self._node, args="tuple")

    def visit_default(self, node: nodes.NodeNG) -> None:
        name = getattr(node, "name", node.__class__.__name__)
        self._checker.add_message("raising-bad-type", node=self._node, args=name)


class ExceptionsChecker(checkers.BaseChecker):
    """Exception related checks."""

    __implements__ = interfaces.IAstroidChecker

    name = "exceptions"
    msgs = MSGS
    priority = -4
    options = (
        (
            "overgeneral-exceptions",
            {
                "default": OVERGENERAL_EXCEPTIONS,
                "type": "csv",
                "metavar": "<comma-separated class names>",
                "help": "Exceptions that will emit a warning "  # pylint: disable=consider-using-f-string
                'when being caught. Defaults to "%s".'
                % (", ".join(OVERGENERAL_EXCEPTIONS),),
            },
        ),
    )

    def open(self):
        self._builtin_exceptions = _builtin_exceptions()
        super().open()

    @utils.check_messages(
        "misplaced-bare-raise",
        "raising-bad-type",
        "raising-non-exception",
        "notimplemented-raised",
        "bad-exception-context",
        "raising-format-tuple",
        "raise-missing-from",
    )
    def visit_raise(self, node: nodes.Raise) -> None:
        if node.exc is None:
            self._check_misplaced_bare_raise(node)
            return

        if node.cause is None:
            self._check_raise_missing_from(node)
        else:
            self._check_bad_exception_context(node)

        expr = node.exc
        ExceptionRaiseRefVisitor(self, node).visit(expr)

        try:
            inferred_value = expr.inferred()[-1]
        except astroid.InferenceError:
            pass
        else:
            if inferred_value:
                ExceptionRaiseLeafVisitor(self, node).visit(inferred_value)

    def _check_misplaced_bare_raise(self, node):
        # Filter out if it's present in __exit__.
        scope = node.scope()
        if (
            isinstance(scope, nodes.FunctionDef)
            and scope.is_method()
            and scope.name == "__exit__"
        ):
            return

        current = node
        # Stop when a new scope is generated or when the raise
        # statement is found inside a TryFinally.
        ignores = (nodes.ExceptHandler, nodes.FunctionDef)
        while current and not isinstance(current.parent, ignores):
            current = current.parent

        expected = (nodes.ExceptHandler,)
        if not current or not isinstance(current.parent, expected):
            self.add_message("misplaced-bare-raise", node=node)

    def _check_bad_exception_context(self, node: nodes.Raise) -> None:
        """Verify that the exception context is properly set.

        An exception context can be only `None` or an exception.
        """
        cause = utils.safe_infer(node.cause)
        if cause in (astroid.Uninferable, None):
            return

        if isinstance(cause, nodes.Const):
            if cause.value is not None:
                self.add_message("bad-exception-context", node=node)
        elif not isinstance(cause, nodes.ClassDef) and not utils.inherit_from_std_ex(
            cause
        ):
            self.add_message("bad-exception-context", node=node)

    def _check_raise_missing_from(self, node: nodes.Raise) -> None:
        if node.exc is None:
            # This is a plain `raise`, raising the previously-caught exception. No need for a
            # cause.
            return
        # We'd like to check whether we're inside an `except` clause:
        containing_except_node = utils.find_except_wrapper_node_in_scope(node)
        if not containing_except_node:
            return
        # We found a surrounding `except`! We're almost done proving there's a
        # `raise-missing-from` here. The only thing we need to protect against is that maybe
        # the `raise` is raising the exception that was caught, possibly with some shenanigans
        # like `exc.with_traceback(whatever)`. We won't analyze these, we'll just assume
        # there's a violation on two simple cases: `raise SomeException(whatever)` and `raise
        # SomeException`.
        if containing_except_node.name is None:
            # The `except` doesn't have an `as exception:` part, meaning there's no way that
            # the `raise` is raising the same exception.
            self.add_message("raise-missing-from", node=node)
        elif isinstance(node.exc, nodes.Call) and isinstance(node.exc.func, nodes.Name):
            # We have a `raise SomeException(whatever)`.
            self.add_message("raise-missing-from", node=node)
        elif (
            isinstance(node.exc, nodes.Name)
            and node.exc.name != containing_except_node.name.name
        ):
            # We have a `raise SomeException`.
            self.add_message("raise-missing-from", node=node)

    def _check_catching_non_exception(self, handler, exc, part):
        if isinstance(exc, nodes.Tuple):
            # Check if it is a tuple of exceptions.
            inferred = [utils.safe_infer(elt) for elt in exc.elts]
            if any(node is astroid.Uninferable for node in inferred):
                # Don't emit if we don't know every component.
                return
            if all(
                node
                and (utils.inherit_from_std_ex(node) or not utils.has_known_bases(node))
                for node in inferred
            ):
                return

        if not isinstance(exc, nodes.ClassDef):
            # Don't emit the warning if the inferred stmt
            # is None, but the exception handler is something else,
            # maybe it was redefined.
            if isinstance(exc, nodes.Const) and exc.value is None:
                if (
                    isinstance(handler.type, nodes.Const) and handler.type.value is None
                ) or handler.type.parent_of(exc):
                    # If the exception handler catches None or
                    # the exception component, which is None, is
                    # defined by the entire exception handler, then
                    # emit a warning.
                    self.add_message(
                        "catching-non-exception",
                        node=handler.type,
                        args=(part.as_string(),),
                    )
            else:
                self.add_message(
                    "catching-non-exception",
                    node=handler.type,
                    args=(part.as_string(),),
                )
            return

        if (
            not utils.inherit_from_std_ex(exc)
            and exc.name not in self._builtin_exceptions
        ):
            if utils.has_known_bases(exc):
                self.add_message(
                    "catching-non-exception", node=handler.type, args=(exc.name,)
                )

    def _check_try_except_raise(self, node):
        def gather_exceptions_from_handler(
            handler,
        ) -> Optional[List[nodes.NodeNG]]:
            exceptions: List[nodes.NodeNG] = []
            if handler.type:
                exceptions_in_handler = utils.safe_infer(handler.type)
                if isinstance(exceptions_in_handler, nodes.Tuple):
                    exceptions = list(
                        {
                            exception
                            for exception in exceptions_in_handler.elts
                            if isinstance(exception, nodes.Name)
                        }
                    )
                elif exceptions_in_handler:
                    exceptions = [exceptions_in_handler]
                else:
                    # Break when we cannot infer anything reliably.
                    return None
            return exceptions

        bare_raise = False
        handler_having_bare_raise = None
        exceptions_in_bare_handler = []
        for handler in node.handlers:
            if bare_raise:
                # check that subsequent handler is not parent of handler which had bare raise.
                # since utils.safe_infer can fail for bare except, check it before.
                # also break early if bare except is followed by bare except.

                excs_in_current_handler = gather_exceptions_from_handler(handler)
                if not excs_in_current_handler:
                    break
                if exceptions_in_bare_handler is None:
                    # It can be `None` when the inference failed
                    break
                for exc_in_current_handler in excs_in_current_handler:
                    inferred_current = utils.safe_infer(exc_in_current_handler)
                    if any(
                        utils.is_subclass_of(utils.safe_infer(e), inferred_current)
                        for e in exceptions_in_bare_handler
                    ):
                        bare_raise = False
                        break

            # `raise` as the first operator inside the except handler
            if _is_raising([handler.body[0]]):
                # flags when there is a bare raise
                if handler.body[0].exc is None:
                    bare_raise = True
                    handler_having_bare_raise = handler
                    exceptions_in_bare_handler = gather_exceptions_from_handler(handler)
        else:
            if bare_raise:
                self.add_message("try-except-raise", node=handler_having_bare_raise)

    @utils.check_messages("wrong-exception-operation")
    def visit_binop(self, node: nodes.BinOp) -> None:
        if isinstance(node.parent, nodes.ExceptHandler):
            # except (V | A)
            suggestion = f"Did you mean '({node.left.as_string()}, {node.right.as_string()})' instead?"
            self.add_message("wrong-exception-operation", node=node, args=(suggestion,))

    @utils.check_messages("wrong-exception-operation")
    def visit_compare(self, node: nodes.Compare) -> None:
        if isinstance(node.parent, nodes.ExceptHandler):
            # except (V < A)
            suggestion = f"Did you mean '({node.left.as_string()}, {', '.join(operand.as_string() for _, operand in node.ops)})' instead?"
            self.add_message("wrong-exception-operation", node=node, args=(suggestion,))

    @utils.check_messages(
        "bare-except",
        "broad-except",
        "try-except-raise",
        "binary-op-exception",
        "bad-except-order",
        "catching-non-exception",
        "duplicate-except",
    )
    def visit_tryexcept(self, node: nodes.TryExcept) -> None:
        """Check for empty except."""
        self._check_try_except_raise(node)
        exceptions_classes: List[Any] = []
        nb_handlers = len(node.handlers)
        for index, handler in enumerate(node.handlers):
            if handler.type is None:
                if not _is_raising(handler.body):
                    self.add_message("bare-except", node=handler)

                # check if an "except:" is followed by some other
                # except
                if index < (nb_handlers - 1):
                    msg = "empty except clause should always appear last"
                    self.add_message("bad-except-order", node=node, args=msg)

            elif isinstance(handler.type, nodes.BoolOp):
                self.add_message(
                    "binary-op-exception", node=handler, args=handler.type.op
                )
            else:
                try:
                    exceptions = list(_annotated_unpack_infer(handler.type))
                except astroid.InferenceError:
                    continue

                for part, exception in exceptions:
                    if exception is astroid.Uninferable:
                        continue
                    if isinstance(
                        exception, astroid.Instance
                    ) and utils.inherit_from_std_ex(exception):
                        exception = exception._proxied

                    self._check_catching_non_exception(handler, exception, part)

                    if not isinstance(exception, nodes.ClassDef):
                        continue

                    exc_ancestors = [
                        anc
                        for anc in exception.ancestors()
                        if isinstance(anc, nodes.ClassDef)
                    ]

                    for previous_exc in exceptions_classes:
                        if previous_exc in exc_ancestors:
                            msg = f"{previous_exc.name} is an ancestor class of {exception.name}"
                            self.add_message(
                                "bad-except-order", node=handler.type, args=msg
                            )
                    if (
                        exception.name in self.config.overgeneral_exceptions
                        and exception.root().name == utils.EXCEPTIONS_MODULE
                        and not _is_raising(handler.body)
                    ):
                        self.add_message(
                            "broad-except", args=exception.name, node=handler.type
                        )

                    if exception in exceptions_classes:
                        self.add_message(
                            "duplicate-except", args=exception.name, node=handler.type
                        )

                exceptions_classes += [exc for _, exc in exceptions]


def register(linter: "PyLinter") -> None:
    linter.register_checker(ExceptionsChecker(linter))
