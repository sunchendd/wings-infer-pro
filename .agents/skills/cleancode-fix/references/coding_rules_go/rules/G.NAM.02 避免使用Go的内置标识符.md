# G.NAM.02 避免使用Go的内置标识符

- **规则ID**：7b824bdd-ae4e-4c42-981e-c254a99f1dee
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

Go语言规范声明了一些内置的标识符，使用这些内置标识符作为Go程序中的名称，将在当前作用域（和嵌套作用域）中隐藏原始的内置标识符，同时会造成代码难以理解，难以阅读，也容易引入潜在的错误。

**【正确示例】**

```
##### 场景1：下面的代码中使用内置名称string作为变量名称，使得代码难以理解，难以维护。
- 修复示例：修改变量名

  ```go
  func foo() string {
      // 符合：未使用内置标识符
      var str = "hello world"
      return str
  }
  ```


```
**【错误示例】**

```
##### 场景1：下面的代码中使用内置名称string作为变量名称，使得代码难以理解，难以维护。
- 错误示例：

  ```go
  func foo() string {
      // 不符合：使用了内置标识符string作为变量名
      var string string = "hello world"
      return string
  }
  ```


```
**【修复建议】**

修改标识符，不要使用Go内置的标识符。



内置标识符列表



| **分类** | **内置标识符**                                               |

| -------- | ------------------------------------------------------------ |

| 类型     | `bool byte complex64 complex128 error float32 float64 int int8 int16 int32 int64` `rune string uint uint8 uint16 uint32 uint64 uintptr` |

| 常量     | `true false iota`                                            |

| 零值     | `nil`                                                        |

| 函数     | `append cap close complex copy delete imag len make new panic print println real recover` |
