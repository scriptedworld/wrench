package wrench

import "fmt"

// A ReadError says the file could not be read at all. The reader failed before
// any question of format or conformance arose.
type ReadError struct {
	Path string
	Err  error
}

func (e *ReadError) Error() string {
	return fmt.Sprintf("wrench: reading %s: %v", e.Path, e.Err)
}

func (e *ReadError) Unwrap() error { return e.Err }

// A ParseError says the codec could not turn the bytes into a structure. The
// file is not the format it was read as.
type ParseError struct {
	Path string
	Err  error
}

func (e *ParseError) Error() string {
	return fmt.Sprintf("wrench: parsing %s: %v", e.Path, e.Err)
}

func (e *ParseError) Unwrap() error { return e.Err }

// A ValidationError says the structure parsed but does not match its schema.
// The file is the right format and the wrong shape, which is a different
// condition from ParseError with a different fix.
type ValidationError struct {
	Path string
	Err  error
}

func (e *ValidationError) Error() string {
	return fmt.Sprintf("wrench: validating %s: %v", e.Path, e.Err)
}

func (e *ValidationError) Unwrap() error { return e.Err }

// An EncodeError says a valid structure could not be rendered in the codec's
// canonical form.
type EncodeError struct {
	Path string
	Err  error
}

func (e *EncodeError) Error() string {
	return fmt.Sprintf("wrench: encoding %s: %v", e.Path, e.Err)
}

func (e *EncodeError) Unwrap() error { return e.Err }

// A WriteError says the bytes could not be put in place.
type WriteError struct {
	Path string
	Err  error
}

func (e *WriteError) Error() string {
	return fmt.Sprintf("wrench: writing %s: %v", e.Path, e.Err)
}

func (e *WriteError) Unwrap() error { return e.Err }
