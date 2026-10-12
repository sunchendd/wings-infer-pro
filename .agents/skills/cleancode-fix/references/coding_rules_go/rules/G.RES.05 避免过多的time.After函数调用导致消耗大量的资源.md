# G.RES.05 避免过多的time.After函数调用导致消耗大量的资源

- **规则ID**：ee7e1637-f246-4016-9f19-e1a995d6dd40
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

循环语句中使用time.After函数，可能导致过多的time.After函数调用导致消耗大量的资源，从而导致程序出问题。

因此，为了避免过多的time.After函数调用，不要在循环语句中使用time.After函数。

**【正确示例】**

```
##### 场景1：在循环语句中使用time.After函数。
- 修复示例：不要在循环语句中使用time.After函数，应该只使用（并复用）一个Timer值。

    ```go
    func longRunning(messages <-chan string) {
        // 符合：为了避免太多的Timer值被创建，应该只使用（并复用）一个Timer值
        timer := time.NewTimer(time.Minute)
        defer timer.Stop()
        for {
            select {
            case <-timer.C:
                return
            case msg, ok := <-messages:
                if !ok {
                    return
                }
                fmt.Println(msg)
                if !timer.Stop() {
                    <-timer.C // 重要：丢弃当前的过期通知，避免影响下一次循环选择
                }
            }
            // 重要：必须重置以复用
            timer.Reset(time.Minute)
        }
    }
    ```


```
**【错误示例】**

```
##### 场景1：在循环语句中使用time.After函数。
- 错误示例：

    ```go
    func longRunning(messages <-chan string) {
        for {
            select {
            case <-time.After(time.Minute): // 不符合
                return // 如果某两个连续的消息的间隔大于一分钟，此函数将返回
            case msg := <-messages:
                fmt.Println(msg)
            }
        }
    }
    ```


```
**【修复建议】**

不要在循环语句中使用time.After函数，应该只使用（并复用）一个Timer值。
