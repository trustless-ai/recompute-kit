// Owner-side counterpart to _self_grading.py; no semantic expected values here.
export function expectationError(c, field, { required = [], types = {} } = {}) {
  if (!Object.hasOwn(c, field)) return `missing ${field}`;
  const exp = c[field];
  if (!exp || typeof exp !== "object" || Array.isArray(exp) || !Object.keys(exp).length)
    return `${field} must be a nonempty object`;
  for (const key of required)
    if (!Object.hasOwn(exp, key)) return `missing ${field}.${key}`;
  for (const [key, shape] of Object.entries(types)) {
    if (!Object.hasOwn(exp, key)) continue;
    const valid = shape === "nullable_string" ? exp[key] === null || typeof exp[key] === "string"
      : shape === "string" && typeof exp[key] === "string";
    if (!valid) return `${field}.${key} must be ${shape}`;
  }
  return null;
}

export class Grading {
  constructor(cases) {
    this.cases = cases;
    this.admitted = cases.length;
    this.outcomes = new Map();
    this.faults = [];
  }
  ungradable(index, reason) {
    this._record(index, "ungradable");
    console.error(`UNVERIFIABLE: UNGRADABLE_CASE ${this.cases[index].name ?? index}: ${reason}`);
  }
  expectation(index, c, field, shape) {
    const error = expectationError(c, field, shape);
    if (error !== null) {
      this.ungradable(index, error);
      return false;
    }
    return true;
  }
  _record(index, outcome) {
    if (this.outcomes.has(index) || index < 0 || index >= this.admitted) {
      this.faults.push(`duplicate or out-of-range grading outcome: ${index}`);
      return;
    }
    this.outcomes.set(index, outcome);
  }
  record(index, reproduced) { this._record(index, reproduced ? "reproduced" : "refuted"); }
  count(outcome) { return [...this.outcomes.values()].filter(v => v === outcome).length; }
  get reproduced() { return this.count("reproduced"); }
  get refuted() { return this.count("refuted"); }
  finish() {
    for (let i = 0; i < this.admitted; i++)
      if (!this.outcomes.has(i)) this.ungradable(i, "no grading outcome recorded");
    const ungradable = this.count("ungradable");
    for (const reason of this.faults) console.error(`UNVERIFIABLE: GRADING_ACCOUNTING ${reason}`);
    if (ungradable || this.faults.length)
      console.error(`GRADING admitted=${this.admitted} graded=${this.reproduced + this.refuted} reproduced=${this.reproduced} refuted=${this.refuted} ungradable=${ungradable}`);
    return this.refuted ? 1 : ungradable || this.faults.length ? 2 : 0;
  }
}
