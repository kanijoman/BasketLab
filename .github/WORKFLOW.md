# 🔄 WORKFLOW OBLIGATORIO

## Recibir Request del Usuario
↓

## 🚦 CHECKPOINT 1: Pre-Implementation
```bash
# ¿El archivo existe y tiene código?
get_errors(["path/to/file.py"])
grep -c "" path/to/file.py  # Count lines
```

**Decision Matrix:**

| Líneas | Funciones >40 | Duplicación | Acción |
|--------|---------------|-------------|--------|
| <300 | No | No | ✅ Proceder con feature |
| >300 | No | No | ⚠️ Avisar + proceder con cuidado |
| >300 | Sí | - | ❌ **PROPONER REFACTOR FIRST** |
| >500 | - | - | ❌ **PROPONER REFACTOR FIRST** |
| - | Sí (>40) | - | ❌ **PROPONER REFACTOR FIRST** |
| - | - | Sí | ❌ **CREAR HELPER FIRST** |

**Si ❌ → Mensaje al usuario:**
> "Antes de implementar [FEATURE], detecto que [FILE] tiene [ISSUES]. Las guidelines del proyecto requieren refactorizar primero. ¿Procedo con:
> 1. Refactor + Feature (recomendado)
> 2. Solo Feature (crear deuda técnica)
> 3. Solo Refactor (sin feature)"

↓

## ⚙️ CHECKPOINT 2: Durante Implementación (cada 100 líneas)

**PAUSE y verificar:**
- [ ] Archivo sigue <500 líneas?
- [ ] Nueva función <40 líneas?
- [ ] No duplicación introducida?
- [ ] Complejidad <3 niveles nested?

**Si alguna falla → STOP y refactorizar AHORA**

↓

## ✅ CHECKPOINT 3: Post-Implementation

```bash
# Tests
pytest tests/ -v

# Linting
get_errors()

# Verificar no regressions
pytest tests/test_[modified_module].py -v
```

**Checklist final:**
- [ ] Tests pasan
- [ ] No errores de linting
- [ ] Edge cases cubiertos
- [ ] FEB + FBCYL testeado
- [ ] No regresiones

↓

## 📊 Report al Usuario (conciso)

**Formato:**
- Cambios realizados: [lista breve]
- Tests: ✅ X/Y pasando
- Calidad: ✅ Sin issues / ⚠️ [issues encontrados]

---

## 🚨 REGLA DE ORO

**"Refactor BEFORE proceeding, not AFTER"**

No agregar código a archivos que ya superan límites de calidad.
