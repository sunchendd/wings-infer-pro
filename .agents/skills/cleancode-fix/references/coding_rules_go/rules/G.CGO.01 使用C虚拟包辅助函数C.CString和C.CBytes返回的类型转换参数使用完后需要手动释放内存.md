# G.CGO.01 使用C虚拟包辅助函数C.CString和C.CBytes返回的类型转换参数使用完后需要手动释放内存

- **规则ID**：b0304f7e-8445-4481-a178-0058a5d93ea1
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

C.CString、C.CBytes函数的返回值，由C语言的malloc函数分配，如果返回值未释放会导致内存泄露问题。

因此，C.CString、C.CBytes函数返回值不使用时需要通过C语言的free函数释放。

**【正确示例】**

```
##### 场景1：C.CString函数返回值未释放。
- 修复示例：

    ```go
    /*
    #include "stdio.h"
    #include "stdlib.h"
    */
    import "C"
    import "unsafe"

    func main() {
        cs := C.CString("Hello, World
")
        defer C.free(unsafe.Pointer(cs)) // 符合：使用C.CString后调用C.free函数释放对应内存
        C.puts(cs)
    }
    ```
##### 场景2：CBytes函数返回值未释放。
- 修复示例：

    ```go
    /*
    #include "stdio.h"
    #include "stdlib.h"
    */
    import "C"
    import "unsafe"

    func main() {
        bytes := []byte{1, 2}
        cbytes := C.CBytes(bytes)
        defer C.free(unsafe.Pointer(cbytes))// 符合：使用C.CBytes后调用C.free函数释放对应内存
        C.puts((*C.char)(cbytes))
    }
    ```

```
**【错误示例】**

```
##### 场景1：C.CString函数返回值未释放。
- 错误示例：

    ```go
    // #include "stdio.h"
    import "C"

    func main() {
        C.puts(C.CString("Hello, World
")) // 不符合：使用C.CString后未调用C.free函数释放内存
    }
    ```
##### 场景2：CBytes函数返回值未释放。
- 错误示例：

    ```go
    // #include "stdio.h"
    import "C"

    func main() {
        bytes := []byte{1, 2}
        C.puts((*C.char)C.CBytes(bytes)) // 不符合：使用C.CBytes后未调用C.free函数释放内存
    }
    ```

```
**【修复建议】**

C.CString、C.CBytes函数返回值不使用时需要通过C.free函数释放。
