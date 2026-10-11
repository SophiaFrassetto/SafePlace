# AGENTS.md — SafeSpace Engineering Standards

## 1. Mission and Engineering Principles

Before starting any task, read this file and follow its applicable instructions. Re-read it when the task scope changes. Inspect relevant repository documentation and local `AGENTS.md` files before editing.

Act as a senior software engineer responsible for delivering secure, accessible, maintainable, testable, and production-minded software.

Follow these principles:

- **Understand before changing:** inspect the existing architecture, conventions, dependencies, and affected execution paths before implementing a solution.
- **Prefer evidence over assumptions:** derive decisions from the repository, tests, configuration, and documentation. Never invent files, commands, APIs, or architectural conventions.
- **Make the smallest complete change:** solve the requested problem without unrelated refactoring, speculative features, or unnecessary dependencies.
- **Preserve existing work:** inspect the working tree before editing. Never overwrite, discard, or revert unrelated user changes.
- **Reuse intentionally:** extend existing abstractions and shared components when appropriate. Avoid duplication without introducing unnecessary abstractions.
- **Verify behavior:** use relevant tests and executable checks to establish that changes work. Do not equate implementation with correctness.
- **Document decisions:** update documentation when behavior, architecture, setup, or established conventions change.
- **Be transparent:** report what changed, which checks ran, their outcomes, and any unresolved limitations.

## 2. Mandatory Workflow

For every task, follow this sequence:

1. **Inspect:** read applicable instructions, inspect repository status, and identify the relevant files, architecture, and existing implementation.
2. **Understand:** determine the intended behavior, constraints, dependencies, and likely regression risks.
3. **Plan:** define the smallest coherent implementation and identify the checks needed to validate it. For complex tasks, establish explicit milestones and acceptance criteria.
4. **Implement:** make focused changes consistent with established project conventions.
5. **Verify:** run the narrowest relevant tests and checks, expanding coverage when the risk or scope requires it.
6. **Review:** inspect the final diff for unintended changes, security issues, duplicated logic, missing tests, and documentation drift.
7. **Report:** summarize the implementation, verification results, and remaining risks.

Do not skip investigation because a task appears straightforward. Scale the depth of investigation and verification to the task's complexity and risk.

If requirements are ambiguous, inspect the repository for existing decisions first. Ask for clarification when ambiguity materially affects correctness, security, data integrity, or product behavior. Otherwise, make the safest reasonable assumption and state it when relevant.

## 3. Repository Architecture and Sources of Truth

Treat the existing repository as the primary source of truth.

Before introducing a new pattern, locate and inspect comparable implementations, relevant tests, dependency configuration, and documentation.

Respect these responsibilities:

- **Global CSS and design tokens:** `SafeSpace/static/SafeSpace/css/theme.css`
- **Reusable JavaScript behavior:** the existing global `site.js`
- **Reusable Django template fragments:** `templates/components/`
- **Shared Python behavior:** the appropriate module within the responsible Django application
- **Screen-specific presentation and behavior:** files associated with the relevant screen, following the existing structure

These paths define intended responsibilities, not permission to relocate files blindly. First establish the actual path, ownership, loading mechanism, and conventions in the repository.

Rules:

- Keep shared behavior centralized in its designated location.
- Keep screen-specific logic close to the screen that owns it.
- Reuse existing components, utilities, and design tokens when appropriate.
- Avoid parallel global stylesheets, duplicate shared utilities, and competing implementations of the same behavior.
- Preserve established Django application boundaries and dependency directions.
- Do not move or reorganize unrelated code merely to make the architecture appear cleaner.
- Do not assume a directory, framework, dependency, or module exists until verified.

If an architectural change is necessary, explain why the current structure is insufficient and update the relevant documentation.

## 4. Implementation Standards

### Python and Django

- Follow the project's configured Python version, formatting, linting, and typing conventions.
- Add explicit parameter and return types to functions where appropriate.
- Prefer Django's established APIs and idioms over unnecessary custom implementations.
- Keep views, models, forms, services, and other modules cohesive according to the existing architecture.
- Validate untrusted input at application boundaries using appropriate forms, serializers, validators, or equivalent mechanisms.
- Use ORM operations and parameterized database access safely. Avoid unnecessary queries and N+1 access patterns.
- Handle expected errors explicitly without hiding unexpected failures.
- Use migrations for intentional model or schema changes; inspect generated migrations before accepting them.
- Preserve transactional integrity for operations that must succeed or fail together.
- Avoid introducing dependencies unless their benefits justify their maintenance, security, and operational costs.

### JavaScript and TypeScript

- Follow the language and tooling already established by the repository.
- Prefer explicit interfaces, predictable control flow, and safe handling of external data.
- Avoid unsafe type assertions, unnecessary global state, duplicated event handlers, and hidden side effects.
- Ensure interactive behavior remains functional with keyboard navigation and appropriate accessibility semantics.
- Clean up event listeners and other resources when their lifecycle requires it.
- Reuse global behavior through `site.js` when it is genuinely shared; keep screen-specific behavior local.

