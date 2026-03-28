# Scope And Principles

## Product goal
The new web application must replace the current Telegram-centered product without losing real working capabilities.

The replacement target is broader than the bot alone. Today the circle operates through a combined environment:
- bot for authentication, task flow, submissions, teacher review, oral queue, service commands;
- channel for tasks, hints, solutions, announcements, statistics, links, and structured tagged archive;
- discussion group for moderated public questions and discussion;
- external pages and files referenced from the channel and the bot.

The web product must provide one coherent system that covers these jobs directly.

## Primary actors
- student;
- teacher;
- admin;
- parent or other read-only participant of the circle community;
- moderator, if moderation is later separated from admin/teacher.

## Core product principle
The application must be built around the weekly lesson cycle.

One lesson `N` moves through a predictable lifecycle:
- Monday publication;
- Monday to Wednesday synchronous oral acceptance windows;
- Monday evening to Sunday asynchronous written and test submission;
- Saturday hints publication;
- Sunday submission cutoff;
- Sunday solutions publication.

The system must make this lifecycle explicit in the interface and in permissions.

## Replacement principle
The product must not merely preserve raw data operations. It must preserve the operational visibility users currently get from Telegram.

Examples:
- a student must always understand what tasks exist, what was already submitted, what was checked, and what still needs action;
- a teacher must always understand what queue exists now and which students need attention;
- an admin must always understand which weekly stage is currently active and what public information has already been published;
- community participants must always know where to read announcements, hints, solutions, and discussion threads.

## Required product domains

### 1. Identity and access
- login and session management;
- mapping of accounts to roles and permissions;
- mapping of accounts to student profile, level, and current mode;
- support for students, teachers, admins, and read-only community participants.

### 2. Task and lesson domain
- lessons;
- problems;
- task types: test, written, oral;
- level-aware visibility of tasks;
- hints and solutions publication by schedule;
- task archive and search.

### 3. Submission and result domain
- test answer submission and automatic checking;
- written submission with text and photo attachments;
- oral submission flow with synchronous session support;
- result history and current status per task;
- teacher review and re-review.

### 4. Community and publications domain
- announcements feed;
- tagged publications archive;
- moderated discussion space;
- separation between public discussion and private checking.

### 5. Operations domain
- weekly mode management;
- broadcasts and announcements;
- imports and sync jobs;
- surveys;
- auditability and observability.

## Explicit non-goals for the first requirements baseline
- redesigning pedagogical logic;
- changing the weekly schedule itself;
- replacing moderation policy with something looser;
- removing oral mode from the product.

## Product-level acceptance criteria
- the web app can run one full week of the circle without requiring Telegram bot, Telegram channel, or Telegram group for core operation;
- students can complete the full task journey in web;
- teachers can process written and oral work in web;
- admins can operate the weekly cycle in web;
- announcements, hints, solutions, and discussion are accessible in web with search and tags;
- historical progress and current weekly state are visible enough that users do not need chat archaeology to understand what is going on.
