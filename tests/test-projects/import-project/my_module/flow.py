import syntask

from .utils import get_output


@syntask.flow(name="test")
def test_flow():
    return get_output()


@syntask.flow(name="test")
def prod_flow():
    return get_output()
