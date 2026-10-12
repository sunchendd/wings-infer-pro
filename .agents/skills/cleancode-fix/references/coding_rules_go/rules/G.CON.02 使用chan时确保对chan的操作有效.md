# G.CON.02 使用chan时确保对chan的操作有效

- **规则ID**：5d465891-5700-4ec4-9c47-0dc471bb244c
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

确保chan在使用前已经被初始化，禁止对nil和closed的chan进行操作，否则可能导致如下问题：



关闭closed的channel会产生panic

关闭nil的channel会产生panic

向closed的channel发送数据会产生panic

当chan中没有数据时，从closed的channel接收数据，会返回该chan类型对应的零值（所以为了确保接收的数据有效，从chan读取数据时，必须通过comma ok的方式检查chan是否成功读取到有效数据，否则可能导致读取到非预期的零值消息。若代码接收到chan消息就退出当前的消息循环，则可不判断返回值，但应该对 <-返回元组的第二个值使用 _ 惯用法主动忽略）

**【正确示例】**

```
func foo(c chan int) {

   defer close(c) // 【修改】使用defer延迟关闭channel

   for {

       err := processBusiness()

       if err != nil {

           c <- 0

           // 【修改】删除重复关闭channel方法

           return

      }

       c <- 1

  }

}

```
**【错误示例】**

```
func foo(c chan int) {

   defer close(c)

   for {

       err := processBusiness()

       if err != nil {

           c <- 0

           close(c) // 【错误】重复释放channel

           return

      }

       c <- 1

  }

}

```
**【修复建议】**

不要重复释放资源
