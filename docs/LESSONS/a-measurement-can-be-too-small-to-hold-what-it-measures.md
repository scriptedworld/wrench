# A measurement can be too small to hold what it measures

## What happened

A Zig spike was timed against the Go, Rust and Python packs on
`testdata/canonical/an-envelope/input.yaml`, twelve lines, one load per process.

    Zig     627us      Rust   6383us      Go   8669us

That was reported as Zig being an order of magnitude faster, and the gap was
attributed to the codec. Both halves were wrong.

A document that small finishes before anything can be timed, so a bigger file
and a loop were both wanted. Both were built. Varying only the iteration
count, on `github-workflow.json` against the draft-07 meta-schema:

                 1 iteration   50 iterations   marginal per iteration
    Zig              5.4ms         56.4ms          1.04ms
    Rust             5.3ms         21.0ms          0.32ms
    Go              16.1ms        216.5ms          4.09ms

Fixed cost is a tie between Zig and Rust. Marginal cost is Rust's by 3.2x. The
first run had measured **startup and schema compilation on a document holding no
throughput to measure**, and reported it as throughput.

Size went the other way and is the one thing Zig won outright: 348KB stripped
against Go's 3.5MB and Rust's 5.9MB. So the honest summary of the whole spike is
that Zig is decisively smaller, Rust is faster per document, and the crossover
is around three documents per process.

The codec attribution was worse than unproven. Isolated on matched pairs of the
same content, YAML costs 2.36x JSON in Zig, 3.54x in Rust and 2.35x in Go, and
the first run had put Zig on YAML. **The explanation offered had the sign
backwards.**

## What it cost

A headline published twice, a working note carrying it, and a commit
message. All three needed correcting, and the correction is now longer than the
original claim.

## The general shape

**A measurement whose subject is absent returns a number anyway**, and the
number looks like an answer. Nothing in `627us` announces that it contains no
throughput. The tell is not in the result; it is in whether the workload was
large enough for the quantity of interest to exist in it.

The hardware counters said so and were ignored. Every command under 10ms had a
sigma exceeding its mean and a minimum sample of 0, meaning most runs recorded
nothing. That was visible in the first run's output and read past.

## The sharper form, which came from qwark

**The case a property is about can be the one case no corpus contains.**

Their instance: an engine's deny-by-default behaviour is invisible on real
traffic, because real traffic always matches something and two architectures
differ only on the ruleset that matches nothing.

## Where this lands on wrench directly

**`testdata/canonical/` cannot validate a property wrench's own documents never
exercise.** `each-format-has-one-authority-for-what-a-document-means.md` already
records that the range rule is defensive for consumers rather than load-bearing
for wrench's own traffic, and that the shipped schemas carry one integer field,
an execution index.

So a fixture set grown from real envelopes never goes near int64, and would
report a pack that widens and a pack that refuses as identical.

## What to do instead

**Size the workload to the quantity, then check the workload contains it.** For
timing, run long enough that the counters stabilise: sigma below the mean and no
zero samples. For a property, ask what input would distinguish the two
behaviours, and confirm the corpus has one.

**Author the distinguishing cases when no corpus supplies them**, mark them with
the reason they exist, and do not prune them as unrealistic. Being unrealistic
is what they are for.

**Put the control before the result.** A replay harness here now prints seven
discriminating commands and their verdicts *above* its agreement count, so the
number cannot be read without its own control. That is stronger than a caveat
somebody has to remember, and it is the same move as stating a fixture's purpose
in the fixture.

## Its neighbour

`a-fixture-set-agrees-about-the-values-somebody-thought-of.md` is the inverse and
the two are worth reading together. There the danger is a value nobody thought
of. Here it is a value nobody would naturally write down, which no amount of
harvesting real traffic will ever supply.
