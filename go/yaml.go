package wrench

import (
	"bytes"
	"fmt"
	"math"
	"sort"
	"strconv"
	"time"

	yaml "go.yaml.in/yaml/v3"
)

// canonicalIndent is two spaces. One indent width everywhere, so two results
// differ by the lines that changed and nothing else.
const canonicalIndent = 2

// YAML is the YAML codec. It decodes into maps, lists and scalars, and encodes
// in canonical form: block style, one key to a line, a scalar quoted exactly
// when it is meant to be a string, booleans and numbers bare.
//
// Quoting marks intent. `no`, `1.20` and `null` survive a round trip as the
// strings they were, because they are written back quoted, and a boolean stays
// a boolean because it is not.
var YAML Codec = yamlCodec{}

type yamlCodec struct{}

// Decode turns YAML bytes into maps, lists and scalars.
//
// The YAML library's own error type does not cross this boundary: a consumer
// should not have to know which parser wrench binds in order to recognise a
// parse failure. The cause is kept and reachable through errors.Unwrap.
func (yamlCodec) Decode(data []byte) (any, error) {
	var raw any
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, &ParseError{Err: err}
	}
	value, err := normalise(raw)
	if err != nil {
		return nil, &ParseError{Err: err}
	}
	return value, nil
}

func (yamlCodec) Encode(value any) ([]byte, error) {
	node, err := canonicalNode(value)
	if err != nil {
		return nil, &EncodeError{Err: err}
	}

	var buf bytes.Buffer
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(canonicalIndent)
	if err := enc.Encode(node); err != nil {
		return nil, &EncodeError{Err: err}
	}
	if err := enc.Close(); err != nil {
		return nil, &EncodeError{Err: err}
	}
	return buf.Bytes(), nil
}

// normalise turns what the YAML parser produced into the shape a JSON Schema
// validator expects: string-keyed maps, lists, and scalars. A mapping with a
// key that is not a string has no JSON equivalent and is refused rather than
// coerced, because coercing invents a document nobody wrote.
//
// A TIMESTAMP IS THE ONE VALUE THAT IS COERCED, and it is the exception that
// proves the rule. YAML has a native timestamp type and JSON does not, so an
// unquoted 2026-01-01 decoded to a time.Time and the structure stopped being the
// maps, lists and JSON scalars everything downstream assumes. It reached the
// validator, which has no type for it, and the save call then refused to write
// back a file the load call had just read.
//
// RFC 3339 is lossless for the value and is what the timestamp was written as,
// so the string carries everything the time.Time did. Refusing instead would
// mean wrench cannot read an ordinary YAML file, and leaving it alone is what
// broke the round trip.
func normalise(value any) (any, error) {
	switch v := value.(type) {
	case time.Time:
		return v.Format(time.RFC3339), nil
	case uint64:
		// THE ONE BAND WHERE GO KEPT AN EXACT INTEGER AND THE OTHER PACKS DID
		// NOT. go-yaml reaches for uint64 when a positive integer will not fit
		// int64, so values in (int64max, uint64max] arrived here exact while
		// anything larger, and anything negative past the boundary, had already
		// become a float64. Go's own JSON codec widens the whole band.
		//
		// Past int64 a number widens to a float in every pack and every codec,
		// and the widening is visible: 18446744073709551615 comes back spelled
		// 18446744073709552000.0 rather than as a different exact integer.
		// docs/DECISIONS/parity-is-reached-by-widening-never-by-refusing.md
		if v > math.MaxInt64 {
			return float64(v), nil
		}
		return int64(v), nil
	case map[string]any:
		return normaliseMap(v)
	case map[any]any:
		converted := make(map[string]any, len(v))
		for key, item := range v {
			name, ok := key.(string)
			if !ok {
				return nil, fmt.Errorf("mapping key %v is %T, not a string", key, key)
			}
			converted[name] = item
		}
		return normaliseMap(converted)
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			normalised, err := normalise(item)
			if err != nil {
				return nil, err
			}
			out[i] = normalised
		}
		return out, nil
	default:
		return value, nil
	}
}

func normaliseMap(in map[string]any) (any, error) {
	out := make(map[string]any, len(in))
	for name, item := range in {
		normalised, err := normalise(item)
		if err != nil {
			return nil, err
		}
		out[name] = normalised
	}
	return out, nil
}

func canonicalNode(value any) (*yaml.Node, error) {
	switch v := value.(type) {
	case nil:
		return scalar("!!null", "null"), nil
	case bool:
		return scalar("!!bool", strconv.FormatBool(v)), nil
	case string:
		return quoted(v), nil
	case int:
		return scalar("!!int", strconv.FormatInt(int64(v), 10)), nil
	case int32:
		return scalar("!!int", strconv.FormatInt(int64(v), 10)), nil
	case int64:
		return scalar("!!int", strconv.FormatInt(v, 10)), nil
	case uint:
		return scalar("!!int", strconv.FormatUint(uint64(v), 10)), nil
	case uint64:
		return scalar("!!int", strconv.FormatUint(v, 10)), nil
	case float32:
		return floatNode(float64(v))
	case float64:
		return floatNode(v)
	case map[string]any:
		return mappingNode(v)
	case []any:
		return sequenceNode(v)
	default:
		return nil, fmt.Errorf("cannot write %T in canonical form", value)
	}
}

func scalar(tag, value string) *yaml.Node {
	return &yaml.Node{Kind: yaml.ScalarNode, Tag: tag, Value: value}
}

// quoted writes a string double-quoted, which is what makes its type
// unambiguous on the way back in.
func quoted(value string) *yaml.Node {
	return &yaml.Node{
		Kind:  yaml.ScalarNode,
		Tag:   "!!str",
		Value: value,
		Style: yaml.DoubleQuotedStyle,
	}
}

// floatNode writes a float in the spelling canonicalFloatText defines, which is
// the same one the JSON and TOML codecs write and the same one the other two
// packs write. FR-4.8.
func floatNode(v float64) (*yaml.Node, error) {
	text, err := canonicalFloatText(v)
	if err != nil {
		return nil, err
	}
	return scalar("!!float", text), nil
}

// mappingNode writes keys in sorted order. A Go map has no order of its own,
// so sorting is what makes two runs over the same structure produce the same
// bytes.
func mappingNode(in map[string]any) (*yaml.Node, error) {
	names := make([]string, 0, len(in))
	for name := range in {
		names = append(names, name)
	}
	sort.Strings(names)

	node := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
	for _, name := range names {
		item, err := canonicalNode(in[name])
		if err != nil {
			return nil, fmt.Errorf("at key %q: %w", name, err)
		}
		node.Content = append(node.Content, quoted(name), item)
	}
	return node, nil
}

func sequenceNode(in []any) (*yaml.Node, error) {
	node := &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
	for i, item := range in {
		element, err := canonicalNode(item)
		if err != nil {
			return nil, fmt.Errorf("at index %d: %w", i, err)
		}
		node.Content = append(node.Content, element)
	}
	return node, nil
}
