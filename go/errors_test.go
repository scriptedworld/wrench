package wrench_test

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench/go"
)

// errFromSeam is what a seam fails with when the test is about what wrench does
// with the failure rather than about the failure itself.
var errFromSeam = errors.New("the seam refused")

// A kindCase drives one failure kind through a public call and says what the
// message and the chain must carry afterwards.
type kindCase struct {
	kind  string
	step  string
	verb  string
	cause error
	run   func(schema wrench.Schema) error
}

// theErrorOf discards the value of a call that returns one beside its error, so
// a case whose call hands back a document reads like a case whose call hands
// back an error alone. The error is passed through untouched: wrapping it here
// would make `errors.Unwrap` reach this helper's wrap rather than the cause the
// assertions are about, and the test would pass on an error carrying nothing.
func theErrorOf(_ any, err error) error { return err }

// kindCases is every kind a seam can fail at, one case each.
//
// A function rather than a package variable: a table at package level is
// mutable state any test in the package could write through.
func kindCases() []kindCase {
	return []kindCase{
		{
			kind:  "read",
			step:  wrench.StepRead,
			verb:  "reading",
			cause: errFromSeam,
			run: func(schema wrench.Schema) error {
				reader := &stubReader{err: &wrench.ReadError{Err: errFromSeam}}
				return theErrorOf(wrench.LoadYAMLFile("named.yaml", schema, reader))
			},
		},
		{
			kind:  "parse",
			step:  wrench.StepParse,
			verb:  "parsing",
			cause: nil,
			run: func(schema wrench.Schema) error {
				reader := &stubReader{data: []byte("a: [1,\n")}
				return theErrorOf(wrench.LoadYAMLFile("named.yaml", schema, reader))
			},
		},
		{
			kind:  "encode",
			step:  wrench.StepEncode,
			verb:  "encoding",
			cause: nil,
			run: func(schema wrench.Schema) error {
				// A channel has no canonical form, so the codec refuses it
				// before any writer is reached.
				return wrench.SaveYAMLFile(map[string]any{"a": make(chan int)},
					"named.yaml", schema, &stubWriter{})
			},
		},
		{
			kind:  "write",
			step:  wrench.StepWrite,
			verb:  "writing",
			cause: errFromSeam,
			run: func(schema wrench.Schema) error {
				writer := &stubWriter{err: &wrench.WriteError{Err: errFromSeam}}
				return wrench.SaveYAMLFile(map[string]any{"a": 1}, "named.yaml", schema, writer)
			},
		},
	}
}

// assertKindSaysItself holds the assertions one case is judged by, so the table
// above stays a table and each case is read beside the others.
func assertKindSaysItself(t *testing.T, c kindCase, schema wrench.Schema) {
	t.Helper()

	err := c.run(schema)
	if err == nil {
		t.Fatalf("%s: nothing failed", c.kind)
	}

	var stepped interface{ Step() string }
	if !errors.As(err, &stepped) {
		t.Fatalf("%s: %T is outside the family", c.kind, err)
	}
	if stepped.Step() != c.step {
		t.Errorf("%s: step is %q, want %q", c.kind, stepped.Step(), c.step)
	}

	// The message says the step as prose and names the file the caller asked
	// for, which is the path the seam never had.
	if !strings.Contains(err.Error(), c.verb) {
		t.Errorf("%s: %q does not say %q", c.kind, err.Error(), c.verb)
	}
	if !strings.Contains(err.Error(), "named.yaml") {
		t.Errorf("%s: %q does not name the file", c.kind, err.Error())
	}

	// The cause is always reachable. A wrap that discarded it would be worse
	// than the leak it replaced.
	if c.cause != nil && !errors.Is(err, c.cause) {
		t.Errorf("%s: the cause is not reachable through %q", c.kind, err.Error())
	}
	if errors.Unwrap(err) == nil {
		t.Errorf("%s: unwrapping reached nothing", c.kind)
	}
}

// COVERS: FR-2.11 | property
func TestEveryKindSaysItselfWithTheCallersPath(t *testing.T) {
	t.Parallel()

	// A seam is handed the path and fails without one: a codec never learns
	// which file its bytes came from, and a reader may report the failure with
	// no path at all. The two calls fill it in, so a consumer unwraps once and
	// reads one spelling whichever step failed.
	//
	// Each case drives one kind through a public call, because the filling in
	// happens there and asserting on a constructed error would test the test.
	schema := compileAnything(t)

	for _, c := range kindCases() {
		t.Run(c.kind, func(t *testing.T) {
			t.Parallel()
			assertKindSaysItself(t, c, schema)
		})
	}
}

