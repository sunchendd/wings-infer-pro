# G.CHK.02 布尔变量不要与true/false比较

- **规则ID**：7b3c95fd-b25b-4ac6-ba4c-7eedbc8ff982
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：布尔值“xxx”不能参与xxx运算

**【正确示例】**

```
```
if found then ... End
```

```
**【错误示例】**

```
```
if found == true then ... End
```

```
**【修复建议】**

布尔变量不用跟true/false比较
