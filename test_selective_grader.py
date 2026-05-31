from pipelines.specialist_runner import _should_use_grader


def test_should_use_grader():
    assert not _should_use_grader(0.30, "tuyen_sinh"), "Qc=0.30 should skip grade"
    assert not _should_use_grader(0.20, "bieu_mau"), "Qc=0.20 should skip grade"

    assert _should_use_grader(0.40, "diem_thi"), "Qc=0.40 should use grade"
    assert _should_use_grader(0.50, "ma_tran"), "Qc=0.50 should use grade"
    assert _should_use_grader(0.60, "khao_thi"), "Qc=0.60 should use grade"

    assert not _should_use_grader(0.70, "tuyen_sinh"), "Qc=0.70 should skip grade"
    assert not _should_use_grader(0.85, "bieu_mau"), "Qc=0.85 should skip grade"

    assert not _should_use_grader(0.349, "tuyen_sinh"), "Qc=0.349 should skip"
    assert _should_use_grader(0.350, "tuyen_sinh"), "Qc=0.350 should grade (boundary)"
    assert _should_use_grader(0.649, "tuyen_sinh"), "Qc=0.649 should grade (boundary)"
    assert not _should_use_grader(0.650, "tuyen_sinh"), "Qc=0.650 should skip"

    print("PASS: All selective grader tests passed!")


if __name__ == "__main__":
    test_should_use_grader()
