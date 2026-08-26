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
// atomic and defeats the point.
//
// It creates no directories. A path whose parent is missing is an error, and
// deciding that a directory should exist belongs to whoever chose the path.
var LocalFile = localFile{}

type localFile struct{}

func (localFile) Read(path string) ([]byte, error) {
	return os.ReadFile(path)
}

func (localFile) Write(path string, data []byte) (err error) {
	dir := filepath.Dir(path)

	temp, err := os.CreateTemp(dir, "."+filepath.Base(path)+".*")
	if err != nil {
		return err
	}
	name := temp.Name()

	// Until the rename lands, the temporary is litter. Any path out of here
	// that is not the successful one takes it with us.
	defer func() {
		if err != nil {
			temp.Close()
			os.Remove(name)
		}
	}()

	if _, err = temp.Write(data); err != nil {
		return err
	}
	if err = temp.Sync(); err != nil {
		return err
	}
	if err = temp.Close(); err != nil {
		return err
	}
	if err = os.Chmod(name, fileMode); err != nil {
		return err
	}
	if err = os.Rename(name, path); err != nil {
		return fmt.Errorf("renaming %s into place: %w", name, err)
	}

	return nil
}
