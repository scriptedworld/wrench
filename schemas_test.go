package wrench_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench"
)

// COVERS: FR-1.1, FR-3.2, FR-3.5 | positive
func TestTheSchemasShipAsFilesBesideTheLibrary(t *testing.T) {
	// Embedded is how a consumer links one static binary. Present as files is
	// what lets a YAML language server be pointed at them while a jig is being
	// written, and it is what keeps one copy rather than one per pack.
	for _, name := range []string{"envelope.schema.json", "jig.schema.json", "manifest.schema.json", "definitions.schema.json"} {
		path := filepath.Join("schemas", name)
		data, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("%s is not present as a file: %v", path, err)
			continue
		}
		if !strings.Contains(string(data), `"$schema"`) {
			t.Errorf("%s does not declare which JSON Schema dialect it is", path)
		}
	}
}

// COVERS: FR-5.2 | property
func TestValidationIsARealJSONSchemaImplementation(t *testing.T) {
	// $ref resolution, $defs and conditional application are the parts a
	// hand-written checker never gets right. Binding to an established
	// implementation means they work, and this is what that buys.
	document := `{
	  "$schema": "https://json-schema.org/draft/2020-12/schema",
	  "type": "object",
	  "properties": { "items": { "type": "array", "items": { "$ref": "#/$defs/entry" } } },
	  "$defs": { "entry": { "type": "object", "required": ["id"], "properties": { "id": { "type": "integer" } } } }
	}`

	schema, err := wrench.CompileSchema("refs.schema.json", strings.NewReader(document))
	if err != nil {
		t.Fatalf("compiling: %v", err)
	}

	if err := schema.Validate(map[string]any{"items": []any{map[string]any{"id": 1}}}); err != nil {
		t.Errorf("a conforming structure was refused: %v", err)
	}

	err = schema.Validate(map[string]any{"items": []any{map[string]any{"id": "one"}}})
	if err == nil {
		t.Error("a $ref'd constraint was not applied, so the reference did not resolve")
	}
}

// COVERS: FR-3.1 | edge
func TestTheEnvelopeSchemaRequiresReasonsOnlyWhenItFailed(t *testing.T) {
	// The conditional is the part of the envelope schema most likely to be
	// wrong, because it is the only rule that reads one key to decide another.
	passing := "success: true\n"
	if _, err := wrench.LoadFormattedFile("f.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte(passing)}); err != nil {
		t.Errorf("a passing envelope with no reasons was refused: %v", err)
	}

	failingWithout := "success: false\n"
	if _, err := wrench.LoadFormattedFile("f.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte(failingWithout)}); err == nil {
		t.Error("a failing envelope with no reasons was accepted, so a failure need not say why")
	}
}

// COVERS: FR-3.2 | regression
func TestAValidationErrorNamesTheSchemaByIdNotByLocalPath(t *testing.T) {
	// The identifier lands in the error, the error lands in a reason, and a
	// reason travels as evidence. Naming a shipped schema by a relative
	// filename resolved it against whatever directory the process started in,
	// which put an absolute local path in front of every consumer.
	invalid := []byte("success: \"yes\"\n")
	_, err := wrench.LoadFormattedFile("f.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: invalid})
	if err == nil {
		t.Fatal("an invalid envelope was accepted")
	}

	message := err.Error()
	if !strings.Contains(message, "scriptedworld.github.io/wrench/envelope.schema.json") {
		t.Errorf("the error does not name the schema by its id: %v", message)
	}
	if strings.Contains(message, "file:///") {
		t.Errorf("the error carries a local filesystem path: %v", message)
	}
	if home := os.Getenv("HOME"); home != "" && strings.Contains(message, home) {
		t.Errorf("the error carries the running user's home directory: %v", message)
	}
}

// COVERS: FR-3.1, FR-3.3 | positive
func TestAJigsDefinitionsBlockIsHeldToTheSharedShape(t *testing.T) {
	// The block and the file are one shape, written once and referenced across
	// two shipped schemas. A jig carrying a nested value has to be refused by a
	// rule the jig schema does not itself state, which is what proves the
	// reference between them resolved.
	flat := "definitions:\n  requirements: REQUIREMENTS.md\n  line_length: 100\ntasks:\n  - name: check\n    command: \"true\"\n"
	if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(flat)}); err != nil {
		t.Errorf("a jig with a flat definitions block was refused: %v", err)
	}

	nested := "definitions:\n  python:\n    line_length: 100\ntasks:\n  - name: check\n    command: \"true\"\n"
	if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(nested)}); err == nil {
		t.Error("a nested definitions value was accepted, so the shared shape did not apply")
	}
}

// COVERS: FR-3.2, FR-3.3 | negative
func TestADefinitionsFileTakesOneLevelOfScalars(t *testing.T) {
	scalars := "requirements: ../REQUIREMENTS.md\nline_length: 100\nstrict: true\nempty: \"\"\n"
	if _, err := wrench.LoadFormattedFile("d.yaml", wrench.DefinitionsSchema, wrench.YAML, &stubReader{data: []byte(scalars)}); err != nil {
		t.Errorf("a file of scalars was refused: %v", err)
	}

	refused := map[string]string{
		"a list value":         "tags:\n  - one\n  - two\n",
		"a nested value":       "python:\n  line_length: 100\n",
		"a hyphenated name":    "line-length: 100\n",
		"a name with a brace":  "\"{line_length}\": 100\n",
		"a leading underscore": "_leading: 1\n",
	}
	for what, document := range refused {
		if _, err := wrench.LoadFormattedFile("d.yaml", wrench.DefinitionsSchema, wrench.YAML, &stubReader{data: []byte(document)}); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}
