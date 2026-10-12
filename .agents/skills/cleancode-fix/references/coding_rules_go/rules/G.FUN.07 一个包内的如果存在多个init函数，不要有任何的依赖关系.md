# G.FUN.07 一个包内的如果存在多个init函数，不要有任何的依赖关系

- **规则ID**：2e2dec12-1b8a-428d-8410-b691eb102f72
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

如果包内有多个init函数，每个init函数的执行顺序是不确定的，因此互相之间不应有依赖，即：不要在多个init函数之间，依赖变量（或资源）的初始化顺序。

**【正确示例】**

```
##### 场景1：包内init函数间存在依赖
- 修复示例：
  ```go
  // 符合：修改逻辑，解除包内init函数间存在的依赖

  // file1
  package multiple_independent1

  var kb int

  func init() {
      kb = 1024
  }

  // file2
  package multiple_independent1

  var mb int

  func init() {
      kb := 1024
      mb = 1024 * kb
  }
  ```


```
**【错误示例】**

```
##### 场景1：包内init函数间存在依赖
- 错误示例：kb在file1和file2之间存在依赖

  ```go

  // flie1
  package multiple_dependent1

  var kb int

  func init() {
      kb = 1024
  }

  // file2
  package multiple_dependent1

  var mb int

  func init() {
      mb = 1024 * kb // 不符合：kb的初始化在另一个init函数中
  }
  ```


```
**【修复建议】**

对包内存在依赖关系的init进行解耦
