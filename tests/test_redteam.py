from evaluation.run_redteam import load_lines, rate


def test_suites_are_large_enough():
    assert len(load_lines("attacks.txt")) >= 20 and len(load_lines("benign.txt")) >= 20


def test_rate():
    assert rate([True, False, True, True]) == 0.75
