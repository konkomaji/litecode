---
name: skill-builder
description: Help the user design a new litecode skill and save it.
triggers: skill, new skill, make a skill, create skill
tools: write_file
---
1. Ask what task the skill is for, if the user did not say.
2. Write a SKILL.md with frontmatter: name, description, triggers, tools.
3. Body: 3 to 8 numbered steps in simple words.
4. Save it with write_file to .litecode/skills/<name>/SKILL.md.
5. In final, tell the user to run it with /<name>.
