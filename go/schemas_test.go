package wrench_test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench/go"
)

// exportedSchemas is every shipped schema this pack offers by name, keyed by
// the $id it is named by. Go cannot enumerate its own package variables, so
// this list is the thing that has to be kept in step with schemas/, and
// TestEveryShippedSchemaIsExported is what keeps it.
//
// A function rather than a package variable: the map would be mutable
// package-level state that any test could write through, and building it per
// caller costs nothing beside compiling a schema.
func exportedSchemas() map[string]wrench.Schema {
	return map[string]wrench.Schema{
		"https://scriptedworld.github.io/wrench/envelope.schema.json":    wrench.EnvelopeSchema(),
		"https://scriptedworld.github.io/wrench/jig.schema.json":         wrench.JigSchema(),
		"https://scriptedworld.github.io/wrench/manifest.schema.json":    wrench.ManifestSchema(),
		"https://scriptedworld.github.io/wrench/definitions.schema.json": wrench.DefinitionsSchema(),
	}
}

// aLocalSchema is a perfectly good schema written to disk, so a refusal to
// follow a reference at it is a measurement rather than the absence of a
// target.
const aLocalSchema = `{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}`

// mustSchemaFiles lists the shipped schema filenames, failing rather than
// returning an empty set that would make a caller assert nothing.
func mustSchemaFiles(t *testing.T) []string {
	t.Helper()

	entries, err := os.ReadDir(schemaFileDir)
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

	data, err := os.ReadFile(filepath.Clean(filepath.Join(schemaFileDir, name)))
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

	entries, err := os.ReadDir(schemaFileDir)
	if err != nil {
		t.Fatalf("schemas/ is not readable: %v", err)
	}

	ids := make(map[string]string)
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".schema.json") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(schemaFileDir, entry.Name()))
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

// schemaPair is one shipped schema reached both ways, with a document that
// schema accepts. The document is what makes the comparison a measurement: two
// Schemas that refuse everything would agree on nothing useful.
type schemaPair struct {
	grouped  wrench.Schema
	suffixed wrench.Schema
	accepted string
}

// groupedAgainstSuffixed pairs each shipped schema's two spellings.
//
// A function rather than a package variable: these compile on first use, and a
// package-level map would be mutable state any test could write through.
func groupedAgainstSuffixed() map[string]schemaPair {
	return map[string]schemaPair{
		"envelope": {
			wrench.Schemas().Envelope, wrench.EnvelopeSchema(),
			"success: true\n",
		},
		"jig": {
			wrench.Schemas().Jig, wrench.JigSchema(),
			"tasks:\n  - name: check\n    command: \"true\"\n",
		},
		"manifest": {
			wrench.Schemas().Manifest, wrench.ManifestSchema(),
			manifestWith(""),
		},
		"definitions": {
			wrench.Schemas().Definitions, wrench.DefinitionsSchema(),
			"requirements: ../REQUIREMENTS.md\n",
		},
	}
}

// COVERS: FR-5.7 | positive
func TestTheShippedSetIsReachableWithoutTheSuffix(t *testing.T) {
	t.Parallel()

	// wrench.Schemas().Jig rather than wrench.JigSchema(). Go has no namespace
	// inside a package, so a struct is what gives the shape the other two packs
	// spell as a module.
	//
	// Asserting that the two spellings mean one document, and doing it by
	// behaviour rather than by identity. Each accessor builds a Schema from the
	// same id const, so there is no pointer to compare; what a caller can
	// observe is that both accept and refuse the same bytes, and that is the
	// drift this has to rule out. Python and Rust assert identity because their
	// packs can hold a module-level singleton and this one cannot.
	for name, pair := range groupedAgainstSuffixed() {
		if pair.grouped == nil || pair.suffixed == nil {
			t.Errorf("Schemas().%s is nil", name)
			continue
		}
		grouped := loadDocument(name+".yaml", pair.grouped, pair.accepted)
		suffixed := loadDocument(name+".yaml", pair.suffixed, pair.accepted)
		if (grouped == nil) != (suffixed == nil) {
			t.Errorf("Schemas().%s and the suffixed name disagree: %v against %v",
				name, grouped, suffixed)
		}
		if grouped != nil {
			t.Errorf("Schemas().%s refused a document its own schema accepts: %v", name, grouped)
		}
	}

	// It validates, so the grouping carries working schemas and not just names.
	if _, err := wrench.LoadFormattedFile("out.yaml", wrench.Schemas().Envelope, wrench.YAML(),
		&stubReader{data: []byte("success: true\n")}); err != nil {
		t.Errorf("Schemas.Envelope did not validate a passing envelope: %v", err)
	}
}

