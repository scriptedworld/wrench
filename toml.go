package wrench

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/BurntSushi/toml"
)

// TOML is the TOML codec.
//
// TOML is the one format wrench ships that cannot hold everything the other two
// can, so two questions were answered rather than implemented around, and both
// are answered the way the contract answers them elsewhere.
//
// A null is refused rather than substituted. TOML has no null, and FR-4.1 says a
// value with no canonical form is refused rather than guessed at. Writing "" or
// dropping the key invents a document nobody wrote.
//
// A date decodes to its ISO 8601 string. FR-2.9 says a decoder produces maps,
// lists and JSON scalars and nothing else, and the YAML codec already coerces
// its native timestamps for the same reason.
//
// A TOML document is a table. There is no top-level scalar or array in the
// format, so encoding one is refused rather than wrapped in an invented key.
//
// THE EMITTER IS WRITTEN BY HAND, for the reason the YAML emitter is: no TOML
// library produces these bytes. Measured 2026-08-28, the same structure through
// BurntSushi/toml and Python's tomli_w differed in array layout and in
// indentation under a table, so two packs each using their own library disagree
// about canonical form, which is the failure wrench exists to prevent.
var TOML Codec = tomlCodec{}

type tomlCodec struct{}

// Decode turns TOML bytes into maps, lists and scalars.
func (tomlCodec) Decode(data []byte) (any, error) {
	var value map[string]any
	if err := toml.Unmarshal(data, &value); err != nil {
		return nil, err
	}
	return tomlNormalise(value)
}

// tomlNormalise is TOML's own rather than the YAML codec's, because TOML draws
// distinctions YAML does not: a local date, a local time, a local datetime and
// an offset datetime are four types, and BurntSushi carries which one it read in
// the location name. Formatting them all as RFC3339 would turn `2026-01-01` into
// `2026-01-01T00:00:00-07:00`, which Python's tomllib does not do, so the packs
// would disagree about the same file.
func tomlNormalise(value any) (any, error) {
	switch v := value.(type) {
	case time.Time:
		return tomlTime(v), nil
	case map[string]any:
		out := make(map[string]any, len(v))
		for name, item := range v {
			normalised, err := tomlNormalise(item)
			if err != nil {
				return nil, err
			}
			out[name] = normalised
		}
		return out, nil
	case []any:
		out := make([]any, len(v))
		for index, item := range v {
			normalised, err := tomlNormalise(item)
			if err != nil {
				return nil, err
			}
			out[index] = normalised
		}
		return out, nil
	default:
		return value, nil
	}
}

// tomlTime spells a temporal value the way Python's `.isoformat()` spells the
// type tomllib produces for the same input.
func tomlTime(v time.Time) string {
	switch v.Location().String() {
	case "date-local":
		return v.Format("2006-01-02")
	case "time-local":
		return v.Format("15:04:05")
	case "Local":
		return v.Format("2006-01-02T15:04:05")
	default:
		return v.Format(time.RFC3339)
	}
}

// Encode writes a structure in canonical form: scalars first and sorted, then
// each sub-table as a [path] section, arrays inline, no indentation.
func (tomlCodec) Encode(value any) ([]byte, error) {
	table, ok := value.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("cannot write %T in canonical form: a TOML document is a table", value)
	}
	if err := refuseNull(table, ""); err != nil {
		return nil, err
	}

	var out strings.Builder
	if err := tomlTable(&out, table, nil); err != nil {
		return nil, err
	}
	return []byte(out.String()), nil
}

// tomlTable writes one table: its scalars, then its sub-tables, each sorted.
//
// Scalars first because TOML binds a bare key to the most recent [header], so a
// scalar written after a sub-table would land inside it. That is a correctness
// rule rather than a layout preference.
func tomlTable(out *strings.Builder, value map[string]any, path []string) error {
	if len(path) > 0 {
		parts := make([]string, len(path))
		for i, part := range path {
			parts[i] = tomlKey(part)
		}
		fmt.Fprintf(out, "[%s]\n", strings.Join(parts, "."))
	}

	names := make([]string, 0, len(value))
	for name := range value {
		names = append(names, name)
	}
	sort.Strings(names)

	var sections []string
	for _, name := range names {
		if _, ok := value[name].(map[string]any); ok {
			sections = append(sections, name)
			continue
		}
		if isTableArray(value[name]) {
			sections = append(sections, name)
			continue
		}
		text, err := tomlInline(value[name])
		if err != nil {
			return err
		}
		fmt.Fprintf(out, "%s = %s\n", tomlKey(name), text)
	}

	for _, name := range sections {
		deeper := append(append([]string{}, path...), name)
		if table, ok := value[name].(map[string]any); ok {
			out.WriteString("\n")
			if err := tomlTable(out, table, deeper); err != nil {
				return err
			}
			continue
		}
		// An array of tables is repeated [[path]] sections. TOML has no inline
		// form for one, so this is the only spelling available rather than a
		// choice between two.
		parts := make([]string, len(deeper))
		for i, part := range deeper {
			parts[i] = tomlKey(part)
		}
		header := strings.Join(parts, ".")
		for _, entry := range value[name].([]any) {
			fmt.Fprintf(out, "\n[[%s]]\n", header)
			if err := tomlTable(out, entry.(map[string]any), nil); err != nil {
				return err
			}
		}
	}
	return nil
}

