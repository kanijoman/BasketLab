# ⚠️ MANDATORY PRE-MODIFICATION CHECKS

**RUN BEFORE touching any file. NO EXCEPTIONS.**

## 🚦 STOP and CHECK (Every file modification)

```bash
# 1. Check file size
Get-Content path/to/file.py | Measure-Object -Line
```

**Decision Tree:**
- **>500 lines?** → ❌ STOP. Extract modules FIRST
- **>300 lines?** → ⚠️ CAUTION. Consider refactor before adding code
- **<300 lines?** → ✅ OK to proceed

```bash
# 2. Check function length
$content | Select-String -Pattern "^\s{4}def " 
```

**Decision Tree:**
- **Any function >40 lines?** → ❌ STOP. Split FIRST
- **All functions <40 lines?** → ✅ OK to proceed

```bash
# 3. Scan for duplication
grep_search -q "similar patterns" -isRegexp true
```

**Decision Tree:**
- **Duplicated code found?** → ❌ STOP. Extract helper FIRST
- **No duplication?** → ✅ OK to proceed

## 🔄 DURING IMPLEMENTATION (Every 100 lines written)

**Pause and verify:**
1. [ ] Total file lines still <500?
2. [ ] New function length <40 lines?
3. [ ] No code duplication introduced?
4. [ ] Following existing patterns?

**If ANY checkbox fails → STOP and refactor immediately**

## 📋 POST-IMPLEMENTATION (Before completing)

1. Run linter: `get_errors()`
2. Run tests: `pytest -v`
3. Verify no regressions

## 🚨 NEVER IGNORE THESE CHECKS

Guidelines exist to **prevent** technical debt, not **fix** it later.

**Priority Order:**
1. Code quality checks ← **DO FIRST**
2. Feature implementation ← Do second
3. Tests ← Do third
