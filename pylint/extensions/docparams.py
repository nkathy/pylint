# Copyright (c) 2014-2015 Bruno Daniel <bruno.daniel@blue-yonder.com>
# Copyright (c) 2015-2020 Claudiu Popa <pcmanticore@gmail.com>
# Copyright (c) 2016-2019 Ashley Whetter <ashley@awhetter.co.uk>
# Copyright (c) 2016 Glenn Matthews <glenn@e-dad.net>
# Copyright (c) 2016 Glenn Matthews <glmatthe@cisco.com>
# Copyright (c) 2016 Moises Lopez <moylop260@vauxoo.com>
# Copyright (c) 2017 Ville Skyttä <ville.skytta@iki.fi>
# Copyright (c) 2017 John Paraskevopoulos <io.paraskev@gmail.com>
# Copyright (c) 2018, 2020 Anthony Sottile <asottile@umich.edu>
# Copyright (c) 2018 Jim Robertson <jrobertson98atx@gmail.com>
# Copyright (c) 2018 Sushobhit <31987769+sushobhit27@users.noreply.github.com>
# Copyright (c) 2018 Adam Dangoor <adamdangoor@gmail.com>
# Copyright (c) 2019, 2021 Pierre Sassoulas <pierre.sassoulas@gmail.com>
# Copyright (c) 2019 Hugo van Kemenade <hugovk@users.noreply.github.com>
# Copyright (c) 2020 Luigi <luigi.cristofolini@q-ctrl.com>
# Copyright (c) 2020 hippo91 <guillaume.peillex@gmail.com>
# Copyright (c) 2020 Damien Baty <damien.baty@polyconseil.fr>
# Copyright (c) 2021 Daniël van Noord <13665637+DanielNoord@users.noreply.github.com>
# Copyright (c) 2021 Konstantina Saketou <56515303+ksaketou@users.noreply.github.com>
# Copyright (c) 2021 SupImDos <62866982+SupImDos@users.noreply.github.com>
# Copyright (c) 2021 Marc Mueller <30130371+cdce8p@users.noreply.github.com>
# Copyright (c) 2021 Logan Miller <14319179+komodo472@users.noreply.github.com>

# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE

"""Pylint plugin for checking in Sphinx, Google, or Numpy style docstrings."""
import re
from typing import TYPE_CHECKING, Optional

