# G.FUN.01 函数功能要单一

- **规则ID**：2ae3a240-84bb-4a35-b15b-f0e5057bc4ef
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

函数功能要单一，过长的函数往往意味着函数功能不单一，可以进行进一步拆分或分层。过于复杂的函数不利于阅读理解，难以维护。



项目组可从如下维度间接衡量函数功能是否单一 (具体阈值可根据实际情况调整)：



- 函数行数，建议不超过50行（非空非注释）

- 函数的参数个数，建议不超过5个

- 函数最大代码块嵌套深度，建议不超过4层

- 函数的返回值个数不超过3个

**【正确示例】**

```
##### 场景1：函数的代码块嵌套深度超过4层
- 修复示例：

  ```go
  // 符合：使用卫语句
  func testFuncDepthAndParams5() {
      a := 1
      b := 2
      c := 3
      d := 4
      e := 5
      f := 6
      fmt.Println(b)
      if test1 != a {
          return
      }
      if test2 != b {
          return
      }
      if test3 != c {
          return
      }
      if test4 != d {
          return
      }
      if test5 != e {
          return
      }
      if test6 != f {
          return
      }
      fmt.Println(a)
  }
  ```
##### 场景2：函数过长
- 修复示例：可以进行进一步拆分或分层

    ```go
    func testFunc() {
        func1()
        func2()
        ... // 符合：不超过50行的函数内容
    }
    ```
##### 场景3：函数参数超过5个
- 修复示例：对方法进行抽象或重构，或者将参数合并成一个结构体传入。

    ```go
    type data {
        a int,
        b int,
        c int,
        d int,
        e int,
        f int
    }

    func testFunc(d data) { // 符合
        ...
    }
    ```
##### 场景4：函数返回值超过3个
- 修复示例：将返回值合并成一个结构体返回

    ```go
    type data {
        a int,
        b int,
        c int,
        d int,
    }

    func testFunc() data { // 符合
        ...
        return data{
            a: xx,
            b: xx,
            c: xx,
            d: xx,
        }
    }
    ```


```
**【错误示例】**

```
##### 场景1：函数的代码块嵌套深度超过4层
- 错误示例：
  ```go
  // 不符合
  func testFuncDepthAndParams5() {
      a := 1
      b := 2
      c := 3
      d := 4
      e := 5
      f := 6
      if test1 == a {
          if test2 == b {
              if test3 == c {
                  if test4 == d {
                      if test5 == e {
                          if test6 == f {
                              fmt.Println(a)
                          }
                      }
                  }
              }
          }
      }
      fmt.Println(b)
  }
  ```
##### 场景2：函数过长
- 错误示例：
  ```go
  func testFunc() {
      ... // 不符合：超过50行的函数内容
  }
  ```
##### 场景3：函数参数超过5个
- 错误示例：
  ```go
  func testFunc(a, b, c, d, e, f int) { // 不符合：参数过多
      ...
  }
  ```
##### 场景4：函数返回值超过3个
- 错误示例：
  ```go
  func testFunc() (a, b, c, d int) { // 不符合：返回值过多
      ...
  }
  ```


```
**【修复建议】**

1. 过长的函数：可以进行进一步拆分或分层。

2. 过多的函数参数：可以考虑如下优化方式：

    - 对方法进行抽象或重构

    - 将相关参数合在一起，定义成结构体

3. 过多的返回值：可以考虑将其中关系密切的返回值参数封装成一个结构体。

4.  过深的嵌套：使用卫语句可以有效的减少if相关的嵌套层次。
