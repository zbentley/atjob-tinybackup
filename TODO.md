# TODOs
- Python script that eats the YACC `at` timeparser grammar, and can output: equivalence tests, unambiguous identity, validation info for supplied jobs.
- Tests.
- More OO: at-jobs should be objects with the subprocess-derived metadata lazily loaded on accessor call. This also could yield a Python API for this script.
- Should slurp and write itself into the `at` scheduler rather than relying on being left in the same filesystem location.
- Arbitrary user identifier string.
- Iteration count/burndown, after which it will stop backing things up.
- Make sure debug.txt actually gets written next to the script.