# G.OTH.05 避免调用os.Exit()和runtime.Goexit()退出函数

- **规则ID**：ef244b0c-ed7a-4bbc-b54a-e74c36439c98
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

调用`os.Exit()`函数退出，无法执行相应的`defer`函数，可能会导致某些资源无法清除。

调用`runtime.Goexit()`函数退出`goroutine`，虽然能执行相应的`defer`函数, 但`defer`函数中的`recover`函数无法捕获到`err`错误，可能会导致某些状态难以得到有效恢复。

因此，应避免调用以上2个函数。

**【正确示例】**

```
##### 场景1：调用`os.Exit()`函数退出。
- 修复示例：

```go
func CreateFile() error {
    f, err := ioutil.TempFile("/opt/pwm", "prefix")
    if err != nil {
        fmt.Println("Create temp file failure.")
        return err
    }
    defer closeAndRemove(f)
    _, err2 := f.Write([]byte("This is a example."))
    if err2 != nil {
        return err2  // 符合
    }
    return nil
}

func closeAndRemove(f *os.File) {
    f.Close()
    os.Remove(f.Name())
}
```
##### 场景2：调用`runtime.Goexit()`退出`goroutine`。
- 修复示例：

```go
func foo() error {
    ...
}

func bar() {
    go func() {
        defer func() {
            fmt.Println("defer!")
            fmt.Println("recovered = ",recover())
        }()

        ...
        err = foo()
        if err != nil {
           return // 符合
        }
    }()

    fmt.Println("bar")
}
```


```
**【错误示例】**

```
##### 场景1：调用`os.Exit()`函数退出。
- 错误示例：

```go
func CreateFile() {
    f, err := ioutil.TempFile("/opt/pwm", "prefix")
    if err != nil {
        fmt.Println("Create temp file failure.")
        return
    }
    defer closeAndRemove(f)
    _, err2 := f.Write([]byte("This is a example."))
    if err2 != nil {
        os.Exit(0) // 不符合：会导致临时文件无法清除
    }
}

func closeAndRemove(f *os.File) {
    f.Close()
    os.Remove(f.Name())
}
```
##### 场景2：调用`runtime.Goexit()`退出`goroutine`。
- 错误示例：

```go
func foo() error {
    ...
}

func bar() {
    go func() {
        defer func() {
            fmt.Println("defer!")
            // Goexit 导致无法捕获到`err`错误，error会为nil
            fmt.Println("recovered = ",recover())
        }()

        ...
        err = foo()
        if err != nil {
           runtime.Goexit() // 不符合
        }
    }()

    fmt.Println("bar")
}
```


```
**【修复建议】**

1. 除了main函数以外，禁止任何地方调用`os.Exit()`函数退出。

2. 禁止调用`runtime.Goexit()`退出`goroutine`。

3. 可通过错误值传递机制给调用者进行相应的处理。
