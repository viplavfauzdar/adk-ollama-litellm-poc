from app.tools import calc
def test_calc():
    assert calc("2*(5+7)") == "24"
