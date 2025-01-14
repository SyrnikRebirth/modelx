from collections import ChainMap
import itertools
import networkx as nx



class SpaceGraph(nx.DiGraph):

    def add_edge(self, basespace, subspace):

        if basespace.has_linealrel(subspace):
            raise ValueError("%s and %s have parent-child relationship"
                             % (basespace, subspace))

        nx.DiGraph.add_edge(self, basespace, subspace)

        if not nx.is_directed_acyclic_graph(self):
            self.remove_edge(basespace, subspace)
            raise ValueError("Loop detected in inheritance")

        try:
            self._start_space = subspace
            self.traverse_subspaces(subspace, check_only=True)
        finally:
            self._start_space = None

    def get_bases(self, node):
        """Direct Bases iterator"""
        return self.predecessors(node)

    def get_mro(self, space):
        """Calculate the Method Resolution Order of bases using the C3 algorithm.

        Code modified from
        http://code.activestate.com/recipes/577748-calculate-the-mro-of-a-class/

        Args:
            bases: sequence of direct base spaces.

        Returns:
            mro as a list of bases including node itself
        """
        seqs = [self.get_mro(base) for base
                in self.get_bases(space)] + [list(self.get_bases(space))]
        res = []
        while True:
            non_empty = list(filter(None, seqs))

            if not non_empty:
                # Nothing left to process, we're done.
                res.insert(0, space)
                return res

            for seq in non_empty:  # Find merge candidates among seq heads.
                candidate = seq[0]
                not_head = [s for s in non_empty if candidate in s[1:]]
                if not_head:
                    # Reject the candidate.
                    candidate = None
                else:
                    break

            if not candidate:
                raise TypeError(
                    "inconsistent hierarchy, no C3 MRO is possible")

            res.append(candidate)

            for seq in non_empty:
                # Remove candidate.
                if seq[0] == candidate:
                    del seq[0]


    def traverse_subspaces(self, space,  skip=True, check_only=False):
        self.traverse_subspaces_downward(space, skip, check_only)
        self.traverse_subspaces_upward(space)

    def traverse_subspaces_upward(self, space):
        if space.parent.parent is None:
            return
        else:
            succ = self.successors(space.parent)
            for subspace in succ:
                if subspace is self._start_space:
                    raise ValueError("Cyclic inheritance")
                self.traverse_subspaces(subspace, False)
            self.traverse_subspaces_upward(space.parent)

    def traverse_subspaces_downward(self, space, skip=True, check_only=False):
        for child in space.spaces.values():
            self.traverse_subspaces_downward(child, False, check_only)
        if not skip and not check_only:
                space.inherit()
        succ = self.successors(space)
        for subspace in succ:
            if subspace is self._start_space:
                raise ValueError("Cyclic inheritance")
            self.traverse_subspaces(subspace, False, check_only)

    def update_subspaces(self, space, skip=True):
        self.traverse_subspaces(space, skip)


class SpaceContainer:

    def new_space(self, name, is_derived=False):
        space = self.spaces[name] = MiniSpace(self, name, is_derived)
        graph.add_node(space)
        # space.inherit()
        graph.update_subspaces(space)
        return space

    def del_space(self, name):
        space = self.spaces.pop(name)
        graph.remove_node(space)
        for space in self.spaces.values():
            space.inherit()


class MiniModel(SpaceContainer):
    def __init__(self):
        self.spaces = {}
        self.parent = None


class MiniDerivable:
    def __init__(self, parent):
        self.parent = parent

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
        if isinstance(self.parent, MiniModel):
            return []
        else:
            parent_bases = self.parent.bases # graph.get_mro(self.parent)[1:]
            result = []
            for space in parent_bases:
                if self.name in space.children:
                    if type(self) is type(space.children[self.name]):
                        result.append(space.children[self.name])
            return result

    @property
    def self_bases(self):
        raise NotImplementedError

    def inherit(self):
        raise NotImplementedError

    def __repr__(self):
        if isinstance(self.parent, MiniModel):
            return self.name
        else:
            return repr(self.parent) + '.' + self.name


class MiniSpace(MiniDerivable, SpaceContainer):

    def __init__(self, parent, name, is_derived):
        self.name = name
        self.is_derived = is_derived
        parent.spaces[name] = self
        self.spaces = {}
        self.items = {}
        self.children = ChainMap(self.items, self.spaces)
        MiniDerivable.__init__(self, parent)

    def new_item(self, name, is_derived):
        item = MiniItem(self, name, is_derived)
        item.inherit()
        graph.update_subspaces(self)
        return item

    def new_member(self, type_, name, is_derived=False):
        if type_ == 'space':
            return self.new_space(name, is_derived)
        elif type_ == 'item':
            return self.new_item(name, is_derived)

    def del_space(self, name):
        space = self.spaces.pop(name)
        graph.remove_node(space)
        self.inherit()
        graph.update_subspaces(self)

    def del_item(self, name):
        self.items.pop(name)
        self.inherit()
        graph.update_subspaces(self)

    def del_member(self, type_, name):
        if type_ == 'space':
            return self.del_space(name)
        elif type_ == 'item':
            return self.del_item(name)

    def add_base(self, other):
        graph.add_edge(other, self)
        self.inherit()
        graph.update_subspaces(self)

    def remove_base(self, other):
        graph.remove_edge(other, self)
        self.inherit()

    def has_descendant(self, other):
        if self.spaces:
            if other in self.spaces.values():
                return True
            else:
                return any(child.has_descendant(other)
                           for child in self.spaces.values())
        else:
            return False

    def has_linealrel(self, other):
        return self.has_ascendant(other) or self.has_descendant(other)

    # --- Derivable Interface Override ---

    @property
    def self_bases(self):
        return graph.get_mro(self)[1:]

    def inherit(self):
        bases = self.bases
        attrs = ('items', 'spaces')
        for attr in attrs:
            selfmap = getattr(self, attr)
            basemap = ChainMap(*[getattr(base, attr) for base in bases])
            for name in basemap:
                if name not in selfmap:
                    selfmap[name] = self.new_member(attr[:-1], name,
                                                    is_derived=True)
                selfmap[name].inherit()

            names = set(selfmap) - set(basemap)
            for name in names:
                if selfmap[name].is_derived:
                    self.del_member(attr[:-1], name)
                else:
                    selfmap[name].inherit()


class MiniItem(MiniDerivable):

    def __init__(self, parent, name, is_derived):
        self.name = name
        self.is_derived = is_derived
        parent.items[name] = self
        MiniDerivable.__init__(self, parent)
        self.content = None

    def set_content(self, value):
        self.content = value
        graph.update_subspaces(self)

    # --- Derivable Interface Override ---

    @property
    def self_bases(self):
        return []

    def inherit(self):
        if self.bases:
            self.content = self.bases[0].content


graph = SpaceGraph()



