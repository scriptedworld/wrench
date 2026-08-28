package wrench_test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench"
)

// exported is every shipped schema this pack offers by name, keyed by the $id it
// is named by. Go cannot enumerate its own package variables, so this list is
// the thing that has to be kept in step with schemas/, and
// TestEveryShippedSchemaIsExported is what keeps it.
var exported = map[string]wrench.Schema{
	"https://scriptedworld.github.io/wrench/envelope.schema.json":    wrench.EnvelopeSchema,
	"https://scriptedworld.github.io/wrench/jig.schema.json":         wrench.JigSchema,
	"https://scriptedworld.github.io/wrench/manifest.schema.json":    wrench.ManifestSchema,
	"https://scriptedworld.github.io/wrench/definitions.schema.json": wrench.DefinitionsSchema,
}

// mustSchemaFiles lists the shipped schema filenames, failing rather than
// returning an empty set that would make a caller assert nothing.
func mustSchemaFiles(t *testing.T) []string {
	t.Helper()

	entries, err := os.ReadDir("schemas")
	if err != nil {
		t.Fatalf("schemas/ is not readable: %v", err)
	}
	var names []string
	for _, entry := range entries {
		if strings.HasSuffix(entry.Name(), ".schema.json") {
			names = append(names, entry.Name())
		}
	}
	if len(names) == 0 {
		t.Fatal("schemas/ holds no schemas")
	}
	return names
}

// mustDecodeSchema reads one shipped schema as a plain document.
func mustDecodeSchema(t *testing.T, name string) map[string]any {
	t.Helper()

	data, err := os.ReadFile(filepath.Join("schemas", name))
	if err != nil {
		t.Fatalf("%s is not readable: %v", name, err)
	}
	var document map[string]any
	if err := json.Unmarshal(data, &document); err != nil {
		t.Fatalf("%s is not JSON: %v", name, err)
	}
	return document
}

// declaredIDs reads schemas/ and returns the $id each file declares. The
// directory is the authority on what ships, not any list in Go or in Python.
func declaredIDs(t *testing.T) map[string]string {
	t.Helper()

	entries, err := os.ReadDir("schemas")
	if err != nil {
		t.Fatalf("schemas/ is not readable: %v", err)
	}

	ids := make(map[string]string)
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".schema.json") {
			continue
		}
		data, err := os.ReadFile(filepath.Join("schemas", entry.Name()))
		if err != nil {
			t.Fatalf("%s is not readable: %v", entry.Name(), err)
		}
		var document struct {
			ID string `json:"$id"`
		}
		if err := json.Unmarshal(data, &document); err != nil {
			t.Fatalf("%s is not JSON: %v", entry.Name(), err)
		}
		if document.ID == "" {
			t.Errorf("%s declares no $id, so nothing can reference it", entry.Name())
			continue
		}
		ids[document.ID] = entry.Name()
	}
	return ids
}

// COVERS: FR-3.7, FR-5.7 | regression
func TestEveryShippedSchemaIsExported(t *testing.T) {
	// A schema added to schemas/ and picked up by one pack but not the other is
	// a divergence in the contract that nothing reports. It has happened: a
	// fourth schema shipped, Go exported it, Python named three filenames in its
	// source and did not. Each pack asserts against the directory, so both
	// agreeing with the directory is what makes them agree with each other.
	declared := declaredIDs(t)

	for id, file := range declared {
		schema, ok := exported[id]
		if !ok {
			t.Errorf("%s declares %s and this pack exports no schema for it", file, id)
			continue
		}
		if schema == nil {
			t.Errorf("%s is exported as nil", id)
		}
	}

	for id := range exported {
		if _, ok := declared[id]; !ok {
			t.Errorf("this pack exports %s and no file in schemas/ declares it", id)
		}
	}
}

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

// COVERS: FR-3.1, FR-3.3, FR-3.6 | positive
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

