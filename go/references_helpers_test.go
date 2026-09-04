package wrench_test

import (
	"os"
	"sync"
	"testing"
)

// The sentence FR-3.10d requires of every pack. Held as a constant so a change
// to the wording fails a test rather than drifting quietly through three
// repositories' worth of consumers.
const wrenchRefusal = "a schema may reference the shipped schemas and its own fragments, and nothing else"

// A schema that really is on disk, so "it was not read" is a measurement rather
// than the absence of a target. It requires a property no test instance carries,
// so a document validated against it would fail loudly.
const reachablePath = "/tmp/wrench-reachable.schema.json"

var seedOnce sync.Once

func seedReachableSchema(t *testing.T) {
	t.Helper()
	seedOnce.Do(func() {
		body := []byte(`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","required":["proof_it_resolved"]}`)
		if err := os.WriteFile(reachablePath, body, 0o644); err != nil {
			t.Fatalf("seeding the reachable schema: %v", err)
		}
	})
}