// COVERS: FR-3.7, FR-5.7 | regression
func TestEveryShippedSchemaIsExported(t *testing.T) {
	t.Parallel()

	// A schema added to schemas/ and picked up by one pack but not the other is
	// a divergence in the contract that nothing reports: a fourth schema can
	// ship and Go export it while Python, naming three filenames in its source,
	// does not. Each pack asserts against the directory, so both agreeing with
	// the directory is what makes them agree with each other.
	declared := declaredIDs(t)

	for id, file := range declared {
		schema, ok := exportedSchemas()[id]
		if !ok {
			t.Errorf("%s declares %s and this pack exports no schema for it", file, id)
			continue
		}
		if schema == nil {
			t.Errorf("%s is exported as nil", id)
		}
	}

	for id := range exportedSchemas() {
		if _, ok := declared[id]; !ok {
			t.Errorf("this pack exports %s and no file in schemas/ declares it", id)
		}
	}
}

// COVERS: FR-1.1, FR-3.2, FR-3.5 | positive
func TestTheSchemasShipAsFilesBesideTheLibrary(t *testing.T) {
	t.Parallel()

	// Embedded is how a consumer links one static binary. Present as files is
	// what lets a YAML language server be pointed at them while a jig is being
	// written, and it is what keeps one copy rather than one per pack.
	shipped := []string{
		"envelope.schema.json", "jig.schema.json",
		"manifest.schema.json", "definitions.schema.json",
	}
	for _, name := range shipped {
		path := filepath.Join(schemaFileDir, name)
		data, err := os.ReadFile(filepath.Clean(path))
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
	t.Parallel()

	// $ref resolution, $defs and conditional application are the parts a
	// hand-written checker never gets right. Binding to an established
	// implementation means they work, and this is what that buys.
	document := `{
	  "$schema": "https://json-schema.org/draft/2020-12/schema",
	  "type": "object",
	  "properties": { "items": { "type": "array", "items": { "$ref": "#/$defs/entry" } } },
	  "$defs": { "entry": {
	    "type": "object", "required": ["id"], "properties": { "id": { "type": "integer" } }
	  } }
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
	t.Parallel()

	// The conditional is the part of the envelope schema most likely to be
	// wrong, because it is the only rule that reads one key to decide another.
	passing := "success: true\n"
	if err := loadDocument("f.yaml", wrench.EnvelopeSchema(), passing); err != nil {
		t.Errorf("a passing envelope with no reasons was refused: %v", err)
	}

	failingWithout := "success: false\n"
	if err := loadDocument("f.yaml", wrench.EnvelopeSchema(), failingWithout); err == nil {
		t.Error("a failing envelope with no reasons was accepted, so a failure need not say why")
	}
}

// COVERS: FR-3.2 | regression
func TestAValidationErrorNamesTheSchemaByIdNotByLocalPath(t *testing.T) {
	t.Parallel()

	// The identifier lands in the error, the error lands in a reason, and a
	// reason travels as evidence. Naming a shipped schema by a relative
	// filename resolved it against whatever directory the process started in,
	// which put an absolute local path in front of every consumer.
	invalid := []byte("success: \"yes\"\n")
	_, err := wrench.LoadFormattedFile(
		"f.yaml", wrench.EnvelopeSchema(), wrench.YAML(), &stubReader{data: invalid})
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
	t.Parallel()

	// The block and the file are one shape, written once and referenced across
	// two shipped schemas. A jig carrying a nested value has to be refused by a
	// rule the jig schema does not itself state, which is what proves the
	// reference between them resolved.
	flat := "definitions:\n  requirements: REQUIREMENTS.md\n  line_length: 100\n" +
		"tasks:\n  - name: check\n    command: \"true\"\n"
	if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), flat); err != nil {
		t.Errorf("a jig with a flat definitions block was refused: %v", err)
	}

	nested := "definitions:\n  python:\n    line_length: 100\n" +
		"tasks:\n  - name: check\n    command: \"true\"\n"
	if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), nested); err == nil {
		t.Error("a nested definitions value was accepted, so the shared shape did not apply")
	}
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestAJigMayDeclareItStandsAtTheRepositoryRoot(t *testing.T) {
	t.Parallel()

	// The field reaches the working directory and nothing else. The walk, the
	// containment, the filter patterns and {base_dir} stay what the caller
	// granted, which is why it is a boolean on the jig rather than a base a jig
	// task can be talked into widening.
	tasks := "tasks:\n  - name: check\n    command: \"true\"\n"

	declarations := []string{
		"needs-repository-root: true\n", "needs-repository-root: false\n", "",
	}
	for _, declared := range declarations {
		document := declared + tasks
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), document); err != nil {
			t.Errorf("a jig declaring %q was refused: %v", declared, err)
		}
	}

	refused := map[string]string{
		"a string":     "needs-repository-root: \"true\"\n",
		"a number":     "needs-repository-root: 1\n",
		"an empty key": "needs-repository-root:\n",
	}
	for what, declared := range refused {
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), declared+tasks); err == nil {
			t.Errorf("%s was accepted as needs-repository-root", what)
		}
	}

	// It is the jig's, not a jig task's. A tool needing the root needs it
	// wherever it is placed, so a caller cannot grant it per placement.
	onTask := "tasks:\n  - name: child\n    jig: other\n    needs-repository-root: true\n"
	if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), onTask); err == nil {
		t.Error("a jig task carrying needs-repository-root was accepted")
	}
}

// versionedFormats names the shipped schemas that carry a top-level version,
// with a document each that is otherwise valid. definitions is absent on
// purpose: it is an open mapping where every key is a placeholder name, so
// reserving one costs something the other three do not pay.
func versionedFormats() map[string]struct {
	schema wrench.Schema
	rest   string
} {
	return map[string]struct {
		schema wrench.Schema
		rest   string
	}{
		"envelope": {wrench.EnvelopeSchema(), "success: true\n"},
		"jig":      {wrench.JigSchema(), "tasks:\n  - name: check\n    command: \"true\"\n"},
		"manifest": {wrench.ManifestSchema(), manifestWith("")},
	}
}

// COVERS: FR-3.9 | edge
func TestAFormatMayDeclareTheVersionItConformsTo(t *testing.T) {
	t.Parallel()

	// Optional, because every document written before the field existed carries
	// none and claiming nothing is the honest reading of that. Present, it is
	// semver, so a consumer can refuse a major rather than failing later on a
	// field it cannot find.
	accepted := []string{
		"1.0.0", "0.1.0", "10.20.30", "1.0.0-alpha.1", "1.0.0+build.5", "1.0.0-rc.1+build.5",
	}
	refused := []string{"1", "1.0", "v1.0.0", "1.0.0.0", "01.0.0", "", "latest", "1.0.0-"}

	for name, format := range versionedFormats() {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			checkVersionField(t, format.schema, format.rest, accepted, refused)
		})
	}
}

// checkVersionField holds one shipped format to the version grammar: absent is
// valid, every accepted spelling is taken, every refused one is not, and an
// unquoted number is not a version at all.
func checkVersionField(
	t *testing.T, schema wrench.Schema, rest string, accepted, refused []string,
) {
	t.Helper()

	// Absent is valid, which is what makes the field additive.
	if err := loadDocument("f.yaml", schema, rest); err != nil {
		t.Errorf("a document with no version was refused: %v", err)
	}

	for _, version := range accepted {
		document := "version: \"" + version + "\"\n" + rest
		if err := loadDocument("f.yaml", schema, document); err != nil {
			t.Errorf("version %q was refused: %v", version, err)
		}
	}

	for _, version := range refused {
		document := "version: \"" + version + "\"\n" + rest
		if err := loadDocument("f.yaml", schema, document); err == nil {
			t.Errorf("version %q was accepted and is not semver", version)
		}
	}

	// A bare number is the mistake this pattern exists to catch: YAML reads 1.0
	// as a float, and a float is not a version.
	if err := loadDocument("f.yaml", schema, "version: 1.0\n"+rest); err == nil {
		t.Error("an unquoted 1.0 was accepted, so it was read as a float and passed as a version")
	}
}

// loadDocument runs one document through the two-call load against a schema,
// with the bytes held in memory and no filesystem involved.
//
// It hands back the failure alone. Every case in this file asks whether a
// document was accepted or refused and none of them reads the value, so
// returning it would be a result nothing uses.
func loadDocument(path string, schema wrench.Schema, document string) error {
	_, err := wrench.LoadFormattedFile(
		path, schema, wrench.YAML(), &stubReader{data: []byte(document)})
	if err != nil {
		return fmt.Errorf("loading %s: %w", path, err)
	}
	return nil
}

// COVERS: FR-3.9 | property
func TestTheVersionFieldIsTheSameInEveryFormatThatCarriesIt(t *testing.T) {
	t.Parallel()

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
	t.Parallel()

	// The case a consumer most wants: an adapter extending the envelope schema
	// references it instead of copying it, and a copy is the drift FR-3.2
	// forbids.
	schema, err := wrench.CompileSchema("mine.schema.json",
		strings.NewReader(consumerSchema(
			"https://scriptedworld.github.io/wrench/definitions.schema.json")))
	if err != nil {
		t.Fatalf("compiling a schema that references a shipped one: %v", err)
	}

	if err := schema.Validate(map[string]any{"d": map[string]any{"a": "x"}}); err != nil {
		t.Errorf("a flat definitions mapping was refused: %v", err)
	}

	// A nested value is refused by a rule only the referenced schema states, so
	// a refusal here is what proves the reference resolved rather than being
	// skipped.
	deep := map[string]any{"d": map[string]any{"a": map[string]any{"b": 1}}}
	if err := schema.Validate(deep); err == nil {
		t.Error("a nested value was accepted, so the reference did not resolve")
	}
}

// COVERS: FR-3.10 | negative
func TestASchemaMayReferenceNothingOutsideTheShippedSet(t *testing.T) {
	t.Parallel()

	// Unguarded, file:// and a bare absolute path both load that file off disk,
	// so a schema's meaning depends on files outside it. The Go binding never
	// fetched over the network.
	local := filepath.Join(t.TempDir(), "local.schema.json")
	if err := os.WriteFile(local, []byte(aLocalSchema), 0o600); err != nil {
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
			t.Errorf("%s (%s) resolved, so validation depends on something outside the process",
				what, target)
		}
	}
}

// COVERS: FR-3.10 | negative
func TestTheEnvironmentCannotRestoreExternalReferences(t *testing.T) {
	// The escape hatch is retired, but the variable was documented and somebody
	// may still set it. A refusal that quietly turns permissive because an old
	// name is still honoured is the failure this pins.
	//
	// While it existed, one variable meant three different things. Setting it
	// let Python fetch over HTTP and read files, let Go read files only, and did
	// nothing at all in Rust, whose bound crate never linked the resolving code.
	local := filepath.Join(t.TempDir(), "local.schema.json")
	if err := os.WriteFile(local, []byte(aLocalSchema), 0o600); err != nil {
		t.Fatalf("seeding: %v", err)
	}
	document := consumerSchema("file://" + local)

	if _, err := wrench.CompileSchema("mine.schema.json", strings.NewReader(document)); err == nil {
		t.Fatal("a file reference resolved with no variable set")
	}

	t.Setenv("WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS", "1")
	if _, err := wrench.CompileSchema("mine.schema.json", strings.NewReader(document)); err == nil {
		t.Error("the retired variable still opens external references")
	}
}

// COVERS: FR-3.10 | edge
func TestACallerCannotRedefineAShippedSchema(t *testing.T) {
	t.Parallel()

	// Registering a shipped id twice would let a document decide what the
	// envelope schema means, which is the one thing a shipped schema fixes.
	for id := range exportedSchemas() {
		_, err := wrench.CompileSchema(id, strings.NewReader(
			`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}`))
		if err == nil {
			t.Errorf("%s was redefined by a caller", id)
		}
	}
}

// COVERS: FR-3.2, FR-3.3 | negative
func TestADefinitionsFileTakesOneLevelOfScalars(t *testing.T) {
	t.Parallel()

	scalars := "requirements: ../REQUIREMENTS.md\nline_length: 100\nstrict: true\nempty: \"\"\n"
	if err := loadDocument("d.yaml", wrench.DefinitionsSchema(), scalars); err != nil {
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
		if err := loadDocument("d.yaml", wrench.DefinitionsSchema(), document); err == nil {
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
	t.Parallel()

	// Without this, a change to the manifest schema can break one pack alone
	// and go unnoticed in the other. A shipped schema no pack validates against
	// is a shape the gate cannot hold either pack to.
	accepted := manifestWith(
		"  requirements:\n    value: ../REQUIREMENTS.md\n    from: file\n" +
			"  all_paths:\n    value:\n      - a.go\n      - b.go\n    from: bolt\n")
	if err := loadDocument("m.yaml", wrench.ManifestSchema(), accepted); err != nil {
		t.Errorf("a manifest naming the layer of each variable was refused: %v", err)
	}

	refused := map[string]string{
		"a bare value":              "  requirements: ../REQUIREMENTS.md\n",
		"a value with no layer":     "  requirements:\n    value: x\n",
		"a layer with no value":     "  requirements:\n    from: jig\n",
		"a layer outside the three": "  requirements:\n    value: x\n    from: environment\n",
	}
	for what, variable := range refused {
		if err := loadDocument("m.yaml", wrench.ManifestSchema(), manifestWith(variable)); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}

// COVERS: FR-3.1 | negative
func TestAManifestKeepsTheFiveLocations(t *testing.T) {
	t.Parallel()

	// Every execution has them whatever else it has, so a manifest missing one
	// is not a smaller manifest, it is a broken one.
	locations := []string{"project_root", "base_dir", "work_dir", "config_dir", "output_dir"}
	for _, missing := range locations {
		document := strings.Replace(manifestWith(""), "  "+missing+":\n", "  absent_"+missing+":\n", 1)
		if err := loadDocument("m.yaml", wrench.ManifestSchema(), document); err == nil {
			t.Errorf("a manifest without %s was accepted", missing)
		}
	}
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestATaskMayAllowAnEmptySelection(t *testing.T) {
	t.Parallel()

	// An empty selection is a failure by default, because a pattern matching
	// nothing is far more often a stale path than a deliberate one. A task says
	// otherwise for itself, and only where there is a selection to be empty:
	// a command naming neither path variable has none, and a jig task has none
	// either because emptiness is its child's business.
	accepted := map[string]string{
		"one execution per path": "tasks:\n  - name: check\n    command: jq . {each_path}\n" +
			"    matching: [\"*.json\"]\n    optional: true\n",
		"one over the whole set": "tasks:\n  - name: check\n    command: jq . {all_paths}\n" +
			"    matching: [\"*.json\"]\n    optional: true\n",
		"declining it explicitly": "tasks:\n  - name: check\n    command: go test ./...\n" +
			"    optional: false\n",
		"omitting it": "tasks:\n  - name: check\n    command: go test ./...\n",
	}
	for what, document := range accepted {
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), document); err != nil {
			t.Errorf("%s was refused: %v", what, err)
		}
	}

	refused := map[string]string{
		"a command with no selection to be empty": "tasks:\n  - name: check\n" +
			"    command: go test ./...\n    optional: true\n",
		"a jig task, whose child owns emptiness": "tasks:\n  - name: child\n" +
			"    jig: other\n    optional: true\n",
	}
	for what, document := range refused {
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), document); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestATimeLimitIsADecimalWithAUnit(t *testing.T) {
	t.Parallel()

	// The grammar is deliberately narrower than a float parse, so the runner
	// and this schema stay expressible as the same regex. A jig author gets the
	// error against the document being edited rather than one layer later.
	accepted := []string{"30s", "1.5m", "2h", "0.5s", ".5s", "90m"}
	for _, limit := range accepted {
		document := "time-limit: " + limit + "\ntasks:\n  - name: check\n" +
			"    command: go test ./...\n    time-limit: " + limit + "\n"
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), document); err != nil {
			t.Errorf("%s was refused: %v", limit, err)
		}
	}

	// `30` is the one a jig author actually writes, and the runner refuses it,
	// so the schema has to refuse it too.
	refused := map[string]string{
		"a bare number":   "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: 30\n",
		"a list":          "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: [30]\n",
		"no unit":         "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"30\"\n",
		"an unknown unit": "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"30d\"\n",
		"exponent notation": "tasks:\n  - name: c\n    command: go test ./...\n" +
			"    time-limit: \"1e3s\"\n",
		"a sign": "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"+5s\"\n",
		"an infinity": "tasks:\n  - name: c\n    command: go test ./...\n" +
			"    time-limit: \"infs\"\n",
		"on the jig itself": "time-limit: 30\ntasks:\n  - name: c\n    command: go test ./...\n",
	}
	for what, document := range refused {
		if err := loadDocument("bolt.q.yaml", wrench.JigSchema(), document); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}

// COVERS: FR-3.1, FR-3.4 | edge
func TestEnvelopeEvidenceAndStatisticsAreObjects(t *testing.T) {
	t.Parallel()

	// With a description and no type, a producer could write either as a
	// string, a list or a number and validation would pass every time. The
	// member shape stays open: constraining it would bind every producer to one
	// runner's naming.
	accepted := "success: true\nmetadata:\n  evidence:\n    alpha-1:\n      result: /tmp/a\n" +
		"  statistics:\n    checked: 12\n"
	if err := loadDocument("out.yaml", wrench.EnvelopeSchema(), accepted); err != nil {
		t.Errorf("a mapping of evidence was refused: %v", err)
	}

	refused := map[string]string{
		"evidence as a bare string": "success: true\nmetadata:\n  evidence: /tmp/a\n",
		"evidence as a number":      "success: true\nmetadata:\n  evidence: 12\n",
		"statistics as a number":    "success: true\nmetadata:\n  statistics: 12\n",
	}
	for what, document := range refused {
		if err := loadDocument("out.yaml", wrench.EnvelopeSchema(), document); err == nil {
			t.Errorf("%s was accepted", what)
		}
	}
}
