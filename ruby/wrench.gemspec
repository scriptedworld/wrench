# frozen_string_literal: true

Gem::Specification.new do |spec|
  spec.name = "wrench"
  spec.version = "0.4.0"
  spec.summary = "Reads, writes and validates the form of structured files."
  spec.description = <<~TEXT.strip
    The Ruby pack of wrench. Two calls handle every file: load_formatted_file
    reads, decodes and validates; save_formatted_file validates, encodes and
    writes. Two codecs ship, YAML and JSON, each emitting through its library
    with the adapters that preserve meaning rather than layout.
  TEXT
  spec.authors = ["J W"]
  spec.license = "Apache-2.0"
  spec.required_ruby_version = ">= 3.2"

  spec.files = Dir["lib/**/*.rb", "LICENSE", "NOTICE"]
  spec.require_paths = ["lib"]

  # The JSON Schema binding, chosen in
  # docs/DECISIONS/which-json-schema-library-each-pack-binds.md. Each pack binds
  # its language's established implementation rather than implementing JSON
  # Schema itself, FR-5.2.
  spec.add_dependency "json_schemer", "~> 2.5"

  # psych and json are both in the standard library and are not declared. They
  # are the emitters, and the pack adds only the four adapters on top of them.

  spec.metadata = {
    "source_code_uri" => "https://github.com/scriptedworld/wrench",
    "rubygems_mfa_required" => "true"
  }
end
