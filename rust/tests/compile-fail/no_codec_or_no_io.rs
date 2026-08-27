//! FR-2.2: nothing reads or writes without naming what the file must conform
//! to, the codec that spells it and the IO that moves the bytes.
//!
//! Go and Python pass nil and None here and assert a refusal at run time. This
//! pack cannot, because the parameters are `&dyn` references and Rust has no
//! null to pass. The four calls below are rejected by the compiler instead,
//! which is the same rule held one stage earlier.

use wrench::{load_formatted_file, save_formatted_file, Reader, Writer, ENVELOPE_SCHEMA, YAML};

struct Io;

impl Reader for Io {
    fn read(&self, _path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        Ok(Vec::new())
    }
}

impl Writer for Io {
    fn write(
        &self,
        _path: &str,
        _data: &[u8],
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        Ok(())
    }
}

fn main() {
    let io = Io;
    let value = serde_json::Value::Null;

    // Loading with no codec named at all.
    let _ = load_formatted_file("f.yaml", &ENVELOPE_SCHEMA, &io);

    // Loading with the codec standing in for the reader. A codec is not an IO
    // boundary, and declaring them separately is what makes that checkable.
    let _ = load_formatted_file("f.yaml", &ENVELOPE_SCHEMA, &YAML, &YAML);

    // Saving with no writer named at all.
    let _ = save_formatted_file(&value, "f.yaml", &ENVELOPE_SCHEMA, &YAML);

    // Saving with the codec standing in for the writer.
    let _ = save_formatted_file(&value, "f.yaml", &ENVELOPE_SCHEMA, &YAML, &YAML);
}
