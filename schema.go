package wrench

import (
	"fmt"
	"io"
	"os"
	"strings"
	"sync"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

// The shipped schemas are carried as source in shipped_gen.go, generated from
// schemas/ by bin/generate-shipped.py, so the pack links one static binary and
// need not sit in the directory the schemas do. //go:embed cannot reach above
// its own package: a ../ pattern is invalid syntax and a symlink is an
// irregular file.
//
// The generated file is a second copy, so the gate task
// `shipped-schemas-are-current` runs the generator with --check.

// EnvelopeSchema is the result envelope every producer in the ecosystem writes.
var EnvelopeSchema Schema = shipped(
	"https://scriptedworld.github.io/wrench/envelope.schema.json",
)

// JigSchema is the jig a runner reads a project's tasks from.
var JigSchema Schema = shipped(
	"https://scriptedworld.github.io/wrench/jig.schema.json",
)

// ManifestSchema is what one task execution was going to be given, written
// before its command runs.
var ManifestSchema Schema = shipped(
	"https://scriptedworld.github.io/wrench/manifest.schema.json",
)

// DefinitionsSchema is the values a runner substitutes for a jig's
// placeholders, whether they are a jig's own block or a file supplying them.
var DefinitionsSchema Schema = shipped(
	"https://scriptedworld.github.io/wrench/definitions.schema.json",
)

// CompileSchema turns a JSON Schema document into a Schema. The shipped pair
// are not special: anything in the ecosystem can attach a schema to its own
// structured files and hand it to the same two calls.
//
// The name identifies the schema in error messages and resolves any relative
// reference inside it.
// CompileSchema turns a JSON Schema document into a Schema.
//
// The JSON parser's and the validator's own error types do not cross this
// boundary. A caller should not have to know which library wrench binds in order
// to catch a schema that will not compile. The cause is kept and reachable
// through errors.Unwrap.
func CompileSchema(name string, document io.Reader) (Schema, error) {
	compiled, err := compile(name, document)
	if err != nil {
		return nil, &SchemaError{Name: name, Err: err}
	}
	return &readySchema{compiled: compiled}, nil
}

// AllowExternalRefs names the environment variable that lets a schema reference
// something outside the shipped set. Unset, which is the ordinary case, a $ref
// resolves only against the shipped schemas and the document's own fragments.
//
// THE UNSAFE BEHAVIOUR IS THE ONE YOU ASK FOR. Set to "1" it restores whatever
// the underlying implementation would do, which includes reading files.
//
// IT IS ON BORROWED TIME AND SHOULD NOT BE BUILT ON. The Python pack's binding
// emits a DeprecationWarning when this is set, saying that automatically
// retrieving remote references is a security vulnerability, is discouraged by
// the JSON Schema specifications, and will shortly become an error. So the
// escape hatch exists to unblock a caller today rather than as a supported mode,
// and it will close whether or not wrench decides to close it.
const AllowExternalRefs = "WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS"

// localOnly refuses every reference the compiler was not already given.
//
// Measured 2026-08-27, before this existed: a $ref of "file:///tmp/x.schema.json"
// or of a bare absolute path loaded that file off disk, so a schema's meaning
// depended on files outside it and a consumer could reference a local copy of a
// shipped schema instead of the shipped one, which is the drift FR-3.2 exists to
// prevent. Nothing was fetched over the network, then or now.
type localOnly struct{}

func (localOnly) Load(url string) (any, error) {
	return nil, fmt.Errorf(
		"refusing to resolve %s: a schema may reference the shipped schemas and its own fragments, "+
			"and nothing else unless %s=1", url, AllowExternalRefs)
}

// newCompiler returns a compiler with every shipped schema registered by its own
// $id, so a caller's schema may reference one, and with external resolution
// refused unless the environment says otherwise.
func newCompiler() (*jsonschema.Compiler, error) {
	compiler := jsonschema.NewCompiler()
	if os.Getenv(AllowExternalRefs) != "1" {
		compiler.UseLoader(localOnly{})
	}

	for _, entry := range shippedSchemas {
		document, declared, err := readShipped(entry)
		if err != nil {
			return nil, err
		}
		if err := compiler.AddResource(declared, document); err != nil {
			return nil, fmt.Errorf("wrench: adding schema %s: %w", entry.Name, err)
		}
	}
	return compiler, nil
}

func compile(name string, document io.Reader) (*jsonschema.Schema, error) {
	decoded, err := jsonschema.UnmarshalJSON(document)
	if err != nil {
		return nil, fmt.Errorf("wrench: reading schema %s: %w", name, err)
	}

	compiler, err := newCompiler()
	if err != nil {
		return nil, err
	}

	// A caller may not redefine a shipped $id. Registering one twice would let a
	// document decide what the envelope schema means, which is the one thing a
	// shipped schema exists to fix.
	if _, shipped := shippedIDs()[name]; shipped {
		return nil, fmt.Errorf("wrench: %s is a shipped schema and cannot be redefined", name)
	}

	if err := compiler.AddResource(name, decoded); err != nil {
		return nil, fmt.Errorf("wrench: adding schema %s: %w", name, err)
	}

	compiled, err := compiler.Compile(name)
	if err != nil {
		return nil, fmt.Errorf("wrench: compiling schema %s: %w", name, err)
	}
	return compiled, nil
}

// shippedIDs is the set of $ids the shipped schemas declare, read from what the
// pack actually carries so it cannot drift from what ships.
func shippedIDs() map[string]bool {
	ids := make(map[string]bool)
	for _, entry := range shippedSchemas {
		if _, declared, err := readShipped(entry); err == nil {
			ids[declared] = true
		}
	}
	return ids
}

// shipped defers compiling until something validates against it, so importing
// wrench costs nothing and a broken embedded schema surfaces as an error from
// the call that needed it rather than as a panic at process start.
//
// The id, not the filename, is what a schema is called in an error. A relative
// filename resolves against whatever directory the process happened to start
// in, which puts a local absolute path into a message that travels as evidence.
func shipped(id string) Schema {
	return &lazySchema{
		load: sync.OnceValues(func() (*jsonschema.Schema, error) { return compileShipped(id) }),
	}
}

// compileShipped registers every shipped schema before compiling the one asked
// for, so one may reference another by its $id. A shape two files both need is
// then written once instead of copied, which is the drift a shipped schema
// exists to prevent.
func compileShipped(id string) (*jsonschema.Schema, error) {
	compiler, err := newCompiler()
	if err != nil {
		return nil, err
	}

	compiled, err := compiler.Compile(id)
	if err != nil {
		return nil, fmt.Errorf("wrench: compiling schema %s: %w", id, err)
	}
	return compiled, nil
}

// readShipped decodes one carried schema and returns it with its own $id, which
// is what every other schema references it by.
func readShipped(entry shippedSchema) (any, string, error) {
	document, err := jsonschema.UnmarshalJSON(strings.NewReader(entry.Text))
	if err != nil {
		return nil, "", fmt.Errorf("wrench: reading schema %s: %w", entry.Name, err)
	}

	mapping, ok := document.(map[string]any)
	if !ok {
		return nil, "", fmt.Errorf("wrench: shipped schema %s is %T, want an object", entry.Name, document)
	}
	declared, ok := mapping["$id"].(string)
	if !ok || declared == "" {
		return nil, "", fmt.Errorf("wrench: shipped schema %s declares no $id", entry.Name)
	}
	return document, declared, nil
}

type lazySchema struct {
	load func() (*jsonschema.Schema, error)
}

func (s *lazySchema) Validate(value any) error {
	compiled, err := s.load()
	if err != nil {
		return &SchemaError{Err: err}
	}
	if err := compiled.Validate(value); err != nil {
		// ValidationError with no path: Validate is handed a structure and does
		// not know which file it came from. The two calls fill the path in with
		// atPath rather than wrapping a second time.
		return &ValidationError{Err: err}
	}
	return nil
}

type readySchema struct {
	compiled *jsonschema.Schema
}

func (s *readySchema) Validate(value any) error {
	if err := s.compiled.Validate(value); err != nil {
		// The validator's own type does not cross this boundary. FR-2.11.
		return &ValidationError{Err: err}
	}
	return nil
}
