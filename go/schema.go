package wrench

import (
	"errors"
	"fmt"
	"io"
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

// The shipped set are package-level singletons reached through the accessors
// below, and they are unexported for a reason that is not style. An exported
// var is writable by any package that imports this one, so `wrench.JigSchema =
// somethingElse` would change what every other consumer in the same binary
// validates against. Substitution already belongs to the seams, which take a
// schema, a codec and a reader as arguments, so a mutable global buys nothing
// the design does not already offer. The standard library draws the same line:
// os.Stdout is a var because it is meant to be swapped, elliptic.P256() is a
// function because it is not.
//
// Nothing is held at package level, not even unexported. Measured against
// toolbox's config: gochecknoglobals flags every package-level var except one
// named for an error, so an unexported singleton is refused the same way an
// exported one is. The id is a const instead, and it is the const that makes
// the two spellings below impossible to drift: one string, one constructor,
// so JigSchema() and Schemas().Jig cannot come to mean different documents.
//
// Each call returns a fresh Schema that compiles on first use rather than on
// every call, `shipped` deferring the work behind a sync.OnceValues. So a
// caller that holds what it is given pays once, which is what a caller does.
const (
	envelopeSchemaID    = "https://scriptedworld.github.io/wrench/envelope.schema.json"
	jigSchemaID         = "https://scriptedworld.github.io/wrench/jig.schema.json"
	manifestSchemaID    = "https://scriptedworld.github.io/wrench/manifest.schema.json"
	definitionsSchemaID = "https://scriptedworld.github.io/wrench/definitions.schema.json"
)

// EnvelopeSchema is the result envelope every producer in the ecosystem writes.
func EnvelopeSchema() Schema { return shipped(envelopeSchemaID) }

// JigSchema is the jig a runner reads a project's tasks from.
func JigSchema() Schema { return shipped(jigSchemaID) }

// ManifestSchema is what one task execution was going to be given, written
// before its command runs.
func ManifestSchema() Schema { return shipped(manifestSchemaID) }

// DefinitionsSchema is the values a runner substitutes for a jig's
// placeholders, whether they are a jig's own block or a file supplying them.
func DefinitionsSchema() Schema { return shipped(definitionsSchemaID) }

// A SchemaSet is the shipped schemas grouped so the names carry no suffix:
// wrench.Schemas().Jig rather than wrench.JigSchema(), which says schema twice
// and reads worse the more of them there are. Go has no namespace inside a
// package, so a struct is what gives the other packs' wrench.schemas.JIG shape.
//
// A struct and not a map, so a field is checked when the pack is compiled. A
// typo in Jig is a build failure; a typo in a string key is a nil Schema found
// at run time.
type SchemaSet struct {
	Envelope    Schema
	Jig         Schema
	Manifest    Schema
	Definitions Schema
}

// Schemas returns the shipped set grouped under one name.
//
// Each field is built from the same id const its suffixed accessor uses, so the
// two spellings validate against one document and cannot drift the way two
// copies would. The suffixed ones stay while consumers move; only one of them
// is the spelling to write.
func Schemas() SchemaSet {
	return SchemaSet{
		Envelope:    EnvelopeSchema(),
		Jig:         JigSchema(),
		Manifest:    ManifestSchema(),
		Definitions: DefinitionsSchema(),
	}
}

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
		// Already wrench's, from the compiler itself. Passed on rather than
		// wrapped a second time, which would say "compiling <name>" twice.
		var schemaErr *SchemaError
		if errors.As(err, &schemaErr) {
			return nil, err
		}
		return nil, &SchemaError{Name: name, Err: err}
	}
	return &readySchema{compiled: compiled}, nil
}

// localOnly refuses every reference the compiler was not already given.
//
// Without it, a $ref of "file:///tmp/x.schema.json" or of a bare absolute path
// loads that file off disk, so a schema's meaning depends on files outside it
// and a consumer can reference a local copy of a shipped schema instead of the
// shipped one. FR-3.2 forbids that drift.
//
// The message is the same sentence in every pack, because a consumer reading a
// refusal should not be able to tell which language produced it. The packs
// refuse by different mechanisms (this loader, a registry holding only the
// shipped set, a retriever) and each would otherwise word the refusal in its
// own library's vocabulary.
type localOnly struct{}

func (localOnly) Load(url string) (any, error) {
	return nil, &unresolvedRefError{url: url}
}

// An unresolvedRefError is a reference the loader will not follow. It is a type
// rather than a dynamic error so that the sentence FR-3.10d fixes is rendered
// from one place and cannot pick up a prefix.
type unresolvedRefError struct {
	url string
}

func (e *unresolvedRefError) Error() string { return unresolved(e.url) }

// unresolved is the one sentence every pack gives for a reference it will not
// follow. It names the reference as RESOLVED rather than as written, because a
// relative $ref resolves against the document's $id and the two can look
// nothing alike.
func unresolved(url string) string {
	return "cannot resolve " + url +
		": a schema may reference the shipped schemas and its own fragments, and nothing else"
}

// newCompiler returns a compiler with every shipped schema registered by its own
// $id, so a caller's schema may reference one, and with external resolution
// refused unless the environment says otherwise.
func newCompiler() (*jsonschema.Compiler, error) {
	compiler := jsonschema.NewCompiler()
	compiler.UseLoader(localOnly{})

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
	// document decide what the envelope schema means, and fixing that meaning
	// is what a shipped schema is for.
	if _, shipped := shippedIDs()[name]; shipped {
		return nil, &redefinedSchemaError{name: name}
	}

	if err := compiler.AddResource(name, decoded); err != nil {
		return nil, fmt.Errorf("wrench: adding schema %s: %w", name, err)
	}

	// Given wrench's own type here rather than a prefix. CompileSchema renders
	// this inside a SchemaError that already says "compiling <name>", so a
	// prefix would read twice: "wrench: compiling mine.json: wrench: compiling
	// schema mine.json: ...". compileShipped keeps its own, because the lazy
	// path wraps with no name.
	compiled, err := compiler.Compile(name)
	if err != nil {
		return nil, &SchemaError{Name: name, Err: err}
	}
	return compiled, nil
}

// A redefinedSchemaError says a caller tried to register a shipped $id. Fixing
// what a shipped schema means is the whole reason one ships, so a document may
// not decide it.
type redefinedSchemaError struct {
	name string
}

func (e *redefinedSchemaError) Error() string {
	return "wrench: " + e.name + " is a shipped schema and cannot be redefined"
}

// A shippedSchemaError says one of the carried schemas is not usable. It is a
// fault in what the generator wrote, not in anything a caller passed.
type shippedSchemaError struct {
	name   string
	detail string
}

func (e *shippedSchemaError) Error() string {
	return "wrench: shipped schema " + e.name + " " + e.detail
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
// then written once instead of copied, and cannot drift between copies.
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
		return nil, "", &shippedSchemaError{
			name:   entry.Name,
			detail: fmt.Sprintf("is %T, want an object", document),
		}
	}
	declared, ok := mapping["$id"].(string)
	if !ok || declared == "" {
		return nil, "", &shippedSchemaError{name: entry.Name, detail: "declares no $id"}
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
