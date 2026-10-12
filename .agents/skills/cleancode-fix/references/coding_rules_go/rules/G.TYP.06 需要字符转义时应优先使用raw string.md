# G.TYP.06 需要字符转义时应优先使用raw string

- **规则ID**：0bd47a40-04d7-40d5-85c6-6b5900d6dfb1
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

raw string是反引号之间的字符序列，如`foo`。在反引号内，除反引号外的任何字符都可以出现。在需要转义的场景下，我们应该尽量使用raw string，这样可以避免手工转义及跨越多行等造成的阅读困难。若使⽤raw string，应注意如果反引号中的内容被⼿动换⾏了，将会在字符串中⾃动插⼊换⾏符。

**【正确示例】**

```
##### 场景1：字符串存在转义未使用raw string
- 修复示例：

  ```go
  const prefix = `package p; import "unsafe"; type P *struct{}; type I interface{}; type T ` // 符合：使用了Raw字符串去掉了反斜杠，字符串更容易阅读
  ```


```
**【错误示例】**

```
##### 场景1：字符串存在转义未使用raw string
- 错误示例：

  ```go
  const prefix = "package p; import \"unsafe\"; type P *struct{}; type I interface{}; type T " // 不符合：这是一句用于解析go程序的字符串定义
  ```


```
**【修复建议】**

字符串中存在字符转义时，优先使用raw string
