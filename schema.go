package wrench

import (
	"bytes"
	"embed"
	"fmt"
	"io"
	"sync"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

// schemaFiles holds the shipped schemas. They are embedded so a consumer links
// one static binary and still names a schema rather than carrying a copy that
// can drift. The files stay in the tree as files, so a YAML language server can
// be pointed at them while a jig is being written.
//
//go:embed schemas/*.schema.json
var schemaFiles embed.FS

// schemaDir is where the shipped schemas sit, both embedded and in the tree.
const schemaDir = "schemas"

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
func CompileSchema(name string, document io.Reader) (Schema, error) {
	compiled, err := compile(name, document)
	if err != nil {
		return nil, err
	}
	return &readySchema{compiled: compiled}, nil
}

func compile(name string, document io.Reader) (*jsonschema.Schema, error) {
	decoded, err := jsonschema.UnmarshalJSON(document)
	if err != nil {
		return nil, fmt.Errorf("wrench: reading schema %s: %w", name, err)
	}

	compiler := jsonschema.NewCompiler()
	if err := compiler.AddResource(name, decoded); err != nil {
		return nil, fmt.Errorf("wrench: adding schema %s: %w", name, err)
	}

	compiled, err := compiler.Compile(name)
	if err != nil {
		return nil, fmt.Errorf("wrench: compiling schema %s: %w", name, err)
	}
	return compiled, nil
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
	compiler := jsonschema.NewCompiler()

	entries, err := schemaFiles.ReadDir(schemaDir)
	if err != nil {
		return nil, fmt.Errorf("wrench: shipped schemas: %w", err)
	}
	for _, entry := range entries {
		file := schemaDir + "/" + entry.Name()
		document, declared, err := readShipped(file)
		if err != nil {
			return nil, err
		}
		if err := compiler.AddResource(declared, document); err != nil {
			return nil, fmt.Errorf("wrench: adding schema %s: %w", file, err)
		}
	}

	compiled, err := compiler.Compile(id)
	if err != nil {
		return nil, fmt.Errorf("wrench: compiling schema %s: %w", id, err)
	}
	return compiled, nil
}

// readShipped decodes one embedded schema and returns it with its own $id,
// which is what every other schema references it by.
func readShipped(file string) (any, string, error) {
	data, err := schemaFiles.ReadFile(file)
	if err != nil {
		return nil, "", fmt.Errorf("wrench: shipped schema %s: %w", file, err)
	}
	document, err := jsonschema.UnmarshalJSON(bytes.NewReader(data))
	if err != nil {
		return nil, "", fmt.Errorf("wrench: reading schema %s: %w", file, err)
	}

	mapping, ok := document.(map[string]any)
	if !ok {
		return nil, "", fmt.Errorf("wrench: shipped schema %s is %T, want an object", file, document)
	}
	declared, ok := mapping["$id"].(string)
	if !ok || declared == "" {
		return nil, "", fmt.Errorf("wrench: shipped schema %s declares no $id", file)
	}
	return document, declared, nil
}

type lazySchema struct {
	load func() (*jsonschema.Schema, error)
}

func (s *lazySchema) Validate(value any) error {
	compiled, err := s.load()
	if err != nil {
		return err
	}
	return compiled.Validate(value)
}

type readySchema struct {
	compiled *jsonschema.Schema
}

func (s *readySchema) Validate(value any) error {
	return s.compiled.Validate(value)
}
