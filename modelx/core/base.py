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

import sys
import builtins
from types import FunctionType
from collections import Sequence, ChainMap, Mapping, UserDict, OrderedDict
from inspect import BoundArguments
from modelx.core.formula import create_closure
from modelx.core.node import get_node

# To add new method apply_defaults to BoundArguments.
if sys.version_info < (3, 5, 0):

    def _apply_defaults(self):
        """Set default values for missing arguments.

        For variable-positional arguments (*args) the default is an
        empty tuple.

        For variable-keyword arguments (**kwargs) the default is an
        empty dict.
        """
        from collections import OrderedDict
        from inspect import _empty, _VAR_KEYWORD, _VAR_POSITIONAL

        arguments = self.arguments
        new_arguments = []
        for name, param in self._signature.parameters.items():
            try:
                new_arguments.append((name, arguments[name]))
            except KeyError:
                if param.default is not _empty:
                    val = param.default
                elif param.kind is _VAR_POSITIONAL:
                    val = ()
                elif param.kind is _VAR_KEYWORD:
                    val = {}
                else:
                    # This BoundArguments was likely produced by
                    # Signature.bind_partial().
                    continue
                new_arguments.append((name, val))
        self.arguments = OrderedDict(new_arguments)

    BoundArguments.apply_defaults = _apply_defaults


def get_interfaces(impls):
    """Get interfaces from their implementations."""
    if impls is None:
        return None

    elif isinstance(impls, OrderMixin):
        result = OrderedDict()
        for name in impls.order:
            result[name] = impls[name].interface
        return result

    elif isinstance(impls, Mapping):
        return {name: impls[name].interface for name in impls}

    elif isinstance(impls, Sequence):
        return [impl.interface for impl in impls]

    else:
        return impls.interface


def get_impls(interfaces):
    """Get impls from their interfaces."""
    if interfaces is None:
        return None

    elif isinstance(interfaces, Mapping):
        return {name: interfaces[name]._impl for name in interfaces}

    elif isinstance(interfaces, Sequence):
        return [interfaces._impl for interfaces in interfaces]

    else:
        return interfaces._impl


class Impl:
    """The ultimate base class of *Impl classes.

    The rationales for splitting implementation from its interface are twofold,
    one is to hide from users attributes used only within the package,
    and the other is to free referring objects from getting affected by
    special methods that are meant for changing the behaviour of operations
    for users."""

    state_attrs = ["interface", "parent", "allow_none", "lazy_evals"]

    if_class = None  # Override in sub classes if interface class exists

    def __init__(self, system, interface=None):

        if self.if_class:
            self.interface = self.if_class(self)
        else:
            self.interface = interface

        self.system = system
        self.parent = None  # To be overwritten in Space and Cells
        self.name = None
        self.allow_none = None
        self.lazy_evals = None

    def get_property(self, name):
        prop = getattr(self, name)
        if prop is None:
            return self.parent.get_property(name)
        else:
            return prop

    def update_lazyevals(self):
        """Update all LazyEvals in self

        self.lzy_evals must be set to LazyEval object(s) enough to
        update all owned LazyEval objects.
        """
        if self.lazy_evals is None:
            return
        elif isinstance(self.lazy_evals, LazyEval):
            self.lazy_evals.get_updated()
        else:
            for lz in self.lazy_evals:
                lz.get_updated()

    def get_fullname(self, omit_model=False):

        if self.parent:
            result = self.parent.get_fullname(False) + "." + self.name
            if omit_model:
                separated = result.split(".")
                separated.pop(0)
                return ".".join(separated)
            else:
                return result
        else:
            if omit_model:
                return ""
            else:
                return self.name

    @property
    def evalrepr(self):
        """Evaluable repr"""
        if self.is_model():
            return self.get_fullname()
        else:
            return self.parent.evalrepr + "." + self.name

    def restore_state(self, system):
        """Called after unpickling to restore some attributes manually."""
        self.system = system

    def is_model(self):
        return self.parent is None

    # ----------------------------------------------------------------------
    # repr methods

    def repr_self(self, add_params=True):
        raise NotImplementedError

    def repr_parent(self):
        raise NotImplementedError

    def get_repr(self, fullname=False, add_params=True):

        if fullname:
            return self.repr_parent() + "." + self.repr_self(add_params)
        else:
            return self.repr_self(add_params)


