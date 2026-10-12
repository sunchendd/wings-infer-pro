# G.TYP.06 不应使用字符串的行连续符号

- **规则ID**：643e3eba-3987-4bfb-b063-4e89e46e1707
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

提示

**【描述】**

使用反斜杠作为连续符号时，如果在反斜杠之后还有空格，则会导致错误，并且该错误不容易被发现。

**【正确示例】**

```
##### 场景1：行连续符号
- 修复示例：使用+作为连续符号

```javascript
const longString = 'This is a very long string that far exceeds the 80 ' +
  'column limit. It does not contain long stretches of spaces since ' +
  'the concatenated strings are cleaner.';

```

```
**【错误示例】**

```
##### 场景1：行连续符号
- 错误示例：使用反斜杠作为连续符号

```javascript
const longString = 'This is a very long string that far exceeds the 80 \   
  column limit. It unfortunately contains long stretches of spaces due \
  to how the continued lines are indented.';
```

```
**【修复建议】**

不要使用反斜杠作为连续符号，建议使用+作为字符串的连接符号。