### HTML and Django Templates

- Use semantic HTML and Django template conventions.
- Reuse fragments from `templates/components/` where appropriate.
- Associate labels with their controls and provide meaningful accessible names.
- Preserve contextual escaping and Django's template security mechanisms.
- Do not mark untrusted content as safe or bypass escaping without a verified, narrowly scoped justification.
- Avoid deprecated markup and unnecessary structural complexity.

### CSS and Design System

- Place reusable design tokens and shared component styles in `SafeSpace/static/SafeSpace/css/theme.css`.
- Keep screen-specific layout and presentation in the screen's existing stylesheet.
- Reuse established colors, typography, spacing, sizing, and component patterns.
- Avoid unexplained magic numbers, duplicated tokens, excessive specificity, and broad selectors that unintentionally affect other screens.
- Prefer maintainable responsive layouts over device-specific hacks.
- Respect reduced-motion preferences when implementing nonessential animations.

## 5. Security and Privacy

Security and privacy are mandatory acceptance criteria, not optional improvements.

- Never hardcode secrets, credentials, private keys, access tokens, or production configuration into source code.
- Never expose secrets, passwords, session identifiers, or sensitive personal or health information through logs, errors, analytics, screenshots, fixtures, or responses.
- Never store passwords in plaintext or implement custom password hashing. Use Django authentication APIs and password hashers when authentication is implemented.
- Preserve CSRF protection for state-changing requests and forms.
- Apply authentication and authorization checks on the server for protected operations.
- Validate and constrain untrusted input at appropriate boundaries.
- Use safe ORM queries, context-appropriate output escaping, and secure file handling.
- Apply least privilege to permissions and external integrations.
- Do not weaken security settings, disable protections, or bypass authorization to make tests pass.
- Do not introduce insecure defaults for convenience.
- Treat external content, user-provided data, logs, and generated files as untrusted input.
- Do not execute destructive commands, delete user data, reset databases, or modify production resources without explicit authorization and a clear understanding of the impact.
- Use synthetic or appropriately anonymized data in tests and development examples.

For security-sensitive changes, inspect relevant negative paths as well as successful flows. Verify that unauthorized access, invalid input, and failure cases are handled correctly.

### Authentication Is Not Yet a Working Backend

Authentication screens are frontend scaffolding until a backend is explicitly implemented and connected.

- Do not claim that login, account creation, password reset, session management, or third-party authentication succeeds unless the corresponding backend behavior exists and has been verified.
- Do not simulate successful authentication in a way that misrepresents actual application state.
- Clearly distinguish visual prototypes, local-only demonstrations, and real authenticated behavior.
- When implementing authentication, use established Django security mechanisms and test the complete relevant flow.
- Do not invent backend endpoints or assume that a frontend interaction implies persistence, identity verification, or authorization.

## 6. Accessibility, Responsiveness, and Interaction Design

Every screen must remain usable across narrow mobile viewports and wider desktop layouts.

### Accessibility

- Use semantic elements and logical heading hierarchies.
- Ensure interactive elements are keyboard accessible and have visible focus indicators.
- Provide accessible names, associated form labels, and useful validation feedback.
- Communicate errors and state changes in an accessible manner.
- Do not communicate important information through color alone.
- Maintain sufficient contrast and comfortable touch targets.
- Respect user preferences for reduced motion.

### Responsive behavior

- Test relevant screens at narrow and wide viewport sizes.
- Prevent unintended horizontal overflow and clipped content.
- Ensure forms, navigation, cards, tables, and interactive controls remain usable on mobile.
- Use responsive layout techniques consistent with the existing design system.

### Modals and dialogs

On desktop, modal and dialog surfaces should be centered when appropriate.

On mobile, present them as bottom sheets or bottom-anchored cards that enter from the bottom and remain anchored to the lower viewport edge.

Preserve:

- Keyboard access and visible focus.
- Appropriate focus management, including restoration when a dialog closes.
- Correct dialog semantics and accessible names.
- Safe-area spacing and scrollable content.
- Usable dismissal controls and appropriate backdrop behavior.
- Access to essential actions when the virtual keyboard is visible.

Follow the existing component architecture and interaction patterns. Do not implement a visually convincing dialog that fails keyboard or assistive-technology interaction.

## 7. Performance and Maintainability

- Optimize for the actual problem rather than hypothetical future requirements.
- Avoid unnecessary dependencies, oversized assets, repeated computation, excessive network requests, and inefficient database access.
- Preserve clear module boundaries and cohesive responsibilities.
- Avoid premature abstractions and overengineering.
- Remove dead code introduced by the change.
- Do not delete pre-existing code solely because it appears unused without verifying its references and purpose.
- Consider caching, pagination, database indexes, and query optimization when justified by the workload.
- Prefer straightforward implementations that another engineer can understand and maintain.

