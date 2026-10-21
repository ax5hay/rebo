from reportsbot.evals import columns_match


def test_extra_readable_columns_are_allowed_but_values_must_match():
    gold = [[1, "a"], [2, "b"]]
    assert columns_match(gold, [["a", 1, "Oak Court"], ["b", 2, "Elm"]])
    assert not columns_match(gold, [["a", 1], ["c", 2]])
    assert not columns_match(gold, [["a", 1]])                         # row count differs
    assert not columns_match([[1, 1]], [[1, 2]])                         # a predicted column is used once


def test_presentation_tolerances():
    assert columns_match([[11.046]], [[65, 11.0]])                       # rounded average
    assert columns_match([["Ava", "Kim", 9]], [["Ava Kim", 9]], ["first_name", "last_name", "n"])  # joined name
    assert columns_match([[7, "Oak"]], [["Oak"]], ["unit_id", "building"])  # surrogate key optional
    assert not columns_match([[7, "Oak"]], [["Oak"]], ["units", "building"])  # a real value is not optional
    assert columns_match([[None, None]], [[None]], ["first_name", "last_name"])  # empty name both sides
