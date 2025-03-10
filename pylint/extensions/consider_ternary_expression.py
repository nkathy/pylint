"""Check for if / assign blocks that can be rewritten with if-expressions."""

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class ConsiderTernaryExpressionChecker(BaseChecker):

    __implements__ = (IAstroidChecker,)
    name = "consider_ternary_expression"
    msgs = {
        "W0160": (
            "Consider rewriting as a ternary expression",
            "consider-ternary-expression",
            "Multiple assign statements spread across if/else blocks can be "
            "rewritten with a single assignment and ternary expression",
        )
    }

    def visit_if(self, node: nodes.If) -> None:
        if isinstance(node.parent, nodes.If):
            return

        if len(node.body) != 1 or len(node.orelse) != 1:
            return

        bst = node.body[0]
        ost = node.orelse[0]

        if not isinstance(bst, nodes.Assign) or not isinstance(ost, nodes.Assign):
            return

        for (bname, oname) in zip(bst.targets, ost.targets):
            if not isinstance(bname, nodes.AssignName) or not isinstance(
                oname, nodes.AssignName
            ):
                return

            if bname.name != oname.name:
                return

        self.add_message("consider-ternary-expression", node=node)


def register(linter: "PyLinter") -> None:
    linter.register_checker(ConsiderTernaryExpressionChecker(linter))
