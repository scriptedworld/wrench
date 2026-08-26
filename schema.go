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

// EnvelopeSchema is the result envelope every producer in the ecosystem writes.
var EnvelopeSchema Schema = shipped(
	"schemas/envelope.schema.json",
	"https://scriptedworld.github.io/wrench/envelope.schema.json",
)

// JigSchema is the jig a runner reads a project's tasks from.
var JigSchema Schema = shipped(
	"schemas/jig.schema.json",
	"https://scriptedworld.github.io/wrench/jig.schema.json",
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
func shipped(file, id string) Schema {
	return &lazySchema{
		load: sync.OnceValues(func() (*jsonschema.Schema, error) {
			data, err := schemaFiles.ReadFile(file)
			if err != nil {
				return nil, fmt.Errorf("wrench: shipped schema %s: %w", file, err)
			}
			return compile(id, bytes.NewReader(data))
		}),
	}
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
