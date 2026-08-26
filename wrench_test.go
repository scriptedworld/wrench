package wrench_test

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/scriptedworld/wrench"
)

// stubReader hands back bytes without touching a filesystem. Its existence is
// the point of FR-2.5a: a reader takes the path, so a test replaces the whole
// IO boundary rather than only the parse.
type stubReader struct {
	data    []byte
	err     error
	sawPath string
}

func (r *stubReader) Read(path string) ([]byte, error) {
	r.sawPath = path
	return r.data, r.err
}

type stubWriter struct {
	sawPath string
	data    []byte
	err     error
}

func (w *stubWriter) Write(path string, data []byte) error {
	w.sawPath = path
	w.data = data
	return w.err
}

const validEnvelope = `success: true` + "\n"

// COVERS: FR-2.1, FR-2.2 | positive
func TestLoadFormattedFileReturnsTheValidatedStructure(t *testing.T) {
	reader := &stubReader{data: []byte(validEnvelope)}

	value, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, reader)
	if err != nil {
		t.Fatalf("load: %v", err)
	}

	mapping, ok := value.(map[string]any)
	if !ok {
		t.Fatalf("got %T, want a mapping", value)
	}
	if mapping["success"] != true {
		t.Errorf("success is %v, want true", mapping["success"])
	}
}

// COVERS: FR-2.5a | positive
func TestTheReaderIsHandedThePathAndNothingTouchesDisk(t *testing.T) {
	reader := &stubReader{data: []byte(validEnvelope)}

	if _, err := wrench.LoadFormattedFile("nowhere/output.yaml", wrench.EnvelopeSchema, wrench.YAML, reader); err != nil {
		t.Fatalf("load: %v", err)
	}

	if reader.sawPath != "nowhere/output.yaml" {
		t.Errorf("reader saw %q, want the path it was given", reader.sawPath)
	}
}

// COVERS: FR-2.3 | negative
func TestACallWithNoSchemaIsRefused(t *testing.T) {
	reader := &stubReader{data: []byte(validEnvelope)}

	_, loadErr := wrench.LoadFormattedFile("output.yaml", nil, wrench.YAML, reader)
	if !errors.Is(loadErr, wrench.ErrNoSchema) {
		t.Errorf("load with no schema gave %v, want ErrNoSchema", loadErr)
	}

	saveErr := wrench.SaveFormattedFile(map[string]any{"success": true}, "output.yaml", nil, wrench.YAML, &stubWriter{})
	if !errors.Is(saveErr, wrench.ErrNoSchema) {
		t.Errorf("save with no schema gave %v, want ErrNoSchema", saveErr)
	}
}

// COVERS: FR-2.6 | negative
func TestAFailureSaysWhichStepFailed(t *testing.T) {
	t.Run("the parser could not load it", func(t *testing.T) {
		reader := &stubReader{data: []byte("success: [unterminated\n")}

		_, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, reader)

		var parseErr *wrench.ParseError
		if !errors.As(err, &parseErr) {
			t.Fatalf("got %T (%v), want a ParseError", err, err)
		}
		var validationErr *wrench.ValidationError
		if errors.As(err, &validationErr) {
			t.Error("a parse failure also reports as a validation failure")
		}
	})

	t.Run("it parsed and does not match the schema", func(t *testing.T) {
		reader := &stubReader{data: []byte("success: \"yes\"\n")}

		_, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, reader)

		var validationErr *wrench.ValidationError
		if !errors.As(err, &validationErr) {
			t.Fatalf("got %T (%v), want a ValidationError", err, err)
		}
	})

	t.Run("it could not be read at all", func(t *testing.T) {
		reader := &stubReader{err: os.ErrNotExist}

		_, err := wrench.LoadFormattedFile("gone.yaml", wrench.EnvelopeSchema, wrench.YAML, reader)

		var readErr *wrench.ReadError
		if !errors.As(err, &readErr) {
			t.Fatalf("got %T (%v), want a ReadError", err, err)
		}
		if !errors.Is(err, os.ErrNotExist) {
			t.Error("the underlying cause did not survive wrapping")
		}
	})
}

