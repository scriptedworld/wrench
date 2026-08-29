package wrench_test

import (
	"errors"
	"math"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench"
)

// The expected bytes below are asserted identically in all three suites. A table
// that differs between packs is packs that differ, which is the whole argument
// of docs/PATTERNS/holding-two-packs-level.md.

func threeFormats() map[string]any {
	return map[string]any{
		"b": int64(1),
		"a": map[string]any{"z": []any{int64(1), int64(2)}, "y": "x"},
		"d": true,
	}
}

const canonicalJSON = "{\n  \"a\": {\n    \"y\": \"x\",\n    \"z\": [\n      1,\n      2\n    ]\n  },\n  \"b\": 1,\n  \"d\": true\n}\n"

const canonicalTOML = "b = 1\nd = true\n\n[a]\ny = \"x\"\nz = [1, 2]\n"

// COVERS: FR-2.7, FR-4.6 | property
func TestJSONCanonicalForm(t *testing.T) {
	encoded, err := wrench.JSON.Encode(threeFormats())
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	if string(encoded) != canonicalJSON {
		t.Errorf("canonical JSON:\ngot:\n%s\nwant:\n%s", encoded, canonicalJSON)
	}

	// Decoded and re-encoded, because a form nothing reads back is not a form.
	value, err := wrench.JSON.Decode([]byte(canonicalJSON))
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	again, err := wrench.JSON.Encode(value)
	if err != nil {
		t.Fatalf("re-encode: %v", err)
	}
	if string(again) != canonicalJSON {
		t.Errorf("not a fixed point:\n%s", again)
	}
}

// COVERS: FR-2.7, FR-4.7 | property
func TestTOMLCanonicalForm(t *testing.T) {
	encoded, err := wrench.TOML.Encode(threeFormats())
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	if string(encoded) != canonicalTOML {
		t.Errorf("canonical TOML:\ngot:\n%s\nwant:\n%s", encoded, canonicalTOML)
	}

	value, err := wrench.TOML.Decode([]byte(canonicalTOML))
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	again, err := wrench.TOML.Encode(value)
	if err != nil {
		t.Fatalf("re-encode: %v", err)
	}
	if string(again) != canonicalTOML {
		t.Errorf("not a fixed point:\n%s", again)
	}
}

// COVERS: FR-4.7 | edge
func TestTOMLWritesAnArrayOfTablesAsRepeatedSections(t *testing.T) {
	// The most ordinary shape in a hand-written config, and the one TOML has no
	// inline spelling for. Found by the skid session round-tripping a real
	// config while FR-4.7 was still being written: the emitter sent every array
	// down the inline path, so [[x]] had no route at all.
	value := map[string]any{
		"name": "x",
		"substitution": []any{
			map[string]any{"kind": "literal", "pattern": "kokoro"},
			map[string]any{"kind": "regex", "pattern": "skid"},
		},
	}
	want := "name = \"x\"\n\n[[substitution]]\nkind = \"literal\"\npattern = \"kokoro\"\n" +
		"\n[[substitution]]\nkind = \"regex\"\npattern = \"skid\"\n"

	encoded, err := wrench.TOML.Encode(value)
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	if string(encoded) != want {
		t.Errorf("array of tables:\ngot:\n%s\nwant:\n%s", encoded, want)
	}

	// An empty array is not a table array, whatever it would have held.
	empty, err := wrench.TOML.Encode(map[string]any{"a": []any{}})
	if err != nil {
		t.Fatalf("encode empty: %v", err)
	}
	if string(empty) != "a = []\n" {
		t.Errorf("an empty array wrote %q", empty)
	}
}

// COVERS: FR-4.7 | negative
func TestTOMLRefusesANull(t *testing.T) {
	_, err := wrench.TOML.Encode(map[string]any{"a": map[string]any{"b": nil}})
	if err == nil {
		t.Fatal("a null was accepted")
	}
	if !strings.Contains(err.Error(), "a.b") {
		t.Errorf("the error does not say where: %v", err)
	}
}

// COVERS: FR-4.7 | edge
func TestTOMLRefusesADocumentThatIsNotATable(t *testing.T) {
	if _, err := wrench.TOML.Encode([]any{1, 2}); err == nil {
		t.Fatal("a top-level array was accepted")
	}
}

