# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "tmpdir"

require "wrench"

# The Ruby pack's suite.
#
# Nothing here is mocked. A reader is handed a path rather than bytes precisely
# so a test can substitute one without a filesystem, and where a file is wanted
# the test writes a real one into a temporary directory.
class TestWrench < Minitest::Test
  # The shared parity tree, the same 53 keys every pack is measured against, so
  # a divergence here is a divergence from the other packs rather than from a
  # fixture only this pack has.
  #
  # A COPY, BESIDE THE SUITE, AND NOT THE ONE IN .ephemera. It was read from
  # there first, and `.gitignore` holds that directory out, so `git archive HEAD`
  # carried this file and not the tree it loads: the suite passed here and could
  # not run in a clone. A test fixture is part of the pack.
  TREE = JSON.parse(File.read(File.join(__dir__, "parity-tree.json"))).freeze

  ANY = Wrench.compile_schema("anything", {}).freeze

  def with_file(name = "doc.yaml")
    Dir.mktmpdir { |dir| yield File.join(dir, name) }
  end

  # COVERS: FR-2.1 | positive
  def test_the_two_calls_round_trip_a_document
    with_file do |path|
      Wrench.save_yaml_file(TREE, path, ANY, Wrench::LOCAL_FILE)
      assert_equal TREE, Wrench.load_yaml_file(path, ANY, Wrench::LOCAL_FILE)
    end
  end

  # COVERS: FR-2.1 | positive
  def test_json_round_trips_the_same_tree
    with_file("doc.json") do |path|
      Wrench.save_json_file(TREE, path, ANY, Wrench::LOCAL_FILE)
      assert_equal TREE, Wrench.load_json_file(path, ANY, Wrench::LOCAL_FILE)
    end
  end

  # COVERS: FR-4.8 | property
  def test_a_float_is_positional_and_never_an_exponent
    {
      1.0 => "1.0", 1.2 => "1.2", 1e20 => "100000000000000000000.0",
      1e-7 => "0.0000001", -0.0 => "-0.0", 0.1 => "0.1"
    }.each do |value, want|
      assert_equal want, Wrench::FloatText.canonical(value), "spelling #{value}"
    end
  end

  # COVERS: FR-4.8 | negative
  def test_a_float_with_no_canonical_form_is_refused
    [Float::NAN, Float::INFINITY, -Float::INFINITY].each do |value|
      assert_raises(ArgumentError) { Wrench::FloatText.canonical(value) }
    end
  end

  # COVERS: FR-4.1 | property
  def test_a_string_keeps_its_type_through_a_round_trip
    # The point of quoting every string. Unquoted, a YAML reader takes each of
    # these for something else, and `1.20` loses its trailing zero as a number.
    tricky = { "a" => "no", "b" => "yes", "c" => "on", "d" => "null",
               "e" => "~", "f" => "1.20", "g" => "007", "h" => "12:30:45" }
    back = Wrench::YAML.decode(Wrench::YAML.encode(tricky))
    assert_equal tricky, back
  end

  # COVERS: FR-4.1 | property
  def test_a_numeric_key_stays_a_string
    # Sharper than the value case: to a YAML 1.1 reader an unquoted `10:` is an
    # integer key, so the key is quoted too.
    back = Wrench::YAML.decode(Wrench::YAML.encode({ "10" => 1, "2" => 2 }))
    assert_equal({ "10" => 1, "2" => 2 }, back)
  end

  # COVERS: FR-4.3 | property
  def test_keys_are_sorted_so_two_runs_agree
    one = Wrench::YAML.encode({ "z" => 1, "a" => 2, "m" => 3 })
    two = Wrench::YAML.encode({ "m" => 3, "a" => 2, "z" => 1 })
    assert_equal one, two
    assert_equal %w["a" "m" "z"], one.scan(/^"(\w)"/).flatten.map { |k| %("#{k}") }
  end

  # COVERS: FR-4.9 | property
  def test_control_characters_survive_a_round_trip
    # A raw control character in a quoted scalar is refused by a strict reader
    # and folded by a lenient one, so escaping is the only answer that keeps
    # every value writable.
    tricky = (0..0x1F).to_a.push(0x7F, 0x85, 0x2028, 0x2029, 0xFEFF)
                      .to_h { |cp| [format("cp%04X", cp), "a#{cp.chr(Encoding::UTF_8)}b"] }
    assert_equal tricky, Wrench::YAML.decode(Wrench::YAML.encode(tricky))
  end

  # COVERS: FR-2.11 | property
  def test_every_failure_is_one_family_with_a_step
    assert_equal %w[read parse schema validate encode write usage], Wrench::STEPS
    {
      Wrench::ReadError => "read", Wrench::ParseError => "parse",
      Wrench::SchemaError => "schema", Wrench::ValidationError => "validate",
      Wrench::EncodeError => "encode", Wrench::WriteError => "write",
      Wrench::UsageError => "usage"
    }.each do |kind, step|
      assert_equal step, kind.new("x").step
      assert_kind_of Wrench::Error, kind.new("x")
    end
  end

  # COVERS: FR-2.11 | property
  def test_no_failure_subclasses_a_narrower_ruby_error
    # A validation failure can be a wrong type, which `'three' is not of type
    # 'integer'` demonstrates, and TypeError and ArgumentError each exclude half
    # of what a schema refuses.
    [Wrench::ValidationError, Wrench::ParseError, Wrench::EncodeError].each do |kind|
      refute_operator kind, :<, TypeError
      refute_operator kind, :<, ArgumentError
    end
  end

  # COVERS: FR-2.2 | negative
  def test_a_missing_seam_is_usage_and_touches_no_file
    with_file do |path|
      error = assert_raises(Wrench::UsageError) do
        Wrench.load_yaml_file(path, nil, Wrench::LOCAL_FILE)
      end
      assert_equal "usage", error.step
      refute File.exist?(path), "nothing should have been written"
    end
  end

  # COVERS: FR-2.5a | property
  def test_a_reader_is_handed_the_path_and_can_be_substituted
    # No filesystem at all. This is what handing the reader a path rather than
    # bytes buys: a substituted reader exercises decode and validate together.
    seen = []
    reader = Object.new
    reader.define_singleton_method(:read) { |p| seen << p and '{"k": 1}' }
    assert_equal({ "k" => 1 }, Wrench.load_json_file("some/path", ANY, reader))
    assert_equal ["some/path"], seen
  end

  # COVERS: FR-2.4 | negative
  def test_a_structure_the_schema_refuses_is_not_written
    schema = Wrench.compile_schema("needs a name", {
                                     "type" => "object", "required" => ["name"]
                                   })
    with_file do |path|
      error = assert_raises(Wrench::ValidationError) do
        Wrench.save_yaml_file({ "other" => 1 }, path, schema, Wrench::LOCAL_FILE)
      end
      assert_equal "validate", error.step
      refute File.exist?(path), "a refused structure must not reach the file"
    end
  end

  # COVERS: FR-6.3 | property
  def test_a_write_replaces_the_previous_contents_whole
    with_file do |path|
      Wrench.save_yaml_file({ "a" => 1 }, path, ANY, Wrench::LOCAL_FILE)
      Wrench.save_yaml_file({ "b" => 2 }, path, ANY, Wrench::LOCAL_FILE)
      assert_equal({ "b" => 2 }, Wrench.load_yaml_file(path, ANY, Wrench::LOCAL_FILE))
      assert_empty Dir.glob(File.join(File.dirname(path), ".wrench-*"))
    end
  end

  # COVERS: FR-2.11 | property
  def test_an_error_names_the_file_it_happened_to
    with_file do |path|
      File.write(path, "{ this is not yaml or json")
      error = assert_raises(Wrench::Error) do
        Wrench.load_json_file(path, ANY, Wrench::LOCAL_FILE)
      end
      assert_equal "parse", error.step
      assert_includes error.message, path
    end
  end

  # COVERS: FR-1.2 | negative
  def test_a_key_that_is_not_a_string_is_refused
    [Wrench::YAML, Wrench::JSON].each do |codec|
      assert_raises(Wrench::EncodeError) { codec.encode({ 1 => "x" }) }
    end
  end
end
