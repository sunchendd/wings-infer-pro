# G.STR.04 需要判断字符串以哪个字符开头或结尾时，不要按字符迭代比较-试行

- **规则ID**：160808d0-638d-4876-9f06-959e1a26f1d9
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**



**【正确示例】**

```
let name = "_";
name.ends_with('_') || name.ends_with('-');
let name = "foo";
if name.starts_with('_') {};

```
**【错误示例】**

```
let name = "_";
name.chars().last() == Some('_') || name.chars().next_back() == Some('-');
let name = "foo";
if name.chars().next() == Some('_') {};

```
**【修复建议】**
