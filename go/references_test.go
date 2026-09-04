package wrench_test

import (
	"encoding/json"
	"strings"
	"testing"

	wrench "github.com/scriptedworld/wrench/go"
)

// The three cases below are the same cases the Python and Rust suites run, and
// the packs were measured against each other on 2026-09-03 before any of them
// were written. A divergence here is a divergence in the contract.

const permissiveSchema = `{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object"}`

// compiles a schema and validates one instance, returning what happened rather
// than failing, so a table can state its own expectation.
func outcome(t *testing.T, name, schemaBody, instanceJSON string) (string, string) {
	t.Helper()

	schema, err := wrench.CompileSchema(name, strings.NewReader(schemaBody))
	if err != nil {
		return "schema", err.Error()
	}
	var instance any
	if err := json.Unmarshal([]byte(instanceJSON), &instance); err != nil {
		t.Fatalf("the instance is not JSON: %v", err)
	}
	if err := schema.Validate(instance); err != nil {
		return "validate", err.Error()
	}
	return "accepted", ""
}

// COVERS: FR-3.10c | negative
func TestAKeywordInAnInstanceIsData(t *testing.T) {
	// The schema keywords are ordinary keys in a document being validated, and
	// a data file is allowed to carry them. The file this points at EXISTS, so
	// an implementation that resolved it would be caught here rather than
	// passing for want of a target.
	seedReachableSchema(t)

	for what, instance := range map[string]string{
		"a $ref at a file that exists": `{"$ref":"file://` + reachablePath + `"}`,
		"a $ref at an http url":        `{"$ref":"http://example.invalid/x.schema.json"}`,
		"an $id":                       `{"$id":"https://example.invalid/other"}`,
		"a $schema":                    `{"$schema":"https://json-schema.org/draft/2020-12/schema"}`,
		"a document that is a schema": `{"$schema":"https://json-schema.org/draft/2020-12/schema",` +
			`"$id":"https://example.invalid/embedded","$ref":"file://` + reachablePath + `"}`,
	} {
		got, detail := outcome(t, "https://example.invalid/s.schema.json", permissiveSchema, instance)
		if got != "accepted" {
			t.Errorf("%s in an instance was interpreted rather than carried: %s: %s", what, got, detail)
		}
	}
}

// COVERS: FR-3.10a | positive
func TestAReferenceWithinTheDocumentResolves(t *testing.T) {
	// Both spellings of an internal reference, and each is asserted by its
	// VIOLATION: an accepted document says nothing, because a $ref that
	// silently contributed no constraint would accept it too.
	for what, body := range map[string]string{
		"a pointer into $defs": `{"$schema":"https://json-schema.org/draft/2020-12/schema",` +
			`"$defs":{"tight":{"type":"string","minLength":3}},` +
			`"type":"object","properties":{"a":{"$ref":"#/$defs/tight"}}}`,
		"an $anchor": `{"$schema":"https://json-schema.org/draft/2020-12/schema",` +
			`"$defs":{"t":{"$anchor":"tight","type":"string","minLength":3}},` +
			`"type":"object","properties":{"a":{"$ref":"#tight"}}}`,
	} {
		if got, detail := outcome(t, "https://example.invalid/s.schema.json", body, `{"a":"abc"}`); got != "accepted" {
			t.Errorf("%s refused a document it should take: %s: %s", what, got, detail)
		}
		if got, _ := outcome(t, "https://example.invalid/s.schema.json", body, `{"a":"x"}`); got != "validate" {
			t.Errorf("%s did not constrain, so the reference resolved to nothing: got %s", what, got)
		}
	}
}

// COVERS: FR-3.10b, FR-3.10d | negative
func TestARefusalNamesTheResolvedReference(t *testing.T) {
	// A relative reference resolves against the document's $id, so the text and
	// the reference are different strings. Naming the text would send a reader
	// looking for something that is not what failed.
	//
	// This also pins that the $id wins over the compile name: the name here is
	// a bare filename, and were IT the base the reference would resolve to a
	// path rather than to elsewhere.invalid.
	body := `{"$schema":"https://json-schema.org/draft/2020-12/schema",` +
		`"$id":"https://elsewhere.invalid/root.schema.json","$ref":"sibling.schema.json"}`

	got, detail := outcome(t, "mine.schema.json", body, `{"anything":1}`)
	if got != "schema" {
		t.Fatalf("a reference outside the shipped set resolved: %s", got)
	}
	if !strings.Contains(detail, "https://elsewhere.invalid/sibling.schema.json") {
		t.Errorf("the refusal does not name the resolved reference: %s", detail)
	}
	if !strings.Contains(detail, wrenchRefusal) {
		t.Errorf("the refusal is not the shared sentence: %s", detail)
	}
}

// COVERS: FR-3.10d | negative
func TestEveryRefusedFormGivesTheSameSentence(t *testing.T) {
	// One sentence for every shape a reference can take, so a consumer matching
	// on the failure does not need a list of the ways it can be spelled.
	seedReachableSchema(t)

	for what, ref := range map[string]string{
		"an http url":         "http://example.invalid/x.schema.json",
		"an https url":        "https://example.invalid/x.schema.json",
		"a file url":          "file://" + reachablePath,
		"an absolute path":    reachablePath,
		"a relative path":     "sibling.schema.json",
		"an unshipped wrench": "https://scriptedworld.github.io/wrench/not-shipped.schema.json",
	} {
		body := `{"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"` + ref + `"}`
		got, detail := outcome(t, "https://example.invalid/s.schema.json", body, `{"anything":1}`)
		if got != "schema" {
			t.Errorf("%s resolved rather than being refused: %s", what, got)
			continue
		}
		if !strings.Contains(detail, wrenchRefusal) {
			t.Errorf("%s was refused in different words: %s", what, detail)
		}
	}
}

// COVERS: FR-3.10 | negative
func TestNoEnvironmentVariableOpensAReference(t *testing.T) {
	// WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS was documented before it was retired on
	// 2026-09-03, so somebody may still set it. It meant three different things
	// while it existed: Python fetched over HTTP and read files, Go read files,
	// and Rust did nothing at all.
	seedReachableSchema(t)
	body := `{"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"file://` + reachablePath + `"}`

	// A subtest each, because t.Setenv restores at the end of the test rather
	// than at the end of an iteration: setting three names in one loop leaves
	// all three set, and the second and third would report a failure the first
	// one caused. Seen while proving these fail for the right reason.
	for _, name := range []string{
		"WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS",
		"WRENCH_ALLOW_LOCAL_SCHEMA_REFS",
		"WRENCH_ALLOW_NET_SCHEMA_REFS",
	} {
		t.Run(name, func(t *testing.T) {
			t.Setenv(name, "1")
			if got, _ := outcome(t, "https://example.invalid/s.schema.json", body, `{"anything":1}`); got != "schema" {
				t.Errorf("%s=1 opened a reference", name)
			}
		})
	}
}
