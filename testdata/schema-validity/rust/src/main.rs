//! Asks the Rust pack whether each file is a valid schema.
//!
//! ```text
//! wrench-schema-validity-driver FILE...
//! ```
//!
//! One line per file, `ok NAME` or `INVALID NAME: reason`, which is what
//! `bin/test-schema-validity.py` reads. The exit status is not what it reads.

use std::path::Path;
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut refused = 0;
    for arg in std::env::args().skip(1) {
        let name = Path::new(&arg)
            .file_name()
            .map_or_else(|| arg.clone(), |n| n.to_string_lossy().into_owned());
        let text = match std::fs::read_to_string(&arg) {
            Ok(text) => text,
            Err(error) => {
                eprintln!("{arg}: {error}");
                return ExitCode::from(2);
            }
        };
        match wrench::compile_schema(&name, &text) {
            Ok(_) => println!("ok {name}"),
            Err(error) => {
                refused += 1;
                let first = error.to_string();
                println!("INVALID {name}: {}", first.lines().next().unwrap_or(""));
            }
        }
    }
    if refused > 0 {
        ExitCode::from(1)
    } else {
        ExitCode::SUCCESS
    }
}
