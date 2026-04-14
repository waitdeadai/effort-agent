# Effort — WAITDEAD Real Estate CRM

## 1. Process Philosophy
No shortcuts allowed. Every implementation requires research, drafting,
verification, and iteration. Speed is secondary to correctness and
completeness. The system serves real estate brokerages in LATAM — a
single bug can cost a deal. Every line of code must be tested, every
API call must be verified, every copy change must be reviewed.

## 2. Verification Requirements
- All code changes MUST be verified with `pytest` — unit tests required
- All API routes MUST be verified with integration tests
- All WhatsApp bot state changes MUST be verified manually
- No "should work" or "looks good" language in any output
- Verification commands MUST be included in every PR description
- Database migrations MUST be tested against a test database before merge

## 3. Iteration Standards
- Minimum drafts per task: 2
- Maximum single-pass completion: NEVER
- Review cycles before accept: 2
- Research MUST precede implementation — show search queries, doc lookups
- Context compaction MUST NOT skip verification step

## 4. Forbidden Shortcuts
- "Good enough" language ("good enough", "should work", "probably works")
- Skipped verification ("no need to run tests", "skip verification")
- Single-pass completion ("Done.", "Complete.", "All set.", "task is done")
- Vague/generic copy ("we help you", "transform your", "seamless", "cutting-edge")
- Assumptions without verification ("assume it will work", "assuming correctness")
- Placeholder code left untested (TODO, FIXME, stub, dummy data, "will implement later")
- Hardcoded secrets or credentials left in code
- Unverified database migrations

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
| exhaustive | 3 | true | true |
| perfectionist | 4 | true | true |