// isTableArray reports a non-empty array whose every item is a table.
//
// Empty stays inline as `[]`, because an empty array of tables and an empty
// array of anything else are the same document and `[]` is the shorter of the
// two spellings. A mixed array is not a table array and is refused by
// tomlInline, which is where the message about it belongs.
func isTableArray(value any) bool {
	items, ok := value.([]any)
	if !ok || len(items) == 0 {
		return false
	}
	for _, item := range items {
		if _, ok := item.(map[string]any); !ok {
			return false
		}
	}
	return true
}

// tomlKey writes a key bare where TOML allows it and quoted where it does not.
func tomlKey(name string) string {
	if name == "" {
		return tomlString(name)
	}
	for _, r := range name {
		if !(r == '_' || r == '-' || ('0' <= r && r <= '9') || ('a' <= r && r <= 'z') || ('A' <= r && r <= 'Z')) {
			return tomlString(name)
		}
	}
	return name
}

// tomlInline writes a value on one line: a scalar, or an array of them.
func tomlInline(value any) (string, error) {
	switch v := value.(type) {
	case bool:
		if v {
			return "true", nil
		}
		return "false", nil
	case string:
		return tomlString(v), nil
	case int:
		return strconv.Itoa(v), nil
	case int64:
		return strconv.FormatInt(v, 10), nil
	case float64:
		return tomlFloat(v)
	case time.Time:
		return tomlString(tomlTime(v)), nil
	case []any:
		parts := make([]string, len(v))
		for i, item := range v {
			text, err := tomlInline(item)
			if err != nil {
				return "", err
			}
			parts[i] = text
		}
		return "[" + strings.Join(parts, ", ") + "]", nil
	case map[string]any:
		// An inline table would be a second way to spell a sub-table, and two
		// spellings of one thing is what canonical form exists to remove.
		return "", fmt.Errorf("cannot write a table inline in canonical form")
	default:
		return "", fmt.Errorf("cannot write %T in canonical form", value)
	}
}

// tomlFloat writes the spelling canonicalFloatText defines, in step with the
// YAML and JSON codecs: a float spelled differently per format is the same
// defect as a float that reads back as an integer.
func tomlFloat(v float64) (string, error) {
	return canonicalFloatText(v)
}

// tomlString writes a basic string, escaped the way TOML spells escapes.
func tomlString(value string) string {
	replacer := strings.NewReplacer(
		`\`, `\\`,
		`"`, `\"`,
		"\n", `\n`,
		"\t", `\t`,
		"\r", `\r`,
	)
	return `"` + replacer.Replace(value) + `"`
}

// refuseNull walks the structure and refuses a nil anywhere in it, naming where
// it sits. Checked before encoding rather than left to the emitter, because a
// caller with a nested document needs to find the key.
func refuseNull(value any, where string) error {
	switch v := value.(type) {
	case nil:
		at := ""
		if where != "" {
			at = " at " + where
		}
		return fmt.Errorf("cannot write null in canonical form%s: TOML has no null", at)
	case map[string]any:
		names := make([]string, 0, len(v))
		for name := range v {
			names = append(names, name)
		}
		sort.Strings(names)
		for _, name := range names {
			path := name
			if where != "" {
				path = where + "." + name
			}
			if err := refuseNull(v[name], path); err != nil {
				return err
			}
		}
	case []any:
		for index, item := range v {
			if err := refuseNull(item, fmt.Sprintf("%s[%d]", where, index)); err != nil {
				return err
			}
		}
	}
	return nil
}
