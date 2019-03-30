import pytest
import modelx as mx


def func1(x):
    return 2 * x


src_func1 ="""\
def func1(x):
    return 2 * x
"""


@pytest.fixture
def testspace():
    m, s = mx.new_model(), mx.new_space()

    s.new_cells(name="func1_code", formula=func1)
    s.new_cells(name="func1_src", formula=src_func1)

    s.new_cells(name="lambda1_code", formula=lambda x: 3 * x)
    s.new_cells(name="lambda1_src", formula="lambda x: 3 * x")

    return s


def test_formula_source(testspace):
    s = testspace

    assert repr(s.func1_code.formula) == repr(s.func1_src.formula)
    assert repr(s.lambda1_code.formula) == repr(s.lambda1_src.formula)

    assert s.func1_code[2] == s.func1_src[2]
    assert s.lambda1_code[2] == s.lambda1_src[2]



