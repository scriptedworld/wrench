# A retired field stays in the schema where the runner refuses it by name

`jig`, `in`, `config-dir`, `output-dir` and `definitions` describe nested jigs,
which bolt retired. Once wrench's own gate stopped using them, nothing in the
estate did, and the question was whether the schema should stop describing them.

It should not. They stay, and their descriptions say they are retired.

## What decided it

Three schemas against one jig carrying all five fields.

    current    validates, and says nothing
    dropped    'command' is a required property, at tasks/0
    refusing   '.' should not be valid under {}, at one of the five

Dropping them is the option that reads right and measures worst. The schema
sets no `additionalProperties` anywhere, so a retired field is not an unexpected
key. What removal actually does is delete the jig-task branch of the task
`oneOf`, leaving `required: [command]` to fail. A reader is told a command is
missing from a task that deliberately has none.

Refusing them inside the schema, with a `not` carrying the replacement in a
`$comment`, gets the failure to the right field and still says nothing useful. A
validator prints its own message, and the `$comment` is only reached by a
consumer that goes looking for it.

Keeping them lets the document validate and the runner speak:

    kind: jig-task-retired
    task python-common carries the retired jig field; run the jig as a command
    instead, bolt <jig> <directory>

That names the task, the field and the replacement. No schema keyword produces
it, because the schema knows the shape of a valid document and not what a
retired feature was replaced by.

## The general form

**An earlier error is not automatically a better one.** The argument for
dropping was that the schema accepts a document the runner will refuse, putting
the error a layer later than it could be. Later is worse only when the earlier
layer can say as much. Here it cannot, and the measurement is the difference
between a message naming the fix and one naming a missing key.

So a field is dropped from the schema when nothing refuses it, and kept when
something refuses it well. The test is what a reader is told, not which layer
tells them.

## What was actually wrong

The five descriptions were written in the present tense, as things a jig author
should reach for. `config-dir` said *"Where the child looks for jigs. Left out,
it inherits."* Nothing in that sentence suggests no runner has read it since
bolt `f3304d8`.

That is the defect the task found without naming: not a schema describing too
much, but a schema describing a dead feature as a live one. Each description now
opens with the retirement, and the `oneOf` branch carries why it is kept, so the
next reader deciding this question finds the measurement rather than repeating
it.

## Where the compatibility surface was

The bolt session scanned all 35 jigs in the estate. Beyond wrench's own two
tasks, nothing used these fields, and nothing used `short-circuit-failure`,
`time-limit`, `optional` or `adapter-command` either. `bolt.wrench-quality.yaml`
was the whole surface, which is why this could be settled on its merits rather
than against a migration.