class _DummyBuiltins:
    pass


class Derivable(Impl):

    state_attrs = ["_is_derived"] + Impl.state_attrs

    def __init__(self, system, interface=None):
        Impl.__init__(self, system, interface)
        self._is_derived = None  # must be initialized after __init__.

    @property
    def is_derived(self):
        return self._is_derived

    @is_derived.setter
    def is_derived(self, is_derived):
        self._is_derived = is_derived
        if not is_derived:
            if self.parent.parent is not None:
                self.parent.is_derived = is_derived

    def has_ascendant(self, other):
        if other is self.parent:
            return True
        elif self.parent.parent is None:
            return False
        else:
            return self.parent.has_ascendant(self.parent)

    @property
    def bases(self):
        return self.self_bases + self.parent_bases

    @property
    def parent_bases(self):
        if self.parent.is_model():
            return []
        else:
            parent_bases = self.parent.bases
            result = []
            for space in parent_bases:
                bases = self._get_members(space)
                if self.name in bases:
                    result.append(bases[self.name])
            return result

    @staticmethod
    def _get_members(other):
        raise NotImplementedError

    @property
    def self_bases(self):
        raise NotImplementedError

    def inherit(self, **kwargs):
        raise NotImplementedError

    def __repr__(self):
        if self.parent.is_model():
            return self.name
        else:
            return repr(self.parent) + "." + self.name


class ReferenceImpl(Derivable):

    state_attrs = Derivable.state_attrs

    def __init__(self, parent, name, value, base=None):
        Derivable.__init__(self, parent.system, interface=value)

        self.parent = parent
        self.model = parent.model
        self.name = name

    def __getstate__(self):
        state = {
            key: value
            for key, value in self.__dict__.items()
            if key in self.state_attrs
        }

        if state["interface"] is builtins:
            state["interface"] = _DummyBuiltins()

        return state

    def __setstate__(self, state):

        if isinstance(state["interface"], _DummyBuiltins):
            state["interface"] = builtins

        self.__dict__.update(state)

    @property
    def self_bases(self):
        return []

    @staticmethod
    def _get_members(other):
        return other.self_refs

    def inherit(self, **kwargs):

        if "clear_value" in kwargs:
            clear_value = kwargs["clear_value"]
        else:
            clear_value = True

        if self.bases:
            if clear_value:
                self.model.clear_obj(self)
            self.interface = self.bases[0].interface


class NullImpl(Impl):
    """Singleton to represent deleted objects.

    Call ``impl.del_self`` if it exists,
    and detach ``impl`` from its interface.
    The interface points to this NllImpl singleton.
    """

    the_instance = None

    def __new__(cls, impl):

        if cls.the_instance is None:
            cls.the_instance = object.__new__(cls)

        if hasattr(impl, "del_self"):
            impl.del_self()

        impl.interface._impl = cls.the_instance

        return cls.the_instance

    def __init__(self, impl):
        pass

    def __getattr__(self, item):
        raise RuntimeError("Deleted object")


