import json

from flaghunt.site import build_site
from flaghunt.transcript import MASKED_FLAG, Transcript


def write_run(dirpath, flag="flaghunt{secret}"):
    t = Transcript(agent={"name": "a", "budget": {"max_steps": 1, "max_submissions": 1, "time_limit_s": 60}},
                   challenge={"id": "c", "name": "C", "category": "misc", "difficulty": "easy"})
    t.log("model", model="m", reasoning=f"it is {flag}", text="</script><b>x</b>", input_tokens=1, output_tokens=1)
    t.log("submit", flag=flag, correct=True)
    t.outcome, t.solved = "solved", True
    return t.save(dirpath)


def test_site_embeds_runs_and_masks_unmasked_flags(tmp_path):
    write_run(tmp_path / "results")
    out = build_site(tmp_path / "results", tmp_path / "site", "https://example.org/repo")
    html = out.read_text()
    assert "flaghunt{secret}" not in html
    assert MASKED_FLAG in html
    assert "/*__DATA__*/" not in html
    assert "</script><b>" not in html  # embedded text can't close the script tag
    assert '"repo_url": "https://example.org/repo"' in html


def test_transcript_mask_replaces_everywhere():
    t = Transcript(agent={"name": "a"}, challenge={"id": "c"})
    t.log("tool_result", output="flaghunt{x} and again flaghunt{x}")
    t.mask("flaghunt{x}")
    assert json.dumps(t.to_dict()).count("flaghunt{x}") == 0


def test_site_masks_flags_the_model_printed_but_never_submitted(tmp_path):
    from flaghunt.challenge import hash_flag
    ch = tmp_path / "challenges" / "c"
    ch.mkdir(parents=True)
    (ch / "challenge.yaml").write_text(
        "id: c\nname: C\ncategory: misc\ndifficulty: easy\ndescription: d\n"
        f"flag_sha256: {hash_flag('flaghunt{seen_not_sent}')}\n")
    t = Transcript(agent={"name": "a"}, challenge={"id": "c", "name": "C", "category": "misc", "difficulty": "easy"})
    t.log("model", model="m", reasoning="", text="The password is flaghunt{seen_not_sent}.",
          input_tokens=1, output_tokens=1)
    t.outcome = "gave_up"
    t.save(tmp_path / "results")
    html = build_site(tmp_path / "results", tmp_path / "site", challenges_dir=tmp_path / "challenges").read_text()
    assert "seen_not_sent" not in html and MASKED_FLAG in html
