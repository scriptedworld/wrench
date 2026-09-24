package wrench_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench/go"
)

// schemaFileDir is where the shipped schemas sit as files. The library embeds
// the same directory; this is the test reading them the way a YAML language
// server would.
const schemaFileDir = "../schemas"

// fixtureRoot holds the shared fixture set. Each case is a directory with an
// input and the canonical form the codec must produce from it. The files are
// language-neutral on purpose: a second language pack is held level by being
// run against these same directories, which is what stops two implementations
// agreeing on the schema and disagreeing on the bytes.
const fixtureRoot = "../testdata/canonical"

// updateVariable asks for the canonical fixtures to be rewritten from what the
// codec emits, rather than compared against.
const updateVariable = "WRENCH_UPDATE_FIXTURES"

// updatingFixtures reports whether this run was asked to rewrite the fixtures.
//
// An environment variable rather than a -update flag. Registering a flag has to
// happen before the testing package parses the command line, which needs either
// a package-level variable holding it, which is the mutable package state
// gochecknoglobals refuses, or a TestMain, which test-traceability.py reads as
// a test and fails for discharging no requirement.
//
//	WRENCH_UPDATE_FIXTURES=1 go test ./...
func updatingFixtures() bool {
	return os.Getenv(updateVariable) != ""
}

// COVERS: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-5.5, FR-5.6 | property
func TestCanonicalFixtures(t *testing.T) {
	t.Parallel()

	// Each subtest is one fixture directory and writes only its own file when
	// rewriting, so no two touch the same path. The test that READS those
	// golden files declines to run while rewriting, for that reason.
	cases, err := os.ReadDir(fixtureRoot)
	if err != nil {
		t.Fatalf("reading %s: %v", fixtureRoot, err)
	}
	if len(cases) == 0 {
		t.Fatalf("%s holds no cases, so this test asserts nothing", fixtureRoot)
	}

	for _, entry := range cases {
		if !entry.IsDir() {
			continue
		}
		t.Run(entry.Name(), func(t *testing.T) {
			t.Parallel()
			checkCanonicalFixture(t, filepath.Join(fixtureRoot, entry.Name()))
		})
	}
}

// checkCanonicalFixture holds one fixture directory to the canonical form its
// input produces, and to the schema it declares where it declares one.
func checkCanonicalFixture(t *testing.T, dir string) {
	t.Helper()

	input := mustRead(t, filepath.Join(dir, "input.yaml"))

	value, err := wrench.YAML().Decode(input)
	if err != nil {
		t.Fatalf("decoding input: %v", err)
	}

	got, err := wrench.YAML().Encode(value)
	if err != nil {
		t.Fatalf("encoding: %v", err)
	}

	golden := filepath.Join(dir, "canonical.yaml")
	if updatingFixtures() {
		writeGolden(t, golden, got)
		return
	}

	want := mustRead(t, golden)
	if string(got) != string(want) {
		t.Errorf("canonical form differs\n--- want ---\n%s\n--- got ---\n%s", want, got)
	}

	// A fixture that is an instance of a shipped schema says so, and is held to
	// it. Byte-identical output between two packs says they agree on the
	// spelling; it does not say the thing they spelled is a document any
	// consumer would accept.
	schema := declaredSchema(t, dir)
	if schema == nil {
		return
	}
	if err := schema.Validate(value); err != nil {
		t.Errorf("the fixture does not satisfy the schema it declares: %v", err)
	}
}

// declaredSchema returns the shipped schema a fixture names in its `schema`
// file, or nil where it names none. A fixture with no such file is a codec case
// and nothing more.
func declaredSchema(t *testing.T, dir string) wrench.Schema {
	t.Helper()

	data, err := os.ReadFile(filepath.Clean(filepath.Join(dir, "schema")))
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		t.Fatalf("reading the declared schema: %v", err)
	}

	id := strings.TrimSpace(string(data))
	shipped := map[string]wrench.Schema{
		"https://scriptedworld.github.io/wrench/envelope.schema.json":    wrench.EnvelopeSchema(),
		"https://scriptedworld.github.io/wrench/jig.schema.json":         wrench.JigSchema(),
		"https://scriptedworld.github.io/wrench/manifest.schema.json":    wrench.ManifestSchema(),
		"https://scriptedworld.github.io/wrench/definitions.schema.json": wrench.DefinitionsSchema(),
	}
	schema, ok := shipped[id]
	if !ok {
		t.Fatalf("%s declares schema %q, which this pack does not ship", dir, id)
	}
	return schema
}

