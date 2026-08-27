package wrench_test

import (
	"errors"
	"math"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench"
)

// anythingSchema accepts any structure at all, so a test can reach the encode
// path without the schema being what refused it first.
const anythingSchema = `{"$schema": "https://json-schema.org/draft/2020-12/schema"}`

func compileAnything(t *testing.T) wrench.Schema {
	t.Helper()
	schema, err := wrench.CompileSchema("anything.schema.json", strings.NewReader(anythingSchema))
	if err != nil {
		t.Fatalf("compiling: %v", err)
	}
	return schema
}

// COVERS: FR-3.1 | positive
func TestAnyoneCanAttachTheirOwnSchema(t *testing.T) {
	document := `{
	  "$schema": "https://json-schema.org/draft/2020-12/schema",
	  "type": "object",
	  "required": ["ratchet"],
	  "properties": { "ratchet": { "type": "string" } }
	}`

	schema, err := wrench.CompileSchema("ratchet.schema.json", strings.NewReader(document))
	if err != nil {
		t.Fatalf("compiling: %v", err)
	}

	if _, err := wrench.LoadFormattedFile("node.yaml", schema, wrench.YAML, &stubReader{data: []byte("ratchet: node\n")}); err != nil {
		t.Errorf("a conforming file was refused: %v", err)
	}

	_, err = wrench.LoadFormattedFile("node.yaml", schema, wrench.YAML, &stubReader{data: []byte("ratchet: 3\n")})
	var validationErr *wrench.ValidationError
	if !errors.As(err, &validationErr) {
		t.Errorf("got %T (%v), want a ValidationError", err, err)
	}
}

// COVERS: FR-3.1 | negative
func TestAnUnusableSchemaFailsWhenItIsCompiled(t *testing.T) {
	for name, document := range map[string]string{
		"not json":     `{ not json at all`,
		"not a schema": `{"type": 42}`,
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := wrench.CompileSchema("broken.schema.json", strings.NewReader(document)); err == nil {
				t.Error("compiling succeeded, so the failure would have surfaced later and elsewhere")
			}
		})
	}
}

// COVERS: FR-2.2 | negative
func TestACallWithNoCodecOrNoIOIsRefused(t *testing.T) {
	schema := compileAnything(t)

	if _, err := wrench.LoadFormattedFile("f.yaml", schema, nil, &stubReader{}); !errors.Is(err, wrench.ErrNoCodec) {
		t.Errorf("load with no codec gave %v, want ErrNoCodec", err)
	}
	if _, err := wrench.LoadFormattedFile("f.yaml", schema, wrench.YAML, nil); !errors.Is(err, wrench.ErrNoReader) {
		t.Errorf("load with no reader gave %v, want ErrNoReader", err)
	}
	if err := wrench.SaveFormattedFile(nil, "f.yaml", schema, nil, &stubWriter{}); !errors.Is(err, wrench.ErrNoCodec) {
		t.Errorf("save with no codec gave %v, want ErrNoCodec", err)
	}
	if err := wrench.SaveFormattedFile(nil, "f.yaml", schema, wrench.YAML, nil); !errors.Is(err, wrench.ErrNoWriter) {
		t.Errorf("save with no writer gave %v, want ErrNoWriter", err)
	}
}

// COVERS: FR-4.1 | negative
func TestAValueWithNoCanonicalFormIsRefused(t *testing.T) {
	schema := compileAnything(t)
	writer := &stubWriter{}

	// A channel has no YAML spelling. Refusing beats inventing one.
	err := wrench.SaveFormattedFile(map[string]any{"c": make(chan int)}, "f.yaml", schema, wrench.YAML, writer)

	var encodeErr *wrench.EncodeError
	if !errors.As(err, &encodeErr) {
		t.Fatalf("got %T (%v), want an EncodeError", err, err)
	}
	if !strings.Contains(err.Error(), "at key \"c\"") {
		t.Errorf("the error does not say where the trouble was: %v", err)
	}
	if writer.data != nil {
		t.Error("the writer ran despite encoding failing")
	}
}

