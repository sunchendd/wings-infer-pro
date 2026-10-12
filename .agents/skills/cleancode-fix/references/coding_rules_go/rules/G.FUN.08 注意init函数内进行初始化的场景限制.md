# G.FUN.08 注意init函数内进行初始化的场景限制

- **规则ID**：daeeb603-8525-4eb3-a2f6-175e0a725a81
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

由于init函数没有返回值，如果init函数内发生初始化失败，只能通过异常来反馈错误。因此，应该慎用init函数进行复杂的初始化动作。

**【正确示例】**

```
##### 场景1：init函数中包含文件打开操作
- 修复示例

  ```go
  // 符合：将文件打开操作删除或移出init函数

  package huaweifunction08

  import "fmt"

  func init(i int) {
      fmt.Println("init in main.go ")
  }
  ```
##### 场景2：函数中调用可能抛出异常的函数
- 修复示例

  ```go
  // 符合：将可能抛出异常的函数调用移出init函数

  package huaweifunction08

  import "fmt"

  func init(i int) {
      fmt.Println("init in main.go ")
  }
  ```


```
**【错误示例】**

```
##### 场景1：init函数中包含文件打开操作
- 错误示例：

  ```go
  package huaweifunction08

  import (
      "fmt"
      "io/ioutil"
  )

  func init() {
      fileInfos, err := ioutil.ReadDir("./dir/") // 不符合
      if err != nil {
          return
      }
      for _, info := range fileInfos {
          if info.IsDir() {
              fmt.Println(info.Name(), "\\")
          }
      }
  }
  ```
##### 场景2：函数中调用可能抛出异常的函数
- 错误示例：
  ```go

  package huaweifunction08

  import "fmt"

  func init(i int) {
      foo() // 不符合：此函数可能抛异常
      fmt.Println("init in main.go ")
  }

  func foo() {
      panic("error")
  }
  ```


```
**【修复建议】**

建议使用init函数时需符合以下规定：



- 避免在init函数中进行如申请资源、打开文件、连接数据库等可能失败的操作

- 避免在init函数中调用可能抛出异常的函数
