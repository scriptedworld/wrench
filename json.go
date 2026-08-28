package wrench

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// JSON is the JSON codec. Canonical form is two-space indent, one key to a
// line, and keys sorted.
//
// JSON needs no quoting rule because it already has one spelling per type,
// which is what makes it the cheaper of the formats wrench ships. Keys are
// sorted for the reason the YAML codec sorts them: a mapping has no order of
// its own, so sorting is what makes two runs over the same structure produce
// the same bytes.
//
// The form is `deno fmt` clean, and that is deliberate. bolt.wrench-quality.yaml
// already runs `deno fmt --check` over schemas/*.json, so a second answer about
// JSON layout would put two formatters in one repository. Measured 2026-08-28:
// sorted, two-space, one-key-per-line JSON passes deno fmt unchanged. deno fmt
// does not sort keys and collapses a short object onto one line, so it is a
// formatter rather than a canonical form, and matching it is one direction
// only: what wrench emits, deno accepts.
var JSON Codec = jsonCodec{}

type jsonCodec struct{}

// Decode turns JSON bytes into maps, lists and scalars.
//
// UseNumber is deliberately not set. FR-2.9 says a decoder produces JSON
// scalars, and float64 is what the other packs produce for a JSON number, so
// json.Number here would make the packs disagree about the same input.
func (jsonCodec) Decode(data []byte) (any, error) {
	var value any
	if err := json.Unmarshal(data, &value); err != nil {
		return nil, err
	}
	return value, nil
}

// Encode writes a structure in canonical form.
func (jsonCodec) Encode(value any) ([]byte, error) {
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetIndent("", "  ")
	// Go's encoder escapes <, > and & for HTML embedding, which no consumer here
	// wants and which would make the bytes differ from every other pack's.
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, fmt.Errorf("cannot write in canonical form: %w", err)
	}
	// encoding/json sorts map keys already, and appends the newline this form
	// ends with, so the buffer is the canonical bytes as it stands.
	return out.Bytes(), nil
}