// COVERS: FR-2.11 | property
func TestAValidationFailureSaysItselfWithThePath(t *testing.T) {
	t.Parallel()

	// Validation is its own kind: the document parsed and is not what the
	// schema describes. It is filled with the path the same way, and the schema
	// error underneath stays reachable.
	reader := &stubReader{data: []byte("success: \"yes\"\n")}
	_, err := wrench.LoadYAMLFile("envelope.yaml", wrench.EnvelopeSchema(), reader)
	if err == nil {
		t.Fatal("an envelope with a string success was accepted")
	}

	var validation *wrench.ValidationError
	if !errors.As(err, &validation) {
		t.Fatalf("got %T, want a ValidationError", err)
	}
	if validation.Step() != wrench.StepValidate {
		t.Errorf("step is %q, want %q", validation.Step(), wrench.StepValidate)
	}
	if !strings.Contains(err.Error(), "validating") ||
		!strings.Contains(err.Error(), "envelope.yaml") {
		t.Errorf("the message does not say the step and the file: %q", err.Error())
	}
	if errors.Unwrap(validation) == nil {
		t.Error("the validator's own report is not reachable underneath")
	}
}

// COVERS: FR-2.11 | property
func TestASchemaFailureKeepsItsOwnNameAndNotTheDocumentsPath(t *testing.T) {
	t.Parallel()

	// A schema that will not compile is a fault in the schema, not in any
	// document, so this kind names the schema it was given and keeps that name
	// when it crosses a call that knows a path. Filling in the document's path
	// would send a reader to the wrong file.
	_, err := wrench.CompileSchema("broken.json", strings.NewReader(`{"type": 42}`))
	if err == nil {
		t.Fatal("a schema with a numeric type compiled")
	}

	var schemaErr *wrench.SchemaError
	if !errors.As(err, &schemaErr) {
		t.Fatalf("got %T, want a SchemaError", err)
	}
	if schemaErr.Step() != wrench.StepSchema {
		t.Errorf("step is %q, want %q", schemaErr.Step(), wrench.StepSchema)
	}
	if !strings.Contains(err.Error(), "compiling") || !strings.Contains(err.Error(), "broken.json") {
		t.Errorf("the message does not say the step and the schema: %q", err.Error())
	}
	if errors.Unwrap(schemaErr) == nil {
		t.Error("the compiler's own report is not reachable underneath")
	}

	// Through a call that has a path of its own, the schema's name survives.
	reader := &stubReader{data: []byte(validEnvelope)}
	_, loadErr := wrench.LoadYAMLFile("document.yaml", failingSchema{cause: err}, reader)
	if loadErr == nil {
		t.Fatal("loading against an uncompilable schema reported success")
	}
	if strings.Contains(loadErr.Error(), "document.yaml") {
		t.Errorf("the schema failure took the document's path: %q", loadErr.Error())
	}
	if !strings.Contains(loadErr.Error(), "broken.json") {
		t.Errorf("the schema failure lost its own name: %q", loadErr.Error())
	}
}

// failingSchema is a schema that refuses with a failure the caller supplies,
// which is how a `schema` kind reaches the two calls: the shipped schemas all
// compile, so nothing public produces one there.
type failingSchema struct{ cause error }

func (s failingSchema) Validate(_ any) error { return s.cause }

// COVERS: FR-2.8 | negative
func TestTheShippedReaderFailsOnWhatItCannotRead(t *testing.T) {
	t.Parallel()

	// A directory opens and cannot be read as a file. The shipped reader hands
	// that back rather than returning empty bytes, which would reach the codec
	// as an empty document and fail as a parse error about the wrong thing.
	_, err := wrench.LocalFile().Read(t.TempDir())
	if err == nil {
		t.Fatal("a directory read back as a file")
	}
}

// COVERS: FR-6.3 | negative
func TestTheShippedWriterFailsWhereItCannotCreateItsTemporary(t *testing.T) {
	t.Parallel()

	// The temporary goes beside the target so the rename stays inside one
	// filesystem. With no directory to put it in there is nothing to rename,
	// and the failure names the path the caller asked for rather than the
	// temporary it never made.
	absent := filepath.Join(t.TempDir(), "no-such-directory", "out.yaml")

	err := wrench.LocalFile().Write(absent, []byte("a: 1\n"))
	if err == nil {
		t.Fatal("a write into a directory that does not exist reported success")
	}
	if !strings.Contains(err.Error(), absent) {
		t.Errorf("the failure does not name the target: %q", err.Error())
	}
	if !errors.Is(err, os.ErrNotExist) {
		t.Errorf("the cause is not reachable: %q", err.Error())
	}
}

// COVERS: FR-6.3 | negative
func TestAWriteThatCannotLandLeavesNoTemporaryBehind(t *testing.T) {
	t.Parallel()

	// A directory in the target's place is the case a test can construct:
	// everything up to the rename succeeds and the rename is refused. What the
	// caller sees afterwards is the directory as it was, with no litter beside
	// it, because a temporary nobody removed is a file the next run reads.
	area := t.TempDir()
	occupied := filepath.Join(area, "occupied.yaml")
	if err := os.Mkdir(occupied, 0o750); err != nil {
		t.Fatalf("making the directory in the way: %v", err)
	}

	err := wrench.LocalFile().Write(occupied, []byte("a: 1\n"))
	if err == nil {
		t.Fatal("a write over a directory reported success")
	}

	entries, readErr := os.ReadDir(area)
	if readErr != nil {
		t.Fatalf("reading the area back: %v", readErr)
	}
	if len(entries) != 1 {
		names := make([]string, 0, len(entries))
		for _, entry := range entries {
			names = append(names, entry.Name())
		}
		t.Errorf("the failed write left %v behind, want the directory alone", names)
	}
}