class Interface:
    """The ultimate base class of Model, Space, Cells.

    All the properties defined in this class are available in Model,
    Space and Cells objects.
    """

    __slots__ = ("_impl",)
    properties = ["allow_none"]

    def __new__(cls, _impl):

        if isinstance(_impl, Impl):
            if not hasattr(_impl, "interface"):
                self = object.__new__(cls)
                object.__setattr__(self, "_impl", _impl)
                return self
            else:
                return _impl.interface
        else:
            raise ValueError("Invalid direct constructor call.")

    @property
    def name(self):
        """Name of the object."""
        return self._impl.name

    @property
    def fullname(self):
        """Dotted name of the object.

        Names joined by dots, such as 'Model1.Space1.Cells1',
        each element in the string is the name of the parent object
        of the next one joined by a dot.
        """
        return self._impl.get_fullname()

    @property
    def parent(self):
        """The parent of this object. None for models.

        The parent object of a cells is a space that contains the cells.
        The parent object of a space is either a model or another space
        that contains the space.
        """

        if self._impl.parent is None:
            return None
        else:
            return self._impl.parent.interface

    @property
    def model(self):
        """The model this object belongs to.

        This is a property of Model, Space and Cells.
        For models, this property is themselves.
        """
        return self._impl.model.interface

    def __repr__(self):
        type_ = self.__class__.__name__
        if self.parent:
            return "<%s %s in %s>" % (
                type_, self._impl.repr_self(), self._impl.repr_parent()
            )
        else:
            return "<%s %s>" % (type_, self._impl.repr_self())

    def __getnewargs__(self):
        return (self._impl,)

    def __getstate__(self):
        return self._impl

    def __setstate__(self, state):
        object.__setattr__(self, "_impl", state)

    @property
    def allow_none(self):
        """Whether a cells can have None as its value.

        This is a property of Model, Space and Cells.
        If ``allow_none`` of a cells is False,
        the cells cannot have None as its value.
        Assigning None to the cells
        or its formula returning None raises an Error.
        If True, the cells can have None as their value.
        If set to None, ``allow_none`` of its parent is looked up,
        and the search continues until True or False is found.

        Returns:
            True if the cells can have None, False if it cannot,
            or None if a default value from the parent is to be used.
        """
        return self._impl.allow_none

    @allow_none.setter
    def allow_none(self, value):
        self._impl.allow_none = value if value is None else bool(value)

    # ----------------------------------------------------------------------
    # Override base class methods

    @property
    def _baseattrs(self):
        """A dict of members expressed in literals"""

        result = {
            "type": type(self).__name__,
            "id": id(self),
            "name": self.name,
            "fullname": self.fullname,
            "repr": self._get_repr(),
        }

        return result

    def _to_attrdict(self, attrs=None):
        """Get extra attributes"""
        result = self._baseattrs

        for attr in attrs:
            if hasattr(self, attr):
                result[attr] = getattr(self, attr)._to_attrdict(attrs)

        return result

    def _get_repr(self, fullname=False, add_params=True):
        return self._impl.get_repr(fullname, add_params)

    @property
    def _evalrepr(self):
        return self._impl.evalrepr


class LazyEval:
    """Base class for flagging observers so that they update themselves later.

    An object of a class inherited from LazyEvaluation can have its observers.
    When the data of the object is updated, the users call set_update method,
    to flag the object's observers.
    When the observers get_updated methods are called later, their data
    contents are updated depending on their update states.
    The updating operation can be customized by overwriting _update_data method.
    """

    def __init__(self, observers):
        self.needs_update = False  # must be read only
        self.observers = []
        self.observing = []
        for observer in observers:
            self.append_observer(observer)

    def set_update(self, skip_self=False):

        if not skip_self:
            self.needs_update = True
        for observer in self.observers:
            if not observer.needs_update:
                observer.set_update()

    def get_updated(self):
        if self.needs_update:
            for other in self.observing:
                other.get_updated()
            self._update_data()
            self.needs_update = False
        return self

    def _update_data(self):
        raise NotImplementedError  # To be overwritten in derived classes

    def append_observer(self, observer):
        if all(observer is not other for other in self.observers):
            self.observers.append(observer)
            observer.observing.append(self)
            observer.set_update()

    def observe(self, other):
        other.append_observer(self)

    def remove_observer(self, observer):
        self.observers.remove(observer)
        observer.observing.remove(self)

    def unobserve(self, other):
        other.remove_observer(self)

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def debug_print_observers(self, indent_level=0):
        print(" " * indent_level * 4, self, ":", self.needs_update)
        for observer in self.observers:
            observer.debug_print_observers(indent_level + 1)


