# Copyright (c) 2015-2020 Claudiu Popa <pcmanticore@gmail.com>
# Copyright (c) 2017 Łukasz Rogalski <rogalski.91@gmail.com>
# Copyright (c) 2018 ssolanki <sushobhitsolanki@gmail.com>
# Copyright (c) 2018 Ville Skyttä <ville.skytta@iki.fi>
# Copyright (c) 2019-2021 Pierre Sassoulas <pierre.sassoulas@gmail.com>
# Copyright (c) 2019 Hugo van Kemenade <hugovk@users.noreply.github.com>
# Copyright (c) 2020 hippo91 <guillaume.peillex@gmail.com>
# Copyright (c) 2020 Anthony Sottile <asottile@umich.edu>
# Copyright (c) 2021 Daniël van Noord <13665637+DanielNoord@users.noreply.github.com>
# Copyright (c) 2021 Marc Mueller <30130371+cdce8p@users.noreply.github.com>
# Copyright (c) 2021 Nick Drozd <nicholasdrozd@gmail.com>
# Copyright (c) 2021 Mark Byrne <31762852+mbyrnepr2@users.noreply.github.com>

# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE

"""Visitor doing some postprocessing on the astroid tree.

Try to resolve definitions (namespace) dictionary, relationship...
"""
import collections
import os
import traceback

import astroid
from astroid import nodes

from pylint.pyreverse import utils


def _iface_hdlr(_):
    """Handler used by interfaces to handle suspicious interface nodes."""
    return True


def _astroid_wrapper(func, modname):
    print(f"parsing {modname}...")
    try:
        return func(modname)
    except astroid.exceptions.AstroidBuildingException as exc:
        print(exc)
    except Exception:  # pylint: disable=broad-except
        traceback.print_exc()
    return None


def interfaces(node, herited=True, handler_func=_iface_hdlr):
    """Return an iterator on interfaces implemented by the given class node."""
    try:
        implements = astroid.bases.Instance(node).getattr("__implements__")[0]
    except astroid.exceptions.NotFoundError:
        return
    if not herited and implements.frame(future=True) is not node:
        return
    found = set()
    missing = False
    for iface in nodes.unpack_infer(implements):
        if iface is astroid.Uninferable:
            missing = True
            continue
        if iface not in found and handler_func(iface):
            found.add(iface)
            yield iface
    if missing:
        raise astroid.exceptions.InferenceError()


class IdGeneratorMixIn:
    """Mixin adding the ability to generate integer uid."""

    def __init__(self, start_value=0):
        self.id_count = start_value

    def init_counter(self, start_value=0):
        """Init the id counter."""
        self.id_count = start_value

    def generate_id(self):
        """Generate a new identifier."""
        self.id_count += 1
        return self.id_count


class Project:
    """A project handle a set of modules / packages."""

    def __init__(self, name=""):
        self.name = name
        self.uid = None
        self.path = None
        self.modules = []
        self.locals = {}
        self.__getitem__ = self.locals.__getitem__
        self.__iter__ = self.locals.__iter__
        self.values = self.locals.values
        self.keys = self.locals.keys
        self.items = self.locals.items

    def add_module(self, node):
        self.locals[node.name] = node
        self.modules.append(node)

    def get_module(self, name):
        return self.locals[name]

    def get_children(self):
        return self.modules

    def __repr__(self):
        return f"<Project {self.name!r} at {id(self)} ({len(self.modules)} modules)>"


