# G.FIO.05 临时文件使用完毕必须及时删除

- **规则ID**：871f336b-07eb-433c-b29d-b9ec4de34ef7
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

程序中有很多使用临时文件的场景，比如用于进程间的数据共享，缓存内存数据，动态构造的类文件，动态连接库文件等。临时文件可能创建于操作系统的共享临时文件目录，例如，POSIX系统下的/tmp与/var/tmp目录，Windows系统下的C:\TEMP目录，这类目录中的文件可能会被定期清理。创建在其他路径下的临时文件不会被自动清理。如果文件未被安全地创建或者用完后还是可访问的，具备本地文件系统访问权限的恶意用户便可以利用共享目录中的文件进行恶意操作，另外，临时文件不清理也可能会导致大量垃圾文件占用磁盘的存储空间。删除已经不再需要的临时文件有助于对文件名和其他资源进行回收利用。每一个程序在正常运行过程中都有责任确保已使用完毕的临时文件被删除。

**【正确示例】**

```
##### 场景1：临时文件没删除
- 修复示例：使用了delete方法删除了tempFile文件

```java
private void doSomething(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException{
    File tempFile = null;
    try {
        tempFile = File.createTempFile("temp", "1234");

        /* Set the permissions to avoid insecure temporary file incidentals  */
        if (!tempFile.setWritable(true, true)) {
            System.out.println("Could not set Writable permissions");
        }
        ...
    } catch (IOException exceptIO) {
        System.out.println("Could not create temporary file");
    } finally {
        /* Delete the temporary file manually */
        if (tempFile.exists()) {
            tempFile.delete();
        }
    }
}
```


```
**【错误示例】**

```
##### 场景1：临时文件没删除
- 错误示例：tempFile没有删除操作

```java
@Override
public void doSomething(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
    File tempFile = null;
    try {
        // 【不符合】 临时文件使用完毕应及时删除
        tempFile = File.createTempFile("temp", "1234");

        // 当调用deleteOnExit()方法时，只是相当于对deleteOnExit()作一个声明，当程序运行结束，JVM终止时才真正调用deleteOnExit()方法实现删除操作。
        tempFile.deleteOnExit();

        /* Set the permissions to avoid insecure temporary file incidentals  */
        if (!tempFile.setWritable(true, true)) {
            System.out.println("Could not set Writable permissions");
        }
        ...
    } catch (IOException exceptIO) {
        System.out.println("Could not create temporary file");
    }
}
```


```
**【修复建议】**

临时文件在使用结束后必须删除。