// COVERS: FR-4.7 | regression
func TestTOMLTemporalTypesDecodeToISOStrings(t *testing.T) {
	value, err := wrench.TOML.Decode([]byte("d = 2026-01-01\ndt = 2026-01-01T07:32:00Z\n"))
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	table := value.(map[string]any)
	if table["d"] != "2026-01-01" {
		t.Errorf("a local date became %v, want the date alone", table["d"])
	}
	if got, _ := table["dt"].(string); !strings.HasPrefix(got, "2026-01-01T07:32:00") {
		t.Errorf("an offset datetime became %v", table["dt"])
	}
}

// COVERS: FR-2.10 | positive
func TestAWrapperPerFormatSuppliesTheCodec(t *testing.T) {
	writer := &stubWriter{}
	if err := wrench.SaveJSONFile(map[string]any{"success": true}, "out.json", wrench.EnvelopeSchema, writer); err != nil {
		t.Fatalf("save json: %v", err)
	}
	if string(writer.data) != "{\n  \"success\": true\n}\n" {
		t.Errorf("json wrapper wrote %q", writer.data)
	}

	reader := &stubReader{data: []byte(`{"success": true}`)}
	value, err := wrench.LoadJSONFile("out.json", wrench.EnvelopeSchema, reader)
	if err != nil {
		t.Fatalf("load json: %v", err)
	}
	if value.(map[string]any)["success"] != true {
		t.Errorf("json wrapper read %v", value)
	}

	tomlWriter := &stubWriter{}
	if err := wrench.SaveTOMLFile(map[string]any{"success": true}, "out.toml", wrench.EnvelopeSchema, tomlWriter); err != nil {
		t.Fatalf("save toml: %v", err)
	}
	if string(tomlWriter.data) != "success = true\n" {
		t.Errorf("toml wrapper wrote %q", tomlWriter.data)
	}

	yamlWriter := &stubWriter{}
	if err := wrench.SaveYAMLFile(map[string]any{"success": true}, "out.yaml", wrench.EnvelopeSchema, yamlWriter); err != nil {
		t.Fatalf("save yaml: %v", err)
	}
	if string(yamlWriter.data) != "\"success\": true\n" {
		t.Errorf("yaml wrapper wrote %q", yamlWriter.data)
	}
}

// COVERS: FR-2.10 | negative
func TestAWrapperStillValidates(t *testing.T) {
	writer := &stubWriter{}
	err := wrench.SaveJSONFile(map[string]any{"success": "yes"}, "out.json", wrench.EnvelopeSchema, writer)
	if err == nil {
		t.Fatal("the wrapper accepted a structure the schema refuses")
	}
	if writer.data != nil {
		t.Error("the writer ran despite validation failing")
	}
}

// canonicalFloats is asserted identically in all three suites. A table that
// differs between packs is packs that differ.
func canonicalFloats() []struct {
	value float64
	want  string
} {
	return []struct {
		value float64
		want  string
	}{
		{1000000.0, "1000000.0"},
		{48.0, "48.0"},
		{123456789.0, "123456789.0"},
		{0.1, "0.1"},
		{1e16, "10000000000000000.0"},
		{1e21, "1000000000000000000000.0"},
		{1e-5, "0.00001"},
		{1e-7, "0.0000001"},
		{1.2345678901234567, "1.2345678901234567"},
		{math.Copysign(0, -1), "-0.0"},
	}
}

// COVERS: FR-4.8 | property
func TestAFloatHasOneSpellingInEveryCodec(t *testing.T) {
	codecs := []struct {
		name   string
		codec  wrench.Codec
		prefix string
		suffix string
	}{
		{"yaml", wrench.YAML, "\"n\": ", "\n"},
		{"json", wrench.JSON, "{\n  \"n\": ", "\n}\n"},
		{"toml", wrench.TOML, "n = ", "\n"},
	}

	for _, c := range codecs {
		for _, f := range canonicalFloats() {
			encoded, err := c.codec.Encode(map[string]any{"n": f.value})
			if err != nil {
				t.Fatalf("%s encode %v: %v", c.name, f.value, err)
			}
			want := c.prefix + f.want + c.suffix
			if string(encoded) != want {
				t.Errorf("%s wrote %q, want %q", c.name, encoded, want)
			}
		}
	}
}

