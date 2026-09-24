package wrench_test

import (
	"os"
	"path/filepath"
	"testing"
)

// The sentence FR-3.10d requires of every pack. Held as a constant so a change
// to the wording fails a test rather than drifting quietly through three
// repositories' worth of consumers.
const wrenchRefusal = "a schema may reference the shipped schemas and its own fragments, " +
	"and nothing else"

// reachableSchema is a schema that really is on disk, so "it was not read" is a
// measurement rather than the absence of a target. It requires a property no
// test instance carries, so a document validated against it would fail loudly.
const reachableSchema = `{"$schema":"https://json-schema.org/draft/2020-12/schema",` +
	`"type":"object","required":["proof_it_resolved"]}`

// seedReachableSchema writes that schema and hands back the path it is at.
//
// One file per test under the test's own directory, rather than one fixed path
// seeded once for the package. A shared path is what a caller cannot reason
// about: it outlives the run that wrote it, and it is the reason these tests
// could not be run in parallel.
func seedReachableSchema(t *testing.T) string {
	t.Helper()

	path := filepath.Join(t.TempDir(), "wrench-reachable.schema.json")
	if err := os.WriteFile(path, []byte(reachableSchema), 0o600); err != nil {
		t.Fatalf("seeding the reachable schema: %v", err)
	}
	return path
}
