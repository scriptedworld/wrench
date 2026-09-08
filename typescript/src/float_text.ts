/**
 * The one spelling of a number, shared by both of this pack's codecs.
 *
 * FR-4.8. Positional decimal, never an exponent. The digits are the shortest
 * decimal string that reads back as the same double, placed with the decimal
 * point where it belongs rather than moved into an `e`. A whole float keeps a
 * `.0`, so it never reads back as an integer.
 *
 * The rule carries no threshold on purpose. Every alternative needs a magnitude
 * at which the spelling changes, and that number then has to be stated in the
 * contract and implemented identically in every pack. "Never" is the only
 * answer with nothing to get wrong, and the only one a consumer parsing with a
 * naive numeric pattern reads correctly: `1e+20` matched by `[0-9.]+` yields 1,
 * which is how this defect was found.
 *
 * The cost is bounded: 326 characters for a subnormal near the bottom of the
 * range, 311 for the largest finite double. Both measured against the Python
 * pack's `canonical_float_text`, which produces the same strings.
 *
 * JAVASCRIPT HAS ONE NUMBER TYPE, so unlike every other pack this one cannot be
 * told whether a value is an integer or a float. It is decided by the value:
 * a safe integer is written as an integer, and everything else as a float. That
 * is also what makes the widening FR-4.10 asks for visible here, because a
 * literal past 2^53 arrives already rounded and is written with a `.0` rather
 * than as an exact-looking integer it is not.
 */

/**
 * The canonical spelling of one number.
 *
 * Negative zero is a float in both formats this pack ships. It has no integer
 * spelling that carries the sign, so `-0.0` is the only way to write it, which
 * is what FR-4.11 says about the YAML side.
 */
export function canonicalNumberText(value: number): string {
  if (!Number.isFinite(value)) {
    throw new RangeError(`cannot write ${value} in canonical form`);
  }
  if (Number.isSafeInteger(value) && !Object.is(value, -0)) {
    return String(value);
  }
  return canonicalFloatText(value);
}

/**
 * The positional spelling of one float.
 *
 * `Number.prototype.toString` gives the shortest round-tripping digits and
 * picks an exponent on a threshold of its own, exactly as Python's `repr` and
 * Ruby's `Float#to_s` do. This moves the point back to where the exponent says
 * it belongs without touching a digit, so the round trip is the runtime's and
 * only the placement is wrench's.
 *
 * NaN and the infinities are refused. YAML can spell them, JSON Schema cannot
 * represent them, and a file no consumer in this ecosystem can validate is not
 * canonical form.
 */
export function canonicalFloatText(value: number): string {
  if (!Number.isFinite(value)) {
    throw new RangeError(`cannot write ${value} in canonical form`);
  }
  // `String(-0)` is "0", so the sign has to be put back before anything else
  // reads the digits.
  if (Object.is(value, -0)) return "-0.0";

  const text = String(value);
  const parts = /^(-?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)$/.exec(text);
  if (parts === null) return text.includes(".") ? text : `${text}.0`;

  const [, sign, whole, fraction = "", exponentText] = parts;
  const digits = whole + fraction;
  // Where the point sits once the exponent is spent, counted from the left of
  // the digits. At or below zero it is a leading `0.`; at or past the end the
  // digits are padded with zeros and take a trailing `.0`.
  const point = whole.length + Number(exponentText);
  if (point <= 0) return `${sign}0.${"0".repeat(-point)}${digits}`;
  if (point >= digits.length) {
    return `${sign}${digits}${"0".repeat(point - digits.length)}.0`;
  }
  return `${sign}${digits.slice(0, point)}.${digits.slice(point)}`;
}
