// Package wrench reads, writes and validates the form of the ecosystem's
// structured files.
//
// File handling is two calls. Validation sits in the signature, so nothing
// reads or writes without naming what the file must conform to. The codec is
// the format and the reader or writer is the IO, declared separately, which
// puts the IO boundary wholly outside the call.
//
// The contract names these calls load_formatted_file and save_formatted_file.
// A pack spells them the way its own language spells things, so the Go pack
// exports LoadFormattedFile and SaveFormattedFile. What the packs share is
// behaviour, not spelling.
package wrench

// A usageError is a call made wrongly, before any file was touched. It is a
// seventh kind beside the six steps because it is not one of them: nothing was
// read, parsed or validated.
//
// These stay sentinel values so errors.Is keeps working, and gain Step so
// errors.As reaches them through the Error interface. Before this they were
// plain errors.New values, so a consumer catching "any wrench failure" missed
// exactly the failures that mean it called wrench wrong.
type usageError struct{ message string }

func (e *usageError) Error() string { return e.message }

func (e *usageError) Step() string { return StepUsage }

// ErrNoSchema is returned when a call is handed no schema. The signature
// compels one; nil is the one way round that, and it is refused here so
// FR-2.3's guarantee holds in a language where any interface can be nil.
var ErrNoSchema error = &usageError{"wrench: no schema given"}

// ErrNoCodec is returned when a call is handed no codec.
var ErrNoCodec error = &usageError{"wrench: no codec given"}

// ErrNoReader is returned when a load is handed no reader.
var ErrNoReader error = &usageError{"wrench: no reader given"}

// ErrNoWriter is returned when a save is handed no writer.
var ErrNoWriter error = &usageError{"wrench: no writer given"}

// A Codec turns bytes into a structure and a structure into canonical bytes.
// It is the format, and knows nothing about where the bytes came from.
type Codec interface {
	// Decode turns a file's bytes into maps, lists and scalars.
	Decode(data []byte) (any, error)
	// Encode turns a structure into bytes in the codec's canonical form.
	Encode(value any) ([]byte, error)
}

// A Reader hands back the whole contents of a named file. It is the IO, and
// knows nothing about the format. A Reader is handed the path rather than
// bytes, so substituting one in a test exercises the validation paths against
// no filesystem at all.
type Reader interface {
	Read(path string) ([]byte, error)
}

// A Writer puts the whole contents of a named file in place.
type Writer interface {
	Write(path string, data []byte) error
}

// A Schema validates a decoded structure. It applies to the maps and lists a
// codec produced rather than to the text, so it is indifferent to how the file
// was serialised on the way in.
type Schema interface {
	Validate(value any) error
}

// LoadFormattedFile reads path through reader, decodes it with codec, and
// validates the result against schema.
//
// A failure says which step failed. ReadError, ParseError and ValidationError
// are distinct because they have distinct causes and distinct fixes.
func LoadFormattedFile(path string, schema Schema, codec Codec, reader Reader) (any, error) {
	if err := requireLoadParts(schema, codec, reader); err != nil {
		return nil, err
	}

	data, err := reader.Read(path)
	if err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return nil, filled
		}
		return nil, &ReadError{Path: path, Err: err}
	}

	value, err := codec.Decode(data)
	if err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return nil, filled
		}
		return nil, &ParseError{Path: path, Err: err}
	}

	if err := schema.Validate(value); err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return nil, filled
		}
		return nil, &ValidationError{Path: path, Err: err}
	}

	return value, nil
}

// SaveFormattedFile validates value against schema, encodes it with codec in
// canonical form, and writes it to path through writer.
//
// Validation runs before the write, so a caller cannot put down a structure
// wrench would refuse to read back.
func SaveFormattedFile(value any, path string, schema Schema, codec Codec, writer Writer) error {
	if err := requireSaveParts(schema, codec, writer); err != nil {
		return err
	}

	if err := schema.Validate(value); err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return filled
		}
		return &ValidationError{Path: path, Err: err}
	}

	data, err := codec.Encode(value)
	if err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return filled
		}
		return &EncodeError{Path: path, Err: err}
	}

	if err := writer.Write(path, data); err != nil {
		// Already wrench's, from a codec or a schema that has no path.
		// Fill it in rather than wrap a second time.
		if filled, ours := atPath(err, path); ours {
			return filled
		}
		return &WriteError{Path: path, Err: err}
	}

	return nil
}

func requireLoadParts(schema Schema, codec Codec, reader Reader) error {
	if schema == nil {
		return ErrNoSchema
	}
	if codec == nil {
		return ErrNoCodec
	}
	if reader == nil {
		return ErrNoReader
	}
	return nil
}

func requireSaveParts(schema Schema, codec Codec, writer Writer) error {
	if schema == nil {
		return ErrNoSchema
	}
	if codec == nil {
		return ErrNoCodec
	}
	if writer == nil {
		return ErrNoWriter
	}
	return nil
}