// COVERS: FR-2.4 | negative
func TestSaveRefusesAStructureItWouldNotReadBack(t *testing.T) {
	writer := &stubWriter{}

	err := wrench.SaveFormattedFile(map[string]any{"success": "yes"}, "output.yaml", wrench.EnvelopeSchema, wrench.YAML, writer)

	var validationErr *wrench.ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("got %T (%v), want a ValidationError", err, err)
	}
	if writer.data != nil {
		t.Error("the writer was called despite validation failing")
	}
}

// COVERS: FR-2.4, FR-4.3 | positive
func TestSaveWritesCanonicalForm(t *testing.T) {
	writer := &stubWriter{}
	value := map[string]any{"success": false, "reasons": []any{
		map[string]any{"kind": "tool-findings", "message": "two problems"},
	}}

	if err := wrench.SaveFormattedFile(value, "output.yaml", wrench.EnvelopeSchema, wrench.YAML, writer); err != nil {
		t.Fatalf("save: %v", err)
	}

	want := "\"reasons\":\n  - \"kind\": \"tool-findings\"\n    \"message\": \"two problems\"\n\"success\": false\n"
	if string(writer.data) != want {
		t.Errorf("wrote\n%s\nwant\n%s", writer.data, want)
	}
}

// COVERS: FR-2.5, FR-2.7 | positive
func TestCodecAndIOAreIndependent(t *testing.T) {
	// The same codec with two different readers, and the same reader with a
	// schema it does not satisfy. Neither combination needs a function of its
	// own, which is what declaring them separately buys.
	first := &stubReader{data: []byte(validEnvelope)}
	second := &stubReader{data: []byte("success: false\nreasons:\n  - kind: k\n    message: m\n")}

	for name, reader := range map[string]*stubReader{"first": first, "second": second} {
		if _, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, reader); err != nil {
			t.Errorf("%s reader: %v", name, err)
		}
	}
}

// COVERS: FR-3.1, FR-3.2 | positive
func TestBothShippedSchemasAreUsable(t *testing.T) {
	jig := "tasks:\n  - name: build\n    command: go build ./...\n"

	if _, err := wrench.LoadFormattedFile("bolt.go.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(jig)}); err != nil {
		t.Errorf("jig schema rejected a valid jig: %v", err)
	}
	if _, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte(validEnvelope)}); err != nil {
		t.Errorf("envelope schema rejected a valid envelope: %v", err)
	}
}

// COVERS: FR-1.3, FR-2.3 | negative
func TestTheWrongSchemaIsNotDetected(t *testing.T) {
	// FR-2.3 says the signature compels a schema and not the right one. An
	// envelope handed the jig schema fails, and it fails as a validation
	// error rather than as anything that noticed the mix-up.
	_, err := wrench.LoadFormattedFile("output.yaml", wrench.JigSchema, wrench.YAML, &stubReader{data: []byte(validEnvelope)})

	var validationErr *wrench.ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("got %T (%v), want a plain ValidationError", err, err)
	}
}

// COVERS: FR-3.3 | property
func TestValidationIsIndifferentToSerialisation(t *testing.T) {
	// The same structure written two ways validates the same, because the
	// schema applies to what the parser produced and not to the text.
	block := "success: false\nreasons:\n  - kind: k\n    message: m\n"
	flow := "{success: false, reasons: [{kind: k, message: m}]}\n"

	for name, text := range map[string]string{"block": block, "flow": flow} {
		if _, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte(text)}); err != nil {
			t.Errorf("%s style: %v", name, err)
		}
	}
}

// COVERS: FR-3.4 | edge
func TestASchemaChecksShapeAndNotMeaning(t *testing.T) {
	// A reason whose message is the empty string is the right type and says
	// nothing. Validation passes it, which is the limit the row states.
	envelope := "success: false\nreasons:\n  - kind: k\n    message: \"\"\n"

	if _, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte(envelope)}); err != nil {
		t.Errorf("a well-shaped but meaningless envelope was refused: %v", err)
	}
}

