# Branch Protection Setup

Use this document as the repository administrator checklist.

## Protect `main`

In GitHub:

1. Open repository settings.
2. Go to Branches or Rulesets.
3. Create a rule for `main`.
4. Enable pull request requirement.
5. Enable required approvals.
6. Enable required status checks.
7. Select the CI workflow.
8. Enable CODEOWNERS review.
9. Disable force pushes.
10. Disable branch deletion.

## Recommended Merge Strategy

Use squash merge for ordinary pull requests.

Use merge commits only when preserving branch history is useful for large design work.

Disable direct commits to `main`.

## Sensitive Paths

Changes to the following paths should require maintainer review:

- `skill/acltd/scripts/`
- `skill/acltd/SKILL.md`
- `skill/acltd/references/`
- `.github/`
- `SECURITY.md`
- `GOVERNANCE.md`

## Contributor Flow

External contributors should fork the repository and open pull requests.

Trusted collaborators may use branches in the same repository, but still must open pull requests.
