package wrench

import "fmt"

// An Error is any failure wrench refuses. Every error this package returns
// satisfies it, so a consumer can match the family instead of naming all seven
// types.
//
// Python spells the same thing as a WrenchError base class and Rust as one enum;
// Go has neither, so the interface is what gives all three packs the same
// capability. Without it, "was this wrench's fault" needs seven errors.As calls.
type Error interface {
	error

	// Step names which step failed, as a word a consumer can match on without
	// matching the concrete type. Go and Python return the same seven words and
	// Rust returns six, having no usage step. bolt writes one into a reason's
	// kind.
	Step() string
}

// The steps, as the words a pack returns. They are the vocabulary a consumer
// matches on, so they are declared once here instead of spelled at each method.
const (
	StepRead     = "read"
	StepParse    = "parse"
	StepSchema   = "schema"
	StepValidate = "validate"
	StepEncode   = "encode"
	StepWrite    = "write"

	// StepUsage is the seventh kind: the call itself was made wrongly, before
	// any file was touched. Rust cannot produce it, because the same call does
	// not compile there.
	StepUsage = "usage"
)

// describe words a failure, omitting the path where there is none.
//
// A codec is handed bytes and a schema a structure, so neither knows which file
// it is working on. Those raise with an empty Path and the two calls fill it in
// through atPath, rather than wrapping a second time and making a consumer
// unwrap twice to reach the cause.
func describe(doing, path string, err error) string {
	if path == "" {
		return fmt.Sprintf("wrench: %s: %v", doing, err)
	}
	return fmt.Sprintf("wrench: %s %s: %v", doing, path, err)
}

// A pathFiller is one of wrench's own failures, able to say itself again with
// the path the caller named.
//
// Dispatching on the method rather than on the concrete type keeps the match to
// the error AS RETURNED. errors.As would reach through a wrapper and rebuild
// the inner failure, discarding whatever a consumer's own reader or codec had
// said around it, and FR-2.11 holds that a wrap discarding its cause is worse
// than the leak it replaced.
type pathFiller interface {
	withPath(path string) error
}

// atPath returns the same failure said with the path the caller named, and
// whether it was one of wrench's own to begin with.
//
// The two calls use it to avoid nesting a ParseError inside a ParseError: a
// codec's failure and the call's failure are one event.
func atPath(err error, path string) (error, bool) {
	filler, ours := err.(pathFiller)
	if !ours {
		return err, false
	}
	filled := filler.withPath(path)
	return filled, true
}

// A ReadError says the file could not be read at all. The reader failed before
// any question of format or conformance arose.
type ReadError struct {
	Path string
	Err  error
}

func (e *ReadError) Error() string { return describe("reading", e.Path, e.Err) }

func (e *ReadError) Unwrap() error { return e.Err }

func (e *ReadError) Step() string { return StepRead }

// withPath says the same failure with the path the caller named.
func (e *ReadError) withPath(path string) error { return &ReadError{Path: path, Err: e.Err} }

// A ParseError says the codec could not turn the bytes into a structure. The
// file is not the format it was read as.
type ParseError struct {
	Path string
	Err  error
}

func (e *ParseError) Error() string { return describe("parsing", e.Path, e.Err) }

func (e *ParseError) Unwrap() error { return e.Err }

func (e *ParseError) Step() string { return StepParse }

// withPath says the same failure with the path the caller named.
func (e *ParseError) withPath(path string) error { return &ParseError{Path: path, Err: e.Err} }

// A ValidationError says the structure parsed but does not match its schema.
// The file is the right format and the wrong shape, which is a different
// condition from ParseError with a different fix.
type ValidationError struct {
	Path string
	Err  error
}

func (e *ValidationError) Error() string { return describe("validating", e.Path, e.Err) }

func (e *ValidationError) Unwrap() error { return e.Err }

func (e *ValidationError) Step() string { return StepValidate }

// withPath says the same failure with the path the caller named.
func (e *ValidationError) withPath(path string) error {
	return &ValidationError{Path: path, Err: e.Err}
}

// An EncodeError says a valid structure could not be rendered in the codec's
// canonical form.
type EncodeError struct {
	Path string
	Err  error
}

func (e *EncodeError) Error() string { return describe("encoding", e.Path, e.Err) }

func (e *EncodeError) Unwrap() error { return e.Err }

func (e *EncodeError) Step() string { return StepEncode }

// withPath says the same failure with the path the caller named.
func (e *EncodeError) withPath(path string) error { return &EncodeError{Path: path, Err: e.Err} }

// A WriteError says the bytes could not be put in place.
type WriteError struct {
	Path string
	Err  error
}

func (e *WriteError) Error() string { return describe("writing", e.Path, e.Err) }

func (e *WriteError) Unwrap() error { return e.Err }

func (e *WriteError) Step() string { return StepWrite }

// withPath says the same failure with the path the caller named.
func (e *WriteError) withPath(path string) error { return &WriteError{Path: path, Err: e.Err} }

// A SchemaError says the schema itself will not compile.
//
// Distinct from ValidationError, which is a document failing a schema that is
// fine. This is the schema being unreadable or not valid JSON Schema, so nothing
// can be validated against it at all and the fix is to the schema rather than to
// any document.
//
// It carries the schema's Name rather than a file path, because a schema is
// compiled from a name and a document rather than read from disk.
type SchemaError struct {
	Name string
	Err  error
}

func (e *SchemaError) Error() string { return describe("compiling", e.Name, e.Err) }

func (e *SchemaError) Unwrap() error { return e.Err }

func (e *SchemaError) Step() string { return StepSchema }

// withPath returns the failure unchanged. A schema that will not compile is not
// about the document's path, so its own Name is kept rather than overwritten.
func (e *SchemaError) withPath(_ string) error { return e }
