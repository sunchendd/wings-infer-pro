# G.RES.01 避免资源泄漏

- **规则ID**：371395cc-73f9-4f59-8b1c-8c189087852d
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

应在同一代码抽象层对资源进行管理，例如，提供了函数或方法用于申请资源的包也应该提供释放该资源的函数或方法。



在程序每个可能走到控制流中，应确保完整的释放文件句柄、DB连接等资源。特别是，当错误或异常发生时，若申请的资源（如文件句柄、数据库连接、内存资源等）未得到释放，会引起资源异常占用，可能会导致系统崩溃或者不可用。因为有的资源需要在程序退出的时候释放，所以实际实现的时候，不能强制必须用defer；尽量显式去做资源释放；能够用defer来做释放操作可尽量使用defer。



goroutine是Go语言并行设计的核心，启动一个goroutine就会做一个入栈操作，在系统不退出的情况下，goroutine也没有设置退出条件，则相当于goroutine失去了控制，它占用的资源无法回收，可能会导致内存泄露。



某些对程序外部的操作（如通过 cgo进⾏较低层的操作等）可能无法在合理的时间范围内执行完毕。此时可以考虑把这类外部操作放到独立的进程中执行，⽽不是放到当前进程内的goroutine。



应确保：



主程序结束，所有goroutine默认都会退出，但是有可能不是安全退出，有一些通道的数据可能还没有处理完，有些资源没有安全释放，所以要有安全的通知goroutine结束机制（比如context包）。

主程序没有结束，但是有些goroutine已经不再使用，此时应该保证goroutine及时退出，不要发生泄漏。

**【正确示例】**

```
func test_good04(){
 db, err := sql.Open("postgres", "user=astaxie password=astaxie dbname=test sslmode=disable")
 defer func(){
  defer db.close()
 }()
}

```
**【错误示例】**

```
func test_bad02(){
 db, err := sql.Open("postgres", "user=astaxie password=astaxie dbname=test sslmode=disable")//没有对db释放，告警
 if err != nil {
  fmt.Printf("stmt err:%s
", err)
  return
 }
 //在if 语句之外没有检查到释放函数close，不合法告警
}

```
**【修复建议】**

正确释放使用的资源
