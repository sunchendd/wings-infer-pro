# GoFence 默认命令注入检测规则

- **规则ID**：b18ff87c-a908-48c9-b857-189b2d29c731
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

命令注入是指开发者使用未经校验的不可信输入作为系统命令的参数或命令的一部分，使得攻击者可以利用这个漏洞构造相关系统命令语句，执行一些非法越权操作。在`Go`中，`os/exec`经常被用来调用一个新的进程，如果被执行的命令拼接了外部不可信输入，则可能会产生命令和参数注入

**【正确示例】**

```
```
func CommandInjectBySyscallExec() {
	fmt.Println("====== CommandInjectBySyscallExec ======")
	var injectParam = ".;echo inject success."
	cmd := fmt.Sprintf("ls %s", injectParam)
	cmdSh, err := exec.LookPath("sh")
	if err != nil {
		fmt.Println(err)
	}
	fmt.Println("===", syscall.Exec(cmdSh, []string{cmdSh, "-c", cmd}, os.Environ()))

}
```

```
**【错误示例】**

```
```
func CommandInjectByExecCommand(externalCmd string) {
cmdSh, err := exec.LookPath("sh")
	if err != nil {
		fmt.Println(err)
	}
	command := exec.Command(cmdSh, "-c", externalCmd)
	err = command.Run()
	if err != nil {
		fmt.Println(err)
	}
}
```

```
**【修复建议】**

命令执行的字符串不要去拼接输入的参数，如果必须拼接时，则需要对输入参数进行白名单过滤；

对传入的参数要做类型校验。例如整数数据，需要对数据进行整数强制转换；

保证格式化字符串的正确性。例如int类型参数的拼接对于参数要用`%d`，不能用`%s`

---------参考华为go语言安全编程2.1