// COVERS: FR-3.1, FR-3.4 | edge
func TestAJigMayDeclareItStandsAtTheRepositoryRoot(t *testing.T) {
	// The field reaches the working directory and nothing else. The walk, the
	// containment, the filter patterns and {base_dir} stay what the caller
	// granted, which is why it is a boolean on the jig rather than a base a jig
	// task can be talked into widening.
	tasks := "tasks:\n  - name: check\n    command: \"true\"\n"

	for _, declared := range []string{"needs-repository-root: true\n", "needs-repository-root: false\n", ""} {
		document := declared + tasks
		if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(document)}); err != nil {
			t.Errorf("a jig declaring %q was refused: %v", declared, err)
		}
	}

	refused := map[string]string{
		"a string":     "needs-repository-root: \"true\"\n",
		"a number":     "needs-repository-root: 1\n",
		"an empty key": "needs-repository-root:\n",
	}
	for what, declared := range refused {
		if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(declared + tasks)}); err == nil {
			t.Errorf("%s was accepted as needs-repository-root", what)
		}
	}

	// It is the jig's, not a jig task's. A tool needing the root needs it
	// wherever it is placed, so a caller cannot grant it per placement.
	onTask := "tasks:\n  - name: child\n    jig: other\n    needs-repository-root: true\n"
	if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(onTask)}); err == nil {
		t.Error("a jig task carrying needs-repository-root was accepted")
	}
}

// versioned names the shipped schemas that carry a top-level version, with a
// document each that is otherwise valid. definitions is absent on purpose: it is
// an open mapping where every key is a placeholder name, so reserving one costs
// something the other three do not pay.
var versioned = map[string]struct {
	schema wrench.Schema
	rest   string
}{
	"envelope": {wrench.EnvelopeSchema, "success: true\n"},
	"jig":      {wrench.JigSchema, "tasks:\n  - name: check\n    command: \"true\"\n"},
	"manifest": {wrench.ManifestSchema, manifestWith("")},
}

// COVERS: FR-3.9 | edge
func TestAFormatMayDeclareTheVersionItConformsTo(t *testing.T) {
	// Optional, because every document written before the field existed carries
	// none and claiming nothing is the honest reading of that. Present, it is
	// semver, so a consumer can refuse a major rather than failing later on a
	// field it cannot find.
	accepted := []string{"1.0.0", "0.1.0", "10.20.30", "1.0.0-alpha.1", "1.0.0+build.5", "1.0.0-rc.1+build.5"}
	refused := []string{"1", "1.0", "v1.0.0", "1.0.0.0", "01.0.0", "", "latest", "1.0.0-"}

	for name, format := range versioned {
		t.Run(name, func(t *testing.T) {
			// Absent is valid, which is what makes the field additive.
			if _, err := wrench.LoadFormattedFile("f.yaml", format.schema, wrench.YAML, &stubReader{data: []byte(format.rest)}); err != nil {
				t.Errorf("a document with no version was refused: %v", err)
			}

			for _, version := range accepted {
				document := "version: \"" + version + "\"\n" + format.rest
				if _, err := wrench.LoadFormattedFile("f.yaml", format.schema, wrench.YAML, &stubReader{data: []byte(document)}); err != nil {
					t.Errorf("version %q was refused: %v", version, err)
				}
			}

			for _, version := range refused {
				document := "version: \"" + version + "\"\n" + format.rest
				if _, err := wrench.LoadFormattedFile("f.yaml", format.schema, wrench.YAML, &stubReader{data: []byte(document)}); err == nil {
					t.Errorf("version %q was accepted and is not semver", version)
				}
			}

			// A bare number is the mistake this pattern exists to catch: YAML
			// reads 1.0 as a float, and a float is not a version.
			bare := "version: 1.0\n" + format.rest
			if _, err := wrench.LoadFormattedFile("f.yaml", format.schema, wrench.YAML, &stubReader{data: []byte(bare)}); err == nil {
				t.Error("an unquoted 1.0 was accepted, so it was read as a float and passed as a version")
			}
		})
	}
}

// COVERS: FR-3.9 | property
func TestTheVersionFieldIsTheSameInEveryFormatThatCarriesIt(t *testing.T) {
	// Written into each schema rather than referenced, because it constrains a
	// scalar rather than describing a shape, and a shipped schema exists to be
	// an instance of something. Repetition is the cost, so drift is what this
	// checks.
	var first map[string]any
	var firstName string

	for _, entry := range mustSchemaFiles(t) {
		document := mustDecodeSchema(t, entry)
		properties, ok := document["properties"].(map[string]any)
		if !ok {
			continue
		}
		version, ok := properties["version"].(map[string]any)
		if !ok {
			continue
		}
		if first == nil {
			first, firstName = version, entry
			continue
		}
		if fmt.Sprint(version) != fmt.Sprint(first) {
			t.Errorf("the version field in %s differs from the one in %s", entry, firstName)
		}
	}
	if first == nil {
		t.Fatal("no shipped schema declares a version field, so this test asserts nothing")
	}
}

