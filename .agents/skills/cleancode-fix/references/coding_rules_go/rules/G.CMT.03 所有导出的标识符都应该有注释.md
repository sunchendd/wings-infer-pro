# G.CMT.03 所有导出的标识符都应该有注释

- **规则ID**：2262cfbd-f4c7-4526-bab6-4dd0800c42fd
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

提示

**【描述】**

包内导出的标识符都应该有注释，用于说明导出标识符的作用，使用时的注意事项等信息，避免简单地重复标识符的名称。



注释应该以所描述的标识符开头。

**【正确示例】**

```
##### 场景1：标识符注释只简单重复符号名称
- 修复示例：使用注释说明导出符号（函数）的作用。

  ```go
  // 符合：注释说明了导出符号（函数）的作用

  // LookupHostAddress try enumerate the addresses of all interfaces in the host, get error if enumerate failed.
  func LookupHostAddress(host string) ([]string, error)
  ```


```
**【错误示例】**

```
##### 场景1：标识符注释只简单重复符号名称
- 错误示例：

  ```go
  // 不符合：该标识符注释只简单重复符号名称

  // LookupHostAddress
  func LookupHostAddress(host string) ([]string, error)
  ```


```
**【修复建议】**

给导出标识符增加注释，说明导出符号（函数）的作用。

注释应该以所描述的标识符开头。
