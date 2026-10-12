# G.FIO.01 临时文件使用完毕必须及时删除

- **规则ID**：1b9eb9fe-c72e-495d-9600-3a9db845aa34
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

临时文件使用完毕后不删除会占用系统资源，不断积累甚至可导致空间爆满，进而影响程序正常运行，另外，攻击者可能会利用临时文件进行恶意操作，从而导致安全问题。

因此，临时文件使用完毕必须及时删除。

**【正确示例】**

```
##### 场景1：临时文件使用完毕后未删除。
- 修复示例：临时文件使用完毕必须删除。

    ```go
    package main

    import (
        "fmt"
        "io/ioutil"
        "os"
    )

    func closeAndRemove(f *os.File) {
        f.Close()
        os.Remove(f.Name()) // 符合：显式地调用os.Remove()删除临时文件
    }

    func main() {
        f, err := ioutil.TempFile("/opt/pwm", "prefix")
        if err != nil {
            fmt.Println("Create temp file failure.")
            return
        }

        defer closeAndRemove(f) // 符合：调用关闭并删除函数
        _, err = f.Write([]byte("This is a example."))
        if err != nil {
            // error process 省略
        }
    }
    ```


```
**【错误示例】**

```
##### 场景1：临时文件使用完毕后未删除。
- 错误示例：

    ```go
    func main() {
        f, err := ioutil.TempFile("/opt/pwm", "prefix")
        if err != nil {
            fmt.Println("Create temp file failure.")
            return
        }
        defer f.Close() // 不符合: 临时文件虽然被关闭，但未被删除

        _, err = f.Write([]byte("This is a example."))
        if err != nil {
            // error process 省略
        }
    }
    ```


```
**【修复建议】**

临时文件使用完毕必须删除。
