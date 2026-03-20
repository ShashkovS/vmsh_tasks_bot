# Cross-Cutting Requirements

## 1. Roles and permissions
- Permissions must be role-based and explicit.
- At minimum the system must distinguish:
  - student;
  - teacher;
  - admin;
  - read-only community participant.
- Sensitive actions must not rely on hidden URLs or convention.

## 2. Weekly-state awareness
- The current weekly stage must be a system concept, not just a documentation note.
- The product must consistently enforce:
  - what can be submitted now;
  - what content is visible now;
  - what teacher tools are active now;
  - what deadlines are already passed.

## 3. Status transparency
- Every important object must have visible state.
- This includes:
  - task availability;
  - submission status;
  - review status;
  - publication status;
  - survey status;
  - moderation status.
- The product must minimize hidden state that currently lives in command knowledge or chat context.

## 4. History and auditability
- The system must preserve history rather than only the latest state.
- Users and operators must be able to inspect:
  - submission history;
  - result history;
  - teacher comments;
  - publication history;
  - moderation history;
  - admin operations where appropriate.

## 5. Search and filtering
- Search is a core requirement, not a convenience feature.
- The system must provide fast search and filters across:
  - lessons;
  - tasks;
  - users;
  - results;
  - publications;
  - discussion threads.

## 6. Attachments and media
- The system must support media-heavy workflows, especially student photo uploads.
- Attachments must remain understandable in teacher review.
- Mobile upload must be reliable and simple.

## 7. Notifications
- The system must support event-driven notifications.
- Notifications must be configurable by role and event type.
- The application must provide an internal notifications center even if external delivery is optional.

## 8. Mobile-first critical flows
- The overall product may be responsive web, but the following flows must be optimized for phone use:
  - student task browsing;
  - student photo submission;
  - checking status after teacher review;
  - reading announcements;
  - joining live oral flow.

## 9. Teacher productivity and queue safety
- Queue-heavy teacher flows must be efficient.
- The system must avoid unnecessary page churn and context loss.
- It must be hard to accidentally process the wrong student or task.

## 10. Reliability and recovery
- The system must fail transparently.
- If an upload, check, or publish action fails, the user must see a clear status and retry path.
- Important operations must be idempotent or protected against accidental duplicate execution.

## 11. Observability
- The product must preserve and improve traceability of real user flows.
- Structured event logging must remain available for:
  - student actions;
  - teacher review actions;
  - admin operations;
  - publication lifecycle;
  - live oral session events if still applicable.
- Observability must support later extraction of user stories, incident analysis, and operational reporting.

## 12. Privacy and safety
- The system must protect student data and submission content.
- Public and private spaces must be clearly separated.
- Only authorized teachers/admins may view private submissions and internal results.

## 13. Extensibility
- The product should support later replacement of specific integrations, especially live-video tooling and external messaging channels, without rebuilding the whole workflow model.

## 14. Migration completeness criterion
- The migration is successful only if the web product replaces not just command execution but the full operational ecosystem:
  - task work;
  - checking;
  - weekly orchestration;
  - announcements;
  - searchable tagged archive;
  - moderated community discussion.
