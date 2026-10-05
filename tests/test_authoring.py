import pytest
import yaml

from flaghunt.authoring import check_challenge, new_challenge
from flaghunt.challenge import Challenge, hash_flag

FLAG = "flaghunt{author_test}"


@pytest.fixture
def dirs(tmp_path):
    challenges = tmp_path / "repo" / "challenges"
    challenges.mkdir(parents=True)
    return challenges, tmp_path / "private"


def make(dirs, **overrides):
    challenges, private = dirs
    args = dict(id="demo-one", name="Demo", category="misc", difficulty="easy", flag=FLAG) | overrides
    return new_challenge(challenges, private, **args)


def finish(root, content=b"nothing to see"):
    """Fill in the scaffold the way an author would."""
    (root / "files" / "data.txt").write_bytes(content)
    meta = yaml.safe_load((root / "challenge.yaml").read_text())
    meta["description"] = "Find the flag."
    meta["files"] = ["files/data.txt"]
    (root / "challenge.yaml").write_text(yaml.safe_dump(meta))


def test_new_scaffolds_hashed_flag_and_private_files(dirs):
    root, private = make(dirs)
    meta = yaml.safe_load((root / "challenge.yaml").read_text())
    assert meta["flag_sha256"] == hash_flag(FLAG)
    assert FLAG not in (root / "challenge.yaml").read_text()
    assert (private / "solve.sh").exists() and FLAG in (private / "NOTES.md").read_text()


@pytest.mark.parametrize("bad", [dict(id="Bad_ID"), dict(flag="flag{wrong}"), dict(category="nope")])
def test_new_rejects_bad_input(dirs, bad):
    with pytest.raises(ValueError):
        make(dirs, **bad)


def test_new_refuses_private_dir_inside_repo(dirs):
    challenges, _ = dirs
    with pytest.raises(ValueError, match="inside the repo"):
        new_challenge(challenges, challenges.parent / "secrets", "demo-one", "Demo", "misc", "easy", FLAG)


def test_check_flags_unfinished_scaffold(dirs):
    root, private = make(dirs)
    report = check_challenge(root, private, run_solution=False)
    assert not report.ok
    assert any("TODO" in e for e in report.errors)


def test_check_warns_about_plaintext_flag_and_unlisted_files(dirs):
    root, private = make(dirs)
    finish(root, content=f"here: {FLAG}".encode())
    (root / "files" / "stray.bin").write_bytes(b"x")
    report = check_challenge(root, private, run_solution=False)
    assert report.ok
    assert any("plain text" in w for w in report.warnings)
    assert any("stray.bin" in w for w in report.warnings)


@pytest.mark.docker
def test_check_runs_reference_solution_in_sandbox(dirs):
    root, private = make(dirs)
    finish(root, content=b"ZmxhZ2h1bnR7YXV0aG9yX3Rlc3R9")  # base64 of the flag
    (private / "solve.sh").write_text("base64 -d data.txt; echo\n")
    report = check_challenge(root, private)
    assert report.ok, report.errors
    assert report.solution == "solved in the sandbox"

    (private / "solve.sh").write_text("echo flaghunt{wrong}\n")
    report = check_challenge(root, private)
    assert not report.ok and report.solution == "FAILED"


def test_scaffold_loads_as_challenge_once_finished(dirs):
    root, _ = make(dirs)
    finish(root)
    assert Challenge.load(root).check_flag(FLAG)
