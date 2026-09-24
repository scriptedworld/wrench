package wrench

import (
	"fmt"
	"os"
	"path/filepath"
)

// fileMode is what a written file ends up with. os.CreateTemp makes a file
// only its owner can read, which is not what a piece of evidence meant to be
// handed around should carry.
const fileMode = 0o644

// LocalFile reads and writes files on the machine wrench is running on.
//
// Writes are atomic. The bytes go to a temporary beside the target and the
// temporary is renamed into place, so a reader sees the previous contents or
// the new ones and never a half-written file. Beside the target matters: a
// temporary elsewhere makes the move a copy across filesystems, which is not
// atomic.
//
// It creates no directories. A path whose parent is missing is an error, and
// deciding that a directory should exist belongs to whoever chose the path.
//
// A function and not a var, because an exported var is writable by any package
// that imports this one: `wrench.LocalFile = somethingElse` would redirect
// every other consumer's reads and writes in the same binary. Substitution
// belongs to the seams, which take a reader and a writer as arguments. localFile
// is an empty struct, so building it per call allocates nothing.
//
// It returns the ReadWriter interface rather than the concrete type. The
// concrete type carries only Read and Write, so exporting it would add a name
// that tells a caller nothing the interface does not, and the interface is what
// lets a consumer hold this in a field a test can substitute. FR-2.5a is that
// substitution, and a concrete field would take it away.
func LocalFile() ReadWriter { return localFile{} }

type localFile struct{}

// Read hands back the whole contents of the named file.
//
// The path is cleaned rather than confined. Reading the path the caller named
// is what a Reader is for (FR-2.5a), so there is no set of paths this refuses;
// cleaning normalises the spelling and nothing more, and deciding which paths a
// consumer may name belongs to that consumer.
// The wrap carries no words of its own. LoadFormattedFile renders this inside a
// ReadError that already says "reading <path>", and the os error names the path
// again itself, so anything added here would be the third telling. A Reader is
// not held to FR-2.11 the way the two calls are: what it returns is the seam's
// input, and classifying it is LoadFormattedFile's job.
func (localFile) Read(path string) ([]byte, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, fmt.Errorf("%w", err)
	}
	return data, nil
}

func (localFile) Write(path string, data []byte) (err error) {
	dir := filepath.Dir(path)

	temp, err := os.CreateTemp(dir, "."+filepath.Base(path)+".*")
	if err != nil {
		return fmt.Errorf("creating a temporary beside %s: %w", path, err)
	}
	name := temp.Name()

	// Until the rename lands, the temporary is litter. Any path out of here
	// that is not the successful one takes it with us.
	//
	// Neither result is checked because neither can be acted on: this runs only
	// when the write has already failed, and that failure is what the caller is
	// told about. Reporting a cleanup error instead would lose the cause.
	defer func() {
		if err != nil {
			_ = temp.Close()
			_ = os.Remove(name)
		}
	}()

	if _, err = temp.Write(data); err != nil {
		return fmt.Errorf("writing %s: %w", name, err)
	}
	if err = temp.Sync(); err != nil {
		return fmt.Errorf("flushing %s: %w", name, err)
	}
	if err = temp.Close(); err != nil {
		return fmt.Errorf("closing %s: %w", name, err)
	}
	if err = os.Chmod(name, fileMode); err != nil {
		return fmt.Errorf("setting the mode of %s: %w", name, err)
	}
	if err = os.Rename(name, path); err != nil {
		return fmt.Errorf("renaming %s into place: %w", name, err)
	}

	return nil
}
