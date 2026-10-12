# G.CGO.05 在CGO中避免使用C代码调用Go函数

- **规则ID**：4029cb19-4df1-4727-a338-9568fde4da05
- **更新时间**：2026-04-07 04:20:00

---

**【问题级别】**

一般

**【描述】**

在CGO中如果使用C代码调用Go函数，使用不当有可能导致系统崩溃问题。

因此，建议在CGO中C代码不要调用Go函数。

**【正确示例】**

```
##### 场景1：在CGO中C代码调用Go函数。
- 修复示例：建议在CGO中C代码不要调用Go函数。

    ```go
    // my.h
    int add(int a, int b);
    // my.c
    #include "my.h"

    int addimpl(int a, int b);

    int add(int a, int b) {
        return addimpl(a, b); // 符合：C代码没有调用Go函数
    }

    int addimpl(int a, int b) {
        return a + b
    }
    // main.go
    package main

    import "fmt"

    // #cgo CFLAGS: -I.
    // #cgo LDFLAGS: -L. -lmy
    // #include "my.h"
    import "C"

    func main() {
        fmt.Printf("%v", C.add(1, 2)) // 符合：仅Go调用了C代码
    }
    ```


```
**【错误示例】**

```
##### 场景1：在CGO中C代码调用Go函数。
- 错误示例：Go调用了C代码，C代码又反过来调用了Go。

    ```go
    // my.h
    int add(int a, int b);
    // my.c
    #include "my.h"

    int addimpl(int a, int b);
    int add(int a, int b) {
        return addimpl(a, b); // 不符合：调用Go函数
    }
    // main.go
    package main

    import "fmt"

    // #cgo CFLAGS: -I.
    // #cgo LDFLAGS: -L. -lmy
    // #include "my.h"
    import "C"

    //export addimpl
    func addimpl(a, b C.int) C.int {  // 不符合：addimpl函数通过export导出并在C函数add中调用，导致出现嵌套调用
        return a + b
    }

    func main() {
        fmt.Printf("%v", C.add(1, 2))
    }
    ```


```
**【修复建议】**

建议在CGO中C代码不要调用Go函数。
