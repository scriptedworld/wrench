package wrench

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

// canonicalFloatText is the one spelling of a float that every codec in every
// pack writes. FR-4.8.
//
// Positional decimal, never an exponent. The digits are the shortest decimal
// string that reads back as the same float64, placed with the decimal point
// where it belongs rather than moved into an `e`. A whole number keeps a ".0",
// so a float never reads back as an integer.
//
// The rule carries no threshold on purpose. Every alternative needs a magnitude
// at which the spelling changes, and that number then has to be stated in the
// contract and implemented identically in nine places. "Never" is the only
// answer with nothing to get wrong, and it is the only one a consumer parsing
// with a naive numeric pattern reads correctly: `1e+06` matched by `[0-9.]+`
// yields 1, which is how this defect was found.
//
// The cost is bounded. The longest output is a subnormal near the bottom of the
// range, at 326 characters, and the largest finite double is 311. A file
// carrying such a value is pathological in a way that reading it as 1 is not.
//
// NaN and the infinities are refused. YAML can spell them, JSON Schema cannot
// represent them, and a file no consumer in this ecosystem can validate is not
// canonical form.
// A canonicalFormError says a value has no spelling in canonical form, naming
// what was refused. FR-4.1.
//
// A type rather than a dynamic error, so errors.As reaches it and the sentence
// stays one sentence: a sentinel wrapped with fmt.Errorf would render the
// general statement after the specific one.
type canonicalFormError struct {
	what string
}

func (e *canonicalFormError) Error() string {
	return "cannot write " + e.what + " in canonical form"
}

func canonicalFloatText(v float64) (string, error) {
	if math.IsNaN(v) {
		return "", &canonicalFormError{what: "NaN"}
	}
	if math.IsInf(v, 0) {
		return "", &canonicalFormError{what: fmt.Sprintf("%v", v)}
	}

	// 'f' is positional and never emits an exponent; -1 asks for the fewest
	// digits that round-trip. 'g', which every pack reached for first, chooses
	// between the two spellings on a threshold of its own.
	text := strconv.FormatFloat(v, 'f', -1, 64)
	if !strings.Contains(text, ".") {
		text += ".0"
	}
	return text, nil
}

// canonicalFloat marshals as canonicalFloatText, so the JSON codec can hand
// encoding/json a value it will write in wrench's spelling rather than in the
// one its own number formatter chooses.
type canonicalFloat float64

// MarshalJSON writes the canonical spelling as a bare JSON number.
func (f canonicalFloat) MarshalJSON() ([]byte, error) {
	text, err := canonicalFloatText(float64(f))
	if err != nil {
		return nil, err
	}
	return []byte(text), nil
}

// canonicalNumbers rebuilds a structure with every float replaced by one that
// marshals canonically, and refuses what the YAML codec refuses.
//
// encoding/json writes more than the value model holds: it spells an integer
// map key as a string and a struct as an object, so a document nobody wrote
// would come out of the JSON codec while the YAML codec refused the same
// value. FR-2.9 allows maps with string keys, lists and the JSON scalars, and
// this is the one place the JSON codec sees the value before encoding/json does.
func canonicalNumbers(value any) (any, error) {
	switch v := value.(type) {
	case nil, bool, string, int, int32, int64, uint, uint64:
		return value, nil
	case float64:
		return canonicalFloat(v), nil
	case float32:
		return canonicalFloat(float64(v)), nil
	case map[string]any:
		out := make(map[string]any, len(v))
		for key, inner := range v {
			converted, err := canonicalNumbers(inner)
			if err != nil {
				return nil, fmt.Errorf("at key %q: %w", key, err)
			}
			out[key] = converted
		}
		return out, nil
	case []any:
		out := make([]any, len(v))
		for i, inner := range v {
			converted, err := canonicalNumbers(inner)
			if err != nil {
				return nil, fmt.Errorf("at index %d: %w", i, err)
			}
			out[i] = converted
		}
		return out, nil
	default:
		return nil, &canonicalFormError{what: fmt.Sprintf("%T", value)}
	}
}
