"""정기 탐색 설정 테스트. 네트워크 없이 돈다."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from explore import standing  # noqa: E402


def _write(tmp_path, questions):
    p = tmp_path / "wl.json"
    p.write_text(json.dumps({"questions": questions}, ensure_ascii=False),
                 encoding="utf-8")
    return str(p)


# --- 설정 적재 ---------------------------------------------------------------

def test_repo_watchlist_is_valid():
    """리포에 커밋된 실제 설정이 항상 유효해야 한다."""
    questions = standing.load()
    assert questions, "정기 탐색 질문이 비어 있다"
    for q in questions:
        assert q["id"] and q["start"] and q["end"]
        assert q["start"] <= q["end"]


def test_duplicate_id_rejected(tmp_path):
    path = _write(tmp_path, [
        {"id": "a", "start": "2027-01-01", "end": "2027-01-31"},
        {"id": "a", "start": "2027-02-01", "end": "2027-02-28"},
    ])
    with pytest.raises(SystemExit, match="중복"):
        standing.load(path)


def test_missing_id_rejected(tmp_path):
    path = _write(tmp_path, [{"start": "2027-01-01", "end": "2027-01-31"}])
    with pytest.raises(SystemExit, match="id"):
        standing.load(path)


# --- 인자 변환 ---------------------------------------------------------------

def test_tag_is_pinned_to_id():
    """tag가 id로 고정돼야 질문 문구를 손봐도 이력이 안 끊긴다."""
    argv = standing.to_argv({"id": "family-feb2027", "start": "2027-02-01",
                             "end": "2027-02-28"})
    assert argv[argv.index("--tag") + 1] == "family-feb2027"


def test_to_argv_applies_defaults():
    argv = standing.to_argv({"id": "x", "start": "2027-02-01", "end": "2027-02-28"})
    pairs = dict(zip(argv[::2], argv[1::2]))
    assert pairs["--adults"] == "1"
    assert pairs["--children"] == "0"
    assert pairs["--nights"] == "4,5"
    assert pairs["--scope"] == "international"


def test_to_argv_carries_pax_and_scope():
    argv = standing.to_argv({
        "id": "x", "start": "2027-02-01", "end": "2027-02-28",
        "nights": "5,6", "adults": 2, "children": 1, "infants": 0,
        "scope": "all", "origin": "PUS", "only": "CTS,FUK", "limit": 5,
    })
    pairs = dict(zip(argv[::2], argv[1::2]))
    assert pairs["--adults"] == "2" and pairs["--children"] == "1"
    assert pairs["--nights"] == "5,6" and pairs["--scope"] == "all"
    assert pairs["--origin"] == "PUS" and pairs["--only"] == "CTS,FUK"
    assert pairs["--limit"] == "5"


def test_optional_flags_absent_when_unset():
    argv = standing.to_argv({"id": "x", "start": "2027-02-01", "end": "2027-02-28"})
    assert "--only" not in argv and "--limit" not in argv and "--origin" not in argv


def test_argv_is_accepted_by_explore_parser():
    """to_argv가 만든 인자를 explore.main이 실제로 파싱할 수 있어야 한다."""
    from explore.main import parse_args
    for q in standing.load():
        a = parse_args(standing.to_argv(q))
        assert a.tag == q["id"]
        assert a.start == q["start"]


# --- 실행 흐름 ---------------------------------------------------------------

def test_one_failure_does_not_abort_the_rest(tmp_path, monkeypatch):
    """주 1회뿐이라 하나 실패했다고 멈추면 그 주 관측이 통째로 빈다."""
    path = _write(tmp_path, [
        {"id": "a", "start": "2027-01-01", "end": "2027-01-31"},
        {"id": "b", "start": "2027-02-01", "end": "2027-02-28"},
        {"id": "c", "start": "2027-03-01", "end": "2027-03-31"},
    ])
    calls = []

    def fake_run(argv):
        tag = argv[argv.index("--tag") + 1]
        calls.append(tag)
        if tag == "b":
            raise RuntimeError("가격 그래프 응답 없음")
        return {"ranking": []}

    monkeypatch.setattr(standing.explore_main, "run", fake_run)
    results = standing.run(["--watchlist", path])

    assert calls == ["a", "b", "c"]
    assert len(results) == 2


def test_only_filters_to_one_question(tmp_path, monkeypatch):
    path = _write(tmp_path, [
        {"id": "a", "start": "2027-01-01", "end": "2027-01-31"},
        {"id": "b", "start": "2027-02-01", "end": "2027-02-28"},
    ])
    calls = []
    monkeypatch.setattr(standing.explore_main, "run",
                        lambda argv: calls.append(argv[argv.index("--tag") + 1]))

    standing.run(["--watchlist", path, "--only", "b"])
    assert calls == ["b"]


def test_unknown_only_raises(tmp_path):
    path = _write(tmp_path, [{"id": "a", "start": "2027-01-01", "end": "2027-01-31"}])
    with pytest.raises(SystemExit, match="찾지 못함"):
        standing.run(["--watchlist", path, "--only", "없음"])


def test_list_does_not_run_scans(tmp_path, monkeypatch):
    path = _write(tmp_path, [{"id": "a", "start": "2027-01-01", "end": "2027-01-31"}])
    monkeypatch.setattr(standing.explore_main, "run",
                        lambda argv: pytest.fail("--list인데 스캔이 돌았다"))
    assert standing.run(["--watchlist", path, "--list"]) == []