class LazyEvalDict(LazyEval, UserDict):
    def __init__(self, data=None, observers=None):

        if data is None:
            data = {}
        if observers is None:
            observers = []

        UserDict.__init__(self, data)
        LazyEval.__init__(self, observers)
        self._repr = ""

    def get_updated_data(self):
        """Get updated ``data`` instead of self. """
        self.get_updated()
        return self.data

    def _update_data(self):
        pass

    def set_item(self, name, value, skip_self=False):
        UserDict.__setitem__(self, name, value)
        self.set_update(skip_self)

    def del_item(self, name, skip_self=False):
        UserDict.__delitem__(self, name)
        self.set_update(skip_self)

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)


class LazyEvalChainMap(LazyEval, ChainMap):
    def __init__(self, maps=None, observers=None, observe_maps=True):

        if maps is None:
            maps = []
        if observers is None:
            observers = []

        ChainMap.__init__(self, *maps)
        LazyEval.__init__(self, observers)
        self._repr = ""

        if observe_maps:
            for other in maps:
                if isinstance(other, LazyEval):
                    other.append_observer(self)

    def _update_data(self):
        for map_ in self.maps:
            if isinstance(map_, LazyEval):
                map_.get_updated()

    def __setitem__(self, name, value):
        raise NotImplementedError

    def __delitem__(self, name):
        raise NotImplementedError

    def __getstate__(self):
        state = LazyEval.__getstate__(self)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)


class OwnerMixin:
    def __init__(self, owner):
        self.owner = owner


class OrderMixin:
    def __init__(self):
        self.order = []  # sorted(list(self))

    def _update_order(self):
        prev = set(self.order)
        curr = set(self)
        deleted = prev - curr
        added = curr - prev
        for key in deleted:
            self.order.remove(key)
        for key in sorted(list(added)):
            self.order.append(key)


class InterfaceMixin:
    """Mixin to LazyEval to update interface with impl

    _update_interfaces needs to be manually called from _update_data.
    """

    def __init__(self, map_class):
        self._interfaces = dict()
        self.map_class = map_class
        self._set_interfaces(map_class)

    def _set_interfaces(self, map_class):
        if map_class is None:
            self.interfaces = self._interfaces
        elif map_class is dict:
            raise RuntimeError
        else:
            self.interfaces = map_class(self._interfaces)

    def _update_interfaces(self):
        self._interfaces.clear()
        self._interfaces.update(get_interfaces(self))

    def __getstate__(self):
        state = super().__getstate__()
        state["_interfaces"] = dict()
        del state["interfaces"]
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        if self.map_class == "BaseView":
            self.map_class = BaseView
        self._set_interfaces(self.map_class)
        self.needs_update = True


class ImplDict(OwnerMixin, InterfaceMixin, OrderMixin, LazyEvalDict):
    def __init__(self, owner, ifclass, data=None, observers=None):
        InterfaceMixin.__init__(self, ifclass)
        OrderMixin.__init__(self)
        OwnerMixin.__init__(self, owner)
        LazyEvalDict.__init__(self, data, observers)

    def _update_data(self):
        LazyEvalDict._update_data(self)
        self._update_order()
        self._update_interfaces()

    def __repr__(self):
        if hasattr(self, "debug_name"):
            name = self.debug_name
        else:
            name = ""
        return (
            repr(self.owner.fullname) + ":" + repr(self.__class__) + ":" + name
        )


class ImplChainMap(OwnerMixin, InterfaceMixin, OrderMixin, LazyEvalChainMap):
    def __init__(
        self, owner, ifclass, maps=None, observers=None, observe_maps=True
    ):
        InterfaceMixin.__init__(self, ifclass)
        OrderMixin.__init__(self)
        OwnerMixin.__init__(self, owner)
        LazyEvalChainMap.__init__(self, maps, observers, observe_maps)

    def _update_data(self):
        LazyEvalChainMap._update_data(self)
        self._update_order()
        self._update_interfaces()

    def __repr__(self):
        if hasattr(self, "debug_name"):
            name = self.debug_name
        else:
            name = ""
        return (
            repr(self.owner.fullname) + ":" + repr(self.__class__) + ":" + name
        )


