# Pull Request

## Description
<!-- Briefly describe the changes in this PR -->

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Test improvements

## Testing

### Test Quality Checklist
Please review the [Testing Guidelines](../docs/TESTING_GUIDELINES.md) before submitting.

- [ ] **Tests added/updated** for all changed functionality
- [ ] **Tests verify actual values**, not just structure (e.g., specific P/L amounts, not just `len(results) > 0`)
- [ ] **Integration tests preferred** over mocked tests where possible
- [ ] **Real CSV data used** in tests (from `tests/test_data/`) rather than synthetic data
- [ ] **Mocks are justified**: Any new mocked tests have a comment explaining why real data won't work
- [ ] **No shallow assertions**: Tests check calculated values, not just presence of fields
- [ ] **Deterministic tests**: Monte Carlo tests use `random_seed` for reproducibility
- [ ] **All tests pass**: `tm_trade_analyzer_venv/bin/pytest -v` runs without failures

### Manual Testing
<!-- Describe testing performed manually, if applicable -->
- [ ] Tested in web UI with sample CSV files
- [ ] Verified calculations match expected values
- [ ] Tested edge cases (empty data, single trade, all losses, etc.)

## Changes Made
<!-- List the main changes made in this PR -->
- 
- 
- 

## Impact
<!-- Describe the impact of these changes -->

### Breaking Changes
- [ ] No breaking changes
- [ ] Breaking changes (describe below):

<!-- If breaking changes, describe what breaks and migration path -->

### Performance Impact
- [ ] No performance impact
- [ ] Performance improved
- [ ] Performance degraded (justify why acceptable)

## Documentation
- [ ] README.md updated (if public API changed)
- [ ] Code comments added for complex logic
- [ ] Docstrings updated for modified functions
- [ ] TODO.md updated (if implementing planned work)

## Code Quality
- [ ] Follows existing code style and conventions
- [ ] No new warnings from linters
- [ ] DRY principle followed (no duplicated logic)
- [ ] Functions have clear, single responsibilities
- [ ] Error messages are clear and actionable
- [ ] No hardcoded secrets, API keys, or absolute file paths

## Review Checklist for Reviewers

### Code Review
- [ ] Logic is correct and handles edge cases
- [ ] No obvious bugs or security issues
- [ ] Code is readable and maintainable
- [ ] Performance is acceptable

### Test Review
- [ ] Tests are high quality (actual values, not just structure)
- [ ] Mocking is minimal and justified
- [ ] Tests would catch the bugs they're meant to prevent
- [ ] Edge cases are covered

### Documentation Review
- [ ] Changes are documented appropriately
- [ ] Comments explain "why", not just "what"

## Additional Notes
<!-- Any additional information for reviewers -->