// canonicalEscapes is asserted identically in all three suites. A table that
// differs between packs is packs that differ.
func canonicalEscapes() []struct {
	point rune
	yaml  string
	toml  string
} {
	return []struct {
		point rune
		yaml  string
		toml  string
	}{
		{0x00, `\0`, `\u0000`},
		{0x07, `\a`, `\u0007`},
		{0x08, `\b`, `\b`},
		{0x09, `\t`, `\t`},
		{0x0B, `\v`, `\u000B`},
		{0x1B, `\e`, `\u001B`},
		{0x7F, `\x7F`, `\u007F`},
		{0x85, `\N`, "\u0085"},
		{0x9F, `\x9F`, "\u009f"},
		{0x2028, `\L`, "\u2028"},
		{0x2029, `\P`, "\u2029"},
	}
}

// COVERS: FR-4.9 | property
func TestAControlCharacterIsEscapedInEveryCodec(t *testing.T) {
	for _, c := range canonicalEscapes() {
		text := "a" + string(c.point) + "b"
		value := map[string]any{"n": text}

		yamlBytes, err := wrench.YAML.Encode(value)
		if err != nil {
			t.Fatalf("yaml encode U+%04X: %v", c.point, err)
		}
		if want := "\"n\": \"a" + c.yaml + "b\"\n"; string(yamlBytes) != want {
			t.Errorf("yaml U+%04X wrote %q, want %q", c.point, yamlBytes, want)
		}

		tomlBytes, err := wrench.TOML.Encode(value)
		if err != nil {
			t.Fatalf("toml encode U+%04X: %v", c.point, err)
		}
		if want := "n = \"a" + c.toml + "b\"\n"; string(tomlBytes) != want {
			t.Errorf("toml U+%04X wrote %q, want %q", c.point, tomlBytes, want)
		}

		// Reading it back is the half that was broken: two packs wrote files
		// their own parser then refused.
		back, err := wrench.YAML.Decode(yamlBytes)
		if err != nil {
			t.Fatalf("yaml decode U+%04X: %v", c.point, err)
		}
		if got, _ := back.(map[string]any)["n"].(string); got != text {
			t.Errorf("yaml U+%04X read back %q", c.point, got)
		}
	}
}

// COVERS: FR-2.11 | property
func TestEveryFailureIsWrenchsOwnTypeWithItsStep(t *testing.T) {
	// Six kinds on three axes. `schema` against `validate` is the pair most
	// easily lost: a schema that will not compile is not a document that does
	// not match one, and the fix is to a different file.
	good := compileAnything(t)
	strict, err := wrench.CompileSchema("strict.json", strings.NewReader(
		`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","required":["a"]}`))
	if err != nil {
		t.Fatalf("compile: %v", err)
	}

	_, schemaErr := wrench.CompileSchema("bad.json", strings.NewReader(`{"type": 42}`))
	_, parseErr := wrench.YAML.Decode([]byte("a: [1,\n"))
	_, encodeErr := wrench.YAML.Encode(map[string]any{"a": make(chan int)})
	_, readErr := wrench.LoadYAMLFile("f.yaml", good, &stubReader{err: errors.New("nope")})
	writeErr := wrench.SaveYAMLFile(map[string]any{"a": 1}, "f.yaml", good, &stubWriter{err: errors.New("nope")})

	for want, err := range map[string]error{
		"schema":   schemaErr,
		"validate": strict.Validate(map[string]any{}),
		"parse":    parseErr,
		"encode":   encodeErr,
		"read":     readErr,
		"write":    writeErr,
	} {
		if err == nil {
			t.Errorf("%s: no error", want)
			continue
		}
		// The family is one check rather than six, which is what the interface
		// is for.
		var we wrench.Error
		if !errors.As(err, &we) {
			t.Errorf("%s: %T is not a wrench.Error", want, err)
			continue
		}
		if we.Step() != want {
			t.Errorf("step %q, want %q", we.Step(), want)
		}
	}
}
