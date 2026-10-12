# G.CGO.02 避免将Go内存指针直接传入C函数使用

- **规则ID**：7f77b177-8076-4047-9e46-48cfa5a6ab74
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

将Go内存指针直接传入C函数使用，如果C函数执行时的是失效的Go指针，那么使用失效的指针将导致程序崩溃。

因此，避免将Go内存指针直接传入C函数使用。

**【正确示例】**

```
##### 场景1：直接将Go指针地址传入C函数。
- 修复示例：在需要将Go的字符串传入C语言时，先通过C.CString将Go语言字符串对应的内存数据复制到新创建的C语言内存空间上，再将C语言的内存传入C函数。请注意，使用该方式可以确保内存使用安全，但会导致效率下降。

    ```go
    package main

    /*
    #include "stdio.h"
    #include "stdlib.h"

    void printString(const char* s) {
        printf("%s", s);
    }
    */
    import "C"
    import "unsafe"

    func printString(s string) {
        cs := C.CString(s)
        defer C.free(unsafe.Pointer(cs))
        C.printString(cs) // 符合： 将Go内存通过C.String()复制一个C语言的内存再传入C函数
    }

    func main() {
        s := "hello"
        printString(s)
    }
    ```

```
**【错误示例】**

```
##### 场景1：直接将Go指针地址传入C函数。
- 错误示例：

    ```go
    package main

    /*
    #include "stdio.h"

    void printString(const char* s) {
        printf("%s", s);
    }
    */
    import "C"
    import "unsafe"

    func printString(s string) {
        C.printString((*C.char)(unsafe.Pointer(&s))) // 不符合： 直接将Go指针地址传入C函数
    }

    func main() {
        s := "hello"
        printString(s)
    }
    ```

```
**【修复建议】**

避免将Go内存指针直接传入C函数使用。

例如在需要将Go的字符串传入C语言时，先通过C.CString将Go语言字符串对应的内存数据复制到新创建的C语言内存空间上，再将C语言的内存传入C函数。请注意，使用该方式可以确保内存使用安全，但会导致效率下降。
