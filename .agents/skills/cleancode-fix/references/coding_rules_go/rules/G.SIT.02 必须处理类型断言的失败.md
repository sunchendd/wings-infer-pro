# G.SIT.02 必须处理类型断言的失败

- **规则ID**：bd878696-4fe7-4b85-ad26-c9285e196d01
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

如果断言失败仍然继续执行，可能导致panic，从而导致程序因运行时错误而崩溃。

因此，必须处理类型断言的失败。

**【正确示例】**

```
##### 场景1：未处理类型断言的失败
- 修复示例1：使用类型断言判断是否为对应类型的变量：
    ```go
    func Foo(a interface{}) {
        value, ok := a.(string) // 符合：使用类型断言判断是否为对应类型的变量
        if !ok {
            fmt.Println("It's not ok for type string")
            return
        }
        fmt.Println("The value is ", value)
    }
    ```
- 修复示例2：对于模块的接口函数，在使用的外部输入的接口变量时，当它封装的目标类型为引用/指针的类型，在使用引用/指向的值之前，还应判断引用/指针值不为nil：
    ```go
    func Foo(a interface{}) {
        pvalue, ok := a.(*int) // 符合：使用类型断言判断是否为对应类型的变量
        if !ok || pvalue == nil { // 符合：除了判断断言成功，同时，判断指针值不为nil
            fmt.Println("It's not ok for type *int")
            return
        }
        fmt.Println("The value is ", *pvalue)
    }
    ```
- 修复示例3：下述类型断言的例子，如果类型断言失败，则走default分支。
    ```go
    func Bar(t interface{}) {
        // other process
        switch t := t.(type) {
        default: // 符合：必须有`default`分支用于处理类型断言匹配失败的情况
            fmt.Printf("unexpected type %T", t) // %T prints whatever type t has
        case bool:
            fmt.Printf("boolean %t
", t) // t has type bool
        case int:
            fmt.Printf("integer %d
", t) // t has type int
        case *bool:
            fmt.Printf("pointer to boolean %t
", *t) // t has type *bool
        case *int:
            fmt.Printf("pointer to integer %d
", *t) // t has type *int
        }
        // other process
    }
    ```


```
**【错误示例】**

```
##### 场景1：未处理类型断言的失败
- 错误示例：如下代码如果a不为string类型，会触发panic.
    ```go
        fmt.Println("Where are you,Jonny?", a.(string)) // 不符合
    ```


```
**【修复建议】**

1. 对非引用的目标类型，确保类型断言成功，可防止结果值是一个对应目标类型的空值，以避免程序逻辑错误

2. 对目标类型为引用（或指针）类型的类型断言，如果类型断言成功，在使用类型断言结果前，确保类型断言获得的引用类型变量值不为空指针，以防止类型断言成功，但返回结果值为空值的情况