// COVERS: FR-3.8 | positive
func TestEveryShippedSchemaHasAnInstanceFixture(t *testing.T) {
	t.Parallel()

	// A schema nothing is ever validated against is a schema nobody knows
	// compiles, let alone accepts a real document. Requiring an instance per
	// shipped schema makes "the format is valid" a property of the fixture set
	// rather than something a reader has to take on trust.
	//
	// The directory is the authority on both sides, so a fifth schema fails here
	// until it has a fixture, and this test needs no editing to notice.
	declared := make(map[string]bool)
	entries, err := os.ReadDir(schemaFileDir)
	if err != nil {
		t.Fatalf("reading %s: %v", schemaFileDir, err)
	}
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".schema.json") {
			continue
		}
		data := mustRead(t, filepath.Join(schemaFileDir, entry.Name()))
		var document struct {
			ID string `json:"$id"`
		}
		if err := json.Unmarshal(data, &document); err != nil {
			t.Fatalf("%s is not JSON: %v", entry.Name(), err)
		}
		declared[document.ID] = false
	}
	if len(declared) == 0 {
		t.Fatalf("%s holds no schemas, so this test asserts nothing", schemaFileDir)
	}

	cases, err := os.ReadDir(fixtureRoot)
	if err != nil {
		t.Fatalf("reading %s: %v", fixtureRoot, err)
	}
	for _, entry := range cases {
		if !entry.IsDir() {
			continue
		}
		data, err := os.ReadFile(filepath.Join(fixtureRoot, entry.Name(), "schema"))
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			t.Fatalf("reading the declared schema: %v", err)
		}
		id := strings.TrimSpace(string(data))
		if _, ok := declared[id]; !ok {
			t.Errorf("fixture %s declares %s, which no file in %s declares", entry.Name(), id, schemaFileDir)
			continue
		}
		declared[id] = true
	}

	for id, covered := range declared {
		if !covered {
			t.Errorf("no fixture is an instance of %s, so nothing validates against it", id)
		}
	}
}

// COVERS: FR-4.5 | property
func TestCanonicalFormIsAFixedPoint(t *testing.T) {
	t.Parallel()

	// Rewriting has TestCanonicalFixtures writing the very files this reads,
	// and both run in parallel, so there is then no stable thing here to assert
	// against. The property is not weakened by skipping it: the gate never asks
	// for a rewrite, so every run that decides anything runs this.
	if updatingFixtures() {
		t.Skip(updateVariable + " is rewriting these fixtures; run again without it")
	}

	cases, err := os.ReadDir(fixtureRoot)
	if err != nil {
		t.Fatalf("reading %s: %v", fixtureRoot, err)
	}

	for _, entry := range cases {
		if !entry.IsDir() {
			continue
		}
		t.Run(entry.Name(), func(t *testing.T) {
			t.Parallel()

			golden := filepath.Join(fixtureRoot, entry.Name(), "canonical.yaml")
			canonical := mustRead(t, golden)

			value, err := wrench.YAML().Decode(canonical)
			if err != nil {
				t.Fatalf("decoding canonical form: %v", err)
			}

			again, err := wrench.YAML().Encode(value)
			if err != nil {
				t.Fatalf("re-encoding: %v", err)
			}

			if string(again) != string(canonical) {
				t.Errorf("encoding canonical form changed it, so it is not canonical"+
					"\n--- was ---\n%s\n--- became ---\n%s", canonical, again)
			}
		})
	}
}

// mustRead reads a fixture, failing rather than returning empty bytes that
// would make a caller assert nothing.
//
// The path is cleaned because gosec cannot tell a fixture path from a caller's
// input. Cleaning normalises the spelling and confines nothing; what is read
// here is whatever the fixture tree holds, which is the point.
func mustRead(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		t.Fatalf("reading %s: %v", path, err)
	}
	return data
}

// writeGolden rewrites one fixture. The mode is the owner's
// alone: git records 100644 for every tracked file whatever the working tree
// carries, so what this writes never reaches a consumer.
func writeGolden(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("writing %s: %v", path, err)
	}
	t.Logf("wrote %s", path)
}
