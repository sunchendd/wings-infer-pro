# G.EDV.02 禁止直接使用外部数据拼接命令参数

- **规则ID**：e7677657-4034-4f2b-9f87-c259cf5770b8
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

使用未经校验的不可信输入作为系统命令的参数或命令的一部分，可能会导致命令注入漏洞。对于命令注入漏洞，命令将会以与Go应用程序相同的特权级别执行，它向攻击者提供了类似系统shell的功能。



在Go中，os/exec经常被用来调用一个新的进程，如果被执行的命令来自于外部不可信输入，则可能会产生命令和参数注入。执行命令的时候，需要注意以下几点：



命令执行的字符串不要去拼接输入的参数，如果必须拼接时，则需要对输入参数进行白名单过滤；

对传入的参数要做类型校验。例如整数数据，需要对数据进行整数强制转换；

保证格式化字符串的正确性。例如int类型参数的拼接，对于参数要用%d，不能用%s；

**【正确示例】**

```
##### 场景1：调用OS命令解析器，也没有对入参做合法性校验
- 修复示例1：优先建议程序员禁止调用OS命令解析器，推荐使用其它标准API替代。

```go
// 删除指定的文件
func delFile(param string) {
    err := os.Remove(param) // 符合：使用Go的os.Remove()删除文件
    if err != nil {
        fmt.Println("delete file error.", err)
    }
}
// 后面代码相同，不再赘述...
```
- 修复示例2：出于特殊原因非得使用OS命令解析器，则需要使exec.Command()功能单一，同时对输入数据进行合法性校验。

```go
func delFile(param string) {
    // 符合：对输入参数进行合法性校验
    _, err := os.Stat(param)
    if err != nil && os.IsNotExist(err) {
        fmt.Println("The file not exist or format error.")
        return
    }
    // 符合：使exec.Command()功能单一
    cmd := exec.Command("rm", "-f", param)
    delErr := cmd.Run()
    if delErr != nil {
        fmt.Println("delete file error.")
    }
}
// 后面代码相同，不再赘述...
```

```
**【错误示例】**

```
##### 场景1：调用OS命令解析器，也没有对入参做合法性校验
- 错误示例：

```go
func Cmd_Injection_bad1(param string) {
    param1 := param
    // 不符合: 外部数据未校验
    cmd := exec.Command("/bin/bash", "-c", param1)
    err := cmd.Run()
    if err != nil {
        fmt.Println("cmd error.", err)
    }
}

func main() {
    if len(os.Args) < 2 {
        os.Exit(1)
    }
    file := os.Args[1];
    cmd := fmt.Sprintf("rm -f %v", file)
    Cmd_Injection_bad1(cmd)
}
```

```
**【修复建议】**

命令执行的字符串不要去拼接输入的参数，如果必须拼接时，则需要对输入参数进行白名单过滤；对传入的参数要做类型校验。例如整数数据，需要对数据进行整数强制转换；保证格式化字符串的正确性。例如int类型参数的拼接，对于参数要用%d，不能用%s；