# The code below is modified from UserDict in Python's standard library.
#
# The original code was taken from the following URL:
#   https://github.com/python/cpython/blob/\
#       7e68790f3db75a893d5dd336e6201a63bc70212b/\
#       Lib/collections/__init__.py#L968-L1027


class BaseView(Mapping):

    # Start by filling-out the abstract methods
    def __init__(self, data):
        self._data = data

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        if key in self._data:
            return self._data[key]
        if hasattr(self.__class__, "__missing__"):
            return self.__class__.__missing__(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._data)

    # Modify __contains__ to work correctly when __missing__ is present
    def __contains__(self, key):
        return key in self._data

    # Now, add the methods in dicts but not in MutableMapping
    def __repr__(self):
        return repr(self._data)

    # ----------------------------------------------------------------------
    # Override base class methods

    @property
    def _baseattrs(self):
        """A dict of members expressed in literals"""

        result = {"type": type(self).__name__}
        try:
            result["items"] = {
                name: item._baseattrs
                for name, item in self.items()
                if name[0] != "_"
            }
        except:
            raise RuntimeError("%s literadict raised an error" % self)

        return result

    def _to_attrdict(self, attrs=None):

        result = {"type": type(self).__name__}
        try:
            result["items"] = {
                name: item._to_attrdict(attrs) for name, item in self.items()
            }
        except:
            raise RuntimeError("%s literadict raised an error" % self)

        return result


def _map_repr(self):
    result = [",\n "] * (len(self) * 2 - 1)
    result[0::2] = sorted(list(self))
    return "{" + "".join(result) + "}"


class SelectedView(BaseView):
    """View to the original mapping but has only selected items.

    A base class for :class:`modelx.core.space.CellsView`.

    Args:
        data: The original mapping object.
        keys: Iterable of selected keys.
    """

    def __init__(self, data, keys=None):
        BaseView.__init__(self, data)
        self._set_keys(keys)

    def __getitem__(self, key):
        if isinstance(key, str):
            return BaseView.__getitem__(self, key)
        if isinstance(key, Sequence):
            return type(self)(self._data, key)
        else:
            raise KeyError

    def _set_keys(self, keys=None):

        if keys is None:
            self.__keys = None
        else:
            self.__keys = list(keys)

    def __len__(self):
        return len(list(iter(self)))

    def __iter__(self):
        def newiter():
            for key in self.__keys:
                if key in self._data:
                    yield key

        if self.__keys is None:
            return BaseView.__iter__(self)
        else:
            return newiter()

    def __contains__(self, key):
        return key in iter(self)

    __repr__ = _map_repr


class BoundFunction(LazyEval):
    """Hold function with updated namespace"""

    def __init__(self, owner):
        """Create altered function from owner's formula.

        owner is a StaticSpaceImpl or CellsImpl, which has formula, and
        namespace_impl as its members.
        """
        LazyEval.__init__(self, [])
        self.owner = owner

        # Must not update owner's namespace to avoid circular updates.
        self.namespace_impl = owner._namespace_impl  # No need to hold this
        self.observe(self.namespace_impl)
        self.altfunc = None
        self.set_update()

    def _update_data(self):
        """Update altfunc"""

        func = self.owner.formula.func
        codeobj = func.__code__
        name = func.__name__  # self.cells.name   # func.__name__
        namespace_impl = self.owner._namespace_impl.get_updated()
        namespace = namespace_impl.interfaces
        selfnode = get_node(self.owner, None, None)

        for name in self.owner.formula.srcnames:
            if name in namespace_impl and isinstance(
                namespace_impl[name], ReferenceImpl
            ):
                refnode = get_node(namespace_impl[name], None, None)
                self.owner.model.lexdep.add_path([selfnode, refnode])

        closure = func.__closure__  # None normally.
        if closure is not None:  # pytest fails without this.
            closure = create_closure(self.owner.interface)

        self.altfunc = FunctionType(
            codeobj, namespace, name=name, closure=closure
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["altfunc"]
        state["needs_update"] = True  # Reconstruct altfunc after unpickling
        return state
