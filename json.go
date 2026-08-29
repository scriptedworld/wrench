package wrench

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
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
// UseNumber is set, and the literal decides the type: a number written with a
// point or an exponent is a float, and one written without is an integer. That
// is what the Python and Rust packs already do, and encoding/json alone does
// not: it makes every number a float64, so `1` and `1.0` arrive identical and a
// whole file of integers reads back as floats.
//
// This was invisible while the encoder also spelled a whole float as `1`. Once
// FR-4.8 gave a float its decimal point in every codec, a JSON integer decoded
// here and written back came out as `1.0`, disagreeing with the other two packs
// about the same bytes. The defect was always the decode; the encoder was
// hiding it.
func (jsonCodec) Decode(data []byte) (any, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()

	var value any
	if err := decoder.Decode(&value); err != nil {
		// encoding/json's SyntaxError does not cross this boundary.
		return nil, &ParseError{Err: err}
	}
	// json.Unmarshal refuses trailing content and a Decoder does not, so the
	// check is made here rather than lost with the switch.
	if decoder.More() {
		return nil, &ParseError{Err: fmt.Errorf("unexpected content after the JSON value")}
	}
	converted, err := jsonNumbers(value)
	if err != nil {
		return nil, &ParseError{Err: err}
	}
	return converted, nil
}

// jsonNumbers turns every json.Number in a decoded structure into the int64 or
// float64 its literal spelled.
func jsonNumbers(value any) (any, error) {
	switch v := value.(type) {
	case json.Number:
		return jsonNumber(v)
	case map[string]any:
		for key, inner := range v {
			converted, err := jsonNumbers(inner)
			if err != nil {
				return nil, err
			}
			v[key] = converted
		}
		return v, nil
	case []any:
		for i, inner := range v {
			converted, err := jsonNumbers(inner)
			if err != nil {
				return nil, err
			}
			v[i] = converted
		}
		return v, nil
	default:
		return value, nil
	}
}

// jsonNumber reads one number the way its literal was written. An integer too
// large for int64 stays a float, which is the only spelling left that can hold
// it.
func jsonNumber(n json.Number) (any, error) {
	text := n.String()
	if !strings.ContainsAny(text, ".eE") {
		if i, err := strconv.ParseInt(text, 10, 64); err == nil {
			return i, nil
		}
	}
	f, err := n.Float64()
	if err != nil {
		return nil, fmt.Errorf("cannot read %s as a number: %w", text, err)
	}
	return f, nil
}

// Encode writes a structure in canonical form.
//
// Floats go through canonicalNumbers first. encoding/json writes a number the
// way ECMAScript does, which drops a whole float's decimal point entirely
// (1000000.0 becomes 1000000, read back as an integer by any pack whose JSON
// parser distinguishes the two) and switches to an exponent at 1e21. Neither
// matches what this pack's YAML and TOML codecs write, so the number formatter
// is the one part of encoding/json wrench cannot use. FR-4.8.
func (jsonCodec) Encode(value any) ([]byte, error) {
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetIndent("", "  ")
	// Go's encoder escapes <, > and & for HTML embedding, which no consumer here
	// wants and which would make the bytes differ from every other pack's.
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(canonicalNumbers(value)); err != nil {
		return nil, &EncodeError{Err: fmt.Errorf("cannot write in canonical form: %w", err)}
	}
	// encoding/json sorts map keys already, and appends the newline this form
	// ends with, so the buffer is the canonical bytes as it stands.
	return out.Bytes(), nil
}
