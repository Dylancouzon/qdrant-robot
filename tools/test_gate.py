"""Enforcement checks for tools/gate.py, run against a throwaway git repository."""
import subprocess
from pathlib import Path

import pytest

import gate


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(args, cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    sh(tmp_path, "git", "init", "-q", "-b", "main")
    sh(tmp_path, "git", "config", "user.email", "t@t")
    sh(tmp_path, "git", "config", "user.name", "t")
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "STATE.md").write_text("state\n")
    (tmp_path / "reviews").mkdir()
    sh(tmp_path, "git", "add", "-A")
    sh(tmp_path, "git", "commit", "-q", "-m", "init")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "checks", lambda: 0)  # checks are tested in CI itself
    return tmp_path


def stamp(repo: Path, tree: str, verdict: str = "PASS") -> None:
    (repo / "reviews" / f"{verdict}-review.md").write_text(
        f"<!-- tree: {tree} -->\nfindings\nVERDICT: {verdict}\n")


def test_bookkeeping_is_outside_the_code_tree(repo):
    (repo / "STATE.md").write_text("changed\n")
    assert gate.code_tree("worktree") == gate.code_tree("HEAD")


def test_untracked_code_changes_the_tree(repo):
    (repo / "new.py").write_text("y = 2\n")
    assert gate.code_tree("worktree") != gate.code_tree("HEAD")


def test_precommit_reminds_but_blocks_only_failing_checks(repo, monkeypatch, capsys):
    (repo / "app.py").write_text("x = 2\n")
    sh(repo, "git", "add", "-A")
    assert gate.precommit() == 0
    assert "Reminder" in capsys.readouterr().err
    stamp(repo, gate.code_tree("worktree"))
    assert gate.precommit() == 0
    assert "Reminder" not in capsys.readouterr().err
    monkeypatch.setattr(gate, "checks", lambda: 1)
    assert gate.precommit() == 1
