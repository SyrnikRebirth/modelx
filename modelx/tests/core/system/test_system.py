import sys
from textwrap import dedent
from modelx.core.api import *
from modelx.core.errors import DeepReferenceError
import pytest


@pytest.fixture
def testmodel():
    m, s = new_model(), new_space()
    return m


def test_defcells_withname(testmodel):
    @defcells(name="bar")
    def foo(x):
        if x == 0:
            return 123
        else:
            return bar(x - 1)

    assert foo[10] == 123


def test_defcells_withspace(testmodel):
    @defcells(space=cur_space())
    def foo(x):
        if x == 0:
            return 123
        else:
            return foo(x - 1)

    assert foo[10] == 123


def test_defcells_lambda_object(testmodel):

    fibo = defcells(space=cur_space(), name="fibo")(
        lambda x: x if x == 0 or x == 1 else fibo[x - 1] + fibo[x - 2]
    )

    assert fibo(10) == 55


def test_decells_lambda_source(testmodel):

    src = "lambda x: x if x == 0 or x == 1 else fibo2[x - 1] + fibo2[x - 2]"
    fibo2 = cur_space().new_cells(name="fibo2", formula=src)

    assert fibo2(10) == 55


def test_deep_reference_error():

    from modelx.core import mxsys

    last_maxdepth = mxsys.callstack.maxdepth
    set_recursion(3)

    errfunc = dedent(
        """\
    def erronerous(x, y):
        return erronerous(x + 1, y - 1)"""
    )

    space = new_model(name="ErrModel").new_space(name="ErrSpace")
    cells = space.new_cells(formula=errfunc)
    with pytest.raises(DeepReferenceError) as errinfo:
        cells(1, 3)

    errmsg = dedent(
        """\
    Formula chain exceeded the 3 limit.
    Call stack traceback:
    0: ErrModel.ErrSpace.erronerous(x=1, y=3)
    1: ErrModel.ErrSpace.erronerous(x=2, y=2)
    2: ErrModel.ErrSpace.erronerous(x=3, y=1)
    3: ErrModel.ErrSpace.erronerous(x=4, y=0)"""
    )

    set_recursion(last_maxdepth)
    assert errinfo.value.args[0] == errmsg


def test_configure_python():
    configure_python()
    assert sys.getrecursionlimit() == 10**6


def test_restore_python():

    restore_python()

    assert sys.getrecursionlimit() == 1000
    assert not hasattr(sys, "tracebacklimit")

    configure_python()


def test_rename_same_name():

    m1 = new_model("dupname")
    with pytest.warns(UserWarning):
        m2 = new_model("dupname")

    assert "dupname_BAK" in m1.name
    assert m1.name in get_models()


def test_cur_model_change():
    m1 = new_model()
    m2 = new_model()
    assert cur_model() is m2
    m = cur_model(m1.name)
    assert m is cur_model() is m1
