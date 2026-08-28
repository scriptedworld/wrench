# reaching the library

**FR-6.1 and FR-6.2 are the Python pack's alone**, and are the only rows
here that one pack holds and another cannot. They are about a Python pack reaching
a Python environment; the Go pack cannot discharge them and should not try. Every
other row states one contract that every pack implements, and both suites cite it.

**So a `COVERS:` mark for these three appearing only in `python/tests/` is a
statement rather than a gap.** Anywhere else in this document, a row cited by one
suite and not the other is the divergence FR-5.7 exists to catch.