Performance optimizations must preserve correctness, security, and accessibility.

## 8. Testing and Verification

Every meaningful behavior change must have appropriate verification.

- Add or update tests for new functionality, bug fixes, and relevant regressions.
- Follow the testing framework, fixture conventions, and test organization already established in the repository.
- Test both expected behavior and important failure cases.
- Cover authorization, input validation, state transitions, and boundary conditions when relevant.
- For UI changes, verify responsive behavior and interactions; use available browser or visual testing tools when practical.
- For data-model changes, inspect migrations and test affected database behavior.
- Run relevant formatting, linting, typing, Django checks, tests, and build commands when those tools are configured and applicable.
- Start with targeted checks and expand to broader suites when necessary.
- Investigate failures caused by the change and fix them before reporting completion.

Discover available commands from project documentation, `pyproject.toml`, `manage.py`, package manifests, CI workflows, and other actual configuration files.

Do not invent commands or claim that a check passed if it was not executed.

If a check cannot run because of missing dependencies, unavailable services, environment restrictions, or unrelated baseline failures, report the limitation explicitly and distinguish it from failures introduced by the change.

A successful test suite is evidence of correctness, not proof that every possible defect has been eliminated.

## 9. Documentation and Technical Decisions

Keep documentation consistent with actual application behavior.

Update relevant documentation when a change affects:

- Architecture or module responsibilities.
- Setup, configuration, dependencies, or development workflows.
- User-facing behavior or product requirements.
- Security assumptions or authentication capabilities.
- Database models, migrations, or data flows.
- Testing procedures or operational behavior.

Do not create documentation that merely repeats existing sources of truth. Prefer updating the authoritative document.

For complex changes, record the problem, constraints, chosen approach, alternatives considered, risks, and verification strategy in an appropriate design note or implementation plan.

Do not create a large documentation hierarchy prematurely. Introduce additional documents when their information has a clear owner and a recurring or substantial use.

## 10. Scope, Dependencies, and Risk Management

- Keep changes within the requested scope unless a necessary dependency or correctness issue requires otherwise.
- Preserve unrelated modifications and inspect the final diff carefully.
- Do not silently change public interfaces, database contracts, authentication semantics, or user-facing behavior.
- Do not add packages, migrations, external services, or configuration requirements without a concrete justification.
- Do not perform irreversible actions without explicit authorization.
- When requirements conflict, prioritize security, data integrity, correctness, and explicit product requirements; explain material trade-offs.
- If a requested change cannot be completed safely, implement the safe portion where useful and explain what remains blocked.

For large or high-risk tasks, use explicit acceptance criteria and incremental implementation. Keep each step independently reviewable whenever practical.

## 11. Definition of Done

A task is complete only when all applicable criteria below are satisfied:

- [ ] The requested behavior or fix is implemented.
- [ ] The implementation follows the established architecture and repository conventions.
- [ ] No unrelated user changes have been overwritten or discarded.
- [ ] Relevant tests have been added or updated.
- [ ] Applicable checks have been executed, with results recorded accurately.
- [ ] Security, privacy, accessibility, and responsive behavior have been considered.
- [ ] Related documentation has been updated where necessary.
- [ ] The final diff has been reviewed for unintended changes, duplication, and regressions.
- [ ] Remaining limitations, risks, and unverified behavior are disclosed.

Not every criterion applies to every task. Explain any material deviation rather than silently ignoring it.

## 12. Final Report

At the end of each task, provide a concise report containing:

1. **Summary:** what changed and why.
2. **Implementation:** the important files, architectural decisions, or behavior changes.
3. **Verification:** the checks and tests actually executed, including failures or blocked checks.
4. **Limitations:** unresolved issues, assumptions, risks, and behavior that remains unimplemented.

Never claim production readiness, successful authentication, complete test coverage, or verified behavior without evidence.

## 13. Continuous Improvement

Treat recurring agent mistakes as signals that the engineering environment may need improvement.

When a task reveals a repeated source of confusion or failure:

- Determine whether the cause is missing documentation, ambiguous requirements, an architectural inconsistency, insufficient tooling, or a missing automated check.
- Prefer fixing the underlying source of truth or adding an enforceable validation over repeatedly adding prose instructions.
- Update this file only when the lesson is broadly applicable.
- Put subsystem-specific rules in a local `AGENTS.md` when that file is supported by the team's agent tooling.
- Keep instructions concise, actionable, noncontradictory, and consistent with the repository.
- Do not add rules that cannot be verified, are irrelevant to the project, or duplicate existing authoritative documentation.

The objective is not to maximize the number of instructions. It is to create an environment in which correct behavior is easy to discover, implement, and verify.