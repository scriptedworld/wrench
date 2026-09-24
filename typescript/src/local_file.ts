/**
 * The one reader and writer that ship, both local files, and nothing else
 * (FR-2.8). Everything wrench serves runs on the machine holding the file, and
 * a test brings its own.
 *
 * SYNCHRONOUS, and that is the contract rather than an oversight. The two calls
 * return a value in every pack, so making this half asynchronous would make
 * `loadFormattedFile` return a promise and stop it being the same call. A
 * consumer wanting the work off the main thread has the seam to do it: a reader
 * of its own, awaited before the call.
 *
 * This is the only file in the pack that touches the runtime's filesystem, so
 * everything else runs anywhere JavaScript does.
 *
 * It is written over `node:fs` and `node:process`, which is what makes the pack
 * Node-first: Node runs it with nothing installed and no build step, and Deno
 * runs the same file through its `node:` compatibility. The alternative was
 * `Deno.*`, which is one runtime's own namespace and exists nowhere else.
 */

import {
  chmodSync,
  closeSync,
  fsyncSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeSync,
} from "node:fs";
import process from "node:process";

import { ReadError, WriteError } from "./errors.ts";
import type { Reader, Writer } from "./seams.ts";

/** What a written file ends up as, matching the other packs. */
const FILE_MODE = 0o644;

/** The mode a temporary is created with, before it is widened by the rename. */
const TEMPORARY_MODE = 0o600;

/** The shipped local-file reader and writer, as one object. */
export class LocalFile implements Reader, Writer {
  /** The whole contents as bytes. */
  read(path: string): Uint8Array {
    try {
      const bytes = readFileSync(path);
      // `readFileSync` answers with a Buffer, which is a Uint8Array subclass.
      // The seam declares a Uint8Array, so it is handed on as one: a view over
      // the same memory rather than a copy, so a large file is not read twice.
      return new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    } catch (cause) {
      throw new ReadError("could not read the file", { cause, path });
    }
  }

  /**
   * The bytes, in place, atomically (FR-6.3).
   *
   * They go to a temporary file BESIDE the target and are renamed over it, so a
   * concurrent reader sees the previous contents or the new ones and never a
   * half-written file. Beside rather than in a temporary directory, because a
   * rename across filesystems is a copy and stops being atomic.
   *
   * The data is flushed to the device before the rename. A rename that lands
   * before the contents do leaves a file whose name says it is new and whose
   * bytes are not there, which is the failure atomicity is bought to prevent.
   */
  write(path: string, bytes: Uint8Array): void {
    const suffix = Math.random().toString(36).slice(2, 10);
    const temporary = `${directoryOf(path)}.wrench-${String(process.pid)}-${suffix}.tmp`;
    try {
      // "wx" is create-and-fail-if-present, so this never takes a file
      // somebody else is using as their own temporary.
      const handle = openSync(temporary, "wx", TEMPORARY_MODE);
      try {
        let written = 0;
        while (written < bytes.length) {
          written += writeSync(handle, bytes, written, bytes.length - written);
        }
        fsyncSync(handle);
      } finally {
        closeSync(handle);
      }
      // Created owner-only and widened before the rename, because evidence
      // meant to be handed around has to survive being handed around. The
      // widening happens while the file is still the temporary, so nothing ever
      // sees the target with the narrower mode. The other packs write 0o644 and
      // this is that number.
      chmodSync(temporary, FILE_MODE);
      renameSync(temporary, path);
    } catch (cause) {
      // The temporary is removed on every failing path, including one where the
      // rename itself failed, so a run that could not write does not leave a
      // half-written file beside the target for somebody to find later.
      try {
        unlinkSync(temporary);
      } catch {
        // It was never created, or something else took it. Either way the
        // failure worth reporting is the one being thrown.
      }
      throw new WriteError("could not write the file", { cause, path });
    }
  }
}

/** The directory part of a path, with its separator, or "" for a bare name. */
function directoryOf(path: string): string {
  const cut = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return cut < 0 ? "" : path.slice(0, cut + 1);
}

/** The shipped reader and writer, which is what a caller passes for both. */
export const LOCAL_FILE: LocalFile = new LocalFile();
