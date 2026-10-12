# G.MEM.03 使用[]byte而不是string存储敏感数据，敏感数据使用结束后应立即清0

- **规则ID**：477dbc8c-01dd-4e7d-bc3e-6089167ad324
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

使用string保存口令、秘钥等敏感信息时，这些敏感信息会一直在内存中直至被垃圾收集器回收，如果该进程的内存可dump，这些敏感信息就可能被泄露。

因此，严禁使用string存储敏感信息，要使用[]byte存储，使用结束后立即将[]byte清0。

**【正确示例】**

```
##### 场景1：使用string保存敏感数据
- 修复示例1：
    ```go
    const pwdMaxLen = 20
    func getPassword() (*[pwdMaxLen]byte, error) {
        f, err := os.Open("/secure_area/secue_dat")
        ...
        // 符合：使用[]byte存储敏感数据，使用结束后立即清0
        pwd := new([pwdMaxLen]byte) // 注：如直接定义数组，必须返回数组地址，以保证pwd数组本身会被创建在堆上
        _, err = f.Read(pwd[:])
        return pwd, err
    }

    func doSomething(){
        password, err := getPassword()
        if err != nil {
            ... // log & return
        }
        verifyPassword(password)
        // 注：如果 getPassword() 到清除位置上可能导致异常，应确保异常分支敏感内存数据也得到清理
        for i := 0; i < len(password); i++{
            password[i] = 0
        }
    }

    func verifyPassword(pwd []byte) {
        ...
    }
    ```
- 修复示例2：
    ```go
    func main() {
        password := flag.String("pwd", "", "")
        flag.Parse()
        ...
        fmt.Printf("before clear=%s
", *password)
        // 符合：三方件中使用string存储敏感数据，可在使用结束后通过非类型安全指针（unsafe）方式进行清0
        clearStringMemory(*password)
        fmt.Printf("after clear=%s
", *password)
    }
    func clearStringMemory(s string){
        /* 对单个字符表示的字符串，Go的runtime实现的字符串共享字符数据，位于统一的一个staticbytes数组中，
         * 所以禁止清除它，否则程序后面运行时所有从单个字符解析出的字符串为'\0'值；避免设置口令、密码等敏感信息的长度小于等于1
         */
        if len(s) <= 1 {
            return
        }
        bs := *(*[]byte)(unsafe.Pointer(&s))
        for i := 0; i < len(bs); i++{
            bs[i] = 0
        }
    }
    ```

```
**【错误示例】**

```
##### 场景1：使用string保存敏感数据
- 错误示例：
    ```go
    func doSomething() {
        pass := getPassword()  // 不符合：变量`pass`属于敏感信息
        verifyPassword(password)
    }

    func getPassword() string {
        ...
    }

    func verifyPassword(pwd string) {
        ...
    }
    ```

```
**【修复建议】**

1. 不使用string类型存储敏感数据，使用[]byte存储敏感数据，使用结束后立即清0。

2. 三方件中使用string存储敏感数据，可在使用结束后通过非类型安全指针（unsafe）方式进行清0。

3. 待清理的字符串（包含敏感信息）必须是在堆上构造的字符串。禁止清理静态的字符串，否则会因为修改静态字符串，而导致panic的问题。对动态分配的、值是读取的字符串，则不会出现修改静态分配的字符串问题。
