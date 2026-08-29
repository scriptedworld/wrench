# An unbumped version is a change nobody receives

## What happened

The Python pack took eight commits of substantive change while its version
stayed `0.1.0`. Among them the error base class was renamed `WrenchError` to
`Error`, which is breaking, and the public API gained annotations, protocols and
a widened path type.

The first consumer to move off an editable install did not receive any of it.
uv resolves from its cache by version, so an unchanged version number is a
package it already has, and it does not look further. It took an explicit

    uv sync --reinstall-package wrench

before a source change reached the consumer at all.

## Why an editable install hid it

While every consumer installed editable, the version number did nothing. An
editable install points at the source tree, so a change is live the moment it is
committed and no resolution happens. The number was inert rather than correct.

Carrying the schemas as source removed the reason for the editable install, and
the moment a consumer took a copied install instead, the inert number started
deciding what they got.

So this arrived as a consequence of a fix, and the fix was still right. The
version had been wrong the whole time and nothing had asked it a question.

## What to do

Bump the pack version in the same commit as the change to its surface. Not at a
release, because there is no release step here and a consumer resolves whenever
it syncs.

A consumer that suspects it is holding a stale copy can check what it actually
has rather than what the tree says:

    python -c "import wrench, pathlib; print(pathlib.Path(wrench.__file__).resolve())"

A path into site-packages is a copy and a path into the repository is editable.

## The general shape

Two environments, and only one of them is the one being tested. It is the same
trap as a tool installed editable that carries code but not its dependencies,
and the same as a consumer enforcing the schema it was built with: a change is
committed here and something between here and the consumer decides when it
arrives.

The tell in all three is that the symptom is an absence. Nothing fails, nothing
is logged, and the consumer runs correctly against an older contract.
