# G.OTH.03 删除无效或永不执行的代码

- **规则ID**：a980800f-da1f-40b1-a84d-c9e66c2ed07d
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

无效或永不执行的代码（即无效代码或无法访问的代码）通常是编程错误的结果，并且可能导致意外行为。

因此，应该主动识别并删除无效或永不执行的代码。

**【正确示例】**

```
##### 场景1：无效或永不执行的代码未删除
- 修复示例：重新整理逻辑，删除无效或永不执行的代码。

  ```go
  // 符合
  func Foo(condition int) int {
      var i *int
      if condition == 1 {
          i = new(int)
          return 0
      }
      return 0
  }
  ```
##### 场景2：if/else if语句序列中相同的条件会自动导致无效代码
- 修复示例：修改重复的分支条件

  ```go
  // 符合
  func Foo() {
      if param == 1 {
          DoSomething1()
      } else if param == 2 {
          DoSomething2()
      } else if param == 3 { // 符合
          DoSomething3()
      } else {
          ...
      }
  }
  ```
##### 场景3：if条件中的逻辑操作包含常量操作数false
- 修复示例：修改常量操作数的相关逻辑

  ```go
  func Foo() {
      var condition = false
      ... // 包含condition的赋值逻辑
      if a < b && condition {
          doSomething()
      }
  }
  ```
##### 场景4：变量自己赋值给自己
- 修复示例：删除或重新优化代码。

  ```go
  // 符合
  func Foo() {
      var a int32
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：无效或永不执行的代码未删除
- 错误示例：

  ```go
  func Foo(condition int) int {
      var i *int
      if condition == 1 {
          i = new(int)
          return 0
      }
      if i != nil {
          ... // 不符合：变量i为nil，此处代码不可达
      }
      return 0
  }
  ```
##### 场景2：if/else if语句序列中相同的条件会自动导致无效代码
- 错误示例：

  ```go
  func Foo() {
      if param == 1 {
          DoSomething1()
      } else if param == 2 {
          DoSomething2()
      } else if param == 1 { // 不符合： 条件重复，永远不成立
          DoSomething3()
      } else {
          ...
      }
  }
  ```
##### 场景3：if条件中的逻辑操作包含常量操作数false
- 错误示例：

  ```go
  func Foo() {
      const condition = false
      ...
      if a < b && condition { // 不符合：if条件中的逻辑操作包含常量操作数false
          doSomething()
      }
  }
  ```
##### 场景4：变量自己赋值给自己
- 错误示例：

  ```go
  func Foo() {
      var a int32
      a = a // 不符合：需删除无效代码
      ...
  }
  ```


```
**【修复建议】**

删除无效或永不执行的代码，如：死代码、恒真/恒假的表达式、空代码块、未被引用的代码等。
