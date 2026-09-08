# frozen_string_literal: true

require "fileutils"
require "tmpdir"

require_relative "errors"

module Wrench
  # The four seams. Each argument of the two calls is one job, so a format can
  # be added without inventing a source and a source without inventing a format.
  #
  # Ruby needs no declared interface for this and one is not invented: a codec
  # is anything answering `decode` and `encode`, a reader anything answering
  # `read`. What is written down instead is the contract each promises, because
  # that is the part another pack has to agree with.
  #
  #   Codec   decode(bytes) -> value, encode(value) -> bytes
  #           The format. Knows nothing about where bytes came from.
  #           `encode` emits canonical form.
  #   Reader  read(path) -> bytes
  #           The IO on the way in. HANDED THE PATH, NOT THE BYTES.
  #   Writer  write(path, bytes)
  #           The IO on the way out. Puts the whole contents in place.
  #   Schema  validate(value)
  #           Applies to the decoded structure, not the text.
  #
  # A READER IS HANDED THE PATH RATHER THAN BYTES, FR-2.5a. Handing it bytes
  # would put the open where the caller is, and a test substituting a reader
  # would then be replacing the parse alone. Handed the path, a substituted
  # reader exercises every validation path against no filesystem at all.

  # The one reader and writer that ship, both local files, and nothing else
  # (FR-2.8). Everything wrench serves runs on the machine holding the file, and
  # a test brings its own.
  class LocalFileIO
    # The whole contents as bytes.
    def read(path)
      File.binread(path.to_s)
    rescue SystemCallError, IOError => e
      raise ReadError.new("could not read the file", cause: e, path: path)
    end

    # The bytes, in place, atomically (FR-6.3).
    #
    # They go to a temporary file BESIDE the target and are renamed over it, so
    # a concurrent reader sees the previous contents or the new ones and never a
    # half-written file. Beside rather than in a temporary directory, because a
    # rename across filesystems is a copy and stops being atomic.
    def write(path, bytes)
      target = File.expand_path(path.to_s)
      directory = File.dirname(target)
      temporary = nil
      begin
        File.open(File.join(directory, ".wrench-#{Process.pid}-#{object_id}.tmp"), "wb") do |f|
          temporary = f.path
          f.write(bytes)
          f.flush
          f.fsync
        end
        File.rename(temporary, target)
        temporary = nil
      rescue SystemCallError, IOError => e
        raise WriteError.new("could not write the file", cause: e, path: path)
      ensure
        FileUtils.rm_f(temporary) if temporary
      end
    end
  end

  # The shipped reader and writer, as one object, which is what a caller passes
  # for both seams.
  LOCAL_FILE = LocalFileIO.new
end