// consumerSchema is a caller's own schema whose one property references the
// target, which is what an adapter extending a shipped schema would write.
func consumerSchema(target string) string {
	return `{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",` +
		`"properties":{"d":{"$ref":"` + target + `"}}}`
}

// COVERS: FR-3.10 | positive
func TestAConsumerSchemaMayReferenceAShippedOne(t *testing.T) {
	// The case a consumer most wants: an adapter extending the envelope schema
	// references it rather than copying it, and a copy is the drift FR-3.2
	// exists to prevent.
	schema, err := wrench.CompileSchema("mine.schema.json",
		strings.NewReader(consumerSchema("https://scriptedworld.github.io/wrench/definitions.schema.json")))
	if err != nil {
		t.Fatalf("compiling a schema that references a shipped one: %v", err)
	}

	if err := schema.Validate(map[string]any{"d": map[string]any{"a": "x"}}); err != nil {
		t.Errorf("a flat definitions mapping was refused: %v", err)
	}

	// A nested value is refused by a rule only the referenced schema states, so
	// a refusal here is what proves the reference resolved rather than being
	// skipped.
	if err := schema.Validate(map[string]any{"d": map[string]any{"a": map[string]any{"b": 1}}}); err == nil {
		t.Error("a nested value was accepted, so the reference did not resolve")
	}
}

// COVERS: FR-3.10 | negative
func TestASchemaMayReferenceNothingOutsideTheShippedSet(t *testing.T) {
	// Measured before this existed: file:// and a bare absolute path both loaded
	// that file off disk, so a schema's meaning depended on files outside it.
	// Nothing was ever fetched over the network.
	local := filepath.Join(t.TempDir(), "local.schema.json")
	if err := os.WriteFile(local, []byte(`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}`), 0o644); err != nil {
		t.Fatalf("seeding: %v", err)
	}

	for what, target := range map[string]string{
		"a file url":          "file://" + local,
		"an absolute path":    local,
		"a relative path":     "local.schema.json",
		"an http url":         "http://example.com/x.schema.json",
		"an https url":        "https://example.com/x.schema.json",
		"an unshipped wrench": "https://scriptedworld.github.io/wrench/not-shipped.schema.json",
	} {
		_, err := wrench.CompileSchema("mine.schema.json", strings.NewReader(consumerSchema(target)))
		if err == nil {
			t.Errorf("%s (%s) resolved, so validation depends on something outside the process", what, target)
		}
	}
}

// COVERS: FR-3.10 | edge
func TestTheEnvironmentCanRestoreExternalReferences(t *testing.T) {
	// An escape hatch nobody exercises is one that may not work. This asserts
	// the hatch opens, not that opening it is a good idea.
	local := filepath.Join(t.TempDir(), "local.schema.json")
	if err := os.WriteFile(local, []byte(`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}`), 0o644); err != nil {
		t.Fatalf("seeding: %v", err)
	}
	document := consumerSchema("file://" + local)

	if _, err := wrench.CompileSchema("mine.schema.json", strings.NewReader(document)); err == nil {
		t.Fatal("a file reference resolved with the variable unset")
	}

	t.Setenv(wrench.AllowExternalRefs, "1")
	if _, err := wrench.CompileSchema("mine.schema.json", strings.NewReader(document)); err != nil {
		t.Errorf("%s=1 did not restore external references: %v", wrench.AllowExternalRefs, err)
	}
}