import astroid
from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers import utils as checker_utils
from pylint.extensions import _check_docs_utils as utils
from pylint.extensions._check_docs_utils import Docstring
from pylint.interfaces import IAstroidChecker
from pylint.utils import get_global_option

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class DocstringParameterChecker(BaseChecker):
    """Checker for Sphinx, Google, or Numpy style docstrings.

    * Check that all function, method and constructor parameters are mentioned
      in the params and types part of the docstring.  Constructor parameters
      can be documented in either the class docstring or ``__init__`` docstring,
      but not both.
    * Check that there are no naming inconsistencies between the signature and
      the documentation, i.e. also report documented parameters that are missing
      in the signature. This is important to find cases where parameters are
      renamed only in the code, not in the documentation.
    * Check that all explicitly raised exceptions in a function are documented
      in the function docstring. Caught exceptions are ignored.

    Activate this checker by adding the line::

        load-plugins=pylint.extensions.docparams

    to the ``MASTER`` section of your ``.pylintrc``.
    """

    __implements__ = IAstroidChecker

    name = "parameter_documentation"
    msgs = {
        "W9005": (
            '"%s" has constructor parameters documented in class and __init__',
            "multiple-constructor-doc",
            "Please remove parameter declarations in the class or constructor.",
        ),
        "W9006": (
            '"%s" not documented as being raised',
            "missing-raises-doc",
            "Please document exceptions for all raised exception types.",
        ),
        "W9008": (
            "Redundant returns documentation",
            "redundant-returns-doc",
            "Please remove the return/rtype documentation from this method.",
        ),
        "W9010": (
            "Redundant yields documentation",
            "redundant-yields-doc",
            "Please remove the yields documentation from this method.",
        ),
        "W9011": (
            "Missing return documentation",
            "missing-return-doc",
            "Please add documentation about what this method returns.",
            {"old_names": [("W9007", "old-missing-returns-doc")]},
        ),
        "W9012": (
            "Missing return type documentation",
            "missing-return-type-doc",
            "Please document the type returned by this method.",
            # we can't use the same old_name for two different warnings
            # {'old_names': [('W9007', 'missing-returns-doc')]},
        ),
        "W9013": (
            "Missing yield documentation",
            "missing-yield-doc",
            "Please add documentation about what this generator yields.",
            {"old_names": [("W9009", "old-missing-yields-doc")]},
        ),
        "W9014": (
            "Missing yield type documentation",
            "missing-yield-type-doc",
            "Please document the type yielded by this method.",
            # we can't use the same old_name for two different warnings
            # {'old_names': [('W9009', 'missing-yields-doc')]},
        ),
        "W9015": (
            '"%s" missing in parameter documentation',
            "missing-param-doc",
            "Please add parameter declarations for all parameters.",
            {"old_names": [("W9003", "old-missing-param-doc")]},
        ),
        "W9016": (
            '"%s" missing in parameter type documentation',
            "missing-type-doc",
            "Please add parameter type declarations for all parameters.",
            {"old_names": [("W9004", "old-missing-type-doc")]},
        ),
        "W9017": (
            '"%s" differing in parameter documentation',
            "differing-param-doc",
            "Please check parameter names in declarations.",
        ),
        "W9018": (
            '"%s" differing in parameter type documentation',
            "differing-type-doc",
            "Please check parameter names in type declarations.",
        ),
        "W9019": (
            '"%s" useless ignored parameter documentation',
            "useless-param-doc",
            "Please remove the ignored parameter documentation.",
        ),
        "W9020": (
            '"%s" useless ignored parameter type documentation',
            "useless-type-doc",
            "Please remove the ignored parameter type documentation.",
        ),
        "W9021": (
            'Missing any documentation in "%s"',
            "missing-any-param-doc",
            "Please add parameter and/or type documentation.",
        ),
    }

    options = (
        (
            "accept-no-param-doc",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Whether to accept totally missing parameter "
                "documentation in the docstring of a function that has "
                "parameters.",
            },
        ),
        (
            "accept-no-raise-doc",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Whether to accept totally missing raises "
                "documentation in the docstring of a function that "
                "raises an exception.",
            },
        ),
        (
            "accept-no-return-doc",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Whether to accept totally missing return "
                "documentation in the docstring of a function that "
                "returns a statement.",
            },
        ),
        (
            "accept-no-yields-doc",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Whether to accept totally missing yields "
                "documentation in the docstring of a generator.",
            },
        ),
        (
            "default-docstring-type",
            {
                "type": "choice",
                "default": "default",
                "choices": list(utils.DOCSTRING_TYPES),
                "help": "If the docstring type cannot be guessed "
                "the specified docstring type will be used.",
            },
        ),
    )

    priority = -2

    constructor_names = {"__init__", "__new__"}
    not_needed_param_in_docstring = {"self", "cls"}

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Called for function and method definitions (def).

        :param node: Node for a function or method definition in the AST
        :type node: :class:`astroid.scoped_nodes.Function`
        """
        node_doc = utils.docstringify(node.doc_node, self.config.default_docstring_type)

        # skip functions that match the 'no-docstring-rgx' config option
        no_docstring_rgx = get_global_option(self, "no-docstring-rgx")
        if no_docstring_rgx and re.match(no_docstring_rgx, node.name):
            return

        # skip functions smaller than 'docstring-min-length'
        lines = checker_utils.get_node_last_lineno(node) - node.lineno
        max_lines = get_global_option(self, "docstring-min-length")
        if max_lines > -1 and lines < max_lines:
            return

        self.check_functiondef_params(node, node_doc)
        self.check_functiondef_returns(node, node_doc)
        self.check_functiondef_yields(node, node_doc)

    visit_asyncfunctiondef = visit_functiondef

    def check_functiondef_params(self, node, node_doc):
        node_allow_no_param = None
        if node.name in self.constructor_names:
            class_node = checker_utils.node_frame_class(node)
            if class_node is not None:
                class_doc = utils.docstringify(
                    class_node.doc_node, self.config.default_docstring_type
                )
                self.check_single_constructor_params(class_doc, node_doc, class_node)

                # __init__ or class docstrings can have no parameters documented
                # as long as the other documents them.
                node_allow_no_param = (
                    class_doc.has_params()
                    or class_doc.params_documented_elsewhere()
                    or None
                )
                class_allow_no_param = (
                    node_doc.has_params()
                    or node_doc.params_documented_elsewhere()
                    or None
                )

                self.check_arguments_in_docstring(
                    class_doc, node.args, class_node, class_allow_no_param
                )

        self.check_arguments_in_docstring(
            node_doc, node.args, node, node_allow_no_param
        )

    def check_functiondef_returns(self, node, node_doc):
        if (not node_doc.supports_yields and node.is_generator()) or node.is_abstract():
            return

        return_nodes = node.nodes_of_class(astroid.Return)
        if (node_doc.has_returns() or node_doc.has_rtype()) and not any(
            utils.returns_something(ret_node) for ret_node in return_nodes
        ):
            self.add_message("redundant-returns-doc", node=node)

    def check_functiondef_yields(self, node, node_doc):
        if not node_doc.supports_yields or node.is_abstract():
            return

        if (
            node_doc.has_yields() or node_doc.has_yields_type()
        ) and not node.is_generator():
            self.add_message("redundant-yields-doc", node=node)

    def visit_raise(self, node: nodes.Raise) -> None:
        func_node = node.frame(future=True)
        if not isinstance(func_node, astroid.FunctionDef):
            return

        expected_excs = utils.possible_exc_types(node)

        if not expected_excs:
            return

        if not func_node.doc_node:
            # If this is a property setter,
            # the property should have the docstring instead.
            property_ = utils.get_setters_property(func_node)
            if property_:
                func_node = property_

        doc = utils.docstringify(func_node.doc_node, self.config.default_docstring_type)
        if not doc.matching_sections():
            if doc.doc:
                missing = {exc.name for exc in expected_excs}
                self._handle_no_raise_doc(missing, func_node)
            return

        found_excs_full_names = doc.exceptions()

        # Extract just the class name, e.g. "error" from "re.error"
        found_excs_class_names = {exc.split(".")[-1] for exc in found_excs_full_names}

        missing_excs = set()
        for expected in expected_excs:
            for found_exc in found_excs_class_names:
                if found_exc == expected.name:
                    break
                if any(found_exc == ancestor.name for ancestor in expected.ancestors()):
                    break
            else:
                missing_excs.add(expected.name)

        self._add_raise_message(missing_excs, func_node)

    def visit_return(self, node: nodes.Return) -> None:
        if not utils.returns_something(node):
            return

        if self.config.accept_no_return_doc:
            return

        func_node = node.frame(future=True)
        if not isinstance(func_node, astroid.FunctionDef):
            return

        doc = utils.docstringify(func_node.doc_node, self.config.default_docstring_type)

        is_property = checker_utils.decorated_with_property(func_node)

        if not (doc.has_returns() or (doc.has_property_returns() and is_property)):
            self.add_message("missing-return-doc", node=func_node)

        if func_node.returns:
            return

        if not (doc.has_rtype() or (doc.has_property_type() and is_property)):
            self.add_message("missing-return-type-doc", node=func_node)

    def visit_yield(self, node: nodes.Yield) -> None:
        if self.config.accept_no_yields_doc:
            return

        func_node = node.frame(future=True)
        if not isinstance(func_node, astroid.FunctionDef):
            return

        doc = utils.docstringify(func_node.doc_node, self.config.default_docstring_type)

        if doc.supports_yields:
            doc_has_yields = doc.has_yields()
            doc_has_yields_type = doc.has_yields_type()
        else:
            doc_has_yields = doc.has_returns()
            doc_has_yields_type = doc.has_rtype()

        if not doc_has_yields:
            self.add_message("missing-yield-doc", node=func_node)

        if not (doc_has_yields_type or func_node.returns):
            self.add_message("missing-yield-type-doc", node=func_node)

    def visit_yieldfrom(self, node: nodes.YieldFrom) -> None:
        self.visit_yield(node)

    def _compare_missing_args(
        self,
        found_argument_names,
        message_id,
        not_needed_names,
        expected_argument_names,
        warning_node,
    ):
        """Compare the found argument names with the expected ones and
        generate a message if there are arguments missing.

        :param found_argument_names: argument names found in the docstring
        :type found_argument_names: set

        :param message_id: pylint message id
        :type message_id: str

        :param not_needed_names: names that may be omitted
        :type not_needed_names: set

        :param expected_argument_names: Expected argument names
        :type expected_argument_names: set

        :param warning_node: The node to be analyzed
        :type warning_node: :class:`astroid.scoped_nodes.Node`
        """
        missing_argument_names = (
            expected_argument_names - found_argument_names
        ) - not_needed_names
        if missing_argument_names:
            self.add_message(
                message_id,
                args=(", ".join(sorted(missing_argument_names)),),
                node=warning_node,
            )

    def _compare_different_args(
        self,
        found_argument_names,
        message_id,
        not_needed_names,
        expected_argument_names,
        warning_node,
    ):
        """Compare the found argument names with the expected ones and
        generate a message if there are extra arguments found.

        :param found_argument_names: argument names found in the docstring
        :type found_argument_names: set

        :param message_id: pylint message id
        :type message_id: str

        :param not_needed_names: names that may be omitted
        :type not_needed_names: set

        :param expected_argument_names: Expected argument names
        :type expected_argument_names: set

        :param warning_node: The node to be analyzed
        :type warning_node: :class:`astroid.scoped_nodes.Node`
        """
        differing_argument_names = (
            (expected_argument_names ^ found_argument_names)
            - not_needed_names
            - expected_argument_names
        )

        if differing_argument_names:
            self.add_message(
                message_id,
                args=(", ".join(sorted(differing_argument_names)),),
                node=warning_node,
            )

    def _compare_ignored_args(
        self,
        found_argument_names,
        message_id,
        ignored_argument_names,
        warning_node,
    ):
        """Compare the found argument names with the ignored ones and
        generate a message if there are ignored arguments found.

        :param found_argument_names: argument names found in the docstring
        :type found_argument_names: set

        :param message_id: pylint message id
        :type message_id: str

        :param ignored_argument_names: Expected argument names
        :type ignored_argument_names: set

        :param warning_node: The node to be analyzed
        :type warning_node: :class:`astroid.scoped_nodes.Node`
        """
        existing_ignored_argument_names = ignored_argument_names & found_argument_names

        if existing_ignored_argument_names:
            self.add_message(
                message_id,
                args=(", ".join(sorted(existing_ignored_argument_names)),),
                node=warning_node,
            )

    def check_arguments_in_docstring(
        self,
        doc: Docstring,
        arguments_node: astroid.Arguments,
        warning_node: astroid.NodeNG,
        accept_no_param_doc: Optional[bool] = None,
    ):
        """Check that all parameters are consistent with the parameters mentioned
        in the parameter documentation (e.g. the Sphinx tags 'param' and 'type').

        * Undocumented parameters except 'self' are noticed.
        * Undocumented parameter types except for 'self' and the ``*<args>``
          and ``**<kwargs>`` parameters are noticed.
        * Parameters mentioned in the parameter documentation that don't or no
          longer exist in the function parameter list are noticed.
        * If the text "For the parameters, see" or "For the other parameters,
          see" (ignoring additional whitespace) is mentioned in the docstring,
          missing parameter documentation is tolerated.
        * If there's no Sphinx style, Google style or NumPy style parameter
          documentation at all, i.e. ``:param`` is never mentioned etc., the
          checker assumes that the parameters are documented in another format
          and the absence is tolerated.

        :param doc: Docstring for the function, method or class.
        :type doc: :class:`Docstring`

        :param arguments_node: Arguments node for the function, method or
            class constructor.
        :type arguments_node: :class:`astroid.scoped_nodes.Arguments`

        :param warning_node: The node to assign the warnings to
        :type warning_node: :class:`astroid.scoped_nodes.Node`

        :param accept_no_param_doc: Whether to allow no parameters to be
            documented. If None then this value is read from the configuration.
        :type accept_no_param_doc: bool or None
        """
        # Tolerate missing param or type declarations if there is a link to
        # another method carrying the same name.
        if not doc.doc:
            return

        if accept_no_param_doc is None:
            accept_no_param_doc = self.config.accept_no_param_doc
        tolerate_missing_params = doc.params_documented_elsewhere()

        # Collect the function arguments.
        expected_argument_names = {arg.name for arg in arguments_node.args}
        expected_argument_names.update(arg.name for arg in arguments_node.kwonlyargs)
        not_needed_type_in_docstring = self.not_needed_param_in_docstring.copy()

        expected_but_ignored_argument_names = set()
        ignored_argument_names = get_global_option(self, "ignored-argument-names")
        if ignored_argument_names:
            expected_but_ignored_argument_names = {
                arg
                for arg in expected_argument_names
                if ignored_argument_names.match(arg)
            }

        if arguments_node.vararg is not None:
            expected_argument_names.add(f"*{arguments_node.vararg}")
            not_needed_type_in_docstring.add(f"*{arguments_node.vararg}")
        if arguments_node.kwarg is not None:
            expected_argument_names.add(f"**{arguments_node.kwarg}")
            not_needed_type_in_docstring.add(f"**{arguments_node.kwarg}")
        params_with_doc, params_with_type = doc.match_param_docs()
        # Tolerate no parameter documentation at all.
        if not params_with_doc and not params_with_type and accept_no_param_doc:
            tolerate_missing_params = True

        # This is before the update of param_with_type because this must check only
        # the type documented in a docstring, not the one using pep484
        # See #4117 and #4593
        self._compare_ignored_args(
            params_with_type,
            "useless-type-doc",
            expected_but_ignored_argument_names,
            warning_node,
        )
        for index, arg_name in enumerate(arguments_node.args):
            if arguments_node.annotations[index]:
                params_with_type.add(arg_name.name)
        for index, arg_name in enumerate(arguments_node.kwonlyargs):
            if arguments_node.kwonlyargs_annotations[index]:
                params_with_type.add(arg_name.name)

        if not tolerate_missing_params:
            missing_param_doc = (expected_argument_names - params_with_doc) - (
                self.not_needed_param_in_docstring | expected_but_ignored_argument_names
            )
            missing_type_doc = (expected_argument_names - params_with_type) - (
                not_needed_type_in_docstring | expected_but_ignored_argument_names
            )
            if (
                missing_param_doc == expected_argument_names == missing_type_doc
                and len(expected_argument_names) != 0
            ):
                self.add_message(
                    "missing-any-param-doc",
                    args=(warning_node.name,),
                    node=warning_node,
                )
            else:
                self._compare_missing_args(
                    params_with_doc,
                    "missing-param-doc",
                    self.not_needed_param_in_docstring
                    | expected_but_ignored_argument_names,
                    expected_argument_names,
                    warning_node,
                )
                self._compare_missing_args(
                    params_with_type,
                    "missing-type-doc",
                    not_needed_type_in_docstring | expected_but_ignored_argument_names,
                    expected_argument_names,
                    warning_node,
                )

        self._compare_different_args(
            params_with_doc,
            "differing-param-doc",
            self.not_needed_param_in_docstring,
            expected_argument_names,
            warning_node,
        )
        self._compare_different_args(
            params_with_type,
            "differing-type-doc",
            not_needed_type_in_docstring,
            expected_argument_names,
            warning_node,
        )
        self._compare_ignored_args(
            params_with_doc,
            "useless-param-doc",
            expected_but_ignored_argument_names,
            warning_node,
        )

    def check_single_constructor_params(self, class_doc, init_doc, class_node):
        if class_doc.has_params() and init_doc.has_params():
            self.add_message(
                "multiple-constructor-doc", args=(class_node.name,), node=class_node
            )

    def _handle_no_raise_doc(self, excs, node):
        if self.config.accept_no_raise_doc:
            return

        self._add_raise_message(excs, node)

    def _add_raise_message(self, missing_excs, node):
        """Adds a message on :param:`node` for the missing exception type.

        :param missing_excs: A list of missing exception types.
        :type missing_excs: set(str)

        :param node: The node show the message on.
        :type node: nodes.NodeNG
        """
        if node.is_abstract():
            try:
                missing_excs.remove("NotImplementedError")
            except KeyError:
                pass

        if not missing_excs:
            return

        self.add_message(
            "missing-raises-doc", args=(", ".join(sorted(missing_excs)),), node=node
        )


def register(linter: "PyLinter") -> None:
    linter.register_checker(DocstringParameterChecker(linter))
