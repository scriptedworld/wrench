What changed, and which requirement under `docs/REQUIREMENTS/` it discharges. If
it discharges none, say what the change is for and whether a requirement should
exist.

`CONTRIBUTING.md` has the detail behind each of these.

- [ ] Every new test carries a `COVERS:` line naming a requirement and a kind.
- [ ] `./bin/test-suite-parity.py` passes, or the divergence is declared by a
      scope marker on the requirement.
- [ ] All three suites pass, including `go test ./...`, which `just test` does
      not run.
- [ ] Behaviour that changed changed in all three packs, and in
      `testdata/canonical/` where the emitted bytes moved.
- [ ] A schema change has been through `./bin/generate-shipped.py`.
- [ ] A pack whose surface changed has had its version bumped in this commit.
- [ ] No suppression pragma was added, or it is registered in `SUPPRESSIONS`
      with the question and the answer.