// COVERS: FR-2.9 | regression
func TestATimestampDecodesToAStringSoItCanBeWrittenBack(t *testing.T) {
	// YAML has a native timestamp type and JSON does not. Before this, an
	// unquoted date decoded to a time.Time, reached the validator, which has no
	// type for it, and then could not be encoded: wrench could read a file it
	// could not write back.
	value, err := wrench.YAML.Decode([]byte("day: 2026-01-01\nstamp: 2026-01-01T07:32:00Z\n"))
	if err != nil {
		t.Fatalf("decoding: %v", err)
	}

	mapping, ok := value.(map[string]any)
	if !ok {
		t.Fatalf("got %T, want a mapping", value)
	}
	for _, name := range []string{"day", "stamp"} {
		if _, isString := mapping[name].(string); !isString {
			t.Errorf("%s decoded to %T, want a string so it is a JSON value", name, mapping[name])
		}
	}

	// The point of the coercion: what was read can be written.
	encoded, err := wrench.YAML.Encode(value)
	if err != nil {
		t.Fatalf("encoding what was just decoded: %v", err)
	}
	again, err := wrench.YAML.Decode(encoded)
	if err != nil {
		t.Fatalf("decoding again: %v", err)
	}
	second, err := wrench.YAML.Encode(again)
	if err != nil {
		t.Fatalf("encoding again: %v", err)
	}
	if string(second) != string(encoded) {
		t.Errorf("not a fixed point:\n%s\n%s", encoded, second)
	}
}

// COVERS: FR-4.1 | edge
func TestNaNAndTheInfinitiesAreRefused(t *testing.T) {
	schema := compileAnything(t)

	for name, value := range map[string]float64{
		"NaN":               math.NaN(),
		"positive infinity": math.Inf(1),
		"negative infinity": math.Inf(-1),
	} {
		t.Run(name, func(t *testing.T) {
			err := wrench.SaveFormattedFile([]any{value}, "f.yaml", schema, wrench.YAML, &stubWriter{})
			var encodeErr *wrench.EncodeError
			if !errors.As(err, &encodeErr) {
				t.Errorf("got %T (%v), want an EncodeError", err, err)
			}
		})
	}
}

// COVERS: FR-1.2 | negative
func TestAMappingKeyThatIsNotAStringIsRefused(t *testing.T) {
	schema := compileAnything(t)

	// A YAML mapping may be keyed by anything. JSON Schema addresses string
	// keys, so a document wrench cannot describe is refused rather than
	// silently coerced into one it can.
	_, err := wrench.LoadFormattedFile("f.yaml", schema, wrench.YAML, &stubReader{data: []byte("1: one\n")})

	var parseErr *wrench.ParseError
	if !errors.As(err, &parseErr) {
		t.Fatalf("got %T (%v), want a ParseError", err, err)
	}
	if !strings.Contains(err.Error(), "not a string") {
		t.Errorf("the error does not say what was wrong: %v", err)
	}
}

// COVERS: FR-4.5 | property
func TestEveryScalarTypeSurvivesTheRoundTrip(t *testing.T) {
	schema := compileAnything(t)
	writer := &stubWriter{}

	value := map[string]any{
		"truth":   true,
		"whole":   7,
		"partial": 2.5,
		"round":   3.0,
		"text":    "no",
		"absent":  nil,
		"list":    []any{1, "two", false},
	}

	if err := wrench.SaveFormattedFile(value, "f.yaml", schema, wrench.YAML, writer); err != nil {
		t.Fatalf("save: %v", err)
	}

	back, err := wrench.YAML.Decode(writer.data)
	if err != nil {
		t.Fatalf("decoding what we wrote: %v", err)
	}

	mapping := back.(map[string]any)
	assertSame(t, "truth", mapping["truth"], true)
	assertSame(t, "whole", mapping["whole"], 7)
	assertSame(t, "partial", mapping["partial"], 2.5)
	assertSame(t, "round", mapping["round"], 3.0)
	assertSame(t, "text", mapping["text"], "no")
	assertSame(t, "absent", mapping["absent"], nil)

	list := mapping["list"].([]any)
	assertSame(t, "list[0]", list[0], 1)
	assertSame(t, "list[1]", list[1], "two")
	assertSame(t, "list[2]", list[2], false)
}

func assertSame(t *testing.T, name string, got, want any) {
	t.Helper()
	if got != want {
		t.Errorf("%s came back as %v (%T), want %v (%T)", name, got, got, want, want)
	}
}
