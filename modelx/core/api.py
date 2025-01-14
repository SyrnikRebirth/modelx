# Copyright (c) 2017-2019 Fumito Hamamura <fumito.ham@gmail.com>

# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation version 3.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""modelx core API functions.

Functions listed here are available directly in ``modelx`` module,
either by::

    import modelx as mx

or by::

    from modelx import *

"""
import ast
from types import FunctionType as _FunctionType

from modelx.core import mxsys as _system
from modelx.core.cells import CellsMaker as _CellsMaker
from modelx.core.space import BaseSpace as _Space
from modelx.core.model import Model as _Model
from modelx.core.base import get_interfaces as _get_interfaces


def configure_python():
    """Configure Python ``sys`` settings for modelx.

    This function is called implicitly when importing modelx.
    To restore the Python settings, call :py:func:`restore_python`
    """
    _system.configure_python()


def restore_python():
    """Restore Python ``sys`` settings for modelx.

    Restore ``sys`` settings to the original states before
    importing modelx.
    """
    _system.restore_python()


def setup_ipython():
    """Set up IPython shell for modelx.

    Suppress IPython's default traceback messages upon error.
    """
    _system.setup_ipython()


def restore_ipython():
    """Restore IPython' default error message.

    Bring back IPython's default traceback message upon error for debugging.
    """
    _system.restore_ipython()


def set_recursion(maxdepth=1000):
    """Set formula recursion limit.

    Args:
        maxdepth: The maximum depth of the modelx interpreter stack.
    """
    _system.callstack.maxdepth = maxdepth


def new_model(name=None):
    """Create and return a new model.

    The current model is set set to the created model.

    Args:
        name (:obj:`str`, optional): The name of the model to create.
            Defaults to ``ModelN``, with ``N``
            being an automatically assigned integer.

    Returns:
        The new model.
    """
    return _system.new_model(name).interface


def new_space(name=None, bases=None, formula=None):
    """Create and return a new space in the current model.

    The ``currentspace`` of the current model is set to the created model.

    Args:
        name (:obj:`str`, optional): The name of the space to create.
            Defaults to ``SpaceN``, with ``N``
            being an automatically assigned integer.

    Returns:
        The new space.
    """
    return cur_model().new_space(name, bases, formula)


def defcells(space=None, name=None, *funcs):
    """Decorator/function to create cells from Python functions.

    Convenience decorator/function to create new cells directly from function
    definitions or function objects substituting for calling
    :py:meth:`new_cells <modelx.core.space.StaticSpace.new_cells>`
    method of the parent space.

    There are 3 ways to use ``defcells`` to define cells from functions.

    **1. As a decorator without arguments**

    To create a cells from a function definition in the current space of the
    current model with the same name as the function's::

        @defcells
        def foo(x):
            return x

    **2. As a decorator with arguments**

    To create a cells from a function definition in a given space and/or with
    a given name::

        @defcells(space=space, name=name)
        def foo(x):
            return x

    **3. As a function**

    To create a multiple cells from a multiple function definitions::

        def foo(x):
            return x

        def bar(y):
            return foo(y)

        foo, bar = defcells(foo, bar)

    Args:
        space(optional): For the 2nd usage, a space to create the cells in.
            Defaults to the current space of the current model.
        name(optional): For the 2nd usage, a name of the created cells.
            Defaults to the function name.
        *funcs: For the 3rd usage, function objects. (``space`` and ``name``
            also take function objects for the 3rd usage.)

    Returns:
        For the 1st and 2nd usage, the newly created single cells is returned.
        For the 3rd usage, a list of newly created cells are returned.

    """
    if isinstance(space, _FunctionType) and name is None:
        # called as a function decorator
        func = space
        return _system.currentspace.new_cells(formula=func).interface

    elif (isinstance(space, _Space) or space is None) and (
        isinstance(name, str) or name is None
    ):
        # return decorator itself
        if space is None:
            space = _system.currentspace.interface

        return _CellsMaker(space=space._impl, name=name)

    elif all(
        isinstance(func, _FunctionType) for func in (space, name) + funcs
    ):

        return [defcells(func) for func in (space, name) + funcs]

    else:
        raise TypeError("invalid defcells arguments")


def get_models():
    """Returns a dict that maps model names to models."""
    return _get_interfaces(_system.models)


def get_object(name: str):
    """Get a modelx object from its full name."""
    # TODO: Duplicate of system.get_object
    elms = name.split(".")
    parent = get_models()[elms.pop(0)]
    while len(elms) > 0:
        obj = elms.pop(0)
        parent = getattr(parent, obj)

    return parent


def _get_node(name: str, args: str):
    """Get node from object name and arg string

    Not Used. Left for future reference purpose.
    """
    obj = get_object(name)
    args = ast.literal_eval(args)
    if not isinstance(args, tuple):
        args = (args,)

    return obj.node(*args)


def cur_model(model=None):
    """Get and/or set the current model.

    If ``model`` is given, set the current model to ``model`` and return it.
    ``model`` can be the name of a model object, or a model object itself.
    If ``model`` is not given, the current model is returned.
    """
    if model is None:
        if _system.currentmodel is not None:
            return _system.currentmodel.interface
        else:
            return None
    else:
        if isinstance(model, _Model):
            _system.currentmodel = model._impl
        else:
            _system.currentmodel = _system.models[model]

        return _system.currentmodel.interface


def cur_space(space=None):
    """Get and/or set the current space of the current model.

    If ``name`` is given, the current space of the current model is
    set to ``name`` and return it.
    If ``name`` is not given, the current space of the current model
    is returned.
    """
    if space is None:
        if _system.currentmodel is not None:
            if _system.currentmodel.currentspace is not None:
                return _system.currentmodel.currentspace.interface
            else:
                return None
        else:
            return None
    else:
        if isinstance(space, _Space):
            cur_model(space.model)
            _system.currentmodel.currentspace = space._impl
        else:
            _system.currentmodel.currentspace = _system.currentmodel.spaces[
                space
            ]

        return cur_space()


def open_model(path, name=None):
    """Load a model saved from a file and return it.

    Args:
        path (:obj:`str`): Path to the file to load the model from.
        name (optional): If specified, the model is renamed to this name.

    Returns:
        A new model created from the file.
    """
    return _system.open_model(path, name)
