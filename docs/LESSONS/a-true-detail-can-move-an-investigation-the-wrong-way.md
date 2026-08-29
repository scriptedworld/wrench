# A true detail can move an investigation the wrong way

## What happened

`python3-yaml` was installed on this machine and dotfiles declared it, with a
comment saying the system `python3` needs a YAML parser before tooling exists.
wrench had been shaped around that claim.

The investigation reached the right answer twice and left it once.

dotfiles first called the package an orphan swept up in a cleanup. Our user then
mentioned a QEMU install test, and dotfiles withdrew the orphan reading and
marked it unverified.

**The QEMU run was real and had nothing to do with the package.** It arrived
mid-investigation, it was true, and it moved the reading away from an answer
that was correct. The package came in as a dependency of `llvm-19-tools`. Only
the declaration was ever dotfiles', and the reason in its comment was invented.

## Why a true detail is worse than a false one here

A false detail gets checked and discarded. A true one is checked, confirmed, and
then given weight it has not earned, because confirming it feels like progress.

The QEMU test existed. Confirming it existed said nothing about whether it
installed this package, and that second question never got asked, because the
first one came back yes.

## The rule

**Confirm that a detail is true and separately that it bears on the question.**
Those are two checks and the first one passing makes the second easy to skip.

The form that would have caught it:

    does the QEMU test exist          yes
    did it install python3-yaml       unasked

Ask what would be different if the detail were false. If the answer is nothing,
it is not evidence for this question however true it is.

## What settled it

Four commands, none of which involved the QEMU test at all:

    dotfiles bf38481             resolves, subject matches
    packages.toml                no longer declares it, and says deliberately not
    apt-mark showmanual          does not list it
    dpkg -s python3-yaml         install ok installed

Undeclared and still present, which is what a dependency-installed package looks
like.

## The related shape

This is the same failure as a check that answers a weaker question than its
name. There, an instrument returns green about something narrower than the
reader assumes. Here, a fact is true about something narrower than the
investigation assumes. Both pass a check that was never the one that mattered.
