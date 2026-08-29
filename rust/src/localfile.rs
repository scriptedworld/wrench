//! The IO boundary: bytes in and out of the machine this is running on.
//!
//! A reader is handed the PATH, not an open handle, so substituting one in a
//! test exercises the validation paths against no filesystem at all rather than
//! only replacing the parse. That is FR-2.5a and it is why these are traits.

use std::fs;
use std::io::Write as _;
use std::path::Path;

/// Where bytes come from.
pub trait Reader {
    fn read(&self, path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>>;
}

/// Where bytes go.
pub trait Writer {
    fn write(
        &self,
        path: &str,
        data: &[u8],
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>>;
}

/// The local filesystem, and nothing else ships. Everything wrench serves reads
/// and writes on the machine it is running on, and a test substitutes its own
/// reader rather than needing one shipped to do it.
pub struct LocalFileIo;

/// The one instance callers use.
pub const LOCAL_FILE: LocalFileIo = LocalFileIo;

impl Reader for LocalFileIo {
    fn read(&self, path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        Ok(fs::read(path)?)
    }
}

impl Writer for LocalFileIo {
    /// Atomic: written beside the target and renamed into place, so a reader
    /// sees the previous content or the new one and never a partial file.
    ///
    /// The temporary is created with the owner's permissions only, so it is
    /// chmodded to 0644 before the rename. Evidence has to survive being handed
    /// around, and a file only its writer can read does not.
    fn write(
        &self,
        path: &str,
        data: &[u8],
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let target = Path::new(path);
        let directory = target.parent().filter(|p| !p.as_os_str().is_empty());

        // Beside the target, so the rename stays on one filesystem. A rename
        // across devices is a copy, and a copy is not atomic.
        let temporary = match directory {
            Some(dir) => dir.join(format!(
                ".{}.wrench-tmp",
                target
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default()
            )),
            None => Path::new(&format!(".{}.wrench-tmp", path)).to_path_buf(),
        };

        let mut file = fs::File::create(&temporary)?;
        let outcome = file.write_all(data).and_then(|()| file.sync_all());
        drop(file);

        if let Err(problem) = outcome {
            let _ = fs::remove_file(&temporary);
            return Err(Box::new(problem));
        }

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt as _;
            if let Err(problem) = fs::set_permissions(&temporary, fs::Permissions::from_mode(0o644))
            {
                let _ = fs::remove_file(&temporary);
                return Err(Box::new(problem));
            }
        }

        if let Err(problem) = fs::rename(&temporary, target) {
            let _ = fs::remove_file(&temporary);
            return Err(Box::new(problem));
        }
        Ok(())
    }
}
