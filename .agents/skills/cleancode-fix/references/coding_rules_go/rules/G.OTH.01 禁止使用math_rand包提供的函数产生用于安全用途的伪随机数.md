# G.OTH.01 禁止使用math/rand包提供的函数产生用于安全用途的伪随机数

- **规则ID**：7877d21e-e07a-4d21-8cf1-8e33f6dc4070
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

在安全用途场景下，使用`math/rand`包提供的函数生成的不安全随机数，可能会导致严重的安全漏洞。

因此，应禁止使用`math/rand`包提供的函数产生用于安全用途的伪随机数，必须使用安全的随机数产生方式。

典型的安全用途场景包括（但不限于）以下几种：

- 会话标识SessionID的生成

- 挑战算法中的随机数生成

- 验证码的随机数生成

- 用于密码算法用途（例如用于生成IV、盐值、密钥等）的随机数生成

**【正确示例】**

```
##### 场景1：math/rand用于盐值的随机数生成。
- 修复示例：在安全用途场景下，应禁止使用`math/rand`包提供的函数产生的随机数，必须使用`crypto/rand`提供的安全的随机数产生方式。

    ```go
    package main

    import (
        "crypto/rand" // 安全随机数
        "fmt"
    )

    func main() {
        saltLength := 32
        salt := make([]byte, saltLength)
        // 符合： 使用rand.Read()生成的盐值是安全的
        if _, err := rand.Read(salt); err != nil {
            fmt.Printf("rand.Read() error : %v
", err)
            return
        }
        ...
    }
    ```


```
**【错误示例】**

```
##### 场景1：math/rand用于盐值的随机数生成。
- 错误示例：

    ```go
    package main

    import (
        "math/rand" // 不安全随机数
        "fmt"
    )

    func main() {
        saltLength := 32
        salt := make([]byte, saltLength)
        // 不符合： 使用math/rand生成的盐值是不安全的
        if _, err := rand.Read(salt); err != nil {
            fmt.Printf("rand.Read() error : %v
", err)
            return
        }
        ...
    }
    ```


```
**【修复建议】**

1. 在安全用途场景下，应禁止使用`math/rand`包提供的函数产生的随机数，必须使用`crypto/rand`提供的安全的随机数产生方式。

2.  非安全用途场景可按误报处理。