// COVERS: FR-3.10 | edge
func TestACallerCannotRedefineAShippedSchema(t *testing.T) {
	// Registering a shipped id twice would let a document decide what the
	// envelope schema means, which is the one thing a shipped schema fixes.
	for id := range exported {
		_, err := wrench.CompileSchema(id, strings.NewReader(
			`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}`))
		if err == nil {
			t.Errorf("%s was redefined by a caller", id)
		}
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

// manifestWith builds a manifest carrying the five locations every execution
// has, plus whatever the case under test adds. Written as YAML because that is
// what a manifest is on disk, and validating the decoded structure is what the
// schema is for.
func manifestWith(variables string) string {
	return "task: build\n" +
		"ordinal: 0\n" +
		"command: go build ./...\n" +
		"variables:\n" +
		"  project_root:\n    value: /p\n    from: bolt\n" +
		"  base_dir:\n    value: /p\n    from: bolt\n" +
		"  work_dir:\n    value: /p/w\n    from: bolt\n" +
		"  config_dir:\n    value: /p\n    from: bolt\n" +
		"  output_dir:\n    value: /p/o\n    from: bolt\n" +
		variables
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestAManifestVariableSaysWhichLayerSuppliedIt(t *testing.T) {
	// Nothing in Go exercised this schema until a change to it broke the Python
	// pack alone. A shipped schema no pack validates against is a shape the
	// gate cannot hold either pack to.
	accepted := manifestWith(
		"  requirements:\n    value: ../REQUIREMENTS.md\n    from: file\n" +
			"  all_paths:\n    value:\n      - a.go\n      - b.go\n    from: bolt\n")
	if _, err := wrench.LoadFormattedFile("m.yaml", wrench.ManifestSchema, wrench.YAML, &stubReader{data: []byte(accepted)}); err != nil {
		t.Errorf("a manifest naming the layer of each variable was refused: %v", err)
	}

	refused := map[string]string{
		"a bare value":              "  requirements: ../REQUIREMENTS.md\n",
		"a value with no layer":     "  requirements:\n    value: x\n",
		"a layer with no value":     "  requirements:\n    from: jig\n",
		"a layer outside the three": "  requirements:\n    value: x\n    from: environment\n",
	}
	for what, variable := range refused {
		if _, err := wrench.LoadFormattedFile("m.yaml", wrench.ManifestSchema, wrench.YAML, &stubReader{data: []byte(manifestWith(variable))}); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}

// COVERS: FR-3.1 | negative
func TestAManifestKeepsTheFiveLocations(t *testing.T) {
	// Every execution has them whatever else it has, so a manifest missing one
	// is not a smaller manifest, it is a broken one.
	for _, missing := range []string{"project_root", "base_dir", "work_dir", "config_dir", "output_dir"} {
		document := strings.Replace(manifestWith(""), "  "+missing+":\n", "  absent_"+missing+":\n", 1)
		if _, err := wrench.LoadFormattedFile("m.yaml", wrench.ManifestSchema, wrench.YAML, &stubReader{data: []byte(document)}); err == nil {
			t.Errorf("a manifest without %s was accepted", missing)
		}
	}
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestATaskMayAllowAnEmptySelection(t *testing.T) {
	// An empty selection is a failure by default, because a pattern matching
	// nothing is far more often a stale path than a deliberate one. A task says
	// otherwise for itself, and only where there is a selection to be empty:
	// a command naming neither path variable has none, and a jig task has none
	// either because emptiness is its child's business.
	accepted := map[string]string{
		"one execution per path":  "tasks:\n  - name: check\n    command: jq . {each_path}\n    matching: [\"*.json\"]\n    allow-empty: true\n",
		"one over the whole set":  "tasks:\n  - name: check\n    command: jq . {all_paths}\n    matching: [\"*.json\"]\n    allow-empty: true\n",
		"declining it explicitly": "tasks:\n  - name: check\n    command: go test ./...\n    allow-empty: false\n",
		"omitting it":             "tasks:\n  - name: check\n    command: go test ./...\n",
	}
	for what, document := range accepted {
		if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(document)}); err != nil {
			t.Errorf("%s was refused: %v", what, err)
		}
	}

	refused := map[string]string{
		"a command with no selection to be empty": "tasks:\n  - name: check\n    command: go test ./...\n    allow-empty: true\n",
		"a jig task, whose child owns emptiness":  "tasks:\n  - name: child\n    jig: other\n    allow-empty: true\n",
	}
	for what, document := range refused {
		if _, err := wrench.LoadFormattedFile("bolt.q.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(document)}); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}
