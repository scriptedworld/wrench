// Command wrench-parity-driver is the Go pack's parity driver: it encodes the
// shared tree and decodes a file.
//
// Called by bin/test-cross-pack-parity.py, which owns the wire format this
// reads and writes. Two subcommands, the same two in every pack's driver:
//
//	wrench-parity-driver encode <yaml|json> <probe-in.json> <out-path>
//	wrench-parity-driver decode <yaml|json> <in-path> <probe-out.json>
//
// It calls the pack's public API and nothing else. A driver that repaired,
// rounded or reordered anything would hide the divergence the checker exists to
// find, so a value outside wrench's model is passed through as a foreign node
// for the checker to report rather than being coerced here. Go's decoders can
// hand back several integer types and a time.Time, and telling them apart is
// the point.
package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"

	wrench "github.com/scriptedworld/wrench/go"
)

const wire = 1

type node struct {
	Kind  string `json:"k"`
	Value any    `json:"v,omitempty"`
}

type envelope struct {
	Wire  int  `json:"wire"`
	Value node `json:"value"`
}

// anySchema accepts every instance, so the parity tree is judged by the codecs
// and not by a schema. The schema argument cannot be omitted (FR-2.2), so the
// permissive one is what a driver hands it.
func anySchema() (wrench.Schema, error) {
	return wrench.CompileSchema("wrench-parity-driver", strings.NewReader("{}"))
}

func codec(format string) (wrench.Codec, error) {
	switch format {
	case "yaml":
		return wrench.YAML(), nil
	case "json":
		return wrench.JSON(), nil
	}
	return nil, fmt.Errorf("unknown format %q", format)
}

func toWire(value any) node {
	switch typed := value.(type) {
	case nil:
		return node{Kind: "null"}
	case bool:
		return node{Kind: "bool", Value: strconv.FormatBool(typed)}
	case string:
		return node{Kind: "str", Value: hex.EncodeToString([]byte(typed))}
	case float64:
		return node{Kind: "float", Value: bits(typed)}
	case float32:
		return node{Kind: "float", Value: bits(float64(typed))}
	case int:
		return node{Kind: "int", Value: strconv.FormatInt(int64(typed), 10)}
	case int64:
		return node{Kind: "int", Value: strconv.FormatInt(typed, 10)}
	case uint64:
		return node{Kind: "int", Value: strconv.FormatUint(typed, 10)}
	case json.Number:
		return numberToWire(typed)
	case []any:
		return sequenceToWire(typed)
	case map[string]any:
		return mappingToWire(typed)
	}
	return node{Kind: "foreign", Value: fmt.Sprintf("%T: %#v", value, value)}
}

// A json.Number is text, so which of the two kinds it is is a question about
// the literal rather than about the value. An integer literal that will not fit
// in 64 bits is reported as a float, because that is the widening FR-4.10 asks
// for and the checker should see it as one.
func numberToWire(number json.Number) node {
	if !strings.ContainsAny(number.String(), ".eE") {
		if whole, err := strconv.ParseInt(number.String(), 10, 64); err == nil {
			return node{Kind: "int", Value: strconv.FormatInt(whole, 10)}
		}
	}
	real, err := number.Float64()
	if err != nil {
		return node{Kind: "foreign", Value: "json.Number: " + number.String()}
	}
	return node{Kind: "float", Value: bits(real)}
}

func sequenceToWire(items []any) node {
	out := make([]node, 0, len(items))
	for _, item := range items {
		out = append(out, toWire(item))
	}
	return node{Kind: "seq", Value: out}
}

func mappingToWire(mapping map[string]any) node {
	out := make([][]any, 0, len(mapping))
	for key, item := range mapping {
		out = append(out, []any{hex.EncodeToString([]byte(key)), toWire(item)})
	}
	return node{Kind: "map", Value: out}
}

func bits(real float64) string {
	return fmt.Sprintf("%016x", math.Float64bits(real))
}

func fromWire(raw map[string]any) (any, error) {
	kind, _ := raw["k"].(string)
	switch kind {
	case "null":
		return nil, nil
	case "bool":
		return raw["v"] == "true", nil
	case "int":
		return fromWireInt(raw["v"].(string))
	case "float":
		pattern, err := strconv.ParseUint(raw["v"].(string), 16, 64)
		if err != nil {
			return nil, err
		}
		return math.Float64frombits(pattern), nil
	case "str":
		decoded, err := hex.DecodeString(raw["v"].(string))
		return string(decoded), err
	case "seq":
		return fromWireSeq(raw["v"].([]any))
	case "map":
		return fromWireMap(raw["v"].([]any))
	}
	return nil, fmt.Errorf("unknown wire node kind %q", kind)
}

func fromWireInt(text string) (any, error) {
	whole, err := strconv.ParseInt(text, 10, 64)
	if err == nil {
		return whole, nil
	}
	unsigned, err := strconv.ParseUint(text, 10, 64)
	if err == nil {
		return unsigned, nil
	}
	return nil, fmt.Errorf("integer %s does not fit 64 bits, which this pack has no type for", text)
}

func fromWireSeq(items []any) (any, error) {
	out := make([]any, 0, len(items))
	for _, item := range items {
		built, err := fromWire(item.(map[string]any))
		if err != nil {
			return nil, err
		}
		out = append(out, built)
	}
	return out, nil
}

func fromWireMap(pairs []any) (any, error) {
	out := make(map[string]any, len(pairs))
	for _, pair := range pairs {
		both := pair.([]any)
		key, err := hex.DecodeString(both[0].(string))
		if err != nil {
			return nil, err
		}
		built, err := fromWire(both[1].(map[string]any))
		if err != nil {
			return nil, err
		}
		out[string(key)] = built
	}
	return out, nil
}

func encode(format, probePath, outPath string) error {
	raw, err := os.ReadFile(probePath)
	if err != nil {
		return err
	}
	var carried struct {
		Wire  int            `json:"wire"`
		Value map[string]any `json:"value"`
	}
	if err := json.Unmarshal(raw, &carried); err != nil {
		return err
	}
	if carried.Wire != wire {
		return fmt.Errorf("wire version %d is not %d", carried.Wire, wire)
	}
	value, err := fromWire(carried.Value)
	if err != nil {
		return err
	}
	schema, err := anySchema()
	if err != nil {
		return err
	}
	chosen, err := codec(format)
	if err != nil {
		return err
	}
	return wrench.SaveFormattedFile(value, outPath, schema, chosen, wrench.LocalFile())
}

func decode(format, inPath, probePath string) error {
	schema, err := anySchema()
	if err != nil {
		return err
	}
	chosen, err := codec(format)
	if err != nil {
		return err
	}
	value, err := wrench.LoadFormattedFile(inPath, schema, chosen, wrench.LocalFile())
	if err != nil {
		return err
	}
	written, err := json.Marshal(envelope{Wire: wire, Value: toWire(value)})
	if err != nil {
		return err
	}
	return os.WriteFile(probePath, written, 0o644)
}

func main() {
	args := os.Args[1:]
	if len(args) != 4 {
		fmt.Fprintf(os.Stderr, "usage: %s encode|decode yaml|json <in> <out>\n", os.Args[0])
		os.Exit(2)
	}
	var err error
	switch args[0] {
	case "encode":
		err = encode(args[1], args[2], args[3])
	case "decode":
		err = decode(args[1], args[2], args[3])
	default:
		err = fmt.Errorf("unknown action %q", args[0])
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