// COVERS: FR-1.4 | negative
func TestAnEnvelopeMissingSuccessIsRefused(t *testing.T) {
	_, err := wrench.LoadFormattedFile("output.yaml", wrench.EnvelopeSchema, wrench.YAML, &stubReader{data: []byte("reasons: []\n")})

	var validationErr *wrench.ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("got %T (%v), want a ValidationError", err, err)
	}
	if !strings.Contains(err.Error(), "success") {
		t.Errorf("the error does not name the missing key: %v", err)
	}
}

// COVERS: FR-6.3, FR-2.8 | positive
func TestLocalFileWritesAtomically(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "output.yaml")

	if err := os.WriteFile(path, []byte("previous\n"), 0o644); err != nil {
		t.Fatalf("seeding: %v", err)
	}
	if err := wrench.LocalFile.Write(path, []byte("next\n")); err != nil {
		t.Fatalf("write: %v", err)
	}

	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("reading back: %v", err)
	}
	if string(got) != "next\n" {
		t.Errorf("contents are %q, want the new bytes", got)
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("listing: %v", err)
	}
	if len(entries) != 1 {
		t.Errorf("directory holds %d files, want only the target; a temporary was left behind", len(entries))
	}
}

// COVERS: FR-6.3 | negative
func TestAFailedWriteLeavesNoTemporaryBehind(t *testing.T) {
	dir := t.TempDir()
	// A path whose parent is a file, not a directory, so the temporary cannot
	// be created and the write fails before it starts.
	notADir := filepath.Join(dir, "file")
	if err := os.WriteFile(notADir, nil, 0o644); err != nil {
		t.Fatalf("seeding: %v", err)
	}

	err := wrench.LocalFile.Write(filepath.Join(notADir, "output.yaml"), []byte("x\n"))
	if err == nil {
		t.Fatal("writing under a file succeeded, which cannot be right")
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("listing: %v", err)
	}
	if len(entries) != 1 {
		t.Errorf("directory holds %d entries, want only the seeded file", len(entries))
	}
}

// COVERS: FR-6.3 | edge
func TestAWrittenFileIsReadableByItsConsumers(t *testing.T) {
	// os.CreateTemp makes a file only its owner can read. Evidence meant to be
	// handed around has to survive being handed around.
	path := filepath.Join(t.TempDir(), "output.yaml")
	if err := wrench.LocalFile.Write(path, []byte("success: true\n")); err != nil {
		t.Fatalf("write: %v", err)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o644 {
		t.Errorf("mode is %o, want 644", perm)
	}
}

// COVERS: FR-2.1, FR-6.3 | positive
func TestRoundTripThroughTheRealFilesystem(t *testing.T) {
	path := filepath.Join(t.TempDir(), "output.yaml")
	value := map[string]any{"success": true, "metadata": map[string]any{"statistics": map[string]any{"checked": 12}}}

	if err := wrench.SaveFormattedFile(value, path, wrench.EnvelopeSchema, wrench.YAML, wrench.LocalFile); err != nil {
		t.Fatalf("save: %v", err)
	}

	back, err := wrench.LoadFormattedFile(path, wrench.EnvelopeSchema, wrench.YAML, wrench.LocalFile)
	if err != nil {
		t.Fatalf("load: %v", err)
	}

	mapping, ok := back.(map[string]any)
	if !ok {
		t.Fatalf("got %T, want a mapping", back)
	}
	if mapping["success"] != true {
		t.Errorf("success came back as %v", mapping["success"])
	}
	stats := mapping["metadata"].(map[string]any)["statistics"].(map[string]any)
	if stats["checked"] != 12 {
		t.Errorf("checked came back as %v (%T), want 12", stats["checked"], stats["checked"])
	}
}
