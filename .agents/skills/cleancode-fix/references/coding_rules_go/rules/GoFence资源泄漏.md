# GoFence资源泄漏

- **规则ID**：c0449612-f9a2-4953-a875-744623da3a70
- **更新时间**：2026-04-07 04:20:00

---

**【问题级别】**

一般

**【描述】**

每个可能走到控制流中的分支，应确保能完整的释放文件句柄、DB连接等资源。当错误或异常发生时，若

申请的资源（如文件句柄、数据库连接、内存资源等）未得到释放，会引起资源异常占用，可能会导致系统崩溃或

资源的泄漏。所以在实际实现资源释放时时，尽量显式去做资源释放；能够用defer来做释放操作可尽量使用defer

**【正确示例】**

```
```
func Contents(filename string) (string, error) {
       f, err := os.Open(filename)
       if err != nil {
               return "", err
       }
       defer f.Close() // f.Close 会在函数结束后运行

       var result []byte
       buf := make([]byte, 100)
       for {
               n, err := f.Read(buf[0:])
               result = append(result, buf[0:n]...)
               if err != nil {
                       if err == io.EOF {
                               break
                       }
                       fmt.Println("==北凉徐凤年==")
                       return "", err // 在这里返回后，f 在这里关闭

               }
       }
       fmt.Println("==庆国范闲==")
       fmt.Println(string(result))
       return string(result), nil // 在这里返回后，f 在这里关闭

}
```

```
**【错误示例】**

```
```
func Contents(filename string) (string, error) {
       f, err := os.Open(filename)
       if err != nil {
               return "", err
       }
       var result []byte
       buf := make([]byte, 100)
       for {
               n, err := f.Read(buf[0:])
               result = append(result, buf[0:n]...)
               if err != nil {
                       if err == io.EOF {
                               break
                       }
                       fmt.Println("==北凉徐凤年==")
                       return "", err // 在这里返回后，f 在这里未关闭

               }
       }
       fmt.Println("==庆国范闲==")
       fmt.Println(string(result))
       return string(result), nil // 在这里返回后，f 在这里未关闭

}
```

```
**【修复建议】**

资源一旦打开或者请求，及时关闭相关资源
