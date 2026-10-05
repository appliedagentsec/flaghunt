import pytest

from flaghunt.challenge import Challenge, discover, hash_flag


def test_discovers_starter_challenges(challenges_dir):
    ids = {c.id for c in discover(challenges_dir)}
    assert {"warmup-strings", "layered-encoding", "hidden-archive", "single-byte-xor"} <= ids


def test_flag_check_uses_hash(tmp_path):
    (tmp_path / "challenge.yaml").write_text(
        "id: t\nname: T\ncategory: misc\ndifficulty: easy\ndescription: d\n"
        f"flag_sha256: {hash_flag('flaghunt{yes}')}\n"
    )
    c = Challenge.load(tmp_path)
    assert c.check_flag("flaghunt{yes}")
    assert c.check_flag("  flaghunt{yes}\n")
    assert not c.check_flag("flaghunt{no}")


def test_missing_fields_are_reported(tmp_path):
    (tmp_path / "challenge.yaml").write_text("id: t\nname: T\n")
    with pytest.raises(ValueError, match="flag_sha256"):
        Challenge.load(tmp_path)


def test_missing_file_is_reported(tmp_path):
    (tmp_path / "challenge.yaml").write_text(
        "id: t\nname: T\ncategory: misc\ndifficulty: easy\ndescription: d\nflag_sha256: x\nfiles: [files/nope]\n"
    )
    with pytest.raises(FileNotFoundError):
        Challenge.load(tmp_path)
