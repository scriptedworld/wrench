package wrench_test

import (
	"flag"
	"os"
	"path/filepath"
	"testing"

	"github.com/scriptedworld/wrench"
)

var update = flag.Bool("update", false, "rewrite the canonical fixtures from what the codec emits")

// fixtureRoot holds the shared fixture set. Each case is a directory with an
// input and the canonical form the codec must produce from it. The files are
// language-neutral on purpose: a second language pack is held level by being
// run against these same directories, which is what stops two implementations
// agreeing on the schema and disagreeing on the bytes.
const fixtureRoot = "testdata/canonical"

// COVERS: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-5.5, FR-5.6 | property
func TestCanonicalFixtures(t *testing.T) {
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
			dir := filepath.Join(fixtureRoot, entry.Name())
			input := mustRead(t, filepath.Join(dir, "input.yaml"))

			value, err := wrench.YAML.Decode(input)
			if err != nil {
				t.Fatalf("decoding input: %v", err)
			}

			got, err := wrench.YAML.Encode(value)
			if err != nil {
				t.Fatalf("encoding: %v", err)
			}

			golden := filepath.Join(dir, "canonical.yaml")
			if *update {
				writeGolden(t, golden, got)
				return
			}

			want := mustRead(t, golden)
			if string(got) != string(want) {
				t.Errorf("canonical form differs\n--- want ---\n%s\n--- got ---\n%s", want, got)
			}
		})
	}
}

// COVERS: FR-4.5 | property
func TestCanonicalFormIsAFixedPoint(t *testing.T) {
	cases, err := os.ReadDir(fixtureRoot)
	if err != nil {
		t.Fatalf("reading %s: %v", fixtureRoot, err)
	}

	for _, entry := range cases {
		if !entry.IsDir() {
			continue
		}
		t.Run(entry.Name(), func(t *testing.T) {
			golden := filepath.Join(fixtureRoot, entry.Name(), "canonical.yaml")
			canonical := mustRead(t, golden)

			value, err := wrench.YAML.Decode(canonical)
			if err != nil {
				t.Fatalf("decoding canonical form: %v", err)
			}

			again, err := wrench.YAML.Encode(value)
			if err != nil {
				t.Fatalf("re-encoding: %v", err)
			}

			if string(again) != string(canonical) {
				t.Errorf("encoding canonical form changed it, so it is not canonical\n--- was ---\n%s\n--- became ---\n%s", canonical, again)
			}
		})
	}
}

func mustRead(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("reading %s: %v", path, err)
	}
	return data
}

func writeGolden(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("writing %s: %v", path, err)
	}
	t.Logf("wrote %s", path)
}
