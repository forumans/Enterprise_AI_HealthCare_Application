# Healthcare SaaS Platform — Requirements Specification

This folder holds the requirements for the multi-tenant Healthcare SaaS platform, reverse-engineered from
the working application in `healthcare_saas_app/`. They are written so that an AI coding agent (Claude Code,
Codex or similar) or a human team can build a functionally equivalent application from scratch: the same
roles, screens, business rules, validations, security model and deployment shape.

## How to use these documents

1. Read **01** and **02** first. They define the vocabulary, the roles, the architecture and the data model
   that every other document refers to.
2. Read **03** (business rules) and **09** (security and multi-tenancy) before writing any endpoint. Those
   rules apply to every role.
3. Build role by role with **04–08**. Each one lists that role's screens, functions, conditions, validations
   and acceptance criteria.
4. Use **10** (API) and **11** (UI) as the contract between backend and frontend.
5. Use **12** for configuration, deployment, observability and the test plan.
6. Check **13** last. It lists where the current code falls short of these requirements, so you build the
   intended behavior rather than copy a defect.

## Document map

| # | File | Contents |
|---|------|----------|
| 01 | [01-product-overview.md](01-product-overview.md) | Purpose, scope, roles, glossary, tech stack, architecture |
| 02 | [02-domain-model-and-data.md](02-domain-model-and-data.md) | Entities, fields, enums, constraints, triggers, migrations |
| 03 | [03-business-rules.md](03-business-rules.md) | Scheduling, time zones, slots, appointment lifecycle, accounts, search, field validation catalog |
| 04 | [04-role-guest-and-authentication.md](04-role-guest-and-authentication.md) | Home page, login, self-registration, forgot/reset password, sessions |
| 05 | [05-role-patient.md](05-role-patient.md) | Patient functions |
| 06 | [06-role-doctor.md](06-role-doctor.md) | Doctor functions |
| 07 | [07-role-support-staff.md](07-role-support-staff.md) | Support staff functions |
| 08 | [08-role-admin.md](08-role-admin.md) | Administrator functions |
| 09 | [09-security-and-multitenancy.md](09-security-and-multitenancy.md) | Authentication, RBAC, tenant isolation, audit, PHI, headers, secrets |
| 10 | [10-api-specification.md](10-api-specification.md) | Every endpoint: roles, inputs, outputs, errors |
| 11 | [11-ui-ux-specification.md](11-ui-ux-specification.md) | Layout, navigation, shared components, interaction patterns, styling |
| 12 | [12-non-functional-deployment-testing.md](12-non-functional-deployment-testing.md) | Configuration, AWS deployment, migrations, observability, test plan |
| 13 | [13-known-gaps-and-decisions.md](13-known-gaps-and-decisions.md) | Differences between the current code and these requirements; deferred features |

## Conventions

- **SHALL / MUST** is mandatory. **SHOULD** is recommended. **MAY** is optional.
- Every requirement has an ID such as `PAT-BOOK-03`. Prefixes:
  `GEN` general, `DATA` data model, `BR` business rule, `VAL` field validation, `AUTH` guest and authentication,
  `PAT` patient, `DOC` doctor, `SUP` support staff, `ADM` admin, `SEC` security, `API` interface,
  `UI` user interface, `NFR` non-functional, `TEST` testing.
- **Acceptance** lines are testable conditions. Write an automated test for each one.
- Exact user-facing messages appear in quotes. Reuse them verbatim so automated tests and users see
  consistent wording.
- "Clinic" and "tenant" mean the same thing: one customer organization whose data is isolated from every
  other tenant.
- Times are stored in UTC. "Clinic time" means the tenant's configured IANA time zone
  (default `America/New_York`). See `BR-TIME`.

## Source of truth

Where these documents and the code disagree, these documents describe the intended behavior. Document 13
lists every known disagreement. When you change the application, update the matching requirement in the
same change.
