# Skills

A skill is a saved set of steps for one kind of task. litecode adds the steps to the prompt when the skill runs. Small models follow short numbered steps well.

## Use a skill

- `/NAME TASK` runs a skill. Example: `/review src/api/`.
- A skill also runs automatically when its trigger words appear in your message. Max 2 skills per task.
- `/skills` lists all skills with their scope.

## Built-in skills

| Skill | Use |
|---|---|
| `review` | security review: scan, confirm, fix |
| `test-fix` | run tests, fix failures, repeat |
| `explain` | explain code in simple steps |
| `commit` | commit message from the diff |
| `refactor` | change structure, keep behavior, run tests |
| `skill-builder` | design a new skill with the model's help |

## Make a skill

Option 1, step by step:

```
/skill new django-migrations
```

litecode asks for a description, trigger words, and the steps.

Option 2, the model drafts it:

```
/skill make a skill that checks Django migrations for missing indexes
```

litecode shows the draft. You confirm before it saves.

Option 3, write the file yourself. Create `.litecode/skills/<name>/SKILL.md`:

```
---
name: django-migrations
description: Check new Django migrations for missing indexes and data loss.
triggers: migration, migrations, django
tools: glob, read_file, grep
---
1. Find new files with glob "**/migrations/*.py".
2. Read each new migration.
3. Flag RemoveField and DeleteModel. They lose data.
4. Flag ForeignKey fields without db_index on large tables.
5. In final, list each problem as file:line and a fix.
```

Rules for the file:

- `name`: 2-41 characters. Lowercase letters, digits, `-`, `_`.
- `description`: one sentence.
- `triggers`: comma separated words (optional).
- `tools`: tools the steps use (optional, for the reader).
- Body: 3-8 numbered steps. Use simple words. Name the tools.

## Scope

| Scope | Folder | Who sees it |
|---|---|---|
| project | `<project>/.litecode/skills/` | this project; commit it to share with your team |
| user | `<data_dir>/skills/` | all your projects |
| builtin | shipped with litecode | everyone |

On a name clash, project wins over user, and user wins over builtin.

Delete: `/skill rm NAME`. Built-in skills cannot be deleted. Override one with a project skill of the same name.
