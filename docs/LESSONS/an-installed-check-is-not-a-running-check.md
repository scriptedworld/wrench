# An installed check is not a running check

A pre-commit hook was written, made executable, and symlinked into
`.git/hooks/pre-commit`. Every one of those steps succeeded. The hook never ran,
and the only reason anybody found out was that it was asked to refuse something.

## What happened

`core.hooksPath` is set in `~/.gitconfig` to `~/.git-hooks`. **git then consults
that directory and no other**, so `.git/hooks/` is dead in every repository on
this machine. There is no warning, no message, and `ls -l .git/hooks/pre-commit`
shows exactly what a working installation shows.

    $ git config --show-origin --get core.hooksPath
    file:/home/ancient/.gitconfig   /home/ancient/.git-hooks

The probe that found it: a Go file carrying `//nolint:gochecknoglobals`,
registered nowhere, which the hook existed to refuse.

    [main 0247224] test: this must not land
     1 file changed, 3 insertions(+)
       commit exit 0

## The general shape

**Installing a check and the check running are two facts, and the first is not
evidence of the second.** They look identical from outside: the file is there,
the permissions are right, the syntax is valid, nothing errors. Every observation
available short of making it refuse is consistent with both.

`docs/LESSONS/a-check-that-answers-a-weaker-question.md` names the class, and
bolt's file of that name is the collection. Every instance ran and measured the
wrong thing,
so every one produced output that could be read sceptically. **This one produced
none**, which is the harder case: scepticism has nothing to bite on, and the
absence of a complaint is what a passing check looks like.

## What to do instead

**Verify a guard by making it fail.** Not by reading it, not by running it by
hand, and not by checking it is installed. Give it the thing it exists to refuse
and confirm two facts:

    the exit status is non-zero
    the side effect did not happen

The second matters on its own. A hook can exit non-zero and the commit still
land, and the exit status alone would not say so. Here that is HEAD:

    before=$(git rev-parse HEAD)
    ...attempt...
    [ "$before" = "$(git rev-parse HEAD)" ] && echo REFUSED

**The probe belongs in the record.** `clank/inbox/dotfiles/no-global-pre-commit-dispatch/repro.sh`
builds a throwaway repository, gives it a hook that only refuses, commits, and
reports whether the commit landed. It regenerates the reading in a second, and
it fails loudly if the finding ever goes stale.

## What it also caught, immediately

The first commit the working hook ever saw, it refused, and correctly: a comment
in `bin/test-requirement-count.py` had wrapped so the pragma spelling opened a
line, and the register read the prose as a bare pragma silencing the whole file.
That is the same wrapping hazard the file's own comment was describing.

**A guard earns its place by refusing something on the day it lands.** This one
did, on a defect nothing else in the estate was positioned to see.
