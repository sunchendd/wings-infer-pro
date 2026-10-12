# G.TYP.BOL.04 禁止在if表达式条件中使用块（block）结构-试行

- **规则ID**：397d2c9e-0b44-4d1f-9934-10e53b949a2b
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**

为了增加可读性。

**【正确示例】**

```
if true { /* ... */ }
# fn somefunc() -> bool { true };
let res = { let x = somefunc(); x };
if res { /* ... */ }

```
**【错误示例】**

```
if { true } { /* ... */ }
# fn somefunc() -> bool { true };
if { let x = somefunc(); x } { /* ... */ }

```
**【修复建议】**
