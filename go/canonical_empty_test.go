package wrench_test

import (
	"testing"

	"github.com/scriptedworld/wrench/go"
)

// An empty container has one spelling, and it is the short one. The recursive
// path never reaches this arm, so line coverage read it as covered while the
// branch went untaken — found in the Python pack on 2026-09-04 when the gate
// began judging branches, and asserted here because a pack agreeing about full
// containers and differing about empty ones is exactly what a shared case set
// exists to catch.

// COVERS: FR-4.6 | edge
func TestJSONEmptyContainersAreShort(t *testing.T) {
	for _, tc := range []struct {
		name  string
		value map[string]any
		want  string
	}{
		{"an empty document", map[string]any{}, "{}\n"},
		{"an empty mapping", map[string]any{"v": map[string]any{}}, "{\n  \"v\": {}\n}\n"},
		{"an empty sequence", map[string]any{"v": []any{}}, "{\n  \"v\": []\n}\n"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			encoded, err := wrench.JSON.Encode(tc.value)
			if err != nil {
				t.Fatalf("encode: %v", err)
			}
			if string(encoded) != tc.want {
				t.Errorf("got %q, want %q", encoded, tc.want)
			}
		})
	}
}

// COVERS: FR-4.6 | edge
func TestJSONNestedEmptyContainersKeepTheShortSpelling(t *testing.T) {
	encoded, err := wrench.JSON.Encode(map[string]any{
		"a": map[string]any{"b": map[string]any{}},
		"c": []any{[]any{}},
	})
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	want := "{\n  \"a\": {\n    \"b\": {}\n  },\n  \"c\": [\n    []\n  ]\n}\n"
	if string(encoded) != want {
		t.Errorf("got %q, want %q", encoded, want)
	}
}
