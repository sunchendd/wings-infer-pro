# GoFence默认语义清理规则

- **规则ID**：48156c37-23c9-4a46-908b-5aca63ab2e7d
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

语义清理规则用于清理特殊语义下程序不出现错误的情况，如os.Args[0]的访问

**【正确示例】**

```
```
func parseFatalln() string {
  if len(os.Args) < 2 {
    log.Fatalln("pass a filename to save the profile in.")
  }
  filePath := os.Args[1] // ok
  return filePath
}
```

```
**【错误示例】**

```
GoFence默认语义清理规则，在还有特殊访问如os.Args[0]情形下，不勾选语义清理规则，会有越界的误报产生

```
**【修复建议】**

特殊语义下程序不出现错误的情况，如os.Args[0]的访问，勾选语义规则，有效防止误报。
