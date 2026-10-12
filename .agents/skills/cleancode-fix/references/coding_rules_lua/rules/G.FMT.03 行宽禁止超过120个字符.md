# G.FMT.03 行宽禁止超过120个字符

- **规则ID**：6ea82f7d-c189-4163-8ad6-c1a1a47f9c40
- **更新时间**：2025-04-15 04:45:00

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：行宽%1超过了120个字符

**【正确示例】**

```
long_string = --[[First part of the long string 
and second part of the long string]]

```
**【错误示例】**

```
-- 此行超过120字符
long_string = "First part of the long string and second part of the long string"

```
**【修复建议】**

对行宽进行限制，是为了更好的可读性。

不要因为有高分辨率的显示器，而忽略代码可读性。
