# Storybook and visual testing instructions

- Stories are deterministic, use Russian realistic fixtures and never call production services.
- Use MSW handlers from test utilities for network states; an unhandled application request is a test failure.
- Keep global light/dark and density controls functional. A dark example inside a light document is not an adequate dark-theme test.
- Shared component changes add/update stories and interaction tests in the same change.
- Accessibility violations are errors. Do not disable an a11y rule globally to pass a story; document and scope any temporary exception.
- Never update snapshots or baselines without rendering and inspecting the visual diff in every affected browser/theme/viewport.
- Exploration stories are clearly labeled and must not silently become accepted design-system decisions.
