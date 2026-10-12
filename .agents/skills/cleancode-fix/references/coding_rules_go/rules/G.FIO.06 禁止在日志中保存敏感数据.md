# G.FIO.06 禁止在日志中保存敏感数据

- **规则ID**：c19bb586-bfdc-4f57-bf7c-f922e25b6add
- **更新时间**：2025-06-05 04:20:02

---

**【问题级别】**

严重

**【描述】**

在日志中不能保存口令（包括明文口令和密文口令）、密钥和其它敏感信息。对于敏感信息建议采取以下方法：



1、不在日志中打印敏感信息；

2、不将敏感信息输出到控制台和串口；

3、若因为特殊原因必须要打印日志，则用固定长度的星号（*）代替输出的敏感信息；

4、序列化或输出敏感信息应先加密后，输出到外部设备或文件中，如磁盘文件。参考规则7.4。



敏感数据的具体范围取决于产品具体的应用场景，产品应根据风险进行分析和判断。典型的敏感数据包括口令、银行账号、个人信息、通讯记录、密钥等。如果在传递异常的时候没有对敏感信息进行过滤，则有可能会导致敏感信息泄露，这有可能帮助攻击者尝试发起进一步的攻击，攻击者可以通过构造恶意的输入参数来发掘应用的内部结构和机制。



不管是错误中的文本消息，还是错误本身的类型都可能泄露敏感信息。例如error中的错误消息会透露文件系统的结构信息，而通过错误本身的类型，可以得知所请求的文件不存在。因此，当错误会被传递到信任边界以外时，必须同时对敏感的错误消息和敏感的错误类型进行过滤。

**【正确示例】**

```


```
**【错误示例】**

```
package passwd
func GetIP(IP string) string {
 return IP
}
func test_bad01() {
 sss := "opt/../limit/ssa/focus/etc"
 f := "-f"
 IP := "255.255.255.3"
 passwd := "p2222s"
 pwd := passwd
 log.Printf("information is %v  %v  %v  %v
", GetIP(IP), passwd, IP, sss, pwd)//将敏感信息打印到日志中,所以告警
 cmd := exec.Command("rm ", f, "/"+sss) //t0
 //fmt.Printf("Windows path is %s,  %s", cmd.Path, cmd.Args)
 err := cmd.Run()
 if err != nil {
  fmt.Println("Widows delete file error.", err)
 }
 log.Printf("information is %v   %v  %v
", passwd, IP, sss)//将敏感信息打印到日志中,所以告警
 log.Println(pwd)
}

```
**【修复建议】**

不要将敏感信息保存在日志中或将其输出到控制台及串口
