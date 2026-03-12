# Pull Request

## Description
Provide a clear and concise description of the changes introduced by this pull request.

## Type of Change
Please mark the relevant option(s):

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring
- [ ] Security fix
- [ ] Dependency update
- [ ] Test improvement

## Related Issues
Link to any related issues:

- Fixes #[issue number]
- Relates to #[issue number]
- Depends on #[issue number]

## Changes Made
Please provide a detailed list of changes:

### Files Modified
List all files that were modified:

- `path/to/file1.py` - Brief description of changes
- `path/to/file2.py` - Brief description of changes

### Files Added
List all files that were added:

- `path/to/new_file.py` - Brief description of purpose

### Files Removed
List all files that were removed:

- `path/to/deleted_file.py` - Reason for removal

## Testing
Please describe the tests you ran to verify your changes:

### Test Coverage
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed
- [ ] All existing tests pass

### Test Details
Provide details about the testing:

```bash
# Commands used to run tests
pytest tests/
```

### Test Results
- Total tests: [number]
- Tests passed: [number]
- Tests failed: [number]
- Code coverage: [percentage]

### Manual Testing
Describe any manual testing performed:

1. Test scenario 1
2. Test scenario 2

## Breaking Changes
If this PR introduces breaking changes, please describe them in detail:

### API Changes
List any API changes:

```python
# Old API
old_function(param1, param2)

# New API
new_function(param1, param2, param3)
```

### Migration Guide
Provide a migration guide for users:

```python
# Migration example
```

### Deprecation Timeline
If deprecating features, provide a timeline:

- Version X.Y: Feature deprecated, warnings added
- Version X+1.0: Feature removed

## Security Considerations
Please address any security implications:

- [ ] This change has security implications
- [ ] This change requires security review
- [ ] This change introduces new attack vectors
- [ ] This change modifies security-critical code

### Security Impact
If there are security implications, describe them:

## Performance Impact
Please address any performance implications:

- [ ] This change improves performance
- [ ] This change may impact performance
- [ ] Performance testing completed

### Performance Details
Provide performance testing details if applicable:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Execution time | X ms | Y ms | +/- Z% |
| Memory usage | X MB | Y MB | +/- Z% |

## Documentation
Please verify documentation updates:

- [ ] README.md updated (if applicable)
- [ ] API documentation updated (if applicable)
- [ ] Code comments added/updated
- [ ] Changelog entry added (for user-facing changes)
- [ ] SECURITY.md updated (if applicable)

### Documentation Changes
Describe documentation changes made:

## Dependencies
Please verify dependency changes:

- [ ] No new dependencies added
- [ ] New dependencies added (listed below)
- [ ] Dependencies updated (listed below)
- [ ] Dependencies removed (listed below)

### Dependency Details
If dependencies changed, provide details:

| Package | Old Version | New Version | Reason |
|---------|-------------|-------------|--------|
| package-name | X.Y.Z | A.B.C | Reason for change |

## Code Quality
Please verify code quality:

- [ ] Code follows project style guidelines
- [ ] Code is properly commented
- [ ] Variable and function names are clear and descriptive
- [ ] Code is modular and follows DRY principles
- [ ] Error handling is appropriate
- [ ] Edge cases are handled

## Checklist
Please verify that you have completed the following:

- [ ] I have read the CONTRIBUTING.md document
- [ ] I have read the CODE_OF_CONDUCT.md document
- [ ] My code follows the code style of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published in downstream modules
- [ ] I have checked my code and corrected any misspellings

## Reviewer Guidelines
Please suggest appropriate reviewers:

- [ ] Security review required (tag security-focused reviewers)
- [ ] Performance review required (tag performance-focused reviewers)
- [ ] Architecture review required (tag architecture-focused reviewers)
- [ ] Documentation review required (tag documentation-focused reviewers)

### Suggested Reviewers
@reviewer1
@reviewer2

## Additional Context
Add any other context about the pull request here.

## Screenshots
If applicable, add screenshots to help explain your changes.

## Questions
Are there any questions or areas where you would like specific feedback from reviewers?

---

**Note**: By submitting this pull request, you agree that your contributions will be licensed under the same license as the project.
