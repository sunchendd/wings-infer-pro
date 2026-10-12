# G.RES.03 禁止重复释放资源

- **规则ID**：45ee545a-d0ea-4a30-b11f-ac63cf68c677
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

重复释放一般存在于错误处理流程判断中，如果恶意攻击者构造出错误条件使程序重复释放channel，则会触发运行时错误，从而造成DoS攻击。



重复close文件对象，在特殊的os的ﬁle实现中也可能会导致问题。对sql.DB对象和网络连接的close同样如此。



因此禁止重复释放资源。要求：



1、禁止重复释放文件、数据库对象、网络连接等对象资源

2、禁止重复释放channel等系统内置类型的对象资源

**【正确示例】**

```
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

```
**【错误示例】**

```
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

```
**【修复建议】**

禁止重复释放资源。要求：



1、禁止重复释放文件、数据库对象、网络连接等对象资源

2、禁止重复释放channel等系统内置类型的对象资源
