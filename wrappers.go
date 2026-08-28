package wrench

// Per-format wrappers over the two calls.
//
// These add no behaviour. Each supplies one argument, so validation still sits
// in the signature and the seam is unchanged in both directions.
//
// NAMED RATHER THAN INFERRED FROM THE SUFFIX. Choosing a parser by filename
// makes behaviour depend on what a file is called, so renaming one would
// silently change how it is read. FR-2.2 exists to remove exactly that
// implicitness.

// LoadYAMLFile reads a YAML file and validates it against schema.
func LoadYAMLFile(path string, schema Schema, reader Reader) (any, error) {
	return LoadFormattedFile(path, schema, YAML, reader)
}

// SaveYAMLFile validates a structure and writes it as canonical YAML.
func SaveYAMLFile(value any, path string, schema Schema, writer Writer) error {
	return SaveFormattedFile(value, path, schema, YAML, writer)
}

// LoadJSONFile reads a JSON file and validates it against schema.
func LoadJSONFile(path string, schema Schema, reader Reader) (any, error) {
	return LoadFormattedFile(path, schema, JSON, reader)
}

// SaveJSONFile validates a structure and writes it as canonical JSON.
func SaveJSONFile(value any, path string, schema Schema, writer Writer) error {
	return SaveFormattedFile(value, path, schema, JSON, writer)
}

// LoadTOMLFile reads a TOML file and validates it against schema. A native
// date, time or datetime decodes to its ISO 8601 string, which is what FR-2.9
// requires of every decoder.
func LoadTOMLFile(path string, schema Schema, reader Reader) (any, error) {
	return LoadFormattedFile(path, schema, TOML, reader)
}

// SaveTOMLFile validates a structure and writes it as canonical TOML. It
// refuses a structure containing null, which TOML cannot spell, and one that is
// not a table, which TOML has no way to be.
func SaveTOMLFile(value any, path string, schema Schema, writer Writer) error {
	return SaveFormattedFile(value, path, schema, TOML, writer)
}
