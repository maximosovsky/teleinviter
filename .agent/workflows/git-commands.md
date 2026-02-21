---
description: how to run git commands for this user
---

## Important Rules
// turbo-all

1. **NEVER use `&&` to chain commands** — it does not work in this user's shell. Always run commands separately, one at a time.

2. Standard git flow:
```
git add <files>
```
Wait for completion, then:
```
git commit -m "message"
```
Wait for completion, then:
```
git push
```
