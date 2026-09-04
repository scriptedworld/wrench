"""Tests for `bin/githooks/pre-commit`, the commit-time half of hard rule 4.

The gate checks the suppression register when somebody runs the gate. This hook
runs at the moment a pragma would land, which is the only point at which it
cannot be forgotten, so it is the check that has to work when nobody is looking.

**Both directions, and the negative control is the point.** Showing that a
commit was refused does not show that this hook refused it: a red exit status
looks identical whatever produced it. Every test here pairs the refusal with the
same commit succeeding when the hook is not installed, so the hook is what
changed rather than something in the environment.

That control was suggested by the dotfiles session, whose own dispatch tests do
the same thing by pointing `core.hooksPath` at an empty directory.

**What these do not cover, stated so nobody reads more into a green run.** They
install the hook as `.git/hooks/pre-commit` and redirect `HOME`, so git reads it
directly. In a real checkout `core.hooksPath` sends git to `~/.git-hooks`, whose
dispatch runs `.git/hooks/pre-commit.local` instead. So these test the hook's
logic and not the wiring that reaches it, and the wiring is the half that has
already been silently inert once. dotfiles owns the dispatch and tests it.

Nothing here checks that a given checkout has the symlink installed at all. That
is a per-checkout manual step, and an installed check that does not run is
indistinguishable from a passing one.

**These survived a falsification pass, which is the only thing separating a test
that passed from a test that cannot fail.** Two mutations of the hook, each
failing exactly the tests it should and no others:

    hook replaced by `exit 0`   the two refusal tests fail
    hook replaced by `exit 1`   the clean-source test fails

`test_the_same_commit_succeeds_without_the_hook` passes under both, correctly,
because it installs no hook and must be insensitive to what the hook does.

Run that pass and then distrust it, which is the dotfiles session's finding: their
own falsification harness reported five tests passing under every mutation
because `local got; [ $? = 0 ]` reads `local`'s status and not the command's, so
the harness had never compared anything.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "bin" / "githooks" / "pre-commit"
CHECKER = REPO / "bin" / "no-unregistered-suppression.py"

# An empty register, not wrench's own. The checker reports a registered pragma
# that the source does not carry, so copying the real file into a tree that does
# not carry an entry for a pragma the tools themselves hold makes every commit
# here fail as a phantom rather than for the reason under test.
PROBE_REGISTER = """Register.

Nothing in the probe's own source is suppressed, which is what makes an
unregistered pragma there the only thing the hook can be refusing.

    bin/suppression-register.py    # pylint: disable=duplicate-code

The checker scans everything in the tree it is pointed at, and the tree carries
toolbox's two checkers so the hook can run them. One of them acquired that mark
on 2026-09-04, when toolbox registered the duplication between its own scripts.
Without this row the probe fails on a pragma that is not the probe's, and every
test here refuses for the wrong reason.
"""

# The checker shells out to this, which is a symlink into toolbox. Copied
# resolved, because a symlink into a sibling repository would make these tests
# fail when that repository is absent, which is the wrong reason to fail.
#
# Leaving it out is how the two refusal tests here first passed: the hook
# refused because this file was missing, not because a pragma was unregistered,
# and both looked like the hook working. The clean-source test is what caught
# it, which is the whole argument for a control.
SCANNER = REPO / "bin" / "suppression-register.py"

CLEAN_SOURCE = "package probe\n\nfunc Thing() int { return 1 }\n"
PRAGMA_SOURCE = "package probe\n\nfunc Thing() int { return 1 } //nolint:all\n"


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(root),
            "GIT_AUTHOR_NAME": "probe",
            "GIT_AUTHOR_EMAIL": "probe@example.invalid",
            "GIT_COMMITTER_NAME": "probe",
            "GIT_COMMITTER_EMAIL": "probe@example.invalid",
        },
    )


def repository(tmp_path: Path, *, source: str, install_hook: bool) -> Path:
    """A throwaway repository carrying wrench's checker, register and hook.

    `HOME` is redirected at it, so the machine's own `core.hooksPath` and global
    hooks cannot reach in and decide the answer.
    """
    root = tmp_path / "probe"
    (root / "bin").mkdir(parents=True)
    (root / "python").mkdir()

    shutil.copy(CHECKER, root / "bin" / CHECKER.name)
    shutil.copy(SCANNER, root / "bin" / SCANNER.name)
    (root / "SUPPRESSIONS").write_text(PROBE_REGISTER)
    (root / "probe.go").write_text(source)

    git(root, "init", "-q", "-b", "main")

    if install_hook:
        hooks = root / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        shutil.copy(HOOK, hooks / "pre-commit")
        (hooks / "pre-commit").chmod(0o755)

    git(root, "add", "-A")
    return root


def commit(root: Path) -> subprocess.CompletedProcess[str]:
    return git(root, "commit", "-m", "probe")


def head_exists(root: Path) -> bool:
    return git(root, "rev-parse", "HEAD").returncode == 0


def test_an_unregistered_pragma_is_refused(tmp_path):
    """The case the hook exists for."""
    root = repository(tmp_path, source=PRAGMA_SOURCE, install_hook=True)

    done = commit(root)

    assert done.returncode != 0, "an unregistered pragma was committed"
    assert "Register it in SUPPRESSIONS" in done.stdout + done.stderr
    assert not head_exists(root), "the commit landed despite the refusal"


def test_the_same_commit_succeeds_without_the_hook(tmp_path):
    """The control. Without this the test above shows only that something
    refused, and a red exit status looks the same whatever produced it."""
    root = repository(tmp_path, source=PRAGMA_SOURCE, install_hook=False)

    done = commit(root)

    assert done.returncode == 0, done.stdout + done.stderr
    assert head_exists(root), "nothing was committed, so the pair proves nothing"


def test_source_with_no_pragma_commits_with_the_hook_installed(tmp_path):
    """The hook refuses a pragma rather than refusing everything. A guard that
    stops every commit passes the test above and is useless."""
    root = repository(tmp_path, source=CLEAN_SOURCE, install_hook=True)

    done = commit(root)

    assert done.returncode == 0, done.stdout + done.stderr
    assert head_exists(root)


def test_the_refusal_names_what_to_do_and_refuses_the_way_round_it(tmp_path):
    """A refusal that does not say what to do next gets worked around, and the
    obvious way round is the one option whose whole purpose is to skip it."""
    root = repository(tmp_path, source=PRAGMA_SOURCE, install_hook=True)

    output = commit(root).stdout + commit(root).stderr

    assert "SUPPRESSIONS" in output, "the refusal does not say where to register it"
    assert "--no-verify" in output, "the refusal does not address the way round it"