class Linker(IdGeneratorMixIn, utils.LocalsVisitor):
    """Walk on the project tree and resolve relationships.

    According to options the following attributes may be
    added to visited nodes:

    * uid,
      a unique identifier for the node (on astroid.Project, astroid.Module,
      astroid.Class and astroid.locals_type). Only if the linker
      has been instantiated with tag=True parameter (False by default).

    * Function
      a mapping from locals names to their bounded value, which may be a
      constant like a string or an integer, or an astroid node
      (on astroid.Module, astroid.Class and astroid.Function).

    * instance_attrs_type
      as locals_type but for klass member attributes (only on astroid.Class)

    * implements,
      list of implemented interface _objects_ (only on astroid.Class nodes)
    """

    def __init__(self, project, inherited_interfaces=0, tag=False):
        IdGeneratorMixIn.__init__(self)
        utils.LocalsVisitor.__init__(self)
        # take inherited interface in consideration or not
        self.inherited_interfaces = inherited_interfaces
        # tag nodes or not
        self.tag = tag
        # visited project
        self.project = project

    def visit_project(self, node: Project) -> None:
        """Visit a pyreverse.utils.Project node.

        * optionally tag the node with a unique id
        """
        if self.tag:
            node.uid = self.generate_id()
        for module in node.modules:
            self.visit(module)

    def visit_module(self, node: nodes.Module) -> None:
        """Visit an astroid.Module node.

        * set the locals_type mapping
        * set the depends mapping
        * optionally tag the node with a unique id
        """
        if hasattr(node, "locals_type"):
            return
        node.locals_type = collections.defaultdict(list)
        node.depends = []
        if self.tag:
            node.uid = self.generate_id()

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Visit an astroid.Class node.

        * set the locals_type and instance_attrs_type mappings
        * set the implements list and build it
        * optionally tag the node with a unique id
        """
        if hasattr(node, "locals_type"):
            return
        node.locals_type = collections.defaultdict(list)
        if self.tag:
            node.uid = self.generate_id()
        # resolve ancestors
        for baseobj in node.ancestors(recurs=False):
            specializations = getattr(baseobj, "specializations", [])
            specializations.append(node)
            baseobj.specializations = specializations
        # resolve instance attributes
        node.instance_attrs_type = collections.defaultdict(list)
        for assignattrs in node.instance_attrs.values():
            for assignattr in assignattrs:
                if not isinstance(assignattr, nodes.Unknown):
                    self.handle_assignattr_type(assignattr, node)
        # resolve implemented interface
        try:
            node.implements = list(interfaces(node, self.inherited_interfaces))
        except astroid.InferenceError:
            node.implements = []

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Visit an astroid.Function node.

        * set the locals_type mapping
        * optionally tag the node with a unique id
        """
        if hasattr(node, "locals_type"):
            return
        node.locals_type = collections.defaultdict(list)
        if self.tag:
            node.uid = self.generate_id()

    link_project = visit_project
    link_module = visit_module
    link_class = visit_classdef
    link_function = visit_functiondef

    def visit_assignname(self, node: nodes.AssignName) -> None:
        """Visit an astroid.AssignName node.

        handle locals_type
        """
        # avoid double parsing done by different Linkers.visit
        # running over the same project:
        if hasattr(node, "_handled"):
            return
        node._handled = True
        if node.name in node.frame(future=True):
            frame = node.frame(future=True)
        else:
            # the name has been defined as 'global' in the frame and belongs
            # there.
            frame = node.root()
        if not hasattr(frame, "locals_type"):
            # If the frame doesn't have a locals_type yet,
            # it means it wasn't yet visited. Visit it now
            # to add what's missing from it.
            if isinstance(frame, nodes.ClassDef):
                self.visit_classdef(frame)
            elif isinstance(frame, nodes.FunctionDef):
                self.visit_functiondef(frame)
            else:
                self.visit_module(frame)

        current = frame.locals_type[node.name]
        frame.locals_type[node.name] = list(set(current) | utils.infer_node(node))

    @staticmethod
    def handle_assignattr_type(node, parent):
        """Handle an astroid.assignattr node.

        handle instance_attrs_type
        """
        current = set(parent.instance_attrs_type[node.attrname])
        parent.instance_attrs_type[node.attrname] = list(
            current | utils.infer_node(node)
        )

    def visit_import(self, node: nodes.Import) -> None:
        """Visit an astroid.Import node.

        resolve module dependencies
        """
        context_file = node.root().file
        for name in node.names:
            relative = astroid.modutils.is_relative(name[0], context_file)
            self._imported_module(node, name[0], relative)

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Visit an astroid.ImportFrom node.

        resolve module dependencies
        """
        basename = node.modname
        context_file = node.root().file
        if context_file is not None:
            relative = astroid.modutils.is_relative(basename, context_file)
        else:
            relative = False
        for name in node.names:
            if name[0] == "*":
                continue
            # analyze dependencies
            fullname = f"{basename}.{name[0]}"
            if fullname.find(".") > -1:
                try:
                    fullname = astroid.modutils.get_module_part(fullname, context_file)
                except ImportError:
                    continue
            if fullname != basename:
                self._imported_module(node, fullname, relative)

    def compute_module(self, context_name, mod_path):
        """Return true if the module should be added to dependencies."""
        package_dir = os.path.dirname(self.project.path)
        if context_name == mod_path:
            return 0
        if astroid.modutils.is_standard_module(mod_path, (package_dir,)):
            return 1
        return 0

    def _imported_module(self, node, mod_path, relative):
        """Notify an imported module, used to analyze dependencies."""
        module = node.root()
        context_name = module.name
        if relative:
            mod_path = f"{'.'.join(context_name.split('.')[:-1])}.{mod_path}"
        if self.compute_module(context_name, mod_path):
            # handle dependencies
            if not hasattr(module, "depends"):
                module.depends = []
            mod_paths = module.depends
            if mod_path not in mod_paths:
                mod_paths.append(mod_path)


def project_from_files(
    files, func_wrapper=_astroid_wrapper, project_name="no name", black_list=("CVS",)
):
    """Return a Project from a list of files or modules."""
    # build the project representation
    astroid_manager = astroid.manager.AstroidManager()
    project = Project(project_name)
    for something in files:
        if not os.path.exists(something):
            fpath = astroid.modutils.file_from_modpath(something.split("."))
        elif os.path.isdir(something):
            fpath = os.path.join(something, "__init__.py")
        else:
            fpath = something
        ast = func_wrapper(astroid_manager.ast_from_file, fpath)
        if ast is None:
            continue
        project.path = project.path or ast.file
        project.add_module(ast)
        base_name = ast.name
        # recurse in package except if __init__ was explicitly given
        if ast.package and something.find("__init__") == -1:
            # recurse on others packages / modules if this is a package
            for fpath in astroid.modutils.get_module_files(
                os.path.dirname(ast.file), black_list
            ):
                ast = func_wrapper(astroid_manager.ast_from_file, fpath)
                if ast is None or ast.name == base_name:
                    continue
                project.add_module(ast)
    return project
